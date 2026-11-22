from django.urls import path
from . import views

app_name = 'clientes'

urlpatterns = [
    path('', views.ds_lista_clientes, name='lista'),
    path('', views.ds_lista_clientes, name='inicio'),
    path('nuevo/', views.ds_guardar_cliente, name='crear'),
    path('crear/', views.ds_guardar_cliente, name='crear_alt'),
    path('<int:pk>/', views.ClienteDetailView.as_view(), name='detalle'),
    path('<int:pk>/editar/', views.ds_guardar_cliente, name='editar'),
    path('<int:pk>/eliminar/', views.ds_eliminar_cliente, name='eliminar'),
]
