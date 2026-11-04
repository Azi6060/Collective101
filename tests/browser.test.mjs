// Real Chrome via MCP; model responses are scripted and state is disposable.
import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {connectBrowser,inspect,waitUntil,waitReady,resultText} from '../scripts/playwright-mcp-client.mjs';
import {auditTextContrast} from './contrast-audit.mjs';
import {writeFile} from 'node:fs/promises';
const base=process.env.COLLECTIVE101_TEST_URL;
assert.ok(base&&process.env.COLLECTIVE101_ISOLATED_TEST==='1','Run npm run test:browser with the isolated Python service');
assert.notEqual(new URL(base).port,'8765','Never run interaction tests on the user app');
let browser;
before(async()=>{browser=await connectBrowser(base,{allowLoopbackPreviews:true});await browser.call('browser_navigate',{url:base+'/'});await waitReady(browser);await browser.call('browser_take_screenshot',{filename:'work/playwright/orbital-dashboard-initial.png',scale:'css',fullPage:true});await browser.call('browser_navigate',{url:base+'/chat'});await waitReady(browser);});
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
  assert.equal(await inspect(browser,()=>document.querySelector('#mission-results').hidden),false);
  assert.ok(await inspect(browser,()=>document.querySelectorAll('.deliverable-card').length>0));
  await click('#mission-journey>summary');
  assert.equal(await inspect(browser,()=>document.querySelectorAll('.journey-step').length),4);
  assert.match(await inspect(browser,()=>document.querySelector('.journey-step:last-child').textContent),/Reviewed/);
  assert.ok(await inspect(browser,()=>document.querySelectorAll('.mission-team .department-badge').length>0));
  await shot('studio-mission-journey');
  await browser.call('browser_hover',{target:'#mission-results h2'});
  try{await waitUntil(browser,()=>[...document.querySelectorAll('.saved-page-thumbnail')].some(image=>image.complete&&image.naturalWidth===960),'genuine static thumbnail',30000);}
  catch(error){await shot('thumbnail-capture-failure');const diagnostic=await inspect(browser,()=>({statuses:[...document.querySelectorAll('.thumbnail-status')].map(node=>node.textContent),requests:document.querySelectorAll('.thumbnail-request').length,visible:document.querySelector('.deliverable-sample')?.getBoundingClientRect().toJSON()}));throw new Error(error.message+' '+JSON.stringify(diagnostic));}
  assert.match(await inspect(browser,()=>document.querySelector('.thumbnail-status').textContent),/Static page preview/);
  await shot('visual-deliverable-thumbnail');await shot('studio-deliverables-desktop');
  const studioContrast=await inspect(browser,auditTextContrast);assert.deepEqual(studioContrast.failures,[]);
  await click('#chat-inspector>summary');
  await browser.call('browser_resize',{width:390,height:844});
  await browser.call('browser_hover',{target:'#mission-results h2'});
  const studioLayout=await inspect(browser,()=>({width:document.documentElement.scrollWidth,viewport:innerWidth,bottom:document.querySelector('#mission-form').getBoundingClientRect().bottom,height:innerHeight}));
  assert.ok(studioLayout.width<=studioLayout.viewport&&studioLayout.bottom<=studioLayout.height,JSON.stringify(studioLayout));
  await shot('studio-deliverables-mobile');await browser.call('browser_resize',{width:1440,height:1000});
  await click('[data-nav="settings"]');await click('.theme-option:has(input[value="light"])');
  await browser.call('browser_select_option',{target:'#setting-language',values:['ar']});await click('[data-nav="chat"]');
  await browser.call('browser_resize',{width:390,height:844});await browser.call('browser_hover',{target:'#mission-results h2'});
  assert.equal(await inspect(browser,()=>document.documentElement.scrollWidth<=innerWidth),true);
  assert.equal(await inspect(browser,()=>document.querySelector('.sample-source').dir),'ltr');
  const lightStudioContrast=await inspect(browser,auditTextContrast);assert.deepEqual(lightStudioContrast.failures,[]);
  await shot('studio-deliverables-light-arabic-mobile');
  await browser.call('browser_resize',{width:1440,height:1000});await click('[data-nav="settings"]');await click('#reset-preferences');await click('[data-nav="chat"]');await click('#chat-inspector>summary');
  await click('#mission-results [data-file-path="engineering/index.html"][data-file-action="0"]');
  assert.match(await inspect(browser,()=>document.querySelector('#file-source').textContent),/<!doctype html>/i);
  assert.equal(await inspect(browser,()=>document.querySelector('#mission-results iframe,#mission-results script')),null);await click('#close-file');
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
  const previewContrast=await inspect(browser,auditTextContrast);
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
  assert.deepEqual(previewContrast.failures,[]);
  assert.equal(await inspect(browser,()=>document.querySelector('#preview-project').disabled),false);
  await click('#mission-results [data-file-path="engineering/index.html"][data-file-action="1"]');
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
  assert.ok(await inspect(browser,()=>document.querySelectorAll('.timeline-entry').length>0));await shot('visual-activity-timeline');
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
  assert.equal(await inspect(browser,()=>document.querySelectorAll('.organization-node').length),10);
  await click('.organization-node[data-department="research"]');
  assert.equal(await inspect(browser,()=>document.querySelectorAll('.explorer-employee').length),9);
  await shot('visual-organization-explorer');await click('.explorer-head');
  assert.match(await inspect(browser,()=>document.querySelector('#agent-inspector').textContent),/Reports to: Mission Director/);
  await shot('visual-role-drawer');await browser.call('browser_press_key',{key:'Escape'});
  assert.equal(await inspect(browser,()=>document.activeElement.className),'explorer-head');
  await browser.call('browser_resize',{width:390,height:844});
  assert.equal(await inspect(browser,()=>document.documentElement.scrollWidth<=innerWidth),true);await shot('visual-organization-mobile');
  await browser.call('browser_resize',{width:1440,height:1000});await click('[data-nav="settings"]');await click('.theme-option:has(input[value="light"])');await click('[data-nav="organization"]');
  const explorerContrast=await inspect(browser,auditTextContrast);assert.deepEqual(explorerContrast.failures,[]);await shot('visual-organization-light');
  await click('[data-nav="settings"]');await click('.theme-option:has(input[value="dark"])');await click('[data-nav="organization"]');
  await click('[data-organization-mode="directory"]');
  await type('#agent-search','research-003');await click('#search-results button');
  assert.match(await inspect(browser,()=>document.querySelector('#agent-inspector').textContent),/web_search/);
  await click('[data-nav="connectors"]');
  await waitUntil(browser,()=>document.querySelectorAll('.connector-card').length===9,'connector cards');
  assert.equal(await inspect(browser,()=>document.querySelectorAll('.connector-icon svg').length),9);await shot('visual-connector-icons');
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

