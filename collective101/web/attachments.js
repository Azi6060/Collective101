'use strict';
let pendingAttachments=[],uploadBusy=false,voiceRecorder=null,voiceStream=null,voiceCancelled=false,voiceTimer=null;
const attachmentURLs=new Map();
let uploadEpoch=0;
function cancelVoiceRecording(){if(voiceRecorder?.state==='recording'){voiceCancelled=true;voiceRecorder.stop();}}
function releaseAttachmentURLs(){for(const url of attachmentURLs.values())URL.revokeObjectURL(url);attachmentURLs.clear();}
function clearPendingAttachments(discard=true){
  uploadEpoch++;
  if(discard)for(const item of pendingAttachments){forgetAttachment(item.id);api('/api/attachments/'+item.id+'/remove',{}).catch(()=>{});}
  pendingAttachments=[];$('upload-status').textContent='';renderPendingAttachments();
}
function forgetAttachment(id){const url=attachmentURLs.get(id);if(url)URL.revokeObjectURL(url);attachmentURLs.delete(id);}
function showAttachmentImage(src,name){const dialog=$('attachment-lightbox');$('attachment-large-image').src=src;$('attachment-large-image').alt=name;if(dialog.showModal)dialog.showModal();else dialog.setAttribute('open','');}
function mediaPreview(item,src){
  if(item.kind==='image'){const button=action('',()=>showAttachmentImage(src,item.filename),'attachment-thumbnail');button.setAttribute('aria-label','Preview '+item.filename);const img=element('img','attachment-image');img.src=src;img.alt=item.filename;button.append(img);return button;}
  const box=element('div','audio-replay'),audio=element('audio','replay-native');audio.controls=true;audio.preload='metadata';audio.src=src;audio.tabIndex=-1;audio.setAttribute('aria-label','Audio recording '+item.filename);
  const play=action('',()=>{if(audio.paused)audio.play().catch(()=>notice('Audio cannot be played in this browser. Download the recording to listen.'));else audio.pause();},'audio-play attachment-open');play.setAttribute('aria-label','Play '+item.filename);play.title='Play recording';
  const icon=document.createElementNS('http://www.w3.org/2000/svg','svg');icon.setAttribute('viewBox','0 0 24 24');icon.setAttribute('width','16');icon.setAttribute('height','16');icon.setAttribute('fill','currentColor');icon.setAttribute('aria-hidden','true');const symbol=document.createElementNS('http://www.w3.org/2000/svg','path');symbol.setAttribute('d','M8 5v14l11-7z');icon.append(symbol);play.append(icon);
  const track=element('div','audio-track'),bars=element('div','audio-wave');bars.setAttribute('aria-hidden','true');for(let i=0;i<32;i++){const bar=element('i');bar.style.height=(18+((i*17+item.size)%31))+'%';bars.append(bar);}
  const seek=element('input','audio-seek');seek.type='range';seek.min='0';seek.max='1000';seek.value='0';seek.step='1';seek.setAttribute('aria-label','Seek in '+item.filename);seek.disabled=true;track.append(bars,seek);
  const clock=element('span','audio-clock','0:00'),format=n=>Number.isFinite(n)?Math.floor(n/60)+':'+String(Math.floor(n%60)).padStart(2,'0'):'0:00';
  const update=()=>{const duration=Number.isFinite(audio.duration)?audio.duration:0;clock.textContent=format(audio.currentTime)+(duration?' / '+format(duration):'');seek.disabled=!duration;seek.value=duration?String(Math.round(audio.currentTime/duration*1000)):'0';seek.setAttribute('aria-valuetext',format(audio.currentTime)+' of '+format(duration));};
  for(const event of ['loadedmetadata','durationchange','timeupdate','ended'])audio.addEventListener(event,update);
  audio.addEventListener('play',()=>{symbol.setAttribute('d','M6 5h4v14H6zm8 0h4v14h-4z');play.setAttribute('aria-label','Pause '+item.filename);play.title='Pause recording';});audio.addEventListener('pause',()=>{symbol.setAttribute('d','M8 5v14l11-7z');play.setAttribute('aria-label','Play '+item.filename);play.title='Play recording';});
  seek.addEventListener('input',()=>{if(Number.isFinite(audio.duration))audio.currentTime=audio.duration*Number(seek.value)/1000;});box.append(audio,play,track,clock);return box;
}
function renderPendingAttachments(){
  $('pending-attachments').replaceChildren(...pendingAttachments.map(item=>{const row=element('div','attachment-chip pending-media');row.append(element('span','attachment-kind',item.kind==='audio'?'VOICE':item.kind==='image'?'IMAGE':'FILE'),element('span','attachment-name',item.relative_path||item.filename),element('small','',Math.ceil(item.size/1024)+' KB'));
    const src=attachmentURLs.get(item.id);if(src&&['image','audio'].includes(item.kind))row.append(mediaPreview(item,src));
    const remove=action('Remove',()=>{pendingAttachments=pendingAttachments.filter(a=>a.id!==item.id);forgetAttachment(item.id);api('/api/attachments/'+item.id+'/remove',{}).catch(()=>{});state.pendingRequest=null;renderPendingAttachments();},'attachment-remove');remove.setAttribute('aria-label','Remove '+item.filename);row.append(remove);return row;}));
}
async function normalizeAudio(file){
  const Constructor=window.AudioContext||window.webkitAudioContext;
  if(!Constructor)throw new Error('Audio conversion is unavailable in this browser. Upload mono 16-bit WAV at 16 or 24 kHz.');
  const context=new Constructor();let decoded;
  try{decoded=await context.decodeAudioData(await file.arrayBuffer());}finally{await context.close();}
  const length=Math.ceil(decoded.duration*24000);
  if(length*2+44>25*1024*1024)throw new Error('Recording is too large; choose a shorter audio file.');
  const offline=new OfflineAudioContext(1,length,24000),source=offline.createBufferSource();source.buffer=decoded;source.connect(offline.destination);source.start();
  const result=await offline.startRendering(),samples=result.getChannelData(0),buffer=new ArrayBuffer(44+samples.length*2),view=new DataView(buffer);
  const text=(offset,value)=>{for(let i=0;i<value.length;i++)view.setUint8(offset+i,value.charCodeAt(i));};
  text(0,'RIFF');view.setUint32(4,36+samples.length*2,true);text(8,'WAVE');text(12,'fmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,24000,true);view.setUint32(28,48000,true);view.setUint16(32,2,true);view.setUint16(34,16,true);text(36,'data');view.setUint32(40,samples.length*2,true);
  for(let i=0;i<samples.length;i++){const sample=Math.max(-1,Math.min(1,samples[i]));view.setInt16(44+i*2,sample<0?sample*32768:sample*32767,true);}
  return new File([buffer],file.name.replace(/\.[^.]*$/,'')+'.wav',{type:'audio/wav'});
}
async function fileBase64(file){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onerror=()=>reject(new Error('Could not read '+file.name));reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.readAsDataURL(file);});}
async function queueAttachments(files){
  if(uploadBusy)throw new Error('Wait for the current upload to finish.');
  const epoch=uploadEpoch;uploadBusy=true;$('record-voice').disabled=true;$('attach-files').disabled=true;$('send-mission').disabled=true;
  let skipped=0;try{for(let file of files){
    const relative=file.webkitRelativePath||'';
    if(relative&&(relative.split('/').some(part=>part.startsWith('.')&&!['.env.example','.gitignore','.dockerignore'].includes(part)||/^(node_modules|__pycache__|work|dist|\.venv)$/i.test(part))||/\.(db|sqlite3?|pyc|pem|key)$/i.test(file.name)||!/\.(txt|md|markdown|csv|json|jsonl|docx|pdf|png|jpe?g|webp|gif|wav|mp3|m4a|ogg|webm|html|css|[cm]?js|[jt]sx?|py|ya?ml|xml|log|sql|toml|ini|cfg|conf|go|rs|java|c|cpp|h|cs|sh|ps1|bat|rb|php|r|swift|kt|vue|svelte|graphql|proto)$/i.test(file.name)&&!['dockerfile','makefile','license','procfile','.env.example','.gitignore','.dockerignore'].includes(file.name.toLowerCase()))){skipped++;continue;}
    if(file.size>25*1024*1024)throw new Error(file.name+' exceeds 25 MiB.');
    $('upload-status').textContent='Preparing '+file.name+'...';
    if(/\.(wav|mp3|m4a|ogg|webm)$/i.test(file.name)&&window.AudioContext)file=await normalizeAudio(file);
    const result=await api('/api/attachments',{filename:file.name,relative_path:relative||undefined,mime:file.type,data:await fileBase64(file)});if(epoch!==uploadEpoch){await api('/api/attachments/'+result.id+'/remove',{});continue;}if(['image','audio'].includes(result.kind))attachmentURLs.set(result.id,URL.createObjectURL(file));pendingAttachments.push({...result,relative_path:relative||result.relative_path});state.pendingRequest=null;renderPendingAttachments();
  }
  $('upload-status').textContent='Files stay local until you send. Your connected model processes them with your message.'+(skipped?' Skipped '+skipped+' private, cached or unsupported file(s).':'');
  }catch(error){$('upload-status').textContent=error.message;throw error;}
  finally{uploadBusy=false;$('record-voice').disabled=false;$('attach-files').disabled=false;$('send-mission').disabled=requiresRestart()||!!voiceRecorder||!!state.chat&&['intake','running','clarifying','needs_input','paused','interrupted'].includes(state.chat.status);}
}
const attachmentLoads=new Map();
async function attachmentSource(item){
  if(attachmentURLs.has(item.id))return attachmentURLs.get(item.id);
  if(attachmentLoads.has(item.id))return attachmentLoads.get(item.id);
  const load=(async()=>{const response=await fetch('/api/attachments/'+item.id,{headers:{'X-Console-Token':state.token}});if(!response.ok)throw new Error('Attachment is unavailable');const blob=await response.blob(),url=URL.createObjectURL(new Blob([blob],{type:item.mime}));attachmentURLs.set(item.id,url);return url;})();
  attachmentLoads.set(item.id,load);try{return await load;}finally{attachmentLoads.delete(item.id);}
}
function appendMessageAttachments(bubble,message,chat){
  if(!message.attachments?.length)return;const list=element('div','attachment-list sent-attachments');
  for(const id of message.attachments){const item=chat.attachments?.find(a=>a.id===id);if(!item)continue;
    const card=element('div','attachment-chip sent-media');card.dataset.attachmentId=id;
    const status=element('small','attachment-state',item.status==='ready'?'Ready':item.status==='failed'?'Could not read':item.status==='processing'?'Reading...':'Waiting to read');
    card.append(element('span','attachment-kind',item.kind==='audio'?'VOICE':item.kind==='image'?'IMAGE':'FILE'),element('span','attachment-name',item.relative_path||item.filename),status);
    if(['image','audio'].includes(item.kind)){const loading=element('span','attachment-loading','Loading preview...');card.append(loading);attachmentSource(item).then(src=>{loading.replaceWith(mediaPreview(item,src));}).catch(error=>{loading.textContent=error.message;});}
    const download=action('Download',async()=>{try{const link=element('a');link.href=await attachmentSource(item);link.download=item.filename;link.click();}catch(error){notice(error.message);}},'attachment-download');card.append(download);if(item.error)card.append(element('p','text-danger small',item.error));list.append(card);
  }bubble.append(list);
}
async function recordVoice(){
  if(voiceRecorder){if(voiceRecorder.state==='recording')voiceRecorder.stop();return;}
  if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){notice('Voice recording is unavailable here. Attach a WAV or MP3 file instead.');return;}
  try{
    voiceCancelled=false;voiceStream=await navigator.mediaDevices.getUserMedia({audio:true});voiceRecorder=new MediaRecorder(voiceStream);const chunks=[];let bytes=0;const start=Date.now();
    voiceRecorder.ondataavailable=event=>{chunks.push(event.data);bytes+=event.data.size;if(bytes>20*1024*1024&&voiceRecorder?.state==='recording')voiceRecorder.stop();};
    voiceRecorder.onstop=async()=>{clearInterval(voiceTimer);voiceStream?.getTracks().forEach(track=>track.stop());const mime=voiceRecorder.mimeType;voiceRecorder=null;voiceStream=null;$('record-voice').setAttribute('aria-label','Record voice message');$('record-voice').classList.remove('recording');$('cancel-recording').hidden=true;
      if(voiceCancelled){$('upload-status').textContent='Recording cancelled.';$('send-mission').disabled=requiresRestart();return;}
      try{await queueAttachments([new File(chunks,'voice-message.webm',{type:mime})]);}catch(error){notice(error.message);}
    };
    voiceRecorder.start(1000);$('record-voice').setAttribute('aria-label','Stop recording');$('record-voice').classList.add('recording');$('cancel-recording').hidden=false;$('send-mission').disabled=true;
    const update=()=>{$('upload-status').textContent='Recording '+Math.floor((Date.now()-start)/1000)+'s - click the microphone to stop.';};update();voiceTimer=setInterval(update,1000);
  }catch(error){voiceStream?.getTracks().forEach(track=>track.stop());voiceRecorder=null;notice('Could not start recording. Allow microphone access or attach an audio file.');}
}
function initAttachments(){
  const menu=$('attachment-menu'),opener=$('attach-files');
  function closeMenu(){menu.hidden=true;opener.setAttribute('aria-expanded','false');}
  opener.addEventListener('click',()=>{menu.hidden=!menu.hidden;opener.setAttribute('aria-expanded',String(!menu.hidden));if(!menu.hidden)$('attachment-pick-file').focus();});
  for(const [choice,input] of [['file','files'],['folder','folder'],['photo','photo']])$('attachment-pick-'+choice).addEventListener('click',()=>{closeMenu();$('attachment-'+input).click();});
  menu.addEventListener('keydown',event=>{if(event.key==='Escape'){closeMenu();opener.focus();}if(['ArrowDown','ArrowUp'].includes(event.key)){event.preventDefault();const buttons=[...menu.querySelectorAll('button')],i=buttons.indexOf(document.activeElement);buttons[(i+(event.key==='ArrowDown'?1:buttons.length-1))%buttons.length].focus();}});
  document.addEventListener('click',event=>{if(!menu.contains(event.target)&&!opener.contains(event.target))closeMenu();});
  for(const id of ['attachment-folder','attachment-photo'])$(id).addEventListener('change',async()=>{try{await queueAttachments([...$(id).files]);}catch(error){notice(error.message);}finally{$(id).value='';}});
  $('close-attachment-preview').addEventListener('click',()=>{$('attachment-lightbox').close?.();$('attachment-lightbox').removeAttribute('open');});
  $('attachment-files').addEventListener('change',async()=>{try{await queueAttachments([...$('attachment-files').files]);}catch(error){notice(error.message);}finally{$('attachment-files').value='';}});
  $('record-voice').addEventListener('click',recordVoice);$('cancel-recording').addEventListener('click',()=>{voiceCancelled=true;voiceRecorder?.stop();});
  $('organization-chat').addEventListener('click',()=>{const message=$('mission-input').value||state.chat?.transcript.filter(m=>m.role==='user').at(-1)?.content||'';newMission();$('mission-input').value=message;growComposer();});
  window.addEventListener('beforeunload',()=>{voiceStream?.getTracks().forEach(t=>t.stop());releaseAttachmentURLs();});
}
