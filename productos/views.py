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

# === VISTA EDITORIAL DE PRODUCTO CON VARIANTES DE COLOR E IMAGEN ===
import traceback as _prod_traceback
from decimal import Decimal as _ProdDecimal
from django.contrib import messages as _prod_messages
from django.contrib.auth.decorators import login_required as _prod_login_required
from django.db import connection as _prod_connection
from django.db.models import FileField as _ProdFileField, ForeignKey as _ProdForeignKey
from django.http import Http404 as _ProdHttp404
from django.shortcuts import get_object_or_404 as _prod_get_object_or_404, redirect as _prod_redirect, render as _prod_render
from django.urls import reverse as _prod_reverse
from django.views.decorators.http import require_POST as _prod_require_POST


def _prod_safe_reverse(names, fallback='/'):
    for name in names:
        try:
            return _prod_reverse(name)
        except Exception:
            continue
    return fallback


def _prod_first_attr(obj, names, default=''):
    if not obj:
        return default
    for name in names:
        try:
            val = getattr(obj, name, None)
            if callable(val):
                val = val()
            if val not in (None, ''):
                return val
        except Exception:
            continue
    return default


def _prod_safe_str(obj, default=''):
    if obj in (None, ''):
        return default
    try:
        txt = str(obj).strip()
        return txt if txt else default
    except Exception:
        return default


def _resolve_producto_obj(pk=None, id=None, producto_id=None, slug=None):
    from .models import Producto
    lookup_id = pk if pk is not None else (id if id is not None else producto_id)
    if lookup_id is not None:
        return _prod_get_object_or_404(Producto, pk=lookup_id)
    if slug is not None:
        field_names = {f.name for f in Producto._meta.get_fields()}
        if 'slug' in field_names:
            return _prod_get_object_or_404(Producto, slug=slug)
        if str(slug).isdigit():
            return _prod_get_object_or_404(Producto, pk=int(slug))
    raise _ProdHttp404('Producto no encontrado')


def _get_all_file_urls_from_obj(obj):
    urls = []
    if not obj:
        return urls
    try:
        for f in obj._meta.get_fields():
            if isinstance(f, _ProdFileField):
                try:
                    fval = getattr(obj, f.name, None)
                    if fval and getattr(fval, 'name', ''):
                        u = fval.url
                        if u and u not in urls:
                            urls.append(u)
                except Exception:
                    continue
    except Exception:
        pass
    return urls


def _get_related_images_for_instance(instance, skip_accessors=()):
    urls = []
    if not instance:
        return urls
    try:
        for rel in instance._meta.get_fields():
            if not (rel.one_to_many or rel.many_to_many):
                continue
            accessor = rel.get_accessor_name()
            if not accessor or accessor in skip_accessors:
                continue
            try:
                mgr = getattr(instance, accessor, None)
                if mgr is None or not hasattr(mgr, 'all'):
                    continue
                rel_model = rel.related_model
                has_file = any(isinstance(rf, _ProdFileField) for rf in rel_model._meta.get_fields())
                if not has_file:
                    continue
                qs = mgr.all()
                rel_field_names = {rf.name for rf in rel_model._meta.get_fields()}
                order_by = [f for f in ('orden', 'id') if f in rel_field_names]
                if order_by:
                    qs = qs.order_by(*order_by)
                for item in qs:
                    for u in _get_all_file_urls_from_obj(item):
                        if u not in urls:
                            urls.append(u)
            except Exception:
                continue
    except Exception:
        pass
    return urls


def _store_uploaded_images(producto, files_list, color_obj=None):
    if not files_list:
        return
    from .models import Producto

    # 1. Buscar un modelo relacionado de imágenes en Producto (ej. ProductoImagen)
    target_rel_model = None
    prod_fk_name = None
    color_fk_name = None
    file_field_name = None

    for rel in Producto._meta.get_fields():
        if not (rel.one_to_many or rel.many_to_many):
            continue
        rel_model = rel.related_model
        if rel_model.__name__ == 'ProductoColor':
            continue
        file_fields = [f for f in rel_model._meta.get_fields() if isinstance(f, _ProdFileField)]
        if not file_fields:
            continue
        target_rel_model = rel_model
        file_field_name = file_fields[0].name
        for f in rel_model._meta.get_fields():
            if isinstance(f, _ProdForeignKey):
                if f.related_model is Producto:
                    prod_fk_name = f.name
                elif color_obj is not None and f.related_model is type(color_obj):
                    color_fk_name = f.name
        break

    remaining_files = list(files_list)

    # Si se pasó un color y ProductoColor tiene campo de imagen propio, guardar ahí la primera
    if color_obj is not None and remaining_files:
        color_file_fields = [f for f in type(color_obj)._meta.get_fields() if isinstance(f, _ProdFileField)]
        if color_file_fields:
            cf_name = color_file_fields[0].name
            setattr(color_obj, cf_name, remaining_files.pop(0))
            color_obj.save(update_fields=[cf_name])

    # Guardar el resto (o todas si ProductoColor no tiene ImageField propio) en el modelo de galería
    if remaining_files and target_rel_model and prod_fk_name and file_field_name:
        for fobj in remaining_files:
            kwargs = {prod_fk_name: producto, file_field_name: fobj}
            if color_obj is not None and color_fk_name:
                kwargs[color_fk_name] = color_obj
            target_rel_model.objects.create(**kwargs)
    elif remaining_files and color_obj is None:
        # Si no hay tabla de galería extra y el producto no tiene imagen aún, guardar en Producto
        prod_file_fields = [f for f in Producto._meta.get_fields() if isinstance(f, _ProdFileField)]
        if prod_file_fields and not getattr(producto, prod_file_fields[0].name, None):
            pf_name = prod_file_fields[0].name
            setattr(producto, pf_name, remaining_files[0])
            producto.save(update_fields=[pf_name])


