import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {JSDOM,VirtualConsole} from 'jsdom';
const base=process.env.COLLECTIVE101_TEST_URL;
if(!base)throw new Error('Run npm.cmd run test:ui to use the isolated test service.');
const html=await readFile(new URL('../collective101/web/index.html',import.meta.url),'utf8');
const script=await readFile(new URL('../collective101/web/app.js',import.meta.url),'utf8');
const presentationScripts=await Promise.all(['locales.js','preferences.js','visuals.js','organization-ui.js','thumbnail-ui.js','mission-ui.js','dashboard.js'].map(file=>readFile(new URL('../collective101/web/'+file,import.meta.url),'utf8')));
const markdownScripts=await Promise.all(['vendor/marked.umd.js','vendor/purify.min.js','markdown.js'].map(file=>readFile(new URL('../collective101/web/'+file,import.meta.url),'utf8')));
async function waitFor(predicate,timeout=25000){const end=Date.now()+timeout;while(Date.now()<end){if(await predicate())return;await new Promise(resolve=>setTimeout(resolve,70));}throw new Error('Timed out waiting for UI state');}
async function setup(healthOverride=null,options={}){
  const errors=[];const virtualConsole=new VirtualConsole();virtualConsole.on('jsdomError',error=>errors.push(error.message));
  const dom=new JSDOM(html,{url:base,runScripts:'outside-only',virtualConsole,pretendToBeVisual:true});
  const win=dom.window;let poll=()=>{};
  if(options.savedPreferences)win.localStorage.setItem('collective101.preferences.v1',JSON.stringify(options.savedPreferences));
  if(options.ambientPaused)win.localStorage.setItem('collective101.ambient-paused.v1','true');
  if(options.storageBlocked)Object.defineProperty(win,'localStorage',{get(){throw new Error('Storage blocked');}});
  win.matchMedia=query=>({matches:query.includes('reduced-motion')?options.systemReducedMotion===true:query.includes('pointer')?true:options.systemDark===true,addEventListener(){}});
  win.fetch=async(url,requestOptions={})=>{const target=new URL(url,base);assert.equal(target.origin,base);const response=await fetch(target,{...requestOptions,headers:{...requestOptions.headers,...(requestOptions.method==='POST'?{Origin:base}:{})}});if(target.pathname==='/api/health'&&healthOverride){const data=await response.json();return {ok:response.ok,json:async()=>({...data,...healthOverride})};}if(target.pathname==='/api/chats'&&options.chatRows&&requestOptions.method!=='POST')return {ok:true,json:async()=>options.chatRows};return response;};
  win.setInterval=fn=>{poll=fn;return 1;};win.HTMLElement.prototype.scrollIntoView=function(){};
  for(const code of markdownScripts.slice(0,2))win.eval(code);
  for(const code of presentationScripts)win.eval(code);
  win.eval(markdownScripts[2]+'\n'+script+'\nglobalThis.__testShowSource=showSource;');
  await waitFor(()=>win.document.documentElement.dataset.ready==='true');
  return {dom,win,doc:win.document,poll:()=>poll(),errors};
}
function submit(win,form){form.dispatchEvent(new win.Event('submit',{bubbles:true,cancelable:true}));}

test('dashboard shows saved mission state and opens a draft without spending model credits',async()=>{
  const rows=[{id:'test_running',title:'A real active mission',status:'running',created_at:'2026-11-04T01:00:00Z'},
    {id:'test_waiting',title:'A decision for you',status:'needs_input',created_at:'2026-11-04T01:00:00Z'},
    {id:'test_reviewed',title:'A reviewed result',status:'reviewed',created_at:'2026-11-04T01:00:00Z'},
    {id:'test_answered',title:'<img src=x onerror=alert(1)>',status:'answered',created_at:'2026-11-04T01:00:00Z'}];
  const app=await setup(null,{chatRows:rows});try{
    assert.equal(app.doc.getElementById('metric-active').textContent,'1');
    assert.equal(app.doc.getElementById('metric-attention').textContent,'1');
    assert.equal(app.doc.getElementById('metric-reviewed').textContent,'1');
    assert.equal(app.doc.getElementById('metric-chats').textContent,'4');
    assert.equal(app.doc.querySelectorAll('#dashboard-attention .attention-item').length,1);
    assert.equal(app.doc.querySelectorAll('#mission-list img').length,0);
    assert.match(app.doc.getElementById('mission-list').textContent,/<img/);
    assert.equal(app.doc.querySelectorAll('.constellation-employee').length,90);
    assert.equal(app.doc.querySelectorAll('.constellation-head').length,10);
    assert.equal(app.doc.querySelectorAll('.constellation-cluster').length,10);
    assert.equal(app.doc.querySelectorAll('.constellation-sweep').length,1);
    const constellation=app.doc.getElementById('constellation');
    const firstCluster=constellation.querySelector('.constellation-cluster');
    await app.poll();assert.equal(constellation.querySelector('.constellation-cluster'),firstCluster,'Polling unchanged state must not rebuild/replay the map');
    const focusedCard=app.doc.querySelector('.mission-card');focusedCard.focus();rows[0].status='paused';await app.poll();
    assert.equal(app.doc.activeElement.dataset.chatId,rows[0].id,'Mission updates preserve keyboard focus');
    let posted=false;const original=app.win.fetch;app.win.fetch=(url,opts)=>{if(opts?.method==='POST')posted=true;return original(url,opts);};
    const draft='Create a useful research brief for my team.';app.doc.getElementById('dashboard-input').value=draft;
    submit(app.win,app.doc.getElementById('dashboard-mission'));
    assert.equal(app.win.location.pathname,'/chat');assert.equal(app.doc.getElementById('mission-input').value,draft);assert.equal(posted,false);
    assert.deepEqual(app.errors,[]);
  }finally{app.dom.window.close();}
});

