/* App móvil: registra el service worker, agrega la barra inferior de
 * navegación en pantallas chicas y ofrece instalar la app en el teléfono. */
(function () {
  'use strict';
  if ('serviceWorker' in navigator && location.protocol !== 'file:') {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('sw.js').catch(function () {});
    });
  }

  var LINKS = [
    { href: 'index.html', page: 'index', icon: '✦', label: 'Tablero' },
    { href: 'articulos.html', page: 'articulos', icon: '☰', label: 'Artículos' },
    { href: 'biblioteca.html', page: 'biblioteca', icon: '📚', label: 'Biblioteca' },
    { href: 'argentina.html', page: 'argentina', icon: '◉', label: 'Argentina' },
    { href: 'asistente_ia.html', page: 'asistente_ia', icon: '💬', label: 'Asistente' }
  ];
  var current = document.documentElement.getAttribute('data-page') || '';
  var deferredPrompt = null;
  var standalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
  var isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent) && !window.MSStream;

  function dismissed() {
    try { return localStorage.getItem('pwa-install-dismissed') === '1'; } catch (e) { return false; }
  }
  function dismiss() {
    try { localStorage.setItem('pwa-install-dismissed', '1'); } catch (e) {}
    var b = document.getElementById('pwa-install');
    if (b) b.remove();
  }

  function showInstall(message, action) {
    if (standalone || dismissed() || document.getElementById('pwa-install')) return;
    var box = document.createElement('div');
    box.id = 'pwa-install';
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-label', 'Instalar la app');
    box.innerHTML = '<img src="icons/icon-192.png" alt="" width="36" height="36">' +
      '<span class="pwa-install-text"></span>' +
      (action ? '<button type="button" class="pwa-install-go">Instalar</button>' : '') +
      '<button type="button" class="pwa-install-x" aria-label="Cerrar">×</button>';
    box.querySelector('.pwa-install-text').textContent = message;
    box.querySelector('.pwa-install-x').onclick = dismiss;
    if (action) box.querySelector('.pwa-install-go').onclick = action;
    document.body.appendChild(box);
  }

  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    deferredPrompt = e;
    showInstall('Instalá la app en tu teléfono para abrirla como cualquier aplicación.', function () {
      deferredPrompt.prompt();
      deferredPrompt.userChoice.finally(function () { deferredPrompt = null; dismiss(); });
    });
  });
  window.addEventListener('appinstalled', dismiss);

  function buildNav() {
    if (document.getElementById('pwa-nav')) return;
    var nav = document.createElement('nav');
    nav.id = 'pwa-nav';
    nav.setAttribute('aria-label', 'Secciones de la app');
    LINKS.forEach(function (l) {
      var a = document.createElement('a');
      a.href = l.href;
      if (l.page === current) a.setAttribute('aria-current', 'page');
      a.innerHTML = '<span class="pwa-nav-icon" aria-hidden="true"></span><span class="pwa-nav-label"></span>';
      a.querySelector('.pwa-nav-icon').textContent = l.icon;
      a.querySelector('.pwa-nav-label').textContent = l.label;
      nav.appendChild(a);
    });
    document.body.appendChild(nav);
    document.documentElement.classList.add('has-pwa-nav');
  }

  // En la tabla de artículos la ficha queda debajo de la lista: al tocar una
  // tarjeta en el teléfono, se desplaza hasta ella.
  function followDetail() {
    if (current !== 'articulos') return;
    var rows = document.getElementById('rows');
    var aside = document.querySelector('aside');
    if (!rows || !aside) return;
    rows.addEventListener('click', function (e) {
      if (!window.matchMedia('(max-width:760px)').matches) return;
      if (e.target.closest('button, a') || !e.target.closest('tr')) return;
      setTimeout(function () { aside.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, 50);
    });
  }

  function ready() {
    buildNav();
    followDetail();
    if (isIOS && !standalone) {
      setTimeout(function () {
        showInstall('Para instalar: tocá Compartir (□↑) y luego «Agregar a inicio».', null);
      }, 1500);
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready);
  else ready();
})();
