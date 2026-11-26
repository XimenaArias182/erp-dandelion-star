import traceback
"""Vistas del módulo de catálogo, carrito y checkout — W13 a W16."""
from decimal import Decimal

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView

from clientes.models import Cliente
from productos.models import Producto
from ventas.models import Pedido
from ventas.tasks import enviar_confirmacion_pedido

from .checkout_utils import (
    calcular_totales,
    generar_numero_pedido,
    obtener_o_crear_cliente,
)
from .filters import ProductoFilter

stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', 'sk_test_placeholder')


# ── CATÁLOGO (W13) ──────────────────────────────────────────────────────────

class CatalogoView(ListView):
    """Catálogo público de productos con filtros."""

    model = Producto
    template_name = 'catalogo/catalogo.html'
    context_object_name = 'productos'
    paginate_by = 12

    def get_queryset(self):
        qs = (
            Producto.objects
            .select_related('categoria', 'proveedor')
            .filter(activo=True)
            .order_by('nombre')
        )
        self.filtro = ProductoFilter(self.request.GET, queryset=qs)
        return self.filtro.qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filtro'] = self.filtro
        ctx['categorias'] = self.filtro.form.fields['categoria'].queryset
        return ctx


# ── CARRITO EN SESIÓN (W13) ─────────────────────────────────────────────────

def _obtener_carrito(request) -> dict:
    return request.session.get('carrito', {})


def _guardar_carrito(request, carrito: dict) -> None:
    request.session['carrito'] = carrito
    request.session.modified = True


def ver_carrito(request):
    """Muestra el contenido del carrito con el total calculado."""
    carrito = _obtener_carrito(request)
    items = []
    total = Decimal('0.00')

    for prod_id, datos in carrito.items():
        precio = Decimal(datos['precio'])
        cantidad = int(datos['cantidad'])
        subtotal = precio * cantidad
        total += subtotal
        items.append({
            'prod_id': prod_id,
            'nombre': datos['nombre'],
            'precio': precio,
            'cantidad': cantidad,
            'subtotal': subtotal,
            'imagen': datos.get('imagen'),
        })

    return render(request, 'catalogo/carrito.html', {
        'items': items,
        'total': total,
    })


def agregar_al_carrito(request, producto_id: int):
    """Agrega un producto al carrito o incrementa su cantidad."""
    if request.method != 'POST':
        return redirect('catalogo:catalogo')

    producto = get_object_or_404(Producto, pk=producto_id, activo=True)
    carrito = _obtener_carrito(request)

    clave = str(producto_id)
    cantidad = int(request.POST.get('cantidad', 1))

    if clave in carrito:
        carrito[clave]['cantidad'] += cantidad
    else:
        img_name = None
        if getattr(producto, 'imagen', None):
            try:
                img_name = producto.imagen.url
            except Exception:
                img_name = producto.imagen.name
        carrito[clave] = {
            'nombre': producto.nombre,
            'precio': str(producto.precio),
            'cantidad': cantidad,
            'imagen': img_name,
        }

    _guardar_carrito(request, carrito)
    messages.success(request, f'"{producto.nombre}" agregado al carrito.')

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    return redirect(next_url or 'catalogo:catalogo')


def remover_del_carrito(request, producto_id: int):
    """Elimina un producto del carrito."""
    if request.method != 'POST':
        return redirect('catalogo:carrito')

    carrito = _obtener_carrito(request)
    clave = str(producto_id)

    nombre = carrito.get(clave, {}).get('nombre', 'Producto')
    carrito.pop(clave, None)
    _guardar_carrito(request, carrito)

    messages.warning(request, f'"{nombre}" eliminado del carrito.')
    return redirect('catalogo:carrito')


def actualizar_cantidad(request, producto_id: int):
    """Actualiza la cantidad de un producto en el carrito."""
    if request.method != 'POST':
        return redirect('catalogo:carrito')

    carrito = _obtener_carrito(request)
    clave = str(producto_id)
    cantidad = int(request.POST.get('cantidad', 1))

    if clave in carrito:
        if cantidad > 0:
            carrito[clave]['cantidad'] = cantidad
        else:
            carrito.pop(clave)

    _guardar_carrito(request, carrito)
    return redirect('catalogo:carrito')


def vaciar_carrito(request):
    """Elimina todos los productos del carrito."""
    if request.method == 'POST':
        _guardar_carrito(request, {})
        messages.info(request, 'Carrito vaciado.')
    return redirect('catalogo:carrito')


# ── CHECKOUT CON STRIPE (W14 + W15 + W16) ───────────────────────────────────

