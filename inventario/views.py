from decimal import Decimal
from io import BytesIO
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import re

from django.core.paginator import Paginator
from django.db.models import Q, Sum

from .models import (
    Producto, Cliente, DescargaInventario, DetalleDescarga,
    Cotizacion, DetalleCotizacion, ServicioTecnico
)


# 1. CARGAR PRODUCTOS AL INVENTARIO
@login_required
def cargar_producto(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        cantidad = int(request.POST.get('cantidad', 0))
        precio = Decimal(request.POST.get('precio', '0.00'))
        foto = request.FILES.get('foto')

        if nombre and cantidad > 0:
            Producto.objects.create(
                nombre=nombre,
                descripcion=descripcion,
                cantidad=cantidad,
                precio=precio,
                foto=foto
            )
            messages.success(request, f'Repuesto "{nombre}" agregado al inventario.')
            return redirect('cargar_producto')

    productos = Producto.objects.filter(activo=True).order_by('-fecha_creacion')
    return render(request, 'inventario/cargar_producto.html', {'productos': productos})


# 2. DESCARGAR MÚLTIPLES PRODUCTOS DE INVENTARIO
@login_required
def descargar_inventario(request):
    if request.method == 'POST':
        motivo = request.POST.get('motivo', 'venta')
        cliente_id = request.POST.get('cliente_id')
        cliente_nombre = request.POST.get('cliente_nombre', '').strip()
        nota_salida = request.POST.get('nota_salida', '').strip()
        productos_ids = request.POST.getlist('producto_id[]')
        cantidades = request.POST.getlist('cantidad[]')

        cliente_obj = Cliente.objects.filter(id=cliente_id).first() if cliente_id else None

        try:
            with transaction.atomic():
                descarga = DescargaInventario.objects.create(
                    motivo=motivo,
                    cliente=cliente_obj,
                    cliente_nombre=cliente_nombre if not cliente_obj else '',
                    nota_salida=nota_salida,
                    usuario=request.user
                )

                items_procesados = 0
                total_salida = Decimal('0.00')

                for prod_id, cant_str in zip(productos_ids, cantidades):
                    if not prod_id:
                        continue
                    cant = int(cant_str or 0)
                    if cant <= 0:
                        continue

                    producto = Producto.objects.select_for_update().get(id=prod_id, activo=True)
                    if producto.cantidad < cant:
                        raise ValueError(
                            f'Stock insuficiente para "{producto.nombre}". Disponible: {producto.cantidad}.'
                        )

                    producto.cantidad -= cant
                    producto.save()

                    detalle = DetalleDescarga.objects.create(
                        descarga=descarga,
                        producto=producto,
                        cantidad=cant,
                        precio_unitario=producto.precio,
                        subtotal=cant * producto.precio
                    )
                    total_salida += detalle.subtotal
                    items_procesados += 1

                if items_procesados == 0:
                    raise ValueError('Selecciona al menos un repuesto válido de la lista.')

                descarga.total_descontado = total_salida
                descarga.save()

            messages.success(
                request,
                f'Salida #{descarga.id} registrada correctamente. Total descontado: Q {total_salida:,.2f}.'
            )
            return redirect('descargar_inventario')

        except ValueError as e:
            messages.error(request, str(e))

    productos = Producto.objects.filter(activo=True, cantidad__gt=0)
    clientes = Cliente.objects.all()
    
    historial = DescargaInventario.objects.select_related(
        'cliente', 'servicio_tecnico', 'servicio_tecnico__cotizacion', 'usuario'
    ).prefetch_related(
        'detalles__producto',
        'servicio_tecnico__descargas_repuestos__detalles__producto',
        'servicio_tecnico__cotizacion__items'
    ).all()

    return render(request, 'inventario/descargar_inventario.html', {
        'productos': productos,
        'clientes': clientes,
        'historial': historial,
    })


# 3. PANTALLA DE COTIZACIONES
@login_required
def cotizaciones(request):
    productos = Producto.objects.filter(activo=True)
    clientes = Cliente.objects.all()
    historial_cotizaciones = Cotizacion.objects.select_related('cliente', 'servicio_tecnico').prefetch_related('items').all()[:30]
    return render(request, 'inventario/cotizaciones.html', {
        'productos': productos,
        'clientes': clientes,
        'historial_cotizaciones': historial_cotizaciones,
    })


# --- FUNCIÓN AUXILIAR REUTILIZABLE PARA CONSTRUIR EL PDF ---
def construir_pdf_cotizacion(cotizacion):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    elements = []

    titulo_style = ParagraphStyle('Titulo', parent=styles['Heading1'], textColor=colors.HexColor('#0369a1'), fontSize=18)
    elements.append(Paragraph("INVENTARIO CHOMIN - REPUESTOS DE REFRIGERACIÓN", titulo_style))
    elements.append(Paragraph(
        f"<b>Cotización N.º:</b> COT-{cotizacion.id:04d} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Fecha:</b> {cotizacion.fecha.strftime('%d/%m/%Y')}",
        styles['Normal']
    ))
    elements.append(Spacer(1, 12))

    cliente = cotizacion.cliente
    nombre_cli = cotizacion.nombre_destinatario
    tel_cli = cliente.telefono if cliente else "N/A"
    dir_cli = cliente.direccion if cliente else "N/A"

    elements.append(Paragraph(f"<b>Cliente:</b> {nombre_cli}", styles['Normal']))
    elements.append(Paragraph(f"<b>Teléfono:</b> {tel_cli} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Dirección:</b> {dir_cli}", styles['Normal']))
    elements.append(Paragraph(f"<b>Validez de la oferta:</b> {cotizacion.validez}", styles['Normal']))

    # Bloque de orden técnica y trabajo a realizar (si aplica)
    if cotizacion.servicio_tecnico:
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(
            f"<b>Orden Técnica N.º:</b> ORD-{cotizacion.servicio_tecnico.id:04d} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Equipo:</b> {cotizacion.servicio_tecnico.equipo}",
            styles['Normal']
        ))

    if cotizacion.descripcion_trabajo:
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("<b>Trabajo técnico a realizar:</b>", styles['Normal']))
        elements.append(Spacer(1, 3))
        elements.append(Paragraph(cotizacion.descripcion_trabajo, styles['Normal']))

    elements.append(Spacer(1, 16))

    filas_tabla = [['Cant.', 'Repuesto / Descripción', 'Precio Unit.', 'Subtotal']]
    for item in cotizacion.items.all():
        filas_tabla.append([
            str(item.cantidad),
            Paragraph(item.descripcion, styles['Normal']),
            f"Q {item.precio_unitario:,.2f}",
            f"Q {item.subtotal:,.2f}"
        ])

    if cotizacion.costo_mano_obra > 0:
        filas_tabla.append([
            "1",
            Paragraph("Mano de obra técnica / Servicio de reparación", styles['Normal']),
            f"Q {cotizacion.costo_mano_obra:,.2f}",
            f"Q {cotizacion.costo_mano_obra:,.2f}"
        ])

    filas_tabla.append(['', '', 'TOTAL:', f"Q {cotizacion.total:,.2f}"])

    tabla = Table(filas_tabla, colWidths=[45, 315, 85, 85])
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (2, -1), (-1, -1), colors.HexColor('#e0f2fe')),
        ('FONTNAME', (2, -1), (-1, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (2, -1), (-1, -1), colors.HexColor('#0369a1')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(tabla)
    elements.append(Spacer(1, 24))
    elements.append(Paragraph(
        "<i>Precios expresados en Quetzales (GTQ). Sujeto a disponibilidad de stock al confirmar pedido.</i>",
        styles['Normal']
    ))

    doc.build(elements)
    buffer.seek(0)

    nombre_archivo = nombre_cli.replace(' ', '_')
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Cotizacion_{cotizacion.id}_{nombre_archivo}.pdf"'
    return response


# 3.1 CREAR COTIZACIÓN Y DESCARGAR PDF
@login_required
def generar_cotizacion_pdf(request):
    if request.method != 'POST':
        return redirect('cotizaciones')

    cliente_id = request.POST.get('cliente_id')
    cliente_nombre = request.POST.get('cliente_nombre', '').strip()
    validez = request.POST.get('validez', '15 días calendario')

    productos_ids = request.POST.getlist('producto[]')
    nombres_items = request.POST.getlist('item_nombre[]')
    cantidades = request.POST.getlist('cantidad[]')
    precios = request.POST.getlist('precio[]')
    descripciones = request.POST.getlist('descripcion[]')

    cliente = Cliente.objects.filter(id=cliente_id).first() if cliente_id else None

    with transaction.atomic():
        cotizacion = Cotizacion.objects.create(
            cliente=cliente,
            cliente_nombre=cliente_nombre if not cliente else '',
            validez=validez,
            usuario=request.user
        )

        total_general = Decimal('0.00')
        for prod_id, nombre_item, cant_str, precio_str, desc in zip(
            productos_ids, nombres_items, cantidades, precios, descripciones
        ):
            nombre_limpio = nombre_item.strip()
            desc_limpia = desc.strip()
            if not prod_id and not nombre_limpio and not desc_limpia:
                continue

            producto = Producto.objects.filter(id=prod_id).first() if prod_id else None
            cant = int(cant_str or 1)
            precio_unit = Decimal(precio_str or '0.00')

            base_titulo = producto.nombre if producto else (nombre_limpio or 'Servicio / Ítem')
            if desc_limpia and desc_limpia.lower() != base_titulo.lower():
                texto_desc = f"{base_titulo} - {desc_limpia}" if base_titulo not in desc_limpia else desc_limpia
            else:
                texto_desc = base_titulo

            detalle = DetalleCotizacion.objects.create(
                cotizacion=cotizacion,
                producto=producto,
                descripcion=texto_desc,
                cantidad=cant,
                precio_unitario=precio_unit,
                subtotal=cant * precio_unit
            )
            total_general += detalle.subtotal

        cotizacion.total = total_general
        cotizacion.save()

    return construir_pdf_cotizacion(cotizacion)


# 3.2 RE-DESCARGAR COTIZACIÓN EXISTENTE
@login_required
def descargar_cotizacion_pdf(request, cotizacion_id):
    cotizacion = get_object_or_404(
        Cotizacion.objects.select_related('cliente', 'servicio_tecnico').prefetch_related('items'),
        id=cotizacion_id
    )
    return construir_pdf_cotizacion(cotizacion)


# 4. CLIENTES Y SERVICIO TÉCNICO
@login_required
def clientes(request):
    lista_clientes = Cliente.objects.prefetch_related('cotizaciones', 'servicios', 'descargas').all()
    servicios = ServicioTecnico.objects.select_related('cliente', 'cotizacion').prefetch_related(
        'descargas_repuestos__detalles__producto',
        'cotizacion__items__producto'
    ).all()
    ordenes_activas_count = servicios.filter(
        estado__in=['pendiente', 'esperando_aprobacion', 'en_proceso']
    ).count()
    productos_disponibles = Producto.objects.filter(activo=True, cantidad__gt=0)
    todos_productos_activos = Producto.objects.filter(activo=True)

    return render(request, 'inventario/clientes.html', {
        'clientes': lista_clientes,
        'servicios': servicios,
        'ordenes_activas_count': ordenes_activas_count,
        'productos': productos_disponibles,
        'catalogo_cotizacion': todos_productos_activos,
    })


@login_required
def crear_cliente(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        telefono = re.sub(r'\D', '', request.POST.get('telefono', ''))
        direccion = request.POST.get('direccion', '').strip()

        if len(telefono) != 8:
            messages.error(request, 'El número de teléfono debe contener exactamente 8 dígitos.')
            return redirect(request.META.get('HTTP_REFERER', 'clientes'))

        if nombre:
            Cliente.objects.create(nombre=nombre, telefono=telefono, direccion=direccion)
            messages.success(request, f'Cliente "{nombre}" registrado correctamente.')
    return redirect('clientes')


@login_required
def editar_cliente(request, cliente_id):
    if request.method == 'POST':
        cliente = get_object_or_404(Cliente, id=cliente_id)
        nombre = request.POST.get('nombre', '').strip()
        telefono = re.sub(r'\D', '', request.POST.get('telefono', ''))
        direccion = request.POST.get('direccion', '').strip()

        if len(telefono) != 8:
            messages.error(request, 'El número de teléfono debe contener exactamente 8 dígitos.')
            return redirect(request.META.get('HTTP_REFERER', 'clientes'))

        if nombre:
            cliente.nombre = nombre
            cliente.telefono = telefono
            cliente.direccion = direccion
            cliente.save()
            messages.success(request, f'Datos de "{cliente.nombre}" actualizados.')

    return redirect(request.META.get('HTTP_REFERER', 'clientes'))


@login_required
def crear_servicio_tecnico(request):
    if request.method == 'POST':
        cliente_id = request.POST.get('cliente_id')
        equipo = request.POST.get('equipo', '').strip()
        descripcion_falla = request.POST.get('descripcion_falla', '').strip()

        cliente = get_object_or_404(Cliente, id=cliente_id)
        ServicioTecnico.objects.create(
            cliente=cliente,
            equipo=equipo,
            descripcion_falla=descripcion_falla
        )
        messages.success(request, f'Orden técnica creada para {cliente.nombre}.')
    return redirect('clientes')


@login_required
def perfil_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    cotizaciones_cliente = cliente.cotizaciones.prefetch_related('items').all()
    servicios_cliente = cliente.servicios.select_related('cotizacion').prefetch_related(
        'descargas_repuestos__detalles__producto'
    ).all()
    descargas_cliente = cliente.descargas.prefetch_related('detalles__producto').all()
    productos_disponibles = Producto.objects.filter(activo=True, cantidad__gt=0)

    return render(request, 'inventario/perfil_cliente.html', {
        'cliente': cliente,
        'cotizaciones': cotizaciones_cliente,
        'servicios': servicios_cliente,
        'descargas': descargas_cliente,
        'productos': productos_disponibles,
    })


@login_required
def actualizar_estado_servicio(request, servicio_id):
    if request.method == 'POST':
        servicio = get_object_or_404(ServicioTecnico, id=servicio_id)
        nuevo_estado = request.POST.get('estado')
        estados_validos = dict(ServicioTecnico.ESTADO_CHOICES).keys()

        if nuevo_estado in estados_validos:
            servicio.estado = nuevo_estado
            if nuevo_estado == 'completado' and not servicio.fecha_cierre:
                servicio.fecha_cierre = timezone.now()
            elif nuevo_estado != 'completado':
                servicio.fecha_cierre = None
            servicio.save()
            messages.success(
                request,
                f'Estado de la Orden #{servicio.id} actualizado a "{servicio.get_estado_display()}".'
            )

        return redirect(request.META.get('HTTP_REFERER', 'clientes'))
    return redirect('clientes')


@login_required
def editar_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id, activo=True)

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        cantidad = int(request.POST.get('cantidad', producto.cantidad))
        precio = Decimal(request.POST.get('precio', producto.precio))
        nueva_foto = request.FILES.get('foto')
        eliminar_foto = request.POST.get('eliminar_foto') == 'on'

        if nombre and cantidad >= 0:
            producto.nombre = nombre
            producto.descripcion = descripcion
            producto.cantidad = cantidad
            producto.precio = precio

            if eliminar_foto and producto.foto:
                producto.foto.delete(save=False)
                producto.foto = None
            elif nueva_foto:
                if producto.foto:
                    producto.foto.delete(save=False)
                producto.foto = nueva_foto

            producto.save()
            messages.success(request, f'Repuesto "{producto.nombre}" actualizado correctamente.')
            return redirect('cargar_producto')

    return render(request, 'inventario/editar_producto.html', {'producto': producto})


# --- DAR DE BAJA PRODUCTO ---
@login_required
def dar_baja_producto(request, producto_id):
    if request.method == 'POST':
        producto = get_object_or_404(Producto, id=producto_id, activo=True)
        producto.activo = False
        producto.save()
        messages.success(request, f'Repuesto "{producto.nombre}" dado de baja del inventario activo.')
    return redirect('cargar_producto')


@login_required
def cargar_repuestos_servicio(request, servicio_id):
    servicio = get_object_or_404(ServicioTecnico.objects.select_related('cliente'), id=servicio_id)

    if request.method == 'POST':
        productos_ids = request.POST.getlist('producto_id[]')
        cantidades = request.POST.getlist('cantidad[]')
        mano_obra_str = request.POST.get('costo_mano_obra', '').strip()
        detalle_mano_obra = request.POST.get('detalle_mano_obra', '').strip()

        costo_mano_obra = Decimal(mano_obra_str) if mano_obra_str else Decimal('0.00')
        if costo_mano_obra < 0:
            messages.error(request, 'El costo de mano de obra no puede ser negativo.')
            return redirect(request.META.get('HTTP_REFERER', 'clientes'))

        try:
            with transaction.atomic():
                items_validos = []
                for prod_id, cant_str in zip(productos_ids, cantidades):
                    if not prod_id:
                        continue
                    cant = int(cant_str or 0)
                    if cant > 0:
                        items_validos.append((prod_id, cant))

                if not items_validos and costo_mano_obra == 0 and not detalle_mano_obra:
                    raise ValueError('Agrega al menos un repuesto o ingresa un costo de mano de obra.')

                total_repuestos = Decimal('0.00')
                descarga = None

                if items_validos:
                    descarga = DescargaInventario.objects.create(
                        motivo='tecnico',
                        cliente=servicio.cliente,
                        servicio_tecnico=servicio,
                        nota_salida=f'Orden Técnica #{servicio.id} - {servicio.equipo}',
                        usuario=request.user
                    )

                    for prod_id, cant in items_validos:
                        producto = Producto.objects.select_for_update().get(id=prod_id, activo=True)
                        if producto.cantidad < cant:
                            raise ValueError(
                                f'Stock insuficiente para "{producto.nombre}". Disponible: {producto.cantidad}.'
                            )

                        producto.cantidad -= cant
                        producto.save()

                        detalle = DetalleDescarga.objects.create(
                            descarga=descarga,
                            producto=producto,
                            cantidad=cant,
                            precio_unitario=producto.precio,
                            subtotal=cant * producto.precio
                        )
                        total_repuestos += detalle.subtotal

                    descarga.total_descontado = total_repuestos
                    descarga.save()

                if mano_obra_str != '':
                    servicio.costo_mano_obra = costo_mano_obra
                if detalle_mano_obra:
                    servicio.detalle_mano_obra = detalle_mano_obra
                servicio.save()

            messages.success(
                request,
                f'Orden #{servicio.id} actualizada (Repuestos: Q {total_repuestos:,.2f} • Mano de obra: Q {servicio.costo_mano_obra:,.2f}).'
            )

        except ValueError as e:
            messages.error(request, str(e))

    return redirect(request.META.get('HTTP_REFERER', 'clientes'))


@login_required
def descargar_constancia_servicio_pdf(request, servicio_id):
    servicio = get_object_or_404(
        ServicioTecnico.objects.select_related('cliente').prefetch_related(
            'descargas_repuestos__detalles__producto'
        ),
        id=servicio_id
    )
    if servicio.estado != 'completado':
        messages.warning(
            request,
            f'La constancia de la Orden #{servicio.id} solo puede descargarse cuando el trabajo esté "Completado / Entregado".'
        )
        return redirect(request.META.get('HTTP_REFERER', 'clientes'))

    cliente = servicio.cliente

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    elements = []

    titulo_style = ParagraphStyle(
        'TituloConstancia',
        parent=styles['Heading1'],
        textColor=colors.HexColor('#0369a1'),
        fontSize=16,
        spaceAfter=4
    )
    subtitulo_style = ParagraphStyle(
        'SubtituloConstancia',
        parent=styles['Normal'],
        textColor=colors.HexColor('#475569'),
        fontSize=9.5,
        spaceAfter=10
    )

    # Encabezado
    elements.append(Paragraph("INVENTARIO CHOMIN — SERVICIO TÉCNICO DE REFRIGERACIÓN", titulo_style))
    elements.append(Paragraph(
        f"<b>CONSTANCIA DE REPARACIÓN Y ENTREGA</b> &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Orden N.º:</b> ORD-{servicio.id:04d} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Estado:</b> {servicio.get_estado_display()}",
        subtitulo_style
    ))
    elements.append(Spacer(1, 8))

    # Ficha de Cliente y Equipo
    fecha_ingreso = servicio.fecha_solicitud.strftime('%d/%m/%Y %H:%M')
    fecha_entrega = servicio.fecha_cierre.strftime('%d/%m/%Y %H:%M') if servicio.fecha_cierre else "En proceso / Pendiente de cierre"

    datos_ficha = [
        [
            Paragraph(f"<b>Cliente:</b> {cliente.nombre}", styles['Normal']),
            Paragraph(f"<b>Teléfono:</b> {cliente.telefono}", styles['Normal'])
        ],
        [
            Paragraph(f"<b>Dirección:</b> {cliente.direccion}", styles['Normal']),
            Paragraph(f"<b>Equipo:</b> {servicio.equipo}", styles['Normal'])
        ],
        [
            Paragraph(f"<b>Fecha de ingreso:</b> {fecha_ingreso}", styles['Normal']),
            Paragraph(f"<b>Fecha de cierre / entrega:</b> {fecha_entrega}", styles['Normal'])
        ],
    ]
    tabla_ficha = Table(datos_ficha, colWidths=[265, 265])
    tabla_ficha.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(tabla_ficha)
    elements.append(Spacer(1, 14))

    # Diagnóstico y Trabajo Realizado
    elements.append(Paragraph("<b>1. Falla Reportada / Diagnóstico Inicial:</b>", styles['Normal']))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(servicio.descripcion_falla, styles['Normal']))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("<b>2. Trabajo Técnico Realizado:</b>", styles['Normal']))
    elements.append(Spacer(1, 4))
    trabajo_texto = servicio.detalle_mano_obra if servicio.detalle_mano_obra else "Revisión, ajuste y pruebas de funcionamiento general del equipo."
    elements.append(Paragraph(trabajo_texto, styles['Normal']))
    elements.append(Spacer(1, 16))

    # Tabla de Repuestos y Mano de Obra
    elements.append(Paragraph("<b>3. Desglose de Repuestos Utilizados y Mano de Obra:</b>", styles['Normal']))
    elements.append(Spacer(1, 6))

    filas_costos = [['Cant.', 'Concepto / Repuesto Instalado', 'Precio Unit.', 'Subtotal']]
    tiene_items = False

    for desc in servicio.descargas_repuestos.all():
        for item in desc.detalles.all():
            tiene_items = True
            filas_costos.append([
                str(item.cantidad),
                Paragraph(f"{item.producto.nombre} <font size='8' color='#64748b'>(Salida #{desc.id:04d})</font>", styles['Normal']),
                f"Q {item.precio_unitario:,.2f}",
                f"Q {item.subtotal:,.2f}"
            ])

    if servicio.costo_mano_obra > 0:
        tiene_items = True
        desc_mo = f"Mano de obra técnica ({servicio.detalle_mano_obra})" if servicio.detalle_mano_obra else "Mano de obra técnica"
        filas_costos.append([
            "1",
            Paragraph(desc_mo, styles['Normal']),
            f"Q {servicio.costo_mano_obra:,.2f}",
            f"Q {servicio.costo_mano_obra:,.2f}"
        ])

    if not tiene_items:
        filas_costos.append(['-', 'Sin cargos de repuestos ni mano de obra registrados.', 'Q 0.00', 'Q 0.00'])

    filas_costos.append(['', '', 'TOTAL SERVICIO:', f"Q {servicio.total_reparacion:,.2f}"])

    tabla_costos = Table(filas_costos, colWidths=[45, 315, 85, 85])
    tabla_costos.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (2, -1), (-1, -1), colors.HexColor('#e0f2fe')),
        ('FONTNAME', (2, -1), (-1, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (2, -1), (-1, -1), colors.HexColor('#0369a1')),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    elements.append(tabla_costos)
    elements.append(Spacer(1, 20))

    # Cierre digital (optimizado para envío por WhatsApp)
    elements.append(Paragraph(
        f"<b>Emitido por:</b> Inventario Chomin &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Fecha de emisión:</b> {timezone.now().strftime('%d/%m/%Y %H:%M')}",
        styles['Normal']
    ))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(
        "<i>Nota: Documento digital emitido por Inventario Chomin como constancia técnica de los trabajos realizados "
        "y repuestos instalados; no sustituye a la factura contable (FEL). Precios expresados en Quetzales (GTQ).</i>",
        styles['Normal']
    ))

    doc.build(elements)
    buffer.seek(0)

    nombre_archivo = cliente.nombre.replace(' ', '_')
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Constancia_Orden_{servicio.id}_{nombre_archivo}.pdf"'
    return response


