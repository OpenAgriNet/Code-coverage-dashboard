let data={repositories:[],main:[],releases:[]},view=Branches.initial();   // dev or main, shared with deps.html (assets/branches.js)
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const isNum=v=>v!=null&&v!==''&&Number.isFinite(Number(v));
const num=v=>Number(v).toLocaleString();
const day=v=>{if(!v)return '';const d=new Date(v);return isNaN(d)?'':d.toLocaleDateString(undefined,{day:'numeric',month:'short',year:'numeric'})};
const repoUrl=r=>r.html_url||`https://github.com/OpenAgriNet/${r.repository}`;
// GitHub stars of a tracked repo, from data/stack.json once it has loaded
const repoStars=name=>{const r=((stack&&stack.repositories)||[]).find(x=>x.repository===name);return r?r.stars:null};
const starCount=n=>!Number.isFinite(n)||n<0?'':n>=1e6?(n/1e6).toFixed(1).replace(/\.0$/,'')+'M':n>=1e4?Math.round(n/1e3)+'k':n>=1e3?(n/1e3).toFixed(1).replace(/\.0$/,'')+'k':String(n);
// GitHub's star octicon (MIT, primer/octicons)
const STAR='<svg class="star-icon" viewBox="0 0 16 16" width="12" height="12" aria-hidden="true"><path d="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Zm0 2.445L6.615 5.5a.75.75 0 0 1-.564.41l-3.097.45 2.24 2.184a.75.75 0 0 1 .216.664l-.528 3.084 2.769-1.456a.75.75 0 0 1 .698 0l2.77 1.456-.53-3.084a.75.75 0 0 1 .216-.664l2.24-2.183-3.096-.45a.75.75 0 0 1-.564-.41L8 2.694Z"/></svg>';
const starChip=name=>{const n=repoStars(name);return !Number.isFinite(n)?'':`<span class="stars" title="${esc(n.toLocaleString())} stars on GitHub">${STAR}${starCount(n)}<span class="sr"> stars</span></span> `};
const tagChips=r=>starChip(r.repository)+(r.tags||(r.dpg?['DPG']:[])).map(g=>`<span class="tag"${g==='DPG'?' title="Part of the OpenAgriNet DPG project"':''}>${esc(g)}</span>`).join(' ');
const STALE_DAYS=14;
document.addEventListener('error',e=>{const i=e.target;if(i.tagName==='IMG'&&i.dataset.fallback){const t=document.createElement('span');t.className='fallback';t.textContent=i.dataset.fallback;i.replaceWith(t)}},true);
const SEC={passing:'Passing',failing:'Failing','no runs':'No runs on this branch','no workflow':'No security workflow','branch not found':'Branch not found'};

