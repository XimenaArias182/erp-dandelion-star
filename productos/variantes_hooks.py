import re
import threading
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Producto, ProductoColor, ProductoImagen

_thread_locals = threading.local()


def get_current_request():
    return getattr(_thread_locals, "request", None)


class ProductoVariantesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and request.POST:
            price_keys = [
                k for k in request.POST.keys()
                if any(w in k.lower() for w in ("precio", "costo", "price", "cost", "importe", "monto", "subtotal", "total"))
            ]
            if price_keys:
                mutable_post = request.POST.copy()
                changed = False
                for k in price_keys:
                    vals = mutable_post.getlist(k)
                    clean_vals = []
                    for v in vals:
                        # Limpiar símbolo $ y comas de miles para que DecimalField/float lo guarde sin error
                        cleaned = re.sub(r'[\$\s,]', '', str(v))
                        if cleaned != str(v):
                            changed = True
                        clean_vals.append(cleaned)
                    if changed:
                        mutable_post.setlist(k, clean_vals)
                if changed:
                    request.POST = mutable_post

        _thread_locals.request = request
        try:
            response = self.get_response(request)
        finally:
            _thread_locals.request = None
        return response


@receiver(post_save, sender=Producto)
def guardar_colores_e_imagenes_producto(sender, instance, created, **kwargs):
    request = get_current_request()
    if not request or request.method != "POST":
        return
    if getattr(request, "_ds_variantes_saved", False):
        return

    has_ds_fields = (
        "ds_variantes_form_active" in request.POST
        or "ds_main_color_name" in request.POST
        or bool(request.POST.getlist("ds_color_nombre[]"))
        or bool(request.FILES.getlist("ds_extra_imagenes[]"))
    )
    if not has_ds_fields:
        return

    request._ds_variantes_saved = True

    del_colors = [cid for cid in request.POST.getlist("ds_delete_color_ids[]") if str(cid).isdigit()]
    if del_colors:
        ProductoColor.objects.filter(producto=instance, id__in=del_colors).delete()

    del_imgs = [iid for iid in request.POST.getlist("ds_delete_img_ids[]") if str(iid).isdigit()]
    if del_imgs:
        ProductoImagen.objects.filter(producto=instance, id__in=del_imgs).delete()

    main_color = (request.POST.get("ds_main_color_name") or "").strip()
    if main_color:
        first_main = (
            ProductoColor.objects.filter(producto=instance, imagen_color="").first()
            or ProductoColor.objects.filter(producto=instance, imagen_color__isnull=True).first()
        )
        if first_main:
            first_main.nombre = main_color
            first_main.orden = 0
            first_main.save(update_fields=["nombre", "orden"])
        else:
            ProductoColor.objects.create(
                producto=instance,
                nombre=main_color,
                codigo_hex="#EAE6DF",
                imagen_color=None,
                orden=0,
            )

    nombres = request.POST.getlist("ds_color_nombre[]")
    indices = request.POST.getlist("ds_color_idx[]")
    base_order = ProductoColor.objects.filter(producto=instance).count() + 1

    for pos, raw_name in enumerate(nombres):
        cname = (raw_name or "").strip()
        if not cname:
            continue
        idx_key = indices[pos] if pos < len(indices) else str(pos)
        c_file = request.FILES.get(f"ds_color_imagen_{idx_key}")
        ProductoColor.objects.create(
            producto=instance,
            nombre=cname,
            codigo_hex="#141414",
            imagen_color=c_file,
            orden=base_order + pos,
        )

    extra_files = request.FILES.getlist("ds_extra_imagenes[]")
    img_order = ProductoImagen.objects.filter(producto=instance).count()
    for i, f in enumerate(extra_files):
        ProductoImagen.objects.create(
            producto=instance,
            imagen=f,
            titulo="",
            orden=img_order + i,
        )
