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
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Flowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from reportlab.pdfgen import canvas as pdf_canvas
import re
import math

from django.core.paginator import Paginator
from django.db.models import Q, Sum

from .models import (
    Producto, Cliente, DescargaInventario, DetalleDescarga,
    Cotizacion, DetalleCotizacion, ServicioTecnico
)


# ==============================================================================
# HELPER DE ZONA HORARIA LOCAL (GUATEMALA)
# ==============================================================================
def formatear_fecha_local(dt, formato='%d/%m/%Y %H:%M'):
    """Convierte cualquier datetime (aware o naive) a la hora local de settings.TIME_ZONE."""
    if not dt:
        return ''
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return timezone.localtime(dt).strftime(formato)


# ==============================================================================
# SISTEMA DE DISEÑO PDF CORPORATIVO — TECNI SOLUTION
# ==============================================================================
BRAND_NAVY = colors.HexColor('#091326')
BRAND_COLD = colors.HexColor('#0284c7')
BRAND_COLD_DARK = colors.HexColor('#0369a1')
BRAND_COLD_LIGHT = colors.HexColor('#e0f2fe')
BRAND_ICE = colors.HexColor('#bae6fd')
BRAND_WARM = colors.HexColor('#f97316')
BRAND_SURFACE = colors.HexColor('#f4f7fb')
BRAND_BORDER = colors.HexColor('#cbd5e1')
BRAND_SLATE = colors.HexColor('#475569')
BRAND_SUCCESS = colors.HexColor('#16a34a')


class TecniLogoFlowable(Flowable):
    """Dibuja el isotipo vectorial oficial de TECNI SOLUTION (Frío + Calor) en ReportLab."""
    def __init__(self, width=38, height=54):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        c.saveState()
        sx = self.width / 220.0
        sy = self.height / 310.0
        c.translate(0, self.height)
        c.scale(sx, -sy)

        # 1. Engranaje superior frío (cx=102, cy=70)
        cx1, cy1 = 102, 70
        c.setFillColor(BRAND_COLD)
        for i in range(12):
            ang = math.radians(i * 30)
            tx = cx1 + 47 * math.cos(ang)
            ty = cy1 + 47 * math.sin(ang)
            c.saveState()
            c.translate(tx, ty)
            c.rotate(i * 30)
            c.roundRect(-5, -4, 10, 8, 2, stroke=0, fill=1)
            c.restoreState()

        c.setFillColor(BRAND_COLD_DARK)
        c.circle(cx1, cy1, 43, stroke=0, fill=1)
        c.setFillColor(BRAND_NAVY)
        c.setStrokeColor(colors.HexColor('#38bdf8'))
        c.setLineWidth(2.5)
        c.circle(cx1, cy1, 36, stroke=1, fill=1)
        c.setFillColor(colors.HexColor('#f0f9ff'))
        c.circle(cx1, cy1, 29, stroke=0, fill=1)

        # Copo de nieve interior
        c.setStrokeColor(BRAND_COLD_DARK)
        c.setLineWidth(3.5)
        c.setLineCap(1)
        for deg in (0, 60, 120):
            rad = math.radians(deg)
            dx = 21 * math.cos(rad)
            dy = 21 * math.sin(rad)
            c.line(cx1 - dx, cy1 - dy, cx1 + dx, cy1 + dy)

        # 2. Ola azul (aire frío)
        p_cold = c.beginPath()
        p_cold.moveTo(14, 106)
        p_cold.curveTo(48, 152, 138, 158, 166, 105)
        p_cold.curveTo(178, 82, 168, 52, 148, 38)
        p_cold.curveTo(162, 58, 160, 85, 142, 102)
        p_cold.curveTo(112, 128, 52, 128, 14, 106)
        p_cold.close()
        c.setFillColor(BRAND_COLD)
        c.drawPath(p_cold, stroke=0, fill=1)

        # 3. Ola naranja (climatización / calor)
        p_warm = c.beginPath()
        p_warm.moveTo(14, 106)
        p_warm.curveTo(24, 168, 92, 178, 142, 194)
        p_warm.curveTo(172, 204, 188, 220, 194, 242)
        p_warm.curveTo(194, 212, 174, 186, 136, 172)
        p_warm.curveTo(88, 154, 42, 146, 14, 106)
        p_warm.close()
        c.setFillColor(BRAND_WARM)
        c.drawPath(p_warm, stroke=0, fill=1)

        # 4. Sol / Turbina inferior naranja (cx=96, cy=240)
        cx2, cy2 = 96, 240
        c.setFillColor(BRAND_WARM)
        for i in range(14):
            ang = math.radians(i * (360.0 / 14.0))
            tx = cx2 + 37 * math.cos(ang)
            ty = cy2 + 37 * math.sin(ang)
            c.saveState()
            c.translate(tx, ty)
            c.rotate(i * (360.0 / 14.0))
            c.roundRect(-8, -3.5, 16, 7, 2.5, stroke=0, fill=1)
            c.restoreState()

        c.circle(cx2, cy2, 29, stroke=0, fill=1)
        c.setFillColor(BRAND_NAVY)
        c.setStrokeColor(colors.HexColor('#fb923c'))
        c.setLineWidth(3)
        c.circle(cx2, cy2, 21, stroke=1, fill=1)

        # 5. Gota de condensación
        p_drop = c.beginPath()
        p_drop.moveTo(194, 245)
        p_drop.curveTo(194, 245, 206, 263, 206, 272)
        p_drop.curveTo(206, 279, 200.6, 284, 194, 284)
        p_drop.curveTo(187.4, 284, 182, 279, 182, 272)
        p_drop.curveTo(182, 263, 194, 245, 194, 245)
        p_drop.close()
        c.setFillColor(BRAND_ICE)
        c.drawPath(p_drop, stroke=0, fill=1)

        c.restoreState()


