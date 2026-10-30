/* The All dependencies tab of index.html: every dependency of the repositories the page's own filters show, split by kind
 * (code packages, Docker Hub / GHCR / other registry images, GitHub Actions, CLI tools), with its own filter bar.
 * index.js calls Deps.init(...) once data/stack.json has loaded and Deps.refresh() whenever the branch or its filters change. */
(function (root) {
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
// built-in names for data written before dependencies.ecosystem_names and image kinds; the data's own names replace them
const ECO={npm:'Node.js',python:'Python',golang:'Go',docker:'Container',githubAction:'GitHub Actions',terraform:'Terraform',githubRelease:'CLI tool'};
// a Docker image reference split into its registry (Docker Hub when none is named) and its repository path
function image(n){const p=n.split('/'),host=p.length>1&&/[.:]|^localhost$/.test(p[0]);return {registry:host?p[0]:'docker.io',path:(host?p.slice(1):p).join('/')}}
const LINK={npm:n=>`https://www.npmjs.com/package/${n}`,python:n=>`https://pypi.org/project/${n}/`,golang:n=>`https://pkg.go.dev/${n}`,
  docker:n=>{const i=image(n);return i.registry==='ghcr.io'?`https://github.com/${i.path.split('/').slice(0,2).join('/')}/pkgs/container/${i.path.split('/').slice(1).join('/')}`:i.registry!=='docker.io'?null:`https://hub.docker.com/r/${i.path.includes('/')?i.path:'_/'+i.path}`},githubAction:n=>`https://github.com/${n}`,
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
const LOOKED=['npm','python','golang','githubAction'];
// where an image's kind was read: its Docker Hub category or its source repository's GitHub topic
const kindTitle=d=>d.ecosystem!=='docker'?'':` title="${esc(d.kind_of==='docker hub'?'The first category Docker Hub files this image under':d.kind_of==='github topic'?'The first GitHub topic of its source repository (Docker Hub gives no category)':'Neither Docker Hub nor its source repository says what this image is')}"`;
const RISK={green:'Preferred (green)',yellow:'Not recommended (yellow)',red:'Restricted use (red)',unclassified:'Unclassified',none:'No license',na:'Not looked up'};
const GROUP={main:'main (installed with the app)',dev:'dev',test:'test',security:'security',optional:'optional',peer:'peer',runtime:'runtime (Docker image)',ci:'ci (GitHub Action)',tool:'tool','(not found)':'not found in a manifest'};
const UPDATE={behind:'Update available',current:'Up to date',unknown:'Unknown'};

/* ---- the kind sub-tabs: where a dependency comes from ---- */
const KINDS=[['all','All'],['packages','Code packages'],['hub','Docker Hub images'],['ghcr','GHCR images'],['registry','Other registry images'],['actions','GitHub Actions'],['tools','CLI tools']];
const KIND_NOTE={all:'Every dependency the repositories name.',packages:'npm, PyPI, Go and Terraform packages from the repositories\' manifests.',
  hub:'Images from Docker Hub named in compose files and Dockerfiles. Their vulnerabilities are in the packages inside each image.',
  ghcr:'Images from GitHub Container Registry (ghcr.io). Their vulnerabilities are in the packages inside each image.',
  registry:'Images from other registries (cgr.dev, docker.langfuse.com, ...). Their vulnerabilities are in the packages inside each image.',
  actions:'GitHub Actions used in workflows, and the actions those use.',tools:'Programs downloaded from GitHub Releases in workflows and Dockerfiles.'};
const IMAGE_KINDS=['hub','ghcr','registry'];
function kindOf(d){
  if(d.ecosystem==='githubAction')return 'actions';
  if(d.ecosystem==='githubRelease')return 'tools';
  if(d.ecosystem!=='docker')return 'packages';
  const r=image(d.name).registry;return r==='docker.io'?'hub':r==='ghcr.io'?'ghcr':'registry';
}

/* ---- severity: counts of each, worst first ---- */
const SEVS=['CRITICAL','HIGH','MODERATE','LOW','UNKNOWN'];
const SEVNAME={CRITICAL:'critical',HIGH:'high',MODERATE:'medium',LOW:'low',UNKNOWN:'not rated'};
const SEVCLASS={CRITICAL:'bad',HIGH:'bad',MODERATE:'warn',LOW:'muted',UNKNOWN:'warn'};
// {CRITICAL: n, ...} for every advisory of a dependency; null when only some are listed (data from before by_severity existed)
function sevCounts(q){
  if(!q||!q.count)return null;
  if(q.by_severity)return q.by_severity;
  if(!q.items||q.items.length<q.count)return null;
  const n={};q.items.forEach(i=>{const k=SEVS.includes(i.severity)?i.severity:'UNKNOWN';n[k]=(n[k]||0)+1});return n;
}
const sevChips=n=>`<span class="sevs">${SEVS.filter(k=>n[k]).map(k=>`<span class="sevc sevc-${k.toLowerCase()}">${n[k]} ${SEVNAME[k]}</span>`).join('')}</span>`;
const sevVector=d=>{const n=sevCounts(d.vulns);return !d.vulns?[-1]:n?SEVS.map(k=>n[k]||0):[d.vulns.count?SEVS.length-SEVS.indexOf(d.vulns.severity):0]};
function sevBadge(s){return `<span class="sev ${SEVCLASS[s]||'warn'}">${esc(SEVNAME[s]||String(s).toLowerCase())}</span>`}
// whether the advisories can be fixed by an update: all, some, or none of them
function fixState(q){
  if(!q||!q.count)return null;
  const fixable=q.fixable!=null?q.fixable:q.fixed_in?q.count-(q.unfixed||0):0;
  return fixable>=q.count?'all':fixable>0?'some':'none';
}

let opts=null,policy={green:[],yellow:[],red:[]},all=[],bar=null,pager=null,kind='packages',shown=[],current=[];
const vnum=v=>{const m=String(v||'').replace(/^[\^~=<>v\s]+/,'').match(/^\d+(?:\.\d+)*/);return m?m[0].split('.').map(Number):null};
function newer(a,b){const x=vnum(a),y=vnum(b);if(!x||!y)return null;for(let i=0;i<Math.max(x.length,y.length);i++){const d=(x[i]||0)-(y[i]||0);if(d)return d>0}return false}
const updateOf=d=>{const n=newer(d.latest,d.version);return n===null?'unknown':n?'behind':'current'};
// a license the collector says does not exist for this dependency is 'not looked up' (N/A); one it could not find is 'no license' (nil)
// no license with a class: the policy's licenses.no_license class (nothing states a license for it)
const riskOf=d=>d.license?d.license_class||'unclassified':d.license_class?d.license_class:d.missing&&d.missing.license?(d.missing.license.state==='na'?'na':'none'):LOOKED.includes(d.ecosystem)&&!local(d)?'none':'na';
const vulnOf=d=>!d.vulns?'unchecked':d.vulns.count?'any':'none';
// every severity the dependency has an advisory of; with only the worst ones listed, the ones listed
const sevOf=d=>{const q=d.vulns;if(!q||!q.count)return [];const n=sevCounts(q);return n?Object.keys(n):[...new Set(q.items.map(i=>SEVS.includes(i.severity)?i.severity:'UNKNOWN'))]};

// parameters start with d, so they do not clash with the page's repository filters (repo, vuln, risk, license, q)
const FACETS=[
  {key:'ecosystem',param:'deco',label:'Ecosystem',get:ecoOf,valueLabel:v=>ECO[v]||v},
  {key:'license',param:'dlicense',label:'License',get:d=>d.license||'(none)'},
  {key:'risk',param:'drisk',label:'License risk',get:riskOf,valueLabel:v=>RISK[v]||v,order:['red','yellow','green','unclassified','none','na']},
  {key:'vuln',param:'dvuln',label:'Vulnerabilities',hint:'Number of dependencies',get:vulnOf,
    valueLabel:v=>({any:'Has known vulnerabilities',none:'None known',unchecked:'Not checked'}[v]||v),order:['any','none','unchecked']},
  {key:'sev',param:'dsev',label:'Severity',hint:'Dependencies with at least one advisory of this severity',get:sevOf,
    valueLabel:v=>'Has '+(SEVNAME[v]||v),order:SEVS},
  {key:'fix',param:'dfix',label:'Fix',hint:'Dependencies with known vulnerabilities, by whether an update fixes them',get:d=>fixState(d.vulns),
    valueLabel:v=>({all:'Fix released for all',some:'Fix released for some',none:'No fix released'}[v]||v),order:['all','some','none']},
  {key:'group',param:'dgroup',label:'Group',get:d=>d.groups&&d.groups.length?d.groups:['(not found)'],valueLabel:v=>GROUP[v]||v,order:['main','dev','test','security','optional','peer','runtime','ci','tool']},
  {key:'update',param:'dupdate',label:'Update status',get:updateOf,valueLabel:v=>UPDATE[v]||v,order:['behind','current','unknown']},
];

// nil: the value exists but the dashboard could not get it; N/A: there is no such value for this dependency
const local=d=>d.ecosystem==='githubAction'&&d.name.startsWith('./');
const NIL=why=>`<span class="muted" title="${esc(why)}">nil</span>`,NA=why=>`<span class="muted" title="${esc(why)}">N/A</span>`;
// the collector's reason for an empty value (scripts/stackinfo/rules/reasons.py); null for data written before reasons existed
const missingCell=(d,col)=>{const m=d.missing&&d.missing[col];return m?(m.state==='na'?NA(m.why):NIL(m.why)):null};

/* ---- packages inside an image: what osv-scanner found them as ---- */
const OS=/^(Debian|Ubuntu|Alpine|Wolfi|Chainguard|Red Hat|Rocky Linux|AlmaLinux|SUSE|openSUSE|Amazon Linux|Photon OS|Mariner|Azure Linux|CentOS|Oracle Linux)/i;
const INNER={Go:'Go module, compiled into a program',Maven:'Java library (Maven)',npm:'Node.js package',PyPI:'Python package','crates.io':'Rust crate',RubyGems:'Ruby gem',NuGet:'.NET package',Packagist:'PHP package'};
function innerKind(e){const [n,v]=String(e||'').split(':');return !n?'Package':OS.test(n)?`${n}${v?' '+v.replace(/^v/,''):''} system package`:INNER[n]||n}
// each affected package in the image with its installed version and the version that fixes it; from the collector's
// rollup, or (older data) from the listed advisories, whose summaries read "glibc 2.36-9: ..."
function innerPackages(q){
  if(q.packages)return {list:q.packages,complete:true};
  const by=new Map();
  for(const i of q.items){const m=/^(\S+) (\S+): /.exec(i.summary||'');if(!m)continue;
    const p=by.get(m[1]+' '+m[2])||{name:m[1],version:m[2],ecosystem:'',severity:i.severity,count:0,unfixed:0,fixed:null,by_severity:{}};
    p.count++;p.by_severity[SEVS.includes(i.severity)?i.severity:'UNKNOWN']=(p.by_severity[SEVS.includes(i.severity)?i.severity:'UNKNOWN']||0)+1;
    if(!i.fixed)p.unfixed++;else if(!p.fixed||newer(i.fixed,p.fixed))p.fixed=i.fixed;
    by.set(m[1]+' '+m[2],p)}
  return {list:[...by.values()],complete:q.items.length>=q.count};
}
// how the vulnerabilities were found, in one sentence
function method(d){
  const q=d.vulns;
  if(d.ecosystem==='docker'){
    const kinds=[...new Set((q.packages||[]).map(p=>innerKind(p.ecosystem)))];
    return `Found by <a href="https://github.com/google/osv-scanner" target="_blank" rel="noopener">osv-scanner</a>: it pulled <code>${esc(d.name)}:${esc(d.version)}</code>${d.resolved?` (version ${esc(d.resolved)} today)`:''} anonymously and read the packages installed inside it${kinds.length?` (${esc(kinds.join(', '))})`:''}, then matched them against OSV. Nothing in the image was run. The image itself has no version to fix: each fix is a newer version of a package inside it, which a newer image tag usually includes.`;
  }
  if(d.ecosystem==='githubAction')return `Found in the <a href="https://github.com/advisories?query=ecosystem%3Aactions" target="_blank" rel="noopener">GitHub Advisory Database</a> for release <code>${esc(q.checked_version)}</code>${q.checked_version!==d.version?`, the release <code>${esc(d.version)}</code> points to today`:''}.`;
  return `Found on <a href="https://osv.dev" target="_blank" rel="noopener">OSV.dev</a> for version <code>${esc(q.checked_version)}</code>${d.installed?', the version the lockfile installs':q.exact?'':`, the lowest version <code>${esc(d.version)}</code> allows (the installed one may be newer)`}.`;
}

/* ---- the findings card ---- */
function advisoryTable(d,q){
  const rows=q.items.map(i=>{
    // image findings name the package inside the image in their summary ("glibc 2.36-9: ..."); a package's own findings are about itself
    const m=d.ecosystem==='docker'&&/^(\S+) (\S+): (.*)$/.exec(i.summary||'');
    const pkg=m?`${esc(m[1])} <span class="muted">${esc(m[2])}</span>`:`${esc(displayName(d))} <span class="muted">${esc(q.checked_version||d.version)}</span>`;
    return `<tr><td><a href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.cve||i.id)}</a>${i.cve&&i.id!==i.cve?`<div class="sub">${esc(i.id)}</div>`:''}</td><td>${sevBadge(i.severity)}</td><td>${pkg}</td><td>${i.fixed?`<code>${esc(i.fixed)}</code>`:'<span class="bad">no fix</span>'}</td><td>${esc(m?m[3]:i.summary)}</td></tr>`}).join('');
  return `<table><thead><tr><th class="c-adv">Advisory</th><th class="c-sev">Severity</th><th class="c-pkg">${d.ecosystem==='docker'?'Package inside, installed version':'Package, version checked'}</th><th class="c-fix">Fixed in</th><th class="c-sum">Summary</th></tr></thead><tbody>${rows}</tbody></table>${q.count>q.items.length?`<p class="sub">The ${q.items.length} most severe of ${q.count} are listed.</p>`:''}`;
}
function openCard(d){
  const q=d.vulns;if(!q)return;
  const at=d.resolved||(q.checked_version&&q.checked_version!==d.version?q.checked_version:'');
  const n=sevCounts(q),img=d.ecosystem==='docker';
  $('vc-title').textContent=`${displayName(d)} ${d.version}${at?` (${at})`:''}`;
  const fixable=q.fixable!=null?q.fixable:q.items.filter(i=>i.fixed).length;
  const versions=img?`Current tag <code>${esc(d.version)}</code>${d.resolved?` (${esc(d.resolved)})`:''} · Latest tag ${d.latest?`<code>${esc(d.latest)}</code>`:'<span class="muted">none known</span>'}`
    :`Current <code>${esc(q.checked_version||d.version)}</code> · Latest ${d.latest?`<code>${esc(d.latest)}</code>`:'<span class="muted">not known</span>'} · ${q.fixed_in?`Fixes every fixable one: <code>${esc(q.fixed_in)}</code>`:'<span class="bad">No fixed version released</span>'}`;
  $('vc-sub').innerHTML=`${esc(d.name)} · ${versions}<br><strong>${q.count}</strong> known ${q.count===1?'vulnerability':'vulnerabilities'}${n?' '+sevChips(n):` · worst ${esc(SEVNAME[q.severity]||q.severity)}`} · ${fixable} fixable${q.unfixed?`, ${q.unfixed} with no fix released`:''}<div class="method">${method(d)}</div>`;
  let body='';
  if(img){
    const {list,complete}=innerPackages(q);
    body+=`<h3 class="card-h">Packages inside the image with vulnerabilities${list.length?` (${list.length}${complete?'':' or more'})`:''}</h3>`
      +(list.length?`<table class="inner"><thead><tr><th class="c-ipkg">Package</th><th class="c-ikind">Kind</th><th class="c-icur">Installed now</th><th class="c-ifix">Fixed in</th><th class="c-isev">Advisories</th></tr></thead><tbody>`
        +list.map(p=>`<tr><td><strong>${esc(p.name)}</strong></td><td>${esc(innerKind(p.ecosystem))}</td><td><code>${esc(p.version)}</code></td><td>${p.fixed?`<code>${esc(p.fixed)}</code>${p.unfixed?`<div class="sub">${p.unfixed} with no fix</div>`:''}`:'<span class="bad">no fix released</span>'}</td><td>${p.count} ${sevChips(p.by_severity||{})}</td></tr>`).join('')
        +`</tbody></table>${complete?'':`<p class="sub">From the ${q.items.length} most severe advisories listed; the next refresh lists every affected package.</p>`}`:'<p class="sub">The advisories do not name their packages.</p>')
      +`<h3 class="card-h">Advisories</h3>`;
  }
  $('vc-body').innerHTML=body+advisoryTable(d,q);
  $('vuln-card').showModal();
}

/* ---- table cells ---- */
function vulnCell(d){
  const q=d.vulns;
  if(local(d))return NA('An action in this repository, not a published package');
  if(!q&&missingCell(d,'vulns'))return missingCell(d,'vulns');
  if(!q)return NIL(d.ecosystem==='docker'?'Not scanned: the tag is an unresolved ${VAR}, the image could not be pulled anonymously (private, or built locally), or the scan failed':d.ecosystem==='githubAction'?'Not checked: pinned to a branch or a commit no release tag points at, or the GitHub lookup failed':LOOKED.includes(d.ecosystem)?'Not checked: the version is not exact or the lookup failed':'Not checked: vulnerability lookup does not cover this ecosystem yet');
  if(!q.count)return '<span class="good">None known</span>';
  const n=sevCounts(q),img=d.ecosystem==='docker';
  const where=img?` <span class="sub">${q.packages?`in ${q.packages.length} ${q.packages.length===1?'package':'packages'} inside the image`:'inside the image'}</span>`:'';
  const note=q.exact===false?`<div class="sub">Checked at ${esc(q.checked_version)}, the lowest version the range allows</div>`:'';
  return `<span class="${SEVCLASS[q.severity]||'warn'} vcount">${q.count} known</span>${where}<div>${n?sevChips(n):`<span class="sub">worst ${esc(SEVNAME[q.severity]||q.severity)}; breakdown after the next refresh</span>`}</div>${note}`;
}
function fixCell(d){
  const q=d.vulns;
  if(local(d))return NA('No vulnerabilities to fix');
  if(!q)return NA(missingCell(d,'vulns')?'Nothing was checked, so there is nothing to fix':'No known vulnerabilities to fix');
  if(!q.count)return NA('No known vulnerabilities to fix');
  if(d.ecosystem==='docker'){
    const p=q.packages;
    return (q.fixable?`<span class="warn" title="Fixed in newer versions of the packages inside the image; a newer image tag usually includes them">${q.fixable} of ${q.count} fixable</span>`:'<span class="bad">No fix released</span>')
      +(p?`<div class="sub">${p.filter(x=>x.fixed).length} of ${p.length} packages have a fix</div>`:q.fixable&&q.unfixed?`<div class="sub">${q.unfixed} with no fix released</div>`:'');
  }
  return q.fixed_in?`<code>${esc(q.fixed_in)}</code>${q.unfixed?`<div class="sub">${q.unfixed} more with no fix released</div>`:''}`:'<span class="bad">No fix released</span>';
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
  return `<span class="lic risk risk-${r}" title="${esc(RISK[r]+'.'+several)}"><span class="dot" aria-hidden="true"></span>${esc(d.license)}</span>${d.license_of==='latest'?' <span class="sub" title="Listed version not on deps.dev; license of the latest release">(latest)</span>':''}${d.license_of==='source'&&d.ecosystem!=='docker'?' <span class="sub" title="The registry states no license; this is the license of the package\'s source repository">(source repo)</span>':''}${d.license_of==='github'?' <span class="sub" title="deps.dev could not name this license (non-standard); this is GitHub\'s own license detection for the package\'s source repository">(GitHub detection)</span>':''}${d.license_of==='wheel'?' <span class="sub" title="Not on PyPI: installed from a wheel file; this is the license the wheel\'s own metadata states">(wheel metadata)</span>':''}${d.license_of==='pypi'?' <span class="sub" title="deps.dev and GitHub could not name this license; this is the license PyPI\'s own metadata states">(PyPI metadata)</span>':''}${d.license_of==='repository'?' <span class="sub" title="This is the repository\'s own image, built from its Dockerfile: the repository\'s license">(this repository)</span>':''}${d.license_of==='repo'?` <span class="sub" title="${esc('License of '+(d.license_from||'the GitHub repository')+', this image\'s source repository (named in config/dependencies.json image_sources, or the GitHub repository of the same name for a ghcr.io image), read from its license file; at a version, the file at that release tag')}">(source repo)</span>`:''}${d.license_of==='package'?` <span class="sub" title="${esc((d.license_from||'').includes(' + ')?'Licenses of the program inside the image ('+d.license_from.split(' + ')[0]+') and of the image\'s own repository ('+d.license_from.split(' + ')[1]+'): both apply':'License of the image\'s own program inside it: '+(d.license_from||'its main package'))}">(main package${(d.license_from||'').includes(' + ')?' + repo':''})</span>`:''}${d.license_of==='label'?' <span class="sub" title="From the image\'s own license label (org.opencontainers.image.licenses): declared by whoever published the image, not verified">(image label)</span>':d.license_of==='source'&&d.ecosystem==='docker'?' <span class="sub" title="The image has no license label; this is the license of the GitHub repository its source label names">(source repo)</span>':''}<span class="sr"> (${esc(RISK[r])})</span>`;
}
function latestCell(d){
  return updateOf(d)==='behind'?`<span class="warn">${esc(d.latest)}</span>`:d.latest?esc(d.latest):missingCell(d,'latest')?missingCell(d,'latest'):d.latest_of==='floating'?NA('A floating tag such as latest always points at the newest image'):local(d)?NA('An action in this repository has no releases'):NIL('Latest version not looked up for this ecosystem yet');
}
function nameCell(d,single){
  const href=(LINK[d.ecosystem]||(()=>null))(d.name);
  const short=displayName(d),full=short===d.name?'':` title="${esc(d.name)}"`;
  const name=href?`<a class="pkg" href="${esc(href)}"${full} target="_blank" rel="noopener">${esc(short)}</a>`:`<span class="pkg"${full}>${esc(short)}</span>`;
  const archived=d.archived?` <span class="tag tag-archived" title="${esc('Its source repository'+(d.project?' ('+d.project+')':'')+' is archived on GitHub: read-only, no longer maintained')}">archived</span>`:'';
  const rs=((opts.repos().find(r=>r.repository===d.repository))||{}).stars;
  return `${name}${archived}${starChip(d.stars,d.stars_of)}${single?'':`<div class="sub">${esc(d.repository)}${starChip(rs,'github.com/'+(opts.org()||'')+'/'+d.repository)}</div>`}`;
}
// both vulnerability cells open the findings card
const opener=(d,i,c)=>d.vulns&&d.vulns.count?`<button type="button" class="fix-open" data-i="${i}" aria-haspopup="dialog">${c}<span class="open-hint">Details</span></button>`:c;
const groupsSub=d=>d.groups&&d.groups.length?`<div class="sub" title="${esc((d.sources||[]).join(', ')||'Declared in')}">${d.groups.map(esc).join(' · ')}</div>`:'';
function rowClass(d){const rk=riskOf(d);return rk==='red'||rk==='yellow'?` class="row-risk-${rk}"`:''}   // licenses to avoid or use with care stand out
function row(d,single,i){
  return `<tr${rowClass(d)}><td>${nameCell(d,single)}</td><td data-label="Ecosystem"${kindTitle(d)}>${esc(ECO[ecoOf(d)]||ecoOf(d))}${d.ecosystem==='docker'?`<div class="sub" title="Container image from this registry">image · ${esc(image(d.name).registry)}</div>`:''}</td><td data-label="Current version"><code>${esc(d.version)}</code>${d.installed?`<div class="sub" title="The version the lockfile installs; vulnerabilities are checked at this version">installed ${esc(d.installed)}</div>`:''}${groupsSub(d)}${d.resolved?`<div class="sub" title="The version this tag points to today">${esc(d.resolved)}</div>`:''}</td><td data-label="Latest">${latestCell(d)}</td><td data-label="License">${licCell(d)}</td><td data-label="Vulnerabilities">${opener(d,i,vulnCell(d))}</td><td data-label="Fixed in">${opener(d,i,fixCell(d))}</td></tr>`;
}
// an image: its tag now and what it points to, the newest tag, and the vulnerabilities of the packages inside it
function imageRow(d,single,i){
  return `<tr${rowClass(d)}><td>${nameCell(d,single)}<div class="sub"${kindTitle(d)}>${esc(ECO[ecoOf(d)]||ecoOf(d))}</div></td><td data-label="Current tag"><code>${esc(d.version)}</code>${d.resolved?`<div class="sub" title="The version this tag points to today">version ${esc(d.resolved)}</div>`:''}${groupsSub(d)}</td><td data-label="Latest tag">${latestCell(d)}</td><td data-label="License">${licCell(d)}</td><td data-label="Vulnerabilities inside the image">${opener(d,i,vulnCell(d))}</td><td data-label="Fixable">${opener(d,i,fixCell(d))}</td></tr>`;
}
const HEAD='<tr><th scope="col">Package</th><th scope="col">Ecosystem</th><th scope="col">Current version</th><th scope="col">Latest</th><th scope="col">License</th><th scope="col">Vulnerabilities</th><th scope="col">Fixed in</th></tr>';
const IMAGE_HEAD='<tr><th scope="col">Image</th><th scope="col">Current tag</th><th scope="col">Latest tag</th><th scope="col">License</th><th scope="col">Vulnerabilities inside the image</th><th scope="col">Fixable</th></tr>';

// Row order: the Sort by menu, kept in ?dsort=. Rows without stars, or not checked for vulnerabilities, go last.
const cmpVec=(a,b)=>{for(let i=0;i<Math.max(a.length,b.length);i++){const d=(b[i]??-1)-(a[i]??-1);if(d)return d}return 0};
const SORTS={
  repo:(a,b)=>a.repository.localeCompare(b.repository)||a.name.localeCompare(b.name),
  name:(a,b)=>displayName(a).localeCompare(displayName(b),undefined,{sensitivity:'base'})||a.repository.localeCompare(b.repository),
  severe:(a,b)=>cmpVec(sevVector(a),sevVector(b))||SORTS.repo(a,b),
  vulns:(a,b)=>((b.vulns||{}).count??-1)-((a.vulns||{}).count??-1)||SORTS.repo(a,b),
  unfixed:(a,b)=>((b.vulns||{}).unfixed??-1)-((a.vulns||{}).unfixed??-1)||SORTS.severe(a,b),
  stars:(a,b)=>(Number.isFinite(b.stars)?b.stars:-1)-(Number.isFinite(a.stars)?a.stars:-1)||displayName(a).localeCompare(displayName(b)),
  stars_least:(a,b)=>(Number.isFinite(a.stars)?a.stars:Infinity)-(Number.isFinite(b.stars)?b.stars:Infinity)||displayName(a).localeCompare(displayName(b)),   // no stars still last
};
let sortBy='repo';
function setUrl(k,v,dflt){const q=new URLSearchParams(location.search);v===dflt?q.delete(k):q.set(k,v);try{history.replaceState(null,'',q.toString()?'?'+q:location.pathname)}catch(_){}}

const plural=(n,one,many)=>`${n} ${n===1?one:many}`;
// one KPI card: value is text, sub trusted HTML built from numbers and esc()'d names
const card=(label,value,sub,tone='')=>`<div class="kpi"><div class="kpi-label">${esc(label)}</div><div class="kpi-value${tone?' '+tone:''}">${esc(value)}</div><div class="kpi-sub">${sub}</div></div>`;
// advisories of each severity over many dependencies, and whether every one of them had full counts
function totals(vul){
  const tot={};let full=true;
  vul.forEach(d=>{const n=sevCounts(d.vulns);if(!n)full=false;SEVS.forEach(k=>tot[k]=(tot[k]||0)+((n||{})[k]||0))});
  return {tot,full};
}
function kpis(list){
  const vul=list.filter(d=>d.vulns&&d.vulns.count),{tot,full}=totals(vul);
  const adv=vul.reduce((s,d)=>s+d.vulns.count,0),nofix=vul.reduce((s,d)=>s+(d.vulns.unfixed||0),0),nofixDeps=vul.filter(d=>d.vulns.unfixed).length;
  const unchecked=list.filter(d=>!d.vulns&&!local(d)).length;
  $('kpi-deps').innerHTML=list.length?[
    card('Dependencies',list.length.toLocaleString(),`${plural(new Set(list.map(d=>d.repository)).size,'repository','repositories')}${unchecked?` · ${unchecked} not checked`:''}`),
    card('Known vulnerabilities',adv.toLocaleString(),`${full?sevChips(tot):'Breakdown by severity after the next refresh'}<div>in ${plural(vul.length,'dependency','dependencies')}</div>`,adv?'bad':'good'),
    card('Fixable',(adv-nofix).toLocaleString(),`a newer version fixes them${adv?` · ${Math.round((adv-nofix)/adv*100)}%`:''}`,adv-nofix?'warn':''),
    card('No fix released',nofix.toLocaleString(),`in ${plural(nofixDeps,'dependency','dependencies')}; no newer version fixes them yet`,nofix?'bad':''),
  ].join(''):'';
}
function kindTabs(visible){
  const n={all:visible.length};visible.forEach(d=>{const k=kindOf(d);n[k]=(n[k]||0)+1});
  const has=new Set(all.map(kindOf));
  $('dep-kinds').innerHTML=KINDS.filter(([k])=>k==='all'||has.has(k)).map(([k,label])=>`<button type="button" role="tab" data-kind="${k}" aria-selected="${k===kind}" tabindex="${k===kind?0:-1}">${esc(label)} <span class="count">${n[k]||0}</span></button>`).join('');
}
function render(visible){
  kindTabs(visible);
  const list=visible.filter(d=>kind==='all'||kindOf(d)===kind).sort(SORTS[sortBy]);
  const names=[...new Set(list.map(d=>d.repository))],single=opts.repos().length===1?opts.repos()[0].repository:null;
  const count=f=>list.filter(f).length,looked=list.filter(d=>LOOKED.includes(d.ecosystem)&&!local(d));
  const nv=count(d=>d.vulns&&d.vulns.count),unchecked=count(d=>!d.vulns),down=looked.length>0&&looked.every(d=>!d.vulns);
  const cls={};list.forEach(d=>{const r=riskOf(d);if(r!=='na')cls[r]=(cls[r]||0)+1});
  const risk=['red','yellow','green','unclassified','none'].filter(k=>cls[k]).map(k=>`<span class="risk risk-${k}"><span class="dot" aria-hidden="true"></span>${RISK[k]} <strong>${cls[k]}</strong></span>`).join(' · ');
  $('dep-title').textContent=single?`${single} dependencies`:'All dependencies';
  $('dep-summary').innerHTML=`${KIND_NOTE[kind]} <strong>${list.length}</strong> ${list.length===1?'dependency':'dependencies'}${single?'':` in <strong>${names.length}</strong> ${names.length===1?'repository':'repositories'}`}. `
    +(down?'<strong class="warn">Vulnerability data is unavailable right now</strong> (the lookup failed; this is not a clean result). '
      :nv?`<strong class="bad">${nv}</strong> with known vulnerabilities. `:unchecked===list.length&&list.length?'':'No known vulnerabilities. ')
    +(unchecked&&!down?`${unchecked} not checked (unresolved or private images, local actions, unpinned versions). `:'')
    +(risk?`<br>License risk: ${risk}`:'');
  const meta=single&&opts.repos()[0],view=opts.view();
  $('dep-note').innerHTML=!meta?`On the ${view==='main'?'default':'development'} branch, as chosen above. The repository filters above apply here too.`:`Branch <code>${esc(meta.branch)}</code>${view==='dev'&&meta.branch_source==='default'?' <span class="muted" title="No branch matched the development pattern in config/repos.json">(default branch; no development branch found)</span>':''} · Repository license: ${meta.license?`<span class="lic risk risk-${meta.license_class||'unclassified'}"><span class="dot" aria-hidden="true"></span>${esc(meta.license)}</span>`:meta.license_class?`<span class="lic risk risk-${esc(meta.license_class)}"><span class="dot" aria-hidden="true"></span>No LICENSE file</span>`:'<span class="lic none">No LICENSE file</span>'}`;
  kpis(list);
  current=list;
  const img=IMAGE_KINDS.includes(kind),cols=img?6:7;
  $('dep-head').innerHTML=img?IMAGE_HEAD:HEAD;
  $('dep-table').classList.toggle('images',img);
  shown=list;const page=pager.slice(list),at=pager.offset();
  $('dep-rows').innerHTML=list.length?page.map((d,i)=>(img?imageRow:row)(d,single,at+i)).join(''):`<tr><td colspan="${cols}" class="empty">${all.length?'No dependencies match these filters.':'No dependencies found.'}</td></tr>`;
}
function renderPolicy(){
  const any=['green','yellow','red'].some(k=>(policy[k]||[]).length);
  $('policy').innerHTML=any?`<ul class="policy">${['green','yellow','red'].map(k=>`<li><span class="risk risk-${k}"><span class="dot" aria-hidden="true"></span><b>${RISK[k]}</b></span> ${(policy[k]||[]).length?(policy[k]).map(x=>`<code>${esc(x)}</code>`).join(' '):'<span class="muted">none listed</span>'}</li>`).join('')}${policy.no_license?`<li><span class="risk risk-${esc(policy.no_license)}"><span class="dot" aria-hidden="true"></span><b>${esc(RISK[policy.no_license])}</b></span> also: <i>no license</i> (nothing states one; a failed lookup is not counted)</li>`:''}</ul>`
    :'<p class="muted" style="margin:0 0 14px">No license policy yet. Add SPDX ids or patterns (such as <code>GPL-*</code>) under <code>licenses.green</code> (Preferred), <code>yellow</code> (Not recommended) and <code>red</code> (Restricted use) in <code>config/repos.json</code>; licenses on no list show as unclassified.</p>';
}
// each license list's name with its colour, e.g. Restricted use (red); the names come from licenses.labels
const withColour=l=>Object.fromEntries(Object.entries(l||{}).filter(([k])=>['green','yellow','red'].includes(k)).map(([k,v])=>[k,`${v} (${k})`]));
const load=()=>opts.repos().flatMap(r=>(r.dependencies||[]).map(d=>({...d,repository:r.repository}))).sort((a,b)=>a.repository.localeCompare(b.repository)||a.name.localeCompare(b.name));

/* o: { repos() -> the repository records shown (branch and page filters applied), view() -> 'dev' | 'main', org() -> organization,
 *      policy, ecosystems } */
function init(o){
  opts=o;policy=o.policy||policy;
  Object.assign(RISK,withColour(policy.labels));Object.assign(ECO,o.ecosystems||{});
  const q=new URLSearchParams(location.search);
  kind=KINDS.some(([k])=>k===q.get('kind'))?q.get('kind'):'packages';
  sortBy=SORTS[q.get('dsort')]?q.get('dsort'):'repo';$('dep-sort').value=sortBy;
  renderPolicy();
  all=load();
  pager=Pager.createPager($('dep-pager'),{size:50,param:'dper',onChange:()=>render(bar.visible())});
  bar=Filters.createFilterBar($('dep-filters'),{facets:FACETS,items:all,noun:'dependencies',text:{param:'dq',placeholder:'Find a package or license',of:d=>d.name+' '+(d.license||'')},onChange:list=>{pager.reset();render(list)}});
  render(bar.visible());
  $('dep-sort').addEventListener('change',e=>{sortBy=SORTS[e.target.value]?e.target.value:'repo';setUrl('dsort',sortBy,'repo');pager.reset();render(bar.visible())});
  $('dep-kinds').addEventListener('click',e=>{const t=e.target.closest('[data-kind]');if(!t)return;kind=t.dataset.kind;setUrl('kind',kind,'packages');pager.reset();render(bar.visible());$('dep-kinds').querySelector(`[data-kind="${kind}"]`).focus()});
  $('dep-kinds').addEventListener('keydown',e=>{
    const ks=[...$('dep-kinds').querySelectorAll('[data-kind]')].map(t=>t.dataset.kind),i=ks.indexOf(kind);
    const j=e.key==='ArrowRight'?(i+1)%ks.length:e.key==='ArrowLeft'?(i+ks.length-1)%ks.length:-1;
    if(j<0)return;e.preventDefault();kind=ks[j];setUrl('kind',kind,'packages');pager.reset();render(bar.visible());$('dep-kinds').querySelector(`[data-kind="${kind}"]`).focus();
  });
  $('dep-rows').addEventListener('click',e=>{const b=e.target.closest('.fix-open');if(b)openCard(shown[+b.dataset.i])});
  $('vc-close').addEventListener('click',()=>$('vuln-card').close());
  $('vuln-card').addEventListener('click',e=>{if(e.target===e.currentTarget)$('vuln-card').close()});   // a click on the backdrop
}
function refresh(){if(bar){all=load();bar.setItems(all)}}   // re-renders through the filter bar, which keeps the filters
const exportRows=()=>({kind:(KINDS.find(([k])=>k===kind)||[])[1],rows:current});

// shared with the Vulnerabilities tab (assets/vulns.js)
const lib={init,refresh,exportRows,sevCounts,kindOf,innerKind,sevChips,sevBadge,KINDS,SEVS,SEVNAME,ECO,ecoOf,displayName,image,load:()=>opts?load():[]};
root.Deps=lib;
})(window);
