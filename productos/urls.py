# productos/urls.py
from django.urls import path
from . import views
from .views import (
    producto_detalle_editorial as _producto_detalle_editorial,
    agregar_color_producto as _agregar_color_producto,
    eliminar_color_producto as _eliminar_color_producto,
)

# === RUTAS EDITORIALES PRODUCTOS ===
urlpatterns = [
    path('<int:pk>/', _producto_detalle_editorial, name='detalle'),
    path('detalle/<int:pk>/', _producto_detalle_editorial, name='detalle_alt'),
    path('ver/<int:pk>/', _producto_detalle_editorial, name='ver_detalle'),
    path('producto/<int:pk>/', _producto_detalle_editorial, name='producto_detalle'),
    path('<int:pk>/colores/agregar/', _agregar_color_producto, name='agregar_color'),
    path('colores/<int:color_id>/eliminar/', _eliminar_color_producto, name='eliminar_color'),
] + urlpatterns
