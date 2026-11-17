from django.contrib import admin
from .models import (
    Producto, Cliente, DescargaInventario, DetalleDescarga,
    Cotizacion, DetalleCotizacion, ServicioTecnico
)


class DetalleDescargaInline(admin.TabularInline):
    model = DetalleDescarga
    extra = 0


class DetalleCotizacionInline(admin.TabularInline):
    model = DetalleCotizacion
    extra = 0


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'cantidad', 'precio', 'fecha_actualizacion')
    search_fields = ('nombre', 'descripcion')


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'telefono', 'direccion', 'fecha_registro')
    search_fields = ('nombre', 'telefono')


@admin.register(DescargaInventario)
class DescargaInventarioAdmin(admin.ModelAdmin):
    list_display = ('id', 'motivo', 'nota_salida', 'usuario', 'fecha')
    list_filter = ('motivo', 'fecha')
    inlines = [DetalleDescargaInline]


@admin.register(Cotizacion)
class CotizacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'total', 'validez', 'usuario', 'fecha')
    list_filter = ('fecha',)
    inlines = [DetalleCotizacionInline]


@admin.register(ServicioTecnico)
class ServicioTecnicoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'equipo', 'estado', 'fecha_solicitud')
    list_filter = ('estado', 'fecha_solicitud')
    search_fields = ('cliente__nombre', 'equipo', 'descripcion_falla')