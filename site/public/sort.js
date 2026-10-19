// Sorts a table.sortable by the clicked column, using each cell's data-v.
document.querySelectorAll('table.sortable').forEach(function (t) {
  t.querySelectorAll('th[data-sort]').forEach(function (th, i) {
    th.tabIndex = 0;
    function go() {
      var asc = th.getAttribute('aria-sort') !== 'ascending';
      t.querySelectorAll('th[aria-sort]').forEach(function (h) { h.removeAttribute('aria-sort'); });
      th.setAttribute('aria-sort', asc ? 'ascending' : 'descending');
      var num = th.dataset.sort === 'num', tb = t.tBodies[0];
      Array.prototype.slice.call(tb.rows).sort(function (a, b) {
        var x = a.cells[i].dataset.v, y = b.cells[i].dataset.v;
        var d = num ? (x === '' ? 1e15 : +x) - (y === '' ? 1e15 : +y) : x.localeCompare(y, 'fi');
        return asc ? d : -d;
      }).forEach(function (r) { tb.appendChild(r); });
    }
    th.addEventListener('click', go);
    th.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
  });
});
