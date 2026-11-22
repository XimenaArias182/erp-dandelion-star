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
import unicodedata as _prod_unicodedata
from decimal import Decimal as _ProdDecimal
from django.contrib import messages as _prod_messages
from django.contrib.auth.decorators import login_required as _prod_login_required
from django.db import connection as _prod_connection
from django.http import Http404 as _ProdHttp404
from django.shortcuts import get_object_or_404 as _prod_get_object_or_404, redirect as _prod_redirect, render as _prod_render
from django.urls import reverse as _prod_reverse
from django.views.decorators.http import require_POST as _prod_require_POST


_COLOR_KEYWORDS = [
    ('azul marino', '#1b2f4f'),
    ('navy', '#1b2f4f'),
    ('azul cielo', '#7ec8e3'),
    ('celeste', '#7ec8e3'),
    ('azul rey', '#1e4fa3'),
    ('cobalto', '#1e4fa3'),
    ('turquesa', '#30b5ad'),
    ('aguamarina', '#66cdAA'),
    ('menta', '#76c7a8'),
    ('palo de rosa', '#d49a9e'),
    ('oro rosa', '#d8a48f'),
    ('rose gold', '#d8a48f'),
    ('blanco perla', '#f7f5f0'),
    ('off white', '#f5f2eb'),
    ('marfil', '#f5f0e1'),
    ('ivory', '#f5f0e1'),
    ('crema', '#f3ead8'),
    ('cream', '#f3ead8'),
    ('crudo', '#ede4d3'),
    ('verde esmeralda', '#1f6f50'),
    ('esmeralda', '#1f6f50'),
    ('verde oliva', '#6b7c45'),
    ('oliva', '#6b7c45'),
    ('salvia', '#8fa387'),
    ('verde bosque', '#214a36'),
    ('gris claro', '#c4c7ce'),
    ('gris oscuro', '#4a4d52'),
    ('grafito', '#3d4045'),
    ('antracita', '#383b40'),
    ('negro', '#141414'),
    ('black', '#141414'),
    ('noir', '#141414'),
    ('onyx', '#181818'),
    ('blanco', '#f8f7f4'),
    ('white', '#f8f7f4'),
    ('perla', '#f4f1ea'),
    ('latte', '#d6c1a9'),
    ('beige', '#dfd1be'),
    ('arena', '#dccbb4'),
    ('sand', '#dccbb4'),
    ('nude', '#e3c6b2'),
    ('camel', '#b88b58'),
    ('taupe', '#9c8b7e'),
    ('topo', '#8f7f73'),
    ('capuchino', '#a68265'),
    ('champagne', '#e6d5b8'),
    ('champan', '#e6d5b8'),
    ('cafe', '#63412c'),
    ('marron', '#6b442a'),
    ('brown', '#6b442a'),
    ('chocolate', '#4a2c1d'),
    ('cacao', '#543322'),
    ('cognac', '#8f4722'),
    ('conac', '#8f4722'),
    ('canela', '#9c5a33'),
    ('bronce', '#8c6239'),
    ('dorado', '#c9a24b'),
    ('oro', '#c9a24b'),
    ('gold', '#c9a24b'),
    ('plateado', '#c5c8ce'),
    ('plata', '#c5c8ce'),
    ('silver', '#c5c8ce'),
    ('acero', '#9da3ab'),
    ('gris', '#858990'),
    ('gray', '#858990'),
    ('grey', '#858990'),
    ('vino', '#6e1b29'),
    ('burdeos', '#6e1b29'),
    ('burgundy', '#6e1b29'),
    ('tinto', '#731d2c'),
    ('guinda', '#7a1f30'),
    ('granate', '#7d2027'),
    ('marsala', '#8c3b44'),
    ('terracota', '#b55239'),
    ('rojo', '#b82025'),
    ('red', '#b82025'),
    ('carmesi', '#a81c24'),
    ('cereza', '#9e1b24'),
    ('coral', '#e06d53'),
    ('salmon', '#eb8c78'),
    ('fucsia', '#c92a76'),
    ('fuchsia', '#c92a76'),
    ('magenta', '#c42b78'),
    ('rosa', '#e8a5b5'),
    ('pink', '#e8a5b5'),
    ('blush', '#ecc0c9'),
    ('azul', '#255499'),
    ('blue', '#255499'),
    ('verde', '#2b6e4b'),
    ('green', '#2b6e4b'),
    ('amarillo', '#e3b938'),
    ('yellow', '#e3b938'),
    ('mostaza', '#c99a2e'),
    ('miel', '#d49b35'),
    ('naranja', '#db6a2c'),
    ('orange', '#db6a2c'),
    ('durazno', '#f0a882'),
    ('peach', '#f0a882'),
    ('cobre', '#b35932'),
    ('morado', '#6e448a'),
    ('purple', '#6e448a'),
    ('violeta', '#7c4d99'),
    ('lila', '#bfa3d4'),
    ('lilac', '#bfa3d4'),
    ('lavanda', '#c6b4d8'),
    ('ciruela', '#5c2c52'),
    ('uva', '#5e315b'),
]


def _normalize_color_label(text: str) -> str:
    raw = str(text or '').strip().lower()
    norm = _prod_unicodedata.normalize('NFD', raw)
    return ''.join(ch for ch in norm if _prod_unicodedata.category(ch) != 'Mn')


