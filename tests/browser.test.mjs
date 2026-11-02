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
async function newChat(){await click('.nav-link[data-nav="chat"]');await click('#view-chat .new-mission');}

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

test('all views fit narrow mobile, tablet, laptop and desktop viewports',async()=>{
  const pages=['overview','organization','chat','connectors','activity'];
  const viewports=[[320,568],[360,640],[390,844],[768,1024],[1024,768],[1280,720],[1440,1000]];
  try{
    for(const name of pages){
      await click(`.nav-link[data-nav="${name}"]`);
      for(const [width,height] of viewports){
        await browser.call('browser_resize',{width,height});
        const layout=await inspect(browser,()=>({
          scrollWidth:document.documentElement.scrollWidth,
          viewport:innerWidth,
          active:document.querySelector('.view:not(.d-none)')?.id,
          composer:document.querySelector('#mission-form')?.getBoundingClientRect().bottom??null,
          height:innerHeight
        }));
        assert.equal(layout.active,`view-${name}`);
        assert.ok(layout.scrollWidth<=layout.viewport,`${name} has horizontal overflow at ${width}x${height}: ${layout.scrollWidth}px`);
        if(name==='chat')assert.ok(layout.composer<=layout.height,`Chat composer exceeds ${width}x${height}`);
      }
    }
  }finally{await browser.call('browser_resize',{width:1440,height:1000});}
});

test('visible views expose named controls, form labels and page headings',async()=>{
  for(const name of ['overview','organization','chat','connectors','activity']){
    await click(`.nav-link[data-nav="${name}"]`);
    const audit=await inspect(browser,()=>{
      const visible=element=>!!(element.offsetWidth||element.offsetHeight||element.getClientRects().length);
      const active=document.querySelector('.view:not(.d-none)');
      const controls=[...document.querySelectorAll('button,a,input:not([type="hidden"]),textarea,select,[role="button"]')].filter(visible);
      const named=element=>element.getAttribute('aria-label')||element.getAttribute('aria-labelledby')||element.title||(
        element.matches('input,textarea,select')?element.labels?.length:element.textContent.trim()
      );
      return {
        mainCount:document.querySelectorAll('main').length,
        navCount:document.querySelectorAll('nav').length,
        headingCount:active.querySelectorAll('h1').length,
        unnamed:controls.filter(element=>!named(element)).map(element=>element.outerHTML.slice(0,120)),
        unlabelledFields:controls.filter(element=>element.matches('input,textarea,select')&&!element.getAttribute('aria-label')&&!element.getAttribute('aria-labelledby')&&!element.labels?.length).map(element=>element.id||element.outerHTML.slice(0,120)),
        imagesWithoutAlt:[...active.querySelectorAll('img:not([alt])')].length,
        skipLink:!!document.querySelector('a.skip-link[href="#main"]')
      };
    });
    assert.equal(audit.mainCount,1,`${name} must have one main landmark`);
    assert.equal(audit.navCount,1,`${name} must have one navigation landmark`);
    assert.equal(audit.headingCount,1,`${name} must have one page heading`);
    assert.deepEqual(audit.unnamed,[],`${name} has visible controls without accessible names`);
    assert.deepEqual(audit.unlabelledFields,[],`${name} has form controls without labels`);
    assert.equal(audit.imagesWithoutAlt,0,`${name} has images without alt text`);
    assert.equal(audit.skipLink,true);
  }
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
