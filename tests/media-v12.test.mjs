// Isolated attachment UX regressions. No HTTP server, provider, credentials or live data.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {JSDOM,VirtualConsole} from 'jsdom';
const html=await readFile(new URL('../collective101/web/index.html',import.meta.url),'utf8');
// The historical six media contracts now exercise the merged controller.
// Upload and resource fixtures are local; HTTP/real conversion has separate UI tests.
const media=(await readFile(new URL('../collective101/web/media-ui.js',import.meta.url),'utf8'))+'\n'+(await readFile(new URL('../collective101/web/chat-inputs.js',import.meta.url),'utf8'));
async function waitFor(predicate,label,timeout=800){const until=Date.now()+timeout;while(Date.now()<until){if(predicate())return;await new Promise(r=>setTimeout(r,10));}assert.fail('Missing '+label);}
function setup(){
 const errors=[],created=[],revoked=[],requests=[];let next=0,uploads;
 const virtualConsole=new VirtualConsole();virtualConsole.on('jsdomError',error=>errors.push(error.message));
 const dom=new JSDOM(html,{url:'http://127.0.0.1:43210/chat',runScripts:'outside-only',virtualConsole});const win=dom.window;
 win.URL.createObjectURL=blob=>{const url='blob:fixture-'+(++next);created.push({url,blob});return url;};win.URL.revokeObjectURL=url=>revoked.push(url);
 const playing=new WeakSet();Object.defineProperty(win.HTMLMediaElement.prototype,'paused',{get(){return !playing.has(this);}});
 win.HTMLMediaElement.prototype.play=function(){playing.add(this);this.dispatchEvent(new win.Event('play'));return Promise.resolve();};win.HTMLMediaElement.prototype.pause=function(){playing.delete(this);this.dispatchEvent(new win.Event('pause'));};win.HTMLMediaElement.prototype.load=function(){};
 win.__fixtureAPI=async(path,payload)=>{
  requests.push({url:path,payload});
  if(path==='/api/attachments'){
   const kind=/\.wav$/i.test(payload.filename)?'audio':'image';
   return {id:'att_fixture_'+(++next),name:payload.filename,filename:payload.filename,mime:kind==='audio'?'audio/wav':'image/png',kind,size:200,status:'uploaded',error:null};
  }
  assert.match(path,/^\/api\/attachments\/att_fixture[^/]*\/remove$/);return {removed:true};
 };
 win.CollectiveUploads={init:handlers=>{uploads=handlers;},working:()=>false,busy:()=>false,reserve:()=>0,clear(){},cancelSource(){},
  async upload(files){for(const file of files){const item=await win.__fixtureAPI('/api/attachments',{filename:file.name});uploads.added(item,file);}}
 };
 const helpers=`
 const $=id=>document.getElementById(id);
 function element(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;}
 function action(label,fn,cls=''){const n=element('button',cls,label);n.type='button';n.addEventListener('click',fn);return n;}
 function notice(text){document.getElementById('notice').textContent=text;}
 `;
 win.eval(helpers+'\n'+media);
 const inputs=win.CollectiveChatInputs;
 inputs.init({api:win.__fixtureAPI,token:()=> 'fixture-session-only',changed(){},draftChanged(){},expired(){},save(){},
  resource:async path=>{requests.push({url:path});return new win.Blob(['fixture-media'],{type:'application/octet-stream'});}
 });inputs.available(true);
 const state={chat:null};
 const fixture={state,pending:()=>inputs.ids(),queue:files=>inputs.uploadFiles(files),render(){
  // Preserve the message node during a status-only update, as renderChat does.
  if(!win.document.querySelector('#chat-messages [data-message-index="0"]')){
   const bubble=win.document.createElement('div');bubble.dataset.messageIndex='0';bubble.className='message user';
   win.document.getElementById('chat-messages').replaceChildren(bubble);
  }
  inputs.onChat(state.chat,'chat');
 }};
 return {dom,win,doc:win.document,fixture,errors,created,revoked,requests,close:()=>{win.dispatchEvent(new win.Event('pagehide'));win.close();}};
}
async function queue(app,name,type){await app.fixture.queue([new app.win.File(['fixture'],name,{type})]);}
function chatWith(kind='audio',status='processing'){
 const file={id:'att_fixture_sent',filename:kind==='audio'?'voice.wav':'photo.png',name:kind==='audio'?'voice.wav':'photo.png',kind,mime:kind==='audio'?'audio/wav':'image/png',size:200,status,error:null};
 return {id:'chat_fixture',title:'Fixture media',status:'intake',mode:'meta',agent_id:null,run_id:null,brief:null,error:null,questions:[],interventions:[],progress:{label:'Reading supplied media'},transcript:[{role:'user',content:'Review this attachment',attachments:[file.id]}],attachments:[file]};
}