def _infer_hex_from_color_name(nombre: str, stored_hex: str = '') -> str:
    clean_hex = str(stored_hex or '').strip()
    if clean_hex and not clean_hex.startswith('#'):
        clean_hex = f'#{clean_hex}'

    norm_name = _normalize_color_label(nombre)
    is_explicit_black = any(w in norm_name for w in ('negro', 'black', 'noir', 'onyx', 'carbon'))

    # Si ya existe un color personalizado distinto al valor por defecto, conservarlo
    if re.match(r'^#[0-9a-fA-F]{6}$', clean_hex):
        if clean_hex.lower() not in ('#1c1c1c', '#000000') or is_explicit_black:
            return clean_hex

    for kw, hex_val in _COLOR_KEYWORDS:
        if kw in norm_name:
            return hex_val

    return clean_hex if re.match(r'^#[0-9a-fA-F]{6}$', clean_hex) else '#c8bca9'


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


def _extract_color_image_url(color_obj, fallback_url=''):
    for fname in ('imagen', 'foto', 'image', 'imagen_principal'):
        try:
            fval = getattr(color_obj, fname, None)
            if fval and getattr(fval, 'name', ''):
                return fval.url
        except Exception:
            continue
    for rel_name in ('imagenes', 'fotos', 'images', 'productoimagen_set'):
        try:
            rel_mgr = getattr(color_obj, rel_name, None)
            if rel_mgr is not None and hasattr(rel_mgr, 'all'):
                for item in rel_mgr.all():
                    for fname in ('imagen', 'foto', 'image'):
                        fval = getattr(item, fname, None)
                        if fval and getattr(fval, 'name', ''):
                            return fval.url
        except Exception:
            continue
    return fallback_url


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

    img_url = ''
    for fname in ('imagen', 'foto', 'image', 'imagen_principal', 'foto_principal'):
        try:
            fval = getattr(producto, fname, None)
            if fval and getattr(fval, 'name', ''):
                img_url = fval.url
                if img_url:
                    break
        except Exception:
            continue

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

    colores_list = []
    if colores_qs:
        if img_url:
            colores_list.append({
                'id': 0,
                'nombre': 'Original',
                'codigo_hex': '#efeae1',
                'imagen_url': img_url,
                'stock': stock_val,
                'delete_url': '',
            })
        for c in colores_qs:
            c_nombre = _prod_safe_str(_prod_first_attr(c, ['nombre', 'color', 'titulo', 'name'], ''), 'Variante')
            raw_c_hex = _prod_safe_str(
                _prod_first_attr(c, ['codigo_hex', 'codigo_color', 'hex', 'color_hex', 'hex_color', 'codigo'], ''),
                '',
            )
            c_hex = _infer_hex_from_color_name(c_nombre, raw_c_hex)
            c_img = _extract_color_image_url(c, img_url)
            c_stock_raw = _prod_first_attr(c, ['stock', 'cantidad', 'existencia'], None)
            c_stock = c_stock_raw if c_stock_raw not in (None, '') else stock_val

            try:
                del_url = _prod_reverse('productos:eliminar_color', args=[c.id])
            except Exception:
                del_url = f'/productos/colores/{c.id}/eliminar/'

            colores_list.append({
                'id': c.id,
                'nombre': c_nombre,
                'codigo_hex': c_hex,
                'imagen_url': c_img,
                'stock': c_stock,
                'delete_url': del_url,
            })
    else:
        colores_list.append({
            'id': 0,
            'nombre': 'Único / Original',
            'codigo_hex': '#efeae1',
            'imagen_url': img_url,
            'stock': stock_val,
            'delete_url': '',
        })

    try:
        agregar_color_url = _prod_reverse('productos:agregar_color', args=[producto.pk])
    except Exception:
        agregar_color_url = f'/productos/{producto.pk}/colores/agregar/'

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
        'catalogo_url': catalogo_url,
        'prod_info': {
            'id': producto.pk,
            'nombre': _prod_safe_str(_prod_first_attr(producto, ['nombre', 'titulo'], ''), f'Producto #{producto.pk}'),
            'categoria': cat_nombre,
            'proveedor': prov_nombre,
            'precio_fmt': precio_fmt,
            'stock': stock_val,
            'es_activo': es_activo,
            'estado': estado_str,
            'sku': sku_val,
            'descripcion': desc_val,
            'fecha_fmt': fecha_fmt,
            'imagen_url': img_url,
        },
        'colores_list': colores_list,
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
            'colores_list': [{
                'id': 0,
                'nombre': 'Original',
                'codigo_hex': '#efeae1',
                'imagen_url': '',
                'stock': getattr(producto, 'stock', 0) or 0,
                'delete_url': '',
            }],
        }
        return _prod_render(request, 'productos/detalle.html', fallback_ctx)


@_prod_login_required
@_prod_require_POST
def agregar_color_producto(request, pk=None, id=None, producto_id=None):
    from .models import ProductoColor
    producto = _resolve_producto_obj(pk=pk, id=id, producto_id=producto_id)
    nombre = (request.POST.get('nombre') or '').strip()
    raw_hex = (request.POST.get('codigo_hex') or '').strip()
    codigo_hex = _infer_hex_from_color_name(nombre, raw_hex)
    imagen = request.FILES.get('imagen')
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

    if imagen:
        for fname in ('imagen', 'foto', 'image'):
            if fname in color_fields:
                create_kwargs[fname] = imagen
                break

    if 'stock' in color_fields:
        create_kwargs['stock'] = stock

    try:
        ProductoColor.objects.create(**create_kwargs)
    except Exception:
        _prod_connection.close()
        from django.core.management import call_command
        call_command('migrate', 'productos', interactive=False, verbosity=0)
        _prod_connection.close()
        ProductoColor.objects.create(**create_kwargs)

    _prod_messages.success(request, f'Color "{nombre}" agregado a {producto}.')
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
