# ventas/views.py
"""Vistas de la app ventas — W07.

Lectura: VentaListView y VentaDetailView.
Escritura (crear_venta): W08.
"""# ventas/views.py — agregar imports al inicio:
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import DeleteView, DetailView, ListView

from .forms  import DetalleVentaForm, VentaForm
from .models import DetalleVenta, Venta
from django.views.generic import DetailView, ListView

from .models import Venta

from django.db import transaction as _transaction
from django.forms import inlineformset_factory as _inlineformset_factory
from django.urls import reverse as _reverse

DetalleVentaFormSet = _inlineformset_factory(
    Venta,
    DetalleVenta,
    form=DetalleVentaForm,
    extra=1,
    can_delete=True,
)


def crear_venta(request):
    """Crea un encabezado de venta con uno o más productos."""
    if not request.user.is_authenticated:
        return redirect(f"{settings.LOGIN_URL}?next={request.path}")

    venta_form = VentaForm(request.POST or None)
    formset = DetalleVentaFormSet(request.POST or None, prefix='detalles')

    if request.method == 'POST':
        if 'detalles-TOTAL_FORMS' in request.POST:
            if venta_form.is_valid() and formset.is_valid():
                lineas_validas = [
                    f for f in formset.forms
                    if f.cleaned_data and not f.cleaned_data.get('DELETE', False)
                ]
                if not lineas_validas:
                    formset._non_form_errors = formset.error_class(
                        ['Agrega al menos un producto a la venta.']
                    )
                else:
                    with _transaction.atomic():
                        venta = venta_form.save()
                        for f in lineas_validas:
                            detalle = f.save(commit=False)
                            detalle.venta = venta
                            detalle.save()
                    messages.success(
                        request,
                        f'Venta #{venta.pk} registrada. Total: ${venta.total:.2f}'
                    )
                    return redirect(f"{_reverse('ventas:detalle', args=[venta.pk])}?comprobante=1")
        else:
            detalle_form = DetalleVentaForm(request.POST)
            if venta_form.is_valid() and detalle_form.is_valid():
                with _transaction.atomic():
                    venta = venta_form.save()
                    detalle = detalle_form.save(commit=False)
                    detalle.venta = venta
                    detalle.save()
                messages.success(
                    request,
                    f'Venta #{venta.pk} registrada. Total: ${venta.total:.2f}'
                )
                return redirect(f"{_reverse('ventas:detalle', args=[venta.pk])}?comprobante=1")

    return render(request, 'ventas/crear.html', {
        'venta_form': venta_form,
        'formset': formset,
        'detalle_form': DetalleVentaForm(),
    })

class VentaDeleteView(LoginRequiredMixin, DeleteView):
    """Confirmación y borrado de una venta (y sus detalles en cascada)."""

    model         = Venta
    template_name = 'ventas/eliminar.html'
    pk_url_kwarg  = 'venta_id'
    success_url   = reverse_lazy('ventas:lista')

    def form_valid(self, form):
        pk       = self.object.pk
        response = super().form_valid(form)
        messages.success(self.request, f'Venta #{pk} eliminada.')
        return response


class VentaListView(ListView):
    """Lista paginada de ventas en orden cronológico inverso."""

    model               = Venta
    template_name       = 'ventas/lista.html'
    context_object_name = 'ventas'
    paginate_by         = 20

    def get_queryset(self):
        """Pre-carga cliente para evitar N+1 en la tabla de ventas."""
        return (
            Venta.objects
            .select_related('cliente')
            .order_by('-fecha')
        )


