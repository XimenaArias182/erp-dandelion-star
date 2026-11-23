# Sprint 4 Planning — ERP Django
## Semanas W13–W15 · Espiral 5: E-commerce y Pagos

**Sprint Goal:**
Al finalizar el Sprint 4, el ERP tendrá catálogo filtrable,
carrito de compras y pago completo con Stripe sandbox,
actualizando automáticamente el estado del pedido.

## Sprint 4 — Estado final W15

| HU | Historia | Pts | Estado |
|---|---|---|---|
| HU-E5-01 | Como cliente, quiero ver el catálogo sin registrarme | 2 | ✅ Completada |
| HU-E5-02 | Como cliente, quiero filtrar productos por categoría y precio | 3 | ✅ Completada |
| HU-E5-03 | Como cliente, quiero agregar productos a mi carrito | 3 | ✅ Completada |
| HU-E5-04 | Como cliente, quiero ver el contenido de mi carrito | 2 | ✅ Completada |
| HU-E5-05 | Como cliente, quiero proceder al pago con mis datos | 3 | ✅ Completada |
| HU-E5-06 | Como cliente, quiero pagar con tarjeta (Stripe sandbox) | 5 | ✅ Completada |
| HU-E5-07 | Como sistema, quiero confirmar el pago vía webhook | 5 | ✅ Completada |
| HU-E5-08 | Como admin, quiero que el stock se descuente al confirmar | 3 | ✅ Completada |

## Hito M5 — ALCANZADO ✅
- Catálogo: `/catalogo/` → 200 sin auth con filtros
- Carrito: agregar/remover/actualizar/vaciar funcional
- Stripe: tarjeta 4242 → pago exitoso → pedido `'pagado'`
- Webhook: `payment_intent.succeeded` → stock decrementado con `F()`
