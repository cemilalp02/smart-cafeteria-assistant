/**
 * AI Akıllı Yemekhane Asistan Sistemi — Ortak JavaScript
 */

const API_BASE = '';

async function apiFetch(url, options = {}) {
  try {
    const res = await fetch(`${API_BASE}${url}`, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });
    const data = await res.json();
    return data;
  } catch (err) {
    console.error('API Error:', err);
    showToast('Sunucuya bağlanılamadı.', 'error');
    return { success: false, message: 'Bağlantı hatası' };
  }
}

async function apiUpload(url, formData) {
  try {
    const res = await fetch(`${API_BASE}${url}`, {
      method: 'POST',
      body: formData,
    });
    return await res.json();
  } catch (err) {
    console.error('Upload Error:', err);
    showToast('Dosya yüklenemedi.', 'error');
    return { success: false, message: 'Yükleme hatası' };
  }
}

function showToast(message, type = 'info') {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const icons = { success: '✓', error: '✕', info: 'i' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${icons[type] || ''}</span> ${message}`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

function formatDate(dateStr) {
  const d = new Date(dateStr);
  return d.toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' });
}

function formatNumber(n) {
  return Number(n).toLocaleString('tr-TR', { maximumFractionDigits: 1 });
}

function setupHamburgerMenu() {
  const hamburger = document.querySelector('.hamburger');
  const navLinks = document.querySelector('.nav-links');
  if (!hamburger || !navLinks) return;

  hamburger.addEventListener('click', () => {
    navLinks.classList.toggle('open');
  });

  document.addEventListener('click', (e) => {
    if (!hamburger.contains(e.target) && !navLinks.contains(e.target)) {
      navLinks.classList.remove('open');
    }
  });

  navLinks.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => navLinks.classList.remove('open'));
  });
}

function setupActiveNav() {
  const path = window.location.pathname;
  document.querySelectorAll('.nav-links a').forEach((a) => {
    if (a.getAttribute('href') === path) {
      a.classList.add('active');
    }
  });
}

function setupNavbarScroll() {
  const navbar = document.querySelector('.navbar');
  if (!navbar) return;

  const sync = () => {
    navbar.classList.toggle('nav-scrolled', window.scrollY > 12);
  };

  sync();
  window.addEventListener('scroll', sync, { passive: true });
}

function setupRevealAnimations() {
  const revealTargets = document.querySelectorAll('[data-reveal]');
  document.body.classList.add('page-ready');

  if (!revealTargets.length) return;
  if (!('IntersectionObserver' in window)) {
    revealTargets.forEach((el) => el.classList.add('is-visible'));
    return;
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.18,
    rootMargin: '0px 0px -40px 0px',
  });

  revealTargets.forEach((el, index) => {
    el.style.transitionDelay = `${Math.min(index * 70, 280)}ms`;
    observer.observe(el);
  });
}

// ─── RIPPLE EFFECT on BUTTONS ──────────────────────────────────────
function setupRippleEffect() {
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.btn');
    if (!btn) return;

    const circle = document.createElement('span');
    circle.className = 'ripple-circle';
    const rect = btn.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height) * 2;
    circle.style.width = circle.style.height = `${size}px`;
    circle.style.left = `${e.clientX - rect.left - size / 2}px`;
    circle.style.top = `${e.clientY - rect.top - size / 2}px`;
    btn.appendChild(circle);
    circle.addEventListener('animationend', () => circle.remove());
  });
}


// ─── CARD TILT + GLOW ─────────────────────────────────────────────
function setupCardTilt() {
  const selectors = [
    '.panel-card', '.card', '.rating-card',
    '.admin-stat-card', '.stat-card', '.avg-rating-card',
  ];
  const cards = document.querySelectorAll(selectors.join(','));

  cards.forEach((card) => {
    // inject glow element
    const glow = document.createElement('div');
    glow.className = 'card-glow';
    card.style.position = 'relative';
    card.appendChild(glow);

    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const midX = rect.width / 2;
      const midY = rect.height / 2;
      const rotY = ((x - midX) / midX) * 4;   // max 4deg
      const rotX = ((midY - y) / midY) * 4;

      card.style.transform = `perspective(800px) rotateX(${rotX}deg) rotateY(${rotY}deg) translateY(-4px)`;
      card.classList.add('card-tilt-active');

      // move glow
      glow.style.left = `${x}px`;
      glow.style.top = `${y}px`;
    });

    card.addEventListener('mouseleave', () => {
      card.style.transform = '';
      card.classList.remove('card-tilt-active');
    });
  });
}


// ─── FLOATING PARTICLES ───────────────────────────────────────────
function setupFloatingParticles() {
  const canvas = document.createElement('canvas');
  canvas.id = 'particles-canvas';
  document.body.prepend(canvas);
  const ctx = canvas.getContext('2d');

  let w, h;
  const resize = () => {
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
  };
  resize();
  window.addEventListener('resize', resize);

  const count = Math.min(50, Math.floor(window.innerWidth / 28));
  const particles = Array.from({ length: count }, () => ({
    x: Math.random() * w,
    y: Math.random() * h,
    r: Math.random() * 1.8 + .6,
    vx: (Math.random() - .5) * .3,
    vy: (Math.random() - .5) * .3,
    alpha: Math.random() * .4 + .1,
  }));

  function draw() {
    ctx.clearRect(0, 0, w, h);
    particles.forEach((p) => {
      p.x += p.vx;
      p.y += p.vy;
      if (p.x < 0) p.x = w;
      if (p.x > w) p.x = 0;
      if (p.y < 0) p.y = h;
      if (p.y > h) p.y = 0;

      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(132, 190, 255, ${p.alpha})`;
      ctx.fill();
    });

    // connection lines
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 120) {
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.strokeStyle = `rgba(132, 190, 255, ${.06 * (1 - dist / 120)})`;
          ctx.lineWidth = .5;
          ctx.stroke();
        }
      }
    }

    requestAnimationFrame(draw);
  }
  draw();
}


