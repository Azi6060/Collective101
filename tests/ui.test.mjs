import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {JSDOM,VirtualConsole} from 'jsdom';
const base=process.env.COLLECTIVE101_TEST_URL;
if(!base)throw new Error('Run npm.cmd run test:ui to use the isolated test service.');
const html=await readFile(new URL('../collective101/web/index.html',import.meta.url),'utf8');
const script=await readFile(new URL('../collective101/web/app.js',import.meta.url),'utf8');
const preferencesScript=await readFile(new URL('../collective101/web/preferences.js',import.meta.url),'utf8');
const localesScript=await readFile(new URL('../collective101/web/locales.js',import.meta.url),'utf8');
async function waitFor(predicate,timeout=25000){const end=Date.now()+timeout;while(Date.now()<end){if(await predicate())return;await new Promise(resolve=>setTimeout(resolve,70));}throw new Error('Timed out waiting for UI state');}
async function setup(transformChat=null,preferences={}){
  const errors=[];const virtualConsole=new VirtualConsole();virtualConsole.on('jsdomError',error=>errors.push(error.message));
  const dom=new JSDOM(html,{url:base,runScripts:'outside-only',virtualConsole});
  const win=dom.window;let poll=()=>{};
  if(preferences.browserLanguage)Object.defineProperty(win.navigator,'language',{value:preferences.browserLanguage});
  if(preferences.stored)win.localStorage.setItem('collective101.preferences.v1',JSON.stringify(preferences.stored));
  if(preferences.blockStorage)Object.defineProperty(win,'localStorage',{get(){throw new Error('Storage disabled');}});
  const mediaListeners=[];const media={matches:preferences.systemDark===true,addEventListener:(name,listener)=>mediaListeners.push(listener)};
  win.matchMedia=()=>media;
  win.fetch=async(url,options={})=>{const target=new URL(url,base);assert.equal(target.origin,base);const response=await fetch(target,{...options,headers:{...options.headers,...(options.method==='POST'?{Origin:base}:{})}});if(transformChat&&target.pathname.startsWith('/api/chats/')){const chat=await response.clone().json();return new Response(JSON.stringify(transformChat(chat)),{status:response.status,headers:{'content-type':'application/json'}});}return response;};
  win.setInterval=fn=>{poll=fn;return 1;};win.HTMLElement.prototype.scrollIntoView=function(){};
  win.eval(localesScript);win.eval(preferencesScript);win.eval(script);
  await waitFor(()=>win.document.documentElement.dataset.ready==='true');
  return {dom,win,doc:win.document,poll:()=>poll(),errors,setSystemDark:dark=>{media.matches=dark;mediaListeners.forEach(listener=>listener());}};
}
function submit(win,form){form.dispatchEvent(new win.Event('submit',{bubbles:true,cancelable:true}));}

test('popular interface languages have working settings translations and English is always the default',async()=>{
  const app=await setup(null,{browserLanguage:'ar'});try{
    const language=app.doc.getElementById('setting-language');
    assert.equal(app.doc.documentElement.lang,'en');assert.equal(language.value,'en');
    assert.equal(language.options[0].textContent,'English');
    assert.deepEqual([...language.options].map(option=>option.value),['en','zh','es','hi','ar','fr','pt','ru','bn','de','ja','ko','id','ms']);
    app.doc.querySelector('.nav-link[data-nav="settings"]').click();
    app.doc.getElementById('mission-input').value='Keep this draft unchanged.';
    for(const option of [...language.options]) {
      language.value=option.value;language.dispatchEvent(new app.win.Event('change'));
      assert.equal(app.doc.documentElement.lang,option.value);
      assert.equal(app.doc.documentElement.dir,option.value==='ar'?'rtl':'ltr');
      assert.equal(app.doc.getElementById('breadcrumb').textContent,app.win.CollectivePreferences.t('Settings'));
      assert.equal(app.doc.querySelector('#view-settings h1').textContent,app.win.CollectivePreferences.t('Your workspace, your way.'));
      if(option.value!=='en')assert.notEqual(app.doc.getElementById('breadcrumb').textContent,'Settings');
      assert.equal(app.doc.getElementById('mission-input').value,'Keep this draft unchanged.');
    }
    app.doc.getElementById('reset-preferences').click();
    assert.equal(app.doc.documentElement.lang,'en');assert.equal(app.doc.documentElement.dir,'ltr');
    assert.deepEqual(app.errors,[]);
  }finally{app.dom.window.close();}
});