def _build_producto_editorial_data(producto):
    from configuracion.models import ConfiguracionERP
    from .models import ProductoColor

    try:
        config = ConfiguracionERP.get_instance()
    except Exception:
        config = None

    raw_emp = _prod_safe_str(_prod_first_attr(config, ['nombre_empresa', 'razon_social', 'nombre', 'titulo'], ''), '')
    if not raw_emp or raw_emp.lower() in ('mi empresa erp', 'mi empresa'):
        empresa_nombre = 'DANDELION STAR'
    else:
        empresa_nombre = raw_emp.upper()

    base_imgs = _get_all_file_urls_from_obj(producto)
    rel_prod_imgs = _get_related_images_for_instance(producto, skip_accessors=('colores',))
    img_url = base_imgs[0] if base_imgs else (rel_prod_imgs[0] if rel_prod_imgs else '')

    cat_obj = getattr(producto, 'categoria', None)
    prov_obj = getattr(producto, 'proveedor', None)

    cat_nombre = _prod_safe_str(_prod_first_attr(cat_obj, ['nombre', 'titulo'], None), '') or _prod_safe_str(cat_obj, 'Colección Exclusiva')
    prov_nombre = _prod_safe_str(_prod_first_attr(prov_obj, ['nombre', 'razon_social', 'titulo'], None), '') or _prod_safe_str(prov_obj, empresa_nombre.title())

    activo_val = getattr(producto, 'activo', None)
    if activo_val is None:
        estado_str = _prod_safe_str(_prod_first_attr(producto, ['get_estado_display', 'estado', 'estatus'], 'Activo'), 'Activo')
        es_activo = estado_str.lower() not in ('inactivo', 'agotado', 'false', '0')
    else:
        es_activo = bool(activo_val)
        estado_str = 'Activo' if es_activo else 'Inactivo'

    raw_stock = _prod_first_attr(producto, ['stock', 'cantidad', 'existencia', 'inventario'], 0)
    try:
        stock_val = int(raw_stock or 0)
    except Exception:
        stock_val = 0

    raw_precio = _prod_first_attr(producto, ['precio', 'precio_venta', 'precio_unitario'], 0)
    try:
        precio_fmt = f"{_ProdDecimal(str(raw_precio or 0)):,.2f}"
    except Exception:
        precio_fmt = "0.00"

    sku_val = _prod_safe_str(_prod_first_attr(producto, ['sku', 'codigo', 'referencia', 'clave'], ''), f'DS-{producto.pk:04d}')
    desc_val = _prod_safe_str(_prod_first_attr(producto, ['descripcion', 'detalle', 'notas', 'observaciones'], ''), '')

    fecha_val = _prod_first_attr(producto, ['fecha_creacion', 'created_at', 'fecha_registro', 'actualizado'], None)
    fecha_fmt = ''
    if fecha_val:
        try:
            fecha_fmt = fecha_val.strftime('%d/%m/%Y %H:%M')
        except Exception:
            fecha_fmt = _prod_safe_str(fecha_val, '')

    color_model_fields = {f.name for f in ProductoColor._meta.get_fields()}
    order_fields = [f for f in ('orden', 'id') if f in color_model_fields] or ['pk']

    colores_qs = []
    try:
        colores_qs = list(ProductoColor.objects.filter(producto=producto).order_by(*order_fields))
    except Exception:
        try:
            _prod_connection.close()
            from django.core.management import call_command
            call_command('migrate', 'productos', interactive=False, verbosity=0)
            _prod_connection.close()
            colores_qs = list(ProductoColor.objects.filter(producto=producto).order_by(*order_fields))
        except Exception:
            _prod_connection.close()
            colores_qs = []

    # Construir galería unificada con TODAS las imágenes subidas (sin duplicados)
    galeria_map = {}
    galeria_imagenes = []

    def _register_gallery_url(url, label='', color_idx=-1):
        if not url:
            return
        if url not in galeria_map:
            entry = {
                'index': len(galeria_imagenes),
                'url': url,
                'label': label,
                'color_idx': color_idx,
            }
            galeria_map[url] = entry
            galeria_imagenes.append(entry)
        else:
            if color_idx >= 0 and galeria_map[url]['color_idx'] < 0:
                galeria_map[url]['color_idx'] = color_idx
                if label:
                    galeria_map[url]['label'] = label

    prod_title = _prod_safe_str(_prod_first_attr(producto, ['nombre', 'titulo'], ''), f'Producto #{producto.pk}')
    for u in base_imgs:
        _register_gallery_url(u, prod_title, -1)
    for u in rel_prod_imgs:
        _register_gallery_url(u, prod_title, -1)

    # Construir lista de colores SOLO con los colores registrados por el usuario
    colores_list = []
    for idx, c in enumerate(colores_qs):
        c_nombre = _prod_safe_str(_prod_first_attr(c, ['nombre', 'color', 'titulo', 'name'], ''), f'Color {idx + 1}')
        c_hex = _prod_safe_str(
            _prod_first_attr(c, ['codigo_hex', 'codigo_color', 'hex', 'color_hex', 'hex_color', 'codigo'], ''),
            '#1c1c1c',
        )
        if c_hex and not c_hex.startswith('#'):
            c_hex = f'#{c_hex}'

        c_own_imgs = _get_all_file_urls_from_obj(c) + _get_related_images_for_instance(c)
        for u in c_own_imgs:
            _register_gallery_url(u, c_nombre, idx)

        c_img = c_own_imgs[0] if c_own_imgs else ''
        gallery_idx = galeria_map[c_img]['index'] if c_img and c_img in galeria_map else -1

        c_stock_raw = _prod_first_attr(c, ['stock', 'cantidad', 'existencia'], None)
        c_stock = c_stock_raw if c_stock_raw not in (None, '') else stock_val

        try:
            del_url = _prod_reverse('productos:eliminar_color', args=[c.id])
        except Exception:
            del_url = f'/productos/colores/{c.id}/eliminar/'

        colores_list.append({
            'id': c.id,
            'nombre': c_nombre,
            'codigo_hex': c_hex or '#1c1c1c',
            'imagen_url': c_img,
            'gallery_index': gallery_idx,
            'stock': c_stock,
            'delete_url': del_url,
        })

    # Imagen inicial en el escenario principal
    initial_img = ''
    if colores_list and colores_list[0]['imagen_url']:
        initial_img = colores_list[0]['imagen_url']
    elif galeria_imagenes:
        initial_img = galeria_imagenes[0]['url']
    else:
        initial_img = img_url

    try:
        agregar_color_url = _prod_reverse('productos:agregar_color', args=[producto.pk])
    except Exception:
        agregar_color_url = f'/productos/{producto.pk}/colores/agregar/'

    try:
        agregar_imagenes_url = _prod_reverse('productos:agregar_imagenes_editorial', args=[producto.pk])
    except Exception:
        agregar_imagenes_url = f'/productos/{producto.pk}/imagenes/agregar/'

    ventas_crear_url = _prod_safe_reverse(
        ['ventas:crear', 'ventas:nueva', 'ventas:venta_crear', 'ventas:crear_venta', 'ventas:lista'],
        '/ventas/',
    )
    catalogo_url = _prod_safe_reverse(
        ['productos:lista', 'productos:index', 'productos:productos', 'productos:catalogo'],
        '/productos/',
    )

    return {
        'empresa_nombre': empresa_nombre,
        'ventas_crear_url': ventas_crear_url,
        'agregar_color_url': agregar_color_url,
        'agregar_imagenes_url': agregar_imagenes_url,
        'catalogo_url': catalogo_url,
        'prod_info': {
            'id': producto.pk,
            'nombre': prod_title,
            'categoria': cat_nombre,
            'proveedor': prov_nombre,
            'precio_fmt': precio_fmt,
            'stock': stock_val,
            'es_activo': es_activo,
            'estado': estado_str,
            'sku': sku_val,
            'descripcion': desc_val,
            'fecha_fmt': fecha_fmt,
            'imagen_url': initial_img,
        },
        'colores_list': colores_list,
        'galeria_imagenes': galeria_imagenes,
    }


