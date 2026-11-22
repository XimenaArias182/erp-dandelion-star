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

def crear_venta(request):
    """Crea un encabezado de venta con una línea de detalle.

    GET  → muestra los dos formularios vacíos.
    POST → valida ambos, guarda si correctos, muestra errores si no.

    Protección: redirige a login si no autenticado.
    Nota: para múltiples líneas usar formsets (implementar en Espiral 5).
    """
    if not request.user.is_authenticated:
        return redirect(
            f"{settings.LOGIN_URL}?next={request.path}"
        )

    venta_form   = VentaForm(request.POST or None)
    detalle_form = DetalleVentaForm(request.POST or None)

    if request.method == 'POST':
        if venta_form.is_valid() and detalle_form.is_valid():
            venta          = venta_form.save()
            detalle        = detalle_form.save(commit=False)
            detalle.venta  = venta
            # precio_unitario se auto-captura en save() si es None
            detalle.save()
            messages.success(
                request,
                f'Venta #{venta.pk} registrada. '
                f'Total: ${venta.total:.2f}'
            )
            from django.urls import reverse as _reverse
            return redirect(f"{_reverse('ventas:detalle', args=[venta.pk])}?comprobante=1")

    return render(request, 'ventas/crear.html', {
        'venta_form':   venta_form,
        'detalle_form': detalle_form,
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
    import weasyprint
    from datetime import date
    from configuracion.models import ConfiguracionERP

    venta = _get_object_or_404(
        _Venta.objects
        .select_related('cliente')
        .prefetch_related('detalles__producto__categoria'),
        pk=venta_id,
    )

    config = ConfiguracionERP.get_instance()
    context = {
        'venta': venta,
        'config': config,
        'hoy': date.today(),
    }

    html_string = _render_to_string(
        'ventas/factura_pdf.html',
        context,
        request=request,
    )

    pdf_bytes = weasyprint.HTML(
        string=html_string,
        base_url=request.build_absolute_uri('/'),
    ).write_pdf()

    response = _HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="factura_{venta.pk:05d}.pdf"'
    )
    return response

