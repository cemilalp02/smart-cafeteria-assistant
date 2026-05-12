/* ════════════════════════════════════════════════════════════
   ELEGANCE LAYER v2 — Bold interactions
   ════════════════════════════════════════════════════════════ */

(() => {
    'use strict';

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    // ─── 1) Scroll Progress Bar ──────────────────────────────
    function initScrollProgress() {
        const bar = document.createElement('div');
        bar.className = 'el-scroll-progress';
        document.body.appendChild(bar);

        let ticking = false;
        const update = () => {
            const h = document.documentElement;
            const max = h.scrollHeight - h.clientHeight;
            bar.style.width = max > 0 ? (h.scrollTop / max * 100) + '%' : '0%';
            ticking = false;
        };
        window.addEventListener('scroll', () => {
            if (!ticking) {
                requestAnimationFrame(update);
                ticking = true;
            }
        }, { passive: true });
    }

    // ─── 2) Click Ripple ─────────────────────────────────────
    function initRipples() {
        const sel = 'button, .btn, .nav-btn, input[type="submit"], input[type="button"]';

        document.addEventListener('click', (e) => {
            const t = e.target.closest(sel);
            if (!t || t.disabled) return;

            const rect = t.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height) * 1.6;
            const x = e.clientX - rect.left - size / 2;
            const y = e.clientY - rect.top - size / 2;

            const ripple = document.createElement('span');
            ripple.className = 'el-ripple';
            ripple.style.cssText = `width:${size}px;height:${size}px;left:${x}px;top:${y}px;`;

            const computed = getComputedStyle(t);
            if (computed.position === 'static') t.style.position = 'relative';
            if (computed.overflow !== 'hidden') t.style.overflow = 'hidden';

            t.appendChild(ripple);
            setTimeout(() => ripple.remove(), 900);
        });
    }

    // ─── 3) Scroll Reveal ────────────────────────────────────
    function initReveal() {
        const targets = [
            '.prod-form-card', '.stat-card', '.feature-card', '.metric-card',
            '.summary-card', '.dash-card', '.grid-tile', '.card', 'section'
        ];

        document.querySelectorAll(targets.join(',')).forEach(el => {
            if (el.classList.contains('el-reveal')) return;
            if (el.closest('nav, footer, .navbar')) return;
            el.classList.add('el-reveal');
        });

        const obs = new IntersectionObserver((entries) => {
            entries.forEach(en => {
                if (en.isIntersecting) {
                    en.target.classList.add('is-visible');
                    obs.unobserve(en.target);
                }
            });
        }, { threshold: 0.1, rootMargin: '0px 0px -60px 0px' });

        document.querySelectorAll('.el-reveal').forEach(el => obs.observe(el));
    }

    // ─── 4) Steam Hosts (Food Cards) ─────────────────────────
    function initSteamHosts() {
        const keywords = ['yemek', 'menu', 'menü', 'çorba', 'corba', 'tatli', 'tatlı', 'salata'];
        document.querySelectorAll('.prod-form-card, .feature-card, .stat-card').forEach(card => {
            const txt = (card.textContent || '').toLowerCase();
            if (keywords.some(k => txt.includes(k))) {
                card.classList.add('el-steam-host');
            }
        });
    }

    // ─── 5) Smooth Page Transition ───────────────────────────
    function initPageTransition() {
        document.addEventListener('click', (e) => {
            const link = e.target.closest('a[href]');
            if (!link) return;

            const href = link.getAttribute('href');
            if (!href || href.startsWith('#') || href.startsWith('javascript:')) return;
            if (link.target === '_blank' || link.hasAttribute('download')) return;
            if (e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;

            try {
                const url = new URL(href, window.location.href);
                if (url.origin !== window.location.origin) return;
                if (url.pathname === window.location.pathname && url.search === window.location.search) return;
            } catch (_) {
                return;
            }

            document.body.classList.add('el-leaving');
        });

        // Geri tuşu için temizle
        window.addEventListener('pageshow', (e) => {
            if (e.persisted) document.body.classList.remove('el-leaving');
        });
    }

    // ─── 6) Smooth Anchors ───────────────────────────────────
    function initAnchors() {
        document.addEventListener('click', (e) => {
            const a = e.target.closest('a[href^="#"]');
            if (!a) return;
            const href = a.getAttribute('href');
            if (href === '#' || href.length < 2) return;
            const tgt = document.querySelector(href);
            if (!tgt) return;
            e.preventDefault();
            tgt.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    }

    // ─── INIT ────────────────────────────────────────────────
    function init() {
        initScrollProgress();
        initRipples();
        initReveal();
        initSteamHosts();
        initPageTransition();
        initAnchors();
        console.log('%c[Elegance] v2 yüklendi 🍲', 'color:#F5B83D;font-weight:bold;font-size:13px;');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
