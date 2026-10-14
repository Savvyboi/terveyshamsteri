// Shared page behaviour: language and theme switches, the menu, Ctrl+K search and copy buttons.
(function () {
  var d = document.documentElement;
  var TH = window.TH || { base: '', ui: {} };
  var THEMES = ['light', 'dark', 'contrast'];
  var THEME_KEY = { light: 'themeLight', dark: 'themeDark', contrast: 'themeContrast' };

  function lang() { return d.dataset.lang || 'fi'; }
  function t(key) { var s = TH.ui[key]; return s ? (s[lang()] || s.fi) : key; }
  function save(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  // ---------------------------------------------------------------- language
  // Attributes cannot hold several languages, so swap them in place.
  function applyLang() {
    var l = lang();
    document.querySelectorAll('[data-fi-placeholder]').forEach(function (el) {
      el.setAttribute('placeholder', el.getAttribute('data-' + l + '-placeholder') || el.getAttribute('data-fi-placeholder'));
    });
    document.querySelectorAll('[data-lang-select]').forEach(function (s) { s.value = l; });
    applyTheme();
  }
  document.querySelectorAll('[data-lang-select]').forEach(function (s) {
    s.addEventListener('change', function () {
      d.dataset.lang = s.value; d.lang = s.value; save('lang', s.value);
      document.dispatchEvent(new CustomEvent('langchange', { detail: s.value }));
    });
  });
  document.addEventListener('langchange', applyLang);

  // ------------------------------------------------------------------- theme
  function applyTheme() {
    var cur = d.dataset.theme || 'light';
    document.querySelectorAll('[data-theme-toggle]').forEach(function (b) {
      var next = THEMES[(THEMES.indexOf(cur) + 1) % THEMES.length];
      b.querySelector('.theme-label').textContent = t(THEME_KEY[cur]);
      b.setAttribute('aria-label', t(THEME_KEY[cur]) + ' → ' + t(THEME_KEY[next]));
      b.title = t(THEME_KEY[next]);
    });
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', getComputedStyle(d).getPropertyValue('--paper').trim() || '#f6f3ec');
  }
  document.querySelectorAll('[data-theme-toggle]').forEach(function (b) {
    b.addEventListener('click', function () {
      var cur = d.dataset.theme || 'light';
      var next = THEMES[(THEMES.indexOf(cur) + 1) % THEMES.length];
      d.dataset.theme = next; save('theme', next); applyTheme();
    });
  });

  // -------------------------------------------------------------------- menu
  var menuBtn = document.querySelector('.menu-button');
  var panel = document.getElementById('menu-panel');
  if (menuBtn && panel) {
    menuBtn.addEventListener('click', function () {
      var open = panel.classList.toggle('open');
      menuBtn.setAttribute('aria-expanded', String(open));
    });
  }

  // ------------------------------------------------------------------ search
  var PF = {
    fi: {
      placeholder: 'Hae päätöksistä', clear_search: 'Tyhjennä', load_more: 'Näytä lisää tuloksia',
      search_label: 'Hae sivustolta', filters_label: 'Rajaa', zero_results: 'Ei tuloksia haulle [SEARCH_TERM]',
      many_results: '[COUNT] tulosta haulle [SEARCH_TERM]', one_result: '[COUNT] tulos haulle [SEARCH_TERM]',
      alt_search: 'Ei tuloksia haulle [SEARCH_TERM]. Näytetään tulokset haulle [DIFFERENT_TERM]',
      search_suggestion: 'Ei tuloksia haulle [SEARCH_TERM]. Kokeile jotakin näistä:', searching: 'Haetaan [SEARCH_TERM]...',
    },
    sv: {
      placeholder: 'Sök bland beslut', clear_search: 'Rensa', load_more: 'Visa fler resultat',
      search_label: 'Sök på webbplatsen', filters_label: 'Filter', zero_results: 'Inga resultat för [SEARCH_TERM]',
      many_results: '[COUNT] resultat för [SEARCH_TERM]', one_result: '[COUNT] resultat för [SEARCH_TERM]',
      alt_search: 'Inga resultat för [SEARCH_TERM]. Visar resultat för [DIFFERENT_TERM] i stället',
      search_suggestion: 'Inga resultat för [SEARCH_TERM]. Pröva någon av följande sökningar:', searching: 'Söker efter [SEARCH_TERM]...',
    },
    en: { placeholder: 'Search decisions (in Finnish or Swedish)' },
  };
  var loading = null;
  function loadPagefind() {
    if (loading) return loading;
    loading = new Promise(function (resolve, reject) {
      var css = document.createElement('link');
      css.rel = 'stylesheet'; css.href = TH.base + '/pagefind/pagefind-ui.css';
      document.head.appendChild(css);
      var s = document.createElement('script');
      s.src = TH.base + '/pagefind/pagefind-ui.js';
      s.onload = function () { resolve(window.PagefindUI); };
      s.onerror = reject;
      document.head.appendChild(s);
    });
    return loading;
  }
  function processResult(r) {
    if (r.meta && r.meta.date && r.meta.body) r.meta.title = r.meta.title + ' (' + r.meta.body + ', ' + r.meta.date + ')';
    if (r.meta) { delete r.meta.body; delete r.meta.date; }
    return r;
  }
  /** Mounts Pagefind UI into `selector`; returns the instance. Used by the dialog and /haku/. */
  window.THsearch = function (selector, opts) {
    return loadPagefind().then(function (PagefindUI) {
      var el = document.querySelector(selector);
      el.innerHTML = '';
      return new PagefindUI(Object.assign({
        element: selector, showSubResults: true, showImages: false, resetStyles: false,
        translations: PF[lang()], processResult: processResult,
      }, opts || {}));
    });
  };
  var dialog = document.querySelector('.search-dialog');
  var modal = null, modalLang = null;
  function openSearch() {
    if (!dialog) return;
    if (!dialog.open) dialog.showModal();
    if (!modal || modalLang !== lang()) {
      modalLang = lang();
      modal = window.THsearch('#search-modal', { autofocus: true });
    }
    modal.then(function () {
      var input = dialog.querySelector('input');
      if (input) input.focus();
    });
  }
  document.querySelectorAll('[data-search-open]').forEach(function (b) { b.addEventListener('click', openSearch); });
  document.querySelectorAll('[data-search-close]').forEach(function (b) { b.addEventListener('click', function () { dialog.close(); }); });
  if (dialog) dialog.addEventListener('click', function (e) { if (e.target === dialog) dialog.close(); });
  document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) { e.preventDefault(); openSearch(); }
    else if (e.key === '/' && !/^(INPUT|TEXTAREA|SELECT)$/.test((e.target || {}).tagName || '')) { e.preventDefault(); openSearch(); }
  });

  // ------------------------------------------------------------ copy buttons
  document.querySelectorAll('[data-copy]').forEach(function (b) {
    b.addEventListener('click', function () {
      var el = document.getElementById(b.getAttribute('data-copy'));
      if (!el || !navigator.clipboard) return;
      navigator.clipboard.writeText(el.textContent.trim()).then(function () {
        b.classList.add('done');
        setTimeout(function () { b.classList.remove('done'); }, 1600);
      });
    });
  });

  applyLang();
})();
