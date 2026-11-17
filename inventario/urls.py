from django.urls import path
from . import views

urlpatterns = [
    path('', views.cargar_producto, name='cargar_producto'),
    path('producto/<int:producto_id>/editar/', views.editar_producto, name='editar_producto'),
    path('producto/<int:producto_id>/baja/', views.dar_baja_producto, name='dar_baja_producto'),
    path('descargar/', views.descargar_inventario, name='descargar_inventario'),
    path('cotizaciones/', views.cotizaciones, name='cotizaciones'),
    path('cotizaciones/pdf/', views.generar_cotizacion_pdf, name='generar_cotizacion_pdf'),
    path('cotizaciones/<int:cotizacion_id>/pdf/', views.descargar_cotizacion_pdf, name='descargar_cotizacion_pdf'),
    path('clientes/', views.clientes, name='clientes'),
    path('clientes/nuevo/', views.crear_cliente, name='crear_cliente'),
    path('clientes/servicio-tecnico/', views.crear_servicio_tecnico, name='crear_servicio_tecnico'),
    path('clientes/<int:cliente_id>/', views.perfil_cliente, name='perfil_cliente'),
    path('servicio-tecnico/<int:servicio_id>/estado/', views.actualizar_estado_servicio, name='actualizar_estado_servicio'),
    path('servicio-tecnico/<int:servicio_id>/repuestos/', views.cargar_repuestos_servicio, name='cargar_repuestos_servicio'),
    path('clientes/<int:cliente_id>/editar/', views.editar_cliente, name='editar_cliente'),
    path('servicio-tecnico/<int:servicio_id>/constancia-pdf/', views.descargar_constancia_servicio_pdf, name='descargar_constancia_servicio_pdf'),
]