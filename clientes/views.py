from django.contrib.auth.decorators import login_required
# clientes/views.py
"""Vistas de la app clientes con control de acceso RBAC."""
from django.contrib import messages
from core.mixins import ERPAuthPermissionMixin
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView
)

from .forms import ClienteForm
from .models import Cliente


class ClienteListView(ListView):
    """Lista paginada de clientes activos."""

    model = Cliente
    template_name = 'clientes/lista.html'
    context_object_name = 'clientes'
    paginate_by = 20

    def get_queryset(self):
        return Cliente.objects.filter(activo=True).order_by('nombre')


class ClienteDetailView(DetailView):
    """Detalle de un cliente."""

    model = Cliente
    template_name = 'clientes/detalle.html'
    context_object_name = 'cliente'


class ClienteCreateView(ERPAuthPermissionMixin, CreateView):
    """Formulario para crear un nuevo cliente."""

    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/crear.html'
    permission_required = 'clientes.add_cliente'
    raise_exception = True
    success_url = reverse_lazy('clientes:lista')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f'Cliente "{self.object.nombre}" creado exitosamente.'
        )
        return response


class ClienteUpdateView(ERPAuthPermissionMixin, UpdateView):
    """Formulario para editar un cliente."""

    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/editar.html'
    permission_required = 'clientes.change_cliente'
    raise_exception = True
    success_url = reverse_lazy('clientes:lista')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f'Cliente "{self.object.nombre}" actualizado.'
        )
        return response


class ClienteDeleteView(ERPAuthPermissionMixin, DeleteView):
    """Confirmación y borrado de un cliente."""

    model = Cliente
    template_name = 'clientes/eliminar.html'
    permission_required = 'clientes.delete_cliente'
    raise_exception = True
    success_url = reverse_lazy('clientes:lista')

    def form_valid(self, form):
        nombre = self.object.nombre
        response = super().form_valid(form)
        messages.success(self.request, f'Cliente "{nombre}" eliminado.')
        return response

def ds_lista_clientes(request):
    from django.shortcuts import render
    from .models import Cliente
    qs = Cliente.objects.all().order_by('-id')
    return render(
        request,
        'clientes/lista.html',
        {
            'clientes': qs,
            'cliente_list': qs,
            'object_list': qs,
        }
    )


@login_required
def ds_guardar_cliente(request, pk=None, cliente_id=None):
    from django.db import IntegrityError, transaction
    from django.shortcuts import get_object_or_404, redirect, render
    from .models import Cliente

    obj_id = pk or cliente_id
    cliente = get_object_or_404(Cliente, pk=obj_id) if obj_id else None
    error_msg = None

    fk_choices = {}
    for f in Cliente._meta.fields:
        if not f.primary_key and f.editable and f.is_relation and f.many_to_one:
            fk_choices[f.name] = list(f.related_model.objects.all()[:200])

    if request.method == 'POST':
        inst = cliente if cliente else Cliente()
        for f in Cliente._meta.fields:
            if f.primary_key or not f.editable:
                continue
            ftype = f.get_internal_type()
            if ftype in ('ImageField', 'FileField'):
                continue
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
            with transaction.atomic():

                inst.save()
            return redirect('clientes:lista')
        except IntegrityError as exc:
            err_lower = str(exc).lower()
            if 'correo' in err_lower or 'email' in err_lower:
                error_msg = 'Este correo ya existe en el sistema. Ingresa un correo diferente.'
            elif 'rfc' in err_lower or 'curp' in err_lower:
                error_msg = 'Ya existe un cliente registrado con ese identificador fiscal.'
            else:
                error_msg = 'Ya existe un cliente registrado con alguno de los datos ingresados.'
            cliente = inst
        except Exception as exc:
            error_msg = f'No se pudo guardar el cliente: {exc}'
            cliente = inst

    return render(
        request,
        'clientes/form_cliente.html',
        {'cliente': cliente, 'error_msg': error_msg, 'fk_choices': fk_choices}
    )


def ds_eliminar_cliente(request, pk=None, cliente_id=None):
    from django.shortcuts import get_object_or_404, redirect
    from .models import Cliente
    obj_id = pk or cliente_id
    cliente = get_object_or_404(Cliente, pk=obj_id)
    if request.method == 'POST':
        cliente.delete()
    return redirect('clientes:lista')


