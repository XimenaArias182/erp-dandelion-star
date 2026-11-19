/* Clonación exacta del diseño oro puro del título junto al logo hacia el título central y todos los temas */
(function () {
    document.title = 'Dandelion Star';

    function obtenerEstiloOroDelLogo() {
        var logoBrand = document.querySelector('.navbar-brand, .brand-link, .brand-title, header a');
        if (logoBrand) {
            var cs = window.getComputedStyle(logoBrand);
            var col = cs.color;
            if (col && col !== 'rgba(0, 0, 0, 0)' && col !== 'rgb(0, 0, 0)') {
                return {
                    color: col,
                    shadow: (cs.textShadow && cs.textShadow !== 'none')
                        ? cs.textShadow
                        : '0 1px 0 rgba(255, 248, 214, 0.38), 0 2px 5px rgba(5, 14, 28, 0.52)'
                };
            }
        }
        return {
            color: '#F6D879',
            shadow: '0 1px 0 rgba(255, 248, 214, 0.38), 0 2px 5px rgba(5, 14, 28, 0.52)'
        };
    }

    function estaEnTarjetaBlanca(el) {
        if (el.closest('header, nav, .navbar, .main-header, .hero, .banner, .jumbotron, footer')) {
            return false;
        }
        var cur = el;
        while (cur && cur !== document.body && cur !== document.documentElement) {
            var bg = window.getComputedStyle(cur).backgroundColor;
            if (bg && bg !== 'transparent' && bg !== 'rgba(0, 0, 0, 0)') {
                var m = bg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/i);
                if (m) {
                    var alpha = m[4] !== undefined ? parseFloat(m[4]) : 1;
                    if (alpha > 0.45) {
                        var r = parseInt(m[1], 10);
                        var g = parseInt(m[2], 10);
                        var b = parseInt(m[3], 10);
                        var lum = (0.299 * r + 0.587 * g + 0.114 * b);
                        return lum >= 185;
                    }
                }
            }
            cur = cur.parentElement;
        }
        return false;
    }

    function normalizarMayusculasCaligrafia(el) {
        var walk = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null, false);
        var n;
        while ((n = walk.nextNode())) {
            var v = n.nodeValue;
            if (!v || !v.trim()) continue;
            var letters = v.replace(/[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ]/g, '');
            if (letters.length >= 3 && letters === letters.toUpperCase()) {
                n.nodeValue = v.toLowerCase().replace(/(^|\s|\-|\/)([a-záéíóúüñ])/g, function (all, sep, ch) {
                    return sep + ch.toUpperCase();
                });
            }
        }
    }

    function aplicarOroExacto(el, logoStyle) {
        normalizarMayusculasCaligrafia(el);
        var nodes = [el].concat(Array.prototype.slice.call(el.querySelectorAll('*')));
        var enBlanco = estaEnTarjetaBlanca(el);

        nodes.forEach(function (node) {
            node.classList.add('ds-calligraphy-title');
            node.style.setProperty('font-family', "'Great Vibes', 'Pinyon Script', 'Edwardian Script ITC', cursive", 'important');
            node.style.setProperty('font-weight', '400', 'important');
            node.style.setProperty('text-transform', 'none', 'important');
            node.style.setProperty('opacity', '1', 'important');
            node.style.setProperty('filter', 'none', 'important');
            node.style.setProperty('background', 'none', 'important');
            node.style.setProperty('-webkit-background-clip', 'border-box', 'important');
            node.style.setProperty('background-clip', 'border-box', 'important');
            node.style.setProperty('-webkit-font-smoothing', 'antialiased', 'important');
            node.style.setProperty('text-rendering', 'geometricPrecision', 'important');

            if (enBlanco) {
                node.classList.add('ds-gold-editorial-text');
                node.classList.remove('ds-gold-metallic-text');
                node.style.setProperty('color', '#9A7014', 'important');
                node.style.setProperty('-webkit-text-fill-color', '#9A7014', 'important');
            } else {
                node.classList.add('ds-gold-metallic-text');
                node.classList.remove('ds-gold-editorial-text');
                node.style.setProperty('color', logoStyle.color, 'important');
                node.style.setProperty('-webkit-text-fill-color', logoStyle.color, 'important');
                node.style.setProperty('text-shadow', logoStyle.shadow, 'important');
            }
        });
    }

    function sincronizarDisenoFuente() {
        if (document.title !== 'Dandelion Star') {
            document.title = 'Dandelion Star';
        }

        var logoStyle = obtenerEstiloOroDelLogo();

        var selectors = [
            'h1', 'h2', 'h3', 'h4', '.h1', '.h2', '.h3',
            '.navbar-brand', '.brand-link', '.brand-text', '.brand-title',
            '.hero-title', '.page-title', '.section-title', '.module-title',
            '.card-title', '.content-header h1', '.login-logo a', '.login-box-msg',
            '.ds-plist-title', '.ds-clist-title', '.ds-form-title',
            '.footer-brand', '.ds-calligraphy-title'
        ];

        document.querySelectorAll(selectors.join(',')).forEach(function (el) {
            if (el.closest('svg') || el.closest('table')) return;
            var txt = (el.textContent || '').trim();
            if (!txt || txt.length > 90) return;
            aplicarOroExacto(el, logoStyle);
        });

        var walk = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT, null, false);
        var node;
        while ((node = walk.nextNode())) {
            if (!node.nodeValue || !/dandelion\s*star/i.test(node.nodeValue)) continue;
            var el = node.parentElement;
            if (!el || el.closest('svg')) continue;
            var tag = el.tagName.toLowerCase();
            if (tag === 'script' || tag === 'style' || tag === 'title' || tag === 'input' || tag === 'textarea') continue;
            var full = (el.textContent || '').trim();
            if (full.length > 65 || /sistema\s+de\s+gesti/i.test(full)) continue;
            aplicarOroExacto(el, logoStyle);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', sincronizarDisenoFuente);
    } else {
        sincronizarDisenoFuente();
    }
    if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(sincronizarDisenoFuente);
    }
    window.addEventListener('load', sincronizarDisenoFuente);
    setTimeout(sincronizarDisenoFuente, 250);

    var observer = new MutationObserver(function () {
        sincronizarDisenoFuente();
    });
    if (document.documentElement) {
        observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'data-theme', 'data-bs-theme'] });
    }
})();
