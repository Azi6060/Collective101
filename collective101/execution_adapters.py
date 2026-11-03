"""Explicit static-browser and offline container adapters. Never execute agent code on the host."""
import hashlib,json,os,re,shutil,subprocess,tempfile,threading,time,uuid
from pathlib import Path,PurePosixPath
from functools import lru_cache
from urllib.parse import urlencode
from .org_contracts import safe_path
from .preview import PreviewManager

ROOT=Path(__file__).resolve().parents[1]
EXECUTION=Path(__file__).parent/'execution'

@lru_cache(maxsize=1)
def browser_executable():
    for folder in [os.environ.get('PROGRAMFILES','C:/Program Files'),os.environ.get('PROGRAMFILES(X86)','C:/Program Files (x86)'),os.environ.get('LOCALAPPDATA','')]:
        path=Path(folder)/'Google/Chrome/Application/chrome.exe'
        if folder and path.is_file():return str(path)
    return None

@lru_cache(maxsize=1)
def node_executable():return shutil.which('node')

@lru_cache(maxsize=1)
def docker_executable():return shutil.which('docker')

def browser_readiness():
    available=os.name=='nt' and bool(node_executable()) and bool(browser_executable()) and (ROOT/'node_modules/playwright/package.json').is_file()
    return {'available':available,'engine':'Chromium isolated static project',
        'reason':None if available else 'Local browser execution requires Windows process-tree containment, Node, installed Playwright and Chrome.'}

def container_readiness(profile):
    if profile not in {'python','node_build'}:raise ValueError('Supported container profiles are python and node_build')
    image=os.environ.get('COLLECTIVE101_PYTHON_IMAGE' if profile=='python' else 'COLLECTIVE101_NODE_IMAGE','')
    valid=bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./:-]*@sha256:[a-f0-9]{64}',image))
    available=valid and bool(docker_executable())
    return {'available':available,'engine':'Docker offline '+profile,
        'reason':None if available else 'Install/configure a local Linux Docker engine and a trusted digest-pinned runtime image; no host fallback or automatic image pull is allowed.'}

def validate_files(files,entry):
    if not isinstance(files,list) or not 1<=len(files)<=32:raise ValueError('Provide 1 to 32 bounded source files')
    saved={};total=0
    for file in files:
        if not isinstance(file,dict) or not isinstance(file.get('content'),str):raise ValueError('Source files need path and UTF-8 text content')
        path=safe_path(file.get('path'));fold=path.casefold()
        if fold in {p.casefold() for p in saved} or any(part.startswith('__collective') for part in PurePosixPath(path).parts):raise ValueError('Duplicate or reserved runtime path')
        content=file['content'];total+=len(content.encode())
        if total>1024*1024:raise ValueError('Execution source exceeds 1 MiB')
        saved[path]=content
    names={p.casefold() for p in saved}
    for name in names:
        parts=name.split('/')
        if any('/'.join(parts[:i]) in names for i in range(1,len(parts))):raise ValueError('Execution file/directory paths overlap')
    safe_path(entry)
    if entry not in saved:raise ValueError('Execution entry must be a supplied source file')
    return saved

def validate_browser_checks(checks):
    if not isinstance(checks,list) or not 1<=len(checks)<=12:raise ValueError('Provide 1 to 12 browser checks')
    for check in checks:
        if not isinstance(check,dict) or set(check)-{'selector','action','text','contains','equals','visible','count'}:raise ValueError('Unsupported browser check field')
        if not isinstance(check.get('selector'),str) or not 1<=len(check['selector'])<=300:raise ValueError('Browser check needs a bounded selector')
        if check.get('action') not in {None,'click','fill'}:raise ValueError('Browser actions are click or fill; arbitrary evaluation/navigation is unavailable')
        if check.get('action')=='fill' and (not isinstance(check.get('text'),str) or len(check['text'])>1000):raise ValueError('Fill needs bounded text')
        if 'contains' in check and (not isinstance(check['contains'],str) or len(check['contains'])>1000):raise ValueError('Invalid expected text')
        if 'equals' in check and (not isinstance(check['equals'],str) or len(check['equals'])>1000):raise ValueError('Invalid exact text')
        if 'visible' in check and type(check['visible']) is not bool:raise ValueError('Visibility must be boolean')
        if 'count' in check and (type(check['count']) is not int or not 0<=check['count']<=100):raise ValueError('Invalid expected element count')
        if not any(k in check for k in ('action','contains','equals','visible','count')):raise ValueError('A browser check needs an action or an expectation')
    return checks

