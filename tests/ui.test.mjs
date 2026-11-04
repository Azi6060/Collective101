import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {JSDOM,VirtualConsole} from 'jsdom';
const base=process.env.COLLECTIVE101_TEST_URL;
if(!base)throw new Error('Run npm.cmd run test:ui to use the isolated test service.');
const html=await readFile(new URL('../collective101/web/index.html',import.meta.url),'utf8');
const script=await readFile(new URL('../collective101/web/app.js',import.meta.url),'utf8');
const presentationScripts=await Promise.all(['locales.js','polish-locales.js','preferences.js','visuals.js','organization-ui.js','thumbnail-ui.js','mission-ui.js','accounts-ui.js','drafts.js','workspace-tools.js','upload-queue.js','voice-waveform.js','media-ui.js','chat-inputs.js','dashboard.js'].map(file=>readFile(new URL('../collective101/web/'+file,import.meta.url),'utf8')));
const markdownScripts=await Promise.all(['vendor/marked.umd.js','vendor/purify.min.js','markdown.js'].map(file=>readFile(new URL('../collective101/web/'+file,import.meta.url),'utf8')));
async function waitFor(predicate,timeout=25000){const end=Date.now()+timeout;while(Date.now()<end){if(await predicate())return;await new Promise(resolve=>setTimeout(resolve,70));}throw new Error('Timed out waiting for UI state');}
async function setup(healthOverride=null,options={}){
  const errors=[];const virtualConsole=new VirtualConsole();virtualConsole.on('jsdomError',error=>errors.push(error.message));
  const dom=new JSDOM(html,{url:base+(options.path||'/'),runScripts:'outside-only',virtualConsole,pretendToBeVisual:true});
  const win=dom.window;let poll=()=>{};const pending=new Set();
  const track=promise=>{pending.add(promise);promise.then(()=>pending.delete(promise),()=>pending.delete(promise));return promise;};
  if(options.savedSession)for(const [key,value] of Object.entries(options.savedSession))win.sessionStorage.setItem(key,value);
  if(options.sessionStorageBlocked)Object.defineProperty(win,'sessionStorage',{get(){throw new Error('Session storage blocked fixture');}});
  if(options.savedPreferences)win.localStorage.setItem('collective101.preferences.v1',JSON.stringify(options.savedPreferences));
  if(options.ambientPaused)win.localStorage.setItem('collective101.ambient-paused.v1','true');
  if(options.storageBlocked)Object.defineProperty(win,'localStorage',{get(){throw new Error('Storage blocked');}});
  win.matchMedia=query=>({matches:query.includes('reduced-motion')?options.systemReducedMotion===true:query.includes('pointer')?true:options.systemDark===true,addEventListener(){}});
  if(options.speech){
    win.__recognitions=[];
    win.SpeechRecognition=class {constructor(){win.__recognitions.push(this);}start(){this.onstart?.();}stop(){this.onend?.();}abort(){this.onend?.();}};
    win.SpeechSynthesisUtterance=class {constructor(text){this.text=text;}};
    win.speechSynthesis={spoken:[],cancel(){},getVoices:()=>[{lang:'en-US'}],speak(value){this.spoken.push(value);}};
  }
  if(options.recording){
    win.__audioTime=0;win.__signal=0;win.__recorders=[];win.__revoked=[];win.__objectURLCounter=0;win.__closedContexts=0;
    Object.defineProperty(win.performance,'now',{value:()=>win.__audioTime});
    win.__track=new win.EventTarget();win.__track.stopped=false;win.__track.stop=()=>{win.__track.stopped=true;};
    const stream={getTracks:()=>[win.__track]};
    Object.defineProperty(win.navigator,'mediaDevices',{value:{getUserMedia:async()=>{
      if(options.recording==='denied')throw new win.DOMException('Fixture denial','NotAllowedError');
      if(options.recording==='pending')return new Promise(resolve=>{win.__resolveMicrophone=()=>resolve(stream);});
      return stream;
    }}});
    win.MediaRecorder=class {static isTypeSupported(){return true;}constructor(){this.state='inactive';this.mimeType='audio/webm';win.__recorders.push(this);}start(){this.state='recording';}stop(){this.state='inactive';this.ondataavailable?.({data:new win.Blob(['fixture audio bytes'],{type:this.mimeType})});win.queueMicrotask(()=>this.onstop?.());}};
    win.AudioContext=class {resume(){return Promise.resolve();}close(){win.__closedContexts++;return Promise.resolve();}decodeAudioData(){return Promise.resolve({duration:4});}createMediaStreamSource(){return {connect(){},disconnect(){}};}createAnalyser(){return {getByteTimeDomainData:bytes=>bytes.fill(128+win.__signal)};}};
    win.Blob.prototype.arrayBuffer=function(){return new Promise((resolve,reject)=>{const reader=new win.FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(reader.error);reader.readAsArrayBuffer(this);});};
    win.OfflineAudioContext=class {constructor(channels,length){this.length=length;this.destination={};}createBufferSource(){return {connect(){},start(){}};}async startRendering(){return {getChannelData:()=>new Float32Array(this.length)};}};
    win.URL.createObjectURL=()=> 'blob:fixture-'+(++win.__objectURLCounter);win.URL.revokeObjectURL=url=>win.__revoked.push(url);
    let paused=true;Object.defineProperty(win.HTMLMediaElement.prototype,'paused',{get:()=>paused});
    win.HTMLMediaElement.prototype.play=function(){paused=false;this.dispatchEvent(new win.Event('play'));return Promise.resolve();};
    win.HTMLMediaElement.prototype.pause=function(){paused=true;this.dispatchEvent(new win.Event('pause'));};win.HTMLMediaElement.prototype.load=function(){};
  }
  win.fetch=(url,requestOptions={})=>track((async()=>{const target=new URL(url,base);assert.equal(target.origin,base);const response=await fetch(target,{...requestOptions,headers:{...requestOptions.headers,...(requestOptions.method==='POST'?{Origin:base}:{})}});if(target.pathname==='/api/account/me'&&options.accountState)return {ok:true,json:async()=>options.accountState};if(target.pathname==='/api/health'&&healthOverride){const data=await response.json();return {ok:response.ok,json:async()=>({...data,...healthOverride})};}if(target.pathname==='/api/chats'&&options.chatRows&&requestOptions.method!=='POST')return {ok:true,json:async()=>options.chatRows};await response.clone().arrayBuffer();return response;})());
  win.__uploadAttempts=0;
  if(options.restoreOffline){const original=win.fetch;win.fetch=(url,request)=>String(url).startsWith('/api/attachments?')&&options.restoreOffline?Promise.reject(new Error('Offline recovery fixture')):original(url,request);}
  win.XMLHttpRequest=class {
    constructor(){this.upload={};this.headers={};this.controller=new AbortController();}
    open(method,url){this.method=method;this.url=url;}
    setRequestHeader(name,value){this.headers[name]=value;}
    abort(){this.aborted=true;this.controller.abort();this.onabort?.();}
    send(body){win.__uploadAttempts++;this.upload.onprogress?.({lengthComputable:true,loaded:50,total:100});
      const finish=async()=>{if(this.aborted)return;
        if(win.__failUploadOnce){win.__failUploadOnce=false;this.onerror?.();return;}
        try{const response=await fetch(new URL(this.url,base),{method:this.method,headers:{...this.headers,Origin:base},body,signal:this.controller.signal});this.status=response.status;this.responseText=await response.text();this.upload.onload?.();if(!this.aborted)this.onload?.();}catch(error){if(!this.aborted)this.onerror?.(error);}
      };
      if(win.__holdUploads)win.__finishUpload=()=>track(finish());else track(finish());
    }
  };
  win.setInterval=(fn,delay)=>{if(delay===100){win.__voiceTick=fn;return 2;}poll=fn;return 1;};win.HTMLElement.prototype.scrollIntoView=function(){};
  for(const code of markdownScripts.slice(0,2))win.eval(code);
  // Match the real /app.js bundle so shared strict-scope media functions resolve.
  win.eval(markdownScripts[2]+'\n'+presentationScripts.join('\n;\n')+'\n'+script+'\nglobalThis.__testShowSource=showSource;');
  await waitFor(()=>win.document.documentElement.dataset.ready==='true');
  async function close(){
    // Event-handler fetch/JSON continuations must finish before jsdom is destroyed.
    // Rejections remain visible; teardown never catches or discards failures.
    for(let turn=0;turn<20;turn++){
      await Promise.all([...pending]);await new Promise(resolve=>setTimeout(resolve,0));
      if(!pending.size){await new Promise(resolve=>setTimeout(resolve,0));if(!pending.size)break;}
    }
    assert.equal(pending.size,0,'UI requests must settle before teardown');win.close();
  }
  return {dom,win,doc:win.document,poll:()=>poll(),errors,close};
}
function submit(win,form){form.dispatchEvent(new win.Event('submit',{bubbles:true,cancelable:true}));}
function openConnectors(app){app.doc.querySelector('[data-nav="settings"]').click();app.doc.getElementById('settings-connectors').click();}
const sessionSnapshot=win=>Object.fromEntries(Object.keys(win.sessionStorage).map(key=>[key,win.sessionStorage.getItem(key)]));

