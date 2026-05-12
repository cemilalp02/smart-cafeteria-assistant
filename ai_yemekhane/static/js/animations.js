/**
 * Premium UI v3 — Animasyonlar & Micro-interactions
 * Kaldırmak: base.html + base_admin.html'den <script> satırını sil.
 */

(function () {
    'use strict';

    /* ─── 1. SAYAÇ ANİMASYONU — Rakamlar yukarı sayar ──────────── */
    function animateCounters() {
        document.querySelectorAll('.stat-value, .live-stat-value, .val, #vote-toplam-oy').forEach(el => {
            if (el.dataset.pmCounted) return;
            const observer = new IntersectionObserver(entries => {
                entries.forEach(entry => {
                    if (!entry.isIntersecting) return;
                    el.dataset.pmCounted = '1';
                    observer.disconnect();
                    const text = el.textContent.trim();
                    const match = text.match(/^([\d.,]+)/);
                    if (!match) return;
                    const raw = match[1].replace(/\./g, '').replace(',', '.');
                    const target = parseFloat(raw);
                    if (isNaN(target) || target === 0) return;
                    const isFloat = raw.includes('.');
                    const duration = 1200;
                    const start = performance.now();
                    const suffix = text.slice(match[1].length);
                    function tick(now) {
                        const t = Math.min((now - start) / duration, 1);
                        const ease = 1 - Math.pow(1 - t, 3);
                        const current = target * ease;
                        el.textContent = (isFloat ? current.toFixed(1) : Math.round(current).toLocaleString('tr-TR')) + suffix;
                        if (t < 1) requestAnimationFrame(tick);
                    }
                    requestAnimationFrame(tick);
                });
            }, { threshold: 0.3 });
            observer.observe(el);
        });
    }

    /* ─── 2. 3D KART TİLT EFEKTİ ──────────────────────────────── */
    function initCardTilt() {
        const cards = document.querySelectorAll('.chart-card, .panel-card, .hero-focus-card, .stat-card, .admin-stat-card, .feature-card');
        cards.forEach(card => {
            card.addEventListener('mousemove', e => {
                const rect = card.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                const midX = rect.width / 2;
                const midY = rect.height / 2;
                const rotateY = ((x - midX) / midX) * 4;
                const rotateX = ((midY - y) / midY) * 4;
                card.style.transform = `perspective(800px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-4px)`;
            });
            card.addEventListener('mouseleave', () => {
                card.style.transform = '';
                card.style.transition = 'transform .5s cubic-bezier(.22,1,.36,1)';
                setTimeout(() => { card.style.transition = ''; }, 500);
            });
        });
    }

    /* ─── 3. BUTON RİPPLE EFEKTİ ──────────────────────────────── */
    function initRipple() {
        document.addEventListener('click', e => {
            const btn = e.target.closest('.btn, .nav-btn, button');
            if (!btn) return;
            const ripple = document.createElement('span');
            ripple.className = 'pm-ripple';
            const rect = btn.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height) * 2;
            ripple.style.cssText = `
                position:absolute; border-radius:50%;
                background:rgba(255,255,255,.2);
                width:${size}px; height:${size}px;
                left:${e.clientX - rect.left - size / 2}px;
                top:${e.clientY - rect.top - size / 2}px;
                transform:scale(0); opacity:1;
                animation:pm-ripple-anim .6s ease-out forwards;
                pointer-events:none; z-index:10;
            `;
            btn.style.position = btn.style.position || 'relative';
            btn.style.overflow = 'hidden';
            btn.appendChild(ripple);
            setTimeout(() => ripple.remove(), 700);
        });

        if (!document.getElementById('pm-ripple-style')) {
            const style = document.createElement('style');
            style.id = 'pm-ripple-style';
            style.textContent = `
                @keyframes pm-ripple-anim {
                    to { transform: scale(1); opacity: 0; }
                }
            `;
            document.head.appendChild(style);
        }
    }

    /* ─── 4. SCROLL REVEAL (IntersectionObserver) ─────────────── */
    function initScrollReveal() {
        const reveals = document.querySelectorAll('[data-reveal]');
        if (!reveals.length) return;
        const observer = new IntersectionObserver(entries => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-visible');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });
        reveals.forEach(el => observer.observe(el));
    }

    /* ─── 5. STAGGER ANİMASYON (grid çocukları) ──────────────── */
    function initStagger() {
        const grids = document.querySelectorAll('.dashboard-grid, .admin-summary-grid, .grid-4, .feature-grid, .flow-steps');
        grids.forEach(grid => {
            const children = grid.children;
            const observer = new IntersectionObserver(entries => {
                entries.forEach(entry => {
                    if (!entry.isIntersecting) return;
                    Array.from(children).forEach((child, i) => {
                        child.style.opacity = '0';
                        child.style.transform = 'translateY(30px)';
                        child.style.transition = `opacity .5s ease ${i * 0.08}s, transform .5s cubic-bezier(.22,1,.36,1) ${i * 0.08}s`;
                        requestAnimationFrame(() => {
                            child.style.opacity = '1';
                            child.style.transform = 'translateY(0)';
                        });
                    });
                    observer.unobserve(grid);
                });
            }, { threshold: 0.1 });
            observer.observe(grid);
        });
    }

    /* ─── 6. NAVBAR SCROLL ŞEFFAFLİK ─────────────────────────── */
    function initNavScroll() {
        const nav = document.querySelector('.navbar');
        if (!nav) return;
        let ticking = false;
        window.addEventListener('scroll', () => {
            if (ticking) return;
            ticking = true;
            requestAnimationFrame(() => {
                nav.classList.toggle('nav-scrolled', window.scrollY > 40);
                ticking = false;
            });
        }, { passive: true });
    }

    /* ─── 7. SMOOTH CURSOR GLOW — Fare izleyen gradyan ────────── */
    function initCursorGlow() {
        if (window.innerWidth < 900) return;
        const glow = document.createElement('div');
        glow.id = 'pm-cursor-glow';
        glow.style.cssText = `
            position:fixed; width:400px; height:400px;
            border-radius:50%;
            background:radial-gradient(circle, rgba(99,102,241,.06) 0%, transparent 70%);
            pointer-events:none; z-index:0;
            transform:translate(-50%,-50%);
            transition:left .3s ease, top .3s ease;
            will-change:left,top;
        `;
        document.body.appendChild(glow);
        document.addEventListener('mousemove', e => {
            glow.style.left = e.clientX + 'px';
            glow.style.top = e.clientY + 'px';
        }, { passive: true });
    }

    /* ─── 8. SAYFA YÜKLEME ANİMASYONU ─────────────────────────── */
    function initPageLoad() {
        document.body.style.opacity = '0';
        document.body.style.transition = 'opacity .4s ease';
        requestAnimationFrame(() => {
            document.body.style.opacity = '1';
            document.body.classList.add('page-ready');
        });
    }

    /* ─── INIT ────────────────────────────────────────────────── */
    function init() {
        initPageLoad();
        initNavScroll();
        initScrollReveal();
        initStagger();
        initCardTilt();
        initRipple();
        initCursorGlow();
        // Sayaçları bir süre sonra çalıştır (veriler yüklensin)
        setTimeout(animateCounters, 1500);
        setTimeout(animateCounters, 4000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
