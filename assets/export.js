// The dashboard's tables as spreadsheet rows (assets/xlsx.js writes them): one builder per table, used both by each table's
// own Excel button (the rows on screen, filters applied) and by the workbook of everything on the main page.
(function (root) {
  const SECURITY = { passing: 'Passing', failing: 'Failing', 'no runs': 'No runs on this branch', 'no workflow': 'No security workflow', 'branch not found': 'Branch not found' };
  const CLASS = { green: 'Preferred (green)', yellow: 'Not recommended (yellow)', red: 'Restricted use (red)', unclassified: 'Unclassified' };
  const num = v => v == null || v === '' || !Number.isFinite(Number(v)) ? null : Number(v);
  const list = v => (v || []).join(', ');
  const date = v => v ? String(v).slice(0, 10) : null;
  // licenses.labels from config/repos.json name the classes; the colour stays in brackets
  const classLabel = (k, labels) => !k ? null : labels && labels[k] ? `${labels[k]} (${k})` : CLASS[k] || k;

  const COVERAGE = ['Repository', 'Tags', 'Branch', 'Branch kind', 'Branch chosen by', 'Code coverage %', 'Coverage source', 'Files', 'Lines', 'Hits', 'Misses', 'Measured on', 'Coverage commit', 'Coverage report', 'Security', 'Security run finished', 'Security run'];
  const covCells = r => {
    const c = r.coverage_detail || {}, s = r.security || {};
    return [num(r.coverage), r.coverage_source, num(c.files), num(c.lines), num(c.hits), num(c.misses), date(r.measured_at), r.coverage_commit, c.report_url,
      SECURITY[s.state] || s.state || null, date(s.finished_at), s.run_url];
  };
  // coverage.json repositories or main: one row per repository
  function coverage(repos) {
    return [COVERAGE, ...(repos || []).map(r => [r.repository, list(r.tags || (r.dpg ? ['DPG'] : [])), r.branch, r.ref_kind, r.branch_source, ...covCells(r)])];
  }
  const RELEASE = ['Repository', 'Version', 'Pre-release', 'Shown by default', 'Found as', 'Tag or branch', 'Published', 'Code coverage %', 'Coverage source', 'Files', 'Lines', 'Hits', 'Misses', 'Measured on', 'Coverage commit', 'Coverage report', 'Security', 'Security run finished', 'Security run'];
  const relRow = (g, v) => [g.repository, v.version, !!v.prerelease, v.version === g.default, list(v.kinds), v.branch, date(v.published_at), ...covCells(v)];
  // coverage.json releases: every version of every repository, or with pick(group) only the version each row shows
  function releases(groups, pick) {
    const rows = [];
    for (const g of groups || []) for (const v of pick ? [pick(g)].filter(Boolean) : g.versions || []) rows.push(relRow(g, v));
    return [RELEASE, ...rows];
  }
  const vulnerable = r => (r.dependencies || []).filter(d => d.vulns && d.vulns.count).length;
  // stack.json repositories or main: one row per repository
  function stack(repos, labels) {
    return [['Repository', 'Branch', 'Stars', 'License', 'License class', 'Languages', 'Technologies', 'Dependencies', 'With known vulnerabilities', 'Error'],
      ...(repos || []).map(r => [r.repository, r.branch, num(r.stars), r.license, classLabel(r.license_class, labels),
        (r.languages || []).map(l => Array.isArray(l) ? l[0] : l).join(', '), list(r.techs), (r.dependencies || []).length, vulnerable(r), r.error])];
  }
  const why = d => Object.entries(d.missing || {}).map(([k, m]) => `${k}: ${m.why}`).join(' | ');
  // dependency rows ({...dependency, repository}): one row per package per repository
  function dependencies(deps, labels, ecosystems) {
    const eco = d => d.ecosystem === 'docker' ? d.kind || 'Container' : (ecosystems && ecosystems[d.ecosystem]) || d.ecosystem;
    return [['Repository', 'Package', 'Short name', 'Ecosystem', 'Registry ecosystem', 'Version', 'Installed', 'Resolved', 'Groups', 'Latest', 'License', 'License class', 'License from', 'Stars',
      'Known vulnerabilities', 'Worst severity', 'Fixed in', 'Fixable', 'No fix released', 'Checked at version', 'Declared in', 'Source project', 'Why a value is missing'],
      ...(deps || []).map(d => { const q = d.vulns;
        return [d.repository, d.name, d.short || d.name, eco(d), d.ecosystem, d.version, d.installed, d.resolved, list(d.groups), d.latest, d.license,
          classLabel(d.license_class, labels), d.license_from || d.license_of, num(d.stars),
          q ? q.count : 'Not checked', q && q.count ? String(q.severity || '').toLowerCase() || null : null, q && q.fixed_in, q && num(q.fixable), q && num(q.unfixed),
          q && q.checked_version, list(d.sources), d.project, why(d)]; })];
  }
  // one row per advisory of every listed dependency
  function vulnerabilities(deps) {
    const rows = [];
    for (const d of deps || []) for (const i of (d.vulns && d.vulns.items) || []) {
      const m = d.ecosystem === 'docker' && /^(\S+) (\S+): (.*)$/.exec(i.summary || '');   // an image finding names the package inside it
      rows.push([d.repository, d.name, d.vulns.checked_version || d.version, m ? m[1] : d.name, m ? m[2] : d.vulns.checked_version || d.version,
        i.cve || i.id, i.id, String(i.severity || '').toLowerCase(), i.fixed || 'No fix', m ? m[3] : i.summary, i.url]);
    }
    return [['Repository', 'Dependency', 'Dependency version', 'Affected package', 'Affected version', 'Advisory', 'Advisory id', 'Severity', 'Fixed in', 'Summary', 'Link'], ...rows];
  }
  function policy(p) {
    p = p || {};
    return [['Class', 'Name', 'Licenses'], ...['green', 'yellow', 'red'].map(k => [k, (p.labels || {})[k] || CLASS[k], list(p[k])]),
      ...(p.no_license ? [['no_license', 'A dependency with no license', p.no_license]] : [])];
  }
  // a dated file name: openagrinet-dependencies-2026-10-29.xlsx
  const filename = what => `${what}-${new Date().toISOString().slice(0, 10)}.xlsx`;

  const lib = { coverage, releases, stack, dependencies, vulnerabilities, policy, filename };
  if (typeof module !== 'undefined' && module.exports) module.exports = lib; else root.Export = lib;
})(typeof window !== 'undefined' ? window : globalThis);
