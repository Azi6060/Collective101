'use strict';
let selectedSource=null,progressStarted=null,inspectorChat=null,previewOpening=false,previewChat=null;
const phaseLabels={help_decision:'Reviewing a request for help',help:'Consulting another department',replan:'Revising the team',assess:'Assessing the task',coordinate:'Aligning the departments',select:'Selecting the team',work:'Creating the deliverable',report:'Gathering saved work',review_assignment:'Assigning a reviewer',review:'Checking the result',retrospective:'Preparing your result'};
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
  $('workspace-file-count').textContent=String(w.files.length);
  $('workspace-state').textContent=chat?.status==='reviewed'?'Reviewed':chat?.status==='running'?'Working':chat?.status==='blocked'?'Needs attention':'';
  $('changes-summary').replaceChildren(element('span','lines-added','+'+t.added),element('span','lines-removed','−'+t.removed));
  $('changes-summary').setAttribute('aria-label',`${t.added} lines added, ${t.removed} lines removed in saved files`);
  $('workspace-counts').textContent=t.files?`${t.files} files · ${t.code_lines??t.lines} lines of code · saved changes`:'Files appear as agents save them.';
  $('download-project').disabled=!t.files;
  const preview=w.preview;
  $('preview-project').disabled=previewOpening||!preview?.ready||!state.health?.features?.site_preview;
  $('preview-status').textContent=!state.health?.features?.site_preview?'Restart the local server to enable website previews.':preview?.reason||'No HTML page has been saved yet. Preview becomes available when agents create one.';
  if(previewChat!==chat?.id){previewChat=chat?.id;$('preview-link').classList.add('d-none');$('preview-link').removeAttribute('href');}
  const filter=$('workspace-file-search').value.trim().toLowerCase();
  const signature=JSON.stringify([w.files.map(f=>[f.path,f.sha256]),w.events,w.failures,filter]);
  if($('workspace-files').dataset.signature!==signature){
    $('workspace-files').dataset.signature=signature;
    $('workspace-files').replaceChildren(...w.files.filter(file=>file.path.toLowerCase().includes(filter)).map(file=>{const row=element('div','workspace-file-row');const b=action('',()=>showSource(file),'workspace-file');b.append(element('span','file-path',file.path),element('span','file-meta',`${file.lines} lines`));b.title=`View ${file.path} source`;row.append(b);if(/\.html?$/i.test(file.path)){const p=action('↗',()=>openPreview(file.path),'workspace-action file-preview');p.setAttribute('aria-label',`Preview ${file.path} in a new tab`);p.title=p.getAttribute('aria-label');row.append(p);}return row;}));
    if(filter&&!$('workspace-files').children.length)$('workspace-files').append(element('p','workspace-muted',window.CollectivePreferences?.t('No matching files.')||'No matching files.'));
    $('workspace-events').replaceChildren(...(w.events.length?w.events.slice(-6).reverse().map(e=>{const row=element('div','workspace-event '+e.status);row.append(element('span','event-mark',e.status==='accepted'?'✓':e.status==='failed'?'!':'·'),element('span','',`${prettyAgent(e.agent_id)} · ${phaseLabels[e.phase]||e.phase}`));return row;}):[element('p','workspace-muted','No actions yet.')]));
    $('workspace-failures').replaceChildren(...w.failures.slice(-8).reverse().map(f=>{const row=element('div','failure-record');row.append(element('strong','',`${f.kind||'Task'}${f.agent_id?' · '+prettyAgent(f.agent_id):''}`),element('p','',f.reason||'No diagnostic recorded.'));if(f.request_options)row.append(element('small','',`Output: ${f.request_options.max_tokens.toLocaleString()} · timeout: ${f.request_options.timeout}s`));return row;}));
  }
  $('workspace-failure-details').classList.toggle('d-none',!w.failures.length);
  if(chat?.run_id&&inspectorChat!==chat.id){inspectorChat=chat.id;if(innerWidth>=1280){$('chat-inspector').open=true;document.body.classList.add('inspector-open');}}
  const limits=state.health?.limits,p=state.health?.model_configuration?.request_policy;
  $('chat-limits-info').replaceChildren();
  if(chat?.context)$('chat-limits-info').append(element('p','',`${chat.context.saved_messages} messages saved · ${chat.context.history_bytes.toLocaleString()} bytes in the current history window${chat.context.history_compacted?' · earlier turns windowed':''}`));
  if(chat?.context?.last_request?.input_tokens)$('chat-limits-info').append(element('p','',`${chat.context.last_request.input_tokens.toLocaleString()} input tokens measured for the last large request; output space and a prompt margin are reserved.`));
  if(limits){
    for(const line of [`Message: ${limits.message_characters.toLocaleString()} characters`,`Per-request input: ${limits.request_input_bytes.toLocaleString()} UTF-8 bytes (conservative admission)`,
      `Chat history window sent: ${limits.history_window_bytes.toLocaleString()} bytes; full history remains saved`,
      limits.provider_context_tokens?`Model context window: ${limits.provider_context_tokens.toLocaleString()} tokens`:'Model context window: provider-dependent',
      `Output cap: ${(p?.max_output_tokens||65536).toLocaleString()} tokens, including reasoning`,`Temperature: ${p?.temperature??1} · high reasoning for all agents`,
      `Retries per step: ${limits.provider_failures_per_step} provider failures, ${limits.truncations_per_step} truncations, ${limits.validation_failures_per_step} validation failures; ${limits.requests_per_step} requests maximum`,
      `Repair rounds: ${limits.repair_rounds_default} by default, ${limits.repair_rounds_max} maximum; usage recorded; aggregate spending unlimited`])$('chat-limits-info').append(element('p','',line));
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
function initChatWorkspace(){
  const header=document.querySelector('.app-header');
  const sizeHeader=()=>{if(header.offsetHeight)document.documentElement.style.setProperty('--header-height',header.offsetHeight+'px');};
  sizeHeader();if(window.ResizeObserver)new ResizeObserver(sizeHeader).observe(header);else addEventListener('resize',sizeHeader);
  document.addEventListener('click',event=>{if(!$('chat-history').contains(event.target))closeChatHistory();});
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&$('chat-history').open){event.preventDefault();closeChatHistory(true);}});
  $('chat-inspector').addEventListener('toggle',()=>document.body.classList.toggle('inspector-open',$('chat-inspector').open));
  document.querySelectorAll('[data-workspace-tab]').forEach(button=>button.addEventListener('click',()=>workspaceTab(button.dataset.workspaceTab)));
  document.querySelector('.workspace-tabs').addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const names=['files','references','activity'],current=names.indexOf(document.activeElement.dataset.workspaceTab),next=event.key==='Home'?0:event.key==='End'?2:(current+(event.key==='ArrowRight'?(document.documentElement.dir==='rtl'?2:1):(document.documentElement.dir==='rtl'?1:2)))%3;workspaceTab(names[next]);$('workspace-tab-'+names[next]).focus();});
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
const t = text => window.CollectivePreferences?.t(text)||text;
const state = {token:null,roster:null,health:null,chats:[],chat:null,activity:null,view:'home',chatSignature:'',activitySignature:'',pendingRequest:null,sending:false,selectedAgent:null};
let draftContext='new',restoringDraft=false,draftRecoveryBlocked=false,draftStorageNotice=false,selectionEpoch=0;
function rememberedChat(value){try{if(value===undefined)return sessionStorage.getItem('collective-chat');if(value===null)sessionStorage.removeItem('collective-chat');else sessionStorage.setItem('collective-chat',value);}catch{return null;}}
function saveDraft(){if(restoringDraft||draftRecoveryBlocked)return;window.CollectiveDrafts?.save(draftContext,$('mission-input').value,window.CollectiveChatInputs?.ids()||[],state.chat?.agent_id||state.selectedAgent);if(window.CollectiveDrafts&&!window.CollectiveDrafts.available()&&!draftStorageNotice){draftStorageNotice=true;window.CollectiveWorkspaceTools?.toast(t('Draft recovery is unavailable in this browser. Keep this tab open.'));}}
async function restoreDraft(context){
  restoringDraft=true;draftRecoveryBlocked=false;$('retry-draft-recovery').hidden=true;draftContext=context;const version=selectionEpoch,saved=window.CollectiveDrafts?.get(context);
  if(context==='new')state.selectedAgent=state.roster?.agents.some(agent=>agent.id===saved?.agentId)?saved.agentId:null;
  $('mission-input').value=saved?.text||'';state.pendingRequest=saved?.request?.id||null;$('draft-recovery').hidden=!saved;
  $('draft-recovery-message').textContent=t('Draft restored.');
  try{if(saved?.attachments.length){const missing=await window.CollectiveChatInputs?.restore(saved.attachments);if(version!==selectionEpoch)return;if(missing)$('draft-recovery-message').textContent=t('Some attachments expired. Attach them again.');}}
  catch(error){if(version===selectionEpoch){draftRecoveryBlocked=true;$('retry-draft-recovery').hidden=false;$('draft-recovery').hidden=false;$('draft-recovery-message').textContent=t('Could not restore attachments. Check your connection before sending.');notice(error.message);}}
  finally{if(version===selectionEpoch){restoringDraft=false;saveDraft();growComposer();updateSendAvailability();}}
}
const paths = {home:'/',overview:'/dashboard',organization:'/organization',chat:'/chat',activity:'/activity',connectors:'/connectors',settings:'/settings'};
const labels = {home:'Home',overview:'Dashboard',organization:'Organization',chat:'Chat',activity:'Activity & evidence',connectors:'Connectors',settings:'Settings'};
initChatWorkspace();
function workspaceTab(name){for(const value of ['files','references','activity']){const button=$('workspace-tab-'+value),active=value===name;button.setAttribute('aria-selected',String(active));button.tabIndex=active?0:-1;$('workspace-panel-'+value).hidden=!active;}}
function updateSendAvailability(){const busy=!!state.chat&&['intake','running','clarifying','needs_input','paused','interrupted'].includes(state.chat.status);$('send-mission').disabled=!state.health||busy||state.sending||restoringDraft||draftRecoveryBlocked||requiresRestart()||!!window.CollectiveChatInputs?.busy();$('mission-input').readOnly=state.sending||restoringDraft||draftRecoveryBlocked;}
function element(tag,className,text){const node=document.createElement(tag);if(className)node.className=className;if(text!==undefined)node.textContent=text;return node;}
function pill(status){return element('span','state-pill '+status,status.replaceAll('_',' '));}
function action(label,handler,classes='btn btn-outline-secondary btn-sm'){const button=element('button',classes,label);button.type='button';button.addEventListener('click',handler);return button;}
function notice(message){$('notice-message').textContent=message;$('notice').classList.toggle('d-none',!message);}
async function api(path,body){
  const response=await fetch(path,{method:body===undefined?'GET':'POST',headers:{'X-Console-Token':state.token,...(body===undefined?{}:{'Content-Type':'application/json'})},body:body===undefined?undefined:JSON.stringify(body)});
  const result=await response.json();if(response.status===401)window.CollectiveAccounts?.expire();if(!response.ok)throw new Error(result.error||'Request failed');return result;
}
function closeChatHistory(restoreFocus=false){const history=$('chat-history');if(!history.open)return;const focused=history.contains(document.activeElement)&&document.activeElement.tagName!=='SUMMARY';history.open=false;if(restoreFocus||focused)history.querySelector('summary').focus({preventScroll:true});}
function navigate(view,push=true){const connectors=view==='connectors';if(connectors)view='settings';if(window.CollectiveAccounts?.locked()&&view!=='home'){window.CollectiveAccounts.open('signin');return;}if(view!=='chat')window.CollectiveChatInputs?.stop();closeChatHistory();state.view=view;document.body.classList.toggle('chat-view',view==='chat');document.querySelectorAll('.view').forEach(node=>node.classList.toggle('d-none',node.id!=='view-'+view));document.querySelectorAll('[data-nav]').forEach(node=>{const parent=node.dataset.nav==='settings'&&view==='connectors',active=node.dataset.nav===view||parent;node.classList.toggle('active',active);if(active)node.setAttribute('aria-current',parent?'location':'page');else node.removeAttribute('aria-current');});$('breadcrumb').textContent=t(labels[view]);if(push){history.pushState({},'',paths[view]);document.documentElement.scrollTop=0;document.body.scrollTop=0;}if(view==='activity')refreshActivity();if(view==='settings')refreshConnectors();if(connectors)requestAnimationFrame(()=>$('view-connectors').scrollIntoView({block:'start'}));}
function newMission(){saveDraft();selectionEpoch++;restoringDraft=true;workspaceTab('files');window.CollectiveChatInputs?.selecting();window.CollectiveChatInputs?.clear(false);state.chat=null;state.selectedAgent=null;state.chatSignature='';state.pendingRequest=null;inspectorChat=null;$('workspace-file-search').value='';$('chat-inspector').open=false;document.body.classList.remove('inspector-open');rememberedChat(null);restoreDraft('new');renderChat();navigate('chat');$('mission-input').focus();}
function prettyAgent(id){return state.roster?.agents.find(agent=>agent.id===id)?.name||id;}
function modelSource(config){return !config?'Configuration source unavailable until server restart':config.credential_source==='environment'?'Server environment':config.credential_source==='saved_connector'?'Saved connector':'No credential detected';}
function requiresRestart(){return !!state.health&&(!state.health.features?.chat_workspace||!state.health.features?.orbital_workspace||!state.health.features?.mission_studio||!state.health.features?.visual_workspace||!state.health.features?.chat_inputs||!state.health.features?.local_accounts||!state.health.features?.workspace_tools||!state.health.features?.structured_output||!state.health.features?.media_previews||!state.health.features?.agent_chat);}
function renderHealth(){
  const h=state.health,c=h.model_configuration;

  if(requiresRestart())notice('The running server is '+h.version+'. Restart through your secrets-manager launcher to activate the new chat and delivery fixes, then refresh. New requests are disabled until then.');
  $('metric-sandbox').textContent=t(h.sandbox.available?'Ready':'Setup needed');
  $('model-status').textContent=t(h.live_configured?'Live model configured':'Connect a live model');
  $('model-description').textContent=h.live_configured?`${c?.model||'Live model'} · ${modelSource(c)}. Send a message to verify the connection.`:'Add a model in Connectors to start receiving replies.';
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
  if(p.max_output_tokens)panel.append(element('p','small mb-2',`Generation cap: ${p.max_output_tokens.toLocaleString()} tokens per request, including reasoning. Work timeout: ${p.timeout_seconds} seconds; bounded retry timeout up to 900 seconds. Per-request and loop safety bounds apply; aggregate spending is unlimited.`));
  panel.append(element('p','small text-secondary mb-0','Configuration presence is not a verified connection. Provider errors appear when a request is sent.'));
  if(c.error)panel.append(element('p','text-danger mb-0',c.error));
}
function renderChats(){
  window.CollectiveDashboard?.render(state);
  const recent=$('recent-missions'),signature=JSON.stringify([state.chats.map(c=>[c.id,c.title]),state.chat?.id,document.documentElement.lang]);
  if(window.CollectiveWorkspaceTools)window.CollectiveWorkspaceTools.render(state.chats,state.chat?.id);
  else
  if(recent.dataset.signature!==signature){
    const focused=recent.contains(document.activeElement)?document.activeElement.dataset.chatId:null;
    recent.dataset.signature=signature;
    recent.replaceChildren(...(state.chats.length?state.chats.map(c=>{const b=action(c.title||t('Saved chat'),()=>selectChat(c.id),'');b.title=c.title||t('Saved chat');b.dataset.chatId=c.id;b.classList.toggle('selected',state.chat?.id===c.id);if(state.chat?.id===c.id)b.setAttribute('aria-current','true');return b;}):[element('p','history-empty',t('No chats started yet'))]));
    if(focused)[...recent.querySelectorAll('button')].find(node=>node.dataset.chatId===focused)?.focus({preventScroll:true});
  }
  const select=$('activity-mission');const old=select.value;select.replaceChildren(element('option','','Select a chat'));select.firstChild.value='';
  state.chats.filter(c=>c.run_id).forEach(c=>{const option=element('option','',c.title||'Saved chat');option.value=c.run_id;select.append(option);});
  select.value=old||state.chat?.run_id||'';
}
let agentOpener=null;
function closeAgent(){const panel=$('agent-inspector');panel.classList.add('d-none');if(agentOpener?.isConnected)agentOpener.focus();}
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&state.view==='organization'&&!$('agent-inspector').classList.contains('d-none'))closeAgent();});
function showAgent(id){
  agentOpener=document.activeElement;
  const agent=state.roster.agents.find(a=>a.id===id),panel=$('agent-inspector');panel.classList.remove('d-none');
  const department=state.roster.departments.find(d=>d.id===agent.department);
  const top=element('div','section-heading');top.append(element('h2','',agent.name),action('Close',closeAgent));
  const info=element('div','agent-details');info.append(element('p','agent-department',department?.name||'Organization leadership'),element('p','',agent.charter));
  const duties=element('ul','agent-responsibilities');for(const r of agent.responsibilities)duties.append(element('li','',r));info.append(duties);
  info.append(element('p','agent-reporting',agent.reports_to?'Works with '+prettyAgent(agent.reports_to):'Coordinates department heads'));
  const tools=(agent.tools||[]).filter(t=>t.available);info.append(element('p','text-secondary',tools.length?tools.length+' connected capabilities available when assigned to relevant work.':'Can reason and draft from supplied information.'));
  info.append(action('Chat with '+agent.name,()=>startAgentChat(agent.id),'btn btn-primary'),element('p','small text-secondary mt-2','Ask about this agent specialty. Use organization chat for coordinated work and saved deliverables.'));
  panel.replaceChildren(top,info);panel.focus();panel.scrollIntoView({block:'nearest',behavior:'smooth'});
}
function startAgentChat(id){newMission();state.selectedAgent=id;renderAgentContext();saveDraft();$('mission-input').focus();}
function renderAgentContext(){const id=state.chat?.agent_id||state.selectedAgent;$('agent-chat-context').hidden=!id;$('agent-chat-name').textContent=id?prettyAgent(id):'';if(id)$('mission-input').placeholder='Message '+prettyAgent(id)+'...';else if(!state.chat||['answered','reviewed','blocked'].includes(state.chat.status))$('mission-input').placeholder=t('Message your organization...');}
function agentRow(agent){const row=element('div','agent-row');const copy=element('div');copy.append(element('strong','',agent.name),element('p','',agent.id+' · '+agent.role.replaceAll('_',' ')));row.append(element('span','agent-avatar',agent.name.split(' ').map(s=>s[0]).slice(0,2).join('')),copy,action('View role',()=>showAgent(agent.id)));return row;}
function showDepartment(department){
  if(window.CollectiveExplorer){window.CollectiveExplorer.selectDepartment(department.id);return;}
  $('agent-search').value='';$('department-grid').classList.add('d-none');const panel=$('search-results');panel.classList.remove('d-none');const heading=element('div','section-heading');heading.append(element('h2','',department.name),action('All departments',()=>{panel.classList.add('d-none');$('department-grid').classList.remove('d-none');}));panel.replaceChildren(heading,...state.roster.agents.filter(a=>a.department===department.id).map(agentRow));
}
function renderOrganization(){
  state.roster.agents.forEach(agent=>{const option=element('option','',agent.name+' · '+agent.id);option.value=agent.id;$('activity-agent').append(option);});
  $('department-grid').replaceChildren(...state.roster.departments.map(department=>{
    const button=element('button','department-card');button.type='button';button.dataset.department=department.id;const emblem=element('span','department-emblem');if(window.CollectiveMissionUI)emblem.append(window.CollectiveMissionUI.icon(department.id));button.append(emblem,element('span','dept-code',department.id.toUpperCase()),element('h2','',department.name),element('p','',department.charter),element('small','',`${department.count} agents · 1 head →`));button.addEventListener('click',()=>showDepartment(department));return button;
  }));
  window.CollectiveExplorer?.init(state.roster,{showAgent,showDepartment});
}
function searchOrganization(){const query=$('agent-search').value.trim().toLowerCase();$('department-grid').classList.toggle('d-none',!!query);$('search-results').classList.toggle('d-none',!query);if(query){const matches=state.roster.agents.filter(a=>`${a.name} ${a.department} ${a.id} ${a.role}`.toLowerCase().includes(query));$('search-results').replaceChildren(element('h2','',`${matches.length} matching agents`),...matches.map(agentRow));if(!matches.length&&window.CollectiveVisuals)$('search-results').append(window.CollectiveVisuals.empty('search','A different perspective?','No agents match this search. Try a department, role or name.'));}window.CollectiveExplorer?.search();}
async function selectChat(id,query=''){saveDraft();const version=++selectionEpoch;window.CollectiveChatInputs?.selecting();try{const chat=await api('/api/chats/'+id);if(version!==selectionEpoch)return;restoringDraft=true;window.CollectiveChatInputs?.clear(false);state.chat=chat;state.selectedAgent=chat.agent_id||null;rememberedChat(id);state.chatSignature='';$('workspace-file-search').value=query;await restoreDraft(id);if(version!==selectionEpoch)return;renderChat();navigate('chat');if(query){workspaceTab(chat.attachments?.some(file=>file.name.toLowerCase().includes(query.toLowerCase()))?'references':'files');$('chat-inspector').open=true;document.body.classList.add('inspector-open');}if(state.chat.run_id)$('activity-mission').value=state.chat.run_id;return chat;}catch(error){notice(error.message);}}
function renderChat(){
  const chat=state.chat;const signature=JSON.stringify(chat);if(signature===state.chatSignature)return;state.chatSignature=signature;
  const busy=!!chat&&['intake','running','clarifying','needs_input','paused','interrupted'].includes(chat.status);updateSendAvailability();$('mission-input').placeholder=t(requiresRestart()?'Restart the server to activate this chat update':busy?'Your organization is working...':'Message your organization...');$('chat-status').textContent=chat?chat.status.replaceAll('_',' '):t('Ready for a chat');
  renderAgentContext();
  const hint=chat?.progress?.label||'';$('chat-progress').classList.toggle('d-none',!hint);$('chat-progress-label').textContent=hint;
  const thread=$('chat-thread');const atBottom=thread.scrollHeight-thread.scrollTop-thread.clientHeight<70;
  const messages=$('chat-messages');
  const transcriptSignature=JSON.stringify([chat?.id,chat?.transcript,chat?.error,chat?.attachments]);
  if(messages.dataset.signature!==transcriptSignature){
    messages.dataset.signature=transcriptSignature;
  if(chat){
    if(messages.dataset.chatId!==chat.id){messages.replaceChildren();messages.dataset.chatId=chat.id;}
    chat.transcript.forEach((message,index)=>{const signature=JSON.stringify(message),existing=messages.children[index];if(existing?.dataset.message===signature)return;
      const bubble=element('div','message '+message.role),body=element('div',message.role==='assistant'?'markdown-body':'message-content');bubble.dataset.messageIndex=String(index);body.dir='auto';const text=(message.display_content||message.content).replace(/^Mission brief:/,'Plan:');if(message.role==='assistant'&&typeof markdownFragment==='function')body.append(markdownFragment(text));else{body.classList.add('markdown-fallback');body.textContent=text;}bubble.append(element('span','message-label',message.role==='user'?'YOU':chat.agent_id?prettyAgent(chat.agent_id):'COLLECTIVE'),body);bubble.dataset.message=signature;if(existing)existing.replaceWith(bubble);else messages.append(bubble);
    });
    while(messages.children.length>chat.transcript.length)messages.lastElementChild.remove();
    if(chat.error&&['blocked','interrupted'].includes(chat.status))messages.append(element('div','alert alert-danger',chat.error));
  }else{const welcome=element('div','chat-welcome');welcome.append(element('span','welcome-glyph','COLLECTIVE / 101'),element('h2','',t('What can we work on?')),element('p','',t('Describe an outcome, ask a question, or bring us your next idea.')));const choices=element('div','welcome-pills');for(const [key,label] of [['website','Build a website'],['research','Explore a decision'],['calculator','Test JavaScript']])choices.append(action(t(label),()=>{$('mission-input').value=examples[key];state.pendingRequest=null;growComposer();$('mission-input').focus();},'btn'));welcome.append(choices);messages.replaceChildren(welcome);}
  }
  const interventions=$('intervention-area');interventions.replaceChildren();
  if(chat?.status==='clarifying')interventions.append(questionForm(chat.questions));
  if(chat?.status==='needs_input')chat.interventions.filter(q=>q.status==='pending').forEach(q=>interventions.append(questionForm([q.question],q)));
  $('brief-title').textContent=chat?.brief?'The agreed outcome':'Intent comes first.';
  const brief=$('brief-content');brief.replaceChildren();
  if(chat?.brief){brief.append(element('p','',chat.brief.objective));const criteria=element('ul');chat.brief.acceptance_criteria.forEach(c=>criteria.append(element('li','',c)));brief.append(element('strong','mini-label','SUCCESS CRITERIA'),criteria,element('p','text-secondary',`Mode: ${chat.mode==='fixture'?'Demo — scripted model responses':'Live Meta inference'}`));if(chat.run)brief.append(element('p','text-secondary',`${chat.run.calls} model requests · ${chat.run.tokens} reported tokens`));}
  else brief.append(element('p','text-secondary','Your agreed objective and success criteria will appear here.'));
  if(chat?.brief)brief.append(element('p','',`Initially routed departments: ${chat.brief.departments?.join(', ')||'all (legacy chat)'}`));
  if(chat?.run?.result)brief.append(element('p','',`Working departments: ${chat.run.result.selected_departments.join(', ')}`));
  if(chat?.budget)brief.append(element('p','text-secondary',`${chat.budget.calls} total provider requests · ${chat.budget.reported_tokens.toLocaleString()} reported tokens (intake included)`));
  renderWorkspace(chat);
  renderMissionPresentation(chat);
  window.CollectiveChatInputs?.onChat(chat,state.view);
  if(atBottom)thread.scrollTop=thread.scrollHeight;
  $('mission-controls').classList.toggle('d-none',!chat?.run_id);$('pause-mission').classList.toggle('d-none',chat?.status!=='running');$('resume-mission').classList.toggle('d-none',!['paused','interrupted'].includes(chat?.status));
}
window.CollectiveThumbnails?.configure((cid,entry)=>api('/api/chats/'+cid+'/thumbnail',{entry}));
function renderMissionPresentation(chat){window.CollectiveMissionUI?.render(chat,state.roster,{showSource,openPreview,previewAvailable:!!state.health?.features?.site_preview,thumbnailsAvailable:!!state.health?.features?.site_thumbnails&&!!state.health?.execution?.browser?.available,downloadFile:file=>saveBlob(new Blob([file.content],{type:'text/plain;charset=utf-8'}),file.path.split('/').pop()),viewEvidence:()=>{$('activity-mission').value=chat.run_id;navigate('activity');}});}
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
  const id=$('activity-mission').value;if(!id){state.activitySignature='';state.activity=null;$('activity-summary').textContent='No mission selected';$('activity-mode').textContent='';if(window.CollectiveVisuals)$('activity-content').replaceChildren(window.CollectiveVisuals.empty('activity','A clear record of the work.','Choose a mission to explore its actions, handoffs and saved evidence.'));return;}
  try{const data=await api('/api/activity/'+id);const signature=id+$('activity-filter').value+$('activity-agent').value+JSON.stringify(data);if(signature===state.activitySignature)return;state.activitySignature=signature;state.activity=data;renderActivity(data,id);}catch(error){notice(error.message);}
}
function activityTime(value){const date=new Date(value);return Number.isNaN(date.getTime())?'Recorded':new Intl.DateTimeFormat(document.documentElement.lang,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}).format(date);}
function detail(title,status,content,subtitle){const item=element('details','activity-item timeline-entry');item.dataset.key=title;const summary=element('summary'),copy=element('span','timeline-copy');copy.append(element('strong','',title));if(subtitle)copy.append(element('small','',subtitle));const marker=element('span','timeline-marker');marker.setAttribute('aria-hidden','true');marker.textContent=status==='failed'?'!':'↗';summary.append(marker,copy,pill(status));const body=element('div','timeline-evidence');body.append(element('p','timeline-evidence-label','Recorded evidence'),element('pre','',typeof content==='string'?content:JSON.stringify(content,null,2)));item.append(summary,body);return item;}
function renderActivity(data,id){
  data={...data,tools:data.tools||[]};
  const selected=$('activity-agent').value;
  if(selected)data={tools:data.tools.filter(t=>t.agent_id===selected),calls:data.calls.filter(c=>c.agent_id===selected),messages:data.messages.filter(m=>m.sender===selected||m.recipient===selected),artifacts:data.artifacts.filter(a=>a.agent_id===selected),executions:data.executions.filter(e=>data.artifacts.some(a=>a.path===e.path&&a.agent_id===selected))};
  const chat=state.chats.find(c=>c.run_id===id);$('activity-mode').textContent=chat?.mode==='fixture'?'Demo · no AI inference':'Live Meta';
  $('activity-summary').textContent=`${data.calls.length} recorded model actions · ${data.messages.length} leadership handoffs · ${data.artifacts.length} artifacts · ${data.executions.length} sandbox executions · ${data.tools.length} tool requests`;
  const filter=$('activity-filter').value;let nodes=[];
  if(filter==='calls')nodes=data.calls.slice().reverse().map(c=>detail(`${prettyAgent(c.agent_id)} · ${phaseLabels[c.phase]||c.phase.replaceAll('_',' ')}`,c.status,{result:c.output||c.error||'Provider request is in progress.',failure_kind:c.error_kind||undefined,request_limits:typeof c.request_options==='string'?JSON.parse(c.request_options):c.request_options||undefined},activityTime(c.created_at)));
  if(filter==='messages')nodes=data.messages.slice().reverse().map(m=>detail(`${prettyAgent(m.sender)} → ${prettyAgent(m.recipient)}`,'recorded',m.content,m.kind));
  if(filter==='artifacts')nodes=data.artifacts.map(a=>{const item=detail(a.path,'produced',a.content,prettyAgent(a.agent_id));item.append(action('Download artifact',()=>{const blob=new Blob([a.content],{type:'text/plain'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=a.path.split('/').pop();link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);},'btn btn-outline-secondary btn-sm mt-2'));return item;});
  if(filter==='tools')nodes=data.tools.slice().reverse().map((t,i)=>detail(`${prettyAgent(t.agent_id)} · ${t.name} · ${i+1}`,t.result.status,{arguments:t.arguments,result:t.result},activityTime(t.created_at)));
  if(filter==='executions')nodes=data.executions.map(e=>detail(e.path,e.result.passed?'passed':'failed',e.result,'Observed execution: '+(e.result.engine||'QuickJS/WebAssembly')));
  const panel=$('activity-content');const expanded=new Set([...panel.querySelectorAll('details[open]')].map(n=>n.dataset.key));nodes.forEach(n=>{if(expanded.has(n.dataset.key))n.open=true;});panel.className='panel activity-timeline';panel.replaceChildren(...(nodes.length?nodes:[window.CollectiveVisuals?window.CollectiveVisuals.empty('activity','The story is still unfolding.','No '+filter+' recorded for this chat yet.'):element('p','text-secondary mb-0','No '+filter+' recorded for this chat yet.')]));
}
if(window.CollectiveVisuals)$('activity-content').replaceChildren(window.CollectiveVisuals.empty('activity','A clear record of the work.','Choose a mission to explore its actions, handoffs and saved evidence.'));
const examples={website:'Build a website for a neighborhood coffee shop. Include a menu, opening hours and location, with an accessible mobile-friendly layout and launch documentation.',calculator:'Build and test a pure JavaScript calculator add(a,b) function. It should handle positive numbers, negative numbers and zero. Include source files and operations documentation.',research:'Compare three ways to improve onboarding documentation for a small software team. Use supplied observations, explain assumptions and provide a decision brief and summary.'};
document.querySelectorAll('[data-nav],[data-goto]').forEach(link=>link.addEventListener('click',event=>{if(event.ctrlKey||event.metaKey||event.shiftKey||event.altKey||event.button>0)return;event.preventDefault();navigate(link.dataset.nav||link.dataset.goto);}));
document.querySelectorAll('.new-mission').forEach(button=>button.addEventListener('click',newMission));
$('inspect-director').addEventListener('click',()=>showAgent('director-001'));$('agent-search').addEventListener('input',searchOrganization);
window.CollectiveDashboard?.init({newMission,selectChat,navigate,growComposer});
const clearPrivateDrafts=()=>{window.CollectiveDrafts?.purge();window.CollectiveChatInputs?.clear(false);};
window.CollectiveAccounts?.init({api,openSettings:()=>navigate('settings'),signedIn:()=>{clearPrivateDrafts();location.assign('/dashboard');},signedOut:()=>{clearPrivateDrafts();location.assign('/');},expired:()=>{clearPrivateDrafts();location.replace('/');},revalidate:()=>location.reload()});
window.CollectiveWorkspaceTools?.init({api,chat:()=>state.chat,selectChat,renamed:async result=>{state.chats=state.chats.map(chat=>chat.id===result.id?{...chat,title:result.title}:chat);if(state.chat?.id===result.id){state.chat.title=result.title;state.chatSignature='';renderChat();}renderChats();}});
window.CollectiveChatInputs?.init({api,growComposer,token:()=>state.token,expired:()=>window.CollectiveAccounts?.expire(),changed:()=>{updateSendAvailability();growComposer();},draftChanged:()=>{if(!restoringDraft){state.pendingRequest=null;saveDraft();}updateSendAvailability();growComposer();},resource:async path=>{const response=await fetch(path,{headers:{'X-Console-Token':state.token}});if(response.status===401)window.CollectiveAccounts?.expire();if(!response.ok)throw new Error('Could not load this attachment. Sign in and try again.');return response.blob();},save:saveBlob});
$('dismiss-notice').addEventListener('click',()=>notice(''));
$('workspace-file-search').addEventListener('input',()=>{renderWorkspace(state.chat);window.CollectiveChatInputs?.onChat(state.chat,state.view);});
$('discard-draft').addEventListener('click',()=>{restoringDraft=true;draftRecoveryBlocked=false;window.CollectiveDrafts?.remove(draftContext);window.CollectiveChatInputs?.clear();$('mission-input').value='';state.pendingRequest=null;$('draft-recovery').hidden=true;restoringDraft=false;updateSendAvailability();growComposer();$('mission-input').focus();});
$('retry-draft-recovery').addEventListener('click',()=>{notice('');restoreDraft(draftContext);});
$('dashboard-input').addEventListener('input',()=>window.CollectiveDrafts?.save('dashboard',$('dashboard-input').value));
$('dashboard-mission').addEventListener('submit',()=>{window.CollectiveDrafts?.remove('dashboard');saveDraft();});
window.addEventListener('pagehide',saveDraft);

window.addEventListener('collective-preferences-change',()=>{
  if(!state.health)return;
  renderHealth();window.CollectiveDashboard?.render(state);$('breadcrumb').textContent=t(labels[state.view]);
  renderMissionPresentation(state.chat);
  if(!state.chat){state.chatSignature='';$('chat-messages').dataset.signature='';renderChat();}
  growComposer();
});
function growComposer(){const input=$('mission-input');input.style.height='auto';input.style.height=Math.min(Math.max(input.scrollHeight,48),Math.max(64,Math.min(200,innerHeight-document.querySelector('.app-header').offsetHeight-200-(window.CollectiveChatInputs?.reserve()||0))))+'px';input.style.overflowY=input.scrollHeight>200?'auto':'hidden';}
$('mission-input').addEventListener('input',()=>{state.pendingRequest=null;saveDraft();growComposer();});
$('mission-input').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();if(!$('send-mission').disabled)$('mission-form').requestSubmit();}});
$('mission-form').addEventListener('submit',async event=>{
  event.preventDefault();if(state.sending)return;$('send-mission').disabled=true;
  const context=draftContext,version=selectionEpoch;
  try{
    if(requiresRestart())throw new Error('Restart the server, then refresh before sending a new request.');
    if(draftRecoveryBlocked||restoringDraft)throw new Error('Restore or discard this draft before sending.');
    if(window.CollectiveChatInputs?.busy())throw new Error('Finish voice input or file uploads before sending.');
    const attachments=window.CollectiveChatInputs?.ids()||[],message=$('mission-input').value.trim()||(attachments.length?'Please review the attached files.':'');
    if(!message)throw new Error('Write a message or attach a file before sending.');
    const followup=state.chat&&['answered','reviewed','blocked'].includes(state.chat.status),path=followup?'/api/chats/'+state.chat.id+'/messages':'/api/chats';
    const payload={message,attachments,...(followup?{}:{mode:'meta',agent_id:state.selectedAgent})};
    state.pendingRequest=window.CollectiveDrafts?.request(context,{path,...payload})||state.pendingRequest||crypto.randomUUID();
    state.sending=true;updateSendAvailability();window.CollectiveChatInputs?.available(false);window.CollectiveChatInputs?.beginMessage();
    const result=await api(path,{...payload,request_id:state.pendingRequest});window.CollectiveDrafts?.remove(context);
    if(version===selectionEpoch){restoringDraft=true;state.chat=result;rememberedChat(result.id);$('mission-input').value='';window.CollectiveChatInputs?.sent();draftContext=result.id;state.pendingRequest=null;restoringDraft=false;$('draft-recovery').hidden=true;growComposer();renderChat();notice('');}
    await refresh();
  }catch(error){notice(error.message);}finally{state.sending=false;window.CollectiveChatInputs?.available(!!state.health?.features?.chat_inputs);updateSendAvailability();}
});
$('activity-agent').addEventListener('change',refreshActivity);$('activity-mission').addEventListener('change',refreshActivity);$('activity-filter').addEventListener('change',refreshActivity);
$('view-evidence').addEventListener('click',()=>{$('activity-mission').value=state.chat.run_id;navigate('activity');});
for(const [id,actionName] of [['pause-mission','pause'],['resume-mission','resume']])$(id).addEventListener('click',async()=>{try{state.chat=await api('/api/chats/'+state.chat.id+'/control',{action:actionName});renderChat();if(actionName==='pause')$(id).textContent='Pause requested…';}catch(error){notice(error.message);}});
function locationView(){return Object.keys(paths).find(k=>paths[k]===location.pathname)||'home';}
window.addEventListener('popstate',()=>navigate(locationView(),false));
let refreshing=false;
async function refresh(){if(refreshing)return;refreshing=true;try{state.chats=await api('/api/chats');renderChats();if(state.chat){state.chat=await api('/api/chats/'+state.chat.id);renderChat();}if(state.view==='activity')await refreshActivity();$('connection-alert').hidden=true;}catch(error){$('connection-alert').textContent=t('Connection interrupted');$('connection-alert').hidden=false;}finally{refreshing=false;}}
(async()=>{try{
  state.token=(await (await fetch('/api/session')).json()).token;
  if(window.CollectiveAccounts){await window.CollectiveAccounts.load();if(window.CollectiveAccounts.locked()){window.CollectiveDrafts?.purge();state.roster=await api('/api/about');window.CollectiveDashboard?.render(state);navigate('home',false);document.documentElement.dataset.ready='true';return;}}
  window.CollectiveDrafts?.configure(window.CollectiveAccounts?.user()?.id||'guest');
  $('dashboard-input').value=window.CollectiveDrafts?.get('dashboard')?.text||'';
  [state.roster,state.health]=await Promise.all([api('/api/organization'),api('/api/health')]);renderHealth();
  $('history-search').disabled=!state.health.features?.workspace_tools;
  window.CollectiveChatInputs?.available(!!state.health.features?.chat_inputs);renderOrganization();await refresh();
  const saved=rememberedChat();if(saved&&state.chats.some(chat=>chat.id===saved))state.chat=await api('/api/chats/'+saved);
  await restoreDraft(state.chat?.id||'new');renderChat();window.CollectiveWorkspaceTools?.render(state.chats,state.chat?.id);navigate(locationView(),false);setInterval(refresh,1500);document.documentElement.dataset.ready='true';
}catch(error){notice('Could not connect to the local console: '+error.message);}})();

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
    const icon=element('span','connector-icon '+c.tone);icon.setAttribute('aria-hidden','true');if(window.CollectiveVisuals)icon.append(window.CollectiveVisuals.serviceIcon(c.id));else icon.textContent=c.icon;
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
  if(!items.length&&window.CollectiveVisuals)$('connector-empty').replaceChildren(window.CollectiveVisuals.empty('connections','The right connection is out there.','No connectors match your search. Try another name.'));
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
  $('connector-max-output').placeholder=String(state.health.model_configuration?.request_policy?.max_output_tokens||65536);
  $('connector-timeout').placeholder=String(state.health.model_configuration?.request_policy?.timeout_seconds||600);
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

$('organization-chat').addEventListener('click',()=>{const message=$('mission-input').value||state.chat?.transcript.filter(m=>m.role==='user').at(-1)?.content||'';newMission();state.selectedAgent=null;$('mission-input').value=message;renderAgentContext();saveDraft();growComposer();});
