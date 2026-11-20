from django.contrib import admin, messages
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    Producto, Cliente, DescargaInventario, DetalleDescarga,
    Cotizacion, DetalleCotizacion, ServicioTecnico
)


# ==============================================================================
# INLINES (DETALLES DENTRO DE COTIZACIONES Y DESCARGAS)
# ==============================================================================
class DetalleCotizacionInline(admin.TabularInline):
    model = DetalleCotizacion
    extra = 0
    fields = ('producto', 'es_mano_obra', 'descripcion', 'cantidad', 'precio_unitario', 'subtotal')
    readonly_fields = ('subtotal',)


class DetalleDescargaInline(admin.TabularInline):
    model = DetalleDescarga
    extra = 0
    fields = ('producto', 'cantidad', 'precio_unitario', 'subtotal')
    readonly_fields = ('producto', 'cantidad', 'precio_unitario', 'subtotal')
    can_delete = False


# ==============================================================================
# 1. PRODUCTOS / REPUESTOS EN BODEGA
# ==============================================================================
@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('miniatura', 'nombre', 'cantidad', 'precio_formateado', 'estado_activo', 'fecha_creacion')
    list_filter = ('activo', 'fecha_creacion')
    search_fields = ('nombre', 'descripcion')
    list_editable = ('cantidad',)
    actions = ['dar_de_baja', 'dar_de_alta']

    @admin.display(description='Foto')
    def miniatura(self, obj):
        if obj.foto:
            return format_html(
                '<img src="{}" style="width:38px;height:38px;object-fit:cover;border-radius:6px;border:1px solid #cbd5e1;" />',
                obj.foto.url
            )
        return "—"

    @admin.display(description='Precio')
    def precio_formateado(self, obj):
        return f"Q {obj.precio:,.2f}"

    @admin.display(description='Estado', boolean=True)
    def estado_activo(self, obj):
        return obj.activo

    @admin.action(description='Dar de baja repuestos seleccionados')
    def dar_de_baja(self, request, queryset):
        actualizados = queryset.update(activo=False)
        self.message_user(request, f'{actualizados} repuesto(s) dados de baja.', messages.SUCCESS)

    @admin.action(description='Dar de alta (reactivar) repuestos seleccionados')
    def dar_de_alta(self, request, queryset):
        actualizados = queryset.update(activo=True)
        self.message_user(request, f'{actualizados} repuesto(s) reactivados en inventario.', messages.SUCCESS)


# ==============================================================================
# 2. CLIENTES
# ==============================================================================
@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'telefono', 'direccion', 'total_ordenes', 'total_cotizaciones')
    search_fields = ('nombre', 'telefono', 'direccion')

    @admin.display(description='Órdenes')
    def total_ordenes(self, obj):
        return obj.servicios.count()

    @admin.display(description='Cotizaciones')
    def total_cotizaciones(self, obj):
        return obj.cotizaciones.count()


# ==============================================================================
# 3. ÓRDENES DE SERVICIO TÉCNICO
# ==============================================================================
@admin.register(ServicioTecnico)
class ServicioTecnicoAdmin(admin.ModelAdmin):
    list_display = (
        'folio_orden', 'cliente', 'equipo', 'estado',
        'costo_mano_obra', 'total_orden', 'fecha_solicitud', 'boton_constancia'
    )
    list_filter = ('estado', 'fecha_solicitud', 'fecha_cierre')
    search_fields = ('id', 'cliente__nombre', 'equipo', 'descripcion_falla', 'detalle_mano_obra')
    readonly_fields = ('fecha_solicitud',)

    @admin.display(description='Orden')
    def folio_orden(self, obj):
        return f"ORD-{obj.id:04d}"

    @admin.display(description='Total Reparación')
    def total_orden(self, obj):
        return f"Q {obj.total_reparacion:,.2f}"

    @admin.display(description='Constancia PDF')
    def boton_constancia(self, obj):
        if obj.estado == 'completado':
            url = reverse('descargar_constancia_servicio_pdf', args=[obj.id])
            return format_html('<a class="button" href="{}" target="_blank">Descargar PDF</a>', url)
        return "Pendiente de cierre"


# ==============================================================================
# 4. COTIZACIONES COMERCIALES Y DE TALLER
# ==============================================================================
@admin.register(Cotizacion)
class CotizacionAdmin(admin.ModelAdmin):
    list_display = (
        'folio_cot', 'nombre_destinatario', 'servicio_tecnico',
        'estado', 'validez', 'total_cotizado', 'fecha', 'boton_pdf'
    )
    list_filter = ('estado', 'fecha')
    search_fields = ('id', 'cliente__nombre', 'cliente_nombre', 'descripcion_trabajo')
    readonly_fields = ('fecha', 'fecha_aprobacion', 'total')
    inlines = [DetalleCotizacionInline]

    @admin.display(description='Folio')
    def folio_cot(self, obj):
        return f"COT-{obj.id:04d}"

    @admin.display(description='Total')
    def total_cotizado(self, obj):
        return f"Q {obj.total:,.2f}"

    @admin.display(description='PDF')
    def boton_pdf(self, obj):
        url = reverse('descargar_cotizacion_pdf', args=[obj.id])
        return format_html('<a class="button" href="{}" target="_blank">Ver PDF</a>', url)


# ==============================================================================
# 5. AUDITORÍA DE DESCARGAS DE INVENTARIO (SOLO LECTURA PARA PROTEGER STOCK)
# ==============================================================================
@admin.register(DescargaInventario)
class DescargaInventarioAdmin(admin.ModelAdmin):
    list_display = ('folio_salida', 'fecha', 'motivo', 'nombre_destinatario', 'servicio_tecnico', 'total_salida', 'usuario')
    list_filter = ('motivo', 'fecha')
    search_fields = ('id', 'cliente__nombre', 'cliente_nombre', 'nota_salida')
    readonly_fields = ('fecha', 'motivo', 'cliente', 'cliente_nombre', 'servicio_tecnico', 'nota_salida', 'total_descontado', 'usuario')
    inlines = [DetalleDescargaInline]

    @admin.display(description='Salida')
    def folio_salida(self, obj):
        return f"#{obj.id:04d}"

    @admin.display(description='Total Descontado')
    def total_salida(self, obj):
        return f"Q {obj.total_descontado:,.2f}"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False