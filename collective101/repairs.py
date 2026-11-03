"""Bounded review-driven revisions with immutable per-attempt evidence."""
import json
from .store import encode,now

SCHEMA='''CREATE TABLE IF NOT EXISTS org_repairs(
 root_id TEXT NOT NULL,round INTEGER NOT NULL,run_id TEXT UNIQUE NOT NULL,created_at TEXT NOT NULL,
 PRIMARY KEY(root_id,round));'''

def run_ids(store,root):
    return [root]+[r['run_id'] for r in store.query('SELECT run_id FROM org_repairs WHERE root_id=? ORDER BY round',(root,))]

def feedback(store,run):
    result=run['result']
    artifacts=store.query('SELECT path,content,sha256 FROM org_artifacts WHERE run_id=? ORDER BY path',(run['id'],))
    remaining=24000; excerpts=[]
    for item in artifacts:
        excerpt=item['content'][:max(0,min(8000,remaining))];remaining-=len(excerpt)
        excerpts.append({**item,'content':excerpt,'truncated':len(excerpt)<len(item['content'])})
    return {'previous_run':run['id'],'review':result['review'],'check_errors':result['check_errors'],'blocked_tasks':result['blocked_tasks'],
        'previous_artifacts':excerpts,'instruction':'Your independent review or deterministic checks failed. Heads must assign corrections and refresh dependent deliverables. Preserve the original objective, permissions and acceptance criteria. Re-review is mandatory; past evidence does not count as a new successful check.'}

def run_with_repairs(org,root):
    original=org.inspect(root)
    if original['status']=='reviewed':return original
    # First-attempt calls, artifacts and checks are immutable and replay safely.
    current=org._run_once(root)
    rounds=original['mission'].get('max_repair_rounds',1)
    history=[]
    for number in range(1,rounds+1):
        result=current.get('result')
        hard_blockers=any(task.get('capability_requests') for task in (result or {}).get('blocked_tasks',[]))
        if current['status']!='blocked' or not result or result['accepted'] or hard_blockers:break
        history.append({'run_id':current['id'],'accepted':False,'review':result['review'],'check_errors':result['check_errors']})
        previous=org.store.query('SELECT run_id FROM org_repairs WHERE root_id=? AND round=?',(root,number))
        from .department_runtime import DepartmentOrganization
        child=DepartmentOrganization(org.db_path,org.provider,concurrency=org.concurrency,memory_enabled=org.memory_enabled)
        try:
            if previous:rid=previous[0]['run_id']
            else:
                from .connectors import ConnectorManager
                connectors=ConnectorManager(org.store,org.roster)
                for bound in org.store.query('SELECT tool_key,fingerprint FROM org_connector_bindings WHERE run_id=?',(root,)):
                    if connectors.fingerprint(bound['tool_key'])!=bound['fingerprint']:
                        org.store.execute("UPDATE org_runs SET status='blocked',error='Connector changed; start a new mission' WHERE id=?",(root,))
                        return org.inspect(root)
                binding=org.store.query('SELECT budget_id FROM org_run_budgets WHERE run_id=?',(root,))[0]['budget_id']
                # Same capabilities and checks. Only reviewer feedback is added.
                mission={**original['mission'],'max_repair_rounds':0}
                rid=child.create(mission,max_calls=original['max_calls'],budget_id=binding)
                mission['repair_feedback']=feedback(org.store,current)
                child.store.execute('UPDATE org_runs SET mission=? WHERE id=?',(encode(mission),rid))
                org.store.execute('INSERT INTO org_repairs VALUES(?,?,?,?)',(root,number,rid,now()))
            current=child._run_once(rid)
        finally:child.close()
        if current['status'] in {'paused','needs_input'}:break
    if current['id']!=root:
        result=current.get('result')
        if result:result={**result,'repair_history':history,'effective_run_id':current['id']}
        org.store.execute('UPDATE org_runs SET status=?,result=?,error=? WHERE id=?',
            (current['status'],encode(result) if result else None,current['error'],root))
    final=org.inspect(root)
    if final['status']=='reviewed':org._remember(current['id'],current['result'])
    if final['status'] in {'reviewed','blocked'} and current.get('result'):
        from .learning import record_contributions
        record_contributions(org,root,current['id'],current['result'])
    return final