test('orbital dashboard uses the real roster and opens a mission draft',async()=>{
  await click('[data-nav="overview"]');
  if(await inspect(browser,()=>document.querySelector('.sidebar').getBoundingClientRect().width<100))await click('#toggle-sidebar');
  assert.equal(await inspect(browser,()=>document.querySelectorAll('.constellation-employee').length),90);
  assert.equal(await inspect(browser,()=>document.querySelectorAll('.constellation-head').length),10);
  await shot('orbital-dashboard-dark');
  await type('#dashboard-input','Prepare an onboarding guide for a small product team.');
  await click('#dashboard-mission button');
  assert.equal(await inspect(browser,()=>document.querySelector('#mission-input').value),'Prepare an onboarding guide for a small product team.');
  assert.equal(await inspect(browser,()=>document.querySelectorAll('#chat-messages .message').length),0);
  await shot('orbital-chat-dark');
});

test('orbital Settings supports keyboard appearance, 14 languages, reload and Arabic',async()=>{
  await click('[data-nav="settings"]');
  assert.equal(await inspect(browser,()=>document.documentElement.lang),'en');
  await click('.theme-option:has(input[value="light"])');
  await browser.call('browser_press_key',{key:'ArrowRight'});
  assert.equal(await inspect(browser,()=>document.documentElement.dataset.theme),'dark');
  await browser.call('browser_press_key',{key:'Tab'});
  const focus=await inspect(browser,()=>({id:document.activeElement.id,outline:getComputedStyle(document.activeElement).outlineWidth}));
  assert.equal(focus.id,'setting-language');assert.ok(parseFloat(focus.outline)>=2);
  const codes=await inspect(browser,()=>[...document.querySelector('#setting-language').options].map(option=>option.value));assert.equal(codes.length,14);
  for(const code of codes){await browser.call('browser_select_option',{target:'#setting-language',values:[code]});assert.equal(await inspect(browser,()=>document.documentElement.lang),code);}
  await browser.call('browser_select_option',{target:'#setting-language',values:['ar']});
  await click('#setting-reduce-motion');
  await browser.call('browser_navigate',{url:base+'/settings'});await waitReady(browser);
  assert.deepEqual(await inspect(browser,()=>({lang:document.documentElement.lang,dir:document.documentElement.dir,motion:document.documentElement.dataset.reduceMotion})),{lang:'ar',dir:'rtl',motion:'true'});
  await shot('orbital-settings-arabic');
  await browser.call('browser_resize',{width:390,height:844});
  await shot('orbital-settings-arabic-mobile');
  const rtlLayout=await inspect(browser,()=>({width:document.documentElement.scrollWidth,viewport:innerWidth}));
  assert.ok(rtlLayout.width<=rtlLayout.viewport,JSON.stringify(rtlLayout));
  await click('#toggle-sidebar');assert.ok(await inspect(browser,()=>document.querySelector('.sidebar').getBoundingClientRect().width>200));
  await browser.call('browser_press_key',{key:'Escape'});assert.ok(await inspect(browser,()=>document.querySelector('.sidebar').getBoundingClientRect().width<70));
  await browser.call('browser_resize',{width:1440,height:1000});await click('#reset-preferences');
  assert.equal(await inspect(browser,()=>document.documentElement.lang),'en');
});

