// Isolated attachment UX regressions. No HTTP server, provider, credentials or live data.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {JSDOM,VirtualConsole} from 'jsdom';
const html=await readFile(new URL('../collective101/web/index.html',import.meta.url),'utf8');
const media=await readFile(new URL('../collective101/web/attachments.js',import.meta.url),'utf8');
const app=await readFile(new URL('../collective101/web/app.js',import.meta.url),'utf8');
const renderer=app.slice(app.indexOf('function renderChat(){'),app.indexOf('function questionForm('));
async function waitFor(predicate,label,timeout=800){const until=Date.now()+timeout;while(Date.now()<until){if(predicate())return;await new Promise(r=>setTimeout(r,10));}assert.fail('Missing '+label);}
function setup(){
 const errors=[],created=[],revoked=[],requests=[];let next=0;
 const virtualConsole=new VirtualConsole();virtualConsole.on('jsdomError',error=>errors.push(error.message));
 const dom=new JSDOM(html,{url:'http://127.0.0.1:43210/chat',runScripts:'outside-only',virtualConsole});const win=dom.window;
 win.URL.createObjectURL=blob=>{const url='blob:fixture-'+(++next);created.push({url,blob});return url;};win.URL.revokeObjectURL=url=>revoked.push(url);
 win.HTMLMediaElement.prototype.play=function(){return Promise.resolve();};win.HTMLMediaElement.prototype.pause=function(){};win.HTMLMediaElement.prototype.load=function(){};
 win.fetch=async(url,options={})=>{requests.push({url,options});assert.match(String(url),/^\/api\/attachments\/att_fixture/);return {ok:true,blob:async()=>new win.Blob(['fixture-media'],{type:'application/octet-stream'}),json:async()=>({})};};
 win.__fixtureAPI=async(path,payload)=>{
  requests.push({url:path,payload});
  if(path==='/api/attachments'){const kind=/\.wav$/i.test(payload.filename)?'audio':'image';return {id:'att_fixture_'+(++next),filename:payload.filename,mime:kind==='audio'?'audio/wav':'image/png',kind,size:200,status:'uploaded',error:null};}
  assert.match(path,/^\/api\/attachments\/att_fixture[^/]*\/remove$/);return {removed:true};
 };
 const helpers=`
 const $=id=>document.getElementById(id);
 const state={token:'fixture-session-only',chat:null,chatSignature:'',pendingRequest:null,health:{features:{attachments:true,agent_chat:true}},selectedAgent:null};
 function element(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;}
 function action(label,fn,cls=''){const n=element('button',cls,label);n.type='button';n.addEventListener('click',fn);return n;}
 const api=(path,payload)=>globalThis.__fixtureAPI(path,payload);
 function notice(text){document.getElementById('notice').textContent=text;}
 function requiresRestart(){return false;}
 function renderAgentContext(){} function renderWorkspace(){} function prettyAgent(id){return id;}
 function newMission(){} function growComposer(){}
 `;
 win.eval(helpers+'\n'+media+'\n'+renderer+`\ninitAttachments();globalThis.__mediaFixture={queue:queueAttachments,render:renderChat,state,pending:()=>pendingAttachments};`);
 return {dom,win,doc:win.document,fixture:win.__mediaFixture,errors,created,revoked,requests,close:()=>win.close()};
}
async function queue(app,name,type){await app.fixture.queue([new app.win.File(['fixture'],name,{type})]);}
function chatWith(kind='audio',status='processing'){
 const file={id:'att_fixture_sent',filename:kind==='audio'?'voice.wav':'photo.png',kind,mime:kind==='audio'?'audio/wav':'image/png',size:200,status,error:null};
 return {id:'chat_fixture',title:'Fixture media',status:'intake',mode:'meta',agent_id:null,run_id:null,brief:null,error:null,questions:[],interventions:[],progress:{label:'Reading supplied media'},transcript:[{role:'user',content:'Review this attachment',attachments:[file.id]}],attachments:[file]};
}

