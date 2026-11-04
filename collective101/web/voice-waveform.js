'use strict';
// Local recording with waveform and replay; attachment processing starts only when the user sends.
window.CollectiveVoiceRecording=(()=>{
  const $=id=>document.getElementById(id),limitSeconds=120,limitBytes=8*1024*1024;
  const supported=()=>!!(navigator.mediaDevices?.getUserMedia&&window.MediaRecorder);
  let callbacks,session=null,clipUrl=null,duration=0,envelope=[],bars=[],generation=0;
  const clock=seconds=>Math.floor(seconds/60)+':'+String(Math.floor(seconds%60)).padStart(2,'0');
  const audio=()=>$('voice-audio');
  const busy=()=>!!session;
  function changed(){callbacks?.changed();}
  function label(text){$('voice-recording-state').textContent=text;}
  function reduced(){return document.documentElement.dataset.reduceMotion==='true'||window.matchMedia('(prefers-reduced-motion: reduce)').matches;}
  function draw(values,progress=0){
    bars.forEach((bar,index)=>{
      const start=Math.floor(index*values.length/bars.length),end=Math.max(start+1,Math.floor((index+1)*values.length/bars.length));
      let peak=0;for(let i=start;i<end;i++)peak=Math.max(peak,values[i]||0);
      const height=Math.max(3,Math.min(42,peak*100));
      bar.setAttribute('y1',String(24-height/2));bar.setAttribute('y2',String(24+height/2));
      bar.classList.toggle('heard',progress>0&&index/bars.length<progress);
    });
    $('voice-playhead').setAttribute('x1',String(2+progress*316));$('voice-playhead').setAttribute('x2',String(2+progress*316));
    $('voice-playhead').style.visibility=clipUrl?'visible':'hidden';
  }
  function playback(){
    const current=Math.min(duration,audio().currentTime||0);
    $('voice-seek').value=String(current);$('voice-elapsed').textContent=clock(current)+' / '+clock(duration);
    const action=audio().paused?'Play recording':'Pause playback';
    $('voice-replay').setAttribute('aria-label',action);$('voice-replay').title=action;$('voice-replay').dataset.playing=String(!audio().paused);
    draw(envelope,duration?current/duration:0);
  }
  function pause(){if(clipUrl){audio().pause();playback();}}
  function release(active){
    clearInterval(active.timer);active.stream?.getTracks().forEach(track=>track.stop());
    try{active.source?.disconnect();}catch{}
    if(active.context)active.context.close().catch(()=>{});
  }
  function forget(){
    if(clipUrl){audio().pause();audio().removeAttribute('src');audio().load();URL.revokeObjectURL(clipUrl);clipUrl=null;}
    duration=0;envelope=[];$('voice-recording').hidden=true;$('voice-review-controls').hidden=true;changed();
  }
  function clear(){
    generation++;
    if(session){const active=session;session=null;active.discard=true;try{if(active.recorder?.state!=='inactive')active.recorder?.stop();}catch{}release(active);}
    forget();
  }
  function finish(message='Recording ready. Listen back and review your transcript before sending.'){
    if(!session)return;
    const active=session;
    if(active.stopping)return;
    active.stopping=true;active.message=message;active.stoppedAt=performance.now();
    if(!active.recorder){clear();callbacks?.finished();return;}
    label('Finishing recording');$('voice-record-stop').disabled=true;
    try{active.recorder.stop();}catch{active.discard=true;session=null;forget();callbacks?.status('The recording could not be saved. Your typed transcript is still available.');changed();}
    release(active);callbacks?.finished();
  }
  function tick(active){
    if(session!==active||active.stopping)return;
    const seconds=(performance.now()-active.started)/1000;
    let peak=0;
    if(active.analyser){active.analyser.getByteTimeDomainData(active.samples);for(const value of active.samples)peak+=(value-128)**2;peak=Math.sqrt(peak/active.samples.length)/128;}
    active.envelope.push(peak);
    if(active.envelope.length>1201)active.envelope.shift();
    $('voice-elapsed').textContent=clock(seconds)+' / 2:00';
    if(!reduced()||active.envelope.length%3===0)draw(active.envelope.slice(-40));
    if(seconds>=limitSeconds)finish('Two-minute limit reached. Listen back and review your transcript.');
  }
  async function start(){
    if(!supported()||session)return false;
    callbacks?.discardClip?.();forget();callbacks?.beforePlay();
    const active={generation:++generation,chunks:[],bytes:0,envelope:[],started:0};session=active;
    $('voice-recording').hidden=false;$('voice-recording').dataset.state='starting';$('voice-record-stop').hidden=false;$('voice-record-stop').disabled=false;
    $('voice-elapsed').textContent='0:00 / 2:00';label('Waiting for microphone permission');draw([]);changed();
    try{
      const stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true},video:false});
      if(session!==active||active.generation!==generation){stream.getTracks().forEach(track=>track.stop());return false;}
      active.stream=stream;
      const mime=['audio/webm;codecs=opus','audio/ogg;codecs=opus','audio/mp4'].find(type=>MediaRecorder.isTypeSupported?.(type));
      active.recorder=new MediaRecorder(stream,mime?{mimeType:mime,audioBitsPerSecond:64000}:{audioBitsPerSecond:64000});
      const Context=window.AudioContext||window.webkitAudioContext;
      if(Context){try{active.context=new Context();await active.context.resume();
        if(session!==active){release(active);return false;}
        active.source=active.context.createMediaStreamSource(stream);active.analyser=active.context.createAnalyser();active.analyser.fftSize=512;
        active.samples=new Uint8Array(512);active.source.connect(active.analyser);
      }catch{try{await active.context?.close();}catch{}active.context=null;}}
      if(session!==active){release(active);return false;}
      active.recorder.ondataavailable=event=>{
        if(active.discard||!event.data.size)return;
        active.bytes+=event.data.size;
        if(active.bytes>limitBytes){active.discard=true;finish('Recording was too large. Please try a shorter recording.');return;}
        active.chunks.push(event.data);
      };
      active.recorder.onerror=()=>{active.discard=true;finish('Audio recording failed. Your typed transcript is still available.');};
      active.recorder.onstop=()=>{
        release(active);if(session!==active||active.generation!==generation)return;
        const returnFocus=document.activeElement===$('voice-record-stop');
        session=null;$('voice-record-stop').hidden=true;callbacks?.finished();
        if(active.discard||!active.chunks.length){forget();callbacks?.status(active.message||'No audio was recorded. Check your microphone and try again.');changed();return;}
        duration=Math.min(limitSeconds,Math.max(.1,((active.stoppedAt||performance.now())-active.started)/1000));envelope=active.envelope;
        const clip=new Blob(active.chunks,{type:active.recorder.mimeType||active.chunks[0].type});clipUrl=URL.createObjectURL(clip);callbacks?.file?.(new File([clip],'voice-message.webm',{type:clip.type}));
        audio().src=clipUrl;$('voice-seek').max=String(duration);$('voice-recording').dataset.state='ready';$('voice-review-controls').hidden=false;
        label(active.analyser?'Voice clip':'Voice clip (waveform unavailable)');playback();callbacks?.status(active.message||'Recording ready. Listen back and review your transcript.');changed();if(returnFocus)$('voice-replay').focus();
      };
      active.started=performance.now();active.recorder.start(250);
      stream.getTracks().forEach(track=>track.addEventListener('ended',()=>{if(session===active)finish('Microphone disconnected. Review the audio captured so far.');},{once:true}));
      $('voice-recording').dataset.state='recording';label(active.analyser?'Recording':'Recording (waveform unavailable)');
      active.timer=setInterval(()=>tick(active),100);callbacks?.status('Recording. Stop when you are ready to listen back.');changed();return true;
    }catch(error){
      release(active);if(session!==active)return false;session=null;forget();
      const message=error.name==='NotAllowedError'?'Microphone access was denied. Allow it in your browser settings or keep typing.':error.name==='NotFoundError'?'No microphone is available. Connect one or keep typing.':'Recording could not start. Check microphone permissions or keep typing.';
      callbacks?.status(message);changed();return false;
    }
  }
  function init(handlers){
    callbacks=handlers;
    const svg=$('voice-waveform');
    bars=Array.from({length:40},(_,index)=>{const bar=document.createElementNS('http://www.w3.org/2000/svg','line');bar.setAttribute('x1',String(4+index*8));bar.setAttribute('x2',String(4+index*8));svg.insertBefore(bar,$('voice-playhead'));return bar;});
    $('voice-record-stop').addEventListener('click',()=>finish());
    $('voice-discard').addEventListener('click',()=>{callbacks?.discardClip?.();clear();callbacks.finished();callbacks.status('Recording deleted. Your transcript is still editable.');$('voice-input').focus();});
    $('voice-replay').addEventListener('click',async()=>{
      if(!clipUrl)return;
      if(!audio().paused){pause();return;}
      callbacks.beforePlay();if(audio().ended||audio().currentTime>=duration)audio().currentTime=0;
      try{await audio().play();}catch{callbacks.status('Playback could not start. Try again or check your audio device.');}
    });
    $('voice-seek').addEventListener('input',()=>{if(clipUrl){try{audio().currentTime=Math.min(duration,Math.max(0,Number($('voice-seek').value)||0));playback();}catch{callbacks.status('This browser cannot seek this recording yet. Try playing it first.');}}});
    for(const event of ['timeupdate','play','pause','ended','loadedmetadata'])audio().addEventListener(event,()=>{
      if(!clipUrl)return;
      if(event==='loadedmetadata'&&Number.isFinite(audio().duration)&&audio().duration>0){duration=audio().duration;$('voice-seek').max=String(duration);}
      playback();
    });
    audio().addEventListener('error',()=>{if(clipUrl)callbacks.status('Your browser could not play this recording. Try another supported browser.');});
    window.addEventListener('pagehide',clear);
  }
  return {init,start,finish,clear,pause,busy,supported,reserve:()=>$('voice-recording').hidden?0:$('voice-recording').offsetHeight};
})();
