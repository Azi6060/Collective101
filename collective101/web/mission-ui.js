'use strict';
// Read-only presentation of recorded missions and saved files. No model/tool calls.
window.CollectiveMissionUI = (() => {
  const ns='http://www.w3.org/2000/svg';
  const paths={
    distribution:'M12 3v6M5 21v-6h14v6M5 15v-3h14v3M12 12V9M9 3h6',
    research:'M20 20l-5-5M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0M7 10h6M10 7v6',
    strategy:'M5 21V3m0 1h13l-3 4 3 4H5M9 21H2',
    engineering:'m8 6-6 6 6 6m8-12 6 6-6 6M14 3l-4 18',
    data:'M3 3v18h18M7 16v-5m5 5V6m5 10v-8',
    design:'m4 16-1 5 5-1L21 7l-4-4ZM14 6l4 4M4 16l4 4',
    operations:'m3 7 9-4 9 4v10l-9 4-9-4Zm0 0 9 4 9-4M12 11v10M8 5l9 4',
    communications:'M21 11a8 8 0 0 1-8 8H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4ZM7 8h10M7 12h7',
    platform:'m12 2 10 5-10 5L2 7Zm-10 10 10 5 10-5M2 17l10 5 10-5',
    assurance:'m12 2 9 4v6c0 5-9 10-9 10S3 17 3 12V6Zm-5 10 3 3 7-7',
    file:'M14 2H5v20h14V7Zm0 0v5h5M8 12h8M8 16h6',
  };
  const t=text=>window.CollectivePreferences?.t(text)||text;
  const el=(tag,cls,text)=>{const node=document.createElement(tag);if(cls)node.className=cls;if(text!==undefined)node.textContent=text;if(['sample-heading','sample-copy','deliverable-path','journey-title'].includes(cls)||tag==='h3')node.dir='auto';if(cls==='sample-source')node.dir='ltr';return node;};
  function icon(id) {
    const svg=document.createElementNS(ns,'svg');
    for(const [key,value] of Object.entries({viewBox:'0 0 24 24',fill:'none',stroke:'currentColor','stroke-width':'1.5','stroke-linecap':'round','stroke-linejoin':'round','aria-hidden':'true'}))svg.setAttribute(key,value);
    const path=document.createElementNS(ns,'path');path.setAttribute('d',paths[id]||paths.file);svg.append(path);return svg;
  }
  function button(text,callback,cls='btn btn-outline-secondary') {const node=el('button',cls,t(text));node.type='button';node.addEventListener('click',callback);return node;}
  function team(chat,roster) {
    // A shortlist is only a proposal. Display selected departments only when recorded.
    const selected=chat?.run?.result?.selected_departments;
    const ids=Array.isArray(selected)?selected:[];
    const observed=new Set((chat?.workspace?.events||[]).filter(event=>event.agent_id&&event.id?.startsWith((chat.effective_run_id||chat.run_id)+':')).map(event=>event.agent_id.replace(/-\d+$/,'')));
    return (roster?.departments||[]).filter(department=>ids.length?ids.includes(department.id):observed.has(department.id));
  }
  function milestone(chat) {
    const files=chat?.workspace?.files||[],events=(chat?.workspace?.events||[]).filter(event=>event.id?.startsWith((chat.effective_run_id||chat.run_id)+':'));
    const current=chat?.progress?.phase;
    return [
      {name:'Plan',detail:chat?.brief?'Outcome agreed':'Not recorded',recorded:!!chat?.brief,current:['assess','coordinate','select'].includes(current)},
      {name:'Create',detail:files.length?`${files.length} saved files`:'No saved files',recorded:!!files.length,current:['work','report','tool','repair'].includes(current)},
      {name:'Review',detail:events.some(event=>event.phase==='review'&&event.status==='accepted')?'Review recorded':'Not recorded',recorded:events.some(event=>event.phase==='review'&&event.status==='accepted'),current:['review','review_assignment','checks'].includes(current)},
      {name:'Outcome',detail:chat?.status==='reviewed'?'Reviewed':chat?.status==='blocked'?'Blocked':chat?.status==='error'?'Needs attention':chat?.status==='needs_input'?'Your guidance':'Pending',recorded:chat?.status==='reviewed',current:current==='retrospective',blocked:['blocked','error'].includes(chat?.status)},
    ];
  }
  function renderJourney(chat,roster) {
    const host=document.getElementById('mission-journey');host.hidden=!chat?.run_id;if(host.hidden){host.replaceChildren();host.dataset.signature='';return;}
    const members=team(chat,roster),steps=milestone(chat);
    const signature=JSON.stringify([chat.id,chat.title,chat.status,steps,members.map(dept=>dept.id),document.documentElement.lang]);
    if(host.dataset.signature===signature)return;host.dataset.signature=signature;
    const focusedSummary=document.activeElement===host.querySelector('summary');
    const summary=el('summary','journey-summary');summary.append(el('span','journey-glyph','↗'),el('span','journey-title',chat.title||t('Your mission')),el('span','state-pill '+chat.status,t(chat.status==='reviewed'?'Reviewed':chat.status.replaceAll('_',' '))));
    const list=el('ol','journey-steps');list.setAttribute('aria-label',t('Recorded mission milestones'));
    steps.forEach((step,index)=>{const li=el('li','journey-step'+(step.recorded?' is-recorded':'')+(step.current?' is-current':'')+(step.blocked?' is-blocked':''));if(step.current)li.setAttribute('aria-current','step');li.append(el('span','journey-node',String(index+1).padStart(2,'0')),el('strong','',t(step.name)),el('small','',t(step.detail)));list.append(li);});
    const badges=el('div','mission-team');
    if(members.length){badges.append(el('span','team-label',t(chat?.run?.result?.selected_departments?.length?'Selected departments':'Departments in recorded activity')));members.forEach(dept=>{const badge=el('span','department-badge');badge.dataset.department=dept.id;badge.append(icon(dept.id),el('span','',dept.name));badges.append(badge);});}
    host.replaceChildren(summary,list,badges);
    if(focusedSummary)summary.focus({preventScroll:true});
  }
  function fileCard(file,chat,handlers) {
    const html=/\.html?$/i.test(file.path),markdown=/\.(md|markdown)$/i.test(file.path),department=file.agent_id?.replace(/-\d+$/,'')||file.path.split('/')[0];
    const card=el('article','deliverable-card');card.dataset.department=department;card.dataset.filePath=file.path;
    const sample=el('div','deliverable-sample '+(markdown?'sample-document':'sample-code'));sample.setAttribute('aria-label',t('Saved source excerpt'));
    const top=el('div','sample-toolbar');top.append(icon(department),el('span','',file.language||'Text'),el('span','sample-dots','•••'));sample.append(top);
    const source=String(file.content||'');
    if(markdown){
      const lines=source.split('\n').filter(line=>line.trim());
      sample.append(el('p','sample-heading',(lines.find(line=>/^#\s/.test(line))||file.path.split('/').pop()).replace(/^#+\s*/,'')),el('p','sample-copy',lines.filter(line=>!/^#/.test(line)).join(' ').slice(0,200)));
    } else {
      const title=html?source.match(/<title[^>]*>([\s\S]*?)<\/title>/i)?.[1]:null;
      if(title)sample.append(el('p','sample-heading',title.slice(0,90)));
      sample.append(el('pre','sample-source',source.split('\n').filter(line=>line.trim()).slice(0,5).map(line=>line.slice(0,120)).join('\n').slice(0,500)));
    }
    const copy=el('div','deliverable-copy');copy.append(el('p','deliverable-kind',t('Saved source')),el('h3','',file.path.split('/').pop()),el('p','deliverable-path',file.path));
    const meta=el('div','deliverable-meta');meta.append(el('span','',`${file.lines??source.split('\n').length} lines`),el('span','',file.language||'Text'));copy.append(meta);
    const actions=el('div','deliverable-actions');
    actions.append(button(markdown?'Read document':'View source',()=>handlers.showSource(file)));
    if(html&&chat.workspace.preview?.ready&&handlers.previewAvailable)actions.append(button('Open website',()=>handlers.openPreview(file.path),'btn btn-primary'));
    const download=button('Download file',()=>handlers.downloadFile(file),'deliverable-download');download.setAttribute('aria-label',t('Download file')+' '+file.path);actions.append(download);
    [...actions.children].forEach((action,index)=>{action.dataset.filePath=file.path;action.dataset.fileAction=String(index);});
    card.append(sample,copy,actions);return card;
  }
  function renderResults(chat,handlers) {
    const host=document.getElementById('mission-results'),files=chat?.workspace?.files||[];
    host.hidden=!files.length;if(host.hidden){host.replaceChildren();host.dataset.signature='';return;}
    const signature=JSON.stringify([chat.id,chat.status,files.map(file=>[file.path,file.sha256,file.content?.length]),chat.workspace.preview?.ready,handlers.previewAvailable,document.documentElement.lang]);
    if(host.dataset.signature===signature)return;host.dataset.signature=signature;
    const expanded=host.querySelector('.all-deliverables')?.open;
    const focus=host.contains(document.activeElement)?{path:document.activeElement.dataset.filePath,action:document.activeElement.dataset.fileAction}:null;
    const heading=el('div','results-heading'),copy=el('div');copy.append(el('p','section-kicker',t('FROM IDEA TO SOMETHING REAL')),el('h2','',t('Your saved deliverables')));heading.append(copy,el('span','state-pill '+chat.status,t(chat.status==='reviewed'?'Current mission reviewed':'Saved work')));
    const note=el('p','results-note',t('Source previews from this conversation. Saved files may include earlier work.'));
    const ordered=files.map((file,index)=>({file,index})).sort((a,b)=>(/\.html?$/i.test(b.file.path)?2:/\.(md|markdown)$/i.test(b.file.path)?1:0)-(/\.html?$/i.test(a.file.path)?2:/\.(md|markdown)$/i.test(a.file.path)?1:0)||a.index-b.index).map(item=>item.file);
    const grid=el('div','deliverable-grid');grid.append(...ordered.slice(0,4).map(file=>fileCard(file,chat,handlers)));
    const details=el('details','all-deliverables');details.append(el('summary','',`${t('All saved files')} (${files.length})`));
    details.open=!!expanded;
    for(const file of ordered){const row=el('div','all-deliverable-row'),source=button(file.path,()=>handlers.showSource(file),'file-text-link'),download=button('Download file',()=>handlers.downloadFile(file),'deliverable-download');source.dataset.filePath=download.dataset.filePath=file.path;source.dataset.fileAction='list-source';download.dataset.fileAction='list-download';row.append(source,download);details.append(row);}
    const evidence=button('View activity & evidence',handlers.viewEvidence,'btn btn-outline-secondary results-evidence');
    evidence.disabled=!chat.run_id;
    host.replaceChildren(heading,note,grid,details,evidence);
    if(handlers.thumbnailsAvailable)for(const card of grid.children){const file=files.find(item=>item.path===card.dataset.filePath);window.CollectiveThumbnails?.attach(card.querySelector('.deliverable-sample'),file,chat);}
    if(focus?.path)[...host.querySelectorAll('[data-file-path]')].find(node=>node.dataset.filePath===focus.path&&node.dataset.fileAction===focus.action)?.focus({preventScroll:true});
  }
  function render(chat,roster,handlers) {renderJourney(chat,roster);renderResults(chat,handlers);}
  return {icon,team,milestone,render};
})();