@login_required
def cotizar_orden_servicio(request, servicio_id):
    servicio = get_object_or_404(
        ServicioTecnico.objects.select_related('cliente').prefetch_related('cotizacion__items__producto'),
        id=servicio_id
    )
    cotizacion = getattr(servicio, 'cotizacion', None)
    productos = Producto.objects.filter(activo=True)

    if request.method == 'POST':
        if cotizacion and cotizacion.estado == 'aprobada':
            messages.error(request, 'Esta cotización ya fue aprobada y descontada de bodega; no puede editarse.')
            return redirect('clientes')

        productos_ids = request.POST.getlist('producto_id[]')
        descripciones = request.POST.getlist('descripcion[]')
        cantidades = request.POST.getlist('cantidad[]')
        precios = request.POST.getlist('precio[]')
        validez = request.POST.get('validez', '15 días calendario').strip() or '15 días calendario'
        descripcion_trabajo = request.POST.get('descripcion_trabajo', '').strip()
        mano_obra_str = request.POST.get('costo_mano_obra', '0').strip()
        costo_mano_obra = Decimal(mano_obra_str or '0.00')

        try:
            if costo_mano_obra < 0:
                raise ValueError('El costo de mano de obra no puede ser negativo.')

            with transaction.atomic():
                if not cotizacion:
                    cotizacion = Cotizacion.objects.create(
                        cliente=servicio.cliente,
                        servicio_tecnico=servicio,
                        validez=validez,
                        descripcion_trabajo=descripcion_trabajo,
                        costo_mano_obra=costo_mano_obra,
                        usuario=request.user
                    )
                else:
                    cotizacion.validez = validez
                    cotizacion.descripcion_trabajo = descripcion_trabajo
                    cotizacion.costo_mano_obra = costo_mano_obra
                    cotizacion.items.all().delete()

                total_repuestos = Decimal('0.00')
                items_guardados = 0

                for prod_id, desc, cant_str, precio_str in zip(
                    productos_ids, descripciones, cantidades, precios
                ):
                    desc_limpia = desc.strip()
                    if not desc_limpia:
                        continue
                    cant = int(cant_str or 1)
                    precio = Decimal(precio_str or '0.00')
                    if cant <= 0 or precio < 0:
                        continue

                    producto_obj = Producto.objects.filter(id=prod_id, activo=True).first() if prod_id else None
                    sub = cant * precio

                    DetalleCotizacion.objects.create(
                        cotizacion=cotizacion,
                        producto=producto_obj,
                        es_mano_obra=(producto_obj is None),
                        descripcion=desc_limpia,
                        cantidad=cant,
                        precio_unitario=precio,
                        subtotal=sub
                    )
                    total_repuestos += sub
                    items_guardados += 1

                if items_guardados == 0 and costo_mano_obra == 0:
                    raise ValueError('Agrega al menos un repuesto o un costo de mano de obra a la cotización.')

                cotizacion.total = total_repuestos + costo_mano_obra
                cotizacion.save()

                if servicio.estado in ['pendiente', 'esperando_aprobacion']:
                    servicio.estado = 'esperando_aprobacion'
                    servicio.save()

            messages.success(
                request,
                f'Cotización COT-{cotizacion.id:04d} guardada (Total: Q {cotizacion.total:,.2f}).'
            )
            if request.POST.get('accion') == 'guardar_pdf':
                return redirect('descargar_cotizacion_pdf', cotizacion_id=cotizacion.id)
            return redirect('clientes')

        except ValueError as e:
            messages.error(request, str(e))

    return render(request, 'inventario/cotizar_orden.html', {
        'servicio': servicio,
        'cotizacion': cotizacion,
        'productos': productos,
    })


