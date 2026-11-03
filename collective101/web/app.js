'use strict';
let selectedSource=null,progressStarted=null,inspectorChat=null,previewOpening=false,previewChat=null;
let evaluationPage=null,selectedEvaluation=null,evaluationBusy=false;
const phaseLabels={assess:'Assessing the task',coordinate:'Aligning the departments',select:'Selecting the team',work:'Creating the deliverable',report:'Gathering saved work',review_assignment:'Assigning a reviewer',review:'Checking the result',retrospective:'Preparing your result'};
function saveBlob(blob,filename){const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function showSource(file){
  selectedSource=file;$('file-viewer-title').textContent=file.path;$('file-source').textContent=file.content;
  const markdown=/\.(md|markdown)$/i.test(file.path)&&typeof markdownFragment==='function';
  $('file-tabs').hidden=!markdown;
  $('file-preview').replaceChildren();
  if(markdown)$('file-preview').append(markdownFragment(file.content));
  setFileView(markdown?'preview':'source');
  $('preview-file').hidden=!/\.html?$/i.test(file.path);
  if($('file-viewer').showModal)$('file-viewer').showModal();else $('file-viewer').setAttribute('open','');
}
function setFileView(view){
  const preview=view==='preview';
  $('file-preview').hidden=!preview;$('file-source').hidden=preview;
  for(const name of ['preview','source']){const tab=$('file-'+name+'-tab'),selected=view===name;tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;}
}
function renderWorkspace(chat){
  const w=chat?.workspace||{files:[],totals:{files:0,lines:0,code_lines:0,added:0,removed:0},events:[],failures:[]};
  const t=w.totals;$('workspace-title').textContent=chat?.title||'New chat';
  $('workspace-state').textContent=chat?.status==='reviewed'?'Reviewed':chat?.status==='running'?'Working':chat?.status==='blocked'?'Needs attention':'';
  $('changes-summary').replaceChildren(element('span','lines-added','+'+t.added),element('span','lines-removed','−'+t.removed));
  $('changes-summary').setAttribute('aria-label',`${t.added} lines added, ${t.removed} lines removed in saved files`);
  $('workspace-counts').textContent=t.files?`${t.files} files · ${t.code_lines??t.lines} lines of code · saved changes`:'Files appear as agents save them.';
  $('download-project').disabled=!t.files;
  const preview=w.preview;
  $('preview-project').disabled=previewOpening||!preview?.ready||!state.health?.features?.site_preview;
  $('preview-status').textContent=!state.health?.features?.site_preview?'Restart the local server to enable website previews.':preview?.reason||'No HTML page has been saved yet. Preview becomes available when agents create one.';
  if(previewChat!==chat?.id){previewChat=chat?.id;$('preview-link').classList.add('d-none');$('preview-link').removeAttribute('href');}
  const signature=JSON.stringify([w.files.map(f=>[f.path,f.sha256]),w.events,w.failures]);
  if($('workspace-files').dataset.signature!==signature){
    $('workspace-files').dataset.signature=signature;
    $('workspace-files').replaceChildren(...w.files.map(file=>{const row=element('div','workspace-file-row');const b=action('',()=>showSource(file),'workspace-file');b.append(element('span','file-path',file.path),element('span','file-meta',`${file.lines} lines`));b.title=`View ${file.path} source`;row.append(b);if(/\.html?$/i.test(file.path)){const p=action('↗',()=>openPreview(file.path),'workspace-action file-preview');p.setAttribute('aria-label',`Preview ${file.path} in a new tab`);p.title=p.getAttribute('aria-label');row.append(p);}return row;}));
    $('workspace-events').replaceChildren(...(w.events.length?w.events.slice(-6).reverse().map(e=>{const row=element('div','workspace-event '+e.status);row.append(element('span','event-mark',e.status==='accepted'?'✓':e.status==='failed'?'!':'·'),element('span','',`${prettyAgent(e.agent_id)} · ${phaseLabels[e.phase]||e.phase}`));return row;}):[element('p','workspace-muted','No actions yet.')]));
    $('workspace-failures').replaceChildren(...w.failures.slice(-8).reverse().map(f=>{const row=element('div','failure-record');row.append(element('strong','',`${f.kind||'Task'}${f.agent_id?' · '+prettyAgent(f.agent_id):''}`),element('p','',f.reason||'No diagnostic recorded.'));if(f.request_options)row.append(element('small','',`Output: ${f.request_options.max_tokens.toLocaleString()} · timeout: ${f.request_options.timeout}s`));return row;}));
  }
  $('workspace-failure-details').classList.toggle('d-none',!w.failures.length);
  if(chat?.run_id&&inspectorChat!==chat.id){inspectorChat=chat.id;if(innerWidth>=1280){$('chat-inspector').open=true;document.body.classList.add('inspector-open');}}
  const limits=state.health?.limits,p=state.health?.model_configuration?.request_policy;
  $('chat-limits-info').replaceChildren();
  if(chat?.context)$('chat-limits-info').append(element('p','',`${chat.context.saved_messages} messages saved · ${chat.context.history_bytes.toLocaleString()} bytes in the current history window${chat.context.history_compacted?' · earlier turns windowed':''}`));
  if(limits){
    for(const line of [`Message: ${limits.message_characters.toLocaleString()} characters`,`Per-request input: ${limits.request_input_bytes.toLocaleString()} UTF-8 bytes (conservative admission)`,
      `Chat history window sent: ${limits.history_window_bytes.toLocaleString()} bytes; full history remains saved`,
      limits.provider_context_tokens?`Model context window: ${limits.provider_context_tokens.toLocaleString()} tokens`:'Model context window: provider-dependent',
      `Output cap: ${(p?.max_output_tokens||32768).toLocaleString()} tokens, including reasoning`,`Temperature: ${p?.temperature??1} · intake reasoning low / work medium`,
      `Retries per step: ${limits.provider_failures_per_step} provider failures, ${limits.truncations_per_step} truncations, ${limits.validation_failures_per_step} validation failures; ${limits.requests_per_step} requests maximum`,
      `Repair rounds: ${limits.repair_rounds_default} by default, ${limits.repair_rounds_max} maximum; shared chat budget applies`])$('chat-limits-info').append(element('p','',line));
  }
  if(!chat?.progress)progressStarted=null;
  else if(!progressStarted)progressStarted=Date.now();
  updateProgressClock();
}
function updateProgressClock(){if($('chat-progress-time'))$('chat-progress-time').textContent=progressStarted?Math.floor((Date.now()-progressStarted)/1000)+'s':'';}
async function openPreview(entry=null){
  if(!state.chat||previewOpening)return;
  if(!state.health?.features?.site_preview){notice('Restart the local server to enable website previews, then refresh.');return;}
  const cid=state.chat.id,tab=window.open('about:blank','_blank');if(tab)tab.opener=null;
  previewOpening=true;$('preview-project').disabled=true;
  try{
    const result=await api('/api/chats/'+cid+'/preview',{entry});
    const url=new URL(result.url);if(url.protocol!=='http:'||url.hostname!=='127.0.0.1'||url.port===location.port||!url.pathname.startsWith('/p/'))throw new Error('Invalid local preview address');
    url.searchParams.set('entry',result.entry);
    if(state.chat?.id===cid){$('preview-link').href=url.href;$('preview-link').classList.remove('d-none');}
    if(tab)tab.location.href=url.href;else notice('Your browser blocked the new tab. Use “Open website preview” in Files & activity.');
  }catch(error){if(tab)tab.close();notice(error.message);}
  finally{previewOpening=false;renderWorkspace(state.chat);}
}
function renderEvaluationAgents(){
  if(!evaluationPage)return;const query=$('evaluation-search').value.toLowerCase();
  const rows=evaluationPage.agents.filter(a=>(a.name+' '+a.id+' '+a.department+' '+a.verdict).toLowerCase().includes(query));
  $('evaluation-agents').replaceChildren(...rows.map(agent=>{const row=element('tr');const name=element('td');name.append(element('strong','',agent.name),element('small','d-block text-secondary',agent.id+' · '+agent.department));const evidence=element('td','',agent.graded_trials?`${agent.successes}/${agent.graded_trials} graded · ${agent.distinct_cases} cases`:'No graded live evidence');if(agent.evidence_profile?.model)evidence.append(element('small','d-block text-secondary','Last tested: '+agent.evidence_profile.model+' ? '+agent.evidence_profile.suite));if(agent.human_pending)evidence.append(element('small','d-block',agent.human_pending+' awaiting human review'));if(agent.confidence_low!==null)evidence.append(element('small','d-block text-secondary',`Descriptive interval ${Math.round(agent.confidence_low*100)}–${Math.round(agent.confidence_high*100)}%`));row.append(name,evidence,element('td','evaluation-verdict '+agent.verdict,agent.verdict.replaceAll('_',' ')));return row;}));
  if(!rows.length){const row=element('tr');const cell=element('td','','No agents match your search.');cell.colSpan=3;row.append(cell);$('evaluation-agents').append(row);}
}
async function showEvaluation(id){
  selectedEvaluation=id;
  try{
    const report=await api('/api/evaluations/'+id);const signature=JSON.stringify(report);if($('evaluation-detail').dataset.signature===signature)return;
    $('evaluation-detail').dataset.signature=signature;const box=$('evaluation-detail');box.replaceChildren(element('h3','',report.id),element('p','small text-secondary',`${report.status} · ${report.calls} calls · ${report.tokens.toLocaleString()} reported tokens · ${report.metadata.provider} / ${report.metadata.model||'scripted provider'} · ${report.metadata.suite}`));
    if(['queued','running'].includes(report.status))box.append(action('Stop after the current request',async()=>{try{await api('/api/evaluations/'+id+'/stop',{});await refreshEvaluations();}catch(error){notice(error.message);}}));
    if(report.error)box.append(element('p','text-danger',report.error));
    for(const comparison of report.comparisons||[]){const panel=element('div','alert alert-light small');panel.append(element('strong','',comparison.baseline.replaceAll('_',' ')+' ? '+comparison.treatment.replaceAll('_',' ')),element('p','mb-1',`${comparison.paired_trials} graded pairs ? ${comparison.distinct_cases} cases ? ${comparison.wins} wins / ${comparison.losses} losses / ${comparison.ties} ties`),element('p','mb-1',`Mean change: ${comparison.mean_token_difference?.toFixed(0)} tokens ? ${comparison.mean_seconds_difference?.toFixed(2)}s${comparison.memory_sources===0?' ? No reviewed memory was available in the treatment':''}`),element('small','text-secondary',comparison.scope));box.append(panel);}

    for(const trial of report.trials){
      const result=trial.result;const card=element('details','evaluation-trial');const title=evaluationPage?.cases.find(c=>c.id===trial.case_id)?.title||trial.case_id;
      card.append(element('summary','',`${title} · ${trial.mode.replaceAll('_',' ')} · ${result?.human_pending?'Needs human review':result?.passed===true?'Passed':result?.passed===false?'Failed':trial.status}`));
      card.append(element('p','small text-secondary',`${trial.agent_id} · trial ${trial.trial} · ${trial.calls} calls · ${trial.tokens} tokens · ${trial.seconds}s${result?.failure_kind?' · '+result.failure_kind:''}`));
      if(result){const content=element('pre','evaluation-output',JSON.stringify(result,null,2));card.append(content);}
      if(result?.requires_human){
        const form=element('form','evaluation-human-review');const label=element('label','form-label','Independent quality review: explain the evidence');const note=element('textarea','form-control');note.id='review-note-'+trial.id;note.maxLength=2000;note.required=true;note.rows=2;label.htmlFor=note.id;
        const accept=element('button','btn btn-outline-success btn-sm mt-2','Meets the quality rubric');accept.type='submit';const reject=element('button','btn btn-outline-secondary btn-sm mt-2','Needs improvement');reject.type='button';
        async function save(accepted){if(!note.reportValidity())return;try{await api('/api/evaluation-trials/'+trial.id+'/review',{accepted,note:note.value});await refreshEvaluations();}catch(error){notice(error.message);}}
        form.addEventListener('submit',event=>{event.preventDefault();save(true);});reject.addEventListener('click',()=>save(false));form.append(label,note,accept,reject);card.append(form);
      }
      if(trial.requests.length){const records=element('pre','evaluation-output',JSON.stringify(trial.requests,null,2));const disclosure=element('details');disclosure.append(element('summary','','Request diagnostics'),records);card.append(disclosure);}
      box.append(card);
    }
  }catch(error){$('evaluation-detail').replaceChildren(element('p','text-danger',error.message));}
}
async function refreshEvaluations(){
  if(evaluationBusy)return;evaluationBusy=true;
  try{
    evaluationPage=await api('/api/evaluations');const data=evaluationPage;
    const live=data.agents.reduce((sum,a)=>sum+a.live_trials,0),unrated=data.agents.filter(a=>a.verdict==='untested').length;
    $('evaluation-notice').textContent=`${data.agents.length} identities · ${unrated} untested · ${live} specialist live trials. Fixtures never count toward effectiveness.`;
    $('evaluation-policy').textContent=data.policy.criterion+' '+data.policy.limits;
    $('evaluation-model').textContent=state.health?.live_configured?'Model: '+(state.health.model_configuration?.model||'configured provider'):'Connect a live model before starting a benchmark.';
    $('start-evaluation').disabled=!state.health?.live_configured||data.runs.some(r=>['queued','running'].includes(r.status));
    if(!$('evaluation-cases').children.length){
      $('evaluation-cases').replaceChildren(...data.cases.map(c=>{const label=element('label','evaluation-case');const check=element('input');check.type='checkbox';check.value=c.id;check.name='evaluation-case';const text=element('span');text.append(element('strong','',c.title),element('small','d-block',c.agent_id+' · '+c.criteria.join('; ')));label.append(check,text);return label;}));
    }
    renderEvaluationAgents();
    const memory=await api('/api/lessons');$('memory-evidence').replaceChildren(...(memory.lessons.length?memory.lessons.map(lesson=>{const box=element('details','evaluation-trial');box.append(element('summary','',lesson.agent_id+' · '+lesson.status+' · '+lesson.situation),element('p','small',lesson.action),element('p','small','Observed: '+lesson.outcome),element('p','small text-secondary','Limits: '+lesson.limitations+' · evidence '+lesson.evidence_run+' · expires '+lesson.expires_at.slice(0,10)));const note=element('input','form-control');note.placeholder='Evidence note for your review';note.setAttribute('aria-label','Review note for '+lesson.id);note.maxLength=2000;const controls=element('div','d-flex gap-2 mt-2');async function review(accepted){if(!note.value.trim()){notice('Add a short evidence note before reviewing the lesson.');return;}try{await api('/api/lessons/'+lesson.id+'/review',{accepted,note:note.value});await refreshEvaluations();}catch(error){notice(error.message);}}controls.append(action('Approve as reference',()=>review(true)),action('Reject / revoke',()=>review(false)));box.append(note,controls);return box;}):[element('p','small text-secondary','No reviewed lessons yet. Memory experiments use a frozen snapshot and do not write evaluation answers back into operational memory.')]));
    $('evaluation-runs').replaceChildren(...(data.runs.length?data.runs.map(run=>{const button=action('',()=>showEvaluation(run.id),'evaluation-run');button.append(element('strong','',run.id),element('span','',run.status+' · '+run.calls+' calls · '+run.tokens+' tokens'));return button;}):[element('p','text-secondary small','No evaluations yet. Choose a small case set and a call cap to begin.')]));
    for(const proposal of memory.proposals||[]){const box=element('details','evaluation-trial');box.append(element('summary','','Proposed experiment ? '+proposal.recipient),element('p','small',proposal.content.change),element('p','small','Evidence: '+proposal.content.evidence),element('p','small','Measure: '+proposal.content.measure),element('small','text-secondary','Proposal only ? '+proposal.run_id+' ? '+proposal.provider.mode+'. No role, prompt or permission was changed.'));$('memory-evidence').append(box);}
    if(selectedEvaluation)await showEvaluation(selectedEvaluation);
  }catch(error){$('evaluation-notice').textContent='Could not load evaluation evidence: '+error.message;}
  finally{evaluationBusy=false;}
}
function initChatWorkspace(){
  $('lesson-form').addEventListener('submit',async event=>{event.preventDefault();try{await api('/api/lessons',{run_id:$('lesson-run').value,agent_id:$('lesson-agent').value,situation:$('lesson-situation').value,action:$('lesson-action').value,outcome:$('lesson-outcome').value,limitations:$('lesson-limitations').value});$('lesson-form').reset();await refreshEvaluations();}catch(error){notice(error.message);}});
  $('evaluation-search').addEventListener('input',renderEvaluationAgents);$('refresh-evaluations').addEventListener('click',refreshEvaluations);
  $('evaluation-form').addEventListener('submit',async event=>{event.preventDefault();const button=$('start-evaluation');button.disabled=true;try{const cases=[...document.querySelectorAll('[name="evaluation-case"]:checked')].map(c=>c.value),modes=[...document.querySelectorAll('[name="evaluation-mode"]:checked')].map(c=>c.value);const run=await api('/api/evaluations',{cases,modes,trials:Number($('evaluation-trials').value),max_calls:Number($('evaluation-calls').value),confirm_live:$('evaluation-confirm').checked});selectedEvaluation=run.id;$('evaluation-confirm').checked=false;await refreshEvaluations();}catch(error){notice(error.message);button.disabled=!state.health?.live_configured;}});
  document.querySelectorAll('.sidebar .nav [data-nav]').forEach(link=>{
    const text=[...link.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join('').trim().replace('Mission chat','Chat');
    [...link.childNodes].filter(n=>n.nodeType===3).forEach(n=>n.remove());
    link.append(element('span','nav-label',text));link.setAttribute('aria-label',text);link.title=text;
  });
  const toggle=$('toggle-sidebar');
  try{document.body.classList.toggle('sidebar-collapsed',localStorage.getItem('collective-nav-collapsed')==='true');}catch{}
  function navState(){const collapsed=innerWidth<768?!document.body.classList.contains('mobile-nav-open'):document.body.classList.contains('sidebar-collapsed');toggle.setAttribute('aria-expanded',String(!collapsed));toggle.setAttribute('aria-label',collapsed?'Expand navigation':'Collapse navigation');toggle.title=toggle.getAttribute('aria-label');}
  navState();
  toggle.addEventListener('click',()=>{if(innerWidth<768)document.body.classList.toggle('mobile-nav-open');else document.body.classList.toggle('sidebar-collapsed');try{localStorage.setItem('collective-nav-collapsed',String(document.body.classList.contains('sidebar-collapsed')));}catch{}navState();});
  addEventListener('resize',navState);
  $('chat-inspector').addEventListener('toggle',()=>document.body.classList.toggle('inspector-open',$('chat-inspector').open));
  $('close-file').addEventListener('click',()=>{if($('file-viewer').close)$('file-viewer').close();else $('file-viewer').removeAttribute('open');});
  for(const name of ['preview','source'])$('file-'+name+'-tab').addEventListener('click',()=>setFileView(name));
  $('file-tabs').addEventListener('keydown',event=>{
    if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
    event.preventDefault();const name=event.key==='Home'?'preview':event.key==='End'?'source':$('file-preview').hidden?'preview':'source';
    setFileView(name);$('file-'+name+'-tab').focus();
  });
  $('download-file').addEventListener('click',()=>{if(selectedSource)saveBlob(new Blob([selectedSource.content],{type:'text/plain;charset=utf-8'}),selectedSource.path.split('/').pop());});
  $('preview-project').addEventListener('click',()=>openPreview());
  $('preview-file').addEventListener('click',()=>{if(selectedSource)openPreview(selectedSource.path);});
  $('download-project').addEventListener('click',async()=>{
    if(!state.chat)return;const button=$('download-project');button.disabled=true;
    try{const r=await fetch('/api/chats/'+state.chat.id+'/artifacts.zip',{headers:{'X-Console-Token':state.token}});if(!r.ok){const e=await r.json();throw new Error(e.error||'Could not download files');}saveBlob(await r.blob(),(state.chat.title||'collective-files').replace(/[^\w-]+/g,'-')+'.zip');}
    catch(e){notice(e.message);}finally{button.disabled=!state.chat?.workspace?.files.length;}
  });
  setInterval(updateProgressClock,1000);
}


// Organization console and chat orchestration UI.
'use strict';
const $ = id => document.getElementById(id);
const state = {token:null,roster:null,health:null,chats:[],chat:null,activity:null,view:'overview',chatSignature:'',activitySignature:'',pendingRequest:null};
const paths = {overview:'/',organization:'/organization',chat:'/chat',activity:'/activity',connectors:'/connectors',evaluations:'/evaluations'};
const labels = {overview:'Overview',organization:'Organization',chat:'Chat',activity:'Activity & evidence',connectors:'Connectors',evaluations:'Effectiveness'};
initChatWorkspace();
function element(tag,className,text){const node=document.createElement(tag);if(className)node.className=className;if(text!==undefined)node.textContent=text;return node;}
function pill(status){return element('span','state-pill '+status,status.replaceAll('_',' '));}
function action(label,handler,classes='btn btn-outline-secondary btn-sm'){const button=element('button',classes,label);button.type='button';button.addEventListener('click',handler);return button;}
function notice(message){$('notice').textContent=message;$('notice').classList.toggle('d-none',!message);}
async function api(path,body){
  const response=await fetch(path,{method:body===undefined?'GET':'POST',headers:{'X-Console-Token':state.token,...(body===undefined?{}:{'Content-Type':'application/json'})},body:body===undefined?undefined:JSON.stringify(body)});
  const result=await response.json();if(!response.ok)throw new Error(result.error||'Request failed');return result;
}
function navigate(view,push=true){state.view=view;document.body.classList.toggle('chat-view',view==='chat');document.querySelectorAll('.view').forEach(node=>node.classList.toggle('d-none',node.id!=='view-'+view));document.querySelectorAll('[data-nav]').forEach(node=>node.classList.toggle('active',node.dataset.nav===view));$('breadcrumb').textContent=labels[view];if(push)history.pushState({},'',paths[view]);if(view==='activity')refreshActivity();if(view==='connectors')refreshConnectors();if(view==='evaluations')refreshEvaluations();}
function newMission(){state.chat=null;state.chatSignature='';state.pendingRequest=null;inspectorChat=null;$('chat-inspector').open=false;document.body.classList.remove('inspector-open');sessionStorage.removeItem('collective-chat');renderChat();navigate('chat');$('mission-input').focus();}
function prettyAgent(id){return state.roster?.agents.find(agent=>agent.id===id)?.name||id;}
function modelSource(config){return !config?'Configuration source unavailable until server restart':config.credential_source==='environment'?'Server environment':config.credential_source==='saved_connector'?'Saved connector':'No credential detected';}
function requiresRestart(){return !!state.health&&!state.health.features?.chat_workspace;}
function renderHealth(){
  const h=state.health,c=h.model_configuration;
  const units=$('budget-tokens'),cap=h.limits?.max_admission_units_per_chat;
  if(cap){units.max=String(cap);if(Number(units.value)>cap)units.value=String(cap);}
  $('connection-status').textContent='Workspace connected · '+(h.version||'older server');
  document.querySelector('.version-label').textContent='COLLECTIVE 101 / '+(h.version||'older server');
  if(requiresRestart())notice('The running server is '+h.version+'. Restart through your secrets-manager launcher to activate the new chat and delivery fixes, then refresh. New requests are disabled until then.');
  $('metric-sandbox').textContent=h.sandbox.available?'Ready':'Setup needed';
  $('model-status').textContent=h.live_configured?'Model credential detected':'Connect a live model';
  $('model-description').textContent=h.live_configured?`${c?.model||'Live model'} · ${modelSource(c)}. Connection is checked when a request is sent.`:'Open Connectors to configure a model. No chat response can be generated without it.';
  $('mode-description').textContent=h.live_configured?`${c?.model||'Live model'} · ${modelSource(c)}. Head of Distribution receives your message first.`:c?.enabled===false?'Model disconnected. Open Connectors to enable it.':'Model not configured. Open Connectors to start.';
}
function renderModelConfiguration(){
  const c=state.health.model_configuration;
  const panel=$('model-configuration');panel.replaceChildren(element('h2','','Model configuration'));
  if(!c){panel.append(element('p','','Restart the local server to load model configuration details, then refresh this page.'));return;}
  panel.append(element('p','mb-2',`${c.enabled===false?'Disconnected':c.configured?'Credential detected':'Needs setup'} · ${c.model} · ${c.endpoint_host||'Endpoint not configured'}`),
    element('p','mb-2',`Credential source: ${modelSource(c)}. Settings: ${c.settings_source==='saved_connector'?'Saved connector':'Environment / defaults'}.`));
  if(c.credential_source==='environment')panel.append(element('p','small text-secondary','The running server received MODEL_API_KEY from its environment, which may be supplied by a secrets manager. The app cannot identify which extension supplied it.'));
  const p=c.request_policy||{};
  if(p.max_output_tokens)panel.append(element('p','small mb-2',`Generation cap: ${p.max_output_tokens.toLocaleString()} tokens per request, including reasoning. Work timeout: ${p.timeout_seconds} seconds; bounded retry timeout up to 300 seconds. Phase limits and shared mission budgets apply.`));
  panel.append(element('p','small text-secondary mb-0','Configuration presence is not a verified connection. Provider errors appear when a request is sent.'));
  if(c.error)panel.append(element('p','text-danger mb-0',c.error));
}
function renderChats(){
  const count=state.chats.filter(c=>['running','intake'].includes(c.status)).length;
  $('metric-active').replaceChildren(document.createTextNode(String(count)+' '),element('small','', 'in progress'));
  $('metric-runs').textContent=state.chats.length?`${state.chats.length} chats in this workspace`:'No chats started yet';
  if(state.chats.length){
    $('recent-missions').replaceChildren(...state.chats.map(c=>{const b=action(c.title||'Saved chat',()=>selectChat(c.id),'');b.title=c.title||'Saved chat';b.classList.toggle('selected',state.chat?.id===c.id);return b;}));
    $('mission-list').className='';$('mission-list').replaceChildren(...state.chats.slice(0,5).map(c=>{const button=action('',()=>selectChat(c.id),'mission-list-item');button.append(element('span','agent-avatar','↗'),element('strong','',c.title||'Saved chat'));return button;}));
  }
  const select=$('activity-mission');const old=select.value;select.replaceChildren(element('option','','Select a chat'));select.firstChild.value='';
  state.chats.filter(c=>c.run_id).forEach(c=>{const option=element('option','',c.title||'Saved chat');option.value=c.run_id;select.append(option);});
  select.value=old||state.chat?.run_id||'';
}
function showAgent(id){
  const agent=state.roster.agents.find(a=>a.id===id);const panel=$('agent-inspector');panel.classList.remove('d-none');
  const top=element('div','section-heading');top.append(element('h2','',agent.name),action('Close',()=>panel.classList.add('d-none')));
  const info=element('div','agent-details');info.append(element('p','',`${agent.id} · ${agent.department} · ${agent.role.replaceAll('_',' ')}`),element('p','',`Reports to: ${agent.reports_to?prettyAgent(agent.reports_to):'Mission owner'}`));
  if(agent.responsibility)info.append(element('p','',`Responsibility: ${agent.responsibility.level.replaceAll('_',' ')} | ${agent.responsibility.distinct_verified_missions} distinct verified live missions. Role and tool access are unchanged.`));
  agent.responsibilities.forEach(r=>info.append(element('p','',r)));
  info.append(element('strong','','Role instructions'),element('pre','',agent.system_prompt),element('p','',`Declared skills: ${agent.skills.join(', ')}. Tool access is enforced separately by the runtime.`));
  info.append(element('strong','','Eligible tools (assignment and mission permission still required)'));
  (agent.tools||[]).forEach(tool=>info.append(element('p','',`${tool.name}: ${tool.available?'ready':'unconfigured'} ? ${tool.scope}`)));
  info.append(element('p','',`Memory: stable role instructions, current mission context, and own reviewed episodes ranked by relevance. Knowledge files: shared/ and ${agent.department}/.`));
  info.append(action('View recorded activity',()=>{$('activity-agent').value=agent.id;navigate('activity');}));
  panel.replaceChildren(top,info);panel.focus();panel.scrollIntoView({block:'nearest',behavior:'smooth'});
}
function agentRow(agent){const row=element('div','agent-row');const copy=element('div');copy.append(element('strong','',agent.name),element('p','',agent.id+' · '+agent.role.replaceAll('_',' ')));row.append(element('span','agent-avatar',agent.name.split(' ').map(s=>s[0]).slice(0,2).join('')),copy,action('View role',()=>showAgent(agent.id)));return row;}
function showDepartment(department){
  $('agent-search').value='';$('department-grid').classList.add('d-none');const panel=$('search-results');panel.classList.remove('d-none');const heading=element('div','section-heading');heading.append(element('h2','',department.name),action('All departments',()=>{panel.classList.add('d-none');$('department-grid').classList.remove('d-none');}));panel.replaceChildren(heading,...state.roster.agents.filter(a=>a.department===department.id).map(agentRow));
}
function renderOrganization(){
  state.roster.agents.forEach(agent=>{const option=element('option','',agent.name+' ? '+agent.id);option.value=agent.id;$('activity-agent').append(option);});
  $('department-grid').replaceChildren(...state.roster.departments.map(department=>{
    const button=element('button','department-card');button.type='button';button.append(element('span','dept-code',department.id.toUpperCase()),element('h2','',department.name),element('p','',department.charter),element('small','',`${department.count} agents · 1 head →`));button.addEventListener('click',()=>showDepartment(department));return button;
  }));
}
function searchOrganization(){const query=$('agent-search').value.trim().toLowerCase();$('department-grid').classList.toggle('d-none',!!query);$('search-results').classList.toggle('d-none',!query);if(query){const matches=state.roster.agents.filter(a=>`${a.name} ${a.department} ${a.id} ${a.role}`.toLowerCase().includes(query));$('search-results').replaceChildren(element('h2','',`${matches.length} matching agents`),...matches.map(agentRow));}}
async function selectChat(id){try{state.chat=await api('/api/chats/'+id);sessionStorage.setItem('collective-chat',id);state.chatSignature='';renderChat();navigate('chat');if(state.chat.run_id)$('activity-mission').value=state.chat.run_id;}catch(error){notice(error.message);}}
function renderChat(){
  const chat=state.chat;const signature=JSON.stringify(chat);if(signature===state.chatSignature)return;state.chatSignature=signature;
  const busy=!!chat&&['intake','running','clarifying','needs_input','paused','interrupted'].includes(chat.status);$('send-mission').disabled=busy||requiresRestart();$('mission-input').placeholder=requiresRestart()?'Restart the server to activate this chat update':busy?'Your organization is working...':'Message your organization...';$('chat-status').textContent=chat?chat.status.replaceAll('_',' '):'Ready for a chat';
  const hint=chat?.progress?.label||'';$('chat-progress').classList.toggle('d-none',!hint);$('chat-progress-label').textContent=hint;
  const thread=$('chat-thread');const atBottom=thread.scrollHeight-thread.scrollTop-thread.clientHeight<70;
  const messages=$('chat-messages');
  const transcriptSignature=JSON.stringify([chat?.id,chat?.transcript,chat?.error]);
  if(messages.dataset.signature!==transcriptSignature){
    messages.dataset.signature=transcriptSignature;
  if(chat){messages.replaceChildren(...chat.transcript.map(message=>{const bubble=element('div','message '+message.role),body=element('div',message.role==='assistant'?'markdown-body':'message-content');const text=(message.display_content||message.content).replace(/^Mission brief:/,'Plan:');if(message.role==='assistant'&&typeof markdownFragment==='function')body.append(markdownFragment(text));else{body.classList.add('markdown-fallback');body.textContent=text;}bubble.append(element('span','message-label',message.role==='user'?'YOU':'COLLECTIVE'),body);return bubble;}));if(chat.error&&['blocked','interrupted'].includes(chat.status))messages.append(element('div','alert alert-danger',chat.error));
  }else{const welcome=element('div','chat-welcome');welcome.append(element('span','welcome-glyph','✳'),element('h2','','What do you want to accomplish?'),element('p','','Start with the outcome. If something important is missing, we’ll ask before proceeding.'));messages.replaceChildren(welcome);}
  }
  const interventions=$('intervention-area');interventions.replaceChildren();
  if(chat?.status==='clarifying')interventions.append(questionForm(chat.questions));
  if(chat?.status==='needs_input')chat.interventions.filter(q=>q.status==='pending').forEach(q=>interventions.append(questionForm([q.question],q)));
  $('brief-title').textContent=chat?.brief?'The agreed outcome':'Intent comes first.';
  const brief=$('brief-content');brief.replaceChildren();
  if(chat?.brief){brief.append(element('p','',chat.brief.objective));const criteria=element('ul');chat.brief.acceptance_criteria.forEach(c=>criteria.append(element('li','',c)));brief.append(element('strong','mini-label','SUCCESS CRITERIA'),criteria,element('p','text-secondary',`Mode: ${chat.mode==='fixture'?'Demo — scripted model responses':'Live Meta inference'}`));if(chat.run)brief.append(element('p','text-secondary',`${chat.run.calls} / ${chat.run.max_calls} model requests · ${chat.run.tokens} reported tokens`));}
  else brief.append(element('p','text-secondary','Your agreed objective and success criteria will appear here.'));
  if(chat?.brief)brief.append(element('p','',`Initially routed departments: ${chat.brief.departments?.join(', ')||'all (legacy chat)'}`));
  if(chat?.run?.result)brief.append(element('p','',`Working departments: ${chat.run.result.selected_departments.join(', ')}`));
  if(chat?.budget)brief.append(element('p','text-secondary',`${chat.budget.calls} / ${chat.budget.max_calls} total provider requests ? ${chat.budget.charged_tokens} / ${chat.budget.max_tokens} token admission units ? ${chat.budget.reported_tokens} reported tokens (intake included)`));
  renderWorkspace(chat);
  if(atBottom)thread.scrollTop=thread.scrollHeight;
  $('mission-controls').classList.toggle('d-none',!chat?.run_id);$('pause-mission').classList.toggle('d-none',chat?.status!=='running');$('resume-mission').classList.toggle('d-none',!['paused','interrupted'].includes(chat?.status));
}
function questionForm(questions,intervention=null){
  const form=element('form','intervention');form.append(element('h3','',intervention?`${prettyAgent(intervention.agent_id)} needs your guidance`:'Head of Distribution asks'));
  if(intervention)form.append(element('p','',intervention.reason));
  const fields=questions.map((question,i)=>{const label=element('label','',question);const textarea=element('textarea','form-control');textarea.rows=2;textarea.required=true;textarea.maxLength=4000;textarea.id=`answer-${intervention?.id||'intake'}-${i}`;label.htmlFor=textarea.id;form.append(label,textarea);return textarea;});
  if(intervention?.options.length)form.append(element('p','mt-2 text-secondary','Suggested answers: '+intervention.options.join(' · ')));
  if(!intervention && state.chat?.intake?.output?.reason)form.append(element('p','text-secondary',state.chat.intake.output.reason));
  const button=element('button','btn btn-primary','Answer & continue →');button.type='submit';form.append(button);
  form.addEventListener('submit',async event=>{event.preventDefault();button.disabled=true;try{const answers=fields.map(f=>f.value.trim());state.chat=await api('/api/chats/'+state.chat.id+'/answers',{answers:intervention?answers[0]:answers,intervention_id:intervention?.id});renderChat();notice('');}catch(error){notice(error.message);button.disabled=false;}});return form;
}
async function refreshActivity(){
  const id=$('activity-mission').value;if(!id)return;
  try{const data=await api('/api/activity/'+id);const signature=id+$('activity-filter').value+$('activity-agent').value+JSON.stringify(data);if(signature===state.activitySignature)return;state.activitySignature=signature;state.activity=data;renderActivity(data,id);}catch(error){notice(error.message);}
}
function detail(title,status,content,subtitle){const item=element('details','activity-item');item.dataset.key=title;const summary=element('summary');summary.append(pill(status),element('strong','',title));if(subtitle)summary.append(element('small','',subtitle));item.append(summary,element('pre','',typeof content==='string'?content:JSON.stringify(content,null,2)));return item;}
function renderActivity(data,id){
  data={...data,tools:data.tools||[]};
  const selected=$('activity-agent').value;
  if(selected)data={tools:data.tools.filter(t=>t.agent_id===selected),calls:data.calls.filter(c=>c.agent_id===selected),messages:data.messages.filter(m=>m.sender===selected||m.recipient===selected),artifacts:data.artifacts.filter(a=>a.agent_id===selected),executions:data.executions.filter(e=>data.artifacts.some(a=>a.path===e.path&&a.agent_id===selected))};
  const chat=state.chats.find(c=>c.run_id===id);$('activity-mode').textContent=chat?.mode==='fixture'?'Demo · no AI inference':'Live Meta';
  $('activity-summary').textContent=`${data.calls.length} recorded model actions · ${data.messages.length} leadership handoffs · ${data.artifacts.length} artifacts · ${data.executions.length} sandbox executions ? ${data.tools.length} tool requests`;
  const filter=$('activity-filter').value;let nodes=[];
  if(filter==='calls')nodes=data.calls.slice().reverse().map(c=>detail(`${prettyAgent(c.agent_id)} · ${c.phase}`,c.status,{result:c.output||c.error||'Provider request is in progress.',failure_kind:c.error_kind||undefined,request_limits:typeof c.request_options==='string'?JSON.parse(c.request_options):c.request_options||undefined},c.agent_id+' · '+new Date(c.created_at).toLocaleTimeString()));
  if(filter==='messages')nodes=data.messages.slice().reverse().map(m=>detail(`${prettyAgent(m.sender)} → ${prettyAgent(m.recipient)}`,'recorded',m.content,m.kind));
  if(filter==='artifacts')nodes=data.artifacts.map(a=>{const item=detail(a.path,'produced',a.content,prettyAgent(a.agent_id));item.append(action('Download artifact',()=>{const blob=new Blob([a.content],{type:'text/plain'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=a.path.split('/').pop();link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);},'btn btn-outline-secondary btn-sm mt-2'));return item;});
  if(filter==='tools')nodes=data.tools.slice().reverse().map((t,i)=>detail(`${prettyAgent(t.agent_id)} ? ${t.name} ? ${i}`,t.result.status,{arguments:t.arguments,result:t.result},new Date(t.created_at).toLocaleTimeString()));
  if(filter==='executions')nodes=data.executions.map(e=>detail(e.path,e.result.passed?'passed':'failed',e.result,'Observed execution: '+(e.result.engine||'QuickJS/WebAssembly')));
  const panel=$('activity-content');const expanded=new Set([...panel.querySelectorAll('details[open]')].map(n=>n.dataset.key));nodes.forEach(n=>{if(expanded.has(n.dataset.key))n.open=true;});panel.className='panel';panel.replaceChildren(...(nodes.length?nodes:[element('p','text-secondary mb-0','No '+filter+' recorded for this chat yet.')]));
}
const examples={website:'Build a website for a neighborhood coffee shop. Include a menu, opening hours and location, with an accessible mobile-friendly layout and launch documentation.',calculator:'Build and test a pure JavaScript calculator add(a,b) function. It should handle positive numbers, negative numbers and zero. Include source files and operations documentation.',research:'Compare three ways to improve onboarding documentation for a small software team. Use supplied observations, explain assumptions and provide a decision brief and summary.'};
document.querySelectorAll('[data-nav]').forEach(link=>link.addEventListener('click',event=>{event.preventDefault();navigate(link.dataset.nav);}));
document.querySelectorAll('[data-goto]').forEach(link=>link.addEventListener('click',event=>{event.preventDefault();navigate(link.dataset.goto);}));
document.querySelectorAll('.new-mission').forEach(button=>button.addEventListener('click',newMission));
document.querySelectorAll('.starter').forEach(button=>button.addEventListener('click',()=>{newMission();$('mission-input').value=examples[button.dataset.example];growComposer();}));
$('start-chat').addEventListener('click',newMission);$('inspect-director').addEventListener('click',()=>showAgent('director-001'));$('agent-search').addEventListener('input',searchOrganization);
function growComposer(){const input=$('mission-input');input.style.height='auto';input.style.height=Math.min(Math.max(input.scrollHeight,48),200)+'px';input.style.overflowY=input.scrollHeight>200?'auto':'hidden';}
$('mission-input').addEventListener('input',()=>{state.pendingRequest=null;growComposer();});
$('mission-input').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();if(!$('send-mission').disabled)$('mission-form').requestSubmit();}});
for(const id of ['budget-calls','budget-tokens'])$(id).addEventListener('change',()=>state.pendingRequest=null);
$('mission-form').addEventListener('submit',async event=>{event.preventDefault();$('send-mission').disabled=true;try{if(requiresRestart())throw new Error('Restart through your secrets-manager launcher, then refresh before sending a new request.');const message=$('mission-input').value.trim();if(state.chat&&['answered','reviewed','blocked'].includes(state.chat.status)){state.chat=await api('/api/chats/'+state.chat.id+'/messages',{message});}else{state.pendingRequest??=crypto.randomUUID();state.chat=await api('/api/chats',{message,mode:'meta',request_id:state.pendingRequest,max_calls:Number($('budget-calls').value),max_tokens:Number($('budget-tokens').value)});}sessionStorage.setItem('collective-chat',state.chat.id);$('mission-input').value='';growComposer();state.pendingRequest=null;renderChat();notice('');await refresh();}catch(error){notice(error.message);}finally{$('send-mission').disabled=requiresRestart()||(!!state.chat&&['intake','running','clarifying','needs_input','paused','interrupted'].includes(state.chat.status));}});
$('activity-agent').addEventListener('change',refreshActivity);$('activity-mission').addEventListener('change',refreshActivity);$('activity-filter').addEventListener('change',refreshActivity);
$('view-evidence').addEventListener('click',()=>{$('activity-mission').value=state.chat.run_id;navigate('activity');});
for(const [id,actionName] of [['pause-mission','pause'],['resume-mission','resume']])$(id).addEventListener('click',async()=>{try{state.chat=await api('/api/chats/'+state.chat.id+'/control',{action:actionName});renderChat();if(actionName==='pause')$(id).textContent='Pause requested…';}catch(error){notice(error.message);}});
window.addEventListener('popstate',()=>navigate(Object.keys(paths).find(k=>paths[k]===location.pathname)||'overview',false));
let refreshing=false;
async function refresh(){if(refreshing)return;refreshing=true;try{state.chats=await api('/api/chats');renderChats();if(state.chat){state.chat=await api('/api/chats/'+state.chat.id);renderChat();}if(state.view==='activity')await refreshActivity();if(state.view==='evaluations')await refreshEvaluations();$('connection-status').textContent='Workspace connected';}catch(error){$('connection-status').textContent='Connection interrupted';}finally{refreshing=false;}}
(async()=>{try{state.token=(await (await fetch('/api/session')).json()).token;[state.roster,state.health]=await Promise.all([api('/api/organization'),api('/api/health')]);renderHealth();renderOrganization();await refresh();const saved=sessionStorage.getItem('collective-chat');if(saved&&state.chats.some(c=>c.id===saved)){state.chat=await api('/api/chats/'+saved);}renderChat();navigate(Object.keys(paths).find(k=>paths[k]===location.pathname)||'overview',false);setInterval(refresh,1500);document.documentElement.dataset.ready='true';}catch(error){notice('Could not connect to the local console: '+error.message);$('connection-status').textContent='Offline';}})();

