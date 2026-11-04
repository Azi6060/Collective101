'use strict';
window.CollectiveThumbnails=(()=>{
  let request=null,observer=null;const cache=new Map(),pending=new Map();
  function configure(callback){request=callback;}
  function attach(sample,file,chat){
    if(!request||!/\.html?$/i.test(file.path))return;
    const key=JSON.stringify([chat.id,file.path,chat.workspace.files.map(item=>[item.path,item.sha256])]);
    const button=document.createElement('button');button.type='button';button.className='thumbnail-request';button.textContent='Show page thumbnail';sample.append(button);
    const status=document.createElement('span');status.className='thumbnail-status';status.setAttribute('role','status');sample.append(status);
    async function capture(){
      if(button.disabled)return;button.disabled=true;status.textContent='Capturing saved page…';
      try{
        let result=cache.get(key);if(!result){result=await request(chat.id,file.path);cache.set(key,result);while(cache.size>8)cache.delete(cache.keys().next().value);}
        if(!sample.isConnected)return;
        const image=document.createElement('img');image.alt=`Static preview of ${file.path}`;image.width=result.width;image.height=result.height;image.src=result.image;image.className='saved-page-thumbnail';image.decoding='async';
        image.addEventListener('error',()=>{image.remove();sample.classList.remove('has-thumbnail');status.textContent='Thumbnail unavailable. Open website instead.';button.disabled=false;});
        sample.append(image);sample.classList.add('has-thumbnail');status.textContent='Static page preview';button.hidden=true;
      }catch{if(sample.isConnected){status.textContent='Thumbnail unavailable. Open website instead.';button.disabled=false;}}
    }
    button.addEventListener('click',capture);
    // Wait for a stable outcome so successive saved drafts cannot race captures.
    // During work the operator can still explicitly capture the current page.
    if(window.IntersectionObserver&&['reviewed','answered','blocked','error'].includes(chat.status)&&!sample.closest('.deliverable-grid').querySelector('[data-auto-thumbnail]')){
      if(!observer)observer=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting||!entry.target.isConnected){const start=pending.get(entry.target);pending.delete(entry.target);observer.unobserve(entry.target);if(entry.isIntersecting&&entry.target.isConnected)start?.();}}));
      for(const target of pending.keys())if(!target.isConnected){observer.unobserve(target);pending.delete(target);}
      sample.dataset.autoThumbnail='true';pending.set(sample,capture);observer.observe(sample);
    }
  }
  return {configure,attach};
})();
