/* ═══════════════════════════════════════════════════════════════════
   AURORA UI v4 — Interactions
   - Scroll reveal (IntersectionObserver)
   - Button ripple
   - Cursor blob (masaustu)
   - Navbar scroll state
   - Count-up animasyonu
   - Page transition on link click
   ═══════════════════════════════════════════════════════════════════ */
(function() {
    'use strict';

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // ─── 1. SCROLL-REVEAL ─────────────────────────────────────────────
    function initScrollReveal() {
        // Otomatik: yaygin kullanilan container'lara .aur-reveal ekle
        const autoTargets = document.querySelectorAll(
            '.chart-card, .feature-card, .stat-card, .menu-card, ' +
            '.section-header, .hero-stat, .action-card, .report-grid > *, ' +
            '.dashboard-grid > *, .card-panel, .analytics-card'
        );
        autoTargets.forEach((el, i) => {
            if (!el.classList.contains('aur-reveal') &&
                !el.classList.contains('aur-reveal-left') &&
                !el.classList.contains('aur-reveal-right') &&
                !el.classList.contains('aur-reveal-scale')) {
                el.classList.add('aur-reveal');
                // Hafif staggering
                el.style.transitionDelay = Math.min(i * 40, 300) + 'ms';
            }
        });

        if (!('IntersectionObserver' in window) || prefersReducedMotion) {
            document.querySelectorAll('.aur-reveal, .aur-reveal-left, .aur-reveal-right, .aur-reveal-scale')
                .forEach(el => el.classList.add('aur-visible'));
            return;
        }

        const obs = new IntersectionObserver((entries) => {
            entries.forEach(e => {
                if (e.isIntersecting) {
                    e.target.classList.add('aur-visible');
                    obs.unobserve(e.target);
                }
            });
        }, { threshold: 0.1, rootMargin: '0px 0px -60px 0px' });

        document.querySelectorAll('.aur-reveal, .aur-reveal-left, .aur-reveal-right, .aur-reveal-scale')
            .forEach(el => obs.observe(el));
    }

    // ─── 2. BUTTON RIPPLE ─────────────────────────────────────────────
    function initRipple() {
        document.addEventListener('click', (e) => {
            const btn = e.target.closest('.btn, button.btn, button[type="submit"], .action-card');
            if (!btn || prefersReducedMotion) return;
            const rect = btn.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            const ripple = document.createElement('span');
            ripple.className = 'aur-ripple';
            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = (e.clientX - rect.left - size / 2) + 'px';
            ripple.style.top = (e.clientY - rect.top - size / 2) + 'px';
            // Button'un position'ini garanti altina al
            const cs = getComputedStyle(btn);
            if (cs.position === 'static') btn.style.position = 'relative';
            btn.appendChild(ripple);
            setTimeout(() => ripple.remove(), 650);
        });
    }

    // ─── 3. NAVBAR SCROLL STATE ──────────────────────────────────────
    function initNavbarScroll() {
        const nav = document.querySelector('.navbar');
        if (!nav) return;
        let ticking = false;
        const update = () => {
            nav.classList.toggle('aur-scrolled', window.scrollY > 24);
            ticking = false;
        };
        window.addEventListener('scroll', () => {
            if (!ticking) {
                requestAnimationFrame(update);
                ticking = true;
            }
        }, { passive: true });
        update();
    }

    // ─── 4. CURSOR BLOB (masaustu, hover pointer) ────────────────────
    function initCursorBlob() {
        if (window.matchMedia('(hover: none), (pointer: coarse)').matches) return;
        if (prefersReducedMotion) return;

        const blob = document.createElement('div');
        blob.className = 'aur-cursor-blob';
        document.body.appendChild(blob);

        let targetX = 0, targetY = 0;
        let currentX = 0, currentY = 0;
        let visible = false;

        window.addEventListener('mousemove', (e) => {
            targetX = e.clientX; targetY = e.clientY;
            if (!visible) {
                visible = true;
                blob.classList.add('aur-visible');
            }
        });
        window.addEventListener('mouseleave', () => {
            visible = false;
            blob.classList.remove('aur-visible');
        });

        // UI ogeleri uzerinde buyut
        document.addEventListener('mouseover', (e) => {
            const t = e.target;
            if (t.closest('.btn, button, a, .card, .chart-card, input, select, textarea')) {
                blob.classList.add('aur-hover-ui');
            } else {
                blob.classList.remove('aur-hover-ui');
            }
        });

        function loop() {
            // Yumusak takip
            currentX += (targetX - currentX) * 0.18;
            currentY += (targetY - currentY) * 0.18;
            blob.style.transform = `translate(${currentX}px, ${currentY}px) translate(-50%, -50%)`;
            requestAnimationFrame(loop);
        }
        loop();
    }

    // ─── 5. COUNT-UP — sayisal degerleri animate et ──────────────────
    function initCountUp() {
        if (prefersReducedMotion) return;
        const targets = document.querySelectorAll('[data-countup]');
        if (!targets.length || !('IntersectionObserver' in window)) return;

        const animate = (el) => {
            const end = parseFloat(el.dataset.countup);
            const duration = parseInt(el.dataset.countupDuration || 1200, 10);
            const suffix = el.dataset.countupSuffix || '';
            const prefix = el.dataset.countupPrefix || '';
            const decimals = parseInt(el.dataset.countupDecimals || 0, 10);
            const start = performance.now();
            function tick(now) {
                const p = Math.min((now - start) / duration, 1);
                const eased = 1 - Math.pow(1 - p, 3); // easeOutCubic
                const val = end * eased;
                el.textContent = prefix + val.toFixed(decimals) + suffix;
                if (p < 1) requestAnimationFrame(tick);
            }
            requestAnimationFrame(tick);
        };

        const obs = new IntersectionObserver((entries) => {
            entries.forEach(e => {
                if (e.isIntersecting) {
                    animate(e.target);
                    obs.unobserve(e.target);
                }
            });
        }, { threshold: 0.3 });
        targets.forEach(el => obs.observe(el));
    }

    // ─── 6. SAYFA GECIS — Link'e tiklaninca hafif fade ───────────────
    function initPageTransition() {
        if (prefersReducedMotion) return;
        document.addEventListener('click', (e) => {
            const a = e.target.closest('a[href]');
            if (!a) return;
            const href = a.getAttribute('href');
            // Sadece ayni origin, yeni pencere olmayan
            if (!href || href.startsWith('#') || href.startsWith('javascript:')
                || a.target === '_blank'
                || a.hasAttribute('download')) return;
            try {
                const url = new URL(href, window.location.href);
                if (url.origin !== window.location.origin) return;
                if (url.pathname === window.location.pathname) return;
            } catch { return; }

            // Sol click mi?
            if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

            e.preventDefault();
            document.body.style.transition = 'opacity .22s ease';
            document.body.style.opacity = '0';
            setTimeout(() => { window.location.href = href; }, 180);
        });
    }

    // ─── BASLAT ──────────────────────────────────────────────────────
    function init() {
        initScrollReveal();
        initRipple();
        initNavbarScroll();
        initCursorBlob();
        initCountUp();
        initPageTransition();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
