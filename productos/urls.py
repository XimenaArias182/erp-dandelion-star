from .views import (
    producto_detalle_editorial as _producto_detalle_editorial,
    agregar_color_producto as _agregar_color_producto,
    eliminar_color_producto as _eliminar_color_producto,
    actualizar_color_producto as _actualizar_color_producto,
    agregar_imagenes_producto_editorial as _agregar_imagenes_editorial,
)
# productos/urls.py
from django.urls import path
from . import views

app_name = 'productos'

urlpatterns = [
    path('', views.ProductoListView.as_view(), name='lista'),
    path('exportar-excel/', views.exportar_excel, name='exportar_excel'),
    path('', views.ProductoListView.as_view(), name='inicio'),
    path('crear/', views.ProductoCreateView.as_view(), name='crear'),
    path('<int:pk>/', _producto_detalle_editorial, name='detalle'),
    path('<int:pk>/editar/', views.ProductoUpdateView.as_view(), name='editar'),
    path('<int:pk>/eliminar/', views.ProductoDeleteView.as_view(), name='eliminar'),
]

# === RUTAS EDITORIALES PRODUCTOS ===
urlpatterns = [
    path('<int:pk>/', _producto_detalle_editorial, name='detalle'),
    path('detalle/<int:pk>/', _producto_detalle_editorial, name='detalle_alt'),
    path('ver/<int:pk>/', _producto_detalle_editorial, name='ver_detalle'),
    path('producto/<int:pk>/', _producto_detalle_editorial, name='producto_detalle'),
    path('<int:pk>/colores/agregar/', _agregar_color_producto, name='agregar_color'),
    path('<int:pk>/imagenes/agregar/', _agregar_imagenes_editorial, name='agregar_imagenes_editorial'),
    path('colores/<int:color_id>/eliminar/', _eliminar_color_producto, name='eliminar_color'),
    path('colores/<int:color_id>/actualizar/', _actualizar_color_producto, name='actualizar_color'),
] + urlpatterns