test('Settings applies every language and preserves validated preferences with English default and reset',async()=>{
  const app=await setup();try{
    assert.equal(app.doc.documentElement.lang,'en');assert.equal(app.doc.documentElement.dataset.theme,'dark');
    app.doc.querySelector('[data-nav="settings"]').click();
    const language=app.doc.getElementById('setting-language');assert.equal(language.options.length,14);assert.equal(language.options[0].value,'en');
    const draft=app.doc.getElementById('mission-input');draft.value='Keep my draft.';
    for(const option of [...language.options]){language.value=option.value;language.dispatchEvent(new app.win.Event('change'));assert.equal(app.doc.documentElement.lang,option.value);assert.equal(app.doc.documentElement.dir,option.value==='ar'?'rtl':'ltr');assert.equal(app.doc.getElementById('breadcrumb').textContent,app.win.CollectivePreferences.t('Settings'));assert.equal(draft.value,'Keep my draft.');}
    app.doc.querySelector('[name="theme"][value="light"]').click();
    app.doc.getElementById('setting-reduce-motion').click();
    const prefs=app.win.CollectivePreferences.get();const reloaded=await setup(null,{savedPreferences:prefs});try{assert.equal(reloaded.doc.documentElement.dataset.theme,'light');assert.equal(reloaded.doc.documentElement.dataset.reduceMotion,'true');assert.equal(reloaded.doc.documentElement.lang,'ms');}finally{reloaded.dom.window.close();}
    app.doc.getElementById('reset-preferences').click();assert.equal(app.doc.documentElement.lang,'en');assert.equal(app.doc.documentElement.dir,'ltr');assert.equal(app.doc.documentElement.dataset.theme,'dark');
    assert.deepEqual(app.errors,[]);
  }finally{app.dom.window.close();}
});

test('mission studio uses recorded evidence, keeps partial files inert and preserves keyboard focus',async()=>{
  const app=await setup();try{
    const files=[{path:'engineering/index.html',content:'<title><img src=x onerror=alert(1)></title>\n<script>alert(1)</script>',language:'HTML',lines:2,sha256:'first',agent_id:'engineering-003'},
      {path:'research/notes.md',content:'# Actual saved notes\n\n<script>alert(1)</script>\n![remote](https://example.com/track)',language:'Markdown',lines:4,sha256:'second',agent_id:'research-002'}];
    const chat={id:'synthetic',title:'A blocked draft',run_id:'root',effective_run_id:'revision',status:'blocked',brief:{objective:'A useful outcome'},run:{result:{selected_departments:['engineering']}},workspace:{files,preview:{ready:true},events:[{id:'root:review:1',phase:'review',status:'accepted',agent_id:'assurance-001'},{id:'revision:work:1',phase:'work',status:'accepted',agent_id:'engineering-003'}]}};
    const roster={departments:[{id:'engineering',name:'Engineering'},{id:'assurance',name:'Verification'}]};
    const calls=[];const handlers={showSource:file=>calls.push(['source',file.path]),openPreview:path=>calls.push(['preview',path]),downloadFile:file=>calls.push(['download',file.path]),viewEvidence:()=>{},previewAvailable:true};
    app.win.CollectiveMissionUI.render(chat,roster,handlers);
    const journey=app.doc.getElementById('mission-journey'),results=app.doc.getElementById('mission-results');
    assert.equal(journey.hidden,false);assert.match(journey.querySelector('.journey-step:last-child').textContent,/Blocked/);
    assert.match(journey.querySelectorAll('.journey-step')[2].textContent,/Not recorded/,'An earlier revision review cannot mark the active revision reviewed');
    assert.equal(journey.querySelectorAll('.department-badge').length,1);assert.match(journey.querySelector('.department-badge').textContent,/Engineering/);
    assert.equal(results.querySelectorAll('.deliverable-card').length,2);assert.equal(results.querySelector('script,iframe,img'),null);
    assert.match(results.textContent,/<img/);assert.doesNotMatch(results.querySelector('.results-heading').textContent,/Current mission reviewed/);
    [...results.querySelectorAll('button')].find(button=>button.textContent==='Open website').click();
    results.querySelector('.deliverable-download').click();assert.deepEqual(calls,[['preview','engineering/index.html'],['download','engineering/index.html']]);
    const original=results.querySelector('.deliverable-card');app.win.CollectiveMissionUI.render(chat,roster,handlers);assert.equal(results.querySelector('.deliverable-card'),original);
    const details=results.querySelector('.all-deliverables');details.open=true;const focused=details.querySelector('.file-text-link');focused.focus();
    chat.status='reviewed';app.win.CollectiveMissionUI.render(chat,roster,handlers);
    assert.equal(results.querySelector('.all-deliverables').open,true);assert.equal(app.doc.activeElement.dataset.filePath,files[0].path);assert.equal(app.doc.activeElement.dataset.fileAction,'list-source');
    assert.match(results.querySelector('.results-heading').textContent,/Current mission reviewed/);
    app.win.CollectiveMissionUI.render(null,roster,handlers);assert.equal(journey.hidden,true);assert.equal(results.hidden,true);
    app.win.CollectiveMissionUI.render(chat,roster,handlers);assert.ok(journey.querySelector('summary'));
    assert.deepEqual(app.errors,[]);
  }finally{app.dom.window.close();}
});

