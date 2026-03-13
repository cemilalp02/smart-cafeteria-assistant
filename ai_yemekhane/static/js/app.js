/**
 * AI Akıllı Yemekhane Asistan Sistemi — Ortak JavaScript
 * ═══════════════════════════════════════════════════════
 */

const API_BASE = '';

// ─── Fetch Wrapper ────────────────────────────────────────────────
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

// ─── Toast Notification ──────────────────────────────────────────
function showToast(message, type = 'info') {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const icons = { success: '✅', error: '❌', info: 'ℹ️' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${icons[type] || ''}</span> ${message}`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

// ─── Format Helpers ──────────────────────────────────────────────
function formatDate(dateStr) {
  const d = new Date(dateStr);
  return d.toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' });
}

function formatNumber(n) {
  return Number(n).toLocaleString('tr-TR', { maximumFractionDigits: 1 });
}

// ─── Hamburger Menu ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const hamburger = document.querySelector('.hamburger');
  const navLinks = document.querySelector('.nav-links');
  if (hamburger && navLinks) {
    hamburger.addEventListener('click', () => {
      navLinks.classList.toggle('open');
    });
    // Close on outside click
    document.addEventListener('click', (e) => {
      if (!hamburger.contains(e.target) && !navLinks.contains(e.target)) {
        navLinks.classList.remove('open');
      }
    });
  }

  // Active nav link
  const path = window.location.pathname;
  document.querySelectorAll('.nav-links a').forEach((a) => {
    if (a.getAttribute('href') === path) {
      a.classList.add('active');
    }
  });
});
