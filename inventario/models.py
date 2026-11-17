from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Producto(models.Model):
    nombre = models.CharField(max_length=150, verbose_name="Nombre del repuesto")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción técnica")
    cantidad = models.PositiveIntegerField(default=0, verbose_name="Stock disponible")
    precio = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio unitario (Q)")
    foto = models.ImageField(upload_to='repuestos/', blank=True, null=True, verbose_name="Fotografía")
    activo = models.BooleanField(default=True, verbose_name="Activo en inventario")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = "Repuesto"
        verbose_name_plural = "Repuestos"

    def __str__(self):
        return f"{self.nombre} (Stock: {self.cantidad} - Q{self.precio})"


class Cliente(models.Model):
    nombre = models.CharField(max_length=150, verbose_name="Nombre completo o empresa")
    telefono = models.CharField(max_length=30, verbose_name="Teléfono / WhatsApp")
    direccion = models.TextField(verbose_name="Dirección física")
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_registro']
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"

    def __str__(self):
        return f"{self.nombre} ({self.telefono})"


class DescargaInventario(models.Model):
    MOTIVO_CHOICES = [
        ('venta', 'Venta directa en mostrador'),
        ('tecnico', 'Uso en servicio técnico'),
        ('garantia', 'Cambio por garantía'),
    ]

    motivo = models.CharField(max_length=20, choices=MOTIVO_CHOICES, default='venta')
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='descargas',
        verbose_name="Cliente registrado"
    )
    servicio_tecnico = models.ForeignKey(
        'ServicioTecnico',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='descargas_repuestos',
        verbose_name="Orden de Servicio Técnico"
    )
    cliente_nombre = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="Cliente no registrado / Consumidor"
    )
    nota_salida = models.CharField(max_length=255, blank=True, null=True, verbose_name="Referencia / Técnico")
    total_descontado = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    fecha = models.DateTimeField(default=timezone.now)

    @property
    def nombre_destinatario(self):
        if self.cliente:
            return self.cliente.nombre
        return self.cliente_nombre or "Consumidor Final / Interno"

    def __str__(self):
        return f"Salida #{self.id} - {self.nombre_destinatario} (Q{self.total_descontado})"


class DetalleDescarga(models.Model):
    descarga = models.ForeignKey(DescargaInventario, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def save(self, *args, **kwargs):
        self.subtotal = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cantidad}x {self.producto.nombre} (Q{self.subtotal})"

class Cotizacion(models.Model):
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cotizaciones'
    )
    cliente_nombre = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="Cliente no registrado / Prospecto"
    )
    validez = models.CharField(max_length=100, default="15 días calendario")
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-fecha']
        verbose_name = "Cotización"
        verbose_name_plural = "Cotizaciones"

    @property
    def nombre_destinatario(self):
        if self.cliente:
            return self.cliente.nombre
        return self.cliente_nombre or "Consumidor Final"

    def __str__(self):
        return f"Cotización #{self.id} - {self.nombre_destinatario} (Q{self.total})"

class DetalleCotizacion(models.Model):
    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(Producto, on_delete=models.SET_NULL, null=True, blank=True)
    descripcion = models.CharField(max_length=255, verbose_name="Descripción en PDF")
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        self.subtotal = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cantidad}x {self.descripcion} - Q{self.subtotal}"


class ServicioTecnico(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente de revisión'),
        ('en_proceso', 'En reparación'),
        ('completado', 'Completado / Entregado'),
        ('cancelado', 'Cancelado'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='servicios')
    equipo = models.CharField(max_length=150, verbose_name="Equipo a revisar")
    descripcion_falla = models.TextField(verbose_name="Descripción de la falla")
    costo_mano_obra = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Mano de obra (Q)")
    detalle_mano_obra = models.CharField(max_length=255, blank=True, null=True, verbose_name="Detalle mano de obra")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    fecha_solicitud = models.DateTimeField(default=timezone.now)
    fecha_cierre = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-fecha_solicitud']
        verbose_name = "Servicio Técnico"
        verbose_name_plural = "Servicios Técnicos"

    @property
    def total_repuestos(self):
        return sum(d.total_descontado for d in self.descargas_repuestos.all())

    @property
    def total_reparacion(self):
        return self.total_repuestos + self.costo_mano_obra

    def __str__(self):
        return f"Orden #{self.id} - {self.cliente.nombre} ({self.equipo})"