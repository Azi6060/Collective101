'use strict';
// Browser-only presentation preferences. Credentials and mission settings stay elsewhere.
window.CollectivePreferences = (() => {
  const defaults = {theme:'dark',language:'en',textSize:'default',reduceMotion:false};
  const key = 'collective101.preferences.v1';
  const media = window.matchMedia?.('(prefers-color-scheme: dark)');
  const messages = {
    'Overview':'Gambaran keseluruhan','Organization':'Organisasi','Mission chat':'Sembang misi',
    'Connectors':'Penyambung','Activity & evidence':'Aktiviti & bukti','Settings':'Tetapan',
    'Workspace':'Ruang kerja','YOUR WORKSPACE':'RUANG KERJA ANDA','RECENT MISSIONS':'MISI TERKINI',
    'Your missions will appear here.':'Misi anda akan dipaparkan di sini.',
    'Local workspace':'Ruang kerja setempat','Your organization. Your machine.':'Organisasi anda. Komputer anda.',
    'Workspace connected':'Ruang kerja disambungkan','Connection interrupted':'Sambungan terganggu',
    'Connecting':'Sedang menyambung','Offline':'Luar talian','Skip to content':'Langkau ke kandungan',
    'MISSION CONTROL':'PUSAT KAWALAN MISI','Good work starts with':'Kerja yang baik bermula dengan',
    'a clear mission.':'misi yang jelas.','Turn an ambitious request into coordinated, visible work.':'Tukarkan permintaan besar kepada kerja tersusun yang boleh dilihat.',
    'New mission':'Misi baharu','New chat':'Sembang baharu','Open chat':'Buka sembang',
    'REGISTERED AGENTS':'EJEN BERDAFTAR','DEPARTMENTS':'JABATAN','MISSION ACTIVITY':'AKTIVITI MISI',
    'EXECUTION HARNESS':'SISTEM PELAKSANAAN','across the organization':'di seluruh organisasi',
    '1 director · 10 heads · 90 employees':'1 pengarah · 10 ketua · 90 pekerja',
    'working together':'bekerjasama','Specialized roles. Shared objectives.':'Peranan khusus. Matlamat bersama.',
    'in progress':'sedang berjalan','No missions started yet':'Belum ada misi dimulakan',
    'Isolated JavaScript · recorded results':'JavaScript terasing · hasil direkodkan',
    'START WITH AN OUTCOME':'MULAKAN DENGAN HASIL','Head-led collaboration':'Kerjasama dipimpin ketua',
    'What should we work on?':'Apa yang patut kita usahakan?',
    'Describe a mission for your organization…':'Huraikan misi untuk organisasi anda…',
    'Build a website':'Bina laman web','Test JavaScript':'Uji JavaScript','Explore a decision':'Terokai keputusan',
    'Recent missions':'Misi terkini','A clear starting point.':'Titik permulaan yang jelas.',
    'Start your first mission to see departments, decisions, and deliverables here.':'Mulakan misi pertama untuk melihat jabatan, keputusan dan hasil kerja di sini.',
    'HOW WORK MOVES':'CARA KERJA BERJALAN','From intent to evidence.':'Daripada niat kepada bukti.',
    'Clarify the mission':'Jelaskan misi','Resolve the questions that matter.':'Selesaikan persoalan yang penting.',
    'Bring in the right heads':'Libatkan ketua yang sesuai','Departments propose useful work.':'Jabatan mencadangkan kerja yang berguna.',
    'Assign and execute':'Agih dan laksanakan','Employees work within their roles.':'Pekerja bekerja mengikut peranan.',
    'Review the evidence':'Semak bukti','Independent checks precede acceptance.':'Semakan bebas dibuat sebelum penerimaan.',
    'THE ORGANIZATION':'ORGANISASI','Specialists, with a structure.':'Pakar dengan struktur.',
    'Explore departments, reporting lines, and every agent’s responsibilities.':'Terokai jabatan, struktur pelaporan dan tanggungjawab setiap ejen.',
    '101 identities · 10 departments':'101 identiti · 10 jabatan','ORGANIZATION LEAD':'KETUA ORGANISASI',
    'Mission Director':'Pengarah Misi','Selects contributions, aligns heads, and owns the outcome.':'Memilih sumbangan, menyelaras ketua dan bertanggungjawab atas hasil.',
    'View role':'Lihat peranan','Search agents, roles, or departments':'Cari ejen, peranan atau jabatan',
    'Search organization':'Cari organisasi','Shared knowledge':'Pengetahuan bersama',
    'Add document':'Tambah dokumen','Ready':'Sedia','Ready for a mission':'Sedia untuk misi',
    'Mission details':'Butiran misi','Pause':'Jeda','Resume':'Sambung','View activity':'Lihat aktiviti',
    'Message your organization':'Hantar mesej kepada organisasi','Message your organization...':'Hantar mesej kepada organisasi...',
    'Your organization is working...':'Organisasi anda sedang bekerja...',
    'Task limits':'Had tugasan','Model calls':'Panggilan model','Token budget':'Bajet token','Send':'Hantar',
    'A little direction. A lot of possibility.':'Sedikit panduan. Banyak kemungkinan.',
    'What can we work on?':'Apa yang boleh kita usahakan?',
    'Describe an outcome, ask a question, or bring us your next idea.':'Huraikan hasil, ajukan soalan atau kongsikan idea anda yang seterusnya.',
    'TOOLS & CONNECTIONS':'ALAT & SAMBUNGAN',"Connect your organization's tools.":'Sambungkan alat organisasi anda.',
    'One connection for all 101 agents. Each agent uses the tools its work needs.':'Satu sambungan untuk kesemua 101 ejen. Setiap ejen menggunakan alat yang diperlukan.',
    'Shared across the organization':'Dikongsi di seluruh organisasi','Search connectors':'Cari penyambung',
    'Filter connectors':'Tapis penyambung','All connectors':'Semua penyambung','Available now':'Tersedia sekarang',
    'Coming soon':'Akan datang','Configured':'Dikonfigurasi','Available now':'Tersedia sekarang',
    'Manage':'Urus','Set up':'Sediakan','Your connections':'Sambungan anda',
    'Coming soon connectors are previews. They cannot access your accounts yet.':'Penyambung akan datang ialah pratonton. Ia belum boleh mengakses akaun anda.',
    'Available to all agents when enabled':'Tersedia kepada semua ejen apabila diaktifkan',
    'How tools are used':'Cara alat digunakan','No saved connections yet. Choose an available card above to get started.':'Belum ada sambungan disimpan. Pilih kad yang tersedia di atas untuk bermula.',
    'OBSERVABILITY':'PEMANTAUAN','See what actually happened.':'Lihat apa yang sebenarnya berlaku.',
    'Recorded actions, leadership handoffs, artifacts, and execution evidence.':'Tindakan, serahan kepimpinan, artifak dan bukti pelaksanaan yang direkodkan.',
    'No mission selected':'Tiada misi dipilih','Mission':'Misi','Select a mission':'Pilih misi','Agent':'Ejen',
    'All agents':'Semua ejen','Filter activity':'Tapis aktiviti','Agent actions':'Tindakan ejen',
    'Leadership handoffs':'Serahan kepimpinan','Artifacts':'Artifak','Sandbox checks':'Semakan sandbox',
    'Tool requests & results':'Permintaan & hasil alat','No activity to inspect yet.':'Belum ada aktiviti untuk diperiksa.',
    'Start a mission or choose one from your history.':'Mulakan misi atau pilih daripada sejarah anda.',
    'Clarity in the mission. Evidence in the result.':'Misi yang jelas. Hasil yang terbukti.',
    'MAKE IT YOURS':'SESUAIKAN RUANG ANDA','Your workspace, your way.':'Ruang kerja anda, cara anda.',
    'A comfortable place to do your best work.':'Ruang yang selesa untuk menghasilkan kerja terbaik.',
    'Appearance':'Penampilan','Choose the atmosphere for your workspace.':'Pilih suasana ruang kerja anda.',
    'Light':'Cerah','Dark':'Gelap','System':'Sistem','Follow your device':'Ikut peranti anda',
    'Language & reading':'Bahasa & bacaan','Small details that make work feel easier.':'Butiran kecil yang memudahkan kerja.',
    'Interface language':'Bahasa antara muka','Navigation and preferences are translated. Agent content stays in its original language.':'Navigasi dan keutamaan diterjemahkan. Kandungan ejen kekal dalam bahasa asal.',
    'Text size':'Saiz teks','Default':'Lalai','Larger':'Lebih besar',
    'Accessibility':'Kebolehcapaian','Keep your workspace comfortable.':'Pastikan ruang kerja anda selesa.',
    'Reduce motion':'Kurangkan gerakan','Limit decorative animation. Your device’s reduced-motion preference is always respected.':'Hadkan animasi hiasan. Keutamaan kurangkan gerakan peranti anda sentiasa dipatuhi.',
    'Workspace preview':'Pratonton ruang kerja','A space for your next big idea.':'Ruang untuk idea besar anda yang seterusnya.',
    'Research, build, and deliver with a team that fits the mission.':'Selidik, bina dan hasilkan bersama pasukan yang sesuai dengan misi.',
    'Changes apply instantly':'Perubahan berkuat kuasa serta-merta',
    'Preferences are saved in this browser.':'Keutamaan disimpan dalam pelayar ini.',
    'Saved for this visit only. Browser storage is unavailable.':'Disimpan untuk lawatan ini sahaja. Storan pelayar tidak tersedia.',
    'Reset preferences':'Tetapkan semula keutamaan','Model & connections':'Model & sambungan',
    'Manage model credentials and connected tools in Connectors.':'Urus kelayakan model dan alat yang disambungkan dalam Penyambung.',
    'Open Connectors':'Buka Penyambung',
    'Connect a live model':'Sambungkan model langsung','Live model configured':'Model langsung dikonfigurasi',
    'Setup needed':'Persediaan diperlukan','Checking':'Sedang menyemak',
    'Model not configured. Open Connectors to start.':'Model belum dikonfigurasi. Buka Penyambung untuk bermula.',
    'Live model · Head of Distribution receives your message first.':'Model langsung · Ketua Pengagihan menerima mesej anda dahulu.',
  };
  messages.Dashboard=messages.Overview;messages.Chat=messages['Mission chat'];messages.Effectiveness='Keberkesanan';
  const catalogs={en:{},ms:messages,...window.CollectiveLocales.messages};
  const knownLabels=new Set(Object.values(catalogs).flatMap(catalog=>Object.keys(catalog)));
  let saved = {...defaults}, persistent = true;
  try { saved = {...defaults,...JSON.parse(localStorage.getItem(key)||'{}')}; } catch { persistent = false; }
  const normalize = value => ({
    theme:['light','dark','system'].includes(value.theme)?value.theme:defaults.theme,
    language:typeof value.language==='string'&&Object.hasOwn(window.CollectiveLocales.names,value.language)?value.language:defaults.language,
    textSize:['default','large'].includes(value.textSize)?value.textSize:defaults.textSize,
    reduceMotion:value.reduceMotion===true,
  });
  saved = normalize(saved);
  const textNodes = [], attributes = [];
  const t = text => Object.hasOwn(catalogs[saved.language],text)?catalogs[saved.language][text]:text;
  function collectLabels() {
    const walker = document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
    while(walker.nextNode()) {
      const node = walker.currentNode, source = node.textContent.trim();
      if(knownLabels.has(source)&&!node.parentElement.closest('script,style,#chat-messages,#brief-content,#activity-content,#agent-inspector'))textNodes.push({node,source,prefix:node.textContent.match(/^\s*/)[0],suffix:node.textContent.match(/\s*$/)[0]});
    }
    document.querySelectorAll('[placeholder],[aria-label],[title]').forEach(node=>{
      for(const name of ['placeholder','aria-label','title']) {
        const source=node.getAttribute(name);if(knownLabels.has(source))attributes.push({node,name,source});
      }
    });
  }
  function apply() {
    const root=document.documentElement;
    root.dataset.theme=saved.theme==='system'?(media?.matches?'dark':'light'):saved.theme;
    root.dataset.textSize=saved.textSize;
    root.dataset.reduceMotion=String(saved.reduceMotion);
    root.lang=saved.language;
    root.dir=saved.language==='ar'?'rtl':'ltr';
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content',root.dataset.theme==='dark'?'#0b1220':'#f5f3ee');
    textNodes.forEach(({node,source,prefix,suffix})=>{node.textContent=prefix+t(source)+suffix;});
    attributes.forEach(({node,name,source})=>node.setAttribute(name,t(source)));
    document.querySelectorAll('[name="theme"]').forEach(input=>input.checked=input.value===saved.theme);
    if(document.getElementById('setting-language')) {
      document.getElementById('setting-language').value=saved.language;
      document.getElementById('setting-text-size').value=saved.textSize;
      document.getElementById('setting-reduce-motion').checked=saved.reduceMotion;
      document.getElementById('preferences-status').textContent=t(persistent?'Preferences are saved in this browser.':'Saved for this visit only. Browser storage is unavailable.');
    }
  }
  function update(changes, persist=true) {
    saved=normalize({...saved,...changes});
    if(persist)try{localStorage.setItem(key,JSON.stringify(saved));persistent=true;}catch{persistent=false;}
    apply();
    window.dispatchEvent(new CustomEvent('collective-preferences-change'));
  }
  // Apply the theme before the rest of the interface is initialized.
  apply();
  document.addEventListener('DOMContentLoaded',()=>{
    document.getElementById('setting-language').replaceChildren(...Object.entries(window.CollectiveLocales.names).map(([code,name])=>{
      const option=document.createElement('option');option.value=code;option.textContent=name;option.lang=code;option.dir='auto';return option;
    }));
    collectLabels();apply();
    document.querySelectorAll('[name="theme"]').forEach(input=>input.addEventListener('change',()=>update({theme:input.value})));
    document.getElementById('setting-language').addEventListener('change',event=>update({language:event.target.value}));
    document.getElementById('setting-text-size').addEventListener('change',event=>update({textSize:event.target.value}));
    document.getElementById('setting-reduce-motion').addEventListener('change',event=>update({reduceMotion:event.target.checked}));
    document.getElementById('reset-preferences').addEventListener('click',()=>update(defaults));
  });
  media?.addEventListener?.('change',()=>{if(saved.theme==='system')apply();});
  window.addEventListener('storage',event=>{
    if(event.key!==key)return;
    try{saved=normalize({...defaults,...JSON.parse(event.newValue||'{}')});update({},false);}catch{/* Ignore malformed preferences from another tab. */}
  });
  return {t,get:()=>({...saved})};
})();
