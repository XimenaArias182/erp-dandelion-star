# Sprint 4 Retrospective — ERP Django
## Semanas W13–W15 · Espiral 5: E-commerce y Pagos

## ¿Qué funcionó bien? (Keep)
1. `items_snapshot` en el `Pedido` resolvió recuperar los items del carrito después de limpiar la sesión.
2. La expresión `F()` garantizó actualización atómica del stock ante webhooks concurrentes.
3. `unittest.mock.patch` permitió probar Stripe y webhooks sin depender de red.

## ¿Qué mejorar? (Improve)
1. Mostrar feedback visual de carga durante la confirmación de Stripe.js.
2. Automatizar notificaciones post-pago de forma asíncrona (Sprint 5).

## Acción de mejora (Kaizen) para Sprint 5
> En el Sprint 5 (Celery), escribir primero las pruebas unitarias de cada tarea asíncrona con `CELERY_TASK_ALWAYS_EAGER=True` antes de conectar envíos reales.

**Velocidad Sprint 4:** 26/26 puntos
**Velocidad acumulada (S0–S4):** 105 puntos
