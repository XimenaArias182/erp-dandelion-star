"""Tareas asíncronas de la app ventas — W16."""
import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

logger = logging.getLogger(__name__)


def enviar_correo_pedido_inmediato(pedido) -> bool:
    """Construye y envía el correo de confirmación de compra al cliente."""
    destinatario = getattr(pedido.cliente, 'correo', '').strip()
    if not destinatario:
        logger.warning(f'[Correo pedido] Pedido {pedido.numero_pedido} sin correo de cliente.')
        return False

    remitente = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@erp-utec.com')
    asunto = f'Confirmación de tu pedido {pedido.numero_pedido} — ERP UTEC'

    items = pedido.items_snapshot or []
    lineas_txt = []
    filas_html = []

    for item in items:
        nombre = item.get('nombre', 'Producto')
        cantidad = int(item.get('cantidad', 1))
        precio = item.get('precio', '0.00')
        lineas_txt.append(f'- {nombre} x{cantidad} (${precio} c/u)')
        filas_html.append(
            f'<tr>'
            f'<td style="padding:8px;border-bottom:1px solid #eee;">{nombre}</td>'
            f'<td style="padding:8px;border-bottom:1px solid #eee;text-align:center;">{cantidad}</td>'
            f'<td style="padding:8px;border-bottom:1px solid #eee;text-align:right;">${precio}</td>'
            f'</tr>'
        )

    detalle_txt = '\n'.join(lineas_txt) if lineas_txt else '- Artículos del pedido'
    detalle_html = ''.join(filas_html)

    cuerpo_txt = (
        f'Hola {pedido.cliente.nombre},\n\n'
        f'¡Gracias por tu compra! Tu pago ha sido confirmado.\n\n'
        f'Número de pedido: {pedido.numero_pedido}\n'
        f'Estado: {pedido.get_estado_display()}\n'
        f'Total pagado: ${pedido.total_pagado} MXN\n\n'
        f'Detalle de tu compra:\n{detalle_txt}\n\n'
        f'Saludos,\nEquipo ERP UTEC'
    )

    cuerpo_html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;border:1px solid #e5e5e5;border-radius:8px;overflow:hidden;">
        <div style="background:#1c1c1c;color:#fff;padding:20px;text-align:center;">
            <h2 style="margin:0;color:#d4af37;">¡Pago Confirmado!</h2>
            <p style="margin:6px 0 0;font-size:14px;">Pedido {pedido.numero_pedido}</p>
        </div>
        <div style="padding:24px;color:#333;">
            <p>Hola <strong>{pedido.cliente.nombre}</strong>,</p>
            <p>Hemos recibido tu pago correctamente. Aquí tienes el resumen de tu compra:</p>
            <table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:14px;">
                <thead>
                    <tr style="background:#f8f9fa;">
                        <th style="padding:8px;text-align:left;border-bottom:2px solid #8d6e26;">Producto</th>
                        <th style="padding:8px;text-align:center;border-bottom:2px solid #8d6e26;">Cant.</th>
                        <th style="padding:8px;text-align:right;border-bottom:2px solid #8d6e26;">Precio</th>
                    </tr>
                </thead>
                <tbody>
                    {detalle_html}
                </tbody>
            </table>
            <p style="text-align:right;font-size:18px;font-weight:bold;color:#8d6e26;">
                Total pagado: ${pedido.total_pagado} MXN
            </p>
            <p style="font-size:13px;color:#6c757d;margin-top:24px;">
                Este correo es tu comprobante electrónico de compra.
            </p>
        </div>
    </div>
    """

    try:
        msg = EmailMultiAlternatives(
            subject=asunto,
            body=cuerpo_txt,
            from_email=remitente,
            to=[destinatario],
        )
        msg.attach_alternative(cuerpo_html, 'text/html')
        enviados = msg.send(fail_silently=False)
        logger.info(f'[Correo pedido] Enviado ({enviados}) a {destinatario} para {pedido.numero_pedido}.')
        return enviados > 0
    except Exception as exc:
        logger.error(f'[Correo pedido] Error enviando a {destinatario}: {exc}')
        print(f'[MAIL_ERROR] {exc}', flush=True)
        return False


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='ventas.enviar_confirmacion_pedido',
)
def enviar_confirmacion_pedido(self, pedido_id: int) -> dict:
    """Envía el correo de confirmación de pedido al cliente."""
    from ventas.models import Pedido

    try:
        pedido = Pedido.objects.select_related('cliente').get(pk=pedido_id)
    except Pedido.DoesNotExist:
        logger.error(f'[Tarea enviar_confirmacion] Pedido {pedido_id} no existe.')
        return {'estado': 'error', 'pedido_id': pedido_id}

    logger.info(
        f'[Tarea enviar_confirmacion] Procesando pedido '
        f'{pedido.numero_pedido} para {pedido.cliente.correo}. '
        f'Total: ${pedido.total_pagado}. '
        f'Timestamp: {timezone.now().isoformat()}'
    )

    enviar_correo_pedido_inmediato(pedido)

    return {
        'estado': 'ok',
        'pedido_id': pedido_id,
        'numero': pedido.numero_pedido,
        'cliente': pedido.cliente.correo,
    }


@shared_task(
    bind=True,
    max_retries=1,
    name='ventas.verificar_stock_bajo',
)
def verificar_stock_bajo(self, umbral: int = 5) -> dict:
    """Verifica productos con stock por debajo del umbral (placeholder W16)."""
    from productos.models import Producto

    productos_bajos = list(
        Producto.objects
        .filter(activo=True, stock__lt=umbral)
        .values('pk', 'nombre', 'stock')
        .order_by('stock')
    )

    if productos_bajos:
        logger.warning(
            f'[Tarea verificar_stock] {len(productos_bajos)} producto(s) '
            f'con stock < {umbral}: '
            f'{[p["nombre"] for p in productos_bajos]}'
        )
    else:
        logger.info(
            f'[Tarea verificar_stock] Todos los productos tienen '
            f'stock >= {umbral}. OK.'
        )

    return {
        'umbral': umbral,
        'productos_bajos': productos_bajos,
        'total': len(productos_bajos),
    }