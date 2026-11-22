# productos/views.py
"""Vistas de la app productos con control de acceso RBAC."""
from django.contrib import messages
from core.mixins import ERPAuthPermissionMixin
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView
)

from .forms import ProductoForm
from .models import Producto
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from openpyxl import Workbook

from .models import Producto


@login_required
def exportar_excel(request):
    """Exporta el inventario de productos a un archivo .xlsx."""
    wb = Workbook()
    ws = wb.active
    ws.title = 'Inventario'
    ws.append(['ID', 'Nombre', 'Categoría', 'Precio', 'Stock'])

    for p in Producto.objects.select_related('categoria'):
        ws.append([
            p.pk,
            p.nombre,
            p.categoria.nombre if p.categoria else '',
            float(p.precio),
            p.stock,
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="inventario.xlsx"'
    wb.save(response)
    return response


class ProductoListView(ListView):
    """Lista paginada de productos activos."""

    model = Producto
    template_name = 'productos/lista.html'
    context_object_name = 'productos'
    paginate_by = 20

    def get_queryset(self):
        return (
            Producto.objects
            .select_related('categoria', 'proveedor')
            .filter(activo=True)
            .order_by('nombre')
        )


class ProductoDetailView(DetailView):
    """Detalle de un producto por ID."""

    model = Producto
    template_name = 'productos/detalle.html'
    context_object_name = 'producto'

    def get_queryset(self):
        return Producto.objects.select_related('categoria', 'proveedor')


class ProductoCreateView(ERPAuthPermissionMixin, CreateView):
    """Formulario para crear un nuevo producto."""

    model = Producto
    form_class = ProductoForm
    template_name = 'productos/crear.html'
    permission_required = 'productos.add_producto'
    raise_exception = True
    success_url = reverse_lazy('productos:lista')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f'Producto "{self.object.nombre}" creado exitosamente.'
        )
        return response


class ProductoUpdateView(ERPAuthPermissionMixin, UpdateView):
    """Formulario para editar un producto existente."""

    model = Producto
    form_class = ProductoForm
    template_name = 'productos/editar.html'
    permission_required = 'productos.change_producto'
    raise_exception = True
    success_url = reverse_lazy('productos:lista')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f'Producto "{self.object.nombre}" actualizado.'
        )
        return response


class ProductoDeleteView(ERPAuthPermissionMixin, DeleteView):
    """Confirmación y borrado de un producto."""

    model = Producto
    template_name = 'productos/eliminar.html'
    permission_required = 'productos.delete_producto'
    raise_exception = True
    success_url = reverse_lazy('productos:lista')

    def form_valid(self, form):
        nombre = self.object.nombre
        response = super().form_valid(form)
        messages.success(self.request, f'Producto "{nombre}" eliminado.')
        return response

# === VISTAS DE COLORES Y GALERÍA INTERACTIVA DE PRODUCTOS ===
from decimal import Decimal, InvalidOperation
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .models import Producto, ProductoColor, ProductoImagen


def _ds_formatear_precio(valor):
    if valor is None:
        return "0.00"
    try:
        num = Decimal(str(valor).replace(",", "").strip())
        return f"{num:,.2f}"
    except (InvalidOperation, ValueError, TypeError):
        return str(valor)


def _ds_producto_info(prod):
    nombre = getattr(prod, "nombre", None) or getattr(prod, "titulo", None) or getattr(prod, "name", None) or str(prod)
    raw_precio = getattr(prod, "precio", None)
    if raw_precio is None:
        raw_precio = getattr(prod, "precio_venta", None)
    if raw_precio is None:
        raw_precio = getattr(prod, "price", None) or 0
    precio = _ds_formatear_precio(raw_precio)

    stock = getattr(prod, "stock", None)
    if stock is None:
        stock = getattr(prod, "cantidad", None)
    if stock is None:
        stock = getattr(prod, "existencia", 0)

    cat_obj = getattr(prod, "categoria", None)
    cat_nombre = getattr(cat_obj, "nombre", str(cat_obj)) if cat_obj else ""

    prov_obj = getattr(prod, "proveedor", None)
    prov_nombre = getattr(prov_obj, "nombre", str(prov_obj)) if prov_obj else ""

    main_img_url = ""
    for f in prod._meta.fields:
        if f.get_internal_type() in ("FileField", "ImageField"):
            val = getattr(prod, f.name, None)
            if val:
                try:
                    main_img_url = val.url
                    break
                except Exception:
                    pass
    return nombre, precio, raw_precio, stock, cat_nombre, prov_nombre, main_img_url


