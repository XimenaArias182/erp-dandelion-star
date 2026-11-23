# Ficha de Sistematización — Espiral 5
## ERP Django · Espiral E5: E-commerce y Pagos

| Campo | Contenido |
|---|---|
| **Número de espiral** | 5 |
| **Nombre del ciclo** | E-commerce y Pagos |
| **Semanas** | W13 – W15 |
| **Asesor** | MC. Román Fernando López González |

## 1. Objetivo del ciclo
Implementar el canal de e-commerce completo: catálogo público filtrable, carrito de compras en sesión, proceso de pago con Stripe y confirmación automática vía webhook con descuento de stock.

## 2. Tareas realizadas
- App `catalogo` con `django-filter`, `CatalogoView`, vistas del carrito y context processor `carrito_info` (W13).
- Checkout con `stripe`, `checkout_utils.py` y Stripe.js Card Element (W14).
- `items_snapshot` en `Pedido`, endpoint `stripe_webhook` con `construct_event` y descuento atómico de stock con `F()` (W15).
