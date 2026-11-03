// Real Chrome via MCP; model responses are scripted and state is disposable.
import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {connectBrowser,inspect,waitUntil,waitReady,resultText} from '../scripts/playwright-mcp-client.mjs';
const base=process.env.COLLECTIVE101_TEST_URL;
assert.ok(base&&process.env.COLLECTIVE101_ISOLATED_TEST==='1','Run npm run test:browser with the isolated Python service');
assert.notEqual(new URL(base).port,'8765','Never run interaction tests on the user app');
let browser;
before(async()=>{browser=await connectBrowser(base,{allowLoopbackPreviews:true});await browser.call('browser_navigate',{url:base+'/chat'});await waitReady(browser);});
after(async()=>{await browser?.close();});
const click=target=>browser.call('browser_click',{target});
const type=(target,text)=>browser.call('browser_type',{target,text});
const shot=name=>browser.call('browser_take_screenshot',{filename:`work/playwright/test-${name}.png`,scale:'css',fullPage:true});
async function newChat(){await click('#new-chat');}

test('desktop and mobile composer stays visible, grows, caps and shrinks',async()=>{
  assert.equal(await inspect(browser,()=>getComputedStyle(document.querySelector('.topbar')).display),'none');
  assert.equal(await inspect(browser,()=>!!document.querySelector('#view-chat .chat-toolbar')),false);
  assert.equal(await inspect(browser,()=>!!document.querySelector('.sidebar #new-chat')),true);
  await click('#toggle-sidebar');
  assert.ok(await inspect(browser,()=>document.querySelector('.sidebar').getBoundingClientRect().width<=70));
  const initial=await inspect(browser,()=>({height:document.querySelector('#mission-input').clientHeight,resize:getComputedStyle(document.querySelector('#mission-input')).resize}));
  assert.equal(initial.resize,'none');assert.ok(initial.height>0);
  await type('#mission-input',Array(25).fill('A longer line for composer layout').join('\n'));
  assert.equal(await inspect(browser,()=>document.querySelector('#mission-input').getBoundingClientRect().height),200);
  await shot('desktop-expanded');
  await type('#mission-input','Hi');
  assert.ok(await inspect(browser,()=>document.querySelector('#mission-input').getBoundingClientRect().height<100));
  await browser.call('browser_resize',{width:390,height:844});
  try {
    await shot('mobile');
    const layout=await inspect(browser,()=>({width:document.documentElement.scrollWidth,viewport:innerWidth,bottom:document.querySelector('#mission-form').getBoundingClientRect().bottom,height:innerHeight}));
    assert.ok(layout.width<=layout.viewport,'No horizontal overflow');
    assert.ok(layout.bottom<=layout.height,`Composer bottom ${layout.bottom} exceeds viewport ${layout.height}`);
  }finally{await browser.call('browser_resize',{width:1440,height:1000});}
  for(const width of [320,768,1024]){
    await browser.call('browser_resize',{width,height:844});
    const layout=await inspect(browser,()=>({width:document.documentElement.scrollWidth,viewport:innerWidth,bottom:document.querySelector('#mission-form').getBoundingClientRect().bottom,height:innerHeight}));
    assert.ok(layout.width<=layout.viewport&&layout.bottom<=layout.height,JSON.stringify(layout));
  }
  await browser.call('browser_resize',{width:1440,height:1000});
});

test('Hi gets a provider reply without clarification or department work',async()=>{
  await newChat();await type('#mission-input','Hi');await click('#send-mission');
  await waitUntil(browser,()=>document.querySelector('#chat-status').textContent==='answered','greeting reply');
  const result=await inspect(browser,()=>({text:document.querySelector('#chat-messages').textContent,questions:document.querySelectorAll('.intervention textarea').length,controls:document.querySelector('#mission-controls').classList.contains('d-none')}));
  assert.match(result.text,/Hello from the scripted test provider/);assert.equal(result.questions,0);assert.equal(result.controls,true);
});

test('activity hint is visible outside the transcript and clears on completion',async()=>{
  await newChat();await type('#mission-input','progress-check');await click('#send-mission');
  await waitUntil(browser,()=>!document.querySelector('#chat-progress').classList.contains('d-none'),'activity hint');
  const result=await inspect(browser,()=>({label:document.querySelector('#chat-progress-label').textContent,inside:!!document.querySelector('#chat-messages [role="status"]'),disabled:document.querySelector('#send-mission').disabled}));
  assert.match(result.label,/Head of Distribution/);assert.equal(result.inside,false);assert.equal(result.disabled,true);
  await shot('activity-hint');
  await waitUntil(browser,()=>document.querySelector('#chat-status').textContent==='answered','status reply');
  assert.equal(await inspect(browser,()=>document.querySelector('#chat-progress').classList.contains('d-none')),true);
});

