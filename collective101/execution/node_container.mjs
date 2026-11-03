// Executed only inside the offline, bounded Docker profile.
import fs from 'node:fs';import path from 'node:path';import {spawnSync} from 'node:child_process';
try{
  fs.cpSync('/input','/tmp/project',{recursive:true});
  const cwd=path.dirname('/tmp/project/'+process.argv[2]);
  if(fs.existsSync('/opt/collective101/node_modules')){const modules=path.join(cwd,'node_modules');fs.rmSync(modules,{recursive:true,force:true});fs.symlinkSync('/opt/collective101/node_modules',modules,'dir');}
  const build=spawnSync('npm',['--offline','run','build','--','--outDir','/tmp/output'],{cwd,timeout:15000,maxBuffer:32000,env:{PATH:process.env.PATH,HOME:'/tmp',npm_config_cache:'/tmp/npm-cache'}});
  const files=[];let bytes=0;
  function walk(folder){for(const entry of fs.readdirSync(folder,{withFileTypes:true})){const target=path.join(folder,entry.name);if(entry.isSymbolicLink())throw new Error('Links are unsupported');if(entry.isDirectory())walk(target);else{if(!/\.(html|css|js|mjs|svg|json|txt)$/.test(entry.name))continue;const content=fs.readFileSync(target,'utf8');bytes+=Buffer.byteLength(content);if(bytes>40000||files.length>=24)throw new Error('Build output exceeds artifact evidence bound');files.push({path:path.relative('/tmp/output',target).split(path.sep).join('/'),content});}}}
  if(build.status===0&&fs.existsSync('/tmp/output'))walk('/tmp/output');
  process.stdout.write(JSON.stringify({passed:build.status===0&&files.some(f=>f.path.endsWith('.html')),exit_code:build.status,stdout:String(build.stdout||'').slice(0,2000),stderr:String(build.stderr||'').slice(0,2000),files}));
}catch{process.stdout.write(JSON.stringify({passed:false,error:'Offline build failed, dependency image missing, or output exceeded its bounds',files:[]}));}