const connectorCatalog = [
  {id:'gmail',name:'Gmail',icon:'G',tone:'mail',description:'Email context, conversations and follow-ups.',soon:true},
  {id:'slack',name:'Slack',icon:'#',tone:'slack',description:'Team conversations, project context and updates.',soon:true},
  {id:'canva',name:'Canva',icon:'C',tone:'canva',description:'Design assets, presentations and visual content.',soon:true},
  {id:'github',name:'GitHub',icon:'GH',tone:'github',description:'Repositories, issues, pull requests and code context.',soon:true},
  {id:'drive',name:'Google Drive',icon:'D',tone:'drive',description:'Shared documents, project files and team knowledge.',soon:true},
  {id:'calendar',name:'Google Calendar',icon:'31',tone:'calendar',description:'Schedules, availability and project milestones.',soon:true},
  {id:'meta',name:'Live model',icon:'AI',tone:'model',description:'The model powering your 101-agent organization.',kind:'meta'},
  {id:'brave',name:'Web search',icon:'W',tone:'search',description:'Find public sources with Brave Search.',kind:'brave'},
  {id:'mcp',name:'Custom MCP',icon:'<>',tone:'mcp',description:'Connect a compatible server and its read-only tools.',kind:'mcp'},
];
let connectorFilter='all', savedConnectors=[], connectorOpener=null;
function renderConnectorCatalog(){
  const query=$('connector-search').value.trim().toLowerCase();
  const items=connectorCatalog.filter(c=>(connectorFilter==='all'||(connectorFilter==='soon')===!!c.soon)&&(c.name+' '+c.description).toLowerCase().includes(query));
  $('connector-catalog').replaceChildren(...items.map(c=>{
    const card=element('article','connector-card');card.dataset.connector=c.id;
    const icon=element('span','connector-icon '+c.tone,c.icon);icon.setAttribute('aria-hidden','true');
    const body=element('div','connector-card-copy');body.append(element('h2','',c.name),element('p','',c.description));
    const bottom=element('div','connector-card-footer');
    if(c.soon){bottom.append(element('span','connector-badge coming-soon','Coming soon'));}
    else {
      const saved=c.kind==='mcp'?null:savedConnectors.find(x=>x.kind===c.kind);
      const configured=c.kind==='meta'?state.health.live_configured:!!saved?.enabled;
      bottom.append(element('span','connector-badge',configured?(c.kind==='meta'?'Credential detected':'Configured'):'Available now'));
      const button=action(saved?'Manage':'Set up',()=>{connectorOpener=button;editConnector(saved||{kind:c.kind,name:c.name,url:c.kind==='meta'?'https://api.meta.ai/v1':''});},'btn btn-outline-secondary btn-sm');
      button.setAttribute('aria-label',(saved?'Manage ':'Set up ')+c.name);bottom.append(button);
    }
    card.append(icon,body,bottom);return card;
  }));
  $('connector-empty').classList.toggle('d-none',items.length>0);
}
function connectorFields(){
  const kind=$('connector-kind').value;
  $('connector-url-field').classList.toggle('d-none',kind==='brave');$('connector-url').required=kind!=='brave';
  $('connector-model-field').classList.toggle('d-none',kind!=='meta');$('connector-local-field').classList.toggle('d-none',kind!=='mcp');
  $('connector-model-limits').classList.toggle('d-none',kind!=='meta');
  for(const id of ['connector-max-output','connector-timeout','connector-temperature'])$(id).disabled=kind!=='meta';
  $('connector-setup-title').textContent='Set up '+(kind==='meta'?'Live model':kind==='brave'?'Web search':'Custom MCP');
  $('connector-kind-help').textContent=kind==='mcp'?'Save your server, discover its tools, then enable the read-only tools you want to share with all agents.':kind==='brave'?'Save your key to enable web search across the organization. Agents search when their mission and task call for it.':'Save your model settings, then send a message in Chat to verify the connection.';
  $('save-connector').textContent=kind==='brave'?'Save and enable':'Save connection';
}
function closeConnector(){
  $('connector-secret').value='';$('connector-setup').classList.add('d-none');
  if(connectorOpener?.isConnected)connectorOpener.focus();else $('connector-search').focus();
}
function editConnector(c){
  $('connector-form').reset();$('connector-id').value=c.id||'';$('connector-kind').value=c.kind;
  $('connector-name').value=c.name;$('connector-url').value=c.url||'';$('connector-model').value=c.model||'';
  $('connector-max-output').value=c.model_options?.max_output_tokens??'';$('connector-timeout').value=c.model_options?.timeout_seconds??'';
  $('connector-temperature').value=c.model_options?.temperature??'';
  $('connector-max-output').placeholder=String(state.health.model_configuration?.request_policy?.max_output_tokens||32768);
  $('connector-timeout').placeholder=String(state.health.model_configuration?.request_policy?.timeout_seconds||120);
  $('connector-secret').value='';$('connector-local').checked=!!c.allow_local;connectorFields();
  $('connector-setup').classList.remove('d-none');$('connector-name').focus();
}
async function refreshConnectorState(){[state.health,state.roster]=await Promise.all([api('/api/health'),api('/api/organization')]);renderHealth();await refreshConnectors();}
async function connectorAction(c,actionName,payload={},button){
  if(button)button.disabled=true;
  try{await api('/api/connectors/'+c.id+'/'+actionName,payload);notice('');await refreshConnectorState();}
  catch(error){notice(error.message);await refreshConnectors();}
  finally{if(button)button.disabled=false;}
}
function connectionPanel(c){
  const panel=element('article','panel mb-3');panel.dataset.connection=c.id;
  const title=element('div','section-heading');title.append(element('h3','',c.name),pill(c.kind==='meta'&&!state.health.live_configured?'needs_setup':c.enabled?'enabled':'disabled'));
  panel.append(title,element('p','small text-secondary',c.has_secret?'Credential saved securely.':'No saved credential; environment settings may apply.'));
  if(c.kind!=='meta')panel.append(element('p','small','Shared with all 101 agents. Used within mission and task permissions.'));
  if(c.error)panel.append(element('p','text-danger',c.error));
  const buttons=element('div','d-flex gap-2 flex-wrap');
  const edit=action('Edit settings',()=>{connectorOpener=edit;editConnector(c);});buttons.append(edit);
  if(c.kind==='mcp')buttons.append(action('Discover / refresh tools',event=>connectorAction(c,'discover',{},event.currentTarget)));
  if(c.enabled)buttons.append(action('Disconnect',event=>connectorAction(c,'disable',{},event.currentTarget)));
  if(c.kind==='brave'&&!c.enabled)buttons.append(action('Enable search',event=>connectorAction(c,'enable',{tools:['web_search']},event.currentTarget)));
  panel.append(buttons);
  if(c.kind==='mcp'&&c.tools.length){
    const tools=element('details','connector-tool-details');tools.append(element('summary','',`${c.tools.length} discovered tools - review access`));
    const checks=[];
    for(const tool of c.tools){
      const label=element('label','d-block mb-2 mt-2');const checkbox=element('input');checkbox.type='checkbox';checkbox.checked=c.selected.includes(tool.key);checkbox.disabled=!tool.read_only;
      label.append(checkbox,document.createTextNode(' '+tool.name+(tool.read_only?'':' - unavailable: write or unknown access')));tools.append(label);checks.push({checkbox,key:tool.key});
      const info=element('details','small mb-2');info.append(element('summary','','Description & arguments'),element('pre','',JSON.stringify({description:tool.description,inputSchema:tool.inputSchema},null,2)));tools.append(info);
    }
    tools.append(action('Enable selected tools',event=>connectorAction(c,'enable',{tools:checks.filter(t=>t.checkbox.checked).map(t=>t.key)},event.currentTarget),'btn btn-primary btn-sm mt-2'));panel.append(tools);
  }
  return panel;
}
async function refreshConnectors(){
  renderConnectorCatalog();
  try{[savedConnectors,state.health]=await Promise.all([api('/api/connectors'),api('/api/health')]);renderHealth();renderModelConfiguration();renderConnectorCatalog();$('connector-list').replaceChildren(...(savedConnectors.length?savedConnectors.map(connectionPanel):[element('p','connector-empty-connections',state.health.model_configuration?.configured?'No saved connections. The model credential comes from the server environment.':'No saved connections yet. Choose an available card above to get started.')]));}
  catch(error){notice(error.message);const retry=action('Retry loading connections',refreshConnectors);$('connector-list').replaceChildren(element('p','','Could not load your connections.'),retry);}
}
$('connector-search').addEventListener('input',renderConnectorCatalog);
document.querySelectorAll('[data-connector-filter]').forEach(button=>button.addEventListener('click',()=>{
  connectorFilter=button.dataset.connectorFilter;
  document.querySelectorAll('[data-connector-filter]').forEach(b=>{const selected=b===button;b.classList.toggle('active',selected);b.setAttribute('aria-pressed',String(selected));});renderConnectorCatalog();
}));
$('close-connector').addEventListener('click',closeConnector);
$('connector-setup').addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();closeConnector();}});
$('connector-form').addEventListener('submit',async event=>{
  event.preventDefault();const button=$('save-connector');button.disabled=true;
  try{
    const model_options={};
    if($('connector-kind').value==='meta'){
      if($('connector-max-output').value)model_options.max_output_tokens=Number($('connector-max-output').value);
      if($('connector-timeout').value)model_options.timeout_seconds=Number($('connector-timeout').value);
      if($('connector-temperature').value)model_options.temperature=Number($('connector-temperature').value);
    }
    const result=await api('/api/connectors',{id:$('connector-id').value||undefined,kind:$('connector-kind').value,name:$('connector-name').value.trim(),url:$('connector-url').value.trim(),model:$('connector-model').value.trim(),secret:$('connector-secret').value,allow_local:$('connector-local').checked,model_options});
    $('connector-secret').value='';$('connector-id').value=result.id;
    if(result.kind==='brave')await api('/api/connectors/'+result.id+'/enable',{tools:['web_search']});
    closeConnector();notice('');await refreshConnectorState();
  }catch(error){notice(error.message);}finally{button.disabled=false;}
});

$('knowledge-form').addEventListener('submit',async event=>{
  event.preventDefault();const file=$('knowledge-file').files[0];if(!file)return;
  $('knowledge-upload').disabled=true;
  try{if(file.size>65536)throw new Error('Document exceeds 64 KiB');const content=await file.text();const result=await api('/api/knowledge',{filename:file.name,content});$('knowledge-result').textContent='Added '+result.path+' to shared knowledge.';$('knowledge-form').reset();notice('');}
  catch(error){notice(error.message);}finally{$('knowledge-upload').disabled=false;}
});