// ─── HAMBURGER TOGGLE ANIMATION ───────────────────────────────────
function setupHamburgerAnimation() {
  const hamburger = document.querySelector('.hamburger');
  if (!hamburger) return;

  hamburger.addEventListener('click', () => {
    hamburger.classList.toggle('is-active');
  });
}


// ─── COUNTER ANIMATION for STAT VALUES ────────────────────────────
function setupCounterAnimations() {
  const statValues = document.querySelectorAll('.stat-value, .admin-stat-card .stat-value, .calorie-stat .val, .avg-rating-score');
  if (!statValues.length) return;

  const animateCounter = (el) => {
    const text = el.textContent.trim();
    // Extract numeric value
    const match = text.match(/([\d.,]+)/);
    if (!match) return;
    
    const numStr = match[1].replace(/\./g, '').replace(',', '.');
    const target = parseFloat(numStr);
    if (isNaN(target) || target === 0) return;
    
    const prefix = text.substring(0, text.indexOf(match[1]));
    const suffix = text.substring(text.indexOf(match[1]) + match[1].length);
    const isFloat = match[1].includes(',') || (match[1].includes('.') && !match[1].match(/^\d{1,3}(\.\d{3})+$/));
    const decimals = isFloat ? 1 : 0;
    const duration = 1200;
    const startTime = performance.now();

    el.classList.add('counter-animate');

    const step = (currentTime) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = target * eased;

      if (decimals > 0) {
        el.textContent = `${prefix}${current.toLocaleString('tr-TR', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}${suffix}`;
      } else {
        el.textContent = `${prefix}${Math.round(current).toLocaleString('tr-TR')}${suffix}`;
      }

      if (progress < 1) {
        requestAnimationFrame(step);
      }
    };

    requestAnimationFrame(step);
  };

  if (!('IntersectionObserver' in window)) {
    statValues.forEach(animateCounter);
    return;
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        animateCounter(entry.target);
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.3 });

  statValues.forEach((el) => observer.observe(el));
}


// ─── SMOOTH SCROLL ENHANCEMENTS ───────────────────────────────────
function setupSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener('click', function (e) {
      const target = document.querySelector(this.getAttribute('href'));
      if (!target) return;
      e.preventDefault();
      target.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      });
    });
  });
}


document.addEventListener('DOMContentLoaded', () => {
  setupHamburgerMenu();
  setupActiveNav();
  setupNavbarScroll();
  setupRevealAnimations();
  setupRippleEffect();
  setupCardTilt();
  setupFloatingParticles();
  setupHamburgerAnimation();
  setupCounterAnimations();
  setupSmoothScroll();
});
