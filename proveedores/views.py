from django.contrib.auth.decorators import login_required
# proveedores/views.py
"""Vistas de la app proveedores — W07.

Lectura: ListView y DetailView.
"""
# proveedores/views.py — agregar imports al inicio:
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView
)
from .forms import ProveedorForm
from django.views.generic import DetailView, ListView

from .models import Proveedor


class ProveedorListView(ListView):
    """Lista paginada de proveedores activos."""

    model               = Proveedor
    template_name       = 'proveedores/lista.html'
    context_object_name = 'proveedores'
    paginate_by         = 20

    def get_queryset(self):
        return Proveedor.objects.filter(activo=True).order_by('nombre')


class ProveedorDetailView(DetailView):
    """Detalle de un proveedor con sus productos asociados."""

    model               = Proveedor
    template_name       = 'proveedores/detalle.html'
    context_object_name = 'proveedor'
    pk_url_kwarg        = 'proveedor_id'

    def get_context_data(self, **kwargs):
        """Agrega los productos del proveedor al contexto."""
        ctx = super().get_context_data(**kwargs)
        ctx['productos'] = (
            self.object.productos
            .select_related('categoria')
            .filter(activo=True)
            .order_by('nombre')
        )
        return ctx
    
class ProveedorCreateView(LoginRequiredMixin, CreateView):
    """Formulario para crear un proveedor."""

    model         = Proveedor
    form_class    = ProveedorForm
    template_name = 'proveedores/crear.html'
    success_url   = reverse_lazy('proveedores:lista')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f'Proveedor "{self.object.nombre}" creado exitosamente.'
        )
        return response


class ProveedorUpdateView(LoginRequiredMixin, UpdateView):
    """Formulario para editar un proveedor."""

    model         = Proveedor
    form_class    = ProveedorForm
    template_name = 'proveedores/editar.html'
    pk_url_kwarg  = 'proveedor_id'
    success_url   = reverse_lazy('proveedores:lista')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f'Proveedor "{self.object.nombre}" actualizado.'
        )
        return response


class ProveedorDeleteView(LoginRequiredMixin, DeleteView):
    """Confirmación y borrado de un proveedor."""

    model         = Proveedor
    template_name = 'proveedores/eliminar.html'
    pk_url_kwarg  = 'proveedor_id'
    success_url   = reverse_lazy('proveedores:lista')

    def form_valid(self, form):
        nombre   = self.object.nombre
        response = super().form_valid(form)
        messages.success(self.request, f'Proveedor "{nombre}" eliminado.')
        return response

def _ds_sanitizar_archivo(archivo):
    import os
    import uuid
    ext = os.path.splitext(archivo.name)[1].lower()
    if ext not in ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg'):
        ext = '.png'
    archivo.name = f"prov_{uuid.uuid4().hex[:12]}{ext}"
    return archivo


def subir_logo_proveedor(request, pk=None, proveedor_id=None):
    from django.shortcuts import get_object_or_404, redirect
    from .models import Proveedor
    obj_id = pk or proveedor_id
    proveedor = get_object_or_404(Proveedor, pk=obj_id)
    if request.method == 'POST':
        archivo = request.FILES.get('logo') or request.FILES.get('logo')
        if archivo:
            setattr(proveedor, 'logo', _ds_sanitizar_archivo(archivo))
            proveedor.save()
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('proveedores:lista')


@login_required
def ds_guardar_proveedor(request, pk=None, proveedor_id=None):
    from django.db import IntegrityError
    from django.shortcuts import get_object_or_404, redirect, render
    from .models import Proveedor

    obj_id = pk or proveedor_id
    proveedor = get_object_or_404(Proveedor, pk=obj_id) if obj_id else None
    error_msg = None

    fk_choices = {}
    for f in Proveedor._meta.fields:
        if not f.primary_key and f.editable and f.is_relation and f.many_to_one:
            fk_choices[f.name] = list(f.related_model.objects.all()[:200])

    if request.method == 'POST':
        inst = proveedor if proveedor else Proveedor()
        for f in Proveedor._meta.fields:
            if f.primary_key or not f.editable:
                continue
            ftype = f.get_internal_type()
            if ftype in ('ImageField', 'FileField'):
                archivo = request.FILES.get(f.name)
                if archivo:
                    setattr(inst, f.name, _ds_sanitizar_archivo(archivo))
            elif ftype == 'BooleanField':
                if f.name in request.POST:
                    setattr(inst, f.name, request.POST.get(f.name) in ('on', 'true', 'True', '1'))
                elif f'__bool_{f.name}' in request.POST:
                    setattr(inst, f.name, False)
            elif f.is_relation and f.many_to_one:
                val = request.POST.get(f.name, '').strip()
                if val == '':
                    setattr(inst, f.attname, None)
                elif val.isdigit():
                    setattr(inst, f.attname, int(val))
                else:
                    setattr(inst, f.attname, val)
            elif f.name in request.POST:
                val = request.POST.get(f.name, '').strip()
                if val == '' and f.null:
                    val = None
                setattr(inst, f.name, val)
        try:
            inst.save()
            return redirect('proveedores:lista')
        except IntegrityError as exc:
            err_lower = str(exc).lower()
            if 'correo' in err_lower or 'email' in err_lower:
                error_msg = 'Ya existe un proveedor registrado con ese correo electrónico. Ingresa un correo diferente.'
            elif 'nombre' in err_lower:
                error_msg = 'Ya existe un proveedor registrado con ese nombre.'
            else:
                error_msg = f'Dato duplicado: {exc}'
            proveedor = inst
        except Exception as exc:
            error_msg = f'No se pudo guardar el proveedor: {exc}'
            proveedor = inst

    return render(
        request,
        'proveedores/form_proveedor.html',
        {'proveedor': proveedor, 'error_msg': error_msg, 'fk_choices': fk_choices}
    )


def ds_lista_proveedores(request):
    from django.shortcuts import render
    from .models import Proveedor
    qs = Proveedor.objects.all().order_by('-id')
    return render(
        request,
        'proveedores/lista.html',
        {
            'proveedores': qs,
            'proveedor_list': qs,
            'object_list': qs,
        }
    )