test('orbital workspace views fit screen sizes and sampled text meets contrast targets',async()=>{
  const evidence=[],layoutFailures=[];
  for(const theme of ['dark','light']){
    await click('[data-nav="settings"]');await click(`.theme-option:has(input[value="${theme}"])`);
    for(const view of ['overview','organization','chat','connectors','activity','evaluations','settings']){
      await click(`[data-nav="${view}"]`);
      if(view==='evaluations')await waitUntil(browser,()=>document.querySelector('#evaluation-agents tr'));
      for(const [width,height] of theme==='dark'?[[320,568],[768,1024],[1440,1000]]:[[390,844],[1440,1000]]){
        await browser.call('browser_resize',{width,height});
        const layout=await inspect(browser,()=>({width:document.documentElement.scrollWidth,viewport:innerWidth,bottom:document.querySelector('#mission-form').getBoundingClientRect().bottom,height:innerHeight}));
        if(layout.width>layout.viewport){
          const sources=await inspect(browser,()=>[...document.querySelectorAll('body *')].map(node=>({id:node.id,cls:typeof node.className==='string'?node.className:node.tagName,width:node.getBoundingClientRect().width,right:node.getBoundingClientRect().right,left:node.getBoundingClientRect().left,scroll:node.scrollWidth,client:node.clientWidth})).filter(node=>node.width>0&&(node.right>innerWidth+1||node.left< -2||node.scroll>node.client+10)).slice(0,16));
          if(!layoutFailures.length)await shot('orbital-layout-failure');layoutFailures.push({theme,view,viewport:width,layout,sources});
        }
        if(view==='chat'&&layout.bottom>layout.height)layoutFailures.push({theme,view,viewport:width,composer:layout});
      }
      const audit=await inspect(browser,auditTextContrast);evidence.push({theme,view,...audit});
      if(['overview','settings'].includes(view))await shot('orbital-'+view+'-'+theme);
    }
  }
  await writeFile(new URL('../work/playwright/orbital-contrast.json',import.meta.url),JSON.stringify(evidence,null,2));
  assert.deepEqual(layoutFailures,[]);
  assert.deepEqual(evidence.flatMap(entry=>entry.failures.map(failure=>({theme:entry.theme,view:entry.view,...failure}))),[]);
  await click('.theme-option:has(input[value="dark"])');
  const errors=resultText(await browser.call('browser_console_messages',{level:'warning',all:true}));assert.match(errors,/Errors: 0, Warnings: 0/);
});

