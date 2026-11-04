'use strict';
// Presentation of saved state only. No model calls, simulated metrics or permission changes.
window.CollectiveDashboard = (() => {
  let callbacks=null,signature='',rosterSignature='',emptyState=[];
  const $=id=>document.getElementById(id);
  const t=text=>window.CollectivePreferences?.t(text)||text;
  const el=(tag,cls,text)=>{const node=document.createElement(tag);if(cls)node.className=cls;if(text!==undefined)node.textContent=text;return node;};
  const needsInput=new Set(['clarifying','needs_input','needs_approval','paused','interrupted']);
  const statuses={intake:'Considering',running:'In progress',clarifying:'Your guidance',needs_input:'Your guidance',needs_approval:'Your approval',paused:'Paused',interrupted:'Resume when ready',reviewed:'Reviewed',answered:'Answered',blocked:'Needs attention',error:'Needs attention'};
  function savedDate(value) {
    const date=new Date(value);return Number.isNaN(date.getTime())?t('Saved chat'):new Intl.DateTimeFormat(document.documentElement.lang,{month:'short',day:'numeric'}).format(date);
  }
  function init(handlers) {
    callbacks=handlers;
    initAmbientMotion();
    emptyState=[...$('mission-list').childNodes];
    $('dashboard-mission').addEventListener('submit',event=>{
      event.preventDefault();const draft=$('dashboard-input').value.trim();if(!draft)return;
      callbacks.newMission();$('mission-input').value=draft;callbacks.growComposer();$('mission-input').focus();
    });
    $('organization-map').addEventListener('click',()=>callbacks.navigate('organization'));
  }
  function initAmbientMotion() {
    const root=document.documentElement;
    const reduced=window.matchMedia?.('(prefers-reduced-motion: reduce)');
    function update(){
      const limited=root.dataset.reduceMotion==='true'||!!reduced?.matches;
      root.dataset.ambientMotion=limited?'reduced':document.hidden?'hidden':'running';
    }
    reduced?.addEventListener?.('change',update);
    window.addEventListener('collective-preferences-change',update);
    document.addEventListener('visibilitychange',update);
    if(window.IntersectionObserver){const observer=new IntersectionObserver(entries=>entries.forEach(entry=>entry.target.classList.toggle('motion-offscreen',!entry.isIntersecting)));observer.observe(document.querySelector('.dashboard-hero'));}
    update();
  }
  function drawRoster(roster) {
    if(!roster||JSON.stringify(roster.departments)===rosterSignature)return;
    rosterSignature=JSON.stringify(roster.departments);
    $('dashboard-agent-count').textContent=String(roster.agents.length);
    $('dashboard-department-count').textContent=String(roster.departments.length);
    const svg=$('constellation'),ns='http://www.w3.org/2000/svg';svg.replaceChildren();
    function shape(tag,attributes,text,parent=svg){const node=document.createElementNS(ns,tag);for(const [name,value] of Object.entries(attributes))node.setAttribute(name,String(value));if(text!==undefined)node.textContent=text;parent.append(node);return node;}
    shape('ellipse',{cx:220,cy:185,rx:163,ry:70,transform:'rotate(-28 220 185)',class:'constellation-orbit'});
    shape('ellipse',{cx:220,cy:185,rx:163,ry:70,transform:'rotate(28 220 185)',class:'constellation-orbit'});
    shape('circle',{cx:220,cy:185,r:126,class:'constellation-orbit','stroke-dasharray':'2 7'});
    // Decorative introduction, never a signal that agents or missions are active.
    // The whole sequence settles in under five seconds and has a static fallback.
    const sweep=shape('g',{class:'constellation-sweep'});
    shape('circle',{cx:220,cy:185,r:147,class:'constellation-sweep-track','stroke-dasharray':'85 840'},undefined,sweep);
    shape('circle',{cx:367,cy:185,r:3,class:'constellation-spark'},undefined,sweep);
    // These ambient layers are decorative and never represent runtime activity.
    for(const [index,radius] of [152,171,107].entries()){
      const orbit=shape('g',{class:'ambient-orbit ambient-orbit-'+index});
      shape('circle',{cx:220,cy:185,r:radius,class:'ambient-track','stroke-dasharray':index===1?'2 20':'48 900'},undefined,orbit);
      for(let i=0;i<3;i++){const angle=i*Math.PI*2/3;shape('circle',{cx:220+Math.cos(angle)*radius,cy:185+Math.sin(angle)*radius,r:i===0?3.2:1.7,class:'ambient-light'},undefined,orbit);}
    }
    const halo=shape('g',{class:'ambient-halo'});shape('circle',{cx:220,cy:185,r:65,class:'ambient-halo-ring'},undefined,halo);
    const dust=shape('g',{class:'ambient-dust'});
    [[64,60],[340,46],[388,114],[50,260],[355,310],[125,328],[300,350],[90,142],[395,245],[180,27],[38,185],[280,68]].forEach(([x,y],i)=>shape('circle',{cx:x,cy:y,r:i%3===0?1.9:1,class:'ambient-star'},undefined,dust));
    for(const [index,department] of roster.departments.entries()) {
      const angle=(index/roster.departments.length)*Math.PI*2-Math.PI/2;
      const x=220+Math.cos(angle)*126,y=185+Math.sin(angle)*126;
      const entrance=shape('g',{class:'constellation-cluster'});
      entrance.style.setProperty('--cluster-delay',`${index*45}ms`);
      const cluster=shape('g',{class:'cluster-atmosphere'},undefined,entrance);
      cluster.style.setProperty('--float-delay',`${index*-.6}s`);
      shape('line',{x1:220,y1:185,x2:x,y2:y,class:'constellation-line'},undefined,entrance);
      const members=roster.agents.filter(agent=>agent.department===department.id&&agent.id!==department.id+'-001');
      members.forEach((member,i)=>{const a=angle+(i/Math.max(members.length,1))*Math.PI*2;const radius=24+(i%3)*5;shape('circle',{cx:x+Math.cos(a)*radius,cy:y+Math.sin(a)*radius,r:1.7+(i%2)*.5,class:'constellation-employee'},undefined,cluster);});
      shape('circle',{cx:x,cy:y,r:14,class:'constellation-head'},undefined,entrance);
      shape('text',{x,y:y+2.5,class:'constellation-code'},department.id==='assurance'?'VER':department.id.slice(0,3).toUpperCase(),entrance);
    }
    shape('circle',{cx:220,cy:185,r:51,class:'constellation-orbit'});
    shape('circle',{cx:220,cy:185,r:39,class:'constellation-core'});
    shape('text',{x:220,y:188,class:'constellation-brand'},'C');
    shape('text',{x:221.5,y:202,class:'constellation-number'},'101');
  }
  function render(state) {
    drawRoster(state.roster);
    const chats=state.chats||[],key=JSON.stringify([chats,document.documentElement.lang]);if(signature===key)return;signature=key;
    $('view-overview').classList.toggle('has-missions',chats.length>0);
    const waiting=chats.filter(chat=>needsInput.has(chat.status));
    $('metric-active').textContent=String(chats.filter(chat=>['running','intake'].includes(chat.status)).length);
    $('metric-attention').textContent=String(waiting.length);
    $('metric-reviewed').textContent=String(chats.filter(chat=>chat.status==='reviewed').length);
    $('metric-chats').textContent=String(chats.length);
    $('metric-runs').textContent=chats.length?t('In your recent history'):t('Your next idea starts here');
    const list=$('mission-list');
    const focusedChat=list.contains(document.activeElement)?document.activeElement.closest('[data-chat-id]')?.dataset.chatId:null;
    if(chats.length) {
      list.className='dashboard-mission-list';
      list.replaceChildren(...chats.slice(0,5).map(chat=>{
        const button=el('button','mission-list-item mission-card');button.type='button';
        button.dataset.chatId=chat.id;
        const top=el('span','mission-card-top'),kind=el('span','mission-card-kind');
        if(window.CollectiveMissionUI)kind.append(window.CollectiveMissionUI.icon(chat.run_id?'strategy':'communications'));
        kind.append(document.createTextNode(t(chat.run_id?'Mission':'Conversation')));
        const copy=el('span','mission-row-copy');copy.append(el('strong','',chat.title||t('Saved chat')));
        copy.firstChild.dir='auto';
        const status=el('span','state-pill '+chat.status,t(statuses[chat.status]||chat.status.replaceAll('_',' ')));
        top.append(kind,status);
        const actions={reviewed:'View result',clarifying:'Answer questions',needs_input:'Answer questions',needs_approval:'Review request',paused:'Continue',interrupted:'Continue',running:'Follow progress',intake:'Follow progress',blocked:'Review details',error:'Review details'};
        const footer=el('span','mission-card-footer'),next=el('span','mission-card-action',t(actions[chat.status]||'Open conversation'));
        const arrow=el('span','mission-row-arrow','↗');arrow.setAttribute('aria-hidden','true');
        next.append(arrow);footer.append(el('span','mission-card-date',savedDate(chat.created_at)),next);
        button.append(top,copy,footer);button.addEventListener('click',()=>callbacks.selectChat(chat.id));return button;
      }));
    }else{list.className='dashboard-empty';list.replaceChildren(...emptyState);}
    if(focusedChat)[...list.querySelectorAll('[data-chat-id]')].find(node=>node.dataset.chatId===focusedChat)?.focus({preventScroll:true});
    const attention=$('dashboard-attention');
    if(waiting.length)attention.replaceChildren(...waiting.slice(0,3).map(chat=>{
      const button=el('button','attention-item');button.type='button';button.append(el('span','',chat.title||t('Saved chat')),el('small','',t(statuses[chat.status])));button.addEventListener('click',()=>callbacks.selectChat(chat.id));return button;
    }));
    else attention.replaceChildren(el('p','dashboard-caught-up',t('You’re all caught up.')),el('p','text-secondary small',t('Missions waiting for your guidance will appear here.')));
  }
  return {init,render};
})();
