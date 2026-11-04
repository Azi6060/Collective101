'use strict';
// Browser speech and inert, server-validated uploads. Neither submits a model request.
window.CollectiveChatInputs=(()=>{
  const $=id=>document.getElementById(id);
  const languages={en:'en-US',zh:'zh-CN',es:'es-ES',hi:'hi-IN',ar:'ar-SA',fr:'fr-FR',pt:'pt-BR',ru:'ru-RU',bn:'bn-BD',de:'de-DE',ja:'ja-JP',ko:'ko-KR',id:'id-ID',ms:'ms-MY'};
  let callbacks,draft=[],uploads=0,epoch=0,enabled=false,recognition=null,listening=false,consented=false,readAloud=false,lastReply='',blobUrl=null,armed=false,referenceSignature='',decoratedRoot=null,decoratedSignature='',speaking=null,previewOpener=null;
  const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;
  const speech=window.speechSynthesis;
  const recording=window.CollectiveVoiceRecording;
  const queue=window.CollectiveUploads;
  const voiceIDs=new Set();
  const mediaURLs=new Map(),mediaLoads=new Map();
  function discardVoice(){queue?.cancelSource('voice');const removed=draft.filter(item=>voiceIDs.has(item.id));draft=draft.filter(item=>!voiceIDs.has(item.id));voiceIDs.clear();for(const item of removed){forgetURL(item.id);callbacks.api('/api/attachments/'+item.id+'/remove',{}).catch(error=>status(error.message));}drawDraft();}
  async function mediaURL(item){if(mediaURLs.has(item.id))return mediaURLs.get(item.id);if(mediaLoads.has(item.id))return mediaLoads.get(item.id);const promise=(async()=>{const blob=await callbacks.resource('/api/attachments/'+item.id+'/content'),url=URL.createObjectURL(new Blob([blob],{type:item.mime}));mediaURLs.set(item.id,url);return url;})();mediaLoads.set(item.id,promise);try{return await promise;}finally{mediaLoads.delete(item.id);}}
  function forgetURL(id){const url=mediaURLs.get(id);if(url)URL.revokeObjectURL(url);mediaURLs.delete(id);}
  function decorateMedia(row,item){if(!['audio','image'].includes(item.kind))return;const loading=el('small','media-loading','Loading preview...');row.append(loading);mediaURL(item).then(url=>{if(row.isConnected)loading.replaceWith(mediaPreview({...item,filename:item.filename||item.name},url,()=>view(item)));}).catch(error=>{loading.textContent=error.message;});}
  const el=(tag,cls,text)=>{const node=document.createElement(tag);if(cls)node.className=cls;if(text!==undefined)node.textContent=text;return node;};
  function status(text){$('chat-input-status').textContent=text;$('chat-input-status').hidden=!text;callbacks?.changed();}
  function controls(){
    $('attach-files').disabled=!enabled||uploads>0||!!queue?.working();
    const active=listening||recording?.busy(),supported=Recognition||recording?.supported();
    $('voice-input').disabled=!enabled||!supported;
    $('voice-input').setAttribute('aria-pressed',String(!!active));
    $('voice-input').setAttribute('aria-label',active?'Stop voice input':'Start voice input');
    $('voice-input').title=!supported?'Voice input is unavailable in this browser. You can keep typing.':active?'Stop voice input':'Voice input';
    $('voice-input').classList.toggle('listening',!!active);
    $('voice-playback').disabled=!speech||!window.SpeechSynthesisUtterance;
    $('voice-playback').setAttribute('aria-pressed',String(readAloud));
    callbacks?.changed();
  }
  function badge(item){return item.kind==='video'?'Reference only':item.status==='ready'?'Ready':item.status==='failed'?'Could not read':item.status==='processing'?'Reading...':'Read when you send';}
  function action(text,fn,cls='attachment-action'){const button=el('button',cls,text);button.type='button';button.addEventListener('click',fn);return button;}
  function drawDraft(){
    const list=$('composer-attachments');list.hidden=!draft.length;
    list.replaceChildren(...draft.map(item=>{
      const row=el('div','attachment-chip');row.setAttribute('role','listitem');
      const copy=el('span','attachment-chip-copy');copy.append(el('strong','',item.name),el('small','',badge(item)));
      row.append(copy,action('×',async()=>{try{await callbacks.api('/api/attachments/'+item.id+'/remove',{});draft=draft.filter(file=>file.id!==item.id);forgetURL(item.id);drawDraft();status('Attachment removed.');}catch(error){status(error.message);}},'attachment-remove'));
      row.lastChild.setAttribute('aria-label','Remove '+item.name);decorateMedia(row,item);return row;
    }));callbacks?.draftChanged();controls();
  }
  async function uploadFiles(files){
    if(!enabled||uploads)return;const selected=[...files];$('chat-files').value='';await queue?.upload(selected);
  }
  async function restore(identifiers){
    if(!identifiers?.length)return 0;const current=epoch;uploads++;controls();
    try{const result=await callbacks.api('/api/attachments?ids='+identifiers.map(encodeURIComponent).join(','));if(current!==epoch)return 0;draft=result.attachments;drawDraft();return result.missing;}
    finally{uploads--;controls();}
  }
  function stopListening(abort=false){
    if(!recognition)return;
    if(abort){const active=recognition;recognition=null;listening=false;try{active.abort();}catch{}controls();}
    else{try{recognition.stop();status('Finishing the transcript…');}catch{stopListening(true);status('Voice input stopped.');}}
  }
  function startListening(){
    if(!Recognition||listening)return;
    speaking=null;if(speech)speech.cancel();$('stop-speaking').hidden=true;
    const active=new Recognition();recognition=active;active.lang=languages[document.documentElement.lang]||'en-US';active.continuous=true;active.interimResults=true;
    const seen=new Set();
    active.onstart=()=>{if(recognition!==active)return;listening=true;controls();status('Listening. Stop when you are ready to review your message.');};
    active.onresult=event=>{
      if(recognition!==active)return;
      let interim='';
      for(let i=event.resultIndex;i<event.results.length;i++){
        const result=event.results[i];
        if(result.isFinal&&!seen.has(i)){
          seen.add(i);const field=$('mission-input'),next=(field.value.trimEnd()+' '+result[0].transcript).trimStart();
          if(next.length>500000){status('The message limit was reached. Shorten the draft before continuing.');stopListening(true);return;}
          field.value=next;callbacks.draftChanged();callbacks.growComposer();
        }else if(!result.isFinal)interim+=result[0].transcript+' ';
      }
      status(interim?'Listening: '+interim.slice(0,180):'Listening. Your words are being added to the draft.');
    };
    active.onerror=event=>{
      if(recognition!==active)return;
      recognition=null;listening=false;controls();
      const errors={'not-allowed':'Microphone access was denied. Allow it in your browser settings, or keep typing.','audio-capture':'No microphone is available. Check your device, or keep typing.','network':'The browser speech service could not connect. Try again or keep typing.','no-speech':'No speech was detected. Try again when you are ready.','language-not-supported':'Your browser speech service does not support this language.'};
      status((errors[event.error]||'Voice input stopped. You can keep typing or try again.')+(recording?.busy()?' Audio recording continues until you stop it.':''));
    };
    active.onend=()=>{if(recognition!==active)return;recognition=null;listening=false;controls();status(recording?.busy()?'Transcription stopped. Audio recording continues until you stop it.':'Voice input stopped. Review your message before sending.');};
    try{listening=true;controls();status('Waiting for microphone permission…');active.start();}catch{recognition=null;listening=false;controls();status('Voice input could not start. Check microphone permissions or keep typing.');}
  }
  async function startVoice(){
    stopListening(true);speaking=null;if(speech)speech.cancel();$('stop-speaking').hidden=true;recording?.pause();
    if(recording?.supported()){
      const started=await recording.start();if(!started)return;
      if(Recognition&&$('voice-transcribe').checked)startListening();
      else status('Recording audio locally. Type a message when you are ready; audio is not sent.');
    }else if(Recognition)startListening();
  }
  function stopVoice(){recording?.finish();stopListening();}
  function speak(text){
    if(!speech||!window.SpeechSynthesisUtterance)return;
    stopListening(true);recording?.finish();recording?.pause();speaking=null;speech.cancel();
    const utterance=new SpeechSynthesisUtterance(text.slice(0,6000));utterance.lang=languages[document.documentElement.lang]||'en-US';
    speaking=utterance;
    const voice=speech.getVoices().find(item=>item.lang.toLowerCase().startsWith(document.documentElement.lang));if(voice)utterance.voice=voice;
    $('stop-speaking').hidden=false;
    utterance.onend=()=>{if(speaking===utterance){speaking=null;$('stop-speaking').hidden=true;}};utterance.onerror=()=>{if(speaking===utterance){speaking=null;$('stop-speaking').hidden=true;status('Read-aloud stopped. The written reply is still available.');}};
    speech.speak(utterance);status(text.length>6000?'Reading the first 6,000 characters. The full reply is available in Chat.':'Reading the reply aloud.');
  }
  function stop(){const active=listening||speaking;stopListening(true);recording?.finish();recording?.pause();speaking=null;if(speech)speech.cancel();$('stop-speaking').hidden=true;if(active)status('Voice stopped.');}
  function closePreview(){if($('attachment-viewer').close)$('attachment-viewer').close();else $('attachment-viewer').removeAttribute('open');$('attachment-preview').replaceChildren();if(blobUrl){URL.revokeObjectURL(blobUrl);blobUrl=null;}if(previewOpener?.isConnected)previewOpener.focus();}
  async function view(item){
    previewOpener=document.activeElement;
    try{
      const bytes=await callbacks.resource('/api/attachments/'+item.id+'/content');
      $('attachment-preview').replaceChildren();$('attachment-viewer-title').textContent=item.name;
      if(blobUrl)URL.revokeObjectURL(blobUrl);
      if(item.kind==='video'||item.kind==='image'){
        blobUrl=URL.createObjectURL(new Blob([bytes],{type:item.mime}));
        const media=el(item.kind==='video'?'video':'img','attachment-media');media.src=blobUrl;
        if(item.kind==='video'){media.controls=true;media.preload='metadata';media.addEventListener('error',()=>{$('attachment-preview').append(el('p','',"Your browser cannot play this format. Download the original instead."));});}
        else media.alt=item.name;
        $('attachment-preview').append(media);
      }else if(item.kind==='audio'){
        blobUrl=URL.createObjectURL(new Blob([bytes],{type:item.mime}));$('attachment-preview').append(mediaPreview({...item,filename:item.name},blobUrl));
      }else if(item.kind==='text'||item.mime==='text/plain'){
        const text=await bytes.text();$('attachment-preview').append(el('pre','attachment-source',text.slice(0,50000)));
        if(text.length>50000)$('attachment-preview').append(el('p','','Showing the first 50,000 characters. Download the original for the full file.'));
      }else{$('attachment-preview').append(el('p','','This document is available as an original download.'));
      }
      $('attachment-preview').append(action('Download original',()=>download(item)));
      if($('attachment-viewer').showModal)$('attachment-viewer').showModal();else $('attachment-viewer').setAttribute('open','');
      $('close-attachment').focus();
    }catch(error){status(error.message);}
  }
  async function download(item){try{const bytes=await callbacks.resource('/api/attachments/'+item.id+'/content');callbacks.save(bytes,item.name);}catch(error){status(error.message);}}
  function fileRow(item){
    const row=el('div','reference-file');row.dataset.attachmentId=item.id;const icon=el('span','reference-kind',item.kind==='video'?'VID':item.kind==='image'?'IMG':'FILE');icon.setAttribute('aria-hidden','true');
    const copy=el('span','reference-copy');copy.append(el('strong','',item.name),el('small','',Math.max(1,Math.round(item.size/1024))+' KiB · '+badge(item)));
    row.append(icon,copy,action(item.kind==='document'&&item.mime!=='text/plain'?'Download':'View',()=>item.kind==='document'&&item.mime!=='text/plain'?download(item):view(item)));row.lastChild.setAttribute('aria-label',(item.kind==='document'&&item.mime!=='text/plain'?'Download ':'View ')+item.name);decorateMedia(row,item);return row;
  }
  function onChat(chat,viewName){
    const items=chat?.attachments||[];
    document.querySelectorAll('#chat-messages [data-attachment-id]').forEach(card=>{const item=items.find(item=>item.id===card.dataset.attachmentId),label=card.querySelector('.attachment-state');if(item&&label)label.textContent=badge(item);});
    $('workspace-reference-count').textContent=String(items.length);
    const filter=$('workspace-file-search').value.trim().toLowerCase(),visible=items.filter(item=>item.name.toLowerCase().includes(filter));
    const signature=JSON.stringify([chat?.id,items,filter]);
    if(referenceSignature!==signature){
      referenceSignature=signature;
      $('workspace-references').replaceChildren(...(visible.length?visible.map(fileRow):[el('p','workspace-muted',filter?'No matching uploaded files.':'Your uploaded reference files will appear here.')]));
    }
    const root=$('chat-messages').firstChild,key=JSON.stringify([chat?.transcript,signature]);
    if(root!==decoratedRoot||key!==decoratedSignature){
    decoratedRoot=root;decoratedSignature=key;

    chat?.transcript.forEach((message,index)=>{
      const bubble=document.querySelector('#chat-messages [data-message-index="'+index+'"]');if(!bubble)return;
      const files=items.filter(item=>item.message_index===index||message.attachments?.includes(item.id));
      const mediaKey=JSON.stringify(files.map(item=>[item.id,item.mime,item.relative_path]));
      if(bubble.dataset.mediaKey===mediaKey)return;
      bubble.dataset.mediaKey=mediaKey;bubble.querySelectorAll('.message-attachments,.message-listen').forEach(node=>node.remove());
      if(files.length){const list=el('div','message-attachments');list.append(...files.map(fileRow));bubble.append(list);}
      if(message.role==='assistant'&&speech){const read=action('Read aloud',()=>speak(bubble.querySelector('.markdown-body,.message-content')?.textContent||message.content),'message-listen');read.setAttribute('aria-label','Read this reply aloud');bubble.append(read);}
    });
    }
    const last=chat?.transcript.at(-1),replyKey=chat?.id+':'+chat?.status+':'+chat?.transcript.length+':'+last?.content;
    if(replyKey!==lastReply){lastReply=replyKey;if(armed&&readAloud&&viewName==='chat'&&!document.hidden&&last?.role==='assistant'&&['answered','reviewed','blocked','clarifying'].includes(chat.status)){armed=false;const body=window.markdownFragment?markdownFragment(last.display_content||last.content).textContent:last.content;speak(body);}}
  }
  function clear(remove=true){const old=draft;draft=[];epoch++;if(remove)armed=false;stop();recording?.clear();queue?.clear();drawDraft();status('');if(remove)return Promise.allSettled(old.filter(item=>!item.chat_id).map(item=>callbacks.api('/api/attachments/'+item.id+'/remove',{})));}
  function init(handlers){
    callbacks=handlers;
    queue?.init({changed:controls,status,token:()=>callbacks.token(),expired:()=>callbacks.expired(),count:()=>draft.length,bytes:()=>draft.reduce((sum,item)=>sum+item.size,0),remove:id=>callbacks.api('/api/attachments/'+id+'/remove',{}),added:(item,file,source)=>{if(source==='voice')voiceIDs.add(item.id);if(file&&['image','audio'].includes(item.kind)){forgetURL(item.id);mediaURLs.set(item.id,URL.createObjectURL(file));}if(!draft.some(value=>value.id===item.id))draft.push(item);drawDraft();}});
    recording?.init({discardClip:discardVoice,file:file=>queue?.upload([file],'voice'),changed:controls,status,finished:()=>stopListening(),beforePlay:()=>{stopListening(true);speaking=null;if(speech)speech.cancel();$('stop-speaking').hidden=true;}});
    $('voice-transcribe').disabled=!Recognition;$('voice-transcribe').checked=!!Recognition;
    if(!recording?.supported())$('voice-recording-copy').textContent='Audio recording and waveforms are unavailable in this browser. You can still dictate an editable transcript with its speech service.';
    if(!Recognition)$('voice-transcribe-note').textContent='Speech-to-text is unavailable in this browser. You can record, listen back and type your message.';
    const menu=$('attachment-menu'),opener=$('attach-files');opener.setAttribute('aria-haspopup','true');opener.setAttribute('aria-expanded','false');
    const closeMenu=()=>{menu.hidden=true;opener.setAttribute('aria-expanded','false');};
    opener.addEventListener('click',()=>{menu.hidden=!menu.hidden;opener.setAttribute('aria-expanded',String(!menu.hidden));if(!menu.hidden)$('attachment-pick-file').focus();});
    for(const [choice,id] of [['file','chat-files'],['folder','chat-folder'],['photo','chat-photo']])$('attachment-pick-'+choice).addEventListener('click',()=>{closeMenu();$(id).click();});
    for(const id of ['chat-folder','chat-photo'])$(id).addEventListener('change',event=>{uploadFiles(event.target.files);$(id).value='';});
    menu.addEventListener('keydown',event=>{if(event.key==='Escape'){closeMenu();opener.focus();}if(['ArrowUp','ArrowDown'].includes(event.key)){event.preventDefault();const nodes=[...menu.querySelectorAll('button')],index=nodes.indexOf(document.activeElement);nodes[(index+(event.key==='ArrowDown'?1:nodes.length-1))%nodes.length].focus();}});
    document.addEventListener('click',event=>{if(!menu.contains(event.target)&&!opener.contains(event.target))closeMenu();});$('chat-files').addEventListener('change',event=>uploadFiles(event.target.files));
    $('voice-input').addEventListener('click',()=>{if(listening||recording?.busy()){stopVoice();return;}if(!consented){if($('voice-dialog').showModal)$('voice-dialog').showModal();else $('voice-dialog').setAttribute('open','');$('voice-start').focus();return;}startVoice();});
    $('voice-start').addEventListener('click',()=>{consented=true;if($('voice-dialog').close)$('voice-dialog').close();else $('voice-dialog').removeAttribute('open');$('voice-input').focus();startVoice();});
    $('voice-cancel').addEventListener('click',()=>{if($('voice-dialog').close)$('voice-dialog').close();else $('voice-dialog').removeAttribute('open');$('voice-input').focus();});
    $('voice-playback').addEventListener('click',()=>{readAloud=!readAloud;controls();if(!readAloud&&speech){speech.cancel();$('stop-speaking').hidden=true;}status(readAloud?'Read-aloud is on for new replies while you are in Chat.':'Read-aloud is off.');});
    $('stop-speaking').addEventListener('click',()=>{speaking=null;if(speech)speech.cancel();$('stop-speaking').hidden=true;status('Read-aloud stopped.');});
    $('close-attachment').addEventListener('click',closePreview);
    $('attachment-viewer').addEventListener('cancel',event=>{event.preventDefault();closePreview();});
    $('attachment-viewer').addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();closePreview();}});
    window.addEventListener('pagehide',()=>{stop();if(blobUrl)URL.revokeObjectURL(blobUrl);for(const id of mediaURLs.keys())forgetURL(id);});
    document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
    controls();
  }
  function available(value){enabled=value;controls();}
  return {init,available,onChat,uploadFiles,restore,clear,stop,selecting:()=>{armed=false;stop();recording?.clear();},beginMessage:()=>{armed=true;},sent:()=>clear(false),ids:()=>draft.map(item=>item.id),busy:()=>uploads>0||listening||!!recording?.busy()||!!queue?.busy(),
    reserve:()=>($('composer-attachments').hidden?0:$('composer-attachments').offsetHeight)+($('chat-input-status').hidden?0:$('chat-input-status').offsetHeight)+(recording?.reserve()||0)+(queue?.reserve()||0)+($('draft-recovery').hidden?0:$('draft-recovery').offsetHeight)};
})();