class WindowsJob:
    """Kill the entire owned subprocess tree, including Chromium, on handle close."""
    def __init__(self,process):
        import ctypes
        from ctypes import wintypes as w
        class Basic(ctypes.Structure):
            _fields_=[('process_time',ctypes.c_int64),('job_time',ctypes.c_int64),('flags',w.DWORD),('min_ws',ctypes.c_size_t),('max_ws',ctypes.c_size_t),('active',w.DWORD),('affinity',ctypes.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
        class IO(ctypes.Structure):_fields_=[(name,ctypes.c_uint64) for name in ['read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes']]
        class Extended(ctypes.Structure):_fields_=[('basic',Basic),('io',IO),('process_memory',ctypes.c_size_t),('job_memory',ctypes.c_size_t),('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]
        api=ctypes.WinDLL('kernel32',use_last_error=True)
        api.CreateJobObjectW.restype=w.HANDLE;api.CreateJobObjectW.argtypes=[ctypes.c_void_p,w.LPCWSTR]
        api.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD]
        api.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE];api.CloseHandle.argtypes=[w.HANDLE]
        self.api=api;self.handle=api.CreateJobObjectW(None,None)
        limits=Extended();limits.basic.flags=0x2000|0x200;limits.job_memory=1024*1024*1024
        if not self.handle or not api.SetInformationJobObject(self.handle,9,ctypes.byref(limits),ctypes.sizeof(limits)) or not api.AssignProcessToJobObject(self.handle,w.HANDLE(int(process._handle))):
            self.close();raise OSError('Cannot establish Windows process-tree containment')
    def close(self):
        if getattr(self,'handle',None):self.api.CloseHandle(self.handle);self.handle=None

def bounded_process(command,payload=None,timeout=30,tree=False):
    env={k:os.environ[k] for k in ['PATH','SYSTEMROOT','WINDIR','TEMP','TMP','LOCALAPPDATA'] if k in os.environ}
    process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=ROOT,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    job=None;overflow=threading.Event();buffers=[bytearray(),bytearray()]
    def collect(pipe,index):
        try:
            while chunk:=pipe.read(4096):
                left=65536-len(buffers[index]);buffers[index].extend(chunk[:max(0,left)])
                if len(chunk)>left:overflow.set()
        except OSError:pass
        finally:pipe.close()
    threads=[threading.Thread(target=collect,args=(pipe,i),daemon=True) for i,pipe in enumerate([process.stdout,process.stderr])]
    try:
        if tree:
            if os.name!='nt':raise OSError('Process-tree containment is unavailable')
            job=WindowsJob(process)
        for thread in threads:thread.start()
        if payload is not None:process.stdin.write(payload)
        process.stdin.close();deadline=time.monotonic()+timeout;stopped=None
        while process.poll() is None:
            if overflow.is_set() or time.monotonic()>deadline:
                stopped='output_limit' if overflow.is_set() else 'timeout';process.kill();break
            time.sleep(.03)
        process.wait(timeout=3)
        if job:job.close()
        for thread in threads:thread.join(timeout=2)
        return {'returncode':process.returncode,'stdout':buffers[0].decode('utf-8','replace'),'stderr':buffers[1].decode('utf-8','replace'),'stopped':stopped or ('output_limit' if overflow.is_set() else None)}
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=3)
        if job:job.close()
        for pipe in [process.stdin,process.stdout,process.stderr]:
            if pipe and not pipe.closed:pipe.close()

def execute_browser(files,entry,checks):
    saved=validate_files(files,entry);validate_browser_checks(checks)
    if PurePosixPath(entry).suffix.lower() not in {'.html','.htm'}:raise ValueError('Browser entry must be saved HTML')
    ready=browser_readiness()
    if not ready['available']:return {'passed':False,'status':'unavailable','error':ready['reason'],'checks':[]}
    class Source:
        def chat(self,cid):return {'mode':'meta','title':'Runtime browser check','status':'running','workspace':{'files':[
            {'path':path,'content':content,'bytes':len(content.encode()),'sha256':hashlib.sha256(content.encode()).hexdigest()} for path,content in saved.items()]}}
    manager=PreviewManager(Source())
    try:
        preview=manager.open('runtime',entry)
        payload=json.dumps({'url':preview['url']+'?'+urlencode({'entry':entry}),'root':preview['url'],'checks':checks,'executable':browser_executable()}).encode()
        output=bounded_process([shutil.which('node'),str(EXECUTION/'browser_runner.mjs')],payload,timeout=30,tree=True)
        if output['stopped']:return {'passed':False,'status':output['stopped'],'checks':[],'error':'Browser exceeded its bounded execution limits'}
        result=json.loads(output['stdout'])
        if type(result.get('passed')) is not bool or not isinstance(result.get('checks'),list):raise ValueError('Malformed browser evidence')
        return {**result,'status':'passed' if result['passed'] else 'unavailable' if result.get('stage') in {'launch','context'} else 'failed','scope':'Observed static project interaction in isolated Chromium; external services and deployment were not tested'}
    except (OSError,ValueError):return {'passed':False,'status':'unavailable','checks':[],'error':'Isolated browser failed to start or returned invalid evidence; no host fallback was used'}
    finally:manager.close()

def execute_container(profile,files,entry):
    if profile not in {'python','node_build'}:raise ValueError('Only fixed python and node_build profiles are executable')
    saved=validate_files(files,entry)
    if profile=='python' and not entry.endswith('.py'):raise ValueError('Python entry must be a supplied .py file')
    if profile=='node_build' and PurePosixPath(entry).name!='package.json':raise ValueError('Node build entry must be a supplied package.json')
    ready=container_readiness(profile)
    if not ready['available']:return {'passed':False,'status':'unavailable','error':ready['reason'],'files':[]}
    image=os.environ['COLLECTIVE101_PYTHON_IMAGE' if profile=='python' else 'COLLECTIVE101_NODE_IMAGE'];docker=shutil.which('docker')
    parent=ROOT/'work'/'execution';parent.mkdir(parents=True,exist_ok=True);name='collective101-'+uuid.uuid4().hex[:16]
    with tempfile.TemporaryDirectory(dir=parent) as temp:
        folder=Path(temp).resolve()
        if not folder.is_relative_to(parent.resolve()):raise ValueError('Unexpected execution workspace')
        for path,content in saved.items():
            target=folder/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(content,encoding='utf-8')
        runner='__collective_runner.py' if profile=='python' else '__collective_runner.mjs'
        shutil.copyfile(EXECUTION/('python_container.py' if profile=='python' else 'node_container.mjs'),folder/runner)
        command=[docker,'run','--name',name,'--rm','--pull=never','--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',
            '--pids-limit=64','--memory=256m','--memory-swap=256m','--cpus=1','--user=65534:65534','--tmpfs','/tmp:rw,nosuid,nodev,size=64m',
            '--mount',f'type=bind,src={folder},dst=/input,readonly','--env','HOME=/tmp','--entrypoint','python' if profile=='python' else 'node',image]
        command+=['-I','-S','/input/'+runner,entry] if profile=='python' else ['/input/'+runner,entry]
        try:
            output=bounded_process(command,timeout=25)
            if output['stopped']:return {'passed':False,'status':output['stopped'],'error':'Container exceeded execution/output limits','files':[]}
            if output['returncode'] in {125,126,127}:return {'passed':False,'status':'unavailable','error':'Docker engine, trusted image or fixed runtime command is unavailable; automatic pulling and host execution are disabled','files':[]}
            result=json.loads(output['stdout'])
            if type(result.get('passed')) is not bool:raise ValueError('Malformed container evidence')
            generated=result.get('files',[])
            if generated:
                validate_files(generated,generated[0]['path'])
            return {**result,'status':'passed' if result['passed'] else 'failed','engine':ready['engine'],'scope':'Offline resource-limited container; no deployment or external integration was exercised'}
        except (OSError,ValueError):return {'passed':False,'status':'failed','error':'Container failed to return bounded JSON evidence','files':[]}
        finally:
            try:bounded_process([docker,'rm','--force',name],timeout=3)
            except (OSError,subprocess.SubprocessError):pass
