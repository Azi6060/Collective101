import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
export const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
export const resultText=result=>result.content.filter(c=>c.type==='text').map(c=>c.text).join('\n');
export async function inspect(browser,fn) {
  const result=await browser.call('browser_evaluate',{function:String(fn)});
  const match=resultText(result).match(/### Result\s+([\s\S]*?)(?=\n### |$)/);
  if(!match)throw new Error('Missing MCP evaluation result');
  return JSON.parse(match[1].trim());
}
export async function waitUntil(browser,fn,label='browser condition',timeout=30000) {
  const end=Date.now()+timeout;
  do {
    if(await inspect(browser,fn))return;
    await new Promise(resolve=>setTimeout(resolve,200));
  }while(Date.now()<end);
  throw new Error('Timed out waiting for '+label);
}
export async function waitReady(browser) {
  await waitUntil(browser,()=>document.documentElement.dataset.ready==='true','app readiness');
}
export async function connectBrowser(origin='http://127.0.0.1:8765') {
  const url=new URL(origin);
  if(url.protocol!=='http:'||!['127.0.0.1','localhost'].includes(url.hostname))throw new Error('Browser test target must be this local workspace');
  const env=Object.fromEntries(['PATH','SYSTEMROOT','WINDIR','TEMP','TMP','LOCALAPPDATA'].filter(k=>process.env[k]).map(k=>[k,process.env[k]]));
  const transport=new StdioClientTransport({command:process.execPath,cwd:root,env,stderr:'pipe',args:[
    path.join(root,'node_modules/@playwright/mcp/cli.js'),'--browser','chrome','--headless','--isolated','--sandbox',
    '--block-service-workers','--no-webmcp','--ignore-roots','--allowed-origins',url.origin,
    '--output-dir',path.join(root,'work/playwright'),'--viewport-size','1440x1000']});
  let stderr='';transport.stderr?.on('data',chunk=>{stderr=(stderr+chunk.toString()).slice(-4000);});
  const client=new Client({name:'collective101-browser-testing',version:'1.0.0'},{capabilities:{}});
  try{await client.connect(transport);}catch(error){throw new Error(error.message+' '+stderr);}
  async function call(name,args={}){const result=await client.callTool({name,arguments:args});if(result.isError)throw new Error(JSON.stringify(result.content));return result;}
  return {client,call,close:()=>client.close()};
}
if(process.argv[2]==='tools'){
  const browser=await connectBrowser();try{console.log(JSON.stringify(await browser.client.listTools(),null,2));}finally{await browser.close();}
}
