'use strict';
const $ = id => document.getElementById(id);
const state = {token:null,roster:null,health:null,chats:[],chat:null,activity:null,view:'overview',chatSignature:'',activitySignature:'',pendingRequest:null};
const paths = {overview:'/',organization:'/organization',chat:'/chat',activity:'/activity',connectors:'/connectors'};
const labels = {overview:'Overview',organization:'Organization',chat:'Mission chat',activity:'Activity & evidence',connectors:'Connectors'};
function element(tag,className,text){const node=document.createElement(tag);if(className)node.className=className;if(text!==undefined)node.textContent=text;return node;}
function pill(status){return element('span','state-pill '+status,status.replaceAll('_',' '));}
function action(label,handler,classes='btn btn-outline-secondary btn-sm'){const button=element('button',classes,label);button.type='button';button.addEventListener('click',handler);return button;}
function notice(message){$('notice').textContent=message;$('notice').classList.toggle('d-none',!message);}
async function api(path,body){
  const response=await fetch(path,{method:body===undefined?'GET':'POST',headers:{'X-Console-Token':state.token,...(body===undefined?{}:{'Content-Type':'application/json'})},body:body===undefined?undefined:JSON.stringify(body)});
  const result=await response.json();if(!response.ok)throw new Error(result.error||'Request failed');return result;
}
function navigate(view,push=true){state.view=view;document.body.classList.toggle('chat-view',view==='chat');document.querySelectorAll('.view').forEach(node=>node.classList.toggle('d-none',node.id!=='view-'+view));document.querySelectorAll('[data-nav]').forEach(node=>node.classList.toggle('active',node.dataset.nav===view));$('breadcrumb').textContent=labels[view];if(push)history.pushState({},'',paths[view]);if(view==='activity')refreshActivity();if(view==='connectors')refreshConnectors();}
function newMission(){state.chat=null;state.chatSignature='';state.pendingRequest=null;sessionStorage.removeItem('collective-chat');renderChat();navigate('chat');$('mission-input').focus();}
function prettyAgent(id){return state.roster?.agents.find(agent=>agent.id===id)?.name||id;}
function renderHealth(){const h=state.health;$('connection-status').textContent='Workspace connected ? '+(h.version||'older server');$('metric-sandbox').textContent=h.sandbox.available?'Ready':'Setup needed';$('model-status').textContent=h.live_configured?'Live model configured':'Connect a live model';$('model-description').textContent=h.live_configured?'Messages are sent to the live Head of Distribution. Provider errors are shown without a scripted fallback.':'Open Connectors to configure a model. No chat response can be generated without it.';$('mode-description').textContent=h.live_configured?'Live model ? Head of Distribution receives your message first.':'Model not configured. Open Connectors to start.';}
function renderChats(){
  const count=state.chats.filter(c=>['running','intake'].includes(c.status)).length;
  $('metric-active').replaceChildren(document.createTextNode(String(count)+' '),element('small','', 'in progress'));
  $('metric-runs').textContent=state.chats.length?`${state.chats.length} missions in this workspace`:'No missions started yet';
  if(state.chats.length){
    $('recent-missions').replaceChildren(...state.chats.slice(0,8).map(c=>action(c.id.slice(-6)+' · '+c.status,()=>selectChat(c.id),'')));
    $('mission-list').className='';$('mission-list').replaceChildren(...state.chats.slice(0,5).map(c=>{const button=action('',()=>selectChat(c.id),'mission-list-item');button.append(element('span','agent-avatar','↗'),element('strong','',c.id),pill(c.status));return button;}));
  }
  const select=$('activity-mission');const old=select.value;select.replaceChildren(element('option','','Select a mission'));select.firstChild.value='';
  state.chats.filter(c=>c.run_id).forEach(c=>{const option=element('option','',`${c.id.slice(-6)} · ${c.mode} · ${c.status}`);option.value=c.run_id;select.append(option);});
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
  const busy=!!chat&&['intake','running','clarifying','needs_input','paused','interrupted'].includes(chat.status);$('send-mission').disabled=busy;$('mission-input').placeholder=busy?'Your organization is working...':'Message your organization...';$('chat-status').textContent=chat?chat.status.replaceAll('_',' '):'Ready for a mission';
  const hint=chat?.progress?.label||'';$('chat-progress').classList.toggle('d-none',!hint);$('chat-progress-label').textContent=hint;
  const thread=$('chat-thread');const atBottom=thread.scrollHeight-thread.scrollTop-thread.clientHeight<70;
  const messages=$('chat-messages');
  const transcriptSignature=JSON.stringify([chat?.id,chat?.transcript,chat?.error]);
  if(messages.dataset.signature!==transcriptSignature){
    messages.dataset.signature=transcriptSignature;
  if(chat){messages.replaceChildren(...chat.transcript.map(message=>{const bubble=element('div','message '+message.role);bubble.append(element('span','message-label',message.role==='user'?'YOU':chat.run_id?'ORGANIZATION':'HEAD OF DISTRIBUTION'),document.createTextNode(message.content));return bubble;}));if(chat.error)messages.append(element('div','alert alert-danger',chat.error));
  }else{const welcome=element('div','chat-welcome');welcome.append(element('span','welcome-glyph','✳'),element('h2','','What do you want to accomplish?'),element('p','','Start with the outcome. If something important is missing, we’ll ask before proceeding.'));messages.replaceChildren(welcome);}
  }
  const interventions=$('intervention-area');interventions.replaceChildren();
  if(chat?.status==='clarifying')interventions.append(questionForm(chat.questions));
  if(chat?.status==='needs_input')chat.interventions.filter(q=>q.status==='pending').forEach(q=>interventions.append(questionForm([q.question],q)));
  $('brief-title').textContent=chat?.brief?'The agreed outcome':'Intent comes first.';
  const brief=$('brief-content');brief.replaceChildren();
  if(chat?.brief){brief.append(element('p','',chat.brief.objective));const criteria=element('ul');chat.brief.acceptance_criteria.forEach(c=>criteria.append(element('li','',c)));brief.append(element('strong','mini-label','SUCCESS CRITERIA'),criteria,element('p','text-secondary',`Mode: ${chat.mode==='fixture'?'Demo — scripted model responses':'Live Meta inference'}`));if(chat.run)brief.append(element('p','text-secondary',`${chat.run.calls} / ${chat.run.max_calls} model requests · ${chat.run.tokens} reported tokens`));}
  else brief.append(element('p','text-secondary','Your agreed objective and success criteria will appear here.'));
  if(chat?.brief)brief.append(element('p','',`Initially routed departments: ${chat.brief.departments?.join(', ')||'all (legacy mission)'}`));
  if(chat?.run?.result)brief.append(element('p','',`Working departments: ${chat.run.result.selected_departments.join(', ')}`));
  if(chat?.budget)brief.append(element('p','text-secondary',`${chat.budget.calls} / ${chat.budget.max_calls} total provider requests ? ${chat.budget.charged_tokens} / ${chat.budget.max_tokens} token admission units ? ${chat.budget.reported_tokens} reported tokens (intake included)`));
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
  if(filter==='calls')nodes=data.calls.slice().reverse().map(c=>detail(`${prettyAgent(c.agent_id)} · ${c.phase}`,c.status,c.output||c.error||'Provider request is in progress.',c.agent_id+' ? '+new Date(c.created_at).toLocaleTimeString()));
  if(filter==='messages')nodes=data.messages.slice().reverse().map(m=>detail(`${prettyAgent(m.sender)} → ${prettyAgent(m.recipient)}`,'recorded',m.content,m.kind));
  if(filter==='artifacts')nodes=data.artifacts.map(a=>{const item=detail(a.path,'produced',a.content,prettyAgent(a.agent_id));item.append(action('Download artifact',()=>{const blob=new Blob([a.content],{type:'text/plain'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=a.path.split('/').pop();link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);},'btn btn-outline-secondary btn-sm mt-2'));return item;});
  if(filter==='tools')nodes=data.tools.slice().reverse().map((t,i)=>detail(`${prettyAgent(t.agent_id)} ? ${t.name} ? ${i}`,t.result.status,{arguments:t.arguments,result:t.result},new Date(t.created_at).toLocaleTimeString()));
  if(filter==='executions')nodes=data.executions.map(e=>detail(e.path,e.result.passed?'passed':'failed',e.result,'Observed execution: '+(e.result.engine||'QuickJS/WebAssembly')));
  const panel=$('activity-content');const expanded=new Set([...panel.querySelectorAll('details[open]')].map(n=>n.dataset.key));nodes.forEach(n=>{if(expanded.has(n.dataset.key))n.open=true;});panel.className='panel';panel.replaceChildren(...(nodes.length?nodes:[element('p','text-secondary mb-0','No '+filter+' recorded for this mission yet.')]));
}
const examples={website:'Build a website for a neighborhood coffee shop. Include a menu, opening hours and location, with an accessible mobile-friendly layout and launch documentation.',calculator:'Build and test a pure JavaScript calculator add(a,b) function. It should handle positive numbers, negative numbers and zero. Include source files and operations documentation.',research:'Compare three ways to improve onboarding documentation for a small software team. Use supplied observations, explain assumptions and provide a decision brief and summary.'};
document.querySelectorAll('[data-nav]').forEach(link=>link.addEventListener('click',event=>{event.preventDefault();navigate(link.dataset.nav);}));
document.querySelectorAll('.new-mission').forEach(button=>button.addEventListener('click',newMission));
document.querySelectorAll('.starter').forEach(button=>button.addEventListener('click',()=>{newMission();$('mission-input').value=examples[button.dataset.example];growComposer();}));
$('start-chat').addEventListener('click',newMission);$('inspect-director').addEventListener('click',()=>showAgent('director-001'));$('agent-search').addEventListener('input',searchOrganization);
function growComposer(){const input=$('mission-input');input.style.height='auto';input.style.height=Math.min(Math.max(input.scrollHeight,48),200)+'px';input.style.overflowY=input.scrollHeight>200?'auto':'hidden';}
$('mission-input').addEventListener('input',()=>{state.pendingRequest=null;growComposer();});
$('mission-input').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();if(!$('send-mission').disabled)$('mission-form').requestSubmit();}});
for(const id of ['budget-calls','budget-tokens'])$(id).addEventListener('change',()=>state.pendingRequest=null);
$('mission-form').addEventListener('submit',async event=>{event.preventDefault();$('send-mission').disabled=true;try{const message=$('mission-input').value.trim();if(state.chat?.status==='answered'&&!state.chat.run_id){state.chat=await api('/api/chats/'+state.chat.id+'/messages',{message});}else{state.pendingRequest??=crypto.randomUUID();state.chat=await api('/api/chats',{message,mode:'meta',request_id:state.pendingRequest,max_calls:Number($('budget-calls').value),max_tokens:Number($('budget-tokens').value)});}sessionStorage.setItem('collective-chat',state.chat.id);$('mission-input').value='';growComposer();state.pendingRequest=null;renderChat();notice('');await refresh();}catch(error){notice(error.message);}finally{$('send-mission').disabled=!!state.chat&&['intake','running','clarifying','needs_input','paused','interrupted'].includes(state.chat.status);}});
$('activity-agent').addEventListener('change',refreshActivity);$('activity-mission').addEventListener('change',refreshActivity);$('activity-filter').addEventListener('change',refreshActivity);
$('view-evidence').addEventListener('click',()=>{$('activity-mission').value=state.chat.run_id;navigate('activity');});
for(const [id,actionName] of [['pause-mission','pause'],['resume-mission','resume']])$(id).addEventListener('click',async()=>{try{state.chat=await api('/api/chats/'+state.chat.id+'/control',{action:actionName});renderChat();if(actionName==='pause')$(id).textContent='Pause requested…';}catch(error){notice(error.message);}});
window.addEventListener('popstate',()=>navigate(Object.keys(paths).find(k=>paths[k]===location.pathname)||'overview',false));
let refreshing=false;
async function refresh(){if(refreshing)return;refreshing=true;try{state.chats=await api('/api/chats');renderChats();if(state.chat){state.chat=await api('/api/chats/'+state.chat.id);renderChat();}if(state.view==='activity')await refreshActivity();$('connection-status').textContent='Workspace connected';}catch(error){$('connection-status').textContent='Connection interrupted';}finally{refreshing=false;}}
(async()=>{try{state.token=(await (await fetch('/api/session')).json()).token;[state.roster,state.health]=await Promise.all([api('/api/organization'),api('/api/health')]);renderHealth();renderOrganization();await refresh();const saved=sessionStorage.getItem('collective-chat');if(saved&&state.chats.some(c=>c.id===saved)){state.chat=await api('/api/chats/'+saved);renderChat();}navigate(Object.keys(paths).find(k=>paths[k]===location.pathname)||'overview',false);setInterval(refresh,1500);document.documentElement.dataset.ready='true';}catch(error){notice('Could not connect to the local console: '+error.message);$('connection-status').textContent='Offline';}})();

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
      bottom.append(element('span','connector-badge',configured?'Configured':'Available now'));
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
  try{savedConnectors=await api('/api/connectors');renderConnectorCatalog();$('connector-list').replaceChildren(...(savedConnectors.length?savedConnectors.map(connectionPanel):[element('p','connector-empty-connections','No saved connections yet. Choose an available card above to get started.')]));}
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
    const result=await api('/api/connectors',{id:$('connector-id').value||undefined,kind:$('connector-kind').value,name:$('connector-name').value.trim(),url:$('connector-url').value.trim(),model:$('connector-model').value.trim(),secret:$('connector-secret').value,allow_local:$('connector-local').checked});
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