test('saved-work search rename and file filtering use real metadata and preserve inert titles',async()=>{
  const app=await setup();try{
    app.doc.querySelector('.new-mission').click();await app.win.CollectiveChatInputs.uploadFiles([new app.win.File(['Fixture search reference.'],'wrap-up-UI-notes.txt')]);
    app.doc.getElementById('mission-input').value='Hi';submit(app.win,app.doc.getElementById('mission-form'));
    await waitFor(async()=>{await app.poll();return app.doc.getElementById('chat-status').textContent==='answered';});
    app.doc.getElementById('rename-chat').click();app.doc.getElementById('rename-title').value='Review <img src=x> board';submit(app.win,app.doc.getElementById('rename-form'));
    await waitFor(()=>app.doc.getElementById('workspace-title').textContent==='Review <img src=x> board');
    assert.equal(app.doc.querySelector('#workspace-title img'),null);assert.equal(app.doc.getElementById('rename-dialog').hasAttribute('open'),false);
    app.doc.getElementById('chat-history').open=true;app.doc.getElementById('history-search').value='wrap-up-UI';await app.win.CollectiveWorkspaceTools.search();
    assert.match(app.doc.getElementById('recent-missions').textContent,/wrap-up-UI-notes/);
    app.doc.querySelector('#recent-missions button').click();await waitFor(()=>!app.doc.getElementById('workspace-panel-references').hidden);
    assert.equal(app.doc.getElementById('workspace-file-search').value,'wrap-up-UI');assert.equal(app.doc.querySelectorAll('#workspace-references .reference-file').length,1);
    app.doc.getElementById('workspace-file-search').value='no-match-ever';app.doc.getElementById('workspace-file-search').dispatchEvent(new app.win.Event('input'));
    assert.equal(app.doc.querySelectorAll('#workspace-references .reference-file').length,0);
    app.doc.getElementById('history-search').value='no-match-ever';await app.win.CollectiveWorkspaceTools.search();assert.match(app.doc.getElementById('recent-missions').textContent,/No matching/);assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});

test('text and completed attachment drafts recover after refresh and stay scoped to each account',async()=>{
  const identity={configured:true,user:{id:'fixture-alice',name:'Alice',username:'alice',role:'owner'}};
  const original=await setup(null,{accountState:identity});let restored,other;
  try{
    original.doc.querySelector('.new-mission').click();original.doc.getElementById('mission-input').value='Keep my unfinished work.';original.doc.getElementById('mission-input').dispatchEvent(new original.win.Event('input'));
    await original.win.CollectiveChatInputs.uploadFiles([new original.win.File(['These bytes are not stored in sessionStorage.'],'draft-restore.txt')]);
    const saved=sessionSnapshot(original.win);assert.ok(Object.keys(saved).some(key=>key.includes('fixture-alice')));assert.ok(!JSON.stringify(saved).includes('These bytes are not stored'));
    restored=await setup(null,{accountState:identity,savedSession:saved});
    assert.equal(restored.doc.getElementById('mission-input').value,'Keep my unfinished work.');assert.equal(restored.win.CollectiveChatInputs.ids().length,1);assert.equal(restored.doc.getElementById('draft-recovery').hidden,false);
    other=await setup(null,{accountState:{configured:true,user:{id:'fixture-bob',name:'Bob',username:'bob',role:'member'}},savedSession:saved});
    assert.equal(other.doc.getElementById('mission-input').value,'');assert.equal(other.win.CollectiveChatInputs.ids().length,0);
    restored.doc.getElementById('discard-draft').click();assert.equal(restored.doc.getElementById('mission-input').value,'');assert.equal(restored.win.CollectiveDrafts.get('new'),null);assert.deepEqual(restored.errors,[]);
  }finally{await original.close();if(restored)await restored.close();if(other)await other.close();}
});

test('a lost send response preserves the draft and retry identity across refresh without creating another chat',async()=>{
  const original=await setup();let restored;try{
    original.doc.querySelector('.new-mission').click();await original.win.CollectiveChatInputs.uploadFiles([new original.win.File(['A retry reference.'],'retry-reference.txt')]);
    let requestId;const fetchOriginal=original.win.fetch;
    original.win.fetch=async(url,options)=>{const response=await fetchOriginal(url,options);if(String(url)==='/api/chats'&&options?.method==='POST'){requestId=JSON.parse(options.body).request_id;throw new Error('Lost response fixture');}return response;};
    original.doc.getElementById('mission-input').value='  Hi  ';original.doc.getElementById('mission-input').dispatchEvent(new original.win.Event('input'));submit(original.win,original.doc.getElementById('mission-form'));
    await waitFor(()=>original.doc.getElementById('notice').textContent.includes('Lost response fixture'));
    const count=(await (await fetchOriginal('/api/chats')).json()).length;
    original.win.dispatchEvent(new original.win.Event('pagehide'));
    restored=await setup(null,{savedSession:sessionSnapshot(original.win)});assert.equal(restored.doc.getElementById('mission-input').value,'  Hi  ');assert.equal(restored.win.CollectiveChatInputs.ids().length,1);
    let retried;const fetchRestored=restored.win.fetch;restored.win.fetch=(url,options)=>{if(String(url)==='/api/chats'&&options?.method==='POST')retried=JSON.parse(options.body).request_id;return fetchRestored(url,options);};
    submit(restored.win,restored.doc.getElementById('mission-form'));await waitFor(async()=>{await restored.poll();return restored.doc.getElementById('chat-status').textContent==='answered';});
    assert.equal(retried,requestId);assert.equal((await (await fetchRestored('/api/chats')).json()).length,count);assert.equal(restored.win.CollectiveDrafts.get('new'),null);assert.deepEqual(restored.errors,[]);
  }finally{await original.close();if(restored)await restored.close();}
});

test('upload progress cancellation and explicit retry preserve completed files and block incomplete sends',async()=>{
  const app=await setup();try{
    app.doc.querySelector('.new-mission').click();await app.win.CollectiveChatInputs.uploadFiles([new app.win.File(['Keep this file.'],'upload-success.txt')]);
    app.win.__holdUploads=true;const uploading=app.win.CollectiveChatInputs.uploadFiles([new app.win.File(['Retry this file.'],'upload-retry.txt')]);
    await waitFor(()=>app.doc.querySelector('#upload-queue progress')?.value===50);assert.equal(app.doc.getElementById('send-mission').disabled,true);
    app.doc.querySelector('#upload-queue button').click();await uploading;assert.match(app.doc.getElementById('upload-queue').textContent,/Cancelled/);assert.equal(app.win.CollectiveChatInputs.ids().length,1);
    app.win.__holdUploads=false;app.win.__failUploadOnce=true;app.doc.querySelector('#upload-queue button').click();await waitFor(()=>!!app.doc.querySelector('#upload-queue [data-state="failed"]'));
    assert.equal(app.doc.getElementById('send-mission').disabled,true);assert.equal(app.win.CollectiveChatInputs.ids().length,1);
    app.doc.querySelector('#upload-queue button').click();await waitFor(()=>app.win.CollectiveChatInputs.ids().length===2);assert.equal(app.doc.getElementById('upload-queue').hidden,true);assert.equal(app.doc.getElementById('send-mission').disabled,false);assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});

test('draft cache expires bounds and purges its own data without storing credentials or blocking when storage is denied',async()=>{
  const code=await readFile(new URL('../collective101/web/drafts.js',import.meta.url),'utf8'),dom=new JSDOM('',{url:base,runScripts:'outside-only'});try{
    const win=dom.window;win.eval(code);const drafts=win.CollectiveDrafts;drafts.configure('alice');
    for(let index=0;index<25;index++)drafts.save('chat_'+index,'Text '+index);
    assert.ok(Object.keys(JSON.parse(win.sessionStorage.getItem('collective101.drafts.v1:alice'))).length<=20);
    drafts.configure('bob');assert.equal(drafts.get('chat_24'),null);drafts.save('new','Hello');drafts.purge();assert.equal(Object.keys(win.sessionStorage).filter(key=>key.startsWith('collective101.drafts')).length,0);
    win.sessionStorage.setItem('collective101.drafts.v1:alice',JSON.stringify({new:{text:'Expired',attachments:[],at:0}}));drafts.configure('alice');assert.equal(drafts.get('new'),null);
    Object.defineProperty(win,'sessionStorage',{get(){throw new Error('Storage denied fixture');}});drafts.configure('alice');drafts.save('new','Still editable');assert.equal(drafts.get('new').text,'Still editable');assert.equal(drafts.available(),false);
  }finally{dom.window.close();}
});

test('offline attachment recovery blocks sends until explicit retry without dropping the saved draft',async()=>{
  const original=await setup();let restored;try{
    original.doc.querySelector('.new-mission').click();original.doc.getElementById('mission-input').value='Offline draft';original.doc.getElementById('mission-input').dispatchEvent(new original.win.Event('input'));
    await original.win.CollectiveChatInputs.uploadFiles([new original.win.File(['A saved reference.'],'offline-restore.txt')]);
    const options={savedSession:sessionSnapshot(original.win),restoreOffline:true};restored=await setup(null,options);
    assert.equal(restored.doc.getElementById('mission-input').value,'Offline draft');assert.equal(restored.doc.getElementById('send-mission').disabled,true);assert.equal(restored.doc.getElementById('mission-input').readOnly,true);
    options.restoreOffline=false;restored.doc.getElementById('retry-draft-recovery').click();await waitFor(()=>restored.win.CollectiveChatInputs.ids().length===1&&!restored.doc.getElementById('send-mission').disabled);
    assert.equal(restored.doc.getElementById('mission-input').value,'Offline draft');assert.equal(restored.doc.getElementById('notice').classList.contains('d-none'),true);assert.deepEqual(restored.errors,[]);
  }finally{await original.close();if(restored)await restored.close();}
});

test('unavailable session storage keeps the application and in-memory draft editing usable',async()=>{
  const app=await setup(null,{sessionStorageBlocked:true});try{
    app.doc.querySelector('.new-mission').click();app.doc.getElementById('mission-input').value='Keep editing without storage';app.doc.getElementById('mission-input').dispatchEvent(new app.win.Event('input'));
    assert.equal(app.win.CollectiveDrafts.get('new').text,'Keep editing without storage');assert.equal(app.win.CollectiveDrafts.available(),false);assert.equal(app.doc.getElementById('send-mission').disabled,false);assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});

test('microphone waveform measures audio and local playback supports seeking deletion and send cleanup',async()=>{
  const app=await setup(null,{recording:true});try{
    app.doc.querySelector('.new-mission').click();app.doc.getElementById('voice-input').click();
    assert.equal(app.win.__recorders.length,0,'Permission is not requested before opting in');
    assert.equal(app.doc.getElementById('voice-transcribe').disabled,true);
    app.doc.getElementById('voice-start').click();await waitFor(()=>app.doc.getElementById('voice-recording').dataset.state==='recording');
    assert.equal(app.doc.getElementById('send-mission').disabled,true);
    app.win.__audioTime=100;app.win.__voiceTick();const bar=app.doc.querySelector('#voice-waveform>line');const quiet=bar.getAttribute('y1');
    app.win.__signal=40;app.win.__audioTime=200;app.win.__voiceTick();
    assert.ok([...app.doc.querySelectorAll('#voice-waveform>line:not(.voice-playhead)')].some(line=>Number(line.getAttribute('y1'))<Number(quiet)),'Amplitude changes with the sampled signal');
    app.win.__audioTime=4000;app.doc.getElementById('voice-record-stop').click();await waitFor(()=>!app.doc.getElementById('voice-review-controls').hidden);const firstClip=app.doc.getElementById('voice-audio').src;
    assert.equal(app.win.__track.stopped,true);await waitFor(()=>!app.win.CollectiveChatInputs.busy()).catch(error=>{throw new Error(error.message+' | '+app.doc.getElementById('chat-input-status').textContent+' | '+app.doc.getElementById('upload-queue').textContent);});assert.equal(app.doc.getElementById('send-mission').disabled,false);
    app.doc.getElementById('voice-replay').click();await waitFor(()=>app.doc.getElementById('voice-replay').getAttribute('aria-label')==='Pause playback');
    app.doc.getElementById('voice-seek').value='2';app.doc.getElementById('voice-seek').dispatchEvent(new app.win.Event('input'));
    assert.equal(app.doc.getElementById('voice-audio').currentTime,2);assert.ok(Number(app.doc.getElementById('voice-playhead').getAttribute('x1'))>100);
    app.doc.getElementById('voice-discard').click();assert.equal(app.doc.getElementById('voice-recording').hidden,true);assert.ok(app.win.__revoked.includes(firstClip));assert.equal(app.doc.activeElement.id,'voice-input');
    await waitFor(()=>app.win.CollectiveChatInputs.ids().length===0,3000);
    app.doc.getElementById('voice-input').click();await waitFor(()=>app.doc.getElementById('voice-recording').dataset.state==='recording');
    app.win.__audioTime=5000;app.doc.getElementById('voice-record-stop').click();await waitFor(()=>!app.doc.getElementById('voice-review-controls').hidden);const secondClip=app.doc.getElementById('voice-audio').src;await waitFor(()=>!app.win.CollectiveChatInputs.busy());
    app.doc.getElementById('mission-input').value='Hi';submit(app.win,app.doc.getElementById('mission-form'));
    await waitFor(async()=>{await app.poll();return app.doc.getElementById('chat-status').textContent==='answered';});
    assert.equal(app.doc.getElementById('voice-recording').hidden,true);assert.ok(app.win.__revoked.includes(secondClip));assert.equal(app.doc.querySelectorAll('#chat-messages .message.user audio').length,1);assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});

test('recording denial and cancellation during pending microphone permission never leave capture running',async()=>{
  for(const state of ['denied','pending']){
    const app=await setup(null,{recording:state});try{
      app.doc.querySelector('.new-mission').click();app.doc.getElementById('voice-input').click();app.doc.getElementById('voice-start').click();
      if(state==='pending'){
        app.doc.getElementById('voice-record-stop').click();app.win.__resolveMicrophone();await new Promise(resolve=>setTimeout(resolve,0));assert.equal(app.win.__track.stopped,true);
      }else await waitFor(()=>/denied/.test(app.doc.getElementById('chat-input-status').textContent));
      assert.equal(app.win.CollectiveChatInputs.busy(),false);assert.equal(app.doc.getElementById('voice-recording').hidden,true);assert.deepEqual(app.errors,[]);
    }finally{await app.close();}
  }
});

test('recordings stop on duration cap hidden tab and navigation without submitting messages',async()=>{
  const app=await setup(null,{recording:true,speech:true});try{
    app.doc.querySelector('.new-mission').click();app.doc.getElementById('voice-input').click();app.doc.getElementById('voice-start').click();
    await waitFor(()=>app.doc.getElementById('voice-recording').dataset.state==='recording');
    app.win.__holdUploads=true;app.win.__audioTime=120001;app.win.__voiceTick();
    await waitFor(()=>!app.win.CollectiveVoiceRecording.busy());
    assert.match(app.doc.getElementById('chat-input-status').textContent,/Two-minute/);assert.equal(app.win.__track.stopped,true);
    await waitFor(()=>!!app.win.__finishUpload);app.win.__holdUploads=false;await app.win.__finishUpload();await waitFor(()=>!app.win.CollectiveChatInputs.busy());
    app.doc.getElementById('voice-input').click();await waitFor(()=>app.doc.getElementById('voice-recording').dataset.state==='recording');
    Object.defineProperty(app.doc,'hidden',{value:true,configurable:true});app.doc.dispatchEvent(new app.win.Event('visibilitychange'));
    await waitFor(()=>!app.win.CollectiveChatInputs.busy());assert.equal(app.win.__recognitions.at(-1).onresult!=null,true);
    Object.defineProperty(app.doc,'hidden',{value:false});app.doc.getElementById('voice-replay').click();
    app.doc.querySelector('[data-nav="home"]').click();assert.equal(app.doc.getElementById('voice-audio').paused,true);
    app.doc.querySelector('.new-mission').click();assert.equal(app.doc.getElementById('voice-recording').hidden,true);assert.equal(app.doc.querySelectorAll('#chat-messages .message').length,0);assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});

test('recording size limits and device failures discard unusable audio and release capture',async()=>{
  const app=await setup(null,{recording:true});try{
    app.doc.querySelector('.new-mission').click();app.doc.getElementById('voice-input').click();app.doc.getElementById('voice-start').click();
    await waitFor(()=>app.doc.getElementById('voice-recording').dataset.state==='recording');
    app.win.__recorders.at(-1).ondataavailable({data:{size:8*1024*1024+1}});
    await waitFor(()=>!app.win.CollectiveChatInputs.busy());assert.match(app.doc.getElementById('chat-input-status').textContent,/too large/);assert.equal(app.win.__track.stopped,true);assert.equal(app.doc.getElementById('voice-recording').hidden,true);
    app.doc.getElementById('voice-input').click();await waitFor(()=>app.doc.getElementById('voice-recording').dataset.state==='recording');
    app.win.__recorders.at(-1).onerror();await waitFor(()=>!app.win.CollectiveChatInputs.busy());
    assert.match(app.doc.getElementById('chat-input-status').textContent,/recording failed/);assert.equal(app.doc.getElementById('voice-recording').hidden,true);assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});

test('voice input is consented, editable, cancellable and can read a new scripted reply',async()=>{
  const app=await setup(null,{speech:true});try{
    app.doc.querySelector('.new-mission').click();app.doc.getElementById('mission-input').value='My draft';
    app.doc.getElementById('voice-input').click();assert.equal(app.win.__recognitions.length,0,'Microphone service does not start before the disclosure action');
    assert.equal(app.doc.getElementById('voice-dialog').hasAttribute('open'),true);
    app.doc.getElementById('voice-start').click();const recognition=app.win.__recognitions[0];
    assert.equal(app.doc.getElementById('voice-input').getAttribute('aria-pressed'),'true');assert.equal(app.doc.getElementById('send-mission').disabled,true);
    const final=Object.assign([{transcript:'spoken words'}],{isFinal:true});
    recognition.onresult({resultIndex:0,results:[final]});recognition.onresult({resultIndex:0,results:[final]});
    assert.equal(app.doc.getElementById('mission-input').value,'My draft spoken words','Repeated recognition results cannot duplicate dictated text');
    app.doc.getElementById('voice-input').click();assert.equal(app.doc.getElementById('send-mission').disabled,false);
    app.doc.getElementById('voice-input').click();app.win.__recognitions.at(-1).onerror({error:'not-allowed'});
    assert.match(app.doc.getElementById('chat-input-status').textContent,/denied/);assert.equal(app.doc.getElementById('mission-input').value,'My draft spoken words');
    app.doc.getElementById('voice-playback').click();
    const pendingReply={id:'voice-lifecycle',status:'intake',attachments:[],transcript:[{role:'assistant',content:'A reply waiting for its saved status.'}]};
    app.win.CollectiveChatInputs.beginMessage();app.win.CollectiveChatInputs.onChat(pendingReply,'chat');
    assert.equal(app.win.speechSynthesis.spoken.length,0,'A reply is not read before its completed state');
    app.win.CollectiveChatInputs.onChat({...pendingReply,status:'answered'},'chat');
    assert.equal(app.win.speechSynthesis.spoken.length,1,'Saving the completed state reads an unchanged transcript exactly once');
    app.win.CollectiveChatInputs.onChat({...pendingReply,status:'answered'},'chat');assert.equal(app.win.speechSynthesis.spoken.length,1);
    app.doc.getElementById('stop-speaking').click();app.win.speechSynthesis.spoken=[];
    app.doc.getElementById('mission-input').value='Hi';submit(app.win,app.doc.getElementById('mission-form'));
    await waitFor(async()=>{await app.poll();return app.win.speechSynthesis.spoken.length>0;});
    assert.match(app.win.speechSynthesis.spoken.at(-1).text,/Hello from the scripted test provider/);
    assert.equal(app.doc.getElementById('stop-speaking').hidden,false);app.doc.getElementById('stop-speaking').click();assert.equal(app.doc.getElementById('stop-speaking').hidden,true);
    app.doc.querySelector('[data-nav="home"]').click();assert.equal(app.doc.getElementById('voice-input').getAttribute('aria-pressed'),'false');
    assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});

test('chat files and video references survive sending and workspace tabs remain keyboard accessible',async()=>{
  const app=await setup();try{
    app.doc.querySelector('.new-mission').click();assert.equal(app.doc.getElementById('voice-input').disabled,true);
    const video=new Uint8Array([0,0,0,24,102,116,121,112,109,112,52,50,0,0,0,0,0,0,0,0,0,0,0,0]);
    await app.win.CollectiveChatInputs.uploadFiles([new app.win.File(['Actual UI reference.'],'ui-reference.txt'),new app.win.File([video],'ui-video.mp4')]);
    assert.equal(app.doc.querySelectorAll('.attachment-chip').length,2);assert.match(app.doc.getElementById('composer-attachments').textContent,/Reference only/);
    assert.equal(app.win.CollectiveChatInputs.ids().length,2);
    app.doc.getElementById('mission-input').value='Hi';submit(app.win,app.doc.getElementById('mission-form'));
    await waitFor(async()=>{await app.poll();return app.doc.getElementById('chat-status').textContent==='answered';});
    assert.equal(app.doc.querySelectorAll('#chat-messages .message-attachments .reference-file').length,2);
    assert.equal(app.doc.getElementById('workspace-reference-count').textContent,'2');assert.equal(app.doc.querySelectorAll('.attachment-chip').length,0);
    const uploads=app.doc.getElementById('workspace-tab-references');uploads.click();uploads.focus();
    assert.equal(app.doc.getElementById('workspace-panel-references').hidden,false);
    uploads.dispatchEvent(new app.win.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));
    assert.equal(app.doc.activeElement.id,'workspace-tab-activity');assert.equal(app.doc.getElementById('workspace-panel-activity').hidden,false);
    app.doc.querySelector('.new-mission').click();assert.equal(app.doc.getElementById('workspace-tab-files').getAttribute('aria-selected'),'true');
    await app.win.CollectiveChatInputs.uploadFiles([new app.win.File(['<svg><script/></svg>'],'bad.svg')]);
    assert.match(app.doc.getElementById('chat-input-status').textContent,/Unsupported/);assert.equal(app.win.CollectiveChatInputs.ids().length,0);
    assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});

test('a protected signed-out workspace shows public Home and requests sign-in before private navigation',async()=>{
  const app=await setup(null,{accountState:{configured:true,user:null,shared_workspace:true}});try{
    assert.equal(app.doc.getElementById('view-home').classList.contains('d-none'),false);
    assert.equal(app.doc.querySelectorAll('#home-departments li').length,10);
    assert.equal(app.doc.querySelectorAll('#chat-messages .message').length,0);
    app.doc.querySelector('[data-nav="chat"]').click();
    assert.equal(app.doc.getElementById('account-dialog').hasAttribute('open'),true);
    assert.equal(app.doc.getElementById('view-chat').classList.contains('d-none'),true);
    app.doc.getElementById('account-tab-signup').click();assert.equal(app.doc.getElementById('signup-invite-row').hidden,false);
    app.doc.getElementById('close-account').click();assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});

test('account forms expose the real current identity and owner invitations without browser credential storage',async()=>{
  const dom=new JSDOM(html,{url:base,runScripts:'outside-only',pretendToBeVisual:true});const win=dom.window,doc=win.document;
  let current={configured:false,user:null,shared_workspace:true},signedIn=0,signedOut=0;
  try{
    win.HTMLElement.prototype.scrollIntoView=function(){};
    win.eval(await readFile(new URL('../collective101/web/accounts-ui.js',import.meta.url),'utf8'));
    const api=async(path,data)=>{
      if(path.endsWith('/me'))return current;
      if(path.endsWith('/signup')){assert.equal(data.password,'fixture-only-password-123');current={configured:true,user:{id:'fixture-user',name:data.name,username:data.username,role:'owner'},shared_workspace:true};return current;}
      if(path.endsWith('/profile')){current.user.name=data.name;return current;}
      if(path.endsWith('/invite'))return {code:'fixture-invitation-code',expires_in:86400};
      if(path.endsWith('/signout'))return {signed_out:true};
      throw new Error('Unexpected account fixture route '+path);
    };
    win.CollectiveAccounts.init({api,openSettings(){},signedIn(){signedIn++;},signedOut(){signedOut++;},expired(){}});await win.CollectiveAccounts.load();
    doc.querySelector('[data-account-open="signup"]').click();
    doc.getElementById('signup-name').value='Ada Lovelace';doc.getElementById('account-username').value='ada';doc.getElementById('account-password').value='fixture-only-password-123';
    submit(win,doc.getElementById('account-auth-form'));await waitFor(()=>signedIn===1);
    assert.equal(doc.getElementById('account-avatar').textContent,'AL');assert.match(doc.getElementById('account-identity').textContent,/@ada/);assert.equal(doc.getElementById('account-password').value,'');
    doc.getElementById('profile-name').value='<img src=x>';submit(win,doc.getElementById('profile-form'));await waitFor(()=>doc.getElementById('account-name').textContent==='<img src=x>');
    assert.equal(doc.querySelector('#account-menu img'),null);
    doc.getElementById('create-invite').click();await waitFor(()=>doc.getElementById('invite-code').textContent==='fixture-invitation-code');
    doc.querySelector('[data-account-signout]').click();await waitFor(()=>signedOut===1);
  }finally{win.close();}
});

test('top navigation preserves drafts and history, nests connectors in Settings and discloses connection loss',async()=>{
  const rows=[{id:'saved-fixture',title:'Saved conversation',status:'answered',created_at:'2026-11-05T01:00:00Z'}];
  const app=await setup(null,{chatRows:rows});try{
    const header=app.doc.querySelector('.app-header');
    assert.equal(app.doc.querySelector('.sidebar,#toggle-sidebar,#connection-status'),null);
    assert.equal(header.querySelector('[data-nav="connectors"]'),null);
    assert.equal(header.querySelectorAll('.primary-nav [data-nav]').length,5);
    assert.equal(app.doc.getElementById('connection-alert').hidden,true);
    app.doc.querySelector('[data-nav="chat"]').click();app.doc.getElementById('mission-input').value='Keep this draft.';
    openConnectors(app);
    assert.equal(app.win.location.pathname,'/settings');assert.equal(app.doc.getElementById('view-connectors').closest('#view-settings'),app.doc.getElementById('view-settings'));
    assert.equal(header.querySelector('[data-nav="settings"]').getAttribute('aria-current'),'page');
    app.doc.querySelector('#view-connectors .settings-back').click();
    assert.equal(app.win.location.pathname,'/settings');
    app.doc.querySelector('[data-nav="chat"]').click();assert.equal(app.doc.getElementById('mission-input').value,'Keep this draft.');
    const history=app.doc.getElementById('chat-history');history.open=true;
    const first=app.doc.querySelector('#recent-missions button');first.focus();await app.poll();
    assert.equal(app.doc.activeElement,first,'An unchanged history poll must retain the focused item');
    rows[0].title='Updated saved title';await app.poll();
    assert.equal(app.doc.activeElement.dataset.chatId,'saved-fixture','Changed history preserves focus by conversation identity');
    app.doc.activeElement.dispatchEvent(new app.win.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
    assert.equal(history.open,false);assert.equal(app.doc.activeElement,history.querySelector('summary'));
    history.open=true;app.doc.querySelector('[data-nav="overview"]').click();assert.equal(history.open,false);
    const originalFetch=app.win.fetch;
    app.win.fetch=(url,options)=>String(url)==='/api/chats'?Promise.reject(new Error('Offline fixture')):originalFetch(url,options);
    await app.poll();assert.equal(app.doc.getElementById('connection-alert').hidden,false);
    app.win.fetch=originalFetch;await app.poll();assert.equal(app.doc.getElementById('connection-alert').hidden,true);
    assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});

test('home explains the real organization and the single-card dashboard opens a draft without model requests',async()=>{
  const rows=[{id:'saved-fixture',title:'<img src=x onerror=alert(1)>',status:'answered',created_at:'2026-11-05T01:00:00Z'}];
  const app=await setup(null,{chatRows:rows});try{
    assert.equal(app.win.location.pathname,'/');assert.equal(app.doc.getElementById('view-home').classList.contains('d-none'),false);
    assert.equal(app.doc.querySelectorAll('#home-departments li').length,10);
    assert.equal(app.doc.querySelectorAll('.constellation-employee').length,90);
    assert.equal(app.doc.querySelectorAll('.constellation-head').length,10);
    assert.equal(app.doc.querySelectorAll('.constellation-cluster').length,10);
    assert.equal(app.doc.querySelector('#view-home #organization-map')?.tagName,'BUTTON');
    assert.match(app.doc.querySelector('.brand').getAttribute('aria-label'),/101/);
    assert.equal(app.doc.querySelectorAll('.brand-101 i').length,3);
    assert.equal(app.doc.querySelector('.workspace-preview,.settings-aside'),null);
    assert.equal(app.doc.querySelectorAll('#recent-missions img').length,0);assert.match(app.doc.getElementById('recent-missions').textContent,/<img/);
    const firstCluster=app.doc.querySelector('.constellation-cluster');await app.poll();assert.equal(app.doc.querySelector('.constellation-cluster'),firstCluster,'Polling does not replay the home animation');
    let posted=false;const original=app.win.fetch;app.win.fetch=(url,opts)=>{if(opts?.method==='POST')posted=true;return original(url,opts);};
    app.doc.getElementById('home-enter').click();assert.equal(app.win.location.pathname,'/dashboard');
    assert.equal(app.doc.querySelectorAll('#view-overview .dashboard-launch-card').length,1);
    assert.equal(app.doc.querySelector('#view-overview .dashboard-metrics,#view-overview .dashboard-bottom,#view-overview #organization-map'),null);
    const draft='Create a useful research brief for my team.';app.doc.getElementById('dashboard-input').value=draft;
    app.doc.querySelector('[data-nav="home"]').click();app.win.history.back();
    await waitFor(()=>app.win.location.pathname==='/dashboard'&&!app.doc.getElementById('view-overview').classList.contains('d-none'));
    assert.equal(app.doc.getElementById('dashboard-input').value,draft,'Returning to the dashboard keeps the draft');
    submit(app.win,app.doc.getElementById('dashboard-mission'));
    assert.equal(app.win.location.pathname,'/chat');assert.equal(app.doc.getElementById('mission-input').value,draft);assert.equal(posted,false);
    assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
  const direct=await setup(null,{path:'/dashboard'});try{assert.equal(direct.doc.getElementById('view-overview').classList.contains('d-none'),false);assert.equal(direct.doc.getElementById('view-home').classList.contains('d-none'),true);}finally{await direct.close();}
});

test('Settings applies every language and preserves validated preferences with English default and reset',async()=>{
  const app=await setup();try{
    assert.equal(app.doc.documentElement.lang,'en');assert.equal(app.doc.documentElement.dataset.theme,'dark');
    app.doc.querySelector('[data-nav="settings"]').click();
    const language=app.doc.getElementById('setting-language');assert.equal(language.options.length,14);assert.equal(language.options[0].value,'en');
    const draft=app.doc.getElementById('mission-input');draft.value='Keep my draft.';
    for(const option of [...language.options]){language.value=option.value;language.dispatchEvent(new app.win.Event('change'));assert.equal(app.doc.documentElement.lang,option.value);assert.equal(app.doc.documentElement.dir,option.value==='ar'?'rtl':'ltr');assert.equal(app.doc.getElementById('breadcrumb').textContent,app.win.CollectivePreferences.t('Settings'));assert.equal(draft.value,'Keep my draft.');assert.equal(app.doc.querySelector('[data-nav="home"]').textContent.trim(),app.win.CollectivePreferences.t('Home'));}
    app.doc.querySelector('[name="theme"][value="light"]').click();
    app.doc.getElementById('setting-reduce-motion').click();
    const prefs=app.win.CollectivePreferences.get();const reloaded=await setup(null,{savedPreferences:prefs});try{assert.equal(reloaded.doc.documentElement.dataset.theme,'light');assert.equal(reloaded.doc.documentElement.dataset.reduceMotion,'true');assert.equal(reloaded.doc.documentElement.lang,'ms');}finally{await reloaded.close();}
    app.doc.getElementById('reset-preferences').click();assert.equal(app.doc.documentElement.lang,'en');assert.equal(app.doc.documentElement.dir,'ltr');assert.equal(app.doc.documentElement.dataset.theme,'dark');
    assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});

test('mission studio uses recorded evidence, keeps partial files inert and preserves keyboard focus',async()=>{
  const app=await setup();try{
    const files=[{path:'engineering/index.html',content:'<title><img src=x onerror=alert(1)></title>\n<script>alert(1)</script>',language:'HTML',lines:2,sha256:'first',agent_id:'engineering-003'},
      {path:'research/notes.md',content:'# Actual saved notes\n\n<script>alert(1)</script>\n![remote](https://example.com/track)',language:'Markdown',lines:4,sha256:'second',agent_id:'research-002'}];
    const chat={id:'synthetic',title:'A blocked draft',run_id:'root',effective_run_id:'revision',status:'blocked',brief:{objective:'A useful outcome'},run:{result:{selected_departments:['engineering']}},workspace:{files,preview:{ready:true},events:[{id:'root:review:1',phase:'review',status:'accepted',agent_id:'assurance-001'},{id:'revision:work:1',phase:'work',status:'accepted',agent_id:'engineering-003'}]}};
    const roster={departments:[{id:'engineering',name:'Engineering'},{id:'assurance',name:'Verification'}]};
    const calls=[];const handlers={showSource:file=>calls.push(['source',file.path]),openPreview:path=>calls.push(['preview',path]),downloadFile:file=>calls.push(['download',file.path]),viewEvidence:()=>{},previewAvailable:true};
    app.win.CollectiveMissionUI.render(chat,roster,handlers);
    const journey=app.doc.getElementById('mission-journey'),results=app.doc.getElementById('mission-results');
    assert.equal(journey.hidden,false);assert.match(journey.querySelector('.journey-step:last-child').textContent,/Blocked/);
    assert.match(journey.querySelectorAll('.journey-step')[2].textContent,/Not recorded/,'An earlier revision review cannot mark the active revision reviewed');
    assert.equal(journey.querySelectorAll('.department-badge').length,1);assert.match(journey.querySelector('.department-badge').textContent,/Engineering/);
    assert.equal(results.querySelectorAll('.deliverable-card').length,2);assert.equal(results.querySelector('script,iframe,img'),null);
    assert.match(results.textContent,/<img/);assert.doesNotMatch(results.querySelector('.results-heading').textContent,/Current mission reviewed/);
    [...results.querySelectorAll('button')].find(button=>button.textContent==='Open website').click();
    results.querySelector('.deliverable-download').click();assert.deepEqual(calls,[['preview','engineering/index.html'],['download','engineering/index.html']]);
    const original=results.querySelector('.deliverable-card');app.win.CollectiveMissionUI.render(chat,roster,handlers);assert.equal(results.querySelector('.deliverable-card'),original);
    const details=results.querySelector('.all-deliverables');details.open=true;const focused=details.querySelector('.file-text-link');focused.focus();
    chat.status='reviewed';app.win.CollectiveMissionUI.render(chat,roster,handlers);
    assert.equal(results.querySelector('.all-deliverables').open,true);assert.equal(app.doc.activeElement.dataset.filePath,files[0].path);assert.equal(app.doc.activeElement.dataset.fileAction,'list-source');
    assert.match(results.querySelector('.results-heading').textContent,/Current mission reviewed/);
    app.win.CollectiveMissionUI.render(null,roster,handlers);assert.equal(journey.hidden,true);assert.equal(results.hidden,true);
    app.win.CollectiveMissionUI.render(chat,roster,handlers);assert.ok(journey.querySelector('summary'));
    assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});

test('blocked storage and invalid preferences do not block the workspace',async()=>{
  for(const opts of [{storageBlocked:true},{savedPreferences:{theme:'bad',language:'invalid',textSize:'gigantic',reduceMotion:'true'}}]){
    const app=await setup(null,opts);try{
      assert.equal(app.doc.documentElement.lang,'en');assert.equal(app.doc.documentElement.dataset.theme,'dark');
      app.doc.querySelector('[name="theme"][value="light"]').click();assert.equal(app.doc.documentElement.dataset.theme,'light');
      if(opts.storageBlocked)assert.match(app.doc.getElementById('preferences-status').textContent,/this visit only/);
      assert.deepEqual(app.errors,[]);
    }finally{await app.close();}
  }
});

test('ambient motion stays continuous without pause controls and respects reduced-motion preferences',async()=>{
  const app=await setup(null,{ambientPaused:true});try{
    assert.equal(app.doc.documentElement.dataset.ambientMotion,'running');
    assert.equal(app.doc.querySelectorAll('.ambient-orbit').length,3);
    assert.equal(app.doc.querySelector('[data-motion-toggle]'),null);
    assert.equal(app.doc.querySelector('.cluster-atmosphere text'),null,'Floating decorative dots cannot move department labels');
    app.doc.getElementById('setting-reduce-motion').click();assert.equal(app.doc.documentElement.dataset.ambientMotion,'reduced');
    assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
  for(const options of [{systemReducedMotion:true},{storageBlocked:true}]){
    const instance=await setup(null,options);try{
      if(options.systemReducedMotion)assert.equal(instance.doc.documentElement.dataset.ambientMotion,'reduced');
      else assert.equal(instance.doc.documentElement.dataset.ambientMotion,'running');
      assert.deepEqual(instance.errors,[]);
    }finally{await instance.close();}
  }
});

test('assistant Markdown has paragraphs, lists, safe links and inert code',async()=>{
  const app=await setup();try{
    app.doc.querySelector('[data-nav="chat"]').click();
    app.doc.getElementById('mission-input').value='formatting-check';submit(app.win,app.doc.getElementById('mission-form'));
    await waitFor(async()=>{await app.poll();return app.doc.getElementById('chat-status').textContent==='answered';});
    const body=app.doc.querySelector('.message.assistant .markdown-body');
    assert.ok(body);assert.equal(body.querySelectorAll('ol > li').length,2);
    assert.equal(body.querySelector('strong').textContent,'two cafes');
    assert.ok(body.querySelectorAll('p').length>=2);
    assert.match(body.querySelector('pre code').textContent,/<script>/);
    assert.equal(body.querySelector('script,img,iframe,style'),null);
    assert.equal(body.querySelector('a[href^="javascript:"]'),null);
    assert.equal(body.querySelector('a').target,'_blank');assert.match(body.querySelector('a').rel,/noopener/);
    assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});

test('Markdown file opens in Preview with an exact Source tab and no fingerprint details',async()=>{
  const app=await setup();try{
    const source='# Cafe notes\n\n**Reviewed** source.\n\n| Cafe | Area |\n| --- | --- |\n| One | KL |\n\n<script>alert(1)</script>\n\n![remote](https://example.com/track.png)';
    app.win.__testShowSource({path:'research/notes.md',content:source,sha256:'a'.repeat(64)});
    assert.equal(app.doc.getElementById('file-preview-tab').getAttribute('aria-selected'),'true');
    const preview=app.doc.getElementById('file-preview');
    assert.equal(preview.querySelector('h1').textContent,'Cafe notes');assert.ok(preview.querySelector('table'));
    assert.equal(preview.querySelector('script,img,iframe,style'),null);
    assert.equal(app.doc.querySelector('#file-fingerprint'),null);
    assert.equal(app.doc.getElementById('file-viewer').textContent.includes('File details'),false);
    app.doc.getElementById('file-source-tab').click();
    assert.equal(app.doc.getElementById('file-source').hidden,false);
    assert.equal(app.doc.getElementById('file-source').textContent,source);
    assert.equal(preview.hidden,true);
    app.win.__testShowSource({path:'engineering/index.html',content:'<script>doNotExecute()</script>'});
    assert.equal(app.doc.getElementById('file-tabs').hidden,true);
    assert.equal(app.doc.getElementById('file-source').hidden,false);
    assert.equal(app.doc.querySelector('#file-source script'),null);
  }finally{await app.close();}
});

test('aggregate spending controls are absent while request and recovery information remains',async()=>{
  const app=await setup();try{
    for(const id of ['budget-calls','budget-tokens','evaluation-calls'])assert.equal(app.doc.getElementById(id),null);
    assert.match(app.doc.getElementById('chat-limits-info').textContent,/Retries|requests maximum|Output/i);
    assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});

test('old server requires restart and cannot receive new chat requests through the updated UI',async()=>{
  const app=await setup({version:'0.5-reviewed-work',features:{}});try{
    let sent=false;const original=app.win.fetch;
    app.win.fetch=(url,options)=>{if(options?.method==='POST')sent=true;return original(url,options);};
    assert.equal(app.doc.getElementById('send-mission').disabled,true);
    assert.match(app.doc.getElementById('notice').textContent,/Restart/);
    app.doc.getElementById('mission-input').value='Build a grocery landing page';submit(app.win,app.doc.getElementById('mission-form'));
    await waitFor(()=>app.doc.getElementById('notice').textContent.includes('before sending'));
    assert.equal(sent,false);
  }finally{await app.close();}
});

test('model source is visible in chat and connectors when only environment config exists',async()=>{
  const app=await setup({live_configured:true,model_configuration:{configured:true,enabled:true,credential_source:'environment',settings_source:'environment_defaults',model:'muse-spark-1.3',endpoint_host:'api.meta.ai',request_policy:{max_output_tokens:32768,timeout_seconds:120}}});
  try{
    assert.match(app.doc.getElementById('mode-description').textContent,/environment/i);
    openConnectors(app);
    await waitFor(()=>app.doc.getElementById('model-configuration')?.textContent.includes('muse-spark-1.3'));
    assert.match(app.doc.getElementById('model-configuration').textContent,/environment/i);
    assert.match(app.doc.getElementById('model-configuration').textContent,/api.meta.ai/);
    assert.match(app.doc.getElementById('model-configuration').textContent,/32,768|32768/);
    assert.match(app.doc.getElementById('model-configuration').textContent,/not.*verif|not.*test/i);
  }finally{await app.close();}
});

test('model request settings save without storing an environment credential',async()=>{
  const app=await setup();try{
    openConnectors(app);
    await waitFor(()=>!app.doc.getElementById('connector-list').textContent.includes('Loading connections'));
    app.doc.querySelector('[data-connector="meta"] button').click();
    app.doc.getElementById('connector-max-output').value='20000';
    app.doc.getElementById('connector-timeout').value='150';
    submit(app.win,app.doc.getElementById('connector-form'));
    await waitFor(()=>app.doc.getElementById('connector-setup').classList.contains('d-none'));
    await waitFor(()=>app.doc.getElementById('model-configuration').textContent.includes('20,000'));
    assert.equal(app.doc.getElementById('connector-secret').value,'');
    assert.match(app.doc.getElementById('model-configuration').textContent,/150 seconds/);
    assert.match(app.doc.getElementById('model-configuration').textContent,/No credential detected/);
    app.doc.querySelector('[data-connector="meta"] button').click();
    assert.equal(app.doc.getElementById('connector-max-output').value,'20000');
    assert.equal(app.doc.getElementById('connector-timeout').value,'150');
    assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});

test('directory exposes departments, roles, reporting lines and per-agent activity',async()=>{
  const app=await setup();try{
    app.doc.querySelector('[data-nav="organization"]').click();
    assert.equal(app.doc.getElementById('view-organization').classList.contains('d-none'),false);
    const search=app.doc.getElementById('agent-search');search.value='operations';search.dispatchEvent(new app.win.Event('input'));
    assert.equal(app.doc.querySelectorAll('#search-results .agent-row').length,8);
    app.doc.querySelector('#search-results button').click();
    assert.match(app.doc.getElementById('agent-inspector').textContent,/Works with Mission Director/);
    assert.equal(app.doc.querySelectorAll('#activity-agent option').length,102);
    assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});

test('organization explorer preserves real reporting roles, directory access and drawer keyboard return',async()=>{
  const app=await setup();try{
    app.doc.querySelector('[data-nav="organization"]').click();
    assert.equal(app.doc.querySelectorAll('.organization-node').length,10);
    app.doc.querySelector('.organization-node[data-department="research"]').click();
    assert.equal(app.doc.getElementById('organization-details').dataset.department,'research');
    assert.equal(app.doc.querySelectorAll('.explorer-employee').length,9);
    const head=app.doc.querySelector('.explorer-head');head.focus();head.click();
    assert.match(app.doc.getElementById('agent-inspector').textContent,/Works with Mission Director/);
    app.doc.dispatchEvent(new app.win.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
    assert.equal(app.doc.getElementById('agent-inspector').classList.contains('d-none'),true);assert.equal(app.doc.activeElement,head);
    app.doc.querySelector('[data-organization-mode="directory"]').click();assert.equal(app.doc.getElementById('department-grid').classList.contains('d-none'),false);
    app.doc.querySelector('.department-card[data-department="operations"]').click();assert.equal(app.doc.getElementById('organization-details').dataset.department,'operations');
    assert.equal(app.doc.getElementById('organization-explorer').hidden,false);assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});

test('saved-page thumbnail UI uses the capture result and discloses failures without replacing source',async()=>{
  const app=await setup();try{
    app.doc.querySelector('[data-nav="chat"]').click();
    const sample=app.doc.createElement('div');sample.className='deliverable-sample';sample.textContent='Actual saved source';
    const grid=app.doc.createElement('div');grid.className='deliverable-grid';grid.append(sample);app.doc.getElementById('mission-results').append(grid);
    const calls=[];app.win.CollectiveThumbnails.configure(async(cid,entry)=>{calls.push([cid,entry]);return {image:'data:image/png;base64,iVBORw0KGgo=',width:960,height:600};});
    const observed=[];app.win.IntersectionObserver=class {observe(node){observed.push(node);}unobserve(){}};
    const file={path:'engineering/index.html',sha256:'first'},chat={id:'test-capture',status:'running',workspace:{files:[file]}};
    app.win.CollectiveThumbnails.attach(sample,file,chat);sample.querySelector('button').click();
    assert.equal(observed.length,0,'Mutable working drafts must not race automatic thumbnail captures');
    await waitFor(()=>sample.querySelector('img'));assert.deepEqual(calls,[['test-capture','engineering/index.html']]);
    assert.equal(sample.querySelector('img').alt,'Static preview of engineering/index.html');assert.match(sample.textContent,/Static page preview/);
    const stable=app.doc.createElement('div');grid.append(stable);chat.status='reviewed';app.win.CollectiveThumbnails.attach(stable,file,chat);assert.equal(observed.length,1,'Stable saved outcomes can load a visible thumbnail');
    const failure=app.doc.createElement('div');failure.textContent='Original source stays';grid.append(failure);
    app.win.CollectiveThumbnails.configure(async()=>{throw new Error('unavailable');});
    app.win.CollectiveThumbnails.attach(failure,{path:'engineering/other.html',sha256:'other'},chat);failure.querySelector('button').click();
    await waitFor(()=>failure.textContent.includes('Thumbnail unavailable'));assert.match(failure.textContent,/Original source stays/);assert.equal(failure.querySelector('img'),null);
    assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});

test('Effectiveness stays out of navigation and product pages without requesting evaluation data',async()=>{
  const app=await setup();try{
    assert.equal(app.doc.querySelector('[data-nav="evaluations"]'),null);
    assert.equal(app.doc.getElementById('view-evaluations'),null);
    assert.equal(app.doc.getElementById('evaluation-form'),null);
    assert.equal(app.doc.getElementById('evaluation-trials'),null);
    assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});

test('short mission asks questions and answers continue to a recorded result',async()=>{
  const app=await setup();try{
    app.doc.querySelector('.new-mission').click();
    app.doc.getElementById('mission-input').value='Build a website';submit(app.win,app.doc.getElementById('mission-form'));
    await waitFor(async()=>{await app.poll();return app.doc.querySelectorAll('.intervention textarea').length===2;});
    const fields=app.doc.querySelectorAll('.intervention textarea');
    fields[0].value='For a local coffee shop serving residents who need to browse the menu and find the location.';
    fields[1].value='An accessible responsive page with opening hours, clear headings and operations documentation.';
    app.doc.querySelector('[name="theme"][value="light"]').click();
    assert.equal(app.doc.querySelector('.intervention textarea'),fields[0]);
    assert.match(fields[0].value,/local coffee shop/);
    submit(app.win,app.doc.querySelector('form.intervention'));
    await waitFor(async()=>{await app.poll();return app.doc.getElementById('chat-status').textContent==='reviewed';});
    assert.match(app.doc.getElementById('brief-content').textContent,/SUCCESS CRITERIA/);
    assert.equal(app.doc.getElementById('preview-project').disabled,false);
    assert.ok(app.doc.querySelector('[aria-label="Preview engineering/index.html in a new tab"]'));
    app.win.open=()=>null;
    app.doc.getElementById('preview-project').click();
    await waitFor(()=>!app.doc.getElementById('preview-link').classList.contains('d-none'));
    const link=app.doc.getElementById('preview-link');
    assert.equal(link.target,'_blank');assert.match(link.rel,/noopener/);
    assert.notEqual(new URL(link.href).port,new URL(base).port);
    const response=await fetch(link.href);assert.equal(response.status,200);
    assert.match(await response.text(),/Auto-refresh/);
    app.doc.getElementById('view-evidence').click();
    await waitFor(()=>app.doc.querySelectorAll('#activity-content details').length>0);
    assert.match(app.doc.getElementById('activity-mode').textContent,/Live Meta/);
    assert.ok(app.doc.querySelector('.timeline-entry'));
    app.doc.getElementById('activity-mission').value='';app.doc.getElementById('activity-mission').dispatchEvent(new app.win.Event('change'));
    assert.match(app.doc.getElementById('activity-content').textContent,/Choose a mission/);assert.equal(app.doc.querySelector('#activity-content .timeline-entry'),null);
    assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});

test('missing HTML keeps Preview disabled with actionable explanation',async()=>{
  const app=await setup();try{
    app.doc.querySelector('.new-mission').click();
    assert.equal(app.doc.getElementById('preview-project').disabled,true);
    assert.match(app.doc.getElementById('preview-status').textContent,/No HTML/);
    assert.ok(app.doc.getElementById('preview-link').classList.contains('d-none'));
    assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});

test('preview auto-refresh follows saved revisions, manual mode preserves view and missing page is explained',async()=>{
  const page=await readFile(new URL('../collective101/web/preview/index.html',import.meta.url),'utf8');
  const code=await readFile(new URL('../collective101/web/preview/preview.js',import.meta.url),'utf8');
  const errors=[];const console=new VirtualConsole();console.on('jsdomError',e=>errors.push(e.message));
  const dom=new JSDOM(page,{url:'http://127.0.0.1:12345/p/test/',runScripts:'outside-only',virtualConsole:console,pretendToBeVisual:true});
  const win=dom.window,doc=win.document;let poll;
  let meta={ready:true,entries:['engineering/index.html'],revision:'first',title:'Coffee shop',status:'running'};
  win.fetch=async()=>({ok:true,json:async()=>meta});win.setInterval=fn=>{poll=fn;};win.eval(code);
  try{
    await waitFor(()=>doc.getElementById('site').src.includes('revision=first'));
    const first=doc.getElementById('site').src;
    assert.equal(doc.getElementById('site').getAttribute('sandbox'),'allow-scripts');
    meta={...meta,revision:'second'};poll();
    await waitFor(()=>doc.getElementById('site').src.includes('revision=second'));
    assert.notEqual(doc.getElementById('site').src,first);
    doc.getElementById('auto').checked=false;meta={...meta,revision:'third'};poll();
    await waitFor(()=>doc.getElementById('state').textContent.includes('Updates available'));
    assert.match(doc.getElementById('site').src,/revision=second/);
    doc.getElementById('refresh').click();await waitFor(()=>doc.getElementById('site').src.includes('revision=third'));
    meta={...meta,ready:false,entries:[],reason:'No HTML page has been saved yet.'};poll();
    await waitFor(()=>doc.getElementById('site').hidden);
    assert.match(doc.getElementById('empty').textContent,/No HTML/);
    assert.deepEqual(errors,[]);
  }finally{win.close();}
});
test('JavaScript mission displays real sandbox evidence and escapes user markup',async()=>{
  const app=await setup();try{
    app.doc.querySelector('.new-mission').click();
    [...app.doc.querySelectorAll('.welcome-pills button')].find(button=>button.textContent==='Test JavaScript').click();
    app.doc.getElementById('mission-input').value+=' <img src=x onerror=alert(1)>';
    submit(app.win,app.doc.getElementById('mission-form'));
    await waitFor(async()=>{await app.poll();return app.doc.getElementById('chat-status').textContent==='reviewed';});
    assert.equal(app.doc.querySelector('#chat-messages img'),null);
    assert.match(app.doc.getElementById('chat-messages').textContent,/<img/);
    app.doc.getElementById('view-evidence').click();
    const filter=app.doc.getElementById('activity-filter');filter.value='executions';filter.dispatchEvent(new app.win.Event('change'));
    await waitFor(()=>app.doc.getElementById('activity-content').textContent.includes('QuickJS/WebAssembly'));
    assert.match(app.doc.getElementById('activity-content').textContent,/passed/);
    assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});


test('greeting uses injected live-provider response and agent inspector shows scoped tools',async()=>{
  const app=await setup();try{
    app.doc.querySelector('.new-mission').click();
    app.doc.getElementById('mission-input').value='Hi!';submit(app.win,app.doc.getElementById('mission-form'));
    await waitFor(async()=>{await app.poll();return app.doc.getElementById('chat-status').textContent==='answered';});
    assert.match(app.doc.getElementById('brief-content').textContent,/1 total provider requests/);
    assert.equal(app.doc.getElementById('mission-controls').classList.contains('d-none'),true);
    app.doc.querySelector('[data-nav="organization"]').click();
    const search=app.doc.getElementById('agent-search');search.value='research-003';search.dispatchEvent(new app.win.Event('input'));
    app.doc.querySelector('#search-results button').click();
    assert.match(app.doc.getElementById('agent-inspector').textContent,/connected capabilities available when assigned/);
    assert.match(app.doc.getElementById('agent-inspector').textContent,/Use organization chat for coordinated work and saved deliverables/);
    assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});


test('connector catalog previews services, filters, and opens accessible setup without department choices',async()=>{
  const app=await setup();try{
    openConnectors(app);
    await waitFor(()=>app.doc.querySelectorAll('.connector-card').length===9&&!app.doc.getElementById('connector-list').textContent.includes('Loading connections'));
    assert.equal(app.doc.getElementById('connector-departments'),null);
    assert.equal(app.doc.querySelector('#view-connectors select'),null);
    for(const id of ['gmail','slack','canva','github','drive','calendar']){
      const card=app.doc.querySelector(`[data-connector="${id}"]`);
      assert.ok(card.textContent.includes('Coming soon'));assert.equal(card.querySelector('button'),null);
    }
    const search=app.doc.getElementById('connector-search');search.value='github';search.dispatchEvent(new app.win.Event('input'));
    assert.equal(app.doc.querySelectorAll('.connector-card').length,1);
    search.value='missing-service';search.dispatchEvent(new app.win.Event('input'));
    assert.equal(app.doc.getElementById('connector-empty').classList.contains('d-none'),false);
    search.value='';search.dispatchEvent(new app.win.Event('input'));
    app.doc.querySelector('[data-connector-filter="available"]').click();assert.equal(app.doc.querySelectorAll('.connector-card').length,3);
    app.doc.querySelector('[data-connector="mcp"] button').click();
    assert.equal(app.doc.activeElement.id,'connector-name');assert.equal(app.doc.getElementById('connector-kind').value,'mcp');
    app.doc.getElementById('connector-setup').dispatchEvent(new app.win.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
    assert.equal(app.doc.getElementById('connector-setup').classList.contains('d-none'),true);
    assert.equal(app.doc.activeElement.getAttribute('aria-label'),'Set up Custom MCP');assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});

test('card setup saves encrypted search credentials and enables all 101 agents without selection',async()=>{
  const app=await setup();try{
    openConnectors(app);
    await waitFor(()=>app.doc.querySelector('[data-connector="brave"] button'));
    app.doc.querySelector('[data-connector="brave"] button').click();
    app.doc.getElementById('connector-name').value='UI test search';
    app.doc.getElementById('connector-secret').value='ui-test-placeholder-not-a-key';
    submit(app.win,app.doc.getElementById('connector-form'));
    await waitFor(()=>app.doc.querySelector('#connector-list .state-pill')?.textContent==='enabled');
    assert.equal(app.doc.getElementById('connector-secret').value,'');
    assert.equal(app.doc.getElementById('connector-list').textContent.includes('ui-test-placeholder-not-a-key'),false);
    assert.ok(app.doc.getElementById('connector-list').textContent.includes('all 101 agents'));
    const session=await (await fetch(base+'/api/session')).json();
    const headers={'X-Console-Token':session.token};
    const connectors=await (await fetch(base+'/api/connectors',{headers})).json();
    assert.equal(connectors[0].departments.length,10);assert.equal(JSON.stringify(connectors).includes('ui-test-placeholder-not-a-key'),false);
    const roster=await (await fetch(base+'/api/organization',{headers})).json();
    assert.equal(roster.agents.length,101);
    for(const agent of roster.agents)assert.ok(agent.tools.some(t=>t.name==='web_search'&&t.available));
    [...app.doc.querySelectorAll('#connector-list button')].find(b=>b.textContent==='Disconnect').click();
    await waitFor(()=>app.doc.querySelector('#connector-list .state-pill')?.textContent==='disabled');
    assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});


test('chat composer grows without manual resizing and runtime status stays outside messages',async()=>{
  const app=await setup();try{
    app.doc.querySelector('[data-nav="chat"]').click();
    assert.equal(app.doc.querySelector('#view-chat .chat-side'),null);
    assert.equal(app.doc.querySelector('#mission-details'),null);
    assert.equal(app.doc.querySelector('#view-chat .chat-toolbar'),null);
    assert.equal(app.doc.querySelector('#chat-inspector').open,false);
    const input=app.doc.getElementById('mission-input');
    Object.defineProperty(input,'scrollHeight',{configurable:true,get:()=>input.value.length>50?280:48});
    input.value='x'.repeat(100);input.dispatchEvent(new app.win.Event('input'));assert.equal(input.style.height,'200px');assert.equal(input.style.overflowY,'auto');
    input.value='progress-check';input.dispatchEvent(new app.win.Event('input'));assert.equal(input.style.height,'48px');
    submit(app.win,app.doc.getElementById('mission-form'));
    await waitFor(()=>!app.doc.getElementById('chat-progress').classList.contains('d-none'));
    assert.match(app.doc.getElementById('chat-progress-label').textContent,/Head of Distribution/);
    assert.equal(app.doc.querySelector('#chat-messages [role="status"]'),null);
    assert.equal(app.doc.getElementById('chat-messages').textContent.includes('considering your request'),false);
    assert.equal(app.doc.getElementById('mission-form').classList.contains('d-none'),false);
    assert.equal(app.doc.getElementById('send-mission').disabled,true);
    const bubble=app.doc.querySelector('#chat-messages .message');const originalFetch=app.win.fetch;
    app.win.fetch=async(url,options)=>{const response=await originalFetch(url,options);if(String(url).startsWith('/api/chats/')){const value=await response.json();if(value.status==='intake')value.progress={label:'Recorded test action',phase:'intake'};return {ok:response.ok,json:async()=>value};}return response;};
    await app.poll();assert.equal(app.doc.querySelector('#chat-messages .message'),bubble);app.win.fetch=originalFetch;
    await waitFor(async()=>{await app.poll();return app.doc.getElementById('chat-status').textContent==='answered';});
    assert.equal(app.doc.getElementById('chat-progress').classList.contains('d-none'),true);
    assert.equal(app.doc.getElementById('send-mission').disabled,false);assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});

test('direct agent chat preserves identity, role boundary and can hand off to organization',async()=>{
  const app=await setup();try{
    app.doc.querySelector('[data-nav="organization"]').click();
    const search=app.doc.getElementById('agent-search');search.value='Recovery Planner';search.dispatchEvent(new app.win.Event('input'));
    app.doc.querySelector('#search-results button').click();
    const panel=app.doc.getElementById('agent-inspector');assert.equal(panel.querySelector('pre'),null);
    [...panel.querySelectorAll('button')].find(b=>b.textContent.startsWith('Chat with')).click();
    assert.equal(app.doc.getElementById('agent-chat-context').hidden,false);
    assert.match(app.doc.getElementById('agent-chat-name').textContent,/Recovery Planner/);
    app.doc.getElementById('mission-input').value='Build me a website';submit(app.win,app.doc.getElementById('mission-form'));
    await waitFor(async()=>{await app.poll();return app.doc.getElementById('chat-status').textContent==='answered';});
    assert.match(app.doc.querySelector('.message.assistant .message-label').textContent,/Recovery Planner/);
    assert.match(app.doc.querySelector('.message.assistant .markdown-body').textContent,/Engineering/);
    app.doc.getElementById('organization-chat').click();assert.equal(app.doc.getElementById('agent-chat-context').hidden,true);
    assert.equal(app.doc.getElementById('mission-input').value,'Build me a website');assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});


test('voice-only Send attaches normalized audio and receives recorded backend interpretation without typed transcript',async()=>{
  const app=await setup(null,{recording:true});try{
    app.doc.querySelector('.new-mission').click();app.doc.getElementById('voice-input').click();app.doc.getElementById('voice-start').click();
    await waitFor(()=>app.doc.getElementById('voice-recording').dataset.state==='recording');
    app.win.__audioTime=1200;app.doc.getElementById('voice-record-stop').click();
    await waitFor(()=>!app.win.CollectiveChatInputs.busy()&&app.win.CollectiveChatInputs.ids().length===1);
    assert.equal(app.doc.getElementById('mission-input').value,'');assert.equal(app.doc.getElementById('mission-input').required,false);
    let sent,id;const original=app.win.fetch;
    app.win.fetch=async(url,options)=>{const response=await original(url,options);if(String(url)==='/api/chats'&&options?.method==='POST'){sent=JSON.parse(options.body);id=(await response.clone().json()).id;}return response;};
    app.doc.getElementById('send-mission').click();
    await waitFor(async()=>{await app.poll();return !!id&&['answered','clarifying','reviewed'].includes(app.doc.getElementById('chat-status').textContent);});
    assert.equal(sent.attachments.length,1);assert.ok(sent.message.trim());assert.equal(app.doc.querySelectorAll('#chat-messages .message.user audio').length,1);
    const token=(await (await original('/api/session')).json()).token;const chat=await (await original('/api/chats/'+id,{headers:{'X-Console-Token':token}})).json();
    assert.equal(chat.attachments[0].kind,'audio');assert.equal(chat.attachments[0].status,'ready');assert.match(chat.attachments[0].filename,/\.wav$/);
    assert.equal(app.doc.getElementById('voice-recording').hidden,true);assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});

test('an unsent specialist draft preserves its advisory identity across refresh and sends to that agent',async()=>{
  const original=await setup();let restored;try{
    original.doc.querySelector('[data-nav="organization"]').click();
    const search=original.doc.getElementById('agent-search');search.value='Recovery Planner';search.dispatchEvent(new original.win.Event('input'));
    original.doc.querySelector('#search-results button').click();
    [...original.doc.getElementById('agent-inspector').querySelectorAll('button')].find(button=>button.textContent.startsWith('Chat with')).click();
    original.doc.getElementById('mission-input').value='Help me understand failed task recovery.';
    original.doc.getElementById('mission-input').dispatchEvent(new original.win.Event('input'));
    original.win.dispatchEvent(new original.win.Event('pagehide'));
    restored=await setup(null,{path:'/chat',savedSession:sessionSnapshot(original.win)});
    assert.equal(restored.doc.getElementById('mission-input').value,'Help me understand failed task recovery.');
    assert.equal(restored.doc.getElementById('agent-chat-context').hidden,false);
    assert.match(restored.doc.getElementById('agent-chat-name').textContent,/Recovery Planner/);
    let target;const before=restored.win.fetch;
    restored.win.fetch=(url,options)=>{if(String(url)==='/api/chats'&&options?.method==='POST')target=JSON.parse(options.body).agent_id;return before(url,options);};
    submit(restored.win,restored.doc.getElementById('mission-form'));
    await waitFor(async()=>{await restored.poll();return restored.doc.getElementById('chat-status').textContent==='answered';});
    assert.ok(target,'The restored draft must explicitly address its specialist');
    assert.match(restored.doc.querySelector('.message.assistant .message-label').textContent,/Recovery Planner/);
    assert.deepEqual(restored.errors,[]);
  }finally{await original.close();if(restored)await restored.close();}
});

test('Ask the organization clears an unsent specialist target while preserving its draft text',async()=>{
  const app=await setup();try{
    app.doc.querySelector('[data-nav="organization"]').click();
    const search=app.doc.getElementById('agent-search');search.value='Recovery Planner';search.dispatchEvent(new app.win.Event('input'));
    app.doc.querySelector('#search-results button').click();
    [...app.doc.getElementById('agent-inspector').querySelectorAll('button')].find(button=>button.textContent.startsWith('Chat with')).click();
    app.doc.getElementById('mission-input').value='Hi';app.doc.getElementById('mission-input').dispatchEvent(new app.win.Event('input'));
    app.doc.getElementById('organization-chat').click();
    assert.equal(app.doc.getElementById('mission-input').value,'Hi');assert.equal(app.doc.getElementById('agent-chat-context').hidden,true);assert.doesNotMatch(app.doc.getElementById('mission-input').placeholder,/Recovery Planner/);
    let payload;const original=app.win.fetch;
    app.win.fetch=(url,options)=>{if(String(url)==='/api/chats'&&options?.method==='POST')payload=JSON.parse(options.body);return original(url,options);};
    submit(app.win,app.doc.getElementById('mission-form'));
    await waitFor(async()=>{await app.poll();return app.doc.getElementById('chat-status').textContent==='answered';});
    assert.equal(payload.agent_id,null);assert.match(app.doc.querySelector('.message.assistant .markdown-body').textContent,/Hello from the scripted test provider/);
    assert.deepEqual(app.errors,[]);
  }finally{await app.close();}
});