class VentaDetailView(DetailView):
    """Detalle de una venta con todas sus líneas de producto."""

    model               = Venta
    template_name       = 'ventas/detalle.html'
    context_object_name = 'venta'
    pk_url_kwarg        = 'venta_id'

    def get_queryset(self):
        """Pre-carga cliente y prefetch líneas de detalle."""
        return (
            Venta.objects
            .select_related('cliente')
            .prefetch_related('detalles__producto')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comprobante'] = self.request.GET.get('comprobante') == '1'
        return context


# ?? Comprobante PDF de Venta ???????????????????????????????????????????????
from io import BytesIO
from pathlib import Path as _PdfPath
from django.contrib.auth.decorators import login_required as _login_required
from django.contrib.staticfiles import finders as _finders
from django.http import HttpResponse as _HttpResponse
from django.shortcuts import get_object_or_404 as _get_object_or_404
from django.template.loader import render_to_string as _render_to_string
from .models import Venta as _Venta


@_login_required
def venta_pdf(request, venta_id: int) -> _HttpResponse:
    import base64
    from datetime import date
    from decimal import Decimal
    from io import BytesIO as _BytesIO
    from configuracion.models import ConfiguracionERP

    venta = _get_object_or_404(
        _Venta.objects
        .select_related('cliente')
        .prefetch_related('detalles__producto__categoria'),
        pk=venta_id,
    )

    config = ConfiguracionERP.get_instance()

    def _first_attr(obj, names, default=''):
        if not obj:
            return default
        for name in names:
            val = getattr(obj, name, None)
            if callable(val):
                try:
                    val = val()
                except Exception:
                    val = None
            if val not in (None, ''):
                return val
        return default

    # Convertir logo de la empresa a Base64 para que se muestre tanto en xhtml2pdf como en WeasyPrint
    logo_data_uri = ''
    logo_field = getattr(config, 'logo', None)
    if logo_field:
        try:
            with logo_field.open('rb') as f:
                raw = f.read()
            ext = str(getattr(logo_field, 'name', '')).lower().split('.')[-1]
            mime = 'image/jpeg' if ext in ('jpg', 'jpeg') else ('image/webp' if ext == 'webp' else 'image/png')
            logo_data_uri = f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
        except Exception:
            logo_data_uri = ''

    empresa = {
        'nombre': _first_attr(config, ['nombre_empresa', 'razon_social', 'nombre', 'titulo'], 'Dandelion Star'),
        'rfc': _first_attr(config, ['rfc', 'tax_id', 'nit', 'cif']),
        'direccion': _first_attr(config, ['direccion', 'domicilio', 'ubicacion', 'sucursal']),
        'ciudad': _first_attr(config, ['ciudad', 'municipio', 'estado', 'pais']),
        'telefono': _first_attr(config, ['telefono', 'celular', 'whatsapp']),
        'email': _first_attr(config, ['email', 'correo', 'correo_electronico']),
        'sitio_web': _first_attr(config, ['sitio_web', 'web', 'pagina_web']),
        'leyenda': _first_attr(
            config,
            ['pie_pagina', 'mensaje_ticket', 'leyenda', 'notas_factura'],
            'Gracias por su compra. Este documento sirve como comprobante oficial de la operación.',
        ),
        'moneda': _first_attr(config, ['simbolo_moneda', 'moneda'], '),
        'logo_data_uri': logo_data_uri,
    }

    cliente_obj = getattr(venta, 'cliente', None)
    cliente_info = {
        'nombre': _first_attr(cliente_obj, ['nombre_completo', 'nombre', 'razon_social'], 'Público en General'),
        'telefono': _first_attr(cliente_obj, ['telefono', 'celular']),
        'email': _first_attr(cliente_obj, ['email', 'correo']),
        'direccion': _first_attr(cliente_obj, ['direccion', 'domicilio', 'ciudad']),
        'rfc': _first_attr(cliente_obj, ['rfc', 'tax_id']),
    }

    items_pdf = []
    subtotal_calc = Decimal('0.00')
    for idx, d in enumerate(venta.detalles.all(), start=1):
        prod = getattr(d, 'producto', None)
        cant = Decimal(str(getattr(d, 'cantidad', 1) or 1))
        precio = Decimal(str(_first_attr(d, ['precio_unitario', 'precio'], '0.00')))
        sub_attr = getattr(d, 'subtotal', None)
        if callable(sub_attr):
            sub_attr = sub_attr()
        sub = Decimal(str(sub_attr)) if sub_attr not in (None, '') else (cant * precio)
        subtotal_calc += sub

        cat_obj = getattr(prod, 'categoria', None)
        items_pdf.append({
            'num': idx,
            'nombre': _first_attr(prod, ['nombre', 'titulo'], f'Producto #{idx}'),
            'sku': _first_attr(prod, ['sku', 'codigo', 'referencia']),
            'categoria': _first_attr(cat_obj, ['nombre'], str(cat_obj) if cat_obj else ''),
            'cantidad': getattr(d, 'cantidad', 1),
            'precio_unitario': precio,
            'subtotal': sub,
        })

    total_venta = getattr(venta, 'total', None)
    if callable(total_venta):
        total_venta = total_venta()
    total_final = Decimal(str(total_venta)) if total_venta not in (None, '') else subtotal_calc

    subtotal_venta = getattr(venta, 'subtotal', None)
    if callable(subtotal_venta):
        subtotal_venta = subtotal_venta()
    subtotal_final = Decimal(str(subtotal_venta)) if subtotal_venta not in (None, '') else subtotal_calc

    impuestos_final = Decimal(str(_first_attr(venta, ['iva', 'impuestos', 'impuesto'], '0.00')))
    descuento_final = Decimal(str(_first_attr(venta, ['descuento'], '0.00')))

    venta_info = {
        'folio': f"{venta.pk:05d}",
        'fecha': _first_attr(venta, ['fecha', 'fecha_creacion', 'created_at']),
        'estado': _first_attr(venta, ['get_estado_display', 'estado', 'estatus'], 'Completada'),
        'metodo_pago': _first_attr(venta, ['get_metodo_pago_display', 'metodo_pago', 'forma_pago'], 'Contado / Registrado'),
        'lugar': _first_attr(venta, ['sucursal', 'ubicacion', 'lugar']) or empresa['direccion'] or empresa['ciudad'] or 'Matriz / Punto de Venta',
        'notas': _first_attr(venta, ['notas', 'observaciones', 'comentarios']),
        'subtotal': subtotal_final,
        'impuestos': impuestos_final,
        'descuento': descuento_final,
        'total': total_final,
    }

    context = {
        'venta': venta,
        'config': config,
        'hoy': date.today(),
        'empresa': empresa,
        'cliente_info': cliente_info,
        'items_pdf': items_pdf,
        'venta_info': venta_info,
    }

    html_string = _render_to_string(
        'ventas/factura_pdf.html',
        context,
        request=request,
    )

    try:
        import weasyprint
        pdf_bytes = weasyprint.HTML(
            string=html_string,
            base_url=request.build_absolute_uri('/'),
        ).write_pdf()
    except (ImportError, OSError):
        from xhtml2pdf import pisa
        pdf_buffer = _BytesIO()
        pisa_status = pisa.CreatePDF(
            html_string,
            dest=pdf_buffer,
            encoding='utf-8',
        )
        if pisa_status.err:
            return _HttpResponse('Error al generar el comprobante PDF.', status=500)
        pdf_bytes = pdf_buffer.getvalue()

    response = _HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="comprobante_compra_{venta.pk:05d}.pdf"'
    )
    return response
