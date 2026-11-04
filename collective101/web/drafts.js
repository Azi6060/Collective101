'use strict';
// Bounded text/reference recovery in this tab only. Never stores audio, file bytes or credentials.
window.CollectiveDrafts=(()=>{
  const prefix='collective101.drafts.v1:',ttl=24*60*60*1000;
  let key=null,entries={},available=true;
  function prune(){
    entries=Object.fromEntries(Object.entries(entries).filter(([context,value])=>typeof context==='string'&&context.length<=100&&value&&typeof value.text==='string'&&value.text.length<=500000&&Number.isFinite(value.at)&&value.at<=Date.now()+60000&&Date.now()-value.at<ttl)
      .sort((a,b)=>b[1].at-a[1].at).slice(0,20));
  }
  function persist(){prune();if(key)try{sessionStorage.setItem(key,JSON.stringify(entries));available=true;}catch{available=false;}}
  function configure(scope){
    key=prefix+encodeURIComponent(scope||'guest');entries={};
    try{const source=sessionStorage.getItem(key);if(source&&source.length<=600000){const parsed=JSON.parse(source);if(parsed&&typeof parsed==='object'&&!Array.isArray(parsed))entries=parsed;}}catch{available=false;}
    persist();
  }
  function get(context){prune();const value=entries[context];if(!value)return null;
    return {...value,attachments:Array.isArray(value.attachments)?value.attachments.filter(id=>typeof id==='string'&&/^att_[a-f0-9]{32}$/.test(id)):[]};
  }
  function save(context,text,attachments=[],agentId=null){
    if(!key)return;
    const before=get(context),ids=[...attachments];
    if(!text&&!ids.length){delete entries[context];persist();return;}
    const same=before&&before.text.trim()===String(text).trim()&&JSON.stringify(before.attachments)===JSON.stringify(ids)&&before.agentId===agentId;
    entries[context]={text:String(text).slice(0,500000),attachments:ids,agentId,at:Date.now(),...(same&&before.request?{request:before.request}:{})};persist();
  }
  function request(context,payload){
    const before=get(context),fingerprint=JSON.stringify(payload);
    const prior=before?.request;
    const id=prior&&typeof prior.id==='string'&&/^[\w-]{8,80}$/.test(prior.id)&&prior.fingerprint===fingerprint?prior.id:crypto.randomUUID();
    entries[context]={text:before&&before.text.trim()===payload.message?before.text:payload.message,attachments:payload.attachments||[],agentId:payload.agent_id||before?.agentId||null,at:Date.now(),request:{id,fingerprint}};persist();return id;
  }
  function remove(context){delete entries[context];persist();}
  function purge(){
    entries={};try{for(const name of Object.keys(sessionStorage))if(name.startsWith(prefix)||name==='collective-chat')sessionStorage.removeItem(name);}catch{available=false;}
    key=null;
  }
  return {configure,get,save,request,remove,purge,available:()=>available};
})();
