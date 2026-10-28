/* Page sections as tabs: [role=tablist] buttons with data-tab, panels with id sec-<tab>. The open tab is kept in ?tab=. */
(function () {
  function init() {
    var list = document.querySelector('[role=tablist]');
    if (!list) return;
    var tabs = [].slice.call(list.querySelectorAll('[role=tab]'));
    function show(name, focus) {
      var known = tabs.some(function (t) { return t.dataset.tab === name; });
      if (!known) name = tabs[0].dataset.tab;
      tabs.forEach(function (t) {
        var on = t.dataset.tab === name;
        t.setAttribute('aria-selected', on ? 'true' : 'false');
        t.tabIndex = on ? 0 : -1;
        var p = document.getElementById(t.getAttribute('aria-controls'));
        if (p) p.hidden = !on;
        if (on && focus) t.focus();
      });
      try {
        var q = new URLSearchParams(location.search);
        if (name === tabs[0].dataset.tab) q.delete('tab'); else q.set('tab', name);
        history.replaceState(null, '', q.toString() ? '?' + q : location.pathname);
      } catch (e) { /* file:// or sandbox */ }
    }
    list.addEventListener('click', function (e) {
      var t = e.target.closest('[role=tab]');
      if (t) show(t.dataset.tab);
    });
    list.addEventListener('keydown', function (e) {
      var i = tabs.indexOf(document.activeElement);
      if (i < 0) return;
      var j = e.key === 'ArrowRight' ? (i + 1) % tabs.length : e.key === 'ArrowLeft' ? (i + tabs.length - 1) % tabs.length : e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length - 1 : -1;
      if (j >= 0) { e.preventDefault(); show(tabs[j].dataset.tab, true); }
    });
    show(new URLSearchParams(location.search).get('tab') || tabs[0].dataset.tab);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
