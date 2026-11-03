'use strict';
const $=id=>document.getElementById(id);
let revision=null,loadedEntry=null,busy=false;
const initial=new URL(location.href).searchParams.get('entry');
function display(meta,force=false){
  $('title').textContent=meta.title||'Website preview';
  const entries=meta.entries||[],previous=$('entry').value||initial;
  if(JSON.stringify(entries)!==$('entry').dataset.entries){
    $('entry').dataset.entries=JSON.stringify(entries);
    $('entry').replaceChildren(...entries.map(path=>{const option=document.createElement('option');option.value=path;option.textContent=path;return option;}));
    if(entries.includes(previous))$('entry').value=previous;
  }
  $('entry').disabled=!meta.ready;
  if(!meta.ready){$('site').hidden=true;$('site').removeAttribute('src');$('empty').hidden=false;$('empty').textContent=meta.reason;loadedEntry=null;}
  else if(force||loadedEntry===null||($('auto').checked&&revision!==meta.revision)){
    const url=new URL('site/'+$('entry').value.split('/').map(encodeURIComponent).join('/'),location.href);url.searchParams.set('revision',meta.revision);url.searchParams.set('refresh',Date.now());
    $('site').src=url.href;$('site').hidden=false;$('empty').hidden=true;loadedEntry=$('entry').value;revision=meta.revision;
  }
  const pending=meta.ready&&revision!==meta.revision;
  $('state').textContent=(meta.status==='running'?'Agents are working · ':meta.status==='blocked'?'Partial work · ':meta.status==='reviewed'?'Reviewed source · ':'Saved source · ')+(pending?'Updates available — refresh to view':loadedEntry?'Showing '+loadedEntry:'No runnable page yet');
}
async function refresh(force=false){
  if(busy)return;busy=true;$('refresh').disabled=true;
  try{const response=await fetch(new URL('status',location.href),{cache:'no-store'});if(!response.ok)throw new Error('Preview connection unavailable. Keep the local console server running, then reopen Preview if needed.');display(await response.json(),force);}
  catch(error){$('state').textContent=error.message;if(!loadedEntry){$('empty').textContent=error.message;$('empty').hidden=false;}}
  finally{busy=false;$('refresh').disabled=false;}
}
$('refresh').addEventListener('click',()=>refresh(true));$('entry').addEventListener('change',()=>refresh(true));$('auto').addEventListener('change',()=>refresh($('auto').checked));
refresh();setInterval(()=>{if(!document.hidden)refresh();},2000);
