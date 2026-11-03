'use strict';

// Rendering only: original messages/files and execution evidence remain unchanged.
function markdownFragment(source){
  const fallback=()=>{const text=document.createElement('p');text.className='markdown-fallback';text.textContent=source;return text;};
  if(!globalThis.marked||!globalThis.DOMPurify)return fallback();
  try{
    const escape=text=>String(text).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    const renderer=new marked.Renderer();
    renderer.html=({text})=>escape(text);
    renderer.image=({text})=>escape(text||'Image');
    const html=marked.parse(String(source),{renderer,gfm:true,breaks:true,async:false});
    const fragment=DOMPurify.sanitize(html,{RETURN_DOM_FRAGMENT:true,
      ALLOWED_TAGS:['p','br','hr','strong','em','del','h1','h2','h3','h4','h5','h6','ul','ol','li','pre','code','blockquote','table','thead','tbody','tr','th','td','a'],
      ALLOWED_ATTR:['href','title','start'],ALLOW_DATA_ATTR:false,ALLOW_ARIA_ATTR:false});
    for(const link of fragment.querySelectorAll('a')){
      let safe=false;
      try{safe=['https:','http:','mailto:'].includes(new URL(link.getAttribute('href')).protocol);}catch{}
      if(safe){link.target='_blank';link.rel='noopener noreferrer';}
      else link.removeAttribute('href');
    }
    for(const table of fragment.querySelectorAll('table')){
      const scroll=document.createElement('div');scroll.className='markdown-table';
      table.replaceWith(scroll);scroll.append(table);
    }
    return fragment;
  }catch{return fallback();}
}
