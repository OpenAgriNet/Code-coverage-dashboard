/* The Development / Main switch, shared by index.html and deps.html so every table on every page follows one choice.
 *
 * Development lists only repositories whose development branch was found: their dev_branch in config/repos.json, or a
 * branch matching branches.development. A repository without one is left out of Development (showing its default branch
 * there would pass main off as development); the note under the switch names it, and it is listed under Main.
 * Main lists every repository's default branch. The choice is kept in ?branch= and remembered across the two pages. */
(function (root) {
  'use strict';
  // branch_source is 'default' when no development branch was found and the collector fell back to the default branch
  const hasDev = r => !!r && r.branch_source !== 'default';
  const devOnly = list => (list || []).filter(hasDev);

  function initial() {
    let v = 'dev';
    try { if (localStorage.getItem('branchView') === 'main') v = 'main'; } catch (e) { /* storage blocked */ }
    const b = new URLSearchParams(location.search).get('branch');
    return b === 'main' || b === 'dev' ? b : v;
  }
  function remember(v) {
    try { localStorage.setItem('branchView', v); } catch (e) { /* storage blocked */ }
    try {
      const q = new URLSearchParams(location.search);
      q.set('branch', v);
      history.replaceState(null, '', location.pathname + '?' + q + location.hash);
    } catch (e) { /* file:// or sandbox */ }
  }
  /* The sentence under the switch. dev and main are the two lists of repository records as collected. */
  function note(view, dev, main) {
    const hidden = (dev || []).filter(r => !hasDev(r)).map(r => r.repository).sort((a, b) => a.localeCompare(b));
    if (view === 'main') return { text: `Each repository's default branch (${(main || []).length}).`, hidden: [] };
    if (!hidden.length) return { text: 'Each repository\'s development branch.', hidden };
    const n = hidden.length, one = n === 1;
    return {
      text: `Each repository's development branch. ${n} ${one ? 'repository has' : 'repositories have'} no development branch, so ${one ? 'it is' : 'they are'} shown only under Main: `,
      hidden,
    };
  }
  /* Set the buttons, their counts and the note (plain text: repository names never reach innerHTML). */
  function paint(view, dev, main) {
    const $ = id => document.getElementById(id);
    $('view-dev').setAttribute('aria-pressed', view === 'dev');
    $('view-main').setAttribute('aria-pressed', view === 'main');
    $('count-dev').textContent = devOnly(dev).length;
    $('count-main').textContent = (main || []).length;
    const n = note(view, dev, main);
    $('branch-note').textContent = n.text + n.hidden.join(', ') + (n.hidden.length ? '.' : '');
  }

  const lib = { hasDev, devOnly, initial, remember, note, paint };
  if (typeof module !== 'undefined' && module.exports) module.exports = lib; else root.Branches = lib;
})(typeof window !== 'undefined' ? window : globalThis);
