import {chromium} from 'playwright';
let input='';for await(const chunk of process.stdin){input+=chunk;if(input.length>1200000)throw new Error('Browser input bound');}
const options=JSON.parse(input),url=new URL(options.url);
if(url.protocol!=='http:'||url.hostname!=='127.0.0.1'||!options.root.startsWith(url.origin+'/p/'))throw new Error('Only the supplied static preview is accessible');
let browser,stage='launch';
try{
  browser=await chromium.launch({executablePath:options.executable,headless:true,chromiumSandbox:true,timeout:10000});
  stage='context';
  const context=await browser.newContext({viewport:{width:1280,height:900},serviceWorkers:'block',acceptDownloads:false});
  await context.route('**/*',route=>route.request().url().startsWith(options.root)?route.continue():route.abort());
  context.on('page',page=>{page.on('dialog',dialog=>dialog.dismiss());});
  const page=await context.newPage(),errors=[];page.on('pageerror',()=>errors.push('Page script error'));
  stage='page load';
  await page.goto(options.url,{waitUntil:'domcontentloaded',timeout:10000});
  await page.locator('#site:not([hidden])').waitFor({timeout:8000});
  const frame=page.frameLocator('#site'),checks=[];
  for(const check of options.checks){
    let passed=true,actual=null,error=null;const locator=frame.locator(check.selector);
    try{
      if(check.action==='click')await locator.click({timeout:2000});
      if(check.action==='fill')await locator.fill(check.text,{timeout:2000});
      if('contains' in check){actual=(await locator.innerText({timeout:2000})).slice(0,2000);passed&&=actual.includes(check.contains);}
      if('equals' in check){actual=(await locator.innerText({timeout:2000})).slice(0,2000);passed&&=actual.trim()===check.equals;}
      if('visible' in check){actual=await locator.isVisible();passed&&=actual===check.visible;}
      if('count' in check){actual=await locator.count();passed&&=actual===check.count;}
    }catch{passed=false;error='Selector/action failed within its deadline';}
    checks.push({selector:check.selector,action:check.action||'assert',passed,actual,error});
  }
  process.stdout.write(JSON.stringify({engine:'Chromium isolated static project',passed:checks.every(c=>c.passed)&&errors.length===0,checks,script_errors:errors.slice(0,5),viewport:{width:1280,height:900}}));
}catch(error){process.stdout.write(JSON.stringify({engine:'Chromium isolated static project',passed:false,checks:[],error:'Isolated browser or page load failed',stage,failure_type:error.name,diagnostic:String(error.message).split('\n').slice(0,3).join(' ').replace(/https?:\/\/\S+/g,'[preview URL]').slice(0,300)}));}
finally{await browser?.close();}
