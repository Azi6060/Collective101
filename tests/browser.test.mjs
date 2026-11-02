// Real Chrome via MCP; model responses are scripted and state is disposable.
import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {connectBrowser,inspect,waitUntil,waitReady,resultText} from '../scripts/playwright-mcp-client.mjs';
const base=process.env.COLLECTIVE101_TEST_URL;
assert.ok(base&&process.env.COLLECTIVE101_ISOLATED_TEST==='1','Run npm run test:browser with the isolated Python service');
assert.notEqual(new URL(base).port,'8765','Never run interaction tests on the user app');
let browser;
before(async()=>{browser=await connectBrowser(base);await browser.call('browser_navigate',{url:base+'/chat'});await waitReady(browser);});
after(async()=>{await browser?.close();});
const click=target=>browser.call('browser_click',{target});
const type=(target,text)=>browser.call('browser_type',{target,text});
const shot=name=>browser.call('browser_take_screenshot',{filename:`work/playwright/test-${name}.png`,scale:'css',fullPage:true});
async function newChat(){await click('#view-chat .new-mission');}

test('desktop and mobile composer stays visible, grows, caps and shrinks',async()=>{
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
  await click('#view-evidence');
  await waitUntil(browser,()=>document.querySelectorAll('#activity-content details').length>0,'recorded evidence');
});

test('organization and connector catalog support search, roles and keyboard dismissal',async()=>{
  await click('[data-nav="organization"]');
  assert.equal(await inspect(browser,()=>document.querySelectorAll('.department-card').length),10);
  await type('#agent-search','research-003');await click('#search-results button');
  assert.match(await inspect(browser,()=>document.querySelector('#agent-inspector').textContent),/web_search/);
  await click('[data-nav="connectors"]');
  await waitUntil(browser,()=>document.querySelectorAll('.connector-card').length===9,'connector cards');
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
