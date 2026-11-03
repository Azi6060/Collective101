// Read-only DOM audit; serialized by the Playwright MCP client. No storage access.
export function auditTextContrast() {
  const color = value => {
    const parts=value.match(/[\d.]+/g)?.map(Number)||[];
    return parts.length>=3?[parts[0],parts[1],parts[2],parts[3]??1]:[0,0,0,0];
  };
  const over=(front,back)=>{
    const alpha=front[3]+back[3]*(1-front[3]);
    return alpha?[...front.slice(0,3).map((channel,i)=>(channel*front[3]+back[i]*back[3]*(1-front[3]))/alpha),alpha]:[0,0,0,0];
  };
  const background = element => {
    const layers=[];for(let node=element;node;node=node.parentElement)layers.push(color(getComputedStyle(node).backgroundColor));
    return layers.reverse().reduce((back,front)=>over(front,back),[255,255,255,1]);
  };
  const luminance = rgba => rgba.slice(0,3).map(channel=>channel/255).map(channel=>channel<=.04045?channel/12.92:((channel+.055)/1.055)**2.4).reduce((sum,channel,i)=>sum+channel*[.2126,.7152,.0722][i],0);
  const contrast = (front,back) => {const a=luminance(over(front,back)),b=luminance(back);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);};
  const failures=[];let checked=0;
  const scope=[document.querySelector('.sidebar'),document.querySelector('.topbar'),document.querySelector('.view:not(.d-none)')];
  for(const section of scope)for(const element of [section,...section.querySelectorAll('*')]) {
    if(!element.getClientRects().length||element.closest('[aria-hidden="true"],script,style,svg,[disabled]'))continue;
    if(![...element.childNodes].some(node=>node.nodeType===Node.TEXT_NODE&&node.textContent.trim()))continue;
    const style=getComputedStyle(element);
    // Hidden clipping utilities (e.g. skip link until focused) aren't visible text.
    if(style.visibility==='hidden'||style.clip==='rect(0px, 0px, 0px, 0px)')continue;
    const fontSize=parseFloat(style.fontSize),large=fontSize>=24||(fontSize>=18.66&&parseInt(style.fontWeight)>=700);
    const ratio=contrast(color(style.color),background(element)),required=large?3:4.5;
    checked++;
    if(ratio+.005<required)failures.push({text:element.textContent.trim().slice(0,65),selector:element.id||element.className,ratio:Number(ratio.toFixed(2)),required});
  }
  // Placeholders are visible instructional text too, not disabled controls.
  for(const element of document.querySelectorAll('input[placeholder],textarea[placeholder]')) {
    if(!element.getClientRects().length||element.value)continue;
    const style=getComputedStyle(element,'::placeholder'),front=color(style.color);front[3]*=Number(style.opacity);
    const ratio=contrast(front,background(element));checked++;
    if(ratio+.005<4.5)failures.push({text:'Placeholder: '+element.placeholder,selector:element.id,ratio:Number(ratio.toFixed(2)),required:4.5});
  }
  return {checked,failures};
}