function row(r,picker){
  const url=repoUrl(r),cd=r.coverage_detail||{},s=r.security||{},what=r.ref_kind==='tag'?'tag':'branch';
  const age=r.measured_at?Math.floor((Date.now()-new Date(r.measured_at))/864e5):null;
  const measured=day(r.measured_at)?`<div class="sub${age>STALE_DAYS?' stale':''}">Measured ${esc(day(r.measured_at))}${age>STALE_DAYS?` (${age} days ago)`:''}</div>`:'';
  const cov=r.branch_exists===false?'<span class="muted">Branch not found</span>'
    :!isNum(r.coverage)?`<span class="muted">${esc(r.coverage_badge_url?`No report on this ${what}`:(r.coverage_source||'Unknown'))}</span>`
    :`<a class="badge" href="${esc(cd.report_url||url)}" target="_blank" rel="noopener">${r.coverage_badge_url?`<img src="${esc(r.coverage_badge_url)}" data-fallback="${(+r.coverage).toFixed(2)}%" alt="Coverage ${(+r.coverage).toFixed(2)}%">`:`<span class="pct">${(+r.coverage).toFixed(2)}%</span>`}</a>`
     +(cd.lines?`<div class="sub">${num(cd.hits)} of ${num(cd.lines)} lines covered</div>`:'')+measured;
  const label=s.state==='no runs'?`No runs on this ${what}`:SEC[s.state]||'Unknown';
  const sec=(s.badge_url&&s.state!=='no runs'
    ?`<a class="badge" href="${esc(s.run_url||url+'/actions')}" target="_blank" rel="noopener"><img src="${esc(s.badge_url)}" data-fallback="${esc(label)}" alt="Security ${esc(label)}"></a>`
    :(s.run_url&&(s.state==='passing'||s.state==='failing')
      ?`<a class="pct ${s.state==='passing'?'good':'bad'}" href="${esc(s.run_url)}" target="_blank" rel="noopener">${esc(label)}</a>`
      :`<span class="muted">${esc(label)}</span>`))
    +(day(s.finished_at)?`<div class="sub">Last run ${esc(day(s.finished_at))}</div>`:'');
  return `<tr><td><a class="repo" href="${esc(url)}/tree/${esc(r.branch)}" target="_blank" rel="noopener">${esc(r.repository)}</a> ${tagChips(r)}${picker||`<div class="sub">${esc(r.branch)}${devDefault(r)}</div>`}</td><td data-label="Code coverage">${cov}</td><td data-label="Security">${sec}</td></tr>`;
}
const picked={};let relAll='',relSet='',relAllowed=null,relBar=null,bar=null,visibleSet=null;
const devDefault=r=>view==='dev'&&r.branch_source==='default'&&r.ref_kind!=='tag'?' <span title="No branch matched the development pattern in config/repos.json, so the default branch is shown">· default branch</span>':'';
const pool=g=>relSet?g.versions:gv(g);   // a named release ignores the Found as / Stability filters: it names its versions itself
const curSet=()=>(data.release_sets||[]).find(s=>s.alias===relSet);
const setEntry=g=>{const s=curSet();const e=s&&Object.entries(s.repos).find(([k])=>k.toLowerCase()===g.repository.toLowerCase());return e&&e[1]};
function setUrl(k,v){const q=new URLSearchParams(location.search);v?q.set(k,v):q.delete(k);try{history.replaceState(null,'',q.toString()?'?'+q:location.pathname)}catch(_){}}
function fillRelSet(){
  const sets=data.release_sets||[],sel=$('rel-set');
  $('rel-set').hidden=$('rel-set-label').hidden=!sets.length;
  sel.innerHTML='<option value="">Each repo\'s latest</option>'+sets.map(s=>`<option value="${esc(s.alias)}">${esc(s.label)}${s.current?' (current)':''}</option>`).join('');
  sel.value=sets.some(s=>s.alias===relSet)?relSet:'';relSet=sel.value;
}
function initRelSet(){
  const sets=data.release_sets||[],q=new URLSearchParams(location.search),p=q.get('set'),cur=sets.find(s=>s.current);
  relSet=p===null?(q.get('ver')?'':cur?cur.alias:''):p==='latest'?'':p;
  fillRelSet();$('rel-all').disabled=!!relSet;
}
const shown=r=>!visibleSet||visibleSet.has(r.repository);
const vkey=(g,v)=>g.repository+'@'+v.version;
const gv=g=>relAllowed?g.versions.filter(v=>relAllowed.has(vkey(g,v))):g.versions;
const latestOf=g=>gv(g).find(v=>!v.prerelease)||gv(g)[0];
const verCmp=(a,b)=>{const p=v=>{const[n,...r]=v.split('-');return[n.split('.').map(Number),r.join('-')]},[an,ap]=p(a),[bn,bp]=p(b);
  for(let i=0;i<Math.max(an.length,bn.length);i++){const d=(an[i]||0)-(bn[i]||0);if(d)return d}
  return(ap?0:1)-(bp?0:1)||ap.localeCompare(bp,undefined,{numeric:true})};
