'use strict';
window.CollectiveExplorer=(()=>{
  let roster=null,handlers=null,selected=null,mode='map';
  const $=id=>document.getElementById(id);
  const el=(tag,cls,text)=>{const node=document.createElement(tag);if(cls)node.className=cls;if(text!==undefined)node.textContent=text;return node;};
  const action=(label,callback,cls)=>{const node=el('button',cls,label);node.type='button';node.addEventListener('click',callback);return node;};
  function setMode(value){mode=value;const search=!!$('agent-search').value.trim();$('organization-explorer').hidden=mode!=='map'||search;$('department-grid').classList.toggle('d-none',mode!=='directory'||search);document.querySelectorAll('[data-organization-mode]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.organizationMode===mode)));}
  function selectDepartment(id){
    const department=roster.departments.find(item=>item.id===id);if(!department)return;selected=id;$('agent-search').value='';$('search-results').classList.add('d-none');setMode('map');
    document.querySelectorAll('.organization-node').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.department===id)));
    const panel=$('organization-details');panel.dataset.department=id;
    const icon=el('span','explorer-emblem');icon.append(window.CollectiveMissionUI.icon(id));
    const members=roster.agents.filter(agent=>agent.department===id),head=members.find(agent=>agent.role==='department_lead');
    panel.replaceChildren(icon,el('p','section-kicker','DEPARTMENT'),el('h2','',department.name),el('p','explorer-charter',department.charter));
    if(head){const lead=action('',()=>handlers.showAgent(head.id),'explorer-head');lead.append(el('span','mini-label','DEPARTMENT HEAD'),el('strong','',head.name),el('span','', 'View role ↗'));panel.append(lead);}
    const employees=members.filter(agent=>agent.role!=='department_lead'),list=el('div','explorer-employees');
    panel.append(el('p','explorer-reporting',`${employees.length} employees · report to their department head`));
    for(const agent of employees){const row=action('',()=>handlers.showAgent(agent.id),'explorer-employee');row.append(el('span','',agent.name),el('small','',agent.specialty?.replaceAll('_',' ')||agent.role.replaceAll('_',' ')));list.append(row);}
    panel.append(list);
  }
  function init(value,callbacks){
    roster=value;handlers=callbacks;
    document.querySelectorAll('[data-organization-mode]').forEach(button=>button.addEventListener('click',()=>setMode(button.dataset.organizationMode)));
    const map=$('organization-network');map.replaceChildren();const ns='http://www.w3.org/2000/svg',lines=document.createElementNS(ns,'svg');lines.setAttribute('viewBox','0 0 440 430');lines.setAttribute('aria-hidden','true');lines.classList.add('organization-lines');map.append(lines);
    const director=roster.agents.find(agent=>agent.role==='mission_director');
    const center=action('Mission Director',()=>director&&handlers.showAgent(director.id),'organization-director');center.append(el('span','','View role ↗'));map.append(center);
    roster.departments.forEach((department,index)=>{
      const angle=index/roster.departments.length*Math.PI*2-Math.PI/2,x=220+Math.cos(angle)*167,y=215+Math.sin(angle)*158;
      const line=document.createElementNS(ns,'line');for(const [name,value] of Object.entries({x1:220,y1:215,x2:x,y2:y}))line.setAttribute(name,value);lines.append(line);
      const button=action('',()=>selectDepartment(department.id),'organization-node');button.dataset.department=department.id;button.style.setProperty('--node-x',x/440*100+'%');button.style.setProperty('--node-y',y/430*100+'%');
      button.setAttribute('aria-label',`Explore ${department.name}, ${department.count} agents`);button.setAttribute('aria-pressed','false');button.append(window.CollectiveMissionUI.icon(department.id),el('span','',department.name.split(' & ')[0]));map.append(button);
    });
    setMode('map');selectDepartment(selected||'engineering');
  }
  function search(){setMode(mode);}
  return {init,selectDepartment,search};
})();
