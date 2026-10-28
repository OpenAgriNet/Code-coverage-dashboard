const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
// built-in names for data written before dependencies.ecosystem_names and image kinds; the data's own names replace them
const ECO={npm:'Node.js',python:'Python',golang:'Go',docker:'Container',githubAction:'GitHub Actions',terraform:'Terraform',githubRelease:'CLI tool'};
// a Docker image reference split into its registry (Docker Hub when none is named) and its repository path
function image(n){const p=n.split('/'),host=p.length>1&&/[.:]|^localhost$/.test(p[0]);return {registry:host?p[0]:'docker.io',path:(host?p.slice(1):p).join('/')}}
const LINK={npm:n=>`https://www.npmjs.com/package/${n}`,python:n=>`https://pypi.org/project/${n}/`,golang:n=>`https://pkg.go.dev/${n}`,
  docker:n=>{const i=image(n);return i.registry!=='docker.io'?null:`https://hub.docker.com/r/${i.path.includes('/')?i.path:'_/'+i.path}`},githubAction:n=>`https://github.com/${n}`,
  githubRelease:n=>`https://github.com/${n}/releases`,
  terraform:n=>{const p=n.split('/');return p.length===3&&p[0]==='registry.terraform.io'?`https://registry.terraform.io/providers/${p[1]}/${p[2]}`:`https://search.opentofu.org/provider/${p[p.length-2]}/${p[p.length-1]}`}};
// The shown name is the collector's short (scripts/stackinfo/rules/names.py short_name, written on every refresh);
// the full name stays in the tooltip, search and link.
const displayName=d=>d.short||d.name;
// GitHub (or Docker Hub) stars, compact: 950, 4.8k, 230k
const starCount=n=>!Number.isFinite(n)||n<0?'':n>=1e6?(n/1e6).toFixed(1).replace(/\.0$/,'')+'M':n>=1e4?Math.round(n/1e3)+'k':n>=1e3?(n/1e3).toFixed(1).replace(/\.0$/,'')+'k':String(n);
// GitHub's star octicon (MIT, primer/octicons)
const STAR='<svg class="star-icon" viewBox="0 0 16 16" width="12" height="12" aria-hidden="true"><path d="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Zm0 2.445L6.615 5.5a.75.75 0 0 1-.564.41l-3.097.45 2.24 2.184a.75.75 0 0 1 .216.664l-.528 3.084 2.769-1.456a.75.75 0 0 1 .698 0l2.77 1.456-.53-3.084a.75.75 0 0 1 .216-.664l2.24-2.183-3.096-.45a.75.75 0 0 1-.564-.41L8 2.694Z"/></svg>';
const starChip=(n,of)=>!Number.isFinite(n)?'':` <span class="stars" title="${esc(n.toLocaleString()+' stars on '+of)}">${STAR}${starCount(n)}<span class="sr"> stars</span></span>`;
// an image's ecosystem is what it is (Database, Cache, Observability, ...) as the collector classed it
const ecoOf=d=>d.ecosystem==='docker'?d.kind||'docker':d.ecosystem;
const LOOKED=['npm','python','golang','githubAction'],SEVCLASS={CRITICAL:'bad',HIGH:'bad',MODERATE:'warn',LOW:'muted',UNKNOWN:'warn'};
const RISK={green:'Preferred (green)',yellow:'Not recommended (yellow)',red:'Restricted use (red)',unclassified:'Unclassified',none:'No license',na:'Not looked up'};
const VULN={'critical-high':'Critical or high',any:'Any known vulnerability',none:'None known',unchecked:'Not checked'};
const GROUP={main:'main (installed with the app)',dev:'dev',test:'test',security:'security',optional:'optional',peer:'peer',runtime:'runtime (Docker image)',ci:'ci (GitHub Action)',tool:'tool','(not found)':'not found in a manifest'};
const UPDATE={behind:'Update available',current:'Up to date',unknown:'Unknown'};
let data={},repos=[],all=[],policy={green:[],yellow:[],red:[]},bar=null,view=Branches.initial();   // dev or main, shared with index.html (assets/branches.js)