test('attachment button opens File Folder Photo chooser before the platform picker',()=>{
 const a=setup();try{
  let opened=0;a.doc.getElementById('chat-files').click=()=>opened++;
  a.doc.getElementById('attach-files').click();
  const menu=a.doc.getElementById('attachment-menu');assert.ok(menu,'attachment chooser must exist');assert.equal(menu.hidden,false);assert.equal(opened,0,'paperclip should show choices, not immediately open OS picker');
  assert.equal(a.doc.getElementById('attach-files').getAttribute('aria-expanded'),'true');
  for(const [id,label] of [['attachment-pick-file','File'],['attachment-pick-folder','Folder'],['attachment-pick-photo','Photo']])assert.match(a.doc.getElementById(id)?.textContent||'',new RegExp(label));
  assert.ok(a.doc.getElementById('chat-folder')?.hasAttribute('webkitdirectory'));
  assert.match(a.doc.getElementById('chat-photo')?.accept||'',/image\//);
 }finally{a.close();}
});

test('pending uploaded image shows a local thumbnail before Send',async()=>{
 const a=setup();try{await queue(a,'photo.png','image/png');await waitFor(()=>a.doc.querySelector('#composer-attachments img')?.src.startsWith('blob:'),'pending image preview');assert.ok(a.doc.querySelector('#composer-attachments img').alt);assert.equal(a.requests.filter(r=>r.url==='/api/attachments').length,1);}finally{a.close();}
});

test('pending voice message has working replay and seeking controls before Send',async()=>{
 const a=setup();try{
  await queue(a,'voice.wav','audio/wav');await waitFor(()=>a.doc.querySelector('#composer-attachments audio')?.src.startsWith('blob:'),'pending voice replay');
  const audio=a.doc.querySelector('#composer-attachments audio'),play=a.doc.querySelector('#composer-attachments .audio-play'),seek=a.doc.querySelector('#composer-attachments .audio-seek');
  assert.equal(audio.controls,true);Object.defineProperty(audio,'duration',{value:10});audio.dispatchEvent(new a.win.Event('loadedmetadata'));
  assert.equal(seek.disabled,false);seek.value='500';seek.dispatchEvent(new a.win.Event('input'));assert.equal(audio.currentTime,5);
  play.click();assert.equal(audio.paused,false);assert.match(play.getAttribute('aria-label'),/^Pause/);
  play.click();assert.equal(audio.paused,true);assert.match(play.getAttribute('aria-label'),/^Play/);
  assert.deepEqual(a.errors,[]);
 }finally{a.close();}
});

test('sent photo and voice are automatically available without a View or Play prerequisite',async()=>{
 const a=setup();try{
  const photo=chatWith('image');const voice=chatWith('audio').attachments[0];voice.id='att_fixture_voice';photo.attachments.push(voice);photo.transcript[0].attachments.push(voice.id);
  a.fixture.state.chat=photo;a.fixture.render();
  await waitFor(()=>a.doc.querySelector('.message-attachments img')?.src.startsWith('blob:'),'sent image thumbnail');
  await waitFor(()=>a.doc.querySelector('.message-attachments audio')?.src.startsWith('blob:'),'sent voice replay');
  assert.equal(a.doc.querySelector('.message-attachments audio').controls,true);assert.deepEqual(a.errors,[]);
 }finally{a.close();}
});

test('agent status polling preserves the existing audio element and playback position',async()=>{
 const a=setup();try{
  a.fixture.state.chat=chatWith();a.fixture.render();
  if(!a.doc.querySelector('.message-attachments audio')){
   const play=[...a.doc.querySelectorAll('.message-attachments button')].find(b=>b.textContent==='Play');play?.click();
  }
  await waitFor(()=>a.doc.querySelector('.message-attachments audio'),'initial audio player');
  const player=a.doc.querySelector('.message-attachments audio');player.currentTime=3;
  a.fixture.state.chat=JSON.parse(JSON.stringify(a.fixture.state.chat));a.fixture.state.chat.attachments[0].status='ready';a.fixture.state.chat.progress={label:'Head is reviewing'};a.fixture.render();
  assert.equal(a.doc.querySelector('.message-attachments audio'),player,'status-only polling must not replace media DOM');assert.equal(player.currentTime,3);
 }finally{a.close();}
});

test('removing a pending preview revokes its object URL and removes replay media',async()=>{
 const a=setup();try{
  await queue(a,'photo.png','image/png');await waitFor(()=>a.doc.querySelector('#composer-attachments img'),'pending image');
  const url=a.doc.querySelector('#composer-attachments img').src;
  const remove=a.doc.querySelector('#composer-attachments button[aria-label="Remove photo.png"]');assert.ok(remove);remove.click();
  await waitFor(()=>a.doc.querySelectorAll('#composer-attachments .attachment-chip').length===0,'removed pending media');
  assert.ok(a.revoked.includes(url),'removed image object URL must be revoked');assert.equal(a.fixture.pending().length,0);
 }finally{a.close();}
});
