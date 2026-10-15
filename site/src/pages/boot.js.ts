import { strings } from '../lib/i18n';

// Runs in <head> before the page paints: picks language and theme, and hands site.js its
// UI strings. A shared file instead of inline code keeps it out of every page's HTML.
const base = import.meta.env.BASE_URL.replace(/\/$/, '');
const ui = strings(['search', 'searchPlaceholder', 'themeLight', 'themeDark', 'themeContrast', 'menu', 'close']);

const code = `window.TH = ${JSON.stringify({ base, ui })};
// Language: ?lang= > saved choice > browser language. Theme: saved choice > system setting.
(function () {
  var d = document.documentElement, saved = {};
  try { saved = { lang: localStorage.getItem('lang'), theme: localStorage.getItem('theme') }; } catch (e) {}
  var nav = (navigator.language || '').slice(0, 2);
  var lang = new URLSearchParams(location.search).get('lang') || saved.lang || (nav === 'sv' || nav === 'en' ? nav : 'fi');
  if (['fi', 'sv', 'en'].indexOf(lang) < 0) lang = 'fi';
  d.dataset.lang = lang; d.lang = lang;
  var theme = saved.theme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark'
    : matchMedia('(prefers-contrast: more)').matches ? 'contrast' : 'light');
  d.dataset.theme = theme;
})();
`;

export function GET() {
  return new Response(code, { headers: { 'Content-Type': 'text/javascript' } });
}