test('attachment button opens File Folder Photo chooser before the platform picker',()=>{
 const a=setup();try{
  let opened=0;a.doc.getElementById('attachment-files').click=()=>opened++;
  a.doc.getElementById('attach-files').click();
  const menu=a.doc.getElementById('attachment-menu');assert.ok(menu,'attachment chooser must exist');assert.equal(menu.hidden,false);assert.equal(opened,0,'paperclip should show choices, not immediately open OS picker');
  assert.equal(a.doc.getElementById('attach-files').getAttribute('aria-expanded'),'true');
  for(const [id,label] of [['attachment-pick-file','File'],['attachment-pick-folder','Folder'],['attachment-pick-photo','Photo']])assert.match(a.doc.getElementById(id)?.textContent||'',new RegExp(label));
  assert.ok(a.doc.getElementById('attachment-folder')?.hasAttribute('webkitdirectory'));
  assert.match(a.doc.getElementById('attachment-photo')?.accept||'',/image\//);
 }finally{a.close();}
});

test('pending uploaded image shows a local thumbnail before Send',async()=>{
 const a=setup();try{await queue(a,'photo.png','image/png');await waitFor(()=>a.doc.querySelector('#pending-attachments img')?.src.startsWith('blob:'),'pending image preview');assert.ok(a.doc.querySelector('#pending-attachments img').alt);assert.equal(a.requests.filter(r=>r.url==='/api/attachments').length,1);}finally{a.close();}
});

test('pending voice message has replay controls before Send',async()=>{
 const a=setup();try{await queue(a,'voice.wav','audio/wav');await waitFor(()=>a.doc.querySelector('#pending-attachments audio')?.src.startsWith('blob:'),'pending voice replay');assert.equal(a.doc.querySelector('#pending-attachments audio').controls,true);}finally{a.close();}
});

test('sent photo and voice are automatically available without a View or Play prerequisite',async()=>{
 const a=setup();try{
  const photo=chatWith('image');const voice=chatWith('audio').attachments[0];voice.id='att_fixture_voice';photo.attachments.push(voice);photo.transcript[0].attachments.push(voice.id);
  a.fixture.state.chat=photo;a.fixture.render();
  await waitFor(()=>a.doc.querySelector('.sent-attachments img')?.src.startsWith('blob:'),'sent image thumbnail');
  await waitFor(()=>a.doc.querySelector('.sent-attachments audio')?.src.startsWith('blob:'),'sent voice replay');
  assert.equal(a.doc.querySelector('.sent-attachments audio').controls,true);assert.deepEqual(a.errors,[]);
 }finally{a.close();}
});

test('agent status polling preserves the existing audio element and playback position',async()=>{
 const a=setup();try{
  a.fixture.state.chat=chatWith();a.fixture.render();
  if(!a.doc.querySelector('.sent-attachments audio')){
   const play=[...a.doc.querySelectorAll('.sent-attachments button')].find(b=>b.textContent==='Play');play?.click();
  }
  await waitFor(()=>a.doc.querySelector('.sent-attachments audio'),'initial audio player');
  const player=a.doc.querySelector('.sent-attachments audio');player.currentTime=3;
  a.fixture.state.chat=JSON.parse(JSON.stringify(a.fixture.state.chat));a.fixture.state.chat.attachments[0].status='ready';a.fixture.state.chat.progress={label:'Head is reviewing'};a.fixture.render();
  assert.equal(a.doc.querySelector('.sent-attachments audio'),player,'status-only polling must not replace media DOM');assert.equal(player.currentTime,3);
 }finally{a.close();}
});

test('removing a pending preview revokes its object URL and removes replay media',async()=>{
 const a=setup();try{
  await queue(a,'photo.png','image/png');await waitFor(()=>a.doc.querySelector('#pending-attachments img'),'pending image');
  const url=a.doc.querySelector('#pending-attachments img').src;
  const remove=a.doc.querySelector('#pending-attachments button[aria-label="Remove photo.png"]');assert.ok(remove);remove.click();
  await waitFor(()=>a.doc.querySelectorAll('#pending-attachments .attachment-chip').length===0,'removed pending media');
  assert.ok(a.revoked.includes(url),'removed image object URL must be revoked');assert.equal(a.fixture.pending().length,0);
 }finally{a.close();}
});
