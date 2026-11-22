/* Formato de precio con comas, etiqueta 'piezas', variantes y diferencia de stock en cada compra */
(function () {
    // Formatear número poniendo una coma cada 3 dígitos de derecha a izquierda (ej. 23834.00 -> 23,834.00)
    function formatearComasMiles(rawStr, forzarDecimales) {
        if (rawStr === null || rawStr === undefined) return '';
        var clean = String(rawStr).replace(/[^0-9.]/g, '');
        if (!clean) return '';
        var parts = clean.split('.');
        var intPart = parts[0].replace(/^0+(?=\d)/, '');
        if (!intPart) intPart = '0';
        intPart = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
        if (parts.length > 1) {
            var decPart = parts.slice(1).join('').slice(0, 2);
            return intPart + '.' + decPart;
        }
        return forzarDecimales ? (intPart + '.00') : intPart;
    }

    // 1. Habilitar escritura con comas cada 3 dígitos en cualquier campo de precio
    function inicializarInputsDePrecio() {
        var priceInputs = document.querySelectorAll(
            'input[name*="precio"], input[name*="costo"], input[name*="price"], input[id*="precio"], input[id*="costo"]'
        );
        priceInputs.forEach(function (inp) {
            if (inp.getAttribute('data-ds-price-fmt') === '1') return;
            inp.setAttribute('data-ds-price-fmt', '1');
            inp.setAttribute('type', 'text');
            inp.setAttribute('inputmode', 'decimal');
            inp.removeAttribute('step');

            if (inp.value) {
                inp.value = formatearComasMiles(inp.value, false);
            }

            inp.addEventListener('input', function () {
                var posFromEnd = inp.value.length - (inp.selectionStart || 0);
                var formatted = formatearComasMiles(inp.value, false);
                inp.value = formatted;
                var newPos = Math.max(0, formatted.length - posFromEnd);
                try { inp.setSelectionRange(newPos, newPos); } catch (e) {}
            });

            inp.addEventListener('blur', function () {
                if (inp.value.trim()) {
                    inp.value = formatearComasMiles(inp.value, true);
                }
            });

            var form = inp.closest('form');
            if (form && !form.getAttribute('data-ds-price-submit')) {
                form.setAttribute('data-ds-price-submit', '1');
                form.addEventListener('submit', function () {
                    form.querySelectorAll('input[data-ds-price-fmt="1"]').forEach(function (field) {
                        field.value = field.value.replace(/,/g, '').trim();
                    });
                });
            }
        });
    }

    // 2. Formatear textos visibles de precios ($23,834.00) y unidades ("piezas") en toda la pantalla
    function formatearTextosPreciosYPiezas() {
        var walk = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT, null, false);
        var node;
        while ((node = walk.nextNode())) {
            var parent = node.parentElement;
            if (!parent) continue;
            var tag = parent.tagName.toLowerCase();
            if (tag === 'script' || tag === 'style' || tag === 'textarea' || tag === 'input' || tag === 'option') continue;

            var txt = node.nodeValue;
            if (!txt) continue;
            var updated = txt;

            // Poner coma cada 3 dígitos de derecha a izquierda en montos con signo $ (ej. $23834.00 -> $23,834.00)
            updated = updated.replace(/\$\s*(\d{4,})(\.\d{1,2})?/g, function (match, intDigits, decPart) {
                var withCommas = intDigits.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
                return '$' + withCommas + (decPart || '');
            });

            // Reemplazar "uds." o "uds" por "piezas"
            updated = updated.replace(/\buds\.?\b/gi, 'piezas');

            if (updated !== txt) {
                node.nodeValue = updated;
            }
        }
    }

    function extraerProductoId(card) {
        var links = card.querySelectorAll('a[href]');
        for (var i = 0; i < links.length; i++) {
            var href = links[i].getAttribute('href') || '';
            var m = href.match(/\/productos\/(?:editar\/|eliminar\/|detalle\/|vista\/)?(\d+)\/?/);
            if (m) return m[1];
        }
        return card.getAttribute('data-product-id') || null;
    }

    // 3. Catálogo de productos + cálculo de diferencia de stock en cada compra/venta
    function inicializarCatalogoYStock(variantesMap) {
        if (!variantesMap) return;

        // A. Tarjetas del catálogo
        var candidateCards = [];
        document.querySelectorAll('div, article').forEach(function (el) {
            if (el.querySelector('img') && el.querySelector('a[href*="/productos/"]')) {
                var r = el.getBoundingClientRect();
                if (r.width >= 200 && r.width <= 560 && r.height >= 240 && r.height <= 680) {
                    if (!candidateCards.some(function (c) { return c.contains(el) || el.contains(c); })) {
                        candidateCards.push(el);
                    }
                }
            }
        });

        candidateCards.forEach(function (card) {
            if (card.getAttribute('data-ds-var-ready') === '1') return;
            var prodId = extraerProductoId(card);
            if (!prodId || !variantesMap[prodId]) return;

            var info = variantesMap[prodId];
            var imgEl = card.querySelector('img');
            if (!imgEl) return;

            card.setAttribute('data-ds-var-ready', '1');
            card.classList.add('ds-card-interactive');

            var imgs = info.imagenes || [];
            var imgIdx = 0;

            card.addEventListener('click', function (e) {
                if (e.target.closest('button, .ds-card-mini-thumb, .ds-card-img-nav, a[href*="editar"], a[href*="eliminar"], a[href*="delete"], form')) {
                    return;
                }
                window.location.href = info.detalle_url;
            });

            if (imgs.length > 1 && imgEl.parentElement) {
                var imgWrap = imgEl.parentElement;
                if (window.getComputedStyle(imgWrap).position === 'static') {
                    imgWrap.style.position = 'relative';
                }
                var prevBtn = document.createElement('button');
                prevBtn.type = 'button';
                prevBtn.className = 'ds-card-img-nav ds-card-img-prev';
                prevBtn.textContent = '‹';
                prevBtn.addEventListener('click', function (e) {
                    e.stopPropagation();
                    imgIdx = (imgIdx - 1 + imgs.length) % imgs.length;
                    imgEl.src = imgs[imgIdx];
                });

                var nextBtn = document.createElement('button');
                nextBtn.type = 'button';
                nextBtn.className = 'ds-card-img-nav ds-card-img-next';
                nextBtn.textContent = '›';
                nextBtn.addEventListener('click', function (e) {
                    e.stopPropagation();
                    imgIdx = (imgIdx + 1) % imgs.length;
                    imgEl.src = imgs[imgIdx];
                });

                imgWrap.appendChild(prevBtn);
                imgWrap.appendChild(nextBtn);
            }

            var colores = info.colores || [];
            if (colores.length > 1) {
                var strip = document.createElement('div');
                strip.className = 'ds-card-colour-strip';
                colores.forEach(function (col, idx) {
                    if (!col.imagen) return;
                    var thumb = document.createElement('div');
                    thumb.className = 'ds-card-mini-thumb' + (idx === 0 ? ' active' : '');
                    thumb.title = col.nombre;
                    var tImg = document.createElement('img');
                    tImg.src = col.imagen;
                    tImg.alt = col.nombre;
                    thumb.appendChild(tImg);
                    thumb.addEventListener('click', function (e) {
                        e.stopPropagation();
                        strip.querySelectorAll('.ds-card-mini-thumb').forEach(function (t) { t.classList.remove('active'); });
                        thumb.classList.add('active');
                        imgEl.src = col.imagen;
                    });
                    strip.appendChild(thumb);
                });
                var titleTarget = card.querySelector('h3, h4, h5, strong, .product-title, [class*="title"]');
                if (titleTarget && titleTarget.parentElement && titleTarget !== card) {
                    titleTarget.parentElement.insertBefore(strip, titleTarget);
                } else {
                    card.appendChild(strip);
                }
            }
        });

        // B. En formularios de Compra / Venta: mostrar la diferencia de stock en tiempo real
        var prodSelects = document.querySelectorAll('select[name*="producto"], select[id*="producto"], select[name*="product"]');
        prodSelects.forEach(function (sel) {
            var form = sel.closest('form');
            if (!form || form.getAttribute('data-ds-stock-diff-ready') === '1') return;

            var qtyInput = form.querySelector('input[name*="cantidad"], input[id*="cantidad"], input[name*="qty"], input[name*="piezas"]');
            if (!qtyInput) return;

            form.setAttribute('data-ds-stock-diff-ready', '1');

            // Formatear las opciones del select para mostrar stock en piezas y precio con comas
            Array.prototype.slice.call(sel.options).forEach(function (opt) {
                var pid = opt.value;
                if (pid && variantesMap[pid]) {
                    var pInfo = variantesMap[pid];
                    if (opt.text.indexOf('piezas') === -1) {
                        opt.text = pInfo.nombre + ' — $' + pInfo.precio_formateado + ' (' + pInfo.stock + ' piezas disponibles)';
                    }
                }
            });

            var diffBox = document.createElement('div');
            diffBox.className = 'ds-stock-diff-box';
            diffBox.innerHTML = [
                '<div class="ds-stock-diff-item">',
                '  <span class="ds-stock-diff-lbl">Stock actual</span>',
                '  <span class="ds-stock-diff-val" id="dsStockActualVal">—</span>',
                '</div>',
                '<div class="ds-stock-diff-item">',
                '  <span class="ds-stock-diff-lbl">Cantidad de compra</span>',
                '  <span class="ds-stock-diff-badge" id="dsStockMovVal">0 piezas</span>',
                '</div>',
                '<div class="ds-stock-diff-item">',
                '  <span class="ds-stock-diff-lbl">Diferencia de stock (Restante)</span>',
                '  <span class="ds-stock-diff-val" id="dsStockRestanteVal">—</span>',
                '</div>',
                '<div class="ds-stock-diff-item">',
                '  <span class="ds-stock-diff-lbl">Total estimado</span>',
                '  <span class="ds-stock-diff-val" id="dsStockTotalPrecio">$0.00</span>',
                '</div>'
            ].join('');

            var qtyWrapper = qtyInput.parentElement || form;
            if (qtyWrapper.nextSibling) {
                qtyWrapper.parentElement.insertBefore(diffBox, qtyWrapper.nextSibling);
            } else {
                qtyWrapper.parentElement.appendChild(diffBox);
            }

            var pathLower = window.location.pathname.toLowerCase();
            var esEntradaProveedor = /compra_proveedor|entrada|abastec|reabastec/.test(pathLower);

            function actualizarDiferenciaStock() {
                var pid = sel.value;
                var info = pid ? variantesMap[pid] : null;
                var qty = parseInt(qtyInput.value, 10);
                if (isNaN(qty) || qty < 0) qty = 0;

                var actualEl = diffBox.querySelector('#dsStockActualVal');
                var movEl = diffBox.querySelector('#dsStockMovVal');
                var restEl = diffBox.querySelector('#dsStockRestanteVal');
                var totalEl = diffBox.querySelector('#dsStockTotalPrecio');

                if (!info) {
                    actualEl.textContent = 'Selecciona un producto';
                    movEl.textContent = qty + ' piezas';
                    restEl.textContent = '—';
                    restEl.className = 'ds-stock-diff-val';
                    totalEl.textContent = '$0.00';
                    return;
                }

                var stockActual = info.stock;
                var stockFinal = esEntradaProveedor ? (stockActual + qty) : (stockActual - qty);
                var signo = esEntradaProveedor ? '+' : '-';
                var totalMonto = (info.precio * qty).toFixed(2);

                actualEl.textContent = stockActual + ' piezas';
                movEl.textContent = signo + qty + ' piezas';
                restEl.textContent = stockFinal + ' piezas (Dif: ' + signo + qty + ')';
                restEl.className = 'ds-stock-diff-val ' + (stockFinal < 0 ? 'warn' : 'ok');
                totalEl.textContent = '$' + formatearComasMiles(totalMonto, true);
            }

            sel.addEventListener('change', actualizarDiferenciaStock);
            qtyInput.addEventListener('input', actualizarDiferenciaStock);
            qtyInput.addEventListener('change', actualizarDiferenciaStock);
            actualizarDiferenciaStock();
        });

        // C. En tablas/listados de compras o ventas: mostrar diferencia de stock junto al producto/cantidad
        var pathNow = window.location.pathname.toLowerCase();
        if (/venta|compra|pedido|orden/.test(pathNow)) {
            document.querySelectorAll('table tbody tr').forEach(function (tr) {
                if (tr.getAttribute('data-ds-row-diff') === '1') return;
                var rowTxt = tr.textContent || '';
                Object.keys(variantesMap).forEach(function (pid) {
                    var info = variantesMap[pid];
                    if (info.nombre && rowTxt.indexOf(info.nombre) !== -1) {
                        var qtyMatch = rowTxt.match(/\b(\d+)\s*(?:piezas|uds\.?)\b/i);
                        if (qtyMatch) {
                            tr.setAttribute('data-ds-row-diff', '1');
                            var q = parseInt(qtyMatch[1], 10) || 0;
                            var cells = tr.querySelectorAll('td');
                            var targetCell = cells[cells.length - 2] || cells[cells.length - 1];
                            if (targetCell && targetCell.textContent.indexOf('Dif. stock') === -1) {
                                var badge = document.createElement('div');
                                badge.style.fontSize = '11.5px';
                                badge.style.color = '#1B5E43';
                                badge.style.marginTop = '3px';
                                badge.textContent = 'Dif. stock: -' + q + ' piezas (Actual: ' + info.stock + ' piezas)';
                                targetCell.appendChild(badge);
                            }
                        }
                    }
                });
            });
        }
    }

    // 4. Formulario de Agregar / Editar Producto (colores + imágenes adicionales)
    function inicializarFormularioProducto(variantesMap) {
        var path = window.location.pathname.toLowerCase();
        var isProductFormPage = /\/productos\/(nuevo|crear|agregar|editar|\d+\/editar)/.test(path) || /\/admin\/.*producto.*\/(add|\d+\/change)/.test(path);
        if (!isProductFormPage) return;

        var forms = document.querySelectorAll('form');
        var targetForm = null;
        for (var i = 0; i < forms.length; i++) {
            var f = forms[i];
            if (f.querySelector('input[type="file"]') || f.querySelector('input[name*="nombre"], input[name*="precio"]')) {
                targetForm = f;
                break;
            }
        }
        if (!targetForm || targetForm.querySelector('.ds-form-variantes-panel')) return;

        targetForm.setAttribute('enctype', 'multipart/form-data');

        var panel = document.createElement('div');
        panel.className = 'ds-form-variantes-panel';
        panel.innerHTML = [
            '<input type="hidden" name="ds_variantes_form_active" value="1">',
            '<h4 class="ds-form-variantes-title">Colores y diseños del producto</h4>',
            '<div id="dsExistingVariantsContainer"></div>',
            '<div style="margin-bottom: 16px;">',
            '  <label class="ds-form-var-label">Nombre del color de la imagen principal</label>',
            '  <input type="text" name="ds_main_color_name" id="dsMainColorInput" class="ds-form-var-input" placeholder="Ej. Stone / Pearl / Crystal, Marfil, Negro...">',
            '</div>',
            '<div style="margin-bottom: 16px;">',
            '  <label class="ds-form-var-label">Agregar otros colores distintos (con su foto)</label>',
            '  <div id="dsColorRowsContainer"></div>',
            '  <button type="button" class="ds-var-add-btn" id="dsAddColorRowBtn">+ Agregar color</button>',
            '</div>',
            '<div>',
            '  <label class="ds-form-var-label">Agregar más imágenes del diseño (otros ángulos o detalles)</label>',
            '  <input type="file" name="ds_extra_imagenes[]" accept="image/*" multiple class="ds-form-var-input">',
            '</div>'
        ].join('');

        var submitBtn = targetForm.querySelector('button[type="submit"], input[type="submit"]');
        if (submitBtn && submitBtn.parentElement) {
            var container = submitBtn.parentElement;
            if (container === targetForm) {
                targetForm.insertBefore(panel, submitBtn);
            } else {
                targetForm.insertBefore(panel, container);
            }
        } else {
            targetForm.appendChild(panel);
        }

        var rowsContainer = panel.querySelector('#dsColorRowsContainer');
        var rowCounter = 0;

        function agregarFilaColor() {
            var idx = rowCounter++;
            var row = document.createElement('div');
            row.className = 'ds-color-variant-row';
            row.innerHTML = [
                '<input type="hidden" name="ds_color_idx[]" value="' + idx + '">',
                '<input type="text" name="ds_color_nombre[]" class="ds-form-var-input" placeholder="Nombre del color (ej. Negro)">',
                '<input type="file" name="ds_color_imagen_' + idx + '" accept="image/*" class="ds-form-var-input">',
                '<button type="button" class="ds-var-remove-btn" title="Quitar">×</button>'
            ].join('');
            row.querySelector('.ds-var-remove-btn').addEventListener('click', function () {
                row.remove();
            });
            rowsContainer.appendChild(row);
        }

        agregarFilaColor();
        panel.querySelector('#dsAddColorRowBtn').addEventListener('click', agregarFilaColor);

        var editMatch = path.match(/\/productos\/(?:editar\/)?(\d+)/) || path.match(/\/producto\/(\d+)\/change/);
        if (editMatch && variantesMap && variantesMap[editMatch[1]]) {
            var info = variantesMap[editMatch[1]];
            var existingBox = panel.querySelector('#dsExistingVariantsContainer');
            var html = '';

            if (info.colores && info.colores.length) {
                var mainInput = panel.querySelector('#dsMainColorInput');
                if (mainInput && !mainInput.value) {
                    mainInput.value = info.colores[0].nombre || '';
                }
                if (info.colores.length > 1) {
                    html += '<label class="ds-form-var-label">Colores ya guardados (marca para quitar)</label><div class="ds-existing-var-grid">';
                    info.colores.slice(1).forEach(function (c) {
                        html += '<label class="ds-existing-var-chip">';
                        if (c.imagen) html += '<img src="' + c.imagen + '" alt="">';
                        html += '<span>' + c.nombre + '</span>';
                        html += '<input type="checkbox" name="ds_delete_color_ids[]" value="' + c.id + '"> Quitar';
                        html += '</label>';
                    });
                    html += '</div>';
                }
            }

            if (info.extras && info.extras.length) {
                html += '<label class="ds-form-var-label">Imágenes adicionales guardadas (marca para quitar)</label><div class="ds-existing-var-grid">';
                info.extras.forEach(function (ex) {
                    html += '<label class="ds-existing-var-chip">';
                    html += '<img src="' + ex.url + '" alt="">';
                    html += '<input type="checkbox" name="ds_delete_img_ids[]" value="' + ex.id + '"> Quitar';
                    html += '</label>';
                });
                html += '</div>';
            }
            existingBox.innerHTML = html;
        }
    }

    function arrancarTodo() {
        inicializarInputsDePrecio();
        formatearTextosPreciosYPiezas();

        fetch('/api/productos/variantes/')
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (variantesMap) {
                inicializarCatalogoYStock(variantesMap);
                inicializarFormularioProducto(variantesMap);
                formatearTextosPreciosYPiezas();
            })
            .catch(function () {});
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', arrancarTodo);
    } else {
        arrancarTodo();
    }
})();