test('provider clarification can be answered and leads to reviewed mission evidence',async()=>{
  await newChat();await type('#mission-input','Build a website');await click('#send-mission');
  await waitUntil(browser,()=>document.querySelectorAll('.intervention textarea').length===2,'clarification');
  assert.match(await inspect(browser,()=>document.querySelector('.intervention').textContent),/Who will use this website/);
  await type('#answer-intake-0','For a local coffee shop serving residents who need to browse the menu and find the location.');
  await type('#answer-intake-1','An accessible responsive page with opening hours, clear headings and operations documentation.');
  await click('form.intervention button');
  await waitUntil(browser,()=>document.querySelector('#chat-status').textContent==='reviewed','reviewed mission',60000);
  await waitUntil(browser,()=>document.querySelectorAll('.workspace-file').length>0,'saved source files');
  assert.equal(await inspect(browser,()=>document.querySelector('#download-project').disabled),false);
  assert.match(await inspect(browser,()=>document.querySelector('#workspace-counts').textContent),/lines of code/);
  await shot('chat-delivered');
  await click('.workspace-file[title="View engineering/index.html source"]');
  assert.match(await inspect(browser,()=>document.querySelector('#file-source').textContent),/<!doctype html>/i);
  assert.equal(await inspect(browser,()=>document.querySelector('#file-source iframe')),null);
  await click('#close-file');
  const markdownTitle=await inspect(browser,()=>[...document.querySelectorAll('.workspace-file')].find(button=>/\.md source$/.test(button.title))?.title);
  assert.ok(markdownTitle);await click('[title='+JSON.stringify(markdownTitle)+']');
  assert.equal(await inspect(browser,()=>document.querySelector('#file-preview-tab').getAttribute('aria-selected')),'true');
  assert.match(await inspect(browser,()=>document.querySelector('#file-preview h1').textContent),/fixture draft/i);
  assert.equal(await inspect(browser,()=>document.querySelector('#file-fingerprint')),null);
  await shot('markdown-file-preview');
  await click('#file-source-tab');
  assert.match(await inspect(browser,()=>document.querySelector('#file-source').textContent),/^# Deterministic/);
  assert.equal(await inspect(browser,()=>document.querySelector('#file-preview').hidden),true);
  await browser.call('browser_press_key',{key:'ArrowLeft'});
  assert.equal(await inspect(browser,()=>document.activeElement.id),'file-preview-tab');
  await browser.call('browser_resize',{width:390,height:844});
  const fileLayout=await inspect(browser,()=>({right:document.querySelector('#file-viewer').getBoundingClientRect().right,width:innerWidth,overflow:document.documentElement.scrollWidth}));
  assert.ok(fileLayout.right<=fileLayout.width&&fileLayout.overflow<=fileLayout.width);
  await shot('markdown-file-mobile');await browser.call('browser_resize',{width:1440,height:1000});
  await click('#close-file');
  assert.equal(await inspect(browser,()=>document.querySelector('#preview-project').disabled),false);
  await click('#preview-project');
  await waitUntil(browser,()=>!!document.querySelector('#preview-link').getAttribute('href'),'preview link');
  const previewURL=await inspect(browser,()=>document.querySelector('#preview-link').href);
  assert.notEqual(new URL(previewURL).port,new URL(base).port);
  await browser.call('browser_tabs',{action:'select',index:1});
  await waitUntil(browser,()=>!!document.querySelector('#site')&&!document.querySelector('#site').hidden,'preview frame');
  assert.equal(await inspect(browser,()=>window.opener===null),true);
  assert.equal(await inspect(browser,()=>document.querySelector('#site').getAttribute('sandbox')),'allow-scripts');
  const snapshot=resultText(await browser.call('browser_snapshot'));
  assert.match(snapshot,/Interactive preview ready/);
  const reference=snapshot.match(/button "Try interaction" \[ref=([^\]]+)\]/)?.[1];
  assert.ok(reference,'Interactive generated button is accessible');await click(reference);
  assert.match(resultText(await browser.call('browser_snapshot')),/Interaction works/);
  const previous=await inspect(browser,()=>document.querySelector('#site').src);
  await click('#refresh');await waitUntil(browser,()=>!document.querySelector('#refresh').disabled,'manual refresh');
  assert.notEqual(await inspect(browser,()=>document.querySelector('#site').src),previous);
  await shot('website-preview');
  await browser.call('browser_resize',{width:390,height:844});
  const layout=await inspect(browser,()=>({width:document.documentElement.scrollWidth,viewport:innerWidth,bottom:document.querySelector('iframe').getBoundingClientRect().bottom,height:innerHeight}));
  assert.ok(layout.width<=layout.viewport&&layout.bottom<=layout.height,JSON.stringify(layout));await shot('website-preview-mobile');
  await browser.call('browser_resize',{width:320,height:844});
  assert.equal(await inspect(browser,()=>document.documentElement.scrollWidth<=innerWidth),true);
  await browser.call('browser_resize',{width:1440,height:1000});
  const previewErrors=resultText(await browser.call('browser_console_messages',{level:'warning'}));assert.match(previewErrors,/Errors: 0, Warnings: 0/);
  await browser.call('browser_tabs',{action:'close',index:1});await browser.call('browser_tabs',{action:'select',index:0});
  await click('#view-evidence');
  await waitUntil(browser,()=>document.querySelectorAll('#activity-content details').length>0,'recorded evidence');
});

