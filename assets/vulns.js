/* The Vulnerabilities tab of index.html: every advisory found in the dependencies the page's filters show, one row per advisory,
 * with every package and place it was found in. Built from the same records as the All dependencies tab (assets/deps.js), so the
 * branch switch and the repository filters at the top apply. index.js calls Vulns.init() once data/stack.json has loaded and
 * Vulns.refresh() whenever the branch or its filters change. */
(function (root) {
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const D=root.Deps;
const plural=(n,one,many)=>`${n.toLocaleString()} ${n===1?one:many}`;
const sevRank=s=>{const i=D.SEVS.indexOf(s);return i<0?D.SEVS.length-1:i};
const KIND_LABEL=Object.fromEntries(D.KINDS);

// the package an advisory is about: for an image the package inside it ("glibc 2.36-9: ..."), else the dependency itself
function affected(d,i){
  if(d.ecosystem==='docker'){
    if(i.package)return {name:i.package,version:i.version,kind:D.innerKind(i.ecosystem),text:i.summary.replace(/^\S+ \S+: /,'')};
    const m=/^(\S+) (\S+): (.*)$/.exec(i.summary||'');
    if(m)return {name:m[1],version:m[2],kind:'Package inside the image',text:m[3]};
  }
  return {name:D.displayName(d),version:(d.vulns&&d.vulns.checked_version)||d.version,kind:D.ECO[D.ecoOf(d)]||D.ecoOf(d),text:i.summary||''};
}
// one row per advisory id, gathering every place it was found
function advisories(deps){
  const by=new Map();
  for(const d of deps){
    const q=d.vulns;if(!q||!q.items)continue;
    for(const i of q.items){
      const a=affected(d,i),k=i.id;
      const row=by.get(k)||{id:i.id,cve:i.cve,url:i.url,severity:i.severity,text:a.text,packages:new Map(),places:[],fixes:new Set(),unfixed:false};
      if(sevRank(i.severity)<sevRank(row.severity))row.severity=i.severity;
      row.packages.set(a.name+' '+a.version,{name:a.name,version:a.version,kind:a.kind,fixed:i.fixed});
      row.places.push({repository:d.repository,dep:d,kind:D.kindOf(d),pkg:a.name,version:a.version,fixed:i.fixed});
      if(i.fixed)row.fixes.add(i.fixed);else row.unfixed=true;
      by.set(k,row);
    }
  }
  return [...by.values()].map(r=>({...r,packages:[...r.packages.values()],repos:[...new Set(r.places.map(p=>p.repository))],kinds:[...new Set(r.places.map(p=>p.kind))],
    fix:r.unfixed&&r.fixes.size?'some':r.unfixed?'none':'all'}));
}
// how many advisories of images are not listed (data written before every finding was kept)
const missing=deps=>deps.reduce((s,d)=>s+(d.vulns&&d.vulns.items?Math.max(0,d.vulns.count-d.vulns.items.length):0),0);

const FACETS=[
  {key:'sev',param:'vsev',label:'Severity',hint:'Number of advisories',get:r=>r.severity,valueLabel:v=>D.SEVNAME[v]?D.SEVNAME[v][0].toUpperCase()+D.SEVNAME[v].slice(1):v,order:D.SEVS},
  {key:'fix',param:'vfix',label:'Fix',hint:'Number of advisories, by whether a newer version fixes them',get:r=>r.fix,
    valueLabel:v=>({all:'Fix released',some:'Fixed in some places only',none:'No fix released'}[v]||v),order:['all','some','none']},
  {key:'kind',param:'vkind',label:'Found in',hint:'Advisories found in at least one dependency of this kind',get:r=>r.kinds,valueLabel:v=>KIND_LABEL[v]||v,order:D.KINDS.map(k=>k[0])},
  {key:'pkgkind',param:'vtype',label:'Package type',hint:'What the affected package is',get:r=>[...new Set(r.packages.map(p=>p.kind))]},
  {key:'pkg',param:'vpkg',label:'Affected package',get:r=>[...new Set(r.packages.map(p=>p.name))]},
  {key:'dep',param:'vdep',label:'Dependency or image',get:r=>[...new Set(r.places.map(p=>D.displayName(p.dep)))]},
];
const SORTS={
  severe:(a,b)=>sevRank(a.severity)-sevRank(b.severity)||b.places.length-a.places.length||a.id.localeCompare(b.id),
  places:(a,b)=>b.places.length-a.places.length||SORTS.severe(a,b),
  nofix:(a,b)=>(a.fix==='none'?0:a.fix==='some'?1:2)-(b.fix==='none'?0:b.fix==='some'?1:2)||SORTS.severe(a,b),
  pkg:(a,b)=>a.packages[0].name.localeCompare(b.packages[0].name)||SORTS.severe(a,b),
  id:(a,b)=>(a.cve||a.id).localeCompare(b.cve||b.id),
};
let view=()=>'dev',rows=[],bar=null,pager=null,sortBy='severe',shown=[],deps=[];
function setUrl(k,v,dflt){const q=new URLSearchParams(location.search);v===dflt?q.delete(k):q.set(k,v);try{history.replaceState(null,'',q.toString()?'?'+q:location.pathname)}catch(_){}}
const card=(label,value,sub,tone='')=>`<div class="kpi"><div class="kpi-label">${esc(label)}</div><div class="kpi-value${tone?' '+tone:''}">${esc(value)}</div><div class="kpi-sub">${sub}</div></div>`;
function kpis(list){
  const n={};list.forEach(r=>n[r.severity]=(n[r.severity]||0)+1);
  const places=list.reduce((s,r)=>s+r.places.length,0),pk=new Set(list.flatMap(r=>r.packages.map(p=>p.name+' '+p.version))).size;
  const nofix=list.filter(r=>r.fix==='none').length,fixable=list.length-nofix;
  $('kpi-vulns').innerHTML=[
    card('Advisories',list.length.toLocaleString(),`${D.sevChips(n)}<div>found ${plural(places,'time','times')} in ${plural(new Set(list.flatMap(r=>r.repos)).size,'repository','repositories')}</div>`,list.length?'bad':'good'),
    card('Critical or high',((n.CRITICAL||0)+(n.HIGH||0)).toLocaleString(),`${n.CRITICAL||0} critical · ${n.HIGH||0} high`,(n.CRITICAL||0)+(n.HIGH||0)?'bad':''),
    card('Fixable',fixable.toLocaleString(),`a newer version fixes them${list.length?` · ${Math.round(fixable/list.length*100)}%`:''}`,fixable?'warn':''),
    card('No fix released',nofix.toLocaleString(),'no newer version fixes them yet',nofix?'bad':''),
    card('Affected packages',pk.toLocaleString(),'package versions with at least one advisory'),
  ].join('');
}
function row(r,i){
  const pk=r.packages.slice(0,3).map(p=>`<div><strong>${esc(p.name)}</strong> <code>${esc(p.version)}</code><div class="sub">${esc(p.kind)}</div></div>`).join('')+(r.packages.length>3?`<div class="sub">+${r.packages.length-3} more versions</div>`:'');
  const where=r.places.slice(0,3).map(p=>`<div>${esc(D.displayName(p.dep))} <span class="sub">${esc(p.dep.version)} · ${esc(p.repository)}</span></div>`).join('');
  const more=r.places.length>3?`<button type="button" class="fb-link" data-more="${i}">all ${r.places.length} places</button>`:'';
  const fix=[...r.fixes];
  const fixed=!fix.length?'<span class="bad">No fix released</span>':`<code>${esc(fix.slice(0,2).join(', '))}</code>${fix.length>2?` <span class="sub">+${fix.length-2}</span>`:''}${r.fix==='some'?'<div class="sub warn">not fixed in every package</div>':''}`;
  return `<tr><td><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.cve||r.id)}</a>${r.cve&&r.cve!==r.id?`<div class="sub">${esc(r.id)}</div>`:''}</td><td data-label="Severity">${D.sevBadge(r.severity)}</td>`
    +`<td data-label="Affected package">${pk}</td><td data-label="Found in">${where}${more}</td><td data-label="Fixed in">${fixed}</td><td data-label="Summary" class="vsum">${esc(r.text)}</td></tr>`;
}
function render(list){
  list=list.slice().sort(SORTS[sortBy]);shown=list;
  kpis(list);
  const gone=missing(deps);
  $('vuln-note').innerHTML=`One row per advisory, with every package and place it was found in. On the ${view()==='main'?'default':'development'} branch; the repository filters above apply.`
    +(gone?` <span class="warn">${plural(gone,'advisory','advisories')} of the largest images are not listed yet; the next refresh keeps all of them.</span>`:'');
  const page=pager.slice(list),at=pager.offset();
  $('vuln-rows').innerHTML=page.length?page.map((r,i)=>row(r,at+i)).join(''):`<tr><td colspan="6" class="empty">${rows.length?'No advisories match these filters.':'No known vulnerabilities.'}</td></tr>`;
}
function places(r){
  $('vc-title').textContent=`${r.cve||r.id}: found in ${r.places.length} places`;
  $('vc-sub').innerHTML=`${D.sevBadge(r.severity)} ${esc(r.text)}`;
  $('vc-body').innerHTML=`<table><thead><tr><th>Dependency or image</th><th>Repository</th><th>Affected package</th><th>Fixed in</th></tr></thead><tbody>`
    +r.places.map(p=>`<tr><td>${esc(D.displayName(p.dep))} <code>${esc(p.dep.version)}</code><div class="sub">${esc((D.KINDS.find(k=>k[0]===p.kind)||[])[1]||'')}</div></td><td>${esc(p.repository)}</td><td>${esc(p.pkg)} <code>${esc(p.version)}</code></td><td>${p.fixed?`<code>${esc(p.fixed)}</code>`:'<span class="bad">no fix</span>'}</td></tr>`).join('')+'</tbody></table>';
  $('vuln-card').showModal();
}
// o: { view() -> 'dev' | 'main' }
function init(o){
  view=o.view;
  const q=new URLSearchParams(location.search);
  sortBy=SORTS[q.get('vsort')]?q.get('vsort'):'severe';$('vuln-sort').value=sortBy;
  deps=D.load();rows=advisories(deps);
  pager=Pager.createPager($('vuln-pager'),{size:50,param:'vper',onChange:()=>render(bar.visible())});
  bar=Filters.createFilterBar($('vuln-filters'),{facets:FACETS,items:rows,noun:'advisories',text:{param:'vq',placeholder:'Find a CVE, package or text',of:r=>[r.id,r.cve,r.text,...r.packages.map(p=>p.name),...r.places.map(p=>p.dep.name)].join(' ')},onChange:list=>{pager.reset();render(list)}});
  render(bar.visible());
  $('vuln-sort').addEventListener('change',e=>{sortBy=SORTS[e.target.value]?e.target.value:'severe';setUrl('vsort',sortBy,'severe');pager.reset();render(bar.visible())});
  $('vuln-rows').addEventListener('click',e=>{const b=e.target.closest('[data-more]');if(b)places(shown[+b.dataset.more])});
}
function refresh(){if(bar){deps=D.load();rows=advisories(deps);bar.setItems(rows)}}
const exportRows=()=>shown;
root.Vulns={init,refresh,exportRows,advisories};
})(window);