@login_required
def aprobar_cotizacion_orden(request, cotizacion_id):
    if request.method == 'POST':
        cotizacion = get_object_or_404(
            Cotizacion.objects.select_related('servicio_tecnico', 'cliente').prefetch_related('items__producto'),
            id=cotizacion_id
        )
        servicio = cotizacion.servicio_tecnico

        if not servicio:
            messages.error(request, 'Esta cotización no está vinculada a una orden de servicio técnico.')
            return redirect('cotizaciones')

        if cotizacion.estado == 'aprobada':
            messages.info(request, f'La cotización COT-{cotizacion.id:04d} ya estaba aprobada.')
            return redirect('clientes')

        try:
            with transaction.atomic():
                items_repuestos = [it for it in cotizacion.items.all() if it.producto and not it.es_mano_obra]
                items_mo = [it for it in cotizacion.items.all() if it.es_mano_obra or not it.producto]

                # 1. Descontar repuestos del inventario
                if items_repuestos:
                    descarga = DescargaInventario.objects.create(
                        motivo='tecnico',
                        cliente=servicio.cliente,
                        servicio_tecnico=servicio,
                        nota_salida=f'Aprobación COT-{cotizacion.id:04d} — Orden #{servicio.id}',
                        usuario=request.user
                    )
                    total_rep = Decimal('0.00')

                    for item in items_repuestos:
                        prod = Producto.objects.select_for_update().get(id=item.producto.id, activo=True)
                        if prod.cantidad < item.cantidad:
                            raise ValueError(
                                f'Stock insuficiente para "{prod.nombre}". Cotizado: {item.cantidad}, Disponible: {prod.cantidad}.'
                            )
                        prod.cantidad -= item.cantidad
                        prod.save()

                        DetalleDescarga.objects.create(
                            descarga=descarga,
                            producto=prod,
                            cantidad=item.cantidad,
                            precio_unitario=item.precio_unitario,
                            subtotal=item.subtotal
                        )
                        total_rep += item.subtotal

                    descarga.total_descontado = total_rep
                    descarga.save()

                # 2. Transferir mano de obra y descripción del trabajo a la orden
                total_mo = cotizacion.costo_mano_obra + sum((it.subtotal for it in items_mo), Decimal('0.00'))
                if total_mo > 0:
                    servicio.costo_mano_obra += total_mo

                resumen_trabajo = cotizacion.descripcion_trabajo or ", ".join(it.descripcion for it in items_mo)
                if resumen_trabajo:
                    servicio.detalle_mano_obra = (
                        f"{servicio.detalle_mano_obra} | {resumen_trabajo}"
                        if servicio.detalle_mano_obra else resumen_trabajo
                    )

                # Pasar la orden a "En reparación"
                if servicio.estado in ['pendiente', 'esperando_aprobacion']:
                    servicio.estado = 'en_proceso'
                servicio.save()

                # 3. Marcar cotización como aprobada
                cotizacion.estado = 'aprobada'
                cotizacion.fecha_aprobacion = timezone.now()
                cotizacion.save()

            messages.success(
                request,
                f'Cotización COT-{cotizacion.id:04d} aprobada: repuestos descontados de bodega y Orden #{servicio.id} pasó a "En reparación".'
            )

        except ValueError as e:
            messages.error(request, str(e))

    return redirect(request.META.get('HTTP_REFERER', 'clientes'))


