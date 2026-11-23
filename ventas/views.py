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


from django.contrib.auth.decorators import login_required
from django.http import HttpResponse


@login_required
def venta_pdf(request, venta_id: int) -> HttpResponse:
    """Genera y descarga la factura de una venta en formato PDF con WeasyPrint."""
    import base64
    from decimal import Decimal
    from pathlib import Path
    import weasyprint
    from django.conf import settings
    from django.contrib.staticfiles import finders
    from django.http import HttpResponse
    from django.shortcuts import get_object_or_404
    from django.template.loader import render_to_string
    from django.utils import timezone
    from configuracion.models import ConfiguracionERP
    from .models import Venta

    venta = get_object_or_404(
        Venta.objects
        .select_related('cliente')
        .prefetch_related('detalles__producto__categoria'),
        pk=venta_id
    )

    config = ConfiguracionERP.get_instance()
    ahora = timezone.localtime(timezone.now())
    fecha_doc = getattr(venta, 'fecha', None) or ahora

    cliente = getattr(venta, 'cliente', None)
    cliente_nombre = getattr(cliente, 'nombre', '') if cliente else 'Público General'
    cliente_domicilio = (
        getattr(cliente, 'direccion', '')
        or getattr(cliente, 'domicilio', '')
        or ''
    ) if cliente else ''
    cliente_email = getattr(cliente, 'email', '') or getattr(cliente, 'correo', '') if cliente else ''
    cliente_telefono = getattr(cliente, 'telefono', '') or getattr(cliente, 'celular', '') if cliente else ''

    # Buscar logo en ConfiguracionERP o en archivos estáticos
    logo_src = ''
    logo_field = getattr(config, 'logo', None)
    if logo_field and getattr(logo_field, 'name', ''):
        try:
            logo_path = Path(logo_field.path)
            if logo_path.exists():
                ext = logo_path.suffix.lstrip('.').lower() or 'png'
                if ext == 'jpg':
                    ext = 'jpeg'
                b64 = base64.b64encode(logo_path.read_bytes()).decode('ascii')
                logo_src = f'data:image/{ext};base64,{b64}'
        except Exception:
            try:
                logo_src = logo_field.url
            except Exception:
                logo_src = ''

    if not logo_src:
        for rel_static in ('img/logo.png', 'img/logo_dandelion.png', 'images/logo.png', 'logo.png'):
            found = finders.find(rel_static)
            if found and Path(found).exists():
                p = Path(found)
                ext = p.suffix.lstrip('.').lower() or 'png'
                b64 = base64.b64encode(p.read_bytes()).decode('ascii')
                logo_src = f'data:image/{ext};base64,{b64}'
                break

    detalles = list(venta.detalles.all())
    filas_vacias = range(max(0, 10 - len(detalles)))

    total_val = Decimal(str(getattr(venta, 'total', 0) or 0))
    subtotal_val = Decimal(str(getattr(venta, 'subtotal', total_val) or total_val))
    impuesto_val = Decimal(str(getattr(venta, 'impuesto', Decimal('0.00')) or Decimal('0.00')))

    empresa_nombre = getattr(config, 'nombre_empresa', '') or 'Dandelion Star'
    if empresa_nombre.strip().lower() in ('mi empresa erp', 'mi empresa'):
        empresa_nombre = 'Dandelion Star'

    empresa_direccion = getattr(config, 'direccion', '') or 'Celaya, Guanajuato, México'
    empresa_telefono = getattr(config, 'telefono', '') or ''
    empresa_web = (
        getattr(config, 'sitio_web', '')
        or getattr(config, 'web', '')
        or 'erp-dandelion-star.onrender.com'
    )
    metodo_pago = getattr(venta, 'metodo_pago', '') or getattr(venta, 'tipo_pago', '') or 'Contado'

    context = {
        'venta': venta,
        'config': config,
        'hoy': ahora,
        'fecha_doc': fecha_doc,
        'cliente_nombre': cliente_nombre,
        'cliente_domicilio': cliente_domicilio,
        'cliente_email': cliente_email,
        'cliente_telefono': cliente_telefono,
        'logo_src': logo_src,
        'detalles': detalles,
        'filas_vacias': filas_vacias,
        'subtotal': subtotal_val,
        'impuesto': impuesto_val,
        'empresa_nombre': empresa_nombre,
        'empresa_direccion': empresa_direccion,
        'empresa_telefono': empresa_telefono,
        'empresa_web': empresa_web,
        'metodo_pago': metodo_pago,
    }

    html_string = render_to_string(
        'ventas/factura_pdf.html',
        context,
        request=request
    )

    base_url = getattr(settings, 'SITE_DOMAIN', request.build_absolute_uri('/'))
    pdf_bytes = weasyprint.HTML(
        string=html_string,
        base_url=base_url,
    ).write_pdf()

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="factura_{venta.pk:05d}.pdf"'
    )
    return response
