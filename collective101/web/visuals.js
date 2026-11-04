'use strict';
// Original, bundled SVG marks: no external icon/font/image requests.
window.CollectiveVisuals=(()=>{
  const ns='http://www.w3.org/2000/svg';
  function svg(parts){const root=document.createElementNS(ns,'svg');for(const [name,value] of Object.entries({viewBox:'0 0 32 32',fill:'none','aria-hidden':'true'}))root.setAttribute(name,value);for(const [tag,attrs] of parts){const node=document.createElementNS(ns,tag);for(const [name,value] of Object.entries(attrs))node.setAttribute(name,value);root.append(node);}return root;}
  const path=(d,color,width=2.5)=>['path',{d,stroke:color,'stroke-width':width,'stroke-linecap':'round','stroke-linejoin':'round'}];
  function serviceIcon(id){
    const marks={
      gmail:[path('M4 25V9l12 9L28 9v16','#4285f4',4),path('M4 8l12 10L28 8','#ea4335',4),path('M28 13v12','#34a853',4)],
      slack:[path('M11 4v12M4 11h12','#36c5f0',5),path('M21 4v12M16 11h12','#2eb67d',5),path('M21 16v12M16 21h12','#ecb22e',5),path('M11 16v12M4 21h12','#e01e5a',5)],
      canva:[['circle',{cx:16,cy:16,r:13,fill:'#10a8ac'}],path('m10 21 2-7 9-5-5 9Z','#fff',1.8)],
      github:[path('M10 5v15a6 6 0 0 0 6 6h6M10 14h6a6 6 0 0 0 6-6V5','currentColor'),['circle',{cx:10,cy:5,r:3,fill:'currentColor'}],['circle',{cx:22,cy:5,r:3,fill:'currentColor'}],['circle',{cx:22,cy:26,r:3,fill:'currentColor'}]],
      drive:[['path',{d:'m12 3-11 20h9L21 3Z',fill:'#34a853'}],['path',{d:'m21 3 11 20h-9L12 3Z',fill:'#fbbc04'}],['path',{d:'M1 23h31l-5 7H6Z',fill:'#4285f4'}]],
      calendar:[['rect',{x:3,y:5,width:26,height:24,rx:4,fill:'#4285f4'}],path('M3 12h26M10 2v6M22 2v6','#cce0ff',2),path('M9 18h4M19 18h4M9 23h4M19 23h4','#fff',2)],
      meta:[path('M3 22C6 2 12 5 17 16s9 16 12 3S23 2 17 13 6 32 3 22','#4a9eff',2.7)],
      brave:[path('m16 3 12 5v10c0 6-12 12-12 12S4 24 4 18V8Z','#e87b3c',2),['circle',{cx:15,cy:14,r:5,stroke:'#e87b3c','stroke-width':2}],path('m19 18 5 5','#e87b3c',2)],
      mcp:[path('m5 17 9-9a6 6 0 0 1 8 8l-9 9M8 20l9-9M20 23l6 6','currentColor',2.8)],
    };return svg(marks[id]||marks.mcp);
  }
  function empty(kind,title,copy){
    const box=document.createElement('div');box.className='visual-empty';
    const illustration=svg([['ellipse',{cx:16,cy:16,rx:14,ry:7,stroke:'currentColor',transform:'rotate(-30 16 16)'}],['ellipse',{cx:16,cy:16,rx:14,ry:7,stroke:'currentColor',transform:'rotate(30 16 16)'}],['circle',{cx:16,cy:16,r:3,fill:'currentColor'}],['circle',{cx:26,cy:7,r:2,fill:'currentColor'}]]);
    illustration.classList.add('empty-illustration','empty-'+kind);
    const heading=document.createElement('h2');heading.textContent=title;const text=document.createElement('p');text.textContent=copy;box.append(illustration,heading,text);return box;
  }
  return {serviceIcon,empty};
})();
