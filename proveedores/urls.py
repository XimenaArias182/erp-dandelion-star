from django.urls import path
from . import views

app_name = 'proveedores'

urlpatterns = [
    path('', views.ds_lista_proveedores, name='lista'),
    path('', views.ds_lista_proveedores, name='inicio'),
    path('nuevo/', views.ds_guardar_proveedor, name='crear'),
    path('crear/', views.ds_guardar_proveedor, name='crear_alt'),
    path('agregar/', views.ds_guardar_proveedor, name='agregar'),
    path('<int:proveedor_id>/', views.ProveedorDetailView.as_view(), name='detalle'),
    path('<int:proveedor_id>/editar/', views.ds_guardar_proveedor, name='editar'),
    path('<int:pk>/editar/', views.ds_guardar_proveedor, name='editar_pk'),
    path('<int:proveedor_id>/eliminar/', views.ProveedorDeleteView.as_view(), name='eliminar'),
    path('<int:pk>/logo/', views.subir_logo_proveedor, name='subir_logo_proveedor'),
]
