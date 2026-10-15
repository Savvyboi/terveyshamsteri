// Fills a DataTable component from its JSON file. Filters live in the URL so a filtered
// view can be shared; exports download exactly the rows that pass the filters.
(function () {
  var PAGE = 50;
  var FILTERS = ['region', 'type', 'stage', 'party', 'status'];

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
      ['q', 'from', 'to'].forEach(function (k) { if (form[k] && p.get(k)) form[k].value = p.get(k); });
      FILTERS.forEach(function (name) {
        if (!p.has(name)) return;
        var want = p.get(name) === '-' ? [] : p.get(name).split(',');
        root.querySelectorAll('[name=' + name + ']').forEach(function (c) { c.checked = want.indexOf(c.value) >= 0; });
      });
      if (p.get('sort')) root.querySelectorAll('[name=sort]').forEach(function (c) { c.checked = c.value === p.get('sort'); });
    }
    function writeUrl() {
      var p = new URLSearchParams(location.search);
      ['q', 'from', 'to'].forEach(function (k) { if (form[k] && form[k].value) p.set(k, form[k].value); else p.delete(k); });
      FILTERS.forEach(function (name) {
        var all = root.querySelectorAll('[name=' + name + ']');
        var on = checked(name);
        var dflt = Array.prototype.filter.call(all, function (c) { return c.defaultChecked; }).map(function (c) { return c.value; });
        if (!all.length || on.join(',') === dflt.join(',')) p.delete(name); else p.set(name, on.join(',') || '-');
      });
      if (sortKey() !== root.querySelector('[name=sort]').value) p.set('sort', sortKey()); else p.delete('sort');
      var qs = p.toString();
      history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash);
    }

    // ------------------------------------------------------------- filtering
    function apply() {
      var q = form.q.value.trim().toLowerCase();
      var sets = {};
      FILTERS.forEach(function (name) { if (root.querySelector('[name=' + name + ']')) sets[name] = checked(name); });
      var field = { region: 'region', type: 'bodyType', stage: 'stage', party: 'party', status: 'status' };
      var from = form.from ? form.from.value : '', to = form.to ? form.to.value : '';
      filtered = rows.filter(function (r) {
        for (var name in sets) if (sets[name].indexOf(r[field[name]]) < 0) return false;
        if (from && r.date < from) return false;
        if (to && r.date > to) return false;
        if (q && [r.title, r.body, r.name].every(function (v) { return !v || v.toLowerCase().indexOf(q) < 0; })) return false;
        return true;
      });
      var s = sortKey();
      var att = function (r) { return r.present + r.absent ? r.present / (r.present + r.absent) : -1; };
      var margin = function (r) { return r.jaa == null || r.ei == null ? 1e9 : Math.abs(r.jaa - r.ei); };
      filtered.sort(function (a, b) {
        if (s === 'oldest') return a.date.localeCompare(b.date);
        if (s === 'mostItems') return b.items - a.items || b.date.localeCompare(a.date);
        if (s === 'closest') return margin(a) - margin(b) || b.date.localeCompare(a.date);
        if (s === 'mostVotes') return (b.votes || 0) - (a.votes || 0);
        if (s === 'bestAttendance') return att(b) - att(a) || (b.votes || 0) - (a.votes || 0);
        if (s === 'alphabetical') return a.name.localeCompare(b.name, 'fi');
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
      people: [['councillors'], ['region'], ['electionVotes', 'num'], ['councilAttendance', 'num']],
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
      if (kind === 'people') {
        var pm = cfg.parties[r.party] || { color: '#7a8494', fi: r.party };
        var total = r.present + r.absent;
        var pct = total ? Math.round(100 * r.present / total) : null;
        return el('tr', {}, [
          el('td', {}, [el('a', { class: 't', href: r.url, text: r.name }),
            el('span', { class: 'sub' }, [
              el('span', { class: 'party', title: pm[lang()] || pm.fi }, [el('i', { class: 'party-dot', style: 'background:' + pm.color }), el('abbr', { text: r.party })]),
              ' · ' + t('st_' + r.status) + (r.incumbent ? ' · ' + t('incumbent') : '')])]),
          el('td', { text: regionName(r.region) }),
          el('td', { class: 'num', text: r.votes == null ? '–' : r.votes.toLocaleString('fi-FI') }),
          el('td', { class: 'num' }, pct == null ? ['–'] : [
            el('span', { class: 'pct-cell' }, [el('span', { class: 'meter' }, [el('span', { style: 'width:' + pct + '%' })]), pct + ' %']),
            el('span', { class: 'note', text: r.present + '/' + total })]),
        ]);
      }
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
      ['q', 'from', 'to'].forEach(function (k) { if (form[k]) form[k].value = ''; });
      root.querySelectorAll('input[type=checkbox]').forEach(function (c) { c.checked = c.defaultChecked; });
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