test('blocked storage and invalid preferences do not block the workspace',async()=>{
  for(const opts of [{storageBlocked:true},{savedPreferences:{theme:'bad',language:'invalid',textSize:'gigantic',reduceMotion:'true'}}]){
    const app=await setup(null,opts);try{
      assert.equal(app.doc.documentElement.lang,'en');assert.equal(app.doc.documentElement.dataset.theme,'dark');
      app.doc.querySelector('[name="theme"][value="light"]').click();assert.equal(app.doc.documentElement.dataset.theme,'light');
      if(opts.storageBlocked)assert.match(app.doc.getElementById('preferences-status').textContent,/this visit only/);
      assert.deepEqual(app.errors,[]);
    }finally{app.dom.window.close();}
  }
});

test('ambient motion stays continuous without pause controls and respects reduced-motion preferences',async()=>{
  const app=await setup(null,{ambientPaused:true});try{
    assert.equal(app.doc.documentElement.dataset.ambientMotion,'running');
    assert.equal(app.doc.querySelectorAll('.ambient-orbit').length,3);
    assert.equal(app.doc.querySelector('[data-motion-toggle]'),null);
    assert.equal(app.doc.querySelector('.cluster-atmosphere text'),null,'Floating decorative dots cannot move department labels');
    app.doc.getElementById('setting-reduce-motion').click();assert.equal(app.doc.documentElement.dataset.ambientMotion,'reduced');
    assert.deepEqual(app.errors,[]);
  }finally{app.dom.window.close();}
  for(const options of [{systemReducedMotion:true},{storageBlocked:true}]){
    const instance=await setup(null,options);try{
      if(options.systemReducedMotion)assert.equal(instance.doc.documentElement.dataset.ambientMotion,'reduced');
      else assert.equal(instance.doc.documentElement.dataset.ambientMotion,'running');
      assert.deepEqual(instance.errors,[]);
    }finally{instance.dom.window.close();}
  }
});

test('assistant Markdown has paragraphs, lists, safe links and inert code',async()=>{
  const app=await setup();try{
    app.doc.querySelector('[data-nav="chat"]').click();
    app.doc.getElementById('mission-input').value='formatting-check';submit(app.win,app.doc.getElementById('mission-form'));
    await waitFor(async()=>{await app.poll();return app.doc.getElementById('chat-status').textContent==='answered';});
    const body=app.doc.querySelector('.message.assistant .markdown-body');
    assert.ok(body);assert.equal(body.querySelectorAll('ol > li').length,2);
    assert.equal(body.querySelector('strong').textContent,'two cafes');
    assert.ok(body.querySelectorAll('p').length>=2);
    assert.match(body.querySelector('pre code').textContent,/<script>/);
    assert.equal(body.querySelector('script,img,iframe,style'),null);
    assert.equal(body.querySelector('a[href^="javascript:"]'),null);
    assert.equal(body.querySelector('a').target,'_blank');assert.match(body.querySelector('a').rel,/noopener/);
    assert.deepEqual(app.errors,[]);
  }finally{app.dom.window.close();}
});