@login_required
def checkout(request):
    """Proceso de pago: selecciona o registra cliente con correo y crea PaymentIntent."""
    carrito = _obtener_carrito(request)
    if not carrito:
        messages.warning(request, 'Tu carrito está vacío.')
        return redirect('catalogo:catalogo')

    totales = calcular_totales(carrito)
    publishable_key = getattr(settings, 'STRIPE_PUBLISHABLE_KEY', 'pk_test_placeholder')
    stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', 'sk_test_placeholder')
    clientes = Cliente.objects.filter(activo=True).order_by('nombre')

    carrito_vista = {
        k: {
            **v,
            'subtotal': f"{Decimal(str(v.get('precio', 0))) * int(v.get('cantidad', 1)):.2f}"
        }
        for k, v in carrito.items()
    }

    if request.method == 'POST':
        modo_cliente = request.POST.get('modo_cliente', 'nuevo')
        cliente_id = request.POST.get('cliente_id', '').strip()
        nombre_nuevo = request.POST.get('nuevo_nombre', '').strip()
        correo_nuevo = request.POST.get('nuevo_correo', '').strip().lower()
        telefono_nuevo = request.POST.get('nuevo_telefono', '').strip()

        cliente = None

        if modo_cliente == 'existente' and cliente_id:
            cliente = Cliente.objects.filter(pk=cliente_id, activo=True).first()
            if not cliente:
                messages.error(request, 'El cliente seleccionado no es válido.')
                return render(request, 'catalogo/checkout.html', {
                    'carrito': carrito_vista,
                    'totales': totales,
                    'clientes': clientes,
                    'client_secret': None,
                    'publishable_key': publishable_key,
                })
        elif modo_cliente == 'nuevo':
            if not nombre_nuevo or not correo_nuevo:
                messages.error(request, 'Ingresa el nombre y el correo electrónico del cliente para enviarle su confirmación.')
                return render(request, 'catalogo/checkout.html', {
                    'carrito': carrito_vista,
                    'totales': totales,
                    'clientes': clientes,
                    'client_secret': None,
                    'publishable_key': publishable_key,
                })
            cliente, creado = Cliente.objects.get_or_create(
                correo=correo_nuevo,
                defaults={
                    'nombre': nombre_nuevo,
                    'telefono': telefono_nuevo,
                    'activo': True,
                }
            )
            if not creado:
                cliente.nombre = nombre_nuevo
                if telefono_nuevo:
                    cliente.telefono = telefono_nuevo
                cliente.activo = True
                cliente.save()
        else:
            cliente = obtener_o_crear_cliente(request.user)

        try:
            numero = generar_numero_pedido()

            snapshot = [
                {
                    'producto_id': int(prod_id),
                    'nombre': datos['nombre'],
                    'cantidad': int(datos['cantidad']),
                    'precio': datos['precio'],
                }
                for prod_id, datos in carrito.items()
            ]

            pedido = Pedido.objects.create(
                numero_pedido=numero,
                cliente=cliente,
                estado='pendiente',
                total_pagado=totales['total'],
                items_snapshot=snapshot,
            )

            monto_centavos = int(totales['total'] * 100)

            intent = stripe.PaymentIntent.create(
                amount=monto_centavos,
                currency='mxn',
                receipt_email=cliente.correo,
                metadata={
                    'pedido_id': pedido.pk,
                    'pedido_num': pedido.numero_pedido,
                    'cliente': cliente.nombre,
                    'cliente_correo': cliente.correo,
                },
                idempotency_key=f'pedido-{pedido.pk}',
            )

            return render(request, 'catalogo/checkout.html', {
                'carrito': carrito_vista,
                'totales': totales,
                'clientes': clientes,
                'pedido': pedido,
                'client_secret': intent.client_secret,
                'publishable_key': publishable_key,
            })

        except stripe.error.StripeError as exc:
            messages.error(
                request,
                f'Error al conectar con Stripe: {getattr(exc, "user_message", str(exc))}'
            )
            return redirect('catalogo:pago_error')

        except Exception as exc:
            print('CHECKOUT_ERROR:', traceback.format_exc(), flush=True)
            messages.error(
                request,
                f'Error inesperado en el proceso de pago: {exc}'
            )
            return redirect('catalogo:pago_error')

    return render(request, 'catalogo/checkout.html', {
        'carrito': carrito_vista,
        'totales': totales,
        'clientes': clientes,
        'client_secret': None,
        'publishable_key': publishable_key,
    })


def pago_exitoso(request, pedido_id: int):
    """Confirma el pedido, descuenta stock, registra Venta y envía correo sin webhook."""
    from django.db import transaction
    from .webhook_views import _descontar_stock, _registrar_venta
    from ventas.tasks import enviar_correo_pedido_inmediato

    pedido = get_object_or_404(Pedido, pk=pedido_id)
    _guardar_carrito(request, {})

    if pedido.estado != 'pagado':
        with transaction.atomic():
            pedido.estado = 'pagado'
            pedido.save(update_fields=['estado'])
            _descontar_stock(pedido)
            _registrar_venta(pedido)

        enviar_correo_pedido_inmediato(pedido)
        try:
            enviar_confirmacion_pedido.delay(pedido.pk)
        except Exception as _celery_err:
            print('CELERY_BROKER_WARN:', _celery_err, flush=True)

    messages.success(
        request,
        f'¡Pago exitoso! Tu pedido {pedido.numero_pedido} '
        f'está confirmado. Se envió confirmación a {pedido.cliente.correo}.'
    )

    return render(request, 'catalogo/pago_exitoso.html', {
        'pedido': pedido,
    })

def pago_error(request):
    """Vista de error de pago."""
    return render(request, 'catalogo/pago_error.html')