class NumberedBrandCanvas(pdf_canvas.Canvas):
    """Canvas con pie de página institucional y paginación automática."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_footer(num_pages)
            super().showPage()
        super().save()

    def draw_footer(self, page_count):
        width, _ = letter
        self.saveState()
        self.setStrokeColor(BRAND_COLD)
        self.setLineWidth(1.2)
        self.line(40, 34, width / 2, 34)
        self.setStrokeColor(BRAND_WARM)
        self.line(width / 2, 34, width - 40, 34)

        self.setFont('Helvetica-Bold', 7.5)
        self.setFillColor(BRAND_NAVY)
        self.drawString(40, 22, "TECNI SOLUTION — Lo mejor en climatización")

        self.setFont('Helvetica', 7.5)
        self.setFillColor(BRAND_SLATE)
        self.drawRightString(width - 40, 22, f"Página {self._pageNumber} de {page_count}")
        self.restoreState()


def _construir_banner_documento(doc_tipo, folio, fecha_texto, extra_badge=None):
    """Genera el encabezado ejecutivo oscuro con el isotipo y folio del documento."""
    styles = getSampleStyleSheet()

    brand_title_style = ParagraphStyle(
        'TecniBrandTitle',
        parent=styles['Normal'],
        fontName='Times-Bold',
        fontSize=19,
        leading=21,
        textColor=colors.white,
    )
    slogan_style = ParagraphStyle(
        'TecniSlogan',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#fdba74'),
    )
    doc_type_style = ParagraphStyle(
        'DocTypeRight',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#7dd3fc'),
    )
    folio_style = ParagraphStyle(
        'FolioRight',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=17,
        alignment=TA_RIGHT,
        textColor=colors.white,
    )
    meta_right_style = ParagraphStyle(
        'MetaRight',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#cbd5e1'),
    )

    logo = TecniLogoFlowable(width=36, height=51)

    bloque_marca = [
        Paragraph("TECNI SOLUTION", brand_title_style),
        Paragraph("LO MEJOR EN CLIMATIZACIÓN", slogan_style),
    ]

    bloque_folio = [
        Paragraph(doc_tipo.upper(), doc_type_style),
        Paragraph(folio, folio_style),
        Paragraph(fecha_texto, meta_right_style),
    ]
    if extra_badge:
        bloque_folio.append(Paragraph(f"<b>{extra_badge}</b>", meta_right_style))

    banner = Table(
        [[logo, bloque_marca, bloque_folio]],
        colWidths=[50, 295, 187]
    )
    banner.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BRAND_NAVY),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (0, 0), 14),
        ('LEFTPADDING', (1, 0), (1, 0), 6),
        ('RIGHTPADDING', (-1, -1), (-1, -1), 16),
        ('TOPPADDING', (0, 0), (-1, -1), 13),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 13),
        ('LINEBELOW', (0, 0), (1, 0), 3, BRAND_COLD),
        ('LINEBELOW', (2, 0), (2, 0), 3, BRAND_WARM),
    ]))
    return banner


# ==============================================================================
# 1. CARGAR PRODUCTOS AL INVENTARIO
# ==============================================================================
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


# ==============================================================================
# 2. DESCARGAR MÚLTIPLES PRODUCTOS DE INVENTARIO
# ==============================================================================
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


# ==============================================================================
# 3. PANTALLA DE COTIZACIONES
# ==============================================================================
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


# --- FUNCIÓN AUXILIAR REUTILIZABLE PARA CONSTRUIR EL PDF DE COTIZACIÓN ---
def construir_pdf_cotizacion(cotizacion):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=36,
        bottomMargin=48
    )
    styles = getSampleStyleSheet()
    elements = []

    label_style = ParagraphStyle(
        'FichaLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        textColor=BRAND_SLATE,
        leading=10
    )
    val_style = ParagraphStyle(
        'FichaVal',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        textColor=BRAND_NAVY,
        leading=12
    )
    body_style = ParagraphStyle(
        'BodyClean',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor('#1e293b'),
        leading=12.5
    )
    note_style = ParagraphStyle(
        'NoteClean',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.2,
        textColor=BRAND_SLATE,
        leading=11.5
    )

    # 1. Banner Corporativo TECNI SOLUTION (con hora local de Guatemala)
    fecha_emision_local = formatear_fecha_local(cotizacion.fecha, '%d/%m/%Y %H:%M')
    estado_txt = f"Estado: {cotizacion.get_estado_display()}" if hasattr(cotizacion, 'get_estado_display') else None
    elements.append(_construir_banner_documento(
        doc_tipo="Cotización Comercial",
        folio=f"COT-{cotizacion.id:04d}",
        fecha_texto=f"Emisión: {fecha_emision_local}",
        extra_badge=estado_txt
    ))
    elements.append(Spacer(1, 14))

    # 2. Ficha de Cliente y Condiciones
    cliente = cotizacion.cliente
    nombre_cli = cotizacion.nombre_destinatario
    tel_cli = cliente.telefono if cliente else "No registrado"
    dir_cli = cliente.direccion if cliente else "Mostrador / Sin dirección"

    ficha_rows = [
        [
            Paragraph("CLIENTE / DESTINATARIO", label_style),
            Paragraph("TELÉFONO DE CONTACTO", label_style),
        ],
        [
            Paragraph(nombre_cli, val_style),
            Paragraph(tel_cli, val_style),
        ],
        [
            Paragraph("DIRECCIÓN", label_style),
            Paragraph("VALIDEZ DE LA OFERTA", label_style),
        ],
        [
            Paragraph(dir_cli, body_style),
            Paragraph(cotizacion.validez, val_style),
        ],
    ]

    if cotizacion.servicio_tecnico:
        ficha_rows.extend([
            [
                Paragraph("ORDEN DE SERVICIO VINCULADA", label_style),
                Paragraph("EQUIPO A INTERVENIR", label_style),
            ],
            [
                Paragraph(f"ORD-{cotizacion.servicio_tecnico.id:04d}", val_style),
                Paragraph(cotizacion.servicio_tecnico.equipo, val_style),
            ],
        ])

    tabla_ficha = Table(ficha_rows, colWidths=[310, 222])
    tabla_ficha.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BRAND_SURFACE),
        ('BOX', (0, 0), (-1, -1), 0.75, BRAND_BORDER),
        ('LINEBEFORE', (1, 0), (1, -1), 0.5, BRAND_BORDER),
        ('LINEBELOW', (0, 1), (-1, 1), 0.5, colors.HexColor('#e2e8f0')),
        ('LINEBELOW', (0, 3), (-1, 3), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(tabla_ficha)

    # 3. Alcance del Trabajo Técnico (si aplica)
    if cotizacion.descripcion_trabajo:
        elements.append(Spacer(1, 12))
        bloque_alcance = Table(
            [[
                Paragraph("ALCANCE DEL TRABAJO TÉCNICO A REALIZAR", label_style),
            ], [
                Paragraph(cotizacion.descripcion_trabajo, body_style),
            ]],
            colWidths=[532]
        )
        bloque_alcance.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('BOX', (0, 0), (-1, -1), 0.6, BRAND_BORDER),
            ('LINEBEFORE', (0, 0), (0, -1), 3.5, BRAND_COLD),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        elements.append(bloque_alcance)

    elements.append(Spacer(1, 16))

    # 4. Tabla de Repuestos y Servicios Cotizados
    filas_tabla = [['CANT.', 'REPUESTO / DESCRIPCIÓN TÉCNICA', 'PRECIO UNIT.', 'SUBTOTAL']]
    for item in cotizacion.items.all():
        filas_tabla.append([
            str(item.cantidad),
            Paragraph(item.descripcion, body_style),
            f"Q {item.precio_unitario:,.2f}",
            f"Q {item.subtotal:,.2f}"
        ])

    if cotizacion.costo_mano_obra > 0:
        filas_tabla.append([
            "1",
            Paragraph("<b>Mano de obra técnica</b> — Servicio especializado de climatización", body_style),
            f"Q {cotizacion.costo_mano_obra:,.2f}",
            f"Q {cotizacion.costo_mano_obra:,.2f}"
        ])

    filas_tabla.append(['', '', 'TOTAL COTIZADO:', f"Q {cotizacion.total:,.2f}"])

    tabla = Table(filas_tabla, colWidths=[45, 317, 85, 85], repeatRows=1)
    estilos_tabla = [
        ('BACKGROUND', (0, 0), (-1, 0), BRAND_NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8.2),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 1), (-1, -2), 9),
        ('GRID', (0, 0), (-1, -2), 0.5, BRAND_BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, BRAND_SURFACE]),
        ('BACKGROUND', (2, -1), (-1, -1), BRAND_COLD_LIGHT),
        ('BOX', (2, -1), (-1, -1), 0.8, BRAND_COLD),
        ('LINEABOVE', (2, -1), (-1, -1), 2, BRAND_COLD),
        ('FONTNAME', (2, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (2, -1), (2, -1), 9),
        ('FONTSIZE', (3, -1), (3, -1), 10.5),
        ('TEXTCOLOR', (2, -1), (-1, -1), BRAND_COLD_DARK),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]
    tabla.setStyle(TableStyle(estilos_tabla))
    elements.append(tabla)
    elements.append(Spacer(1, 20))

    # 5. Nota Comercial
    nota_box = Table(
        [[Paragraph(
            "<b>Condiciones comerciales:</b> Precios expresados en Quetzales (GTQ). "
            "Sujeto a disponibilidad de inventario al momento de confirmar la orden. "
            "Garantía respaldada por <b>TECNI SOLUTION — Lo mejor en climatización</b>.",
            note_style
        )]],
        colWidths=[532]
    )
    nota_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BRAND_SURFACE),
        ('LINEBEFORE', (0, 0), (0, -1), 3, BRAND_WARM),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(nota_box)

    doc.build(elements, canvasmaker=NumberedBrandCanvas)
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


# ==============================================================================
# 4. CLIENTES Y SERVICIO TÉCNICO
# ==============================================================================
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


# ==============================================================================
# CONSTANCIA DE REPARACIÓN Y ENTREGA (PDF CORPORATIVO TECNI SOLUTION)
# ==============================================================================
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
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=36,
        bottomMargin=48
    )
    styles = getSampleStyleSheet()
    elements = []

    label_style = ParagraphStyle(
        'ConstLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        textColor=BRAND_SLATE,
        leading=10
    )
    val_style = ParagraphStyle(
        'ConstVal',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        textColor=BRAND_NAVY,
        leading=12
    )
    body_style = ParagraphStyle(
        'ConstBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor('#1e293b'),
        leading=12.5
    )
    note_style = ParagraphStyle(
        'ConstNote',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.2,
        textColor=BRAND_SLATE,
        leading=11.5
    )

    # Conversión explícita a hora local de Guatemala
    fecha_ingreso = formatear_fecha_local(servicio.fecha_solicitud, '%d/%m/%Y %H:%M')
    fecha_entrega = formatear_fecha_local(
        servicio.fecha_cierre if servicio.fecha_cierre else timezone.now(),
        '%d/%m/%Y %H:%M'
    )
    fecha_emision_doc = formatear_fecha_local(timezone.now(), '%d/%m/%Y %H:%M')

    # 1. Banner Corporativo TECNI SOLUTION
    elements.append(_construir_banner_documento(
        doc_tipo="Constancia de Reparación",
        folio=f"ORD-{servicio.id:04d}",
        fecha_texto=f"Cierre: {fecha_entrega}",
        extra_badge=f"Estado: {servicio.get_estado_display()}"
    ))
    elements.append(Spacer(1, 14))

    # 2. Ficha de Cliente y Equipo Intervenido
    datos_ficha = [
        [
            Paragraph("CLIENTE / PROPIETARIO", label_style),
            Paragraph("TELÉFONO DE CONTACTO", label_style),
        ],
        [
            Paragraph(cliente.nombre, val_style),
            Paragraph(cliente.telefono, val_style),
        ],
        [
            Paragraph("DIRECCIÓN DEL SERVICIO", label_style),
            Paragraph("EQUIPO INTERVENIDO", label_style),
        ],
        [
            Paragraph(cliente.direccion, body_style),
            Paragraph(servicio.equipo, val_style),
        ],
        [
            Paragraph("FECHA DE INGRESO", label_style),
            Paragraph("FECHA DE ENTREGA / CIERRE", label_style),
        ],
        [
            Paragraph(fecha_ingreso, body_style),
            Paragraph(f"<font color='#16a34a'><b>{fecha_entrega}</b></font>", body_style),
        ],
    ]
    tabla_ficha = Table(datos_ficha, colWidths=[266, 266])
    tabla_ficha.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BRAND_SURFACE),
        ('BOX', (0, 0), (-1, -1), 0.75, BRAND_BORDER),
        ('LINEBEFORE', (1, 0), (1, -1), 0.5, BRAND_BORDER),
        ('LINEBELOW', (0, 1), (-1, 1), 0.5, colors.HexColor('#e2e8f0')),
        ('LINEBELOW', (0, 3), (-1, 3), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(tabla_ficha)
    elements.append(Spacer(1, 12))

    # 3. Bloques de Diagnóstico y Trabajo Realizado
    bloque_falla = Table(
        [[
            Paragraph("1. FALLA REPORTADA / DIAGNÓSTICO INICIAL", label_style),
        ], [
            Paragraph(servicio.descripcion_falla, body_style),
        ]],
        colWidths=[532]
    )
    bloque_falla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.6, BRAND_BORDER),
        ('LINEBEFORE', (0, 0), (0, -1), 3.5, BRAND_WARM),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(bloque_falla)
    elements.append(Spacer(1, 8))

    trabajo_texto = servicio.detalle_mano_obra if servicio.detalle_mano_obra else "Revisión, ajuste y pruebas de funcionamiento general del equipo."
    bloque_trabajo = Table(
        [[
            Paragraph("2. TRABAJO TÉCNICO REALIZADO", label_style),
        ], [
            Paragraph(trabajo_texto, body_style),
        ]],
        colWidths=[532]
    )
    bloque_trabajo.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.6, BRAND_BORDER),
        ('LINEBEFORE', (0, 0), (0, -1), 3.5, BRAND_COLD),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(bloque_trabajo)
    elements.append(Spacer(1, 14))

    # 4. Tabla de Repuestos Instalados y Mano de Obra
    elements.append(Paragraph("3. DESGLOSE DE REPUESTOS UTILIZADOS Y MANO DE OBRA", label_style))
    elements.append(Spacer(1, 5))

    filas_costos = [['CANT.', 'CONCEPTO / REPUESTO INSTALADO', 'PRECIO UNIT.', 'SUBTOTAL']]
    tiene_items = False

    for desc in servicio.descargas_repuestos.all():
        for item in desc.detalles.all():
            tiene_items = True
            filas_costos.append([
                str(item.cantidad),
                Paragraph(
                    f"{item.producto.nombre} <font size='7.8' color='#64748b'>(Salida #{desc.id:04d})</font>",
                    body_style
                ),
                f"Q {item.precio_unitario:,.2f}",
                f"Q {item.subtotal:,.2f}"
            ])

    if servicio.costo_mano_obra > 0:
        tiene_items = True
        desc_mo = f"<b>Mano de obra técnica</b> ({servicio.detalle_mano_obra})" if servicio.detalle_mano_obra else "<b>Mano de obra técnica</b>"
        filas_costos.append([
            "1",
            Paragraph(desc_mo, body_style),
            f"Q {servicio.costo_mano_obra:,.2f}",
            f"Q {servicio.costo_mano_obra:,.2f}"
        ])

    if not tiene_items:
        filas_costos.append(['-', 'Sin cargos de repuestos ni mano de obra registrados.', 'Q 0.00', 'Q 0.00'])

    filas_costos.append(['', '', 'TOTAL SERVICIO:', f"Q {servicio.total_reparacion:,.2f}"])

    tabla_costos = Table(filas_costos, colWidths=[45, 317, 85, 85], repeatRows=1)
    tabla_costos.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BRAND_NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8.2),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 1), (-1, -2), 9),
        ('GRID', (0, 0), (-1, -2), 0.5, BRAND_BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, BRAND_SURFACE]),
        ('BACKGROUND', (2, -1), (-1, -1), BRAND_COLD_LIGHT),
        ('BOX', (2, -1), (-1, -1), 0.8, BRAND_COLD),
        ('LINEABOVE', (2, -1), (-1, -1), 2, BRAND_COLD),
        ('FONTNAME', (2, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (2, -1), (2, -1), 9),
        ('FONTSIZE', (3, -1), (3, -1), 10.5),
        ('TEXTCOLOR', (2, -1), (-1, -1), BRAND_COLD_DARK),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(tabla_costos)
    elements.append(Spacer(1, 18))

    # 5. Bloque de Validación Digital
    cierre_box = Table(
        [[Paragraph(
            f"<b>Emitido por:</b> TECNI SOLUTION &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Fecha de emisión:</b> {fecha_emision_doc}<br/>"
            "<i>Documento digital emitido como constancia técnica de los trabajos realizados y repuestos instalados; "
            "no sustituye a la factura contable (FEL). Precios expresados en Quetzales (GTQ).</i>",
            note_style
        )]],
        colWidths=[532]
    )
    cierre_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BRAND_SURFACE),
        ('LINEBEFORE', (0, 0), (0, -1), 3, BRAND_SUCCESS),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(cierre_box)

    doc.build(elements, canvasmaker=NumberedBrandCanvas)
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

        if cotizacion.estado == 'aprobada':
            messages.info(request, f'La cotización COT-{cotizacion.id:04d} ya estaba aprobada.')
            return redirect(request.META.get('HTTP_REFERER', 'cotizaciones'))

        if cotizacion.estado == 'rechazada':
            messages.error(request, f'La cotización COT-{cotizacion.id:04d} fue rechazada y no puede aprobarse.')
            return redirect(request.META.get('HTTP_REFERER', 'cotizaciones'))

        try:
            with transaction.atomic():
                items_repuestos = [it for it in cotizacion.items.all() if it.producto and not it.es_mano_obra]
                items_mo = [it for it in cotizacion.items.all() if it.es_mano_obra or not it.producto]

                # CASO A: COTIZACIÓN VINCULADA A UNA ORDEN DE SERVICIO TÉCNICO
                if servicio:
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

                    total_mo = cotizacion.costo_mano_obra + sum((it.subtotal for it in items_mo), Decimal('0.00'))
                    if total_mo > 0:
                        servicio.costo_mano_obra += total_mo

                    resumen_trabajo = cotizacion.descripcion_trabajo or ", ".join(it.descripcion for it in items_mo)
                    if resumen_trabajo:
                        servicio.detalle_mano_obra = (
                            f"{servicio.detalle_mano_obra} | {resumen_trabajo}"
                            if servicio.detalle_mano_obra else resumen_trabajo
                        )

                    if servicio.estado in ['pendiente', 'esperando_aprobacion']:
                        servicio.estado = 'en_proceso'
                    servicio.save()

                    msg_exito = (
                        f'Cotización COT-{cotizacion.id:04d} aprobada: repuestos descontados de bodega '
                        f'y Orden #{servicio.id} pasó a "En reparación".'
                    )

                # CASO B: COTIZACIÓN DIRECTA DE MOSTRADOR / VENTA
                else:
                    if items_repuestos:
                        descarga = DescargaInventario.objects.create(
                            motivo='venta',
                            cliente=cotizacion.cliente,
                            cliente_nombre=cotizacion.cliente_nombre if not cotizacion.cliente else '',
                            nota_salida=f'Venta aprobada desde Cotización COT-{cotizacion.id:04d}',
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
                        msg_exito = (
                            f'Venta COT-{cotizacion.id:04d} aprobada: se generó la Salida #{descarga.id:04d} '
                            f'y se descontaron los repuestos de bodega.'
                        )
                    else:
                        msg_exito = f'Cotización COT-{cotizacion.id:04d} marcada como aprobada.'

                cotizacion.estado = 'aprobada'
                cotizacion.fecha_aprobacion = timezone.now()
                cotizacion.save()

            messages.success(request, msg_exito)

        except ValueError as e:
            messages.error(request, str(e))

    return redirect(request.META.get('HTTP_REFERER', 'cotizaciones'))


@login_required
def rechazar_cotizacion(request, cotizacion_id):
    if request.method == 'POST':
        cotizacion = get_object_or_404(Cotizacion, id=cotizacion_id)
        if cotizacion.estado == 'aprobada':
            messages.error(request, f'La cotización COT-{cotizacion.id:04d} ya fue aprobada y no puede rechazarse.')
        else:
            cotizacion.estado = 'rechazada'
            cotizacion.save()
            messages.info(request, f'Cotización COT-{cotizacion.id:04d} marcada como rechazada.')
    return redirect(request.META.get('HTTP_REFERER', 'cotizaciones'))



# ==============================================================================
# 5. HISTORIAL GENERAL Y BITÁCORA DEL TALLER
# ==============================================================================
@login_required
def historial_taller(request):
    q = request.GET.get('q', '').strip()
    fecha_inicio = request.GET.get('fecha_inicio', '').strip()
    fecha_fin = request.GET.get('fecha_fin', '').strip()
    estado_orden = request.GET.get('estado', '').strip()
    tab_activa = request.GET.get('tab', 'ordenes')

    qs_servicios = ServicioTecnico.objects.select_related('cliente', 'cotizacion').prefetch_related(
        'descargas_repuestos__detalles__producto',
        'cotizacion__items'
    ).all()

    qs_cotizaciones = Cotizacion.objects.select_related('cliente', 'servicio_tecnico').prefetch_related('items').all()

    qs_descargas = DescargaInventario.objects.select_related(
        'cliente', 'servicio_tecnico', 'usuario'
    ).prefetch_related('detalles__producto').all()

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

    # Constancias entregadas (fuera de los if para que siempre exista y respete todos los filtros)
    qs_constancias = qs_servicios.filter(estado='completado')

    servicios_completados = [s for s in qs_servicios if s.estado == 'completado']
    total_ingresos_taller = sum((s.total_reparacion for s in servicios_completados), Decimal('0.00'))
    total_ventas_mostrador = qs_descargas.filter(motivo='venta').aggregate(s=Sum('total_descontado'))['s'] or Decimal('0.00')
    cotizaciones_aprobadas_count = qs_cotizaciones.filter(estado='aprobada').count()

    page_ordenes = Paginator(qs_servicios, 20).get_page(request.GET.get('page_ordenes'))
    page_cotizaciones = Paginator(qs_cotizaciones, 20).get_page(request.GET.get('page_cot'))
    page_descargas = Paginator(qs_descargas, 20).get_page(request.GET.get('page_desc'))
    page_constancias = Paginator(qs_constancias, 20).get_page(request.GET.get('page_const'))

    return render(request, 'inventario/historial_taller.html', {
        'q': q,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'estado_orden': estado_orden,
        'tab_activa': tab_activa,
        'page_ordenes': page_ordenes,
        'page_cotizaciones': page_cotizaciones,
        'page_descargas': page_descargas,
        'page_constancias': page_constancias,
        'total_ordenes': qs_servicios.count(),
        'total_cotizaciones': qs_cotizaciones.count(),
        'total_descargas': qs_descargas.count(),
        'total_constancias': qs_constancias.count(),
        'cotizaciones_aprobadas_count': cotizaciones_aprobadas_count,
        'total_ingresos_taller': total_ingresos_taller,
        'total_ventas_mostrador': total_ventas_mostrador,
    })