test('Markdown file opens in Preview with an exact Source tab and no fingerprint details',async()=>{
  const app=await setup();try{
    const source='# Cafe notes\n\n**Reviewed** source.\n\n| Cafe | Area |\n| --- | --- |\n| One | KL |\n\n<script>alert(1)</script>\n\n![remote](https://example.com/track.png)';
    app.win.__testShowSource({path:'research/notes.md',content:source,sha256:'a'.repeat(64)});
    assert.equal(app.doc.getElementById('file-preview-tab').getAttribute('aria-selected'),'true');
    const preview=app.doc.getElementById('file-preview');
    assert.equal(preview.querySelector('h1').textContent,'Cafe notes');assert.ok(preview.querySelector('table'));
    assert.equal(preview.querySelector('script,img,iframe,style'),null);
    assert.equal(app.doc.querySelector('#file-fingerprint'),null);
    assert.equal(app.doc.getElementById('file-viewer').textContent.includes('File details'),false);
    app.doc.getElementById('file-source-tab').click();
    assert.equal(app.doc.getElementById('file-source').hidden,false);
    assert.equal(app.doc.getElementById('file-source').textContent,source);
    assert.equal(preview.hidden,true);
    app.win.__testShowSource({path:'engineering/index.html',content:'<script>doNotExecute()</script>'});
    assert.equal(app.doc.getElementById('file-tabs').hidden,true);
    assert.equal(app.doc.getElementById('file-source').hidden,false);
    assert.equal(app.doc.querySelector('#file-source script'),null);
  }finally{app.dom.window.close();}
});

test('chat budget uses the raised allowance and respects a lower running-server ceiling',async()=>{
  const current=await setup();try{
    assert.equal(current.doc.getElementById('budget-tokens').value,'10000000');
    assert.equal(current.doc.getElementById('budget-tokens').max,'10000000');
  }finally{current.dom.window.close();}
  const session=await (await fetch(base+'/api/session')).json();
  const health=await (await fetch(base+'/api/health',{headers:{'X-Console-Token':session.token}})).json();
  const older=await setup({limits:{...health.limits,max_admission_units_per_chat:2000000}});try{
    assert.equal(older.doc.getElementById('budget-tokens').value,'2000000');
    assert.equal(older.doc.getElementById('budget-tokens').max,'2000000');
  }finally{older.dom.window.close();}
});

test('old server requires restart and cannot receive new chat requests through the updated UI',async()=>{
  const app=await setup({version:'0.5-reviewed-work',features:{}});try{
    let sent=false;const original=app.win.fetch;
    app.win.fetch=(url,options)=>{if(options?.method==='POST')sent=true;return original(url,options);};
    assert.equal(app.doc.getElementById('send-mission').disabled,true);
    assert.match(app.doc.getElementById('notice').textContent,/Restart/);
    app.doc.getElementById('mission-input').value='Build a grocery landing page';submit(app.win,app.doc.getElementById('mission-form'));
    await waitFor(()=>app.doc.getElementById('notice').textContent.includes('before sending'));
    assert.equal(sent,false);
  }finally{app.dom.window.close();}
});

test('model source is visible in chat and connectors when only environment config exists',async()=>{
  const app=await setup({live_configured:true,model_configuration:{configured:true,enabled:true,credential_source:'environment',settings_source:'environment_defaults',model:'muse-spark-1.3',endpoint_host:'api.meta.ai',request_policy:{max_output_tokens:32768,timeout_seconds:120}}});
  try{
    assert.match(app.doc.getElementById('mode-description').textContent,/environment/i);
    app.doc.querySelector('[data-nav="connectors"]').click();
    await waitFor(()=>app.doc.getElementById('model-configuration')?.textContent.includes('muse-spark-1.3'));
    assert.match(app.doc.getElementById('model-configuration').textContent,/environment/i);
    assert.match(app.doc.getElementById('model-configuration').textContent,/api.meta.ai/);
    assert.match(app.doc.getElementById('model-configuration').textContent,/32,768|32768/);
    assert.match(app.doc.getElementById('model-configuration').textContent,/not.*verif|not.*test/i);
  }finally{app.dom.window.close();}
});

test('model request settings save without storing an environment credential',async()=>{
  const app=await setup();try{
    app.doc.querySelector('[data-nav="connectors"]').click();
    await waitFor(()=>!app.doc.getElementById('connector-list').textContent.includes('Loading connections'));
    app.doc.querySelector('[data-connector="meta"] button').click();
    app.doc.getElementById('connector-max-output').value='20000';
    app.doc.getElementById('connector-timeout').value='150';
    submit(app.win,app.doc.getElementById('connector-form'));
    await waitFor(()=>app.doc.getElementById('connector-setup').classList.contains('d-none'));
    await waitFor(()=>app.doc.getElementById('model-configuration').textContent.includes('20,000'));
    assert.equal(app.doc.getElementById('connector-secret').value,'');
    assert.match(app.doc.getElementById('model-configuration').textContent,/150 seconds/);
    assert.match(app.doc.getElementById('model-configuration').textContent,/No credential detected/);
    app.doc.querySelector('[data-connector="meta"] button').click();
    assert.equal(app.doc.getElementById('connector-max-output').value,'20000');
    assert.equal(app.doc.getElementById('connector-timeout').value,'150');
    assert.deepEqual(app.errors,[]);
  }finally{app.dom.window.close();}
});

