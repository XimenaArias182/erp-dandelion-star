"""Endpoint de webhook para recibir eventos de Stripe — W15 + W16."""
from decimal import Decimal
import logging

import stripe
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from productos.models import Producto
from ventas.models import DetalleVenta, Pedido, Venta
from ventas.tasks import enviar_confirmacion_pedido, enviar_correo_pedido_inmediato

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def stripe_webhook(request) -> HttpResponse:
    """Recibe y procesa eventos de Stripe verificando su firma."""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=getattr(settings, 'STRIPE_WEBHOOK_SECRET', 'whsec_placeholder'),
        )
    except ValueError:
        logger.warning('Webhook: payload inválido recibido.')
        return HttpResponse('Payload inválido.', status=400)
    except stripe.error.SignatureVerificationError:
        logger.warning('Webhook: firma inválida — posible ataque.')
        return HttpResponse('Firma inválida.', status=400)

    tipo = event['type']
    logger.info(f'Webhook recibido: {tipo}')

    if tipo == 'payment_intent.succeeded':
        _manejar_pago_exitoso(event['data']['object'])
    elif tipo == 'payment_intent.payment_failed':
        _manejar_pago_fallido(event['data']['object'])
    else:
        logger.debug(f'Evento ignorado: {tipo}')

    return HttpResponse(status=200)


def _manejar_pago_exitoso(payment_intent: dict) -> None:
    """Actualiza el Pedido a pagado, descuenta stock, registra Venta y encola confirmación."""
    pedido_id = _extraer_pedido_id(payment_intent)
    if pedido_id is None:
        return

    try:
        pedido = Pedido.objects.get(pk=pedido_id)
    except Pedido.DoesNotExist:
        logger.error(f'Webhook: Pedido {pedido_id} no encontrado en BD.')
        return

    if pedido.estado != 'pagado':
        with transaction.atomic():
            pedido.estado = 'pagado'
            pedido.save(update_fields=['estado'])
            logger.info(f'Pedido {pedido.numero_pedido} actualizado a "pagado".')
            _descontar_stock(pedido)
            _registrar_venta(pedido)

        enviar_correo_pedido_inmediato(pedido)
        try:
            enviar_confirmacion_pedido.delay(pedido.pk)
        except Exception as _celery_err:
            print('CELERY_BROKER_WARN:', _celery_err, flush=True)
    else:
        logger.info(
            f'Pedido {pedido.numero_pedido} ya estaba pagado — idempotente, sin cambios.'
        )


def _manejar_pago_fallido(payment_intent: dict) -> None:
    """Actualiza el Pedido a cancelado si el pago falló."""
    pedido_id = _extraer_pedido_id(payment_intent)
    if pedido_id is None:
        return

    try:
        pedido = Pedido.objects.get(pk=pedido_id)
    except Pedido.DoesNotExist:
        logger.error(f'Webhook: Pedido {pedido_id} no encontrado.')
        return

    if pedido.estado == 'pendiente':
        pedido.estado = 'cancelado'
        pedido.save(update_fields=['estado'])
        logger.info(f'Pedido {pedido.numero_pedido} cancelado por pago fallido.')


def _extraer_pedido_id(payment_intent: dict) -> int | None:
    """Extrae el pedido_id del metadata del PaymentIntent."""
    metadata = payment_intent.get('metadata', {})
    pedido_id = metadata.get('pedido_id')

    if not pedido_id:
        logger.warning(
            f'Webhook: PaymentIntent sin pedido_id en metadata. '
            f'ID: {payment_intent.get("id")}'
        )
        return None

    try:
        return int(pedido_id)
    except (ValueError, TypeError):
        logger.error(f'Webhook: pedido_id inválido: {pedido_id!r}')
        return None


def _descontar_stock(pedido: 'Pedido') -> None:
    """Descuenta el stock de los productos del pedido atómicamente con F()."""
    items = pedido.items_snapshot or []

    for item in items:
        producto_id = item.get('producto_id')
        cantidad = int(item.get('cantidad', 0))

        if not producto_id or cantidad <= 0:
            continue

        filas_actualizadas = Producto.objects.filter(
            pk=producto_id,
            stock__gte=cantidad
        ).update(
            stock=F('stock') - cantidad
        )

        if filas_actualizadas:
            logger.info(f'Stock decrementado: Producto {producto_id} - {cantidad} unidades.')
        else:
            logger.warning(f'Producto {producto_id}: stock insuficiente para decrementar {cantidad}.')


def _registrar_venta(pedido: 'Pedido') -> None:
    """Crea el registro en Venta y DetalleVenta a partir del Pedido pagado."""
    items = pedido.items_snapshot or []
    if not items:
        return

    venta = Venta.objects.create(cliente=pedido.cliente)
    for item in items:
        producto_id = item.get('producto_id')
        cantidad = int(item.get('cantidad', 0))
        if not producto_id or cantidad <= 0:
            continue

        producto = Producto.objects.filter(pk=producto_id).first()
        if not producto:
            continue

        precio_raw = item.get('precio')
        precio_unit = Decimal(str(precio_raw)) if precio_raw is not None else producto.precio

        DetalleVenta.objects.create(
            venta=venta,
            producto=producto,
            cantidad=cantidad,
            precio_unitario=precio_unit,
        )
    logger.info(f'Venta #{venta.pk} registrada desde Pedido {pedido.numero_pedido}.')