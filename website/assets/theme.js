/* System theme until an explicit preference is saved. */
(() => {
  const key = 'quasileak-research-theme';
  const root = document.documentElement;
  const system = matchMedia('(prefers-color-scheme: dark)');
  const valid = value => ['light', 'dark'].includes(value) ? value : null;
  let preference = null;
  try { preference = valid(localStorage.getItem(key)); } catch (_) {}
  const sun = '<circle cx="12" cy="12" r="4"></circle><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"></path>';
  const moon = '<path d="M20.5 13.3A8.5 8.5 0 0 1 10.7 3.5a8.5 8.5 0 1 0 9.8 9.8Z"></path>';
  function apply() {
    const theme = preference || (system.matches ? 'dark' : 'light');
    root.dataset.researchTheme = theme;
    root.style.colorScheme = theme;
    document.querySelectorAll('[data-theme-toggle]').forEach(button => {
      const label = theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme';
      button.setAttribute('aria-label', label); button.title = label;
      button.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${theme === 'dark' ? sun : moon}</svg>`;
    });
  }
  apply();
  document.addEventListener('DOMContentLoaded', () => {
    apply();
    const header = document.querySelector('.research-header');
    const menu = document.querySelector('[data-nav-toggle]');
    if (header && menu) {
      function setMenu(open, restoreFocus = false) {
        header.classList.toggle('nav-open', open);
        menu.setAttribute('aria-expanded', String(open));
        menu.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
        if (restoreFocus) menu.focus();
      }
      menu.addEventListener('click', () => setMenu(menu.getAttribute('aria-expanded') !== 'true'));
      document.addEventListener('click', event => {
        if (!header.contains(event.target) || event.target.closest('.primary-nav a')) setMenu(false);
      });
      document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && menu.getAttribute('aria-expanded') === 'true') setMenu(false, true);
      });
      matchMedia('(min-width: 761px)').addEventListener('change', event => { if (event.matches) setMenu(false); });
    }
    document.querySelectorAll('[data-theme-toggle]').forEach(button => button.addEventListener('click', () => {
      preference = root.dataset.researchTheme === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem(key, preference); } catch (_) {}
      apply();
    }));
  });
  system.addEventListener('change', apply);
  window.addEventListener('storage', event => {
    if (event.key === key || event.key === null) { preference = valid(event.newValue); apply(); }
  });
})();