test('ambient motion stays sharp on hover, runs continuously and respects both reduction controls',async()=>{
  const evidence={};
  try {
    await browser.call('browser_emulate_media',{reducedMotion:'no-preference'});
    await click('[data-nav="settings"]');await click('#reset-preferences');
    await browser.call('browser_navigate',{url:base+'/dashboard'});await waitReady(browser);
    evidence.intro=await inspect(browser,()=>{
      const sweep=document.querySelector('.constellation-sweep');
      return {name:getComputedStyle(sweep).animationName,animations:sweep.getAnimations().map(animation=>({state:animation.playState,duration:animation.effect.getTiming().duration,iterations:animation.effect.getTiming().iterations,properties:[...new Set(animation.effect.getKeyframes().flatMap(frame=>Object.keys(frame)))].filter(key=>!['offset','computedOffset','easing','composite'].includes(key))}))};
    });
    assert.equal(evidence.intro.name,'constellation-sweep');assert.equal(evidence.intro.animations.length,1);
    const sweep=evidence.intro.animations[0];assert.equal(sweep.iterations,1);assert.ok(sweep.duration>0&&sweep.duration<5000);
    assert.deepEqual(sweep.properties.sort(),['opacity','transform']);
    evidence.ambient=await inspect(browser,()=>({state:document.documentElement.dataset.ambientMotion,orbits:[...document.querySelectorAll('.ambient-orbit')].map(node=>({name:getComputedStyle(node).animationName,running:node.getAnimations().some(animation=>animation.playState==='running'),continuous:node.getAnimations().some(animation=>animation.effect.getTiming().iterations===Infinity)}))}));
    assert.equal(evidence.ambient.state,'running');assert.equal(evidence.ambient.orbits.length,3);assert.ok(evidence.ambient.orbits.every(orbit=>orbit.running&&orbit.continuous));
    await waitUntil(browser,()=>document.querySelector('.ambient-orbit').getAnimations()[0]?.currentTime>800,'orbit advances');
    await shot('ambient-dashboard-running');
    evidence.beforeHover=await inspect(browser,()=>({transform:getComputedStyle(document.querySelector('#constellation')).transform,filter:getComputedStyle(document.querySelector('#constellation')).filter,width:document.querySelector('#constellation').getBoundingClientRect().width}));
    await browser.call('browser_hover',{target:'#organization-map'});
    evidence.afterHover=await inspect(browser,()=>({transform:getComputedStyle(document.querySelector('#constellation')).transform,filter:getComputedStyle(document.querySelector('#constellation')).filter,width:document.querySelector('#constellation').getBoundingClientRect().width}));
    assert.deepEqual(evidence.afterHover,evidence.beforeHover);assert.equal(evidence.afterHover.transform,'none');assert.equal(evidence.afterHover.filter,'none');
    assert.equal(await inspect(browser,()=>getComputedStyle(document.querySelector('.constellation-sweep')).animationName),'none');
    assert.equal(await inspect(browser,()=>document.querySelectorAll('[data-motion-toggle],.cluster-atmosphere text').length),0);
    assert.equal(await inspect(browser,()=>document.querySelector('.ambient-orbit').getAnimations()[0]?.playState),'running');
    await shot('sharp-map-hover');
    await browser.call('browser_navigate',{url:base+'/dashboard'});await waitReady(browser);
    assert.equal(await inspect(browser,()=>document.documentElement.dataset.ambientMotion),'running');
    await browser.call('browser_resize',{width:320,height:568});
    assert.equal(await inspect(browser,()=>document.documentElement.scrollWidth<=innerWidth),true);await shot('ambient-dashboard-mobile');
    await browser.call('browser_hover',{target:'#model-status'});
    await waitUntil(browser,()=>document.querySelector('.dashboard-hero').classList.contains('motion-offscreen'),'offscreen scene suspends');
    assert.equal(await inspect(browser,()=>document.querySelector('.ambient-orbit').getAnimations()[0]?.playState),'paused');
    await browser.call('browser_hover',{target:'#organization-map'});
    await waitUntil(browser,()=>document.querySelector('.ambient-orbit').getAnimations()[0]?.playState==='running','scene resumes when visible');
    await browser.call('browser_resize',{width:1440,height:1000});
    await click('[data-nav="settings"]');await click('#setting-reduce-motion');await click('[data-nav="overview"]');
    await browser.call('browser_hover',{target:'#organization-map'});
    evidence.setting=await inspect(browser,()=>({enabled:document.documentElement.dataset.reduceMotion,animation:getComputedStyle(document.querySelector('.constellation-sweep')).animationName,transform:getComputedStyle(document.querySelector('#constellation')).transform,active:document.querySelector('#view-overview').getAnimations({subtree:true}).length}));
    assert.deepEqual(evidence.setting,{enabled:'true',animation:'none',transform:'none',active:0});
    await click('[data-nav="settings"]');await click('#setting-reduce-motion');
    await browser.call('browser_emulate_media',{reducedMotion:'reduce'});await click('[data-nav="overview"]');
    await browser.call('browser_hover',{target:'#organization-map'});
    evidence.device=await inspect(browser,()=>({matches:matchMedia('(prefers-reduced-motion: reduce)').matches,animation:getComputedStyle(document.querySelector('.constellation-sweep')).animationName,transform:getComputedStyle(document.querySelector('#constellation')).transform,active:document.querySelector('#view-overview').getAnimations({subtree:true}).length}));
    assert.deepEqual(evidence.device,{matches:true,animation:'none',transform:'none',active:0});
    await browser.call('browser_resize',{width:390,height:844});
    assert.equal(await inspect(browser,()=>document.documentElement.scrollWidth<=innerWidth),true);await shot('motion-reduced-mobile');
    await writeFile(new URL('../work/playwright/motion-evidence.json',import.meta.url),JSON.stringify(evidence,null,2));
  } finally {
    await browser.call('browser_emulate_media',{reducedMotion:null});
    await browser.call('browser_resize',{width:1440,height:1000});
    await click('[data-nav="settings"]');await click('#reset-preferences');await click('[data-nav="overview"]');
  }
  const errors=resultText(await browser.call('browser_console_messages',{level:'warning',all:true}));assert.match(errors,/Errors: 0, Warnings: 0/);
});
