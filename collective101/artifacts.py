"""Chat workspaces and bounded source-only archives; never read host files."""
import difflib,io,json,re,zipfile
from functools import lru_cache
from pathlib import PurePosixPath
from .org_contracts import safe_path
from . import repairs

CODE={'.html':'HTML','.css':'CSS','.js':'JavaScript','.mjs':'JavaScript','.ts':'TypeScript','.tsx':'TSX','.jsx':'JSX','.py':'Python','.sql':'SQL','.json':'JSON','.svg':'SVG'}

@lru_cache(maxsize=64)
def line_changes(old_content,content):
    if old_content==content:return 0,0
    old=old_content.splitlines();lines=content.splitlines()
    if not old:return len(lines),0
    plus=minus=0
    for tag,a,b,c,d in difflib.SequenceMatcher(a=old,b=lines,autojunk=True).get_opcodes():
        if tag in {'insert','replace'}:plus+=d-c
        if tag in {'delete','replace'}:minus+=b-a
    return plus,minus

def title(chat):
    brief=chat.get('brief') or {}
    if isinstance(brief,str):brief=json.loads(brief)
    transcript=chat.get('transcript') or []
    if isinstance(transcript,str):transcript=json.loads(transcript)
    source=brief.get('title') or brief.get('objective') or next((m['content'] for m in reversed(transcript) if m['role']=='user'),'New chat')
    source=re.sub(r'^(?:please\s+)?(?:build|create|make|write|develop)(?:\s+me)?\s+(?:an?\s+)?','',source,flags=re.I)
    words=re.findall(r"[\w'-]+",source)[:8]
    return (' '.join(words)[:76] or 'New chat').capitalize()

def workspace(store,roots):
    ids=[]
    for root in roots:
        ids.extend(r for r in repairs.run_ids(store,root) if r not in ids)
    files={};failures=[];events=[];added=removed=0
    for rid in ids:
        for row in store.query('SELECT * FROM org_artifacts WHERE run_id=? ORDER BY rowid',(rid,)):
            path=safe_path(row['path']);content=row['content'];lines=content.splitlines()
            plus,minus=line_changes(files.get(path,{}).get('content',''),content)
            added+=plus;removed+=minus
            suffix=PurePosixPath(path).suffix.lower()
            files[path]={'path':path,'content':content,'bytes':len(content.encode()),'lines':len(lines),
                'language':CODE.get(suffix,'Markdown' if suffix=='.md' else 'Text'),'is_code':suffix in CODE,
                'added':plus,'removed':minus,'agent_id':row['agent_id'],'run_id':rid,'sha256':row['sha256']}
        for call in store.query('SELECT step_key,attempt,agent_id,phase,status,error,error_kind,request_options,created_at FROM org_calls WHERE run_id=? ORDER BY rowid',(rid,)):
            if call['status']=='failed':failures.append({'run_id':rid,'step':call['step_key'],'attempt':call['attempt'],
                'agent_id':call['agent_id'],'phase':call['phase'],'kind':call['error_kind'] or 'request','reason':call['error'],
                'request_options':json.loads(call['request_options']) if call['request_options'] else None})
            events.append({'id':rid+':'+call['step_key']+':'+str(call['attempt']),'agent_id':call['agent_id'],
                'phase':call['phase'],'status':call['status'],'created_at':call['created_at']})
        rows=store.query('SELECT result,error,status FROM org_runs WHERE id=?',(rid,))
        if rows and rows[0]['result']:
            result=json.loads(rows[0]['result'])
            for task in result.get('blocked_tasks',[]):failures.append({'run_id':rid,'agent_id':task.get('department','')+'-001',
                'phase':'work','kind':task.get('kind','task_blocker'),'reason':task['reason'],'task':task['task'],'capability_requests':task.get('capability_requests',[])})
            for error in result.get('check_errors',[]):failures.append({'run_id':rid,'phase':'checks','kind':'acceptance','reason':error})
    items=sorted(files.values(),key=lambda f:f['path'])
    folded=[f['path'].casefold() for f in items]
    if len(set(folded))!=len(folded):raise ValueError('Ambiguous case-insensitive artifact paths')
    names=set(folded)
    if 'manifest.json' in names:raise ValueError('Root manifest.json is reserved for download metadata')
    for name in names:
        parts=name.split('/')
        if any('/'.join(parts[:i]) in names for i in range(1,len(parts))):raise ValueError('Artifact file and directory paths overlap')
    from .preview import describe
    return {'files':items,'preview':describe(items),'totals':{'files':len(items),'lines':sum(f['lines'] for f in items),
        'code_lines':sum(f['lines'] for f in items if f['is_code']),'added':added,'removed':removed},
        'failures':failures[-30:],'events':events[-12:],'run_ids':ids}

def bundle(workspace,chat_title,status):
    if not workspace['files']:raise ValueError('No files have been saved yet')
    if sum(f['bytes'] for f in workspace['files'])>20*1024*1024:raise ValueError('Chat download exceeds 20 MiB')
    manifest={'title':chat_title,'status':status,'scope':'Saved source files; partial work may be incomplete. No deployment is implied.',
              'files':[{k:v for k,v in f.items() if k!='content'} for f in workspace['files']], 'totals':workspace['totals']}
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for f in workspace['files']:archive.writestr(safe_path(f['path']),f['content'])
        archive.writestr('manifest.json',json.dumps(manifest,indent=2))
    return output.getvalue()
