'use strict';
// Membership in one local shared workspace; credentials never enter browser storage.
window.CollectiveAccounts = (()=>{
  const $=id=>document.getElementById(id);
  let callbacks,session={configured:false,user:null},mode='signin',opener=null;
  const locked=()=>session.configured&&!session.user;
  function closeMenu(focus=false){const menu=$('account-menu');menu.open=false;if(focus)menu.querySelector('summary').focus();}
  function render(){
    const user=session.user;
    $('account-avatar').textContent=user?user.name.trim().split(/\s+/).slice(0,2).map(word=>Array.from(word)[0]).join('').toUpperCase():'';
    $('account-avatar').classList.toggle('has-user',!!user);
    $('account-menu-name').textContent=user?user.name.split(/\s+/)[0]:'Account';
    $('account-menu-summary').setAttribute('aria-label',user?'Account: '+user.name:'Account: Guest');
    $('account-name').textContent=user?user.name:'Welcome to your workspace';
    $('account-identity').textContent=user?'@'+user.username+' · '+(user.role==='owner'?'Workspace owner':'Member'):'Guest';
    $('account-menu-guest').hidden=!!user;$('account-menu-member').hidden=!user;
    $('account-settings-guest').hidden=!!user;$('account-settings-member').hidden=!user;
    $('account-settings-copy').textContent=user?'Manage your profile on this computer. Workspace chats, tools and files are shared with its members.':session.configured?'Sign in with your local account, or use an invitation from the workspace owner.':'Create the first account to protect this local shared workspace, or keep exploring as a guest.';
    $('account-invites').hidden=user?.role!=='owner';
    if(user){$('profile-name').value=user.name;$('profile-username').textContent='@'+user.username;$('profile-role').textContent=user.role==='owner'?'Workspace owner':'Member';}
    document.querySelectorAll('[data-account-open]').forEach(button=>button.disabled=false);
  }
  function setMode(value){
    mode=value;
    const signup=mode==='signup';
    for(const name of ['signin','signup']){const tab=$('account-tab-'+name);tab.setAttribute('aria-selected',String(name===mode));tab.tabIndex=name===mode?0:-1;}
    $('account-title').textContent=signup?'Make yourself at home.':'Welcome back.';
    $('account-auth-copy').textContent=signup?(session.configured?'Join this shared workspace with an owner invitation.':'Your first local account becomes the workspace owner.'):'Sign in to your local Collective101 workspace.';
    $('signup-name-row').hidden=!signup;$('signup-invite-row').hidden=!(signup&&session.configured);
    $('signup-name').required=signup;$('signup-name').disabled=!signup;
    $('signup-invite').required=signup&&session.configured;$('signup-invite').disabled=!(signup&&session.configured);
    $('account-password').autocomplete=signup?'new-password':'current-password';
    $('account-auth-submit').textContent=signup?'Create account':'Sign in';
    $('account-auth-form').setAttribute('aria-labelledby','account-tab-'+mode);
    $('account-auth-status').textContent='';
  }
  function open(value='signin'){
    opener=document.activeElement;closeMenu();setMode(value);
    if($('account-dialog').showModal)$('account-dialog').showModal();else $('account-dialog').setAttribute('open','');
    (value==='signup'?$('signup-name'):$('account-username')).focus();
  }
  function close(){
    if($('account-dialog').close)$('account-dialog').close();else $('account-dialog').removeAttribute('open');
    $('account-auth-form').reset();$('account-auth-status').textContent='';
    if(opener?.isConnected)opener.focus();
  }
  async function load(){session=await callbacks.api('/api/account/me');render();return session;}
  function init(handlers){
    callbacks=handlers;
    window.addEventListener('pageshow',event=>{if(event.persisted)callbacks.revalidate?.();});
    $('close-account').addEventListener('click',close);
    $('account-dialog').addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();close();}});
    $('account-dialog').addEventListener('cancel',event=>{event.preventDefault();close();});
    for(const name of ['signin','signup'])$('account-tab-'+name).addEventListener('click',()=>setMode(name));
    $('account-tabs').addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();setMode(event.key==='Home'?'signin':event.key==='End'?'signup':mode==='signin'?'signup':'signin');$('account-tab-'+mode).focus();});
    document.querySelectorAll('[data-account-open]').forEach(button=>button.addEventListener('click',()=>open(button.dataset.accountOpen)));
    document.addEventListener('click',event=>{if(!$('account-menu').contains(event.target))closeMenu();});
    document.addEventListener('keydown',event=>{if(event.key==='Escape'&&$('account-menu').open){event.preventDefault();closeMenu(true);}});
    $('account-manage').addEventListener('click',()=>{closeMenu();callbacks.openSettings();$('account-settings').scrollIntoView({block:'start'});$('account-settings').focus({preventScroll:true});});
    $('account-auth-form').addEventListener('submit',async event=>{
      event.preventDefault();$('account-auth-submit').disabled=true;$('account-auth-status').textContent='';
      try{
        session=await callbacks.api('/api/account/'+mode,{username:$('account-username').value.trim(),password:$('account-password').value,...(mode==='signup'?{name:$('signup-name').value.trim(),invite:$('signup-invite').value.trim()}:{})});
        $('account-auth-form').reset();render();close();callbacks.signedIn();
      }catch(error){$('account-auth-status').textContent=error.message;}finally{$('account-auth-submit').disabled=false;}
    });
    document.querySelectorAll('[data-account-signout]').forEach(button=>button.addEventListener('click',async()=>{
      button.disabled=true;try{await callbacks.api('/api/account/signout',{});callbacks.signedOut();}catch(error){$('account-settings-status').textContent=error.message;button.disabled=false;}
    }));
    $('profile-form').addEventListener('submit',async event=>{
      event.preventDefault();$('profile-save').disabled=true;
      try{session=await callbacks.api('/api/account/profile',{name:$('profile-name').value.trim()});render();$('account-settings-status').textContent='Profile updated.';}catch(error){$('account-settings-status').textContent=error.message;}finally{$('profile-save').disabled=false;}
    });
    $('password-form').addEventListener('submit',async event=>{
      event.preventDefault();$('password-save').disabled=true;
      try{session=await callbacks.api('/api/account/password',{current_password:$('current-password').value,password:$('new-password').value});$('password-form').reset();$('account-settings-status').textContent='Password updated. Other sessions are now signed out.';}catch(error){$('account-settings-status').textContent=error.message;}finally{$('password-save').disabled=false;}
    });
    $('create-invite').addEventListener('click',async()=>{
      $('create-invite').disabled=true;
      try{const result=await callbacks.api('/api/account/invite',{});$('invite-code').textContent=result.code;$('invite-result').hidden=false;$('account-settings-status').textContent='Invitation created. One use, valid for 24 hours.';}catch(error){$('account-settings-status').textContent=error.message;}finally{$('create-invite').disabled=false;}
    });
    $('copy-invite').addEventListener('click',async()=>{try{await navigator.clipboard.writeText($('invite-code').textContent);$('account-settings-status').textContent='Invitation copied.';}catch{$('account-settings-status').textContent='Select and copy the invitation code shown above.';}});
  }
  function expire(){if(!locked()){session={configured:true,user:null};callbacks.expired();}}
  return {init,load,open,locked,expire,user:()=>session.user};
})();
