"""
Generador de comprobante PDF para órdenes de prepago.
Utiliza reportlab para crear un PDF profesional y ligero (< 1MB).
"""
import os
from io import BytesIO
from django.conf import settings
from django.core.files.base import ContentFile
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


def generar_comprobante_pdf(orden):
    """
    Genera un comprobante PDF profesional para una OrdenPrepago pagada.
    Guarda el archivo en el campo comprobante_pdf de la orden.

    Args:
        orden: instancia de OrdenPrepago con estado PAGADO.

    Returns:
        str: ruta relativa del archivo PDF guardado.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    # --- Estilos ---
    styles = getSampleStyleSheet()

    color_primario = HexColor('#1a237e')
    color_secundario = HexColor('#283593')
    color_gris = HexColor('#616161')
    color_fondo = HexColor('#f5f5f5')

    titulo_style = ParagraphStyle(
        'Titulo',
        parent=styles['Title'],
        fontSize=20,
        textColor=color_primario,
        alignment=TA_CENTER,
        spaceAfter=4 * mm,
    )

    subtitulo_style = ParagraphStyle(
        'Subtitulo',
        parent=styles['Normal'],
        fontSize=12,
        textColor=color_secundario,
        alignment=TA_CENTER,
        spaceAfter=6 * mm,
    )

    seccion_style = ParagraphStyle(
        'Seccion',
        parent=styles['Heading2'],
        fontSize=13,
        textColor=color_primario,
        spaceBefore=8 * mm,
        spaceAfter=3 * mm,
    )

    normal_style = ParagraphStyle(
        'Normal2',
        parent=styles['Normal'],
        fontSize=10,
        textColor=color_gris,
        leading=14,
    )

    bold_style = ParagraphStyle(
        'Bold2',
        parent=styles['Normal'],
        fontSize=10,
        textColor=HexColor('#212121'),
        leading=14,
    )

    aviso_style = ParagraphStyle(
        'Aviso',
        parent=styles['Normal'],
        fontSize=9,
        textColor=HexColor('#d32f2f'),
        alignment=TA_CENTER,
        spaceBefore=4 * mm,
    )

    # --- Elementos del PDF ---
    elements = []

    # Encabezado
    elements.append(Paragraph("⛽ SurtidorBolivia", titulo_style))
    elements.append(Paragraph("Comprobante de Prepago de Combustible", subtitulo_style))
    elements.append(HRFlowable(width="100%", thickness=1, color=color_primario))
    elements.append(Spacer(1, 4 * mm))

    # Datos de la orden
    elements.append(Paragraph("Datos de la Orden", seccion_style))
    orden_data = [
        ["Número de Orden:", orden.numero_orden],
        ["Fecha de Compra:", orden.fecha_creacion.strftime('%d/%m/%Y %H:%M:%S') if orden.fecha_creacion else '-'],
        ["Fecha de Vencimiento:", orden.fecha_expiracion.strftime('%d/%m/%Y %H:%M:%S') if orden.fecha_expiracion else '-'],
        ["Estado:", orden.get_estado_display()],
    ]
    tabla_orden = Table(orden_data, colWidths=[150, 300])
    tabla_orden.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), color_primario),
        ('TEXTCOLOR', (1, 0), (1, -1), color_gris),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BACKGROUND', (0, 0), (-1, -1), color_fondo),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#e0e0e0')),
    ]))
    elements.append(tabla_orden)

    # Datos del cliente
    elements.append(Paragraph("Datos del Cliente", seccion_style))
    cliente = orden.cliente
    ci_value = '-'
    if hasattr(cliente, 'nit') and cliente.nit:
        ci_value = cliente.nit
    cliente_data = [
        ["Nombre Completo:", cliente.nombre if cliente else '-'],
        ["Carnet de Identidad (CI):", ci_value],
        ["Teléfono:", cliente.telefono if cliente and cliente.telefono else '-'],
        ["Correo Electrónico:", cliente.email if cliente and cliente.email else '-'],
    ]
    tabla_cliente = Table(cliente_data, colWidths=[150, 300])
    tabla_cliente.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), color_primario),
        ('TEXTCOLOR', (1, 0), (1, -1), color_gris),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BACKGROUND', (0, 0), (-1, -1), color_fondo),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#e0e0e0')),
    ]))
    elements.append(tabla_cliente)

    # Datos de la compra
    elements.append(Paragraph("Datos de la Compra", seccion_style))
    tipo_nombre = orden.tipo_combustible.get_tipo_display() if orden.tipo_combustible else '-'
    compra_data = [
        ["Tipo de Combustible:", tipo_nombre],
        ["Precio por Litro:", f"Bs. {orden.precio_por_litro}"],
        ["Cantidad de Litros:", f"{orden.litros} Lt"],
        ["Monto Total Pagado:", f"Bs. {orden.monto_total}"],
        ["Método de Pago:", "Stripe - Tarjeta"],
    ]
    tabla_compra = Table(compra_data, colWidths=[150, 300])
    tabla_compra.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), color_primario),
        ('TEXTCOLOR', (1, 0), (1, -1), color_gris),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BACKGROUND', (0, 0), (-1, -1), color_fondo),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#e0e0e0')),
    ]))
    elements.append(tabla_compra)

    # Instrucciones para el retiro
    elements.append(Spacer(1, 6 * mm))
    elements.append(HRFlowable(width="100%", thickness=1, color=color_primario))
    elements.append(Spacer(1, 4 * mm))
    elements.append(Paragraph("Instrucciones para el Retiro", seccion_style))

    instrucciones = [
        "• Presente este comprobante (impreso o digital) en cualquier estación SurtidorBolivia.",
        "• Debe presentar su carnet de identidad (CI) físico para verificación.",
        f"• Número de orden para búsqueda manual: <b>{orden.numero_orden}</b>",
    ]
    for instruccion in instrucciones:
        elements.append(Paragraph(instruccion, normal_style))
        elements.append(Spacer(1, 2 * mm))

    elements.append(Spacer(1, 4 * mm))
    fecha_exp = orden.fecha_expiracion.strftime('%d/%m/%Y %H:%M') if orden.fecha_expiracion else 'N/A'
    elements.append(Paragraph(
        f"⚠ ADVERTENCIA: Este comprobante vence el {fecha_exp}. "
        "Pasada esa fecha, la orden ya no será válida para despacho.",
        aviso_style,
    ))

    # Footer
    elements.append(Spacer(1, 10 * mm))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=HexColor('#bdbdbd')))
    footer_style = ParagraphStyle(
        'Footer', parent=styles['Normal'],
        fontSize=8, textColor=HexColor('#9e9e9e'), alignment=TA_CENTER,
    )
    elements.append(Paragraph("SurtidorBolivia - Sistema de Prepago de Combustible", footer_style))
    elements.append(Paragraph("Documento generado electrónicamente - No requiere firma", footer_style))

    # Construir PDF
    doc.build(elements)

    # Guardar en la orden
    pdf_content = buffer.getvalue()
    buffer.close()

    filename = f"comprobante_{orden.numero_orden}.pdf"
    orden.comprobante_pdf.save(filename, ContentFile(pdf_content), save=True)

    return orden.comprobante_pdf.name
