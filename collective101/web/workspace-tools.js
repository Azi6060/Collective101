'use strict';
// Saved-work discovery and presentation controls. No model calls or synthetic activity.
window.CollectiveWorkspaceTools=(()=>{
  const $=id=>document.getElementById(id),el=(tag,cls,text)=>{const node=document.createElement(tag);node.className=cls;if(text!==undefined)node.textContent=text;return node;};
  let callbacks,rows=[],current=null,query='',results=null,timer=null,sequence=0,signature='',renameId=null,opener=null,toastTimer=null;
  const t=text=>window.CollectivePreferences?.t(text)||text;
  function toast(message){clearTimeout(toastTimer);$('workspace-toast-message').textContent=message;$('workspace-toast').hidden=!message;if(message)toastTimer=setTimeout(()=>{$('workspace-toast').hidden=true;},4000);}
  function draw(){
    const items=query?(results||[]):rows;
    const next=JSON.stringify([items,current,query,!!query&&results===null,document.documentElement.lang]);if(next===signature)return;signature=next;
    const list=$('recent-missions'),focused=list.contains(document.activeElement)?document.activeElement.dataset.chatId:null;
    list.replaceChildren(...items.map(chat=>{
      const button=el('button','');button.type='button';button.dataset.chatId=chat.id;button.title=chat.title;
      button.append(el('strong','history-title',chat.title));
      if(chat.matches?.length)button.append(el('small','history-match',chat.matches.join(' · ')));
      button.classList.toggle('selected',chat.id===current);if(chat.id===current)button.setAttribute('aria-current','true');
      button.addEventListener('click',()=>callbacks.selectChat(chat.id,chat.matches?.length?query:''));return button;
    }));
    if(!items.length&&(!query||results!==null))list.append(el('p','history-empty',t(query?'No matching chats or files.':'No chats started yet')));
    if(focused)[...list.querySelectorAll('button')].find(button=>button.dataset.chatId===focused)?.focus({preventScroll:true});
  }
  async function search(){
    const version=++sequence;clearTimeout(timer);query=$('history-search').value.trim();results=null;
    if(!query){$('history-search-status').textContent='';draw();return;}
    $('history-search-status').textContent=t('Searching saved work…');$('recent-missions').setAttribute('aria-busy','true');draw();
    try{const result=await callbacks.api('/api/search?q='+encodeURIComponent(query));if(version!==sequence)return;
      results=result.results;$('history-search-status').textContent=result.more_results?t('Showing the first 30 matching chats.'):
        t('Searches titles and filenames in your latest 100 chats.')+(result.metadata_limited?' '+t('File metadata limit reached.'): '');draw();
    }catch(error){if(version===sequence)$('history-search-status').textContent=error.message;}
    finally{if(version===sequence)$('recent-missions').removeAttribute('aria-busy');}
  }
  function render(chats,selected){rows=chats;current=selected;draw();$('rename-chat').disabled=!selected;}
  function closeRename(){if($('rename-dialog').close)$('rename-dialog').close();else $('rename-dialog').removeAttribute('open');if(opener?.isConnected)opener.focus();}
  function init(handlers){
    callbacks=handlers;
    $('history-search').addEventListener('input',()=>{clearTimeout(timer);sequence++;timer=setTimeout(search,200);});
    $('history-search').addEventListener('search',search);
    $('history-search').addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();search();}if(event.key==='ArrowDown'){$('recent-missions').querySelector('button')?.focus();event.preventDefault();}});
    $('rename-chat').addEventListener('click',()=>{
      const chat=callbacks.chat();if(!chat)return;opener=document.activeElement;renameId=chat.id;
      $('rename-title').value=chat.title;$('rename-status').textContent='';
      if($('rename-dialog').showModal)$('rename-dialog').showModal();else $('rename-dialog').setAttribute('open','');$('rename-title').focus();$('rename-title').select();
    });
    $('rename-cancel').addEventListener('click',closeRename);
    $('rename-dialog').addEventListener('cancel',event=>{event.preventDefault();closeRename();});
    $('rename-dialog').addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();closeRename();}});
    $('rename-form').addEventListener('submit',async event=>{
      event.preventDefault();$('rename-save').disabled=true;
      try{const result=await callbacks.api('/api/chats/'+renameId+'/rename',{title:$('rename-title').value.trim()});await callbacks.renamed(result);closeRename();toast(t('Chat renamed.'));if(query)search();}
      catch(error){$('rename-status').textContent=error.message;}finally{$('rename-save').disabled=false;}
    });
    $('dismiss-toast').addEventListener('click',()=>toast(''));
    window.addEventListener('collective-preferences-change',()=>{signature='';draw();toast(t(window.CollectivePreferences?.persistent()?'Preferences saved.':'Saved for this visit only. Browser storage is unavailable.'));});
  }
  return {init,render,toast,search};
})();
