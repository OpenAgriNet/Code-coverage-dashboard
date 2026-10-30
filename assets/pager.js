/* Page through a long table: "1–50 of 464", previous / page numbers / next, and rows per page. Built from the page's own
 * button and select styles. createPager(el, {sizes, size, param, onChange(page)}) -> { slice(list) -> rows of the current page,
 * reset() back to page 1 }. The rows per page are kept in the address bar under param, so a link keeps them. No dependencies. */
(function (root) {
  'use strict';
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  // page numbers to show: the first, the last, and two either side of the current one, with gaps as null
  function pages(cur, n) {
    const out = [];
    for (let p = 1; p <= n; p++) if (p === 1 || p === n || Math.abs(p - cur) <= 2) out.push(p);
    return out.reduce((a, p) => (a.length && p - a[a.length - 1] > 1 ? a.push(null, p) : a.push(p), a), []);
  }
  function createPager(el, cfg) {
    const sizes = cfg.sizes || [25, 50, 100, 200];
    const want = Number(new URLSearchParams(location.search).get(cfg.param));
    let size = sizes.includes(want) ? want : cfg.size || sizes[0], page = 1, total = 0;
    el.classList.add('pager');
    function draw() {
      const n = Math.max(1, Math.ceil(total / size));
      if (page > n) page = n;
      const from = total ? (page - 1) * size + 1 : 0, to = Math.min(total, page * size);
      el.hidden = total <= sizes[0];
      el.innerHTML = `<span class="pager-info" aria-live="polite">${from.toLocaleString()}–${to.toLocaleString()} of ${total.toLocaleString()}</span>`
        + `<span class="switch pager-pages" role="group" aria-label="Pages"><button type="button" data-p="${page - 1}"${page <= 1 ? ' disabled' : ''} aria-label="Previous page">‹</button>`
        + pages(page, n).map(p => p === null ? '<span class="pager-gap" aria-hidden="true">…</span>'
          : `<button type="button" data-p="${p}" aria-pressed="${p === page}"${p === page ? ' aria-current="page"' : ''}>${p}</button>`).join('')
        + `<button type="button" data-p="${page + 1}"${page >= n ? ' disabled' : ''} aria-label="Next page">›</button></span>`
        + `<label class="sub pager-size">Rows per page <select class="ver">${sizes.map(s => `<option${s === size ? ' selected' : ''}>${esc(s)}</option>`).join('')}</select></label>`;
    }
    el.addEventListener('click', e => {
      const b = e.target.closest('button[data-p]');
      if (!b || b.disabled) return;
      page = +b.dataset.p; cfg.onChange(page);
      const top = el.closest('section'); if (top) top.scrollIntoView({ block: 'start' });
    });
    el.addEventListener('change', e => {
      if (!e.target.matches('select')) return;
      size = +e.target.value; page = 1;
      try { const q = new URLSearchParams(location.search); size === (cfg.size || sizes[0]) ? q.delete(cfg.param) : q.set(cfg.param, size); history.replaceState(null, '', q.toString() ? '?' + q : location.pathname); } catch (_) { /* file:// or sandbox */ }
      cfg.onChange(page);
    });
    return {
      slice(list) { total = list.length; draw(); return list.slice((page - 1) * size, page * size); },
      reset() { page = 1; },
      offset: () => (page - 1) * size,
    };
  }
  const lib = { createPager, pages };
  if (typeof module !== 'undefined' && module.exports) module.exports = lib; else root.Pager = lib;
})(typeof window !== 'undefined' ? window : globalThis);
