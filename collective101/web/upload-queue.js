'use strict';
// Progress is measured by XHR. Retry is explicit; files remain only in memory until uploaded.
window.CollectiveUploads=(()=>{
  const $=id=>document.getElementById(id),t=text=>window.CollectivePreferences?.t(text)||text;
  let callbacks,jobs=[],running=null,epoch=0,counter=0;
  const active=job=>['queued','reading','uploading','checking'].includes(job.state);
  const element=(tag,cls,text)=>{const node=document.createElement(tag);node.className=cls;if(text!==undefined)node.textContent=text;return node;};
  function changed(){draw();callbacks.changed();}
  function cancel(job){job.state='cancelled';job.reader?.abort();job.xhr?.abort();changed();}
  function draw(){
    const root=$('upload-queue');root.hidden=!jobs.length;
    for(const node of [...root.children])if(!jobs.some(job=>job.id===node.dataset.uploadId))node.remove();
    for(const job of jobs){
      let row=[...root.children].find(node=>node.dataset.uploadId===job.id);
      if(!row){row=element('div','upload-row');row.dataset.uploadId=job.id;row.setAttribute('role','listitem');
        const copy=element('div','upload-copy');copy.append(element('strong','upload-name',job.file.name),element('small','upload-status'));
        const progress=element('progress','upload-progress');progress.max=100;progress.setAttribute('aria-label','Upload '+job.file.name);
        row.append(copy,progress,element('div','upload-actions'));root.append(row);
      }
      const labels={queued:'Waiting',reading:'Reading file',uploading:'Uploading',checking:'Checking file',cancelled:'Cancelled',failed:'Upload failed'};
      row.querySelector('.upload-status').textContent=Math.max(1,Math.round(job.file.size/1024))+' KiB · '+t(labels[job.state])+(job.state==='uploading'&&job.percent!==null?' '+job.percent+'%':'')+(job.error?' · '+job.error:'');
      const progress=row.querySelector('progress');progress.hidden=!active(job);
      if(job.state==='uploading'&&job.percent!==null)progress.value=job.percent;else progress.removeAttribute('value');
      if(row.dataset.state!==job.state){const restore=row.contains(document.activeElement);row.dataset.state=job.state;
        const actions=row.querySelector('.upload-actions');actions.replaceChildren();
        const button=(label,fn)=>{const control=element('button','',t(label));control.type='button';control.setAttribute('aria-label',t(label)+' '+job.file.name);control.addEventListener('click',fn);actions.append(control);};
        if(active(job))button('Cancel',()=>cancel(job));
        else{button('Retry',()=>{job.state='queued';job.error='';changed();run();});button('Remove',()=>{jobs=jobs.filter(item=>item!==job);changed();});}
        if(restore)actions.querySelector('button')?.focus();
      }
    }
  }
  function read(job){return new Promise((resolve,reject)=>{
    const reader=new FileReader();job.reader=reader;reader.onload=()=>resolve(String(reader.result).split(',')[1]);
    reader.onerror=()=>reject(new Error('Could not read this file.'));reader.onabort=()=>reject(new DOMException('Upload cancelled','AbortError'));reader.readAsDataURL(job.file);
  });}
  function transfer(job,data){return new Promise((resolve,reject)=>{
    const xhr=new XMLHttpRequest();job.xhr=xhr;
    xhr.upload.onprogress=event=>{if(job.state==='cancelled')return;job.percent=event.lengthComputable?Math.min(100,Math.round(event.loaded/event.total*100)):null;changed();};
    xhr.upload.onload=()=>{if(job.state==='cancelled')return;job.state='checking';changed();};
    xhr.open('POST','/api/attachments');xhr.timeout=45000;xhr.setRequestHeader('Content-Type','application/json');xhr.setRequestHeader('X-Console-Token',callbacks.token());
    xhr.onload=()=>{let result;try{result=JSON.parse(xhr.responseText);}catch{return reject(new Error('The upload response was incomplete. Try again.'));}
      if(xhr.status===401)callbacks.expired();if(xhr.status<200||xhr.status>=300)return reject(new Error(result.error||'Upload failed. Try again.'));resolve(result);
    };
    xhr.onerror=()=>reject(new Error('Connection lost. Try again.'));xhr.ontimeout=()=>reject(new Error('Upload timed out. Try again.'));
    xhr.onabort=()=>reject(new DOMException('Upload cancelled','AbortError'));xhr.send(JSON.stringify({name:job.file.name,relative_path:job.relativePath||undefined,data}));
  });}
  async function drain(){
    const version=epoch;
    for(const job of jobs){
      if(version!==epoch)break;if(job.state!=='queued')continue;
      try{
        job.state='reading';changed();if(/^audio\//.test(job.file.type)||/\.(wav|mp3|m4a|ogg)$/i.test(job.file.name))job.file=await normalizeAudio(job.file);const data=await read(job);
        if(version!==epoch||job.state==='cancelled')continue;
        job.state='uploading';job.percent=null;changed();const item=await transfer(job,data);
        if(version!==epoch||job.state==='cancelled'){await callbacks.remove(item.id).catch(()=>{});continue;}
        callbacks.added(item,job.file,job.source);jobs=jobs.filter(value=>value!==job);callbacks.status(t('File attached.'));changed();
      }catch(error){
        if(version!==epoch)break;
        if(error.name==='AbortError')job.state='cancelled';else{job.state='failed';job.error=error.message;callbacks.status(error.message);}
        changed();
      }finally{job.reader=null;job.xhr=null;}
    }
  }
  function run(){if(running)return running;running=drain().finally(()=>{running=null;changed();if(jobs.some(job=>job.state==='queued'))run();});return running;}
  async function upload(files,source=null){
    const provided=[...files],selected=provided.filter(file=>{const path=file.webkitRelativePath||'';return !path||!path.split('/').some(part=>part.startsWith('.')&&!['.env.example','.gitignore','.dockerignore'].includes(part)||/^(node_modules|__pycache__|work|dist|\.venv)$/i.test(part))&&!/\.(db|sqlite3?|pyc|pem|key)$/i.test(file.name);});if(selected.length<provided.length)callbacks.status('Skipped private or cached folder files.');if(!selected.length)return;
    if(selected.some(file=>file.size>25*1024*1024)||selected.reduce((n,file)=>n+file.size,0)+jobs.reduce((n,job)=>n+job.file.size,0)+callbacks.bytes()>50*1024*1024){callbacks.status('Use files up to 25 MiB each, with 50 MiB total per message.');return;}
    jobs.push(...selected.map(file=>({id:String(++counter),file,source,relativePath:file.webkitRelativePath||'',state:'queued',percent:null,error:''})));changed();await run();
  }
  function cancelSource(source){for(const job of jobs.filter(job=>job.source===source))cancel(job);jobs=jobs.filter(job=>job.source!==source);changed();}
  function clear(){epoch++;for(const job of jobs){job.reader?.abort();job.xhr?.abort();}jobs=[];changed();}
  return {init:handlers=>{callbacks=handlers;window.addEventListener('pagehide',clear);},upload,cancelSource,clear,busy:()=>jobs.length>0,working:()=>jobs.some(active),reserve:()=>$('upload-queue').hidden?0:$('upload-queue').offsetHeight};
})();
