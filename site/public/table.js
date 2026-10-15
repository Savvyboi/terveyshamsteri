// Fills a DataTable component from its JSON file. Filters live in the URL so a filtered
// view can be shared; exports download exactly the rows that pass the filters.
(function () {
  var PAGE = 50;

  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    for (var k in attrs || {}) {
      if (k === 'text') e.textContent = attrs[k];
      else if (k === 'html') e.innerHTML = attrs[k];
      else e.setAttribute(k, attrs[k]);
    }
    (kids || []).forEach(function (c) { if (c) e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return e;
  }
  function fmtDate(iso) { var p = iso.split('-'); return +p[2] + '.' + +p[1] + '.' + p[0]; }
  function lang() { return document.documentElement.dataset.lang || 'fi'; }

  function setup(root) {
    var cfg = JSON.parse(root.querySelector('.dt-config').textContent);
    var kind = root.dataset.kind;
    var rows = [], filtered = [], shown = PAGE;
    var tbody = root.querySelector('tbody'), thead = root.querySelector('thead');
    var count = root.querySelector('.count'), more = root.querySelector('.more');
    var form = {
      q: root.querySelector('[name=q]'), from: root.querySelector('[name=from]'), to: root.querySelector('[name=to]'),
    };
    function t(k) { var s = cfg.ui[k]; return s ? (s[lang()] || s.fi) : k; }
    function regionName(id) { var r = cfg.regions[id] || {}; return r[lang()] || r.fi || id; }
    function checked(name) {
      return Array.prototype.filter.call(root.querySelectorAll('[name=' + name + ']'), function (c) { return c.checked; })
        .map(function (c) { return c.value; });
    }
    function sortKey() { var s = checked('sort'); return s[0] || 'newest'; }

    // ------------------------------------------------------------ URL state
    function readUrl() {
      var p = new URLSearchParams(location.search);
      if (p.get('q')) form.q.value = p.get('q');
      if (p.get('from')) form.from.value = p.get('from');
      if (p.get('to')) form.to.value = p.get('to');
      ['region', 'type', 'stage'].forEach(function (name) {
        if (!p.has(name)) return;
        var want = p.get(name).split(',');
        root.querySelectorAll('[name=' + name + ']').forEach(function (c) { c.checked = want.indexOf(c.value) >= 0; });
      });
      if (p.get('sort')) root.querySelectorAll('[name=sort]').forEach(function (c) { c.checked = c.value === p.get('sort'); });
    }
    function writeUrl() {
      var p = new URLSearchParams(location.search);
      ['q', 'from', 'to'].forEach(function (k) { if (form[k].value) p.set(k, form[k].value); else p.delete(k); });
      ['region', 'type', 'stage'].forEach(function (name) {
        var all = root.querySelectorAll('[name=' + name + ']');
        var on = checked(name);
        if (!all.length || on.length === all.length) p.delete(name); else p.set(name, on.join(','));
      });
      if (sortKey() !== root.querySelector('[name=sort]').value) p.set('sort', sortKey()); else p.delete('sort');
      var qs = p.toString();
      history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash);
    }

    // ------------------------------------------------------------- filtering
    function apply() {
      var q = form.q.value.trim().toLowerCase();
      var regions = checked('region'), types = checked('type');
      var stages = root.querySelector('[name=stage]') ? checked('stage') : null;
      var from = form.from.value, to = form.to.value;
      filtered = rows.filter(function (r) {
        if (regions.indexOf(r.region) < 0 || types.indexOf(r.bodyType) < 0) return false;
        if (stages && stages.indexOf(r.stage) < 0) return false;
        if (from && r.date < from) return false;
        if (to && r.date > to) return false;
        if (q && (r.title || '').toLowerCase().indexOf(q) < 0 && r.body.toLowerCase().indexOf(q) < 0) return false;
        return true;
      });
      var s = sortKey();
      var margin = function (r) { return r.jaa == null || r.ei == null ? 1e9 : Math.abs(r.jaa - r.ei); };
      filtered.sort(function (a, b) {
        if (s === 'oldest') return a.date.localeCompare(b.date);
        if (s === 'mostItems') return b.items - a.items || b.date.localeCompare(a.date);
        if (s === 'closest') return margin(a) - margin(b) || b.date.localeCompare(a.date);
        return b.date.localeCompare(a.date);
      });
      shown = PAGE;
      writeUrl();
      render();
    }

    // ------------------------------------------------------------- rendering
    var HEAD = {
      meetings: [['date'], ['meeting'], ['region'], ['items', 'num']],
      votes: [['date'], ['intro'], ['result']],
    };
    function header() {
      thead.innerHTML = '';
      thead.appendChild(el('tr', {}, HEAD[kind].map(function (h) { return el('th', { class: h[1] || '', text: t(h[0]) }); })));
    }
    function voteBar(r) {
      var parts = ['jaa', 'ei', 'tyhja', 'poissa'].filter(function (k) { return r[k] != null; });
      var track = el('div', { class: 'votebar-track', role: 'img',
        'aria-label': parts.map(function (k) { return t(k) + ' ' + r[k]; }).join(', ') },
        parts.filter(function (k) { return r[k] > 0; }).map(function (k) { return el('span', { class: 'seg seg-' + k, style: 'flex-grow:' + r[k] }); }));
      var legend = el('ul', { class: 'votebar-legend' }, parts.map(function (k) {
        return el('li', {}, [el('i', { class: 'dot seg-' + k }), t(k) + ' ', el('strong', { text: String(r[k]) })]);
      }));
      return el('div', { class: 'votebar compact' }, [track, legend]);
    }
    function row(r) {
      var date = el('td', { class: 'date', text: fmtDate(r.date) });
      if (kind === 'meetings') {
        var stage = el('span', { class: r.stage === 'agenda' ? 'chip agenda' : 'chip muted', text: t(r.stage) });
        return el('tr', {}, [
          date,
          el('td', {}, [el('a', { class: 't', href: r.url, text: r.body }), el('span', { class: 'sub' }, [stage, ' ', t('type_' + r.bodyType)])]),
          el('td', { text: regionName(r.region) }),
          el('td', { class: 'num' }, [String(r.items) + ' ', el('span', { class: 'note', text: t('itemsCount') }),
            r.votes ? el('span', { class: 'sub' }, [el('span', { class: 'chip vote', text: r.votes + ' ' + t(r.votes === 1 ? 'voteOne' : 'votesCount') })]) : null]),
        ]);
      }
      return el('tr', {}, [
        date,
        el('td', {}, [el('a', { class: 't', href: r.url, text: r.title }),
          el('span', { class: 'sub', text: [regionName(r.region), r.body, r.number ? '§ ' + r.number : ''].filter(Boolean).join(' · ') })]),
        el('td', { class: 'result' }, [voteBar(r)]),
      ]);
    }
    function render() {
      header();
      tbody.innerHTML = '';
      var frag = document.createDocumentFragment();
      filtered.slice(0, shown).forEach(function (r) { frag.appendChild(row(r)); });
      if (!filtered.length) frag.appendChild(el('tr', {}, [el('td', { colspan: '4', text: t('noResults') })]));
      tbody.appendChild(frag);
      count.textContent = filtered.length.toLocaleString('fi-FI') + ' / ' + rows.length.toLocaleString('fi-FI') +
        (filtered.length > shown ? ' · ' + shown + ' ' + t('shown') : '');
      more.hidden = filtered.length <= shown;
    }

    // --------------------------------------------------------------- export
    function download(name, type, text) {
      var a = el('a', { href: URL.createObjectURL(new Blob([text], { type: type })), download: name });
      document.body.appendChild(a); a.click(); a.remove();
    }
    function exportRows(fmt) {
      var abs = function (u) { return u && u.charAt(0) === '/' ? location.origin + u : u; };
      var out = filtered.map(function (r) {
        var o = Object.assign({ regionName: regionName(r.region) }, r);
        o.url = abs(o.url);
        return o;
      });
      var name = 'terveyshamsteri-' + kind + '-' + new Date().toISOString().slice(0, 10);
      if (fmt === 'json') return download(name + '.json', 'application/json', JSON.stringify(out, null, 1));
      var cols = out.length ? Object.keys(out[0]) : [];
      var esc = function (v) { v = v == null ? '' : String(v); return /[",\n;]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
      var csv = [cols.join(',')].concat(out.map(function (o) { return cols.map(function (c) { return esc(o[c]); }).join(','); }));
      download(name + '.csv', 'text/csv;charset=utf-8', '﻿' + csv.join('\r\n'));
    }

    // --------------------------------------------------------------- wiring
    readUrl();
    root.addEventListener('input', function (e) { if (e.target.name === 'q') apply(); });
    root.addEventListener('change', function (e) { if (e.target.name && e.target.name !== 'q') apply(); });
    root.querySelectorAll('[data-all],[data-none]').forEach(function (b) {
      b.addEventListener('click', function () {
        var name = b.dataset.all || b.dataset.none;
        root.querySelectorAll('[name=' + name + ']').forEach(function (c) { c.checked = !!b.dataset.all; });
        apply();
      });
    });
    root.querySelector('[data-reset]').addEventListener('click', function () {
      form.q.value = form.from.value = form.to.value = '';
      root.querySelectorAll('input[type=checkbox]').forEach(function (c) { c.checked = true; });
      apply();
    });
    root.querySelector('[data-more]').addEventListener('click', function () { shown += PAGE * 2; render(); });
    root.querySelectorAll('[data-export]').forEach(function (b) {
      b.addEventListener('click', function () { exportRows(b.dataset.export); });
    });
    document.addEventListener('langchange', render);
    fetch(root.dataset.src).then(function (r) { return r.json(); }).then(function (data) { rows = data; apply(); })
      .catch(function () { count.textContent = '⚠ ' + root.dataset.src; });
  }

  document.querySelectorAll('.datatable').forEach(setup);
})();