test('settings preserve presentation preferences, follow system theme, and translate navigation',async()=>{
  const app=await setup(null,{systemDark:true});try{
    app.doc.querySelector('.nav-link[data-nav="settings"]').click();
    assert.equal(app.win.location.pathname,'/settings');
    assert.equal(app.doc.documentElement.dataset.theme,'dark');
    app.setSystemDark(false);assert.equal(app.doc.documentElement.dataset.theme,'light');
    app.doc.querySelector('[name="theme"][value="dark"]').click();
    app.setSystemDark(false);assert.equal(app.doc.documentElement.dataset.theme,'dark');
    const language=app.doc.getElementById('setting-language');language.value='ms';language.dispatchEvent(new app.win.Event('change'));
    assert.equal(app.doc.documentElement.lang,'ms');
    assert.equal(app.doc.getElementById('breadcrumb').textContent,'Tetapan');
    assert.match(app.doc.querySelector('.nav-link[data-nav="chat"]').textContent,/Sembang misi/);
    const size=app.doc.getElementById('setting-text-size');size.value='large';size.dispatchEvent(new app.win.Event('change'));
    app.doc.getElementById('setting-reduce-motion').click();
    const stored=app.win.CollectivePreferences.get();
    const reloaded=await setup(null,{stored});try{
      assert.equal(reloaded.doc.documentElement.dataset.theme,'dark');
      assert.equal(reloaded.doc.documentElement.lang,'ms');
      assert.equal(reloaded.doc.documentElement.dataset.textSize,'large');
      assert.equal(reloaded.doc.documentElement.dataset.reduceMotion,'true');
    }finally{reloaded.dom.window.close();}
    app.doc.getElementById('reset-preferences').click();
    assert.equal(app.doc.documentElement.lang,'en');assert.equal(app.doc.documentElement.dataset.textSize,'default');
    assert.equal(app.doc.getElementById('breadcrumb').textContent,'Settings');
    assert.equal(app.doc.getElementById('setting-reduce-motion').checked,false);
    assert.deepEqual(app.errors,[]);
  }finally{app.dom.window.close();}
});

test('invalid or unavailable preference storage cannot prevent chat startup',async()=>{
  for(const preferences of [{stored:{theme:'bad',language:'xx',textSize:'huge',reduceMotion:'true'}},{blockStorage:true}]){
    const app=await setup(null,preferences);try{
      assert.equal(app.doc.documentElement.lang,'en');assert.equal(app.doc.documentElement.dataset.theme,'light');
      assert.match(app.doc.getElementById('chat-messages').textContent,/What can we work on/);
      app.doc.querySelector('[name="theme"][value="dark"]').click();
      assert.equal(app.doc.documentElement.dataset.theme,'dark');
      if(preferences.blockStorage)assert.match(app.doc.getElementById('preferences-status').textContent,/this visit only/);
      assert.deepEqual(app.errors,[]);
    }finally{app.dom.window.close();}
  }
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
test('short mission asks questions and answers continue to a recorded result',async()=>{
  const app=await setup();try{
    app.doc.querySelector('.new-mission').click();
    app.doc.getElementById('mission-input').value='Build a website';submit(app.win,app.doc.getElementById('mission-form'));
    await waitFor(async()=>{await app.poll();return app.doc.querySelectorAll('.intervention textarea').length===2;});
    const fields=app.doc.querySelectorAll('.intervention textarea');
    fields[0].value='For a local coffee shop serving residents who need to browse the menu and find the location.';
    fields[1].value='An accessible responsive page with opening hours, clear headings and operations documentation.';
    app.doc.querySelector('[name="theme"][value="dark"]').click();
    assert.equal(app.doc.querySelector('.intervention textarea'),fields[0],'Changing presentation must preserve the guidance form');
    assert.match(fields[0].value,/local coffee shop/);
    submit(app.win,app.doc.querySelector('form.intervention'));
    await waitFor(async()=>{await app.poll();return app.doc.getElementById('chat-status').textContent==='reviewed';});
    assert.match(app.doc.getElementById('brief-content').textContent,/SUCCESS CRITERIA/);
    app.doc.getElementById('view-evidence').click();
    await waitFor(()=>app.doc.querySelectorAll('#activity-content details').length>0);
    assert.match(app.doc.getElementById('activity-mode').textContent,/Live Meta/);
    assert.deepEqual(app.errors,[]);
  }finally{app.dom.window.close();}
});
test('mission brief displays prior team and employee evidence with provenance and advisory scope',async()=>{
  const app=await setup(chat=>chat.brief?{...chat,brief:{...chat.brief,team_learning:[
    {outcome:'not_accepted',departments:['engineering','design'],evidence_run:'org_prior_blocked'},
    {outcome:'accepted',departments:['research','communications'],evidence_run:'org_prior_accepted'}
  ]},run:chat.run?{...chat.run,result:{...chat.run.result,
    selected_departments:[...new Set([...chat.run.result.selected_departments,'engineering'])],
    assignment_evidence:[{department:'engineering',agent_id:'engineering-003',similar_verified_tasks:2,
      verified_missions:2,history_strength:'repeated',evidence_runs:['org_task_one','org_task_two']}],
    proposals:{...chat.run.result.proposals,engineering:{tasks:[
      {key:'calculator',title:'Implement calculator addition',assignee:'engineering-003'}
    ]}}
  }}:chat.run}:chat);try{
    app.doc.querySelector('[data-example="calculator"]').click();
    submit(app.win,app.doc.getElementById('mission-form'));
    await waitFor(async()=>{await app.poll();return app.doc.getElementById('chat-status').textContent==='reviewed';});
    const brief=app.doc.getElementById('brief-content').textContent;
    assert.match(brief,/SIMILAR MISSION HISTORY/);
    assert.match(brief,/Not accepted · engineering, design · evidence run org_prior_blocked/);
    assert.match(brief,/Accepted · research, communications · evidence run org_prior_accepted/);
    assert.match(brief,/does not identify which department caused an outcome/);
    assert.match(brief,/CHECKED TASK EXPERIENCE SHARED WITH HEADS/);
    assert.match(brief,/engineering-003 \(engineering\): 2 similar checked task\(s\) across 2 mission\(s\), repeated history; evidence org_task_one, org_task_two; proposed for "Implement calculator addition"/);
    assert.match(brief,/not a rating or automatic assignment/);
    assert.deepEqual(app.errors,[]);
  }finally{app.dom.window.close();}
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
    assert.equal(app.doc.querySelector('#mission-details').open,false);
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
