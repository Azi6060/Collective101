import {connectBrowser,root,waitReady,inspect,waitUntil} from './playwright-mcp-client.mjs';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
const target=process.env.COLLECTIVE101_BROWSER_URL||'http://127.0.0.1:8765';
const browser=await connectBrowser(target);
const output=path.join(root,'work/playwright');await mkdir(output,{recursive:true});
const text=result=>result.content.filter(c=>c.type==='text').map(c=>c.text).join('\n');
try {
  await browser.call('browser_navigate',{url:new URL('/chat',target).href});
  await waitReady(browser);
  const nav=await browser.call('browser_snapshot');
  await writeFile(path.join(output,'chat-snapshot.txt'),text(nav));
  await browser.call('browser_take_screenshot',{filename:'work/playwright/chat-desktop.png',fullPage:true,scale:'css'});
  const metrics=await browser.call('browser_evaluate',{function:`() => {
    const input=document.querySelector('#mission-input');
    return {title:document.title,ready:document.documentElement.dataset.ready,
      viewport:{width:innerWidth,height:innerHeight},documentWidth:document.documentElement.scrollWidth,
      composer:input?{resize:getComputedStyle(input).resize,height:input.getBoundingClientRect().height}:null,
      separateStatus:!!document.querySelector('#chat-progress')&&!document.querySelector('#chat-messages #chat-progress')};
  }`});
  await writeFile(path.join(output,'chat-metrics.txt'),text(metrics));console.log(text(metrics));
  await browser.call('browser_resize',{width:390,height:844});
  const mobile=await inspect(browser,()=>({width:document.documentElement.scrollWidth,viewport:innerWidth,composerBottom:document.querySelector('#mission-form').getBoundingClientRect().bottom,height:innerHeight}));
  assert.ok(mobile.width<=mobile.viewport&&mobile.composerBottom<=mobile.height,'Mobile composer must fit the viewport');
  await writeFile(path.join(output,'chat-mobile-metrics.json'),JSON.stringify(mobile,null,2));
  await browser.call('browser_take_screenshot',{filename:'work/playwright/chat-mobile.png',fullPage:true,scale:'css'});
  await writeFile(path.join(output,'chat-mobile-snapshot.txt'),text(await browser.call('browser_snapshot')));
  await browser.call('browser_resize',{width:1440,height:1000});
  await browser.call('browser_navigate',{url:new URL('/connectors',target).href});
  await waitReady(browser);
  await waitUntil(browser,()=>document.querySelectorAll('.connector-card').length===9,'connector catalog');
  await browser.call('browser_take_screenshot',{filename:'work/playwright/connectors-desktop.png',fullPage:true,scale:'css'});
  const errors=await browser.call('browser_console_messages',{level:'error',all:true});
  await writeFile(path.join(output,'console-errors.txt'),text(errors));console.log(text(errors));
  console.log('Saved browser evidence to '+output);
} finally {await browser.close();}
