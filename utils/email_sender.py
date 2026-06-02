"""
Envío de comprobante PDF por correo electrónico al cliente.
Utiliza Django EmailMessage para adjuntar el PDF y enviar instrucciones HTML.
"""
import logging
from django.core.mail import EmailMultiAlternatives
from django.conf import settings

logger = logging.getLogger(__name__)


def enviar_email_comprobante(orden):
    """
    Envía el comprobante de prepago por email al cliente.

    Args:
        orden: instancia de OrdenPrepago con estado PAGADO y comprobante_pdf generado.

    Returns:
        bool: True si el email se envió correctamente, False en caso de error.
    """
    cliente = orden.cliente
    email_destino = None

    # Intentar obtener email del usuario vinculado, sino del cliente directo
    if cliente.usuario and cliente.usuario.email:
        email_destino = cliente.usuario.email
    elif cliente.email:
        email_destino = cliente.email

    if not email_destino:
        logger.warning(f"No se encontró email para el cliente {cliente.nombre} (orden {orden.numero_orden})")
        return False

    asunto = f"Comprobante de prepago - SurtidorBolivia ({orden.numero_orden})"

    tipo_nombre = orden.tipo_combustible.get_tipo_display() if orden.tipo_combustible else 'N/A'
    fecha_exp = orden.fecha_expiracion.strftime('%d/%m/%Y %H:%M') if orden.fecha_expiracion else 'N/A'

    # Cuerpo en texto plano
    texto_plano = f"""
Estimado/a {cliente.nombre},

Su pago ha sido procesado exitosamente. A continuación, los detalles de su compra:

Número de Orden: {orden.numero_orden}
Tipo de Combustible: {tipo_nombre}
Cantidad: {orden.litros} litros
Monto Pagado: Bs. {orden.monto_total}
Válido hasta: {fecha_exp}

INSTRUCCIONES PARA EL RETIRO:
- Presente este comprobante (impreso o digital) en cualquier estación SurtidorBolivia.
- Debe presentar su carnet de identidad (CI) físico para verificación.
- Este comprobante vence el {fecha_exp}. Pasada esa fecha, la orden ya no será válida.

Atentamente,
SurtidorBolivia
"""

    # Cuerpo en HTML
    html_body = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #f5f5f5; padding: 20px;">
        <div style="background: linear-gradient(135deg, #1a237e, #283593); color: white; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
            <h1 style="margin: 0; font-size: 24px;">⛽ SurtidorBolivia</h1>
            <p style="margin: 5px 0 0; opacity: 0.9;">Comprobante de Prepago</p>
        </div>
        <div style="background: white; padding: 24px; border-radius: 0 0 8px 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
            <p>Estimado/a <strong>{cliente.nombre}</strong>,</p>
            <p>Su pago ha sido procesado exitosamente. Adjuntamos su comprobante en PDF.</p>

            <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                <tr style="background: #e8eaf6;">
                    <td style="padding: 8px 12px; font-weight: bold; color: #1a237e;">Número de Orden</td>
                    <td style="padding: 8px 12px;">{orden.numero_orden}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 12px; font-weight: bold; color: #1a237e;">Combustible</td>
                    <td style="padding: 8px 12px;">{tipo_nombre}</td>
                </tr>
                <tr style="background: #e8eaf6;">
                    <td style="padding: 8px 12px; font-weight: bold; color: #1a237e;">Cantidad</td>
                    <td style="padding: 8px 12px;">{orden.litros} litros</td>
                </tr>
                <tr>
                    <td style="padding: 8px 12px; font-weight: bold; color: #1a237e;">Monto Pagado</td>
                    <td style="padding: 8px 12px;">Bs. {orden.monto_total}</td>
                </tr>
                <tr style="background: #e8eaf6;">
                    <td style="padding: 8px 12px; font-weight: bold; color: #1a237e;">Válido hasta</td>
                    <td style="padding: 8px 12px; color: #d32f2f; font-weight: bold;">{fecha_exp}</td>
                </tr>
            </table>

            <div style="background: #fff3e0; border-left: 4px solid #ff9800; padding: 12px; margin: 16px 0; border-radius: 4px;">
                <strong>📋 Instrucciones para el retiro:</strong>
                <ul style="margin: 8px 0; padding-left: 20px;">
                    <li>Presente este comprobante (impreso o digital) en cualquier estación SurtidorBolivia.</li>
                    <li>Debe presentar su carnet de identidad (CI) físico para verificación.</li>
                </ul>
            </div>

            <div style="background: #ffebee; border-left: 4px solid #d32f2f; padding: 12px; margin: 16px 0; border-radius: 4px;">
                <strong>⚠ Advertencia:</strong> Este comprobante vence el <strong>{fecha_exp}</strong>.
                Pasada esa fecha, la orden ya no será válida para despacho.
            </div>
        </div>
        <p style="text-align: center; color: #9e9e9e; font-size: 12px; margin-top: 16px;">
            SurtidorBolivia - Sistema de Prepago de Combustible
        </p>
    </div>
    """

    try:
        email = EmailMultiAlternatives(
            subject=asunto,
            body=texto_plano,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email_destino],
        )
        email.attach_alternative(html_body, "text/html")

        # Adjuntar el PDF si existe
        if orden.comprobante_pdf:
            try:
                orden.comprobante_pdf.open('rb')
                pdf_content = orden.comprobante_pdf.read()
                orden.comprobante_pdf.close()
                email.attach(
                    f"comprobante_{orden.numero_orden}.pdf",
                    pdf_content,
                    "application/pdf",
                )
            except Exception as e:
                logger.error(f"Error al adjuntar PDF para orden {orden.numero_orden}: {e}")

        email.send(fail_silently=False)
        logger.info(f"Email enviado exitosamente a {email_destino} para orden {orden.numero_orden}")
        return True

    except Exception as e:
        logger.error(f"Error al enviar email para orden {orden.numero_orden}: {e}")
        return False
