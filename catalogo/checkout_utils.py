"""Funciones auxiliares para el proceso de checkout — W14."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from clientes.models import Cliente
from configuracion.models import ConfiguracionERP
from ventas.models import Pedido


def calcular_totales(carrito: dict) -> dict:
    """Calcula subtotal, IVA y total del carrito."""
    config = ConfiguracionERP.get_instance()
    raw_iva = getattr(config, 'iva_porcentaje', Decimal('16.00'))
    iva_pct_val = Decimal(str(raw_iva if raw_iva is not None else '16.00'))
    iva_pct = iva_pct_val / Decimal('100')

    subtotal = sum(
        Decimal(datos['precio']) * int(datos['cantidad'])
        for datos in carrito.values()
    )
    iva_monto = (subtotal * iva_pct).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )
    total = subtotal + iva_monto

    return {
        'subtotal': subtotal,
        'iva_pct': iva_pct_val,
        'iva_monto': iva_monto,
        'total': total,
    }


def obtener_o_crear_cliente(user) -> Cliente:
    """Obtiene o crea un Cliente del ERP vinculado al usuario Django."""
    correo = user.email or f"{user.username}@erp.local"
    nombre = user.get_full_name() or user.username

    cliente, _ = Cliente.objects.get_or_create(
        correo=correo,
        defaults={'nombre': nombre, 'activo': True}
    )
    if cliente.nombre != nombre and user.get_full_name():
        cliente.nombre = nombre
        cliente.save(update_fields=['nombre'])

    return cliente


def generar_numero_pedido() -> str:
    """Genera un número de pedido único con formato PED-YYYY-NNNN."""
    anio = date.today().year
    siguiente = Pedido.objects.filter(
        numero_pedido__startswith=f'PED-{anio}-'
    ).count() + 1
    numero = f'PED-{anio}-{siguiente:04d}'
    while Pedido.objects.filter(numero_pedido=numero).exists():
        siguiente += 1
        numero = f'PED-{anio}-{siguiente:04d}'
    return numero
