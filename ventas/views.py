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
    import weasyprint
    from datetime import date
    from django.conf import settings
    from django.http import HttpResponse
    from django.shortcuts import get_object_or_404
    from django.template.loader import render_to_string
    from configuracion.models import ConfiguracionERP
    from .models import Venta

    venta = get_object_or_404(
        Venta.objects
        .select_related('cliente')
        .prefetch_related('detalles__producto__categoria'),
        pk=venta_id
    )

    config = ConfiguracionERP.get_instance()
    context = {
        'venta': venta,
        'config': config,
        'hoy': date.today(),
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