def producto_detalle_variantes(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    nombre, precio, _, stock, cat_nombre, prov_nombre, main_img_url = _ds_producto_info(producto)

    slides = []
    main_color_obj = None
    colores_qs = list(producto.colores.all())

    for c in colores_qs:
        if not c.imagen_color:
            main_color_obj = c
            break

    if main_img_url:
        slides.append({
            "url": main_img_url,
            "caption": main_color_obj.nombre if main_color_obj else "Diseño principal",
            "color_id": main_color_obj.id if main_color_obj else "main",
            "color_name": main_color_obj.nombre if main_color_obj else "Diseño original",
        })

    colores_data = []
    if main_color_obj and main_img_url:
        colores_data.append({
            "id": main_color_obj.id,
            "nombre": main_color_obj.nombre,
            "thumb_url": main_img_url,
            "slide_index": 0,
            "is_main": True,
        })
    elif main_img_url and colores_qs:
        colores_data.append({
            "id": "main",
            "nombre": "Original",
            "thumb_url": main_img_url,
            "slide_index": 0,
            "is_main": True,
        })

    for c in colores_qs:
        if main_color_obj and c.id == main_color_obj.id:
            continue
        c_url = ""
        if c.imagen_color:
            try:
                c_url = c.imagen_color.url
            except Exception:
                c_url = ""
        thumb = c_url or main_img_url
        slide_idx = 0
        if c_url:
            slide_idx = len(slides)
            slides.append({
                "url": c_url,
                "caption": c.nombre,
                "color_id": c.id,
                "color_name": c.nombre,
            })
        colores_data.append({
            "id": c.id,
            "nombre": c.nombre,
            "thumb_url": thumb,
            "slide_index": slide_idx,
            "is_main": False,
        })

    for img in producto.imagenes_extra.all():
        try:
            i_url = img.imagen.url
            slides.append({
                "url": i_url,
                "caption": img.titulo.strip() if img.titulo else "Vista del diseño",
                "color_id": img.color_id or "",
                "color_name": img.color.nombre if img.color else "",
            })
        except Exception:
            pass

    return render(request, "productos/producto_detalle_variantes.html", {
        "producto": producto,
        "producto_nombre": nombre,
        "producto_precio": precio,
        "producto_stock": stock,
        "categoria_nombre": cat_nombre,
        "proveedor_nombre": prov_nombre,
        "slides": slides,
        "colores": colores_data,
        "back_url": "/productos/",
        "edit_url": f"/productos/{pk}/editar/",
    })


@require_POST
def producto_agregar_color(request, pk):
    return redirect("producto_detalle_variantes", pk=pk)


@require_POST
def producto_eliminar_color(request, pk, color_id):
    color = get_object_or_404(ProductoColor, pk=color_id, producto_id=pk)
    color.delete()
    return redirect("producto_detalle_variantes", pk=pk)


@require_POST
def producto_agregar_imagenes(request, pk):
    return redirect("producto_detalle_variantes", pk=pk)


@require_POST
def producto_eliminar_imagen(request, pk, img_id):
    img = get_object_or_404(ProductoImagen, pk=img_id, producto_id=pk)
    img.delete()
    return redirect("producto_detalle_variantes", pk=pk)


def api_catalogo_variantes(request):
    data = {}
    for prod in Producto.objects.prefetch_related("colores", "imagenes_extra").all():
        nombre, precio_fmt, raw_precio, stock, _, _, main_img = _ds_producto_info(prod)
        imgs = [main_img] if main_img else []
        colores = []
        for c in prod.colores.all():
            c_img = ""
            if c.imagen_color:
                try:
                    c_img = c.imagen_color.url
                    if c_img not in imgs:
                        imgs.append(c_img)
                except Exception:
                    pass
            colores.append({
                "id": c.id,
                "nombre": c.nombre,
                "imagen": c_img or main_img,
            })
        for ex in prod.imagenes_extra.all():
            try:
                u = ex.imagen.url
                if u not in imgs:
                    imgs.append(u)
            except Exception:
                pass
        try:
            stock_num = int(stock or 0)
        except Exception:
            stock_num = 0
        try:
            precio_num = float(str(raw_precio).replace(",", ""))
        except Exception:
            precio_num = 0.0

        data[str(prod.pk)] = {
            "nombre": nombre,
            "precio": precio_num,
            "precio_formateado": precio_fmt,
            "stock": stock_num,
            "detalle_url": f"/productos/{prod.pk}/vista/",
            "imagenes": imgs,
            "colores": colores,
            "extras": [{"id": ex.id, "url": ex.imagen.url} for ex in prod.imagenes_extra.all() if ex.imagen],
        }
    return JsonResponse(data)