test('directory exposes departments, roles, reporting lines and per-agent activity',async()=>{
  const app=await setup();try{
    app.doc.querySelector('[data-nav="organization"]').click();
    assert.equal(app.doc.getElementById('view-organization').classList.contains('d-none'),false);
    const search=app.doc.getElementById('agent-search');search.value='operations';search.dispatchEvent(new app.win.Event('input'));
    assert.equal(app.doc.querySelectorAll('#search-results .agent-row').length,8);
    app.doc.querySelector('#search-results button').click();
    assert.match(app.doc.getElementById('agent-inspector').textContent,/Reports to: Mission Director/);
    assert.equal(app.doc.querySelectorAll('#activity-agent option').length,102);
    assert.deepEqual(app.errors,[]);
  }finally{app.dom.window.close();}
});

test('organization explorer preserves real reporting roles, directory access and drawer keyboard return',async()=>{
  const app=await setup();try{
    app.doc.querySelector('[data-nav="organization"]').click();
    assert.equal(app.doc.querySelectorAll('.organization-node').length,10);
    app.doc.querySelector('.organization-node[data-department="research"]').click();
    assert.equal(app.doc.getElementById('organization-details').dataset.department,'research');
    assert.equal(app.doc.querySelectorAll('.explorer-employee').length,9);
    const head=app.doc.querySelector('.explorer-head');head.focus();head.click();
    assert.match(app.doc.getElementById('agent-inspector').textContent,/Reports to: Mission Director/);
    app.doc.dispatchEvent(new app.win.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
    assert.equal(app.doc.getElementById('agent-inspector').classList.contains('d-none'),true);assert.equal(app.doc.activeElement,head);
    app.doc.querySelector('[data-organization-mode="directory"]').click();assert.equal(app.doc.getElementById('department-grid').classList.contains('d-none'),false);
    app.doc.querySelector('.department-card[data-department="operations"]').click();assert.equal(app.doc.getElementById('organization-details').dataset.department,'operations');
    assert.equal(app.doc.getElementById('organization-explorer').hidden,false);assert.deepEqual(app.errors,[]);
  }finally{app.dom.window.close();}
});

test('saved-page thumbnail UI uses the capture result and discloses failures without replacing source',async()=>{
  const app=await setup();try{
    app.doc.querySelector('[data-nav="chat"]').click();
    const sample=app.doc.createElement('div');sample.className='deliverable-sample';sample.textContent='Actual saved source';
    const grid=app.doc.createElement('div');grid.className='deliverable-grid';grid.append(sample);app.doc.getElementById('mission-results').append(grid);
    const calls=[];app.win.CollectiveThumbnails.configure(async(cid,entry)=>{calls.push([cid,entry]);return {image:'data:image/png;base64,iVBORw0KGgo=',width:960,height:600};});
    const observed=[];app.win.IntersectionObserver=class {observe(node){observed.push(node);}unobserve(){}};
    const file={path:'engineering/index.html',sha256:'first'},chat={id:'test-capture',status:'running',workspace:{files:[file]}};
    app.win.CollectiveThumbnails.attach(sample,file,chat);sample.querySelector('button').click();
    assert.equal(observed.length,0,'Mutable working drafts must not race automatic thumbnail captures');
    await waitFor(()=>sample.querySelector('img'));assert.deepEqual(calls,[['test-capture','engineering/index.html']]);
    assert.equal(sample.querySelector('img').alt,'Static preview of engineering/index.html');assert.match(sample.textContent,/Static page preview/);
    const stable=app.doc.createElement('div');grid.append(stable);chat.status='reviewed';app.win.CollectiveThumbnails.attach(stable,file,chat);assert.equal(observed.length,1,'Stable saved outcomes can load a visible thumbnail');
    const failure=app.doc.createElement('div');failure.textContent='Original source stays';grid.append(failure);
    app.win.CollectiveThumbnails.configure(async()=>{throw new Error('unavailable');});
    app.win.CollectiveThumbnails.attach(failure,{path:'engineering/other.html',sha256:'other'},chat);failure.querySelector('button').click();
    await waitFor(()=>failure.textContent.includes('Thumbnail unavailable'));assert.match(failure.textContent,/Original source stays/);assert.equal(failure.querySelector('img'),null);
    assert.deepEqual(app.errors,[]);
  }finally{app.dom.window.close();}
});

test('Effectiveness exposes honest scorecards and versioned role cases without starting paid work',async()=>{
  const app=await setup();try{
    app.doc.querySelector('[data-nav="evaluations"]').click();
    await waitFor(()=>app.doc.querySelectorAll('#evaluation-agents tr').length===101);
    assert.ok(app.doc.querySelectorAll('[name="evaluation-case"]').length>=22);
    assert.match(app.doc.getElementById('evaluation-policy').textContent,/80%/);
    assert.match(app.doc.getElementById('evaluation-notice').textContent,/Fixtures never count/);
    assert.equal(app.doc.getElementById('start-evaluation').disabled,true);
    await waitFor(()=>app.doc.getElementById('memory-evidence').textContent.includes('frozen snapshot'));
    assert.match(app.doc.getElementById('memory-evidence').textContent,/frozen snapshot/);
    const search=app.doc.getElementById('evaluation-search');search.value='engineering-001';search.dispatchEvent(new app.win.Event('input'));
    assert.equal(app.doc.querySelectorAll('#evaluation-agents tr').length,1);
    assert.match(app.doc.getElementById('evaluation-agents').textContent,/untested/);
    assert.deepEqual(app.errors,[]);
  }finally{app.dom.window.close();}
});

test('confirmed evaluation uses only injected test provider and its fixtures cannot promote effectiveness',async()=>{
  const app=await setup({live_configured:true});try{
    app.doc.querySelector('[data-nav="evaluations"]').click();
    await waitFor(()=>app.doc.querySelector('[name="evaluation-case"][value="intake-greeting"]'));
    app.doc.querySelector('[name="evaluation-case"][value="intake-greeting"]').checked=true;
    app.doc.getElementById('evaluation-calls').value='10';app.doc.getElementById('evaluation-confirm').checked=true;
    submit(app.win,app.doc.getElementById('evaluation-form'));
    await waitFor(async()=>{await app.poll();return app.doc.getElementById('evaluation-detail').textContent.includes('Passed');});
    assert.match(app.doc.getElementById('evaluation-detail').textContent,/fixture/);
    assert.equal(app.doc.getElementById('evaluation-confirm').checked,false);
    assert.equal(app.doc.querySelectorAll('#evaluation-agents .meets_benchmark').length,0);
    assert.deepEqual(app.errors,[]);
  }finally{app.dom.window.close();}
});
test('short mission asks questions and answers continue to a recorded result',async()=>{
  const app=await setup();try{
    app.doc.querySelector('.new-mission').click();
    app.doc.getElementById('mission-input').value='Build a website';submit(app.win,app.doc.getElementById('mission-form'));
    await waitFor(async()=>{await app.poll();return app.doc.querySelectorAll('.intervention textarea').length===2;});
    const fields=app.doc.querySelectorAll('.intervention textarea');
    fields[0].value='For a local coffee shop serving residents who need to browse the menu and find the location.';
    fields[1].value='An accessible responsive page with opening hours, clear headings and operations documentation.';
    app.doc.querySelector('[name="theme"][value="light"]').click();
    assert.equal(app.doc.querySelector('.intervention textarea'),fields[0]);
    assert.match(fields[0].value,/local coffee shop/);
    submit(app.win,app.doc.querySelector('form.intervention'));
    await waitFor(async()=>{await app.poll();return app.doc.getElementById('chat-status').textContent==='reviewed';});
    assert.match(app.doc.getElementById('brief-content').textContent,/SUCCESS CRITERIA/);
    assert.equal(app.doc.getElementById('preview-project').disabled,false);
    assert.ok(app.doc.querySelector('[aria-label="Preview engineering/index.html in a new tab"]'));
    app.win.open=()=>null;
    app.doc.getElementById('preview-project').click();
    await waitFor(()=>!app.doc.getElementById('preview-link').classList.contains('d-none'));
    const link=app.doc.getElementById('preview-link');
    assert.equal(link.target,'_blank');assert.match(link.rel,/noopener/);
    assert.notEqual(new URL(link.href).port,new URL(base).port);
    const response=await fetch(link.href);assert.equal(response.status,200);
    assert.match(await response.text(),/Auto-refresh/);
    app.doc.getElementById('view-evidence').click();
    await waitFor(()=>app.doc.querySelectorAll('#activity-content details').length>0);
    assert.match(app.doc.getElementById('activity-mode').textContent,/Live Meta/);
    assert.ok(app.doc.querySelector('.timeline-entry'));
    app.doc.getElementById('activity-mission').value='';app.doc.getElementById('activity-mission').dispatchEvent(new app.win.Event('change'));
    assert.match(app.doc.getElementById('activity-content').textContent,/Choose a mission/);assert.equal(app.doc.querySelector('#activity-content .timeline-entry'),null);
    assert.deepEqual(app.errors,[]);
  }finally{app.dom.window.close();}
});

test('missing HTML keeps Preview disabled with actionable explanation',async()=>{
  const app=await setup();try{
    app.doc.querySelector('.new-mission').click();
    assert.equal(app.doc.getElementById('preview-project').disabled,true);
    assert.match(app.doc.getElementById('preview-status').textContent,/No HTML/);
    assert.ok(app.doc.getElementById('preview-link').classList.contains('d-none'));
    assert.deepEqual(app.errors,[]);
  }finally{app.dom.window.close();}
});

test('preview auto-refresh follows saved revisions, manual mode preserves view and missing page is explained',async()=>{
  const page=await readFile(new URL('../collective101/web/preview/index.html',import.meta.url),'utf8');
  const code=await readFile(new URL('../collective101/web/preview/preview.js',import.meta.url),'utf8');
  const errors=[];const console=new VirtualConsole();console.on('jsdomError',e=>errors.push(e.message));
  const dom=new JSDOM(page,{url:'http://127.0.0.1:12345/p/test/',runScripts:'outside-only',virtualConsole:console,pretendToBeVisual:true});
  const win=dom.window,doc=win.document;let poll;
  let meta={ready:true,entries:['engineering/index.html'],revision:'first',title:'Coffee shop',status:'running'};
  win.fetch=async()=>({ok:true,json:async()=>meta});win.setInterval=fn=>{poll=fn;};win.eval(code);
  try{
    await waitFor(()=>doc.getElementById('site').src.includes('revision=first'));
    const first=doc.getElementById('site').src;
    assert.equal(doc.getElementById('site').getAttribute('sandbox'),'allow-scripts');
    meta={...meta,revision:'second'};poll();
    await waitFor(()=>doc.getElementById('site').src.includes('revision=second'));
    assert.notEqual(doc.getElementById('site').src,first);
    doc.getElementById('auto').checked=false;meta={...meta,revision:'third'};poll();
    await waitFor(()=>doc.getElementById('state').textContent.includes('Updates available'));
    assert.match(doc.getElementById('site').src,/revision=second/);
    doc.getElementById('refresh').click();await waitFor(()=>doc.getElementById('site').src.includes('revision=third'));
    meta={...meta,ready:false,entries:[],reason:'No HTML page has been saved yet.'};poll();
    await waitFor(()=>doc.getElementById('site').hidden);
    assert.match(doc.getElementById('empty').textContent,/No HTML/);
    assert.deepEqual(errors,[]);
  }finally{win.close();}
});
test('JavaScript mission displays real sandbox evidence and escapes user markup',async()=>{
  const app=await setup();try{
    app.doc.querySelector('[data-example="calculator"]').click();
    app.doc.getElementById('mission-input').value+=' <img src=x onerror=alert(1)>';
    submit(app.win,app.doc.getElementById('mission-form'));
    await waitFor(async()=>{await app.poll();return app.doc.getElementById('chat-status').textContent==='reviewed';});
    assert.equal(app.doc.querySelector('#chat-messages img'),null);
    assert.match(app.doc.getElementById('chat-messages').textContent,/<img/);
    app.doc.getElementById('view-evidence').click();
    const filter=app.doc.getElementById('activity-filter');filter.value='executions';filter.dispatchEvent(new app.win.Event('change'));
    await waitFor(()=>app.doc.getElementById('activity-content').textContent.includes('QuickJS/WebAssembly'));
    assert.match(app.doc.getElementById('activity-content').textContent,/passed/);
    assert.deepEqual(app.errors,[]);
  }finally{app.dom.window.close();}
});


test('greeting uses injected live-provider response and agent inspector shows scoped tools',async()=>{
  const app=await setup();try{
    app.doc.querySelector('.new-mission').click();
    app.doc.getElementById('mission-input').value='Hi!';submit(app.win,app.doc.getElementById('mission-form'));
    await waitFor(async()=>{await app.poll();return app.doc.getElementById('chat-status').textContent==='answered';});
    assert.match(app.doc.getElementById('brief-content').textContent,/1 \/ 160 total provider requests/);
    assert.equal(app.doc.getElementById('mission-controls').classList.contains('d-none'),true);
    app.doc.querySelector('[data-nav="organization"]').click();
    const search=app.doc.getElementById('agent-search');search.value='research-003';search.dispatchEvent(new app.win.Event('input'));
    app.doc.querySelector('#search-results button').click();
    assert.match(app.doc.getElementById('agent-inspector').textContent,/web_search/);
    assert.match(app.doc.getElementById('agent-inspector').textContent,/own reviewed episodes/);
    assert.deepEqual(app.errors,[]);
  }finally{app.dom.window.close();}
});


test('connector catalog previews services, filters, and opens accessible setup without department choices',async()=>{
  const app=await setup();try{
    app.doc.querySelector('[data-nav="connectors"]').click();
    await waitFor(()=>app.doc.querySelectorAll('.connector-card').length===9&&!app.doc.getElementById('connector-list').textContent.includes('Loading connections'));
    assert.equal(app.doc.getElementById('connector-departments'),null);
    assert.equal(app.doc.querySelector('#view-connectors select'),null);
    for(const id of ['gmail','slack','canva','github','drive','calendar']){
      const card=app.doc.querySelector(`[data-connector="${id}"]`);
      assert.ok(card.textContent.includes('Coming soon'));assert.equal(card.querySelector('button'),null);
    }
    const search=app.doc.getElementById('connector-search');search.value='github';search.dispatchEvent(new app.win.Event('input'));
    assert.equal(app.doc.querySelectorAll('.connector-card').length,1);
    search.value='missing-service';search.dispatchEvent(new app.win.Event('input'));
    assert.equal(app.doc.getElementById('connector-empty').classList.contains('d-none'),false);
    search.value='';search.dispatchEvent(new app.win.Event('input'));
    app.doc.querySelector('[data-connector-filter="available"]').click();assert.equal(app.doc.querySelectorAll('.connector-card').length,3);
    app.doc.querySelector('[data-connector="mcp"] button').click();
    assert.equal(app.doc.activeElement.id,'connector-name');assert.equal(app.doc.getElementById('connector-kind').value,'mcp');
    app.doc.getElementById('connector-setup').dispatchEvent(new app.win.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
    assert.equal(app.doc.getElementById('connector-setup').classList.contains('d-none'),true);
    assert.equal(app.doc.activeElement.getAttribute('aria-label'),'Set up Custom MCP');assert.deepEqual(app.errors,[]);
  }finally{app.dom.window.close();}
});

test('card setup saves encrypted search credentials and enables all 101 agents without selection',async()=>{
  const app=await setup();try{
    app.doc.querySelector('[data-nav="connectors"]').click();
    await waitFor(()=>app.doc.querySelector('[data-connector="brave"] button'));
    app.doc.querySelector('[data-connector="brave"] button').click();
    app.doc.getElementById('connector-name').value='UI test search';
    app.doc.getElementById('connector-secret').value='ui-test-placeholder-not-a-key';
    submit(app.win,app.doc.getElementById('connector-form'));
    await waitFor(()=>app.doc.querySelector('#connector-list .state-pill')?.textContent==='enabled');
    assert.equal(app.doc.getElementById('connector-secret').value,'');
    assert.equal(app.doc.getElementById('connector-list').textContent.includes('ui-test-placeholder-not-a-key'),false);
    assert.ok(app.doc.getElementById('connector-list').textContent.includes('all 101 agents'));
    const session=await (await fetch(base+'/api/session')).json();
    const headers={'X-Console-Token':session.token};
    const connectors=await (await fetch(base+'/api/connectors',{headers})).json();
    assert.equal(connectors[0].departments.length,10);assert.equal(JSON.stringify(connectors).includes('ui-test-placeholder-not-a-key'),false);
    const roster=await (await fetch(base+'/api/organization',{headers})).json();
    assert.equal(roster.agents.length,101);
    for(const agent of roster.agents)assert.ok(agent.tools.some(t=>t.name==='web_search'&&t.available));
    [...app.doc.querySelectorAll('#connector-list button')].find(b=>b.textContent==='Disconnect').click();
    await waitFor(()=>app.doc.querySelector('#connector-list .state-pill')?.textContent==='disabled');
    assert.deepEqual(app.errors,[]);
  }finally{app.dom.window.close();}
});


test('chat composer grows without manual resizing and runtime status stays outside messages',async()=>{
  const app=await setup();try{
    app.doc.querySelector('[data-nav="chat"]').click();
    assert.equal(app.doc.querySelector('#view-chat .chat-side'),null);
    assert.equal(app.doc.querySelector('#mission-details'),null);
    assert.equal(app.doc.querySelector('#view-chat .chat-toolbar'),null);
    assert.equal(app.doc.querySelector('#chat-inspector').open,false);
    const input=app.doc.getElementById('mission-input');
    Object.defineProperty(input,'scrollHeight',{configurable:true,get:()=>input.value.length>50?280:48});
    input.value='x'.repeat(100);input.dispatchEvent(new app.win.Event('input'));assert.equal(input.style.height,'200px');assert.equal(input.style.overflowY,'auto');
    input.value='progress-check';input.dispatchEvent(new app.win.Event('input'));assert.equal(input.style.height,'48px');
    submit(app.win,app.doc.getElementById('mission-form'));
    await waitFor(()=>!app.doc.getElementById('chat-progress').classList.contains('d-none'));
    assert.match(app.doc.getElementById('chat-progress-label').textContent,/Head of Distribution/);
    assert.equal(app.doc.querySelector('#chat-messages [role="status"]'),null);
    assert.equal(app.doc.getElementById('chat-messages').textContent.includes('considering your request'),false);
    assert.equal(app.doc.getElementById('mission-form').classList.contains('d-none'),false);
    assert.equal(app.doc.getElementById('send-mission').disabled,true);
    const bubble=app.doc.querySelector('#chat-messages .message');const originalFetch=app.win.fetch;
    app.win.fetch=async(url,options)=>{const response=await originalFetch(url,options);if(String(url).startsWith('/api/chats/')){const value=await response.json();if(value.status==='intake')value.progress={label:'Recorded test action',phase:'intake'};return {ok:response.ok,json:async()=>value};}return response;};
    await app.poll();assert.equal(app.doc.querySelector('#chat-messages .message'),bubble);app.win.fetch=originalFetch;
    await waitFor(async()=>{await app.poll();return app.doc.getElementById('chat-status').textContent==='answered';});
    assert.equal(app.doc.getElementById('chat-progress').classList.contains('d-none'),true);
    assert.equal(app.doc.getElementById('send-mission').disabled,false);assert.deepEqual(app.errors,[]);
  }finally{app.dom.window.close();}
});
