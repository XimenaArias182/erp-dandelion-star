# Sprint 5 Planning — ERP Django
## Semanas W16–W18 · Espiral 6: Celery e Integraciones

**Sprint Goal:**
Al finalizar el Sprint 5, el ERP ejecutará tareas pesadas de forma asíncrona con Celery + Redis: correos de confirmación, alertas de stock bajo y reporte diario de ventas.

## Sprint Backlog — actualización W16

| Tarea | Estado |
|---|---|
| `core/celery.py` + `core/__init__.py` | ✅ W16 |
| `CELERY_*` en `core/settings.py` | ✅ W16 |
| `docker-compose.yml` con `celery_worker` + `flower` | ✅ W16 |
| `ventas/tasks.py` (`enviar_confirmacion_pedido`, `verificar_stock_bajo`) | ✅ W16 |
| `pago_exitoso` y `stripe_webhook` conectados con `.delay()` | ✅ W16 |
| Envío real de correos con SendGrid | ⏳ W17 |
| Tareas programadas con Celery Beat | ⏳ W18 |