def producto_detalle_editorial(request, pk=None, id=None, producto_id=None, slug=None):
    producto = _resolve_producto_obj(pk=pk, id=id, producto_id=producto_id, slug=slug)
    try:
        ctx = {'producto': producto, 'object': producto}
        ctx.update(_build_producto_editorial_data(producto))
        return _prod_render(request, 'productos/detalle.html', ctx)
    except Exception as exc:
        print(f"[ERROR producto_detalle_editorial pk={producto.pk}]: {exc}")
        print(_prod_traceback.format_exc())
        fallback_ctx = {
            'producto': producto,
            'object': producto,
            'empresa_nombre': 'DANDELION STAR',
            'ventas_crear_url': '/ventas/',
            'agregar_color_url': f'/productos/{producto.pk}/colores/agregar/',
            'agregar_imagenes_url': f'/productos/{producto.pk}/imagenes/agregar/',
            'catalogo_url': '/productos/',
            'prod_info': {
                'id': producto.pk,
                'nombre': _prod_safe_str(getattr(producto, 'nombre', ''), f'Producto #{producto.pk}'),
                'categoria': 'Colección Exclusiva',
                'proveedor': 'Dandelion Star',
                'precio_fmt': _prod_safe_str(getattr(producto, 'precio', '0.00'), '0.00'),
                'stock': getattr(producto, 'stock', 0) or 0,
                'es_activo': True,
                'estado': 'Activo',
                'sku': f'DS-{producto.pk:04d}',
                'descripcion': _prod_safe_str(getattr(producto, 'descripcion', ''), ''),
                'fecha_fmt': '',
                'imagen_url': '',
            },
            'colores_list': [],
            'galeria_imagenes': [],
        }
        return _prod_render(request, 'productos/detalle.html', fallback_ctx)