const vnum=v=>{const m=String(v||'').replace(/^[\^~=<>v\s]+/,'').match(/^\d+(?:\.\d+)*/);return m?m[0].split('.').map(Number):null};
function newer(a,b){const x=vnum(a),y=vnum(b);if(!x||!y)return null;for(let i=0;i<Math.max(x.length,y.length);i++){const d=(x[i]||0)-(y[i]||0);if(d)return d>0}return false}
const updateOf=d=>{const n=newer(d.latest,d.version);return n===null?'unknown':n?'behind':'current'};
// a license the collector says does not exist for this dependency is 'not looked up' (N/A); one it could not find is 'no license' (nil)
// no license with a class: the policy's licenses.no_license class (nothing states a license for it)
const riskOf=d=>d.license?d.license_class||'unclassified':d.license_class?d.license_class:d.missing&&d.missing.license?(d.missing.license.state==='na'?'na':'none'):LOOKED.includes(d.ecosystem)&&!local(d)?'none':'na';
function vulnOf(d){const q=d.vulns;if(!q)return['unchecked'];if(!q.count)return['none'];return q.severity==='CRITICAL'||q.severity==='HIGH'?['any','critical-high']:['any']}

const FACETS=[
  {key:'repository',param:'repo',label:'Repository',get:d=>d.repository},
  {key:'ecosystem',param:'eco',label:'Ecosystem',get:ecoOf,valueLabel:v=>ECO[v]||v},
  {key:'license',param:'license',label:'License',get:d=>d.license||'(none)'},
  {key:'risk',label:'License risk',get:riskOf,valueLabel:v=>RISK[v]||v,order:['red','yellow','green','unclassified','none','na']},
  {key:'vuln',label:'Vulnerabilities',get:vulnOf,valueLabel:v=>VULN[v]||v,order:['critical-high','any','none','unchecked']},
  {key:'group',label:'Group',get:d=>d.groups&&d.groups.length?d.groups:['(not found)'],valueLabel:v=>GROUP[v]||v,order:['main','dev','test','security','optional','peer','runtime','ci','tool']},
  {key:'update',label:'Update status',get:updateOf,valueLabel:v=>UPDATE[v]||v,order:['behind','current','unknown']},
];

