(() => {
  const toggle = document.querySelector('.sidebar-toggle');
  const sidebar = document.querySelector('.app-sidebar');
  if (!toggle || !sidebar) return;
  const close = () => {
    sidebar.classList.remove('menu-open');
    toggle.setAttribute('aria-expanded', 'false');
  };
  toggle.addEventListener('click', () => {
    const expanded = sidebar.classList.toggle('menu-open');
    toggle.setAttribute('aria-expanded', String(expanded));
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && sidebar.classList.contains('menu-open')) {
      close();
      toggle.focus();
    }
  });
  sidebar.querySelectorAll('nav a').forEach(link => link.addEventListener('click', close));
})();
