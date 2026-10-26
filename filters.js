/* Multi-select filter bar shared by index.html and deps.html. No dependencies.
 *
 * Logic: a filter with nothing ticked is off; ticked values within one filter are OR-ed; different filters are AND-ed.
 * Every option shows how many items it would give with the other filters as they are now (faceted counts), so an option
 * that would empty the result is greyed out instead of being a dead end. State lives in the URL query string.
 *
 * A facet is { key, label, get(item) -> value | [values], valueLabel?(value), order?: [values], param?: url parameter }. */
(function (root) {
  'use strict';
  const arr = v => (v == null ? [] : Array.isArray(v) ? v : [v]);
  const textHit = (item, text, textOf) => !text || !textOf || textOf(item).toLowerCase().includes(text.toLowerCase());
  const matches = (item, facets, selected, skip) => facets.every(f => {
    if (f.key === skip) return true;
    const sel = selected[f.key];
    return !sel || !sel.length || arr(f.get(item)).some(v => sel.includes(v));
  });
  const filterItems = (items, facets, selected, text, textOf) => items.filter(it => matches(it, facets, selected) && textHit(it, text, textOf));

  /* Options of one facet: every value in the data (plus any selected value that is not), with the count it would give. */
  function optionList(items, facet, facets, selected, text, textOf) {
    const counts = new Map(), all = new Set(selected[facet.key] || []);
    for (const it of items) {
      const vals = arr(facet.get(it));
      vals.forEach(v => all.add(v));
      if (!matches(it, facets, selected, facet.key) || !textHit(it, text, textOf)) continue;
      vals.forEach(v => counts.set(v, (counts.get(v) || 0) + 1));
    }
    const order = facet.order || [], on = selected[facet.key] || [];
    return [...all].map(v => ({ value: v, label: facet.valueLabel ? facet.valueLabel(v) : String(v), count: counts.get(v) || 0, selected: on.includes(v) }))
      .sort((a, b) => {
        const ia = order.indexOf(a.value), ib = order.indexOf(b.value);
        if (ia >= 0 || ib >= 0) return (ia < 0 ? 1e9 : ia) - (ib < 0 ? 1e9 : ib);
        return a.label.localeCompare(b.label, undefined, { numeric: true });
      });
  }
  const param = f => f.param || f.key;
  function readParams(search, facets, textParam) {
    const p = new URLSearchParams(search), selected = {};
    for (const f of facets) {
      const v = [...new Set(p.getAll(param(f)).filter(Boolean))];
      if (v.length) selected[f.key] = v;
    }
    return { selected, text: textParam ? p.get(textParam) || '' : '' };
  }
  /* Rewrites only this bar's own parameters, so two bars on one page do not erase each other. */
  function writeParams(search, facets, textParam, selected, text) {
    const p = new URLSearchParams(search);
    facets.forEach(f => p.delete(param(f)));
    if (textParam) p.delete(textParam);
    facets.forEach(f => (selected[f.key] || []).forEach(v => p.append(param(f), v)));
    if (textParam && text) p.set(textParam, text);
    return p.toString();
  }

  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  let barCount = 0;

  /* cfg: { facets, items, noun, text?: { param, placeholder, of(item) }, onChange(visibleItems, state) }
   * Returns { setItems(items), state(), visible(), clear() }. */
  function createFilterBar(el, cfg) {
    const id = 'fb' + (++barCount), facets = cfg.facets, tx = cfg.text || null;
    let items = cfg.items || [], open = null;
    const init = readParams(location.search, facets, tx && tx.param);
    let selected = init.selected, text = init.text;
    const textOf = tx && tx.of;
    el.classList.add('fb');
    el.innerHTML =
      `<div class="fb-row">${tx ? `<input type="search" class="fb-text" placeholder="${esc(tx.placeholder)}" aria-label="${esc(tx.placeholder)}" value="${esc(text)}">` : ''}` +
      facets.map(f => `<div class="fb-facet" data-key="${esc(f.key)}"><button type="button" class="fb-btn" aria-expanded="false" aria-haspopup="true" aria-controls="${id}-${esc(f.key)}">` +
        `<span>${esc(f.label)}</span><span class="fb-n" hidden></span><span class="fb-caret" aria-hidden="true">▾</span></button>` +
        `<div class="fb-pop" id="${id}-${esc(f.key)}" role="group" aria-label="Filter by ${esc(f.label)}" hidden></div></div>`).join('') + `</div>` +
      `<div class="fb-chips" hidden></div><p class="fb-status" role="status" aria-live="polite"></p>`;
    const $ = sel => el.querySelector(sel), btn = k => $(`.fb-facet[data-key="${CSS.escape(k)}"] .fb-btn`), pop = k => $(`.fb-facet[data-key="${CSS.escape(k)}"] .fb-pop`);
    const facet = k => facets.find(f => f.key === k);
    const visible = () => filterItems(items, facets, selected, text, textOf);

    function sync() {
      const q = writeParams(location.search, facets, tx && tx.param, selected, text);
      try { history.replaceState(null, '', q ? '?' + q : location.pathname); } catch (e) { /* file:// or sandbox */ }
    }
    function fillPop(f) {
      const opts = optionList(items, f, facets, selected, text, textOf), p = pop(f.key);
      const search = opts.length > 8 ? `<input type="search" class="fb-find" placeholder="Find ${esc(f.label.toLowerCase())}" aria-label="Find in ${esc(f.label)}">` : '';
      p.innerHTML = `<div class="fb-pop-head">${search}<button type="button" class="fb-link" data-act="clear">Clear</button></div><ul>` +
        opts.map(o => `<li data-value="${esc(o.value)}"><label><input type="checkbox" value="${esc(o.value)}"${o.selected ? ' checked' : ''}${!o.count && !o.selected ? ' disabled' : ''}>` +
          `<span class="fb-lab">${esc(o.label)}</span><span class="fb-count">${o.count}</span></label></li>`).join('') + `</ul>`;
    }
    function refreshPop(f) {   // update counts in place, so the focused checkbox is not rebuilt
      const byValue = new Map(optionList(items, f, facets, selected, text, textOf).map(o => [o.value, o]));
      pop(f.key).querySelectorAll('li').forEach(li => {
        const o = byValue.get(li.dataset.value), cb = li.querySelector('input');
        if (!o) return;
        li.querySelector('.fb-count').textContent = o.count;
        cb.checked = o.selected; cb.disabled = !o.count && !o.selected;
      });
    }
    function setOpen(k) {
      if (open && open !== k) { pop(open).hidden = true; btn(open).setAttribute('aria-expanded', 'false'); }
      open = k;
      if (k) { fillPop(facet(k)); pop(k).hidden = false; btn(k).setAttribute('aria-expanded', 'true'); }
    }
    function update(notify) {
      const shown = visible();
      facets.forEach(f => {
        const n = (selected[f.key] || []).length, b = btn(f.key), badge = b.querySelector('.fb-n');
        badge.hidden = !n; badge.textContent = n; b.classList.toggle('on', n > 0);
        if (open === f.key) refreshPop(f);
      });
      const chips = [];
      facets.forEach(f => (selected[f.key] || []).forEach(v => {
        const known = items.some(it => arr(f.get(it)).includes(v));
        chips.push(`<button type="button" class="fb-chip${known ? '' : ' fb-stale'}" data-key="${esc(f.key)}" data-value="${esc(v)}" aria-label="Remove filter ${esc(f.label)}: ${esc(f.valueLabel ? f.valueLabel(v) : v)}">` +
          `<span class="fb-chip-k">${esc(f.label)}</span> ${esc(f.valueLabel ? f.valueLabel(v) : v)}${known ? '' : ' (no data)'} <span aria-hidden="true">✕</span></button>`);
      }));
      if (text) chips.push(`<button type="button" class="fb-chip" data-text="1" aria-label="Remove search ${esc(text)}"><span class="fb-chip-k">Search</span> ${esc(text)} <span aria-hidden="true">✕</span></button>`);
      const chipBox = $('.fb-chips');
      chipBox.hidden = !chips.length;
      chipBox.innerHTML = chips.join('') + (chips.length > 1 ? '<button type="button" class="fb-link" data-act="clear-all">Clear all</button>' : '');
      const filtered = chips.length > 0;
      $('.fb-status').textContent = filtered ? `Showing ${shown.length} of ${items.length} ${cfg.noun}` : `${items.length} ${cfg.noun}`;
      sync();
      if (notify !== false && cfg.onChange) cfg.onChange(shown, { selected, text });
    }

    el.addEventListener('click', e => {
      const b = e.target.closest('.fb-btn');
      if (b) { const k = b.closest('.fb-facet').dataset.key; setOpen(open === k ? null : k); return; }
      const chip = e.target.closest('.fb-chip');
      if (chip) {
        if (chip.dataset.text) { text = ''; const t = $('.fb-text'); if (t) t.value = ''; }
        else selected[chip.dataset.key] = (selected[chip.dataset.key] || []).filter(v => v !== chip.dataset.value);
        update(); return;
      }
      const act = e.target.closest('[data-act]');
      if (!act) return;
      if (act.dataset.act === 'clear') { const k = act.closest('.fb-facet').dataset.key; selected[k] = []; update(); }
      if (act.dataset.act === 'clear-all') api.clear();
    });
    el.addEventListener('change', e => {
      const cb = e.target.closest('.fb-pop input[type=checkbox]');
      if (!cb) return;
      const k = cb.closest('.fb-facet').dataset.key, cur = new Set(selected[k] || []);
      cb.checked ? cur.add(cb.value) : cur.delete(cb.value);
      selected[k] = [...cur]; update();
    });
    el.addEventListener('input', e => {
      if (e.target.matches('.fb-text')) { text = e.target.value.trim(); update(); }
      if (e.target.matches('.fb-find')) {
        const q = e.target.value.toLowerCase();
        e.target.closest('.fb-pop').querySelectorAll('li').forEach(li => { li.hidden = !!q && !li.textContent.toLowerCase().includes(q); });
      }
    });
    el.addEventListener('keydown', e => {
      if (e.key === 'Escape' && open) { const k = open; setOpen(null); btn(k).focus(); }
    });
    document.addEventListener('pointerdown', e => { if (open && !el.contains(e.target)) setOpen(null); });
    el.addEventListener('focusout', e => { if (open && e.relatedTarget && !el.contains(e.relatedTarget)) setOpen(null); });

    const api = {
      setItems(next) { items = next || []; update(); },
      state: () => ({ selected, text }),
      visible,
      clear() { selected = {}; text = ''; const t = $('.fb-text'); if (t) t.value = ''; update(); },
    };
    update(false);
    return api;
  }

  const lib = { matches, filterItems, optionList, readParams, writeParams, createFilterBar };
  if (typeof module !== 'undefined' && module.exports) module.exports = lib; else root.Filters = lib;
})(typeof window !== 'undefined' ? window : globalThis);
