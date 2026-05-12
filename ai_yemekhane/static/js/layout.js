(function () {
  'use strict';

  function syncPointerRail() {
    const root = document.documentElement;
    let raf = 0;
    window.addEventListener('pointermove', (event) => {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        root.style.setProperty('--forge-x', `${Math.round((event.clientX / window.innerWidth) * 100)}%`);
        root.style.setProperty('--forge-y', `${Math.round((event.clientY / window.innerHeight) * 100)}%`);
        raf = 0;
      });
    }, { passive: true });
  }

  function stampCards() {
    document.querySelectorAll('.panel-card, .feature-card, .chart-card, .summary-card, .stat-card, .admin-stat-card, .card')
      .forEach((card) => {
        if (!card.querySelector(':scope > .forge-corner')) {
          const corner = document.createElement('span');
          corner.className = 'forge-corner';
          corner.setAttribute('aria-hidden', 'true');
          card.appendChild(corner);
        }
      });
  }

  function init() {
    document.body.classList.add('forge-ready');
    syncPointerRail();
    stampCards();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