@_prod_login_required
@_prod_require_POST
def agregar_color_producto(request, pk=None, id=None, producto_id=None):
    from .models import ProductoColor
    producto = _resolve_producto_obj(pk=pk, id=id, producto_id=producto_id)
    nombre = (request.POST.get('nombre') or '').strip()
    codigo_hex = (request.POST.get('codigo_hex') or '#1c1c1c').strip()
    if not codigo_hex.startswith('#'):
        codigo_hex = f'#{codigo_hex}'

    uploaded_files = request.FILES.getlist('imagenes') or request.FILES.getlist('imagen')
    try:
        stock = max(0, int(request.POST.get('stock') or 0))
    except ValueError:
        stock = 0

    if not nombre:
        _prod_messages.error(request, 'Escribe el nombre del color.')
        return _prod_redirect(request.META.get('HTTP_REFERER') or f'/productos/{producto.pk}/')

    color_fields = {f.name for f in ProductoColor._meta.get_fields()}
    create_kwargs = {'producto': producto}

    for fname in ('nombre', 'color', 'titulo', 'name'):
        if fname in color_fields:
            create_kwargs[fname] = nombre
            break

    for fname in ('codigo_hex', 'codigo_color', 'hex', 'color_hex', 'hex_color', 'codigo'):
        if fname in color_fields:
            create_kwargs[fname] = codigo_hex
            break

    if 'stock' in color_fields:
        create_kwargs['stock'] = stock

    try:
        color_obj = ProductoColor.objects.create(**create_kwargs)
    except Exception:
        _prod_connection.close()
        from django.core.management import call_command
        call_command('migrate', 'productos', interactive=False, verbosity=0)
        _prod_connection.close()
        color_obj = ProductoColor.objects.create(**create_kwargs)

    if uploaded_files:
        _store_uploaded_images(producto, uploaded_files, color_obj=color_obj)

    _prod_messages.success(request, f'Color "{nombre}" agregado a {producto}.')
    return _prod_redirect(request.META.get('HTTP_REFERER') or f'/productos/{producto.pk}/')


@_prod_login_required
@_prod_require_POST
def agregar_imagenes_producto_editorial(request, pk=None, id=None, producto_id=None):
    producto = _resolve_producto_obj(pk=pk, id=id, producto_id=producto_id)
    files_list = request.FILES.getlist('imagenes') or request.FILES.getlist('imagen')
    if not files_list:
        _prod_messages.error(request, 'Selecciona al menos una imagen.')
        return _prod_redirect(request.META.get('HTTP_REFERER') or f'/productos/{producto.pk}/')

    _store_uploaded_images(producto, files_list, color_obj=None)
    _prod_messages.success(request, f'Se subieron {len(files_list)} imagen(es) a {producto}.')
    return _prod_redirect(request.META.get('HTTP_REFERER') or f'/productos/{producto.pk}/')


@_prod_login_required
@_prod_require_POST
def eliminar_color_producto(request, color_id: int):
    from .models import ProductoColor
    color = _prod_get_object_or_404(ProductoColor, pk=color_id)
    prod_pk = color.producto_id
    nombre = _prod_safe_str(_prod_first_attr(color, ['nombre', 'color', 'titulo'], ''), 'Color')
    color.delete()
    _prod_messages.success(request, f'Color "{nombre}" eliminado.')
    return _prod_redirect(request.META.get('HTTP_REFERER') or f'/productos/{prod_pk}/')
