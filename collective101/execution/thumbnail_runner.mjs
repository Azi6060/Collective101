// Only the server-owned frozen artifact capability can be loaded. No page JS.
import {chromium} from 'playwright';
let input='';for await(const chunk of process.stdin){input+=chunk;if(input.length>16000)throw new Error('Thumbnail input bound');}
const options=JSON.parse(input),url=new URL(options.url),root=new URL(options.root);
if(url.protocol!=='http:'||url.hostname!=='127.0.0.1'||root.origin!==url.origin||!/^\/p\/[A-Za-z0-9_-]+\/site\/$/.test(root.pathname)||!url.href.startsWith(root.href))throw new Error('Only the frozen saved-page capability is allowed');
let browser;
try{
  browser=await chromium.launch({executablePath:options.executable,headless:true,chromiumSandbox:true,timeout:8000});
  const context=await browser.newContext({viewport:{width:960,height:600},javaScriptEnabled:false,serviceWorkers:'block',acceptDownloads:false,reducedMotion:'reduce'});
  await context.route('**/*',route=>{
    const target=new URL(route.request().url());
    return target.origin===root.origin&&target.href.startsWith(root.href)?route.continue():route.abort();
  });
  const page=await context.newPage();
  await page.goto(url.href,{waitUntil:'load',timeout:8000});
  await page.screenshot({path:options.output,type:'png',timeout:5000,animations:'disabled',fullPage:false});
  process.stdout.write(JSON.stringify({captured:true,width:960,height:600,scripts_executed:false}));
}catch{process.stdout.write(JSON.stringify({captured:false}));process.exitCode=1;}
finally{await browser?.close();}