// nil: the value exists but the dashboard could not get it; N/A: there is no such value for this dependency
const local=d=>d.ecosystem==='githubAction'&&d.name.startsWith('./');
const NIL=why=>`<span class="muted" title="${esc(why)}">nil</span>`,NA=why=>`<span class="muted" title="${esc(why)}">N/A</span>`;
// the collector's reason for an empty value (scripts/stackinfo/rules/reasons.py); null for data written before reasons existed
const missingCell=(d,col)=>{const m=d.missing&&d.missing[col];return m?(m.state==='na'?NA(m.why):NIL(m.why)):null};
// The findings card behind Fixed in: every advisory with its package, severity and fix
let shown=[];
function sevBadge(s){return `<span class="sev ${SEVCLASS[s]||'warn'}">${esc(s==='UNKNOWN'?'not rated':String(s).toLowerCase())}</span>`}
function openCard(d){
  const q=d.vulns;if(!q)return;
  const at=d.resolved||(q.checked_version&&q.checked_version!==d.version?q.checked_version:'');
  $('vc-title').textContent=`${displayName(d)} ${d.version}${at?` (${at})`:''}`;
  const fixable=q.fixable!=null?q.fixable:q.items.filter(i=>i.fixed).length;
  $('vc-sub').innerHTML=`${esc(d.name)} · ${q.count} known · <span class="${SEVCLASS[q.severity]||'warn'}">worst ${esc(q.severity==='UNKNOWN'?'not rated':String(q.severity).toLowerCase())}</span> · ${q.fixed_in?`all fixable ones fixed in <code>${esc(q.fixed_in)}</code>`:`${fixable} fixable`}${q.unfixed?` · ${q.unfixed} with no fix released`:''}`;
  const rows=q.items.map(i=>{
    // image findings name the package inside the image in their summary ("glibc 2.36-9: ..."); a package's own findings are about itself
    const m=d.ecosystem==='docker'&&/^(\S+) (\S+): (.*)$/.exec(i.summary||'');
    const pkg=m?`${esc(m[1])} <span class="muted">${esc(m[2])}</span>`:`${esc(displayName(d))} <span class="muted">${esc(q.checked_version||d.version)}</span>`;
    return `<tr><td><a href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.cve||i.id)}</a>${i.cve&&i.id!==i.cve?`<div class="sub">${esc(i.id)}</div>`:''}</td><td>${sevBadge(i.severity)}</td><td>${pkg}</td><td>${i.fixed?`<code>${esc(i.fixed)}</code>`:'<span class="bad">no fix</span>'}</td><td>${esc(m?m[3]:i.summary)}</td></tr>`}).join('');
  $('vc-body').innerHTML=`<table><thead><tr><th class="c-adv">Advisory</th><th class="c-sev">Severity</th><th class="c-pkg">Package</th><th class="c-fix">Fixed in</th><th class="c-sum">Summary</th></tr></thead><tbody>${rows}</tbody></table>${q.count>q.items.length?`<p class="sub">The ${q.items.length} most severe of ${q.count} are listed.</p>`:''}`;
  $('vuln-card').showModal();
}
function vulnCells(d){
  const q=d.vulns;
  if(local(d))return[NA('An action in this repository, not a published package'),NA('No vulnerabilities to fix')];
  if(!q&&missingCell(d,'vulns'))return[missingCell(d,'vulns'),NA('Nothing was checked, so there is nothing to fix')];
  if(!q)return[NIL(d.ecosystem==='docker'?'Not scanned: the tag is an unresolved ${VAR}, the image could not be pulled anonymously (private, or built locally), or the scan failed':d.ecosystem==='githubAction'?'Not checked: pinned to a branch or a commit no release tag points at, or the GitHub lookup failed':LOOKED.includes(d.ecosystem)?'Not checked: the version is not exact or the lookup failed':'Not checked: vulnerability lookup does not cover this ecosystem yet'),NA('No known vulnerabilities to fix')];
  if(!q.count)return['<span class="good">None known</span>',NA('No known vulnerabilities to fix')];
  const cls=SEVCLASS[q.severity]||'warn',worst=q.severity==='UNKNOWN'?'severity not rated':q.severity.toLowerCase();
  const list=q.items.map(i=>`<li><a href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.cve||i.id)}</a> <span class="sev ${SEVCLASS[i.severity]||'warn'}">${esc(i.severity==='UNKNOWN'?'not rated':i.severity.toLowerCase())}</span> ${esc(i.summary)} — ${i.fixed?`fixed in <code>${esc(i.fixed)}</code>`:'no fix released'}</li>`).join('');
  const note=q.exact?'':`<div class="sub">Checked at ${esc(q.checked_version)}, the lowest version the range allows</div>`;
  const fixed=d.ecosystem==='docker'?(q.fixable?`<span class="warn" title="Fixed in newer versions of the packages inside the image; a newer image tag usually includes them">${q.fixable} fixable</span>`:'<span class="bad">No fix released</span>')+(q.fixable&&q.unfixed?`<div class="sub">${q.unfixed} with no fix released</div>`:'')
    :q.fixed_in?`<code>${esc(q.fixed_in)}</code>${q.unfixed?`<div class="sub">${q.unfixed} more with no fix released</div>`:''}`:'<span class="bad">No fix released</span>';
  return[`<details class="vuln"><summary class="${cls}">${q.count} known · ${esc(worst)}</summary><ul>${list}</ul>${q.count>q.items.length?`<div class="sub">The ${q.items.length} most severe of ${q.count} are listed.</div>`:''}</details>${note}`,fixed];
}
function licCell(d){
  if(d.license_of==='error')return '<span class="warn" title="deps.dev did not answer; this is not a missing license">Lookup failed</span>';
  if(!d.license&&d.license_class){const r=d.license_class,why=((d.missing||{}).license||{}).why||'No license found';
    return `<span class="lic risk risk-${esc(r)}" title="${esc(why+'. '+RISK[r]+' under the license policy (licenses.no_license).')}"><span class="dot" aria-hidden="true"></span>No license</span><span class="sr"> (${esc(RISK[r])})</span>`}
  if(!d.license&&missingCell(d,'license'))return missingCell(d,'license');
  if(local(d)&&!d.license)return NA('An action in this repository, not a published package');
  if(!d.license&&d.ecosystem==='docker')return NA('The image declares no license label and names no GitHub source repository');
  if(!d.license)return LOOKED.includes(d.ecosystem)?'<span class="muted">Unknown</span>':NIL('Not looked up: license lookup does not cover this ecosystem yet');
  const r=riskOf(d);
  const several=d.license.includes(', ')?' All of these licenses apply, so the strictest one counts.':'';
  return `<span class="lic risk risk-${r}" title="${esc(RISK[r]+'.'+several)}"><span class="dot" aria-hidden="true"></span>${esc(d.license)}</span>${d.license_of==='latest'?' <span class="sub" title="Listed version not on deps.dev; license of the latest release">(latest)</span>':''}${d.license_of==='source'&&d.ecosystem!=='docker'?' <span class="sub" title="The registry states no license; this is the license of the package\'s source repository">(source repo)</span>':''}${d.license_of==='github'?' <span class="sub" title="deps.dev could not name this license (non-standard); this is GitHub\'s own license detection for the package\'s source repository">(GitHub detection)</span>':''}${d.license_of==='pypi'?' <span class="sub" title="deps.dev and GitHub could not name this license; this is the license PyPI\'s own metadata states">(PyPI metadata)</span>':''}${d.license_of==='repository'?' <span class="sub" title="This is the repository\'s own image, built from its Dockerfile: the repository\'s license">(this repository)</span>':''}${d.license_of==='config'?' <span class="sub" title="Stated in config/repos.json (dependencies.image_licenses)">(set in config)</span>':''}${d.license_of==='repo'?` <span class="sub" title="${esc('License of '+(d.license_from||'the GitHub repository')+', which config/repos.json names as this image\'s source (dependencies.image_sources)')}">(source repo)</span>`:''}${d.license_of==='package'?` <span class="sub" title="${esc('License of the image\'s own program inside it: '+(d.license_from||'its main package'))}">(main package)</span>`:''}${d.license_of==='label'?' <span class="sub" title="From the image\'s own license label (org.opencontainers.image.licenses): declared by whoever published the image, not verified">(image label)</span>':d.license_of==='source'&&d.ecosystem==='docker'?' <span class="sub" title="The image has no license label; this is the license of the GitHub repository its source label names">(source repo)</span>':''}<span class="sr"> (${esc(RISK[r])})</span>`;
}
function row(d,single,i){
  const href=(LINK[d.ecosystem]||(()=>null))(d.name);
  const shown=displayName(d),full=shown===d.name?'':` title="${esc(d.name)}"`;
  const name=href?`<a class="pkg" href="${esc(href)}"${full} target="_blank" rel="noopener">${esc(shown)}</a>`:`<span class="pkg"${full}>${esc(shown)}</span>`;
  const latest=updateOf(d)==='behind'?`<span class="warn">${esc(d.latest)}</span>`:d.latest?esc(d.latest):missingCell(d,'latest')?missingCell(d,'latest'):d.latest_of==='floating'?NA('A floating tag such as latest always points at the newest image'):local(d)?NA('An action in this repository has no releases'):NIL('Latest version not looked up for this ecosystem yet');
  const [vc,fx]=vulnCells(d);
  const rs=(repos.find(r=>r.repository===d.repository)||{}).stars;
  const rk=riskOf(d),hl=rk==='red'||rk==='yellow'?` class="row-risk-${rk}"`:'';   // licenses to avoid or use with care stand out
  return `<tr${hl}><td>${name}${starChip(d.stars,d.stars_of)}${single?'':`<div class="sub">${esc(d.repository)}${starChip(rs,'github.com/'+(data.organization||'')+'/'+d.repository)}</div>`}</td><td data-label="Ecosystem">${esc(ECO[ecoOf(d)]||ecoOf(d))}${d.ecosystem==='docker'?`<div class="sub" title="Container image from this registry">image · ${esc(image(d.name).registry)}</div>`:''}</td><td data-label="Version"><code>${esc(d.version)}</code>${d.installed?`<div class="sub" title="The version the lockfile installs; vulnerabilities are checked at this version">installed ${esc(d.installed)}</div>`:''}${d.groups&&d.groups.length?`<div class="sub" title="${esc((d.sources||[]).join(', ')||'Declared in')}">${d.groups.map(esc).join(' · ')}</div>`:''}${d.resolved?`<div class="sub" title="The version this tag points to today">${esc(d.resolved)}</div>`:''}</td><td data-label="Latest">${latest}</td><td data-label="License">${licCell(d)}</td><td data-label="Vulnerabilities">${vc}</td><td data-label="Fixed in">${d.vulns&&d.vulns.count?`<button type="button" class="fix-open" data-i="${i}" aria-haspopup="dialog">${fx}<span class="open-hint">Details</span></button>`:fx}</td></tr>`;
}
// Row order: the Sort by menu, kept in ?sort=. Rows without stars, or not checked for vulnerabilities, go last.
const SORTS={
  repo:(a,b)=>a.repository.localeCompare(b.repository)||a.name.localeCompare(b.name),
  stars:(a,b)=>(Number.isFinite(b.stars)?b.stars:-1)-(Number.isFinite(a.stars)?a.stars:-1)||displayName(a).localeCompare(displayName(b)),
  stars_least:(a,b)=>(Number.isFinite(a.stars)?a.stars:Infinity)-(Number.isFinite(b.stars)?b.stars:Infinity)||displayName(a).localeCompare(displayName(b)),   // no stars still last
  name:(a,b)=>displayName(a).localeCompare(displayName(b),undefined,{sensitivity:'base'})||a.repository.localeCompare(b.repository),
  vulns:(a,b)=>((b.vulns||{}).count??-1)-((a.vulns||{}).count??-1)||SORTS.repo(a,b),
};
// each license list's name with its colour, e.g. Restricted use (red); the names come from licenses.labels
const withColour=l=>Object.fromEntries(Object.entries(l||{}).filter(([k])=>['green','yellow','red'].includes(k)).map(([k,v])=>[k,`${v} (${k})`]));
let sortBy=(k=>SORTS[k]?k:'repo')(new URLSearchParams(location.search).get('sort'));
function render(list,state){
  list=list.slice().sort(SORTS[sortBy]);
  const sel=(state.selected.repository||[]),single=sel.length===1?sel[0]:null;
  $('title').textContent=single?`${single} dependencies`:'Dependencies';
  const count=f=>list.filter(f).length,looked=list.filter(d=>LOOKED.includes(d.ecosystem)&&!local(d));
  const nv=count(d=>d.vulns&&d.vulns.count),unchecked=count(d=>!d.vulns),down=looked.length>0&&looked.every(d=>!d.vulns);
  const cls={};list.forEach(d=>{const r=riskOf(d);if(r!=='na')cls[r]=(cls[r]||0)+1});
  const risk=['red','yellow','green','unclassified','none'].filter(k=>cls[k]).map(k=>`<span class="risk risk-${k}"><span class="dot" aria-hidden="true"></span>${RISK[k]} <strong>${cls[k]}</strong></span>`).join(' · ');
  $('summary').innerHTML=`<strong>${list.length}</strong> ${list.length===1?'dependency':'dependencies'}${single?'':` in <strong>${new Set(list.map(d=>d.repository)).size}</strong> ${new Set(list.map(d=>d.repository)).size===1?'repository':'repositories'}`}. `
    +(down?'<strong class="warn">Vulnerability data is unavailable right now</strong> (the lookup failed; this is not a clean result). '
      :nv?`<strong class="bad">${nv}</strong> with known vulnerabilities. `:unchecked===list.length&&list.length?'':'No known vulnerabilities. ')
    +(unchecked&&!down?`${unchecked} not checked (unresolved or private images, local actions, unpinned versions). `:'')
    +(risk?`<br>License risk: ${risk}`:'');
  const meta=single&&repos.find(x=>x.repository===single);
  $('dep-note').innerHTML=!meta?`On the ${view==='main'?'default':'development'} branch, as chosen above.`:`Branch <code>${esc(meta.branch)}</code>${view==='dev'&&meta.branch_source==='default'?' <span class="muted" title="No branch matched the development pattern in config/repos.json">(default branch; no development branch found)</span>':''} · Repository license: ${meta.license?`<span class="lic risk risk-${meta.license_class||'unclassified'}"><span class="dot" aria-hidden="true"></span>${esc(meta.license)}</span>`:meta.license_class?`<span class="lic risk risk-${esc(meta.license_class)}"><span class="dot" aria-hidden="true"></span>No LICENSE file</span>`:'<span class="lic none">No LICENSE file</span>'}`;
  $('rows').innerHTML=list.length?(shown=list).map((d,i)=>row(d,single,i)).join(''):`<tr><td colspan="7" class="empty">${all.length?'No dependencies match these filters.':'No dependencies found.'}</td></tr>`;
}
function renderPolicy(){
  $('policy-title').textContent=`License policy: ${RISK.green}, ${RISK.yellow}, ${RISK.red}`;
  const any=['green','yellow','red'].some(k=>(policy[k]||[]).length);
  $('policy').innerHTML=any?`<ul class="policy">${['green','yellow','red'].map(k=>`<li><span class="risk risk-${k}"><span class="dot" aria-hidden="true"></span><b>${RISK[k]}</b></span> ${(policy[k]||[]).length?(policy[k]).map(x=>`<code>${esc(x)}</code>`).join(' '):'<span class="muted">none listed</span>'}</li>`).join('')}${policy.no_license?`<li><span class="risk risk-${esc(policy.no_license)}"><span class="dot" aria-hidden="true"></span><b>${esc(RISK[policy.no_license])}</b></span> also: <i>no license</i> (nothing states one; a failed lookup is not counted)</li>`:''}</ul>`
    :'<p class="muted" style="margin:0 0 14px">No license policy yet. Add SPDX ids or patterns (such as <code>GPL-*</code>) under <code>licenses.green</code> (Preferred), <code>yellow</code> (Not recommended) and <code>red</code> (Restricted use) in <code>config/repos.json</code>; licenses on no list show as unclassified.</p>';
}
function load(){   // the records of the branch being shown
  // Development lists only repos whose development branch was found; the note under the switch names the others
  repos=(view==='main'?data.main||data.repositories||[]:Branches.devOnly(data.repositories)).slice().sort((a,b)=>a.repository.localeCompare(b.repository));
  all=repos.flatMap(r=>(r.dependencies||[]).map(d=>({...d,repository:r.repository}))).sort((a,b)=>a.repository.localeCompare(b.repository)||a.name.localeCompare(b.name));
}
function setView(v,store=true){
  view=v;load();
  if(store)Branches.remember(v);
  Branches.paint(v,data.repositories||[],data.main||data.repositories||[]);
  bar.setItems(all);   // re-renders through the filter bar, which keeps the filters
}
async function init(){
  try{
    const res=await fetch('./data/stack.json',{cache:'no-store'});if(!res.ok)throw Error(res.status);
    data=await res.json();policy=data.license_policy||policy;load();
    // names set in config/repos.json (licenses.labels, dependencies.ecosystem_names); the built-in ones cover older data
    Object.assign(RISK,withColour(policy.labels));Object.assign(ECO,(data.display||{}).ecosystems||{});
    $('updated').textContent=data.generated_at?'Updated '+new Date(data.generated_at).toLocaleString(undefined,{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}):'';
    renderPolicy();
    bar=Filters.createFilterBar($('filters'),{facets:FACETS,items:all,noun:'dependencies',text:{param:'q',placeholder:'Find a package or license',of:d=>d.name+' '+(d.license||'')},onChange:render});
    setView(view,false);
  }catch(e){
    $('updated').textContent='Data unavailable';
    $('summary').textContent='Dependency data could not be loaded. Run the refresh workflow and check its logs.';
    $('rows').innerHTML='<tr><td colspan="7" class="empty">data/stack.json is missing or unreadable.</td></tr>';
  }
}
$('sort').value=sortBy;
$('sort').addEventListener('change',e=>{
  sortBy=SORTS[e.target.value]?e.target.value:'repo';
  const q=new URLSearchParams(location.search);sortBy==='repo'?q.delete('sort'):q.set('sort',sortBy);
  try{history.replaceState(null,'',(q.toString()?'?'+q:location.pathname)+location.hash)}catch(_){}
  if(bar)bar.setItems(all);   // re-renders through the filter bar, which keeps the filters
});
$('view-dev').addEventListener('click',()=>setView('dev'));$('view-main').addEventListener('click',()=>setView('main'));
init();
$('rows').addEventListener('click',e=>{const b=e.target.closest('.fix-open');if(b)openCard(shown[+b.dataset.i])});
$('vc-close').addEventListener('click',()=>$('vuln-card').close());
$('vuln-card').addEventListener('click',e=>{if(e.target===e.currentTarget)$('vuln-card').close()});   // a click on the backdrop