function fillRelAll(){
  const sel=$('rel-all'),all=[...new Set((data.releases||[]).flatMap(g=>gv(g).map(v=>v.version)))].sort(verCmp).reverse();
  sel.innerHTML='<option value="">Latest</option>'+all.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('');sel.value=all.includes(relAll)?relAll:'';relAll=sel.value;
}
const KIND={branch:'release branch',tag:'tag',release:'GitHub Release'};
function relPick(g){
  const by=x=>pool(g).find(v=>v.version===x);
  if(picked[g.repository])return by(picked[g.repository])||null;
  if(relSet){const m=setEntry(g);return m&&m.version?by(m.version)||null:null}
  return relAll?by(relAll)||null:latestOf(g);
}
function missingText(g){
  if(picked[g.repository]||!relSet)return `This repository has no ${esc(picked[g.repository]||relAll)} version.`;
  const m=setEntry(g),s=curSet();
  return m?`Tag <code>${esc(m.tag)}</code> is not among this repository's versions (not a version name, or older than <code>releases.max_versions</code>).`:`Not part of ${esc(s.label)}.`;
}
function relRow(g){
  const v=relPick(g),id='ver-'+g.repository.replace(/[^\w-]/g,'_'),want=picked[g.repository]||relAll;
  const gone=v?'':`<option value="" selected disabled>${relSet&&!picked[g.repository]?'Not in this release':'No '+esc(want)}</option>`;
  const opts=gone+pool(g).map(x=>`<option value="${esc(x.version)}"${x===v?' selected':''}>${esc(x.version)}${x.prerelease?' (pre-release)':''}${x===latestOf(g)?' · latest':''}</option>`).join('');
  if(!v)return `<tr><td><a class="repo" href="${esc(g.html_url)}" target="_blank" rel="noopener">${esc(g.repository)}</a> ${tagChips(g)}<div><label class="sr" for="${id}">Version of ${esc(g.repository)}</label><select class="ver" id="${id}" data-repo="${esc(g.repository)}">${opts}</select></div></td><td colspan="2" data-label="Code coverage" class="muted">${missingText(g)}</td></tr>`;
  const more=g.not_measured>0?`<div class="sub">${g.not_measured} older ${g.not_measured===1?'version is':'versions are'} not shown (<code>releases.max_versions</code>).</div>`:'';
  const how=`${v.kinds.map(k=>KIND[k]).join(' + ')} · <code>${esc(v.branch)}</code>${day(v.published_at)?` · ${esc(day(v.published_at))}`:''}`;
  return row({...v,repository:g.repository,html_url:g.html_url,tags:g.tags,dpg:g.dpg},
    `<div><label class="sr" for="${id}">Version of ${esc(g.repository)}</label><select class="ver" id="${id}" data-repo="${esc(g.repository)}">${opts}</select></div><div class="sub">${how}</div>${more}`);
}
const lastShown={};   // the rows each table shows, for its Excel button
function fill(id,list,empty,render1=row){
  const cv=r=>r.versions?0:isNum(r.coverage)?+r.coverage:-1;  // release rows keep name order so a row does not jump while its version is changed
  const a=list.filter(shown).sort((x,y)=>cv(y)-cv(x)||x.repository.localeCompare(y.repository));lastShown[id]=a;
  $(id).innerHTML=a.length?a.map(x=>render1(x)).join(''):`<tr><td colspan="3" class="empty">${visibleSet&&list.length?'No repositories match these filters.':empty}</td></tr>`;
}
const viewList=()=>(view==='main'?data.main:Branches.devOnly(data.repositories))||[];   // Development: only repos whose development branch was found
function summary(){
  const all=viewList().filter(shown),has=all.filter(r=>isNum(r.coverage)).length,st=k=>all.filter(r=>(r.security||{}).state===k).length,pass=st('passing'),fail=st('failing');
  $('summary').innerHTML=all.length?`On their ${view==='main'?'main':'development'} branches, <strong>${has} of ${all.length}</strong> ${visibleSet?'matching ':''}repositories report coverage. Security: <strong>${pass}</strong> passing, <strong class="${fail?'bad':''}">${fail}</strong> failing.`:'No repositories are configured yet.';
}
function setView(v){
  view=v;Branches.remember(v);Branches.paint(v,data.repositories,data.main);
  $('stack-note').innerHTML=`On the ${v==='main'?'default':'development'} branch, as chosen above. <a href="deps.html?branch=${v}">All dependencies →</a>`;
  if(bar)bar.setItems(repoItems());else{summary();render()}
}
let stack=null;
// each license list's name with its colour, e.g. Restricted use (red); the names come from licenses.labels
const withColour=l=>Object.fromEntries(Object.entries(l||{}).filter(([k])=>['green','yellow','red'].includes(k)).map(([k,v])=>[k,`${v} (${k})`]));
// a local action (./.github/actions/x) is not a published package and has no license to find
const licensable=d=>!(d.ecosystem==='githubAction'&&d.name.startsWith('./'));
function stackRow(r){
  const url=repoUrl(r),deps=r.dependencies||[],langs=(r.languages||[]).slice(0,3).map(l=>l[0]).join(' · '),techs=r.techs||[];
  const lic=r.license?`<span class="lic risk risk-${esc(r.license_class||'unclassified')}" title="${esc(RISK[r.license_class||'unclassified'])}"><span class="dot" aria-hidden="true"></span>${esc(r.license)}</span><span class="sr"> (${esc(RISK[r.license_class||'unclassified'])})</span>`   // a class here is the policy's no_license class
    :r.license_class?`<span class="lic risk risk-${esc(r.license_class)}" title="${esc('No LICENSE file. '+RISK[r.license_class]+' under the license policy (licenses.no_license).')}"><span class="dot" aria-hidden="true"></span>No LICENSE file</span><span class="sr"> (${esc(RISK[r.license_class])})</span>`:'<span class="lic none">No LICENSE file</span>';
  const vuln=deps.filter(d=>d.vulns&&d.vulns.count).length,known=deps.filter(d=>d.license).length,pkgs=deps.filter(licensable).length;
  const dep=r.error?`<span class="muted">Not analysed</span><div class="sub">${esc(r.error)}</div>`
    :deps.length?`<a href="deps.html?repo=${encodeURIComponent(r.repository)}">${num(deps.length)} dependencies</a><div class="sub">${pkgs?`${known} of ${pkgs} with a known license`:'Local actions only'}</div>${vuln?`<div class="sub"><a class="bad" href="deps.html?repo=${encodeURIComponent(r.repository)}&vuln=any">${vuln} with known vulnerabilities</a></div>`:deps.some(d=>d.vulns)?'<div class="sub good">No known vulnerabilities</div>':''}`
    :'<span class="muted">None found</span>';
  return `<tr${r.license_class==='red'||r.license_class==='yellow'?` class="row-risk-${r.license_class}"`:''}><td><a class="repo" href="${esc(url)}/tree/${esc(r.branch)}" target="_blank" rel="noopener">${esc(r.repository)}</a> ${tagChips(r)}<div class="sub">${esc(r.branch)}${devDefault(r)}</div></td>`
    +`<td data-label="License">${lic}</td>`
    +`<td data-label="Stack">${esc(langs)||'<span class="muted">Nothing detected</span>'}${techs.length?`<div class="techs">${esc(techs.slice(0,8).join(', '))}${techs.length>8?` +${techs.length-8} more`:''}</div>`:''}</td>`
    +`<td data-label="Dependencies">${dep}</td></tr>`;
}
function fillStack(){
  stackCards();
  if(!stack)return;
  const a=stackList().filter(shown).sort((x,y)=>x.repository.localeCompare(y.repository));lastShown['stack-rows']=a;
  $('stack-rows').innerHTML=a.length?a.map(stackRow).join(''):`<tr><td colspan="4" class="empty">${visibleSet&&stackList().length?'No repositories match these filters.':'No repositories analysed yet.'}</td></tr>`;
}
/* ---- cards above each table: computed from the rows that table shows (the branch switch and the filters apply) ---- */
const TARGET=80;
// value is text (escaped here); sub is trusted HTML built from numbers and esc()'d names
function card({label,value,unit='',of=null,bar=null,sub='',tone=''}){
  const pct=bar==null?null:Math.max(0,Math.min(100,bar*100));
  return `<div class="kpi"><div class="kpi-label">${esc(label)}</div>`
    +`<div class="kpi-value${tone?' '+tone:''}">${esc(value)}${unit?`<span class="kpi-unit">${esc(unit)}</span>`:''}${of!=null?`<span class="kpi-of"> / ${esc(of)}</span>`:''}</div>`
    +(pct==null?'':`<div class="kpi-bar" role="img" aria-label="${Math.round(pct)}%"><span style="width:${pct.toFixed(1)}%"></span></div>`)
    +(sub?`<div class="kpi-sub">${sub}</div>`:'')+'</div>';
}
const plural=(n,one,many)=>`${n} ${n===1?one:many}`;
function devCards(){
  const all=viewList().filter(shown),n=all.length,rep=all.filter(r=>isNum(r.coverage));
  if(!n){$('kpi-dev').innerHTML='';return}
  const det=rep.filter(r=>isNum((r.coverage_detail||{}).lines)&&+r.coverage_detail.lines>0);
  const lines=det.reduce((s,r)=>s+ +r.coverage_detail.lines,0),hits=det.reduce((s,r)=>s+ +r.coverage_detail.hits,0);
  const overall=lines?hits/lines*100:rep.length?rep.reduce((s,r)=>s+ +r.coverage,0)/rep.length:null;
  const below=rep.filter(r=>+r.coverage<TARGET).length;
  const stale=rep.filter(r=>r.measured_at&&(Date.now()-new Date(r.measured_at))/864e5>STALE_DAYS).length;
  const st=k=>all.filter(r=>(r.security||{}).state===k).length,pass=st('passing'),fail=st('failing'),other=n-pass-fail;
  $('kpi-dev').innerHTML=[
    card({label:'Reporting coverage',value:rep.length,of:n,bar:rep.length/n,tone:rep.length<n?'warn':'good',sub:n-rep.length?plural(n-rep.length,'repo uploads nothing','repos upload nothing'):'Every repository reports'}),
    card({label:'Overall line coverage',value:overall==null?'—':overall.toFixed(1),unit:overall==null?'':'%',tone:overall==null?'':overall<TARGET?'warn':'good',
      sub:lines?`${num(hits)} / ${num(lines)} lines · ${num(lines-hits)} uncovered${det.length<rep.length?` · ${rep.length-det.length} without line counts`:''}`
        :rep.length?`Mean of ${plural(rep.length,'reporting repository','reporting repositories')}`:'No repository reports coverage'}),
    card({label:`Below ${TARGET}% target`,value:below,tone:below?'warn':'',sub:`of ${rep.length} reporting`}),
    card({label:`Stale (> ${STALE_DAYS} days)`,value:stale,tone:stale?'warn':'',sub:'Not re-measured recently'}),
    card({label:'Security workflow',value:pass,unit:' passing',tone:fail?'':pass?'good':'',
      sub:`${pass} passing · ${fail?`<span class="bad">${fail} failing</span>`:'0 failing'} · ${other} not run`}),
  ].join('');
}
function releaseCards(){
  const n=viewList().filter(shown).length,groups=(data.releases||[]).filter(g=>shown(g)&&pool(g).length);
  if(!n){$('kpi-release').innerHTML='';return}
  const versions=groups.flatMap(g=>pool(g)),picks=groups.map(relPick).filter(Boolean);
  const newest=versions.map(v=>v.version).sort(verCmp).pop(),pre=versions.filter(v=>v.prerelease).length;
  const fail=picks.filter(v=>(v.security||{}).state==='failing').length,cov=picks.filter(v=>isNum(v.coverage)).length;
  $('kpi-release').innerHTML=[
    card({label:'Repos with a release',value:groups.length,of:n,bar:groups.length/n,sub:n-groups.length?`${n-groups.length} never released`:'Every repository has released'}),
    card({label:'Newest version',value:newest||'—',sub:`${plural(versions.length,'version','versions')} tracked · ${pre} pre-release`}),
    card({label:'Security failing at release',value:fail,tone:fail?'bad':'',sub:fail?'The version shown fails its security workflow':'No shown version fails its security workflow'}),
    card({label:'Coverage measured at release',value:cov,of:picks.length,tone:cov<picks.length?'warn':'',sub:picks.length-cov?`${picks.length-cov} released with no report`:'Every shown version has a report'}),
  ].join('');
}
function stackCards(){
  if(!stack){$('kpi-stack').innerHTML='';return}
  const rs=stackList().filter(shown),n=rs.length;
  if(!n){$('kpi-stack').innerHTML='';return}
  const nolic=rs.filter(r=>!r.license).length;
  const deps=rs.flatMap(r=>(r.dependencies||[]).map(d=>({d,repo:r.repository})));
  const vul=deps.filter(x=>x.d.vulns&&x.d.vulns.count),vrepos=new Set(vul.map(x=>x.repo)).size;
  const lic=deps.filter(x=>licensable(x.d)),known=lic.filter(x=>x.d.license).length,pct=lic.length?known/lic.length*100:null;
  const langs=[...new Set(rs.flatMap(r=>(r.languages||[]).map(l=>l[0])))];
  $('kpi-stack').innerHTML=[
    card({label:'Missing LICENSE file',value:nolic,of:n,tone:nolic?'bad':'good',sub:'Required for DPG certification'}),
    card({label:'Known vulnerabilities',value:vul.length,tone:vul.length?'bad':'good',sub:vul.length?`${vul.length===1?'dependency':'dependencies'} in ${plural(vrepos,'repository','repositories')}`:'No dependency has a known vulnerability'}),
    card({label:'Dependency licenses known',value:pct==null?'—':Math.floor(pct),unit:pct==null?'':'%',bar:pct==null?null:pct/100,tone:pct!=null&&pct<95?'warn':'',sub:`${num(known)} of ${num(lic.length)} dependencies`}),
    card({label:'Dependencies',value:num(deps.length),sub:langs.length?`${plural(langs.length,'language','languages')}: ${esc(langs.join(', '))}`:'No languages detected'}),
  ].join('');
}
function render(){
  if($('rel-all').options.length<2)fillRelAll();
  devCards();releaseCards();
  fill('dev-rows',viewList(),'No repositories configured. Add them to config/repos.json.');
  fill('rel-rows',(data.releases||[]).filter(g=>pool(g).length),relAllowed?'No repository has a version that matches.':'No repository has a release version yet.',relRow);
  fillStack();
}
/* ---- filters: one bar for every table (a repository is shown when it passes all of them) ---- */
const SECL={passing:'Passing',failing:'Failing','no runs':'No runs','no workflow':'No security workflow','branch not found':'Branch not found',unknown:'Unknown'};
const COVL={high:'80% or more',mid:'50% to 79%',low:'Under 50%',none:'No report'},RISK={green:'Preferred (green)',yellow:'Not recommended (yellow)',red:'Restricted use (red)',unclassified:'Unclassified',none:'No LICENSE file'};
const VULNL={'critical-high':'Critical or high',any:'Any known vulnerability',none:'None known',unchecked:'Not checked'};
const stackList=()=>!stack?[]:(view==='main'?stack.main||stack.repositories:Branches.devOnly(stack.repositories))||[];
function repoItems(){
  const st=Object.fromEntries(stackList().map(r=>[r.repository,r]));
  return viewList().map(r=>{
    const s=st[r.repository]||{},deps=s.dependencies||[],c=isNum(r.coverage)?+r.coverage:null;
    const vul=!deps.some(d=>d.vulns)?['unchecked']:!deps.some(d=>d.vulns&&d.vulns.count)?['none']:deps.some(d=>d.vulns&&(d.vulns.severity==='CRITICAL'||d.vulns.severity==='HIGH'))?['any','critical-high']:['any'];
    return {repository:r.repository,tags:r.tags||(r.dpg?['DPG']:[]),sec:(r.security||{}).state||'unknown',cov:c===null?'none':c>=80?'high':c>=50?'mid':'low',
      license:stack?(s.license||'(no LICENSE file)'):null,risk:stack?(s.license?s.license_class||'unclassified':s.license_class||'none'):null,vuln:stack?vul:null,
      langs:(s.languages||[]).map(l=>l[0])};
  });
}
const REPO_FACETS=[
  {key:'repository',param:'repo',label:'Repository',get:i=>i.repository},
  {key:'tag',label:'Tag',get:i=>i.tags.length?i.tags:'(none)'},
  {key:'sec',label:'Security',get:i=>i.sec,valueLabel:v=>SECL[v]||v,order:['failing','passing','no runs','no workflow']},
  {key:'cov',label:'Coverage',get:i=>i.cov,valueLabel:v=>COVL[v],order:['low','mid','high','none']},
  {key:'risk',label:'License risk',get:i=>i.risk,valueLabel:v=>RISK[v]||v,order:['red','yellow','green','unclassified','none']},
  {key:'license',label:'License',get:i=>i.license},
  {key:'vuln',label:'Vulnerabilities',get:i=>i.vuln,valueLabel:v=>VULNL[v]||v,order:['critical-high','any','none','unchecked']},
  {key:'lang',label:'Language',get:i=>i.langs},
];
function onRepoFilter(list){visibleSet=new Set(list.map(i=>i.repository));summary();render()}
function initFilters(){
  bar=Filters.createFilterBar($('filters'),{facets:REPO_FACETS,items:repoItems(),noun:'repositories',text:{param:'q',placeholder:'Find a repository',of:i=>i.repository},onChange:onRepoFilter});
  visibleSet=new Set(bar.visible().map(i=>i.repository));
  const items=(data.releases||[]).flatMap(g=>g.versions.map(v=>({key:vkey(g,v),kinds:v.kinds,stable:v.prerelease?'pre':'stable'})));
  relBar=Filters.createFilterBar($('rel-filters'),{facets:[
    {key:'found',param:'found',label:'Found as',get:i=>i.kinds,valueLabel:v=>({branch:'Release branch',tag:'Tag',release:'GitHub Release'}[v]||v),order:['release','tag','branch']},
    {key:'stable',param:'stab',label:'Stability',get:i=>i.stable,valueLabel:v=>v==='pre'?'Pre-release':'Stable',order:['stable','pre']},
  ],items,noun:'versions',onChange:list=>{relAllowed=list.length===items.length?null:new Set(list.map(i=>i.key));fillRelAll();render()}});
  relAllowed=relBar.visible().length===items.length?null:new Set(relBar.visible().map(i=>i.key));
  const want=new URLSearchParams(location.search).get('ver');if(want)relAll=want;
}
async function initStack(){
  try{const res=await fetch('./data/stack.json',{cache:'no-store'});if(!res.ok)throw Error(res.status);stack=await res.json();Object.assign(RISK,withColour((stack.license_policy||{}).labels));if(bar)bar.setItems(repoItems());fillStack();if(data.main.length)render()}   // repo stars come from stack.json
  catch(e){$('stack-rows').innerHTML='<tr><td colspan="4" class="empty">data/stack.json is missing or unreadable.</td></tr>'}
}
async function init(){
  try{
    const res=await fetch('./data/coverage.json',{cache:'no-store'});if(!res.ok)throw Error(res.status);
    data=await res.json();
    $('updated').textContent=data.generated_at?'Updated '+new Date(data.generated_at).toLocaleString(undefined,{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}):'Not refreshed yet';
    if(!data.main)data.main=data.repositories||[];
    setView(view);initFilters();initRelSet();fillRelAll();summary();render();
  }catch(e){
    $('updated').textContent='Data unavailable';
    $('summary').textContent='Coverage data could not be loaded. Run the refresh workflow and check its logs.';
    ['dev-rows','rel-rows'].forEach(id=>$(id).innerHTML='<tr><td colspan="3" class="empty">data/coverage.json is missing or unreadable.</td></tr>');
  }
}
$('rel-all').addEventListener('change',e=>{relAll=e.target.value;for(const k in picked)delete picked[k];setUrl('ver',relAll);render()});
$('rel-set').addEventListener('change',e=>{relSet=e.target.value;relAll='';$('rel-all').value='';$('rel-all').disabled=!!relSet;for(const k in picked)delete picked[k];setUrl('ver','');setUrl('set',relSet||'latest');render()});
$('rel-rows').addEventListener('change',e=>{const s=e.target.closest('select.ver');if(s){picked[s.dataset.repo]=s.value;render();const again=document.querySelector(`select.ver[data-repo="${CSS.escape(s.dataset.repo)}"]`);if(again)again.focus()}});
$('view-dev').addEventListener('click',()=>setView('dev'));$('view-main').addEventListener('click',()=>setView('main'));
/* ---- Excel: each table's rows as shown, or one workbook with everything ---- */
const branchName=()=>view==='main'?'main':'development';
const deps=repos=>(repos||[]).flatMap(r=>(r.dependencies||[]).map(d=>({...d,repository:r.repository})));
const EXPORTS={
  dev:()=>[`openagrinet-coverage-${branchName()}`,[{name:`Coverage (${branchName()})`,rows:Export.coverage(lastShown['dev-rows'])}]],
  release:()=>[`openagrinet-releases`,[{name:'Releases',rows:Export.releases(lastShown['rel-rows'],relPick)}]],
  stack:()=>[`openagrinet-stack-${branchName()}`,[{name:`Stack (${branchName()})`,rows:Export.stack(lastShown['stack-rows'],(stack&&stack.license_policy||{}).labels)}]],
};
document.querySelectorAll('[data-export]').forEach(b=>b.addEventListener('click',()=>{const [f,sheets]=EXPORTS[b.dataset.export]();Xlsx.download(Export.filename(f),sheets)}));
$('export-all').addEventListener('click',()=>{
  const s=stack||{},labels=(s.license_policy||{}).labels,eco=(s.display||{}).ecosystems,dev=deps(s.repositories),main=deps(s.main||s.repositories);
  Xlsx.download(Export.filename('openagrinet-dashboard'),[
    {name:'About',rows:[['Item','Value'],['Organization',data.organization||s.organization],['Coverage data updated',data.generated_at],['Stack data updated',s.generated_at],['Exported',new Date().toISOString()],
      ['Note','Everything on the dashboard, both branches, with no filters. Development is each repository\'s development branch, or its default branch when none was found.']]},
    {name:'Coverage (development)',rows:Export.coverage(data.repositories)},
    {name:'Coverage (main)',rows:Export.coverage(data.main)},
    {name:'Releases (all versions)',rows:Export.releases(data.releases)},
    {name:'Stack (development)',rows:Export.stack(s.repositories,labels)},
    {name:'Stack (main)',rows:Export.stack(s.main||s.repositories,labels)},
    {name:'Dependencies (development)',rows:Export.dependencies(dev,labels,eco)},
    {name:'Dependencies (main)',rows:Export.dependencies(main,labels,eco)},
    {name:'Vulnerabilities (development)',rows:Export.vulnerabilities(dev)},
    {name:'Vulnerabilities (main)',rows:Export.vulnerabilities(main)},
    {name:'License policy',rows:Export.policy(s.license_policy)},
  ]);
});
init();initStack();
