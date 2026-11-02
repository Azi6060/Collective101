"""Bounded review-driven revisions with immutable per-attempt evidence."""
import json
from .store import encode,now

SCHEMA='''CREATE TABLE IF NOT EXISTS org_repairs(
 root_id TEXT NOT NULL,round INTEGER NOT NULL,run_id TEXT UNIQUE NOT NULL,created_at TEXT NOT NULL,
 PRIMARY KEY(root_id,round));'''

def run_ids(store,root):
    return [root]+[r['run_id'] for r in store.query('SELECT run_id FROM org_repairs WHERE root_id=? ORDER BY round',(root,))]

def _failure_scope(store,run):
    result=run['result']
    proposals=result.get('proposals',{})
    selected=result.get('selected_departments',[])
    tasks={(department,task['key']):task
        for department,spec in proposals.items() if department in selected
        for task in spec.get('tasks',[])}
    by_path={}
    for (department,key),task in tasks.items():
        for output in task['outputs']:
            by_path.setdefault(department+'/'+output,[]).append((department,key))
    failures=set()
    for error in result.get('check_errors',[]):
        failures.update(ref for path,refs in by_path.items() if path in error for ref in refs)

    unresolved_review=[]
    review=result.get('review') or {}
    artifacts=store.query('SELECT id,path,task_key FROM org_artifacts WHERE run_id=?',(run['id'],))
    for check in review.get('criteria',[]):
        if check.get('met') is not False:
            continue
        evidence=check.get('evidence','')
        referenced={ref for artifact in artifacts
            if artifact['path'] in evidence or artifact['id'] in evidence
            for ref in [(artifact['path'].split('/',1)[0],artifact['task_key'])]}
        if len(referenced)==1:
            failures.update(referenced)
        else:
            unresolved_review.append(check.get('criterion','Unspecified review criterion'))
    if not review.get('accepted') and not any(check.get('met') is False for check in review.get('criteria',[])):
        unresolved_review.append('Reviewer rejected the result without identifying an unmet criterion')

    if unresolved_review:
        return [],'Selective repair cannot safely identify the failed task for: '+', '.join(unresolved_review)
    if not failures:
        return [],'Selective repair found no failed artifact path that can be assigned to a task'

    affected=set(failures)
    changed=True
    while changed:
        changed=False
        affected_departments={department for department,key in affected}
        for (department,key),task in tasks.items():
            if (department,key) in affected:
                continue
            if any((department,dependency) in affected for dependency in task['depends_on']):
                affected.add((department,key))
                changed=True
        for department in selected:
            spec=proposals[department]
            if any(dependency in affected_departments for dependency in spec['depends_on']):
                for task in spec['tasks']:
                    ref=(department,task['key'])
                    if ref not in affected:
                        affected.add(ref)
                        changed=True

    ordered=[(department,task['key']) for department in selected
        for task in proposals[department]['tasks'] if (department,task['key']) in affected]
    return ordered,None


def feedback(store,run,task_refs):
    result=run['result']
    selected=set(task_refs)
    task_definitions=[{'department':department,**task}
        for department,spec in result['proposals'].items()
        for task in spec.get('tasks',[]) if (department,task['key']) in selected]
    artifacts=[item for item in store.query(
        'SELECT id,path,task_key,content,sha256 FROM org_artifacts WHERE run_id=? ORDER BY path',(run['id'],))
        if (item['path'].split('/',1)[0],item['task_key']) in selected]
    remaining=24000; excerpts=[]
    for item in artifacts:
        excerpt=item['content'][:max(0,min(8000,remaining))];remaining-=len(excerpt)
        excerpts.append({**item,'content':excerpt,'truncated':len(excerpt)<len(item['content'])})
    return {'previous_run':run['id'],'repair_tasks':task_definitions,
        'review':result['review'],'check_errors':result['check_errors'],
        'previous_artifacts':excerpts,'instruction':'Correct only the listed repair tasks. Accepted unrelated tasks are preserved unchanged. Dependent tasks are included only when their inputs may have changed. Preserve the original objective, permissions and acceptance criteria. Re-review is mandatory; past evidence does not count as a new successful check.'}

def run_with_repairs(org,root):
    original=org.inspect(root)
    if original['status']=='reviewed':return original
    # First-attempt calls, artifacts and checks are immutable and replay safely.
    current=org._run_once(root)
    rounds=original['mission'].get('max_repair_rounds',1)
    history=[]
    repair_blocked_reason=None
    for number in range(1,rounds+1):
        result=current.get('result')
        if (current['status']!='blocked' or not result or result['accepted'] or result['blocked_tasks']
                or any(report.get('blockers') for report in result.get('reports',{}).values())):break
        history.append({'run_id':current['id'],'accepted':False,'review':result['review'],'check_errors':result['check_errors']})
        task_refs,repair_blocked_reason=_failure_scope(org.store,current)
        if repair_blocked_reason:
            break
        previous=org.store.query('SELECT run_id FROM org_repairs WHERE root_id=? AND round=?',(root,number))
        from .department_runtime import DepartmentOrganization
        child=DepartmentOrganization(org.db_path,org.provider)
        try:
            if previous:rid=previous[0]['run_id']
            else:
                from .connectors import ConnectorManager
                child.roster=original['roster']
                connectors=ConnectorManager(org.store,child.roster)
                for bound in org.store.query('SELECT tool_key,fingerprint FROM org_connector_bindings WHERE run_id=?',(root,)):
                    if connectors.fingerprint(bound['tool_key'])!=bound['fingerprint']:
                        org.store.execute("UPDATE org_runs SET status='blocked',error='Connector changed; start a new mission' WHERE id=?",(root,))
                        return org.inspect(root)
                binding=org.store.query('SELECT budget_id FROM org_run_budgets WHERE run_id=?',(root,))[0]['budget_id']
                # Same capabilities and checks. Only reviewer feedback is added.
                mission={**original['mission'],'max_repair_rounds':0}
                rid=child.create(mission,max_calls=original['max_calls'],budget_id=binding)
                mission['repair_feedback']=feedback(org.store,current,task_refs)
                mission['_repair_context']={'source_run_id':current['id'],
                    'tasks':[{'department':department,'key':key} for department,key in task_refs]}
                child.store.execute('UPDATE org_runs SET mission=? WHERE id=?',(encode(mission),rid))
                org.store.execute('INSERT INTO org_repairs VALUES(?,?,?,?)',(root,number,rid,now()))
            current=child._run_once(rid)
        finally:child.close()
        if current['status'] in {'paused','needs_input'}:break
    if current['id']!=root:
        result=current.get('result')
        if result:
            result={**result,'repair_history':history,'effective_run_id':current['id']}
            if repair_blocked_reason:
                result['repair_blocked_reason']=repair_blocked_reason
        org.store.execute('UPDATE org_runs SET status=?,result=?,error=? WHERE id=?',
            (current['status'],encode(result) if result else None,current['error'],root))
    elif repair_blocked_reason and current.get('result'):
        result={**current['result'],'repair_blocked_reason':repair_blocked_reason}
        org.store.execute('UPDATE org_runs SET result=? WHERE id=?',(encode(result),root))
    final=org.inspect(root)
    if final['status']=='reviewed':org._remember(current['id'],current['result'])
    if final['status'] in {'reviewed','blocked'} and current.get('result'):
        from .learning import record_contributions
        record_contributions(org,root,current['id'],current['result'])
    return final