# 5. HISTORIAL GENERAL Y BITÁCORA DEL TALLER
@login_required
def historial_taller(request):
    q = request.GET.get('q', '').strip()
    fecha_inicio = request.GET.get('fecha_inicio', '').strip()
    fecha_fin = request.GET.get('fecha_fin', '').strip()
    estado_orden = request.GET.get('estado', '').strip()
    tab_activa = request.GET.get('tab', 'ordenes')

    # 1. Queryset base de Órdenes de Servicio
    qs_servicios = ServicioTecnico.objects.select_related('cliente', 'cotizacion').prefetch_related(
        'descargas_repuestos__detalles__producto',
        'cotizacion__items'
    ).all()

    # 2. Queryset base de Cotizaciones
    qs_cotizaciones = Cotizacion.objects.select_related('cliente', 'servicio_tecnico').prefetch_related('items').all()

    # 3. Queryset base de Salidas de Inventario
    qs_descargas = DescargaInventario.objects.select_related(
        'cliente', 'servicio_tecnico', 'usuario'
    ).prefetch_related('detalles__producto').all()

    # Aplicar filtros de búsqueda y fechas
    if q:
        q_num = q.lstrip('#').replace('ORD-', '').replace('ord-', '').replace('COT-', '').replace('cot-', '')
        filtro_id = Q(id=int(q_num)) if q_num.isdigit() else Q()

        qs_servicios = qs_servicios.filter(
            filtro_id |
            Q(cliente__nombre__icontains=q) |
            Q(equipo__icontains=q) |
            Q(descripcion_falla__icontains=q) |
            Q(detalle_mano_obra__icontains=q)
        )
        qs_cotizaciones = qs_cotizaciones.filter(
            filtro_id |
            Q(cliente__nombre__icontains=q) |
            Q(cliente_nombre__icontains=q) |
            Q(descripcion_trabajo__icontains=q) |
            Q(items__descripcion__icontains=q)
        ).distinct()
        qs_descargas = qs_descargas.filter(
            filtro_id |
            Q(cliente__nombre__icontains=q) |
            Q(cliente_nombre__icontains=q) |
            Q(nota_salida__icontains=q) |
            Q(detalles__producto__nombre__icontains=q)
        ).distinct()

    if fecha_inicio:
        qs_servicios = qs_servicios.filter(fecha_solicitud__date__gte=fecha_inicio)
        qs_cotizaciones = qs_cotizaciones.filter(fecha__date__gte=fecha_inicio)
        qs_descargas = qs_descargas.filter(fecha__date__gte=fecha_inicio)

    if fecha_fin:
        qs_servicios = qs_servicios.filter(fecha_solicitud__date__lte=fecha_fin)
        qs_cotizaciones = qs_cotizaciones.filter(fecha__date__lte=fecha_fin)
        qs_descargas = qs_descargas.filter(fecha__date__lte=fecha_fin)

    if estado_orden:
        qs_servicios = qs_servicios.filter(estado=estado_orden)

    # KPIs del período filtrado
    servicios_completados = [s for s in qs_servicios if s.estado == 'completado']
    total_ingresos_taller = sum((s.total_reparacion for s in servicios_completados), Decimal('0.00'))
    total_ventas_mostrador = qs_descargas.filter(motivo='venta').aggregate(s=Sum('total_descontado'))['s'] or Decimal('0.00')
    cotizaciones_aprobadas_count = qs_cotizaciones.filter(estado='aprobada').count()

    # Paginación (20 por página para evitar scroll largo)
    page_ordenes = Paginator(qs_servicios, 20).get_page(request.GET.get('page_ordenes'))
    page_cotizaciones = Paginator(qs_cotizaciones, 20).get_page(request.GET.get('page_cot'))
    page_descargas = Paginator(qs_descargas, 20).get_page(request.GET.get('page_desc'))

    return render(request, 'inventario/historial_taller.html', {
        'q': q,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'estado_orden': estado_orden,
        'tab_activa': tab_activa,
        'page_ordenes': page_ordenes,
        'page_cotizaciones': page_cotizaciones,
        'page_descargas': page_descargas,
        'total_ordenes': qs_servicios.count(),
        'total_cotizaciones': qs_cotizaciones.count(),
        'total_descargas': qs_descargas.count(),
        'cotizaciones_aprobadas_count': cotizaciones_aprobadas_count,
        'total_ingresos_taller': total_ingresos_taller,
        'total_ventas_mostrador': total_ventas_mostrador,
    })