test('chat Markdown renders readable paragraphs and lists without executing markup',async()=>{
  await newChat();await type('#mission-input','formatting-check');await click('#send-mission');
  await waitUntil(browser,()=>document.querySelector('#chat-status').textContent==='answered','formatted reply');
  const rendered=await inspect(browser,()=>{const body=document.querySelector('.message.assistant .markdown-body');return {
    paragraphs:body.querySelectorAll('p').length,items:body.querySelectorAll('ol > li').length,
    bold:body.querySelector('strong').textContent,code:body.querySelector('pre code').textContent,
    unsafe:!!body.querySelector('script,img,iframe,style,a[href^="javascript:"]'),
    gap:parseFloat(getComputedStyle(body.querySelector('p')).marginBottom),
    link:body.querySelector('a').target};});
  assert.equal(rendered.items,2);assert.ok(rendered.paragraphs>=2&&rendered.gap>0);
  assert.equal(rendered.bold,'two cafes');assert.equal(rendered.unsafe,false);assert.equal(rendered.link,'_blank');
  assert.match(rendered.code,/<script>/);await shot('markdown-chat');
  await browser.call('browser_resize',{width:390,height:844});await shot('markdown-chat-mobile');
  assert.ok(await inspect(browser,()=>document.documentElement.scrollWidth<=innerWidth));
  await browser.call('browser_resize',{width:1440,height:1000});
});

test('organization and connector catalog support search, roles and keyboard dismissal',async()=>{
  await click('[data-nav="organization"]');
  assert.equal(await inspect(browser,()=>document.querySelectorAll('.department-card').length),10);
  await type('#agent-search','research-003');await click('#search-results button');
  assert.match(await inspect(browser,()=>document.querySelector('#agent-inspector').textContent),/web_search/);
  await click('[data-nav="connectors"]');
  await waitUntil(browser,()=>document.querySelectorAll('.connector-card').length===9,'connector cards');
  await waitUntil(browser,()=>document.querySelector('#model-configuration').textContent.includes('No credential detected'),'model provenance panel');
  const model=await inspect(browser,()=>document.querySelector('#model-configuration').textContent);
  assert.match(model,/muse-spark-1.3/);assert.match(model,/api.meta.ai/);assert.match(model,/not a verified connection/);
  await type('#connector-search','github');
  assert.equal(await inspect(browser,()=>document.querySelectorAll('.connector-card').length),1);
  assert.match(await inspect(browser,()=>document.querySelector('.connector-card').textContent),/Coming soon/);
  await type('#connector-search','');await click('[data-connector="mcp"] button');
  assert.equal(await inspect(browser,()=>document.activeElement.id),'connector-name');
  await browser.call('browser_press_key',{key:'Escape'});
  assert.equal(await inspect(browser,()=>document.activeElement.getAttribute('aria-label')),'Set up Custom MCP');
  await shot('connectors');
  const errors=resultText(await browser.call('browser_console_messages',{level:'warning',all:true}));
  assert.match(errors,/Errors: 0, Warnings: 0/);
});

test('Effectiveness page shows untested role evidence, explicit credit controls and mobile layout',async()=>{
  await click('[data-nav="evaluations"]');
  await waitUntil(browser,()=>document.querySelectorAll('#evaluation-agents tr').length===101,'agent scorecards');
  assert.match(await inspect(browser,()=>document.querySelector('#evaluation-notice').textContent),/Fixtures never count/);
  assert.equal(await inspect(browser,()=>document.querySelector('#start-evaluation').disabled),true);
  assert.equal(await inspect(browser,()=>document.querySelector('#evaluation-confirm').checked),false);
  await shot('effectiveness-desktop');
  await type('#evaluation-search','engineering-003');
  assert.equal(await inspect(browser,()=>document.querySelectorAll('#evaluation-agents tr').length),1);
  assert.match(await inspect(browser,()=>document.querySelector('#evaluation-agents').textContent),/untested/);
  await browser.call('browser_resize',{width:390,height:844});
  assert.equal(await inspect(browser,()=>document.documentElement.scrollWidth<=innerWidth),true);
  await shot('effectiveness-mobile');
  await browser.call('browser_resize',{width:1440,height:1000});
  const errors=resultText(await browser.call('browser_console_messages',{level:'warning',all:true}));
  assert.match(errors,/Errors: 0, Warnings: 0/);
});
