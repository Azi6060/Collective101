'use strict';
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

function mediaPreview(item,src,openImage){
  if(item.kind==='image'){const button=action('',()=>openImage?.(),'attachment-thumbnail');button.setAttribute('aria-label','Preview '+item.filename);const img=element('img','attachment-image');img.src=src;img.alt=item.filename;button.append(img);return button;}
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
