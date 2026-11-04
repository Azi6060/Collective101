"""Plan revisions at drained phase boundaries; original run inputs stay immutable."""
import json
from .store import encode,now

def run(org,root):
    from . import repairs
    original=org.inspect(root)
    if original['status']=='reviewed':return original
    existing=org.store.query('SELECT run_id FROM org_plan_revisions WHERE root_id=? ORDER BY round',(root,))
    current_id=existing[-1]['run_id'] if existing else root
    while True:
        current=repairs.run_with_repairs(org,current_id)
        if current['status']!='replanning':break
        ids=repairs.run_ids(org.store,current_id);pending=[]
        for rid in ids:pending.extend(org.store.query("SELECT * FROM org_assistance WHERE run_id=? AND status='replan_requested' ORDER BY rowid",(rid,)))
        if not pending:raise RuntimeError('Replanning needs a recorded approved assistance request')
        request=pending[-1];revision=json.loads(request['decision'])
        # Concurrent workers may have separate approved needs. Consult their union,
        # never discard a Director-approved missing workstream from the drained wave.
        if len(pending)>1:
            decisions=[json.loads(p['decision']) for p in pending]
            revision={**revision,'departments':list(dict.fromkeys(d for decision in decisions for d in decision['departments'])),'concurrent_decisions':decisions}
        prior=org.store.query('SELECT * FROM org_plan_revisions WHERE root_id=? ORDER BY round',(root,))
        if len(prior)>=2:
            org.store.execute("UPDATE org_runs SET status='blocked',error='Plan revision limit reached; unresolved help requires a new scoped request' WHERE id=?",(current_id,));current=org.inspect(current_id);break
        from .connectors import ConnectorManager
        manager=ConnectorManager(org.store,org.roster)
        for bound in org.store.query('SELECT tool_key,fingerprint FROM org_connector_bindings WHERE run_id=?',(root,)):
            if manager.fingerprint(bound['tool_key'])!=bound['fingerprint']:raise ValueError('Connector changed during replan; start a new scoped task')
        base=org.inspect(request['run_id'])['mission'];mission={**base,'departments':revision['departments']}
        binding=org.store.query('SELECT budget_id FROM org_run_budgets WHERE run_id=?',(root,))[0]['budget_id']
        rid=org.create(mission,max_calls=original['max_calls'],budget_id=binding)
        files=[];remaining=180000
        for old_id in repairs.run_ids(org.store,root):
            for f in org.store.query('SELECT path,content,sha256 FROM org_artifacts WHERE run_id=?',(old_id,)):
                excerpt=f['content'][:max(0,min(60000,remaining))];remaining-=len(excerpt);files.append({**f,'content':excerpt,'excerpt':len(excerpt)<len(f['content'])})
        mission['replan_context']={'parent_run':request['run_id'],'request':json.loads(request['request']),'head_answer':json.loads(request['response']),'requests':[json.loads(p['request']) for p in pending],'head_answers':[json.loads(p['response']) for p in pending],'director_decision':revision,'prior_artifacts':files,'instruction':'Reuse valid saved work as reference and integrate newly needed department output. All original criteria, checks and capabilities remain authoritative. This is a new immutable attempt; fresh independent review is required.'}
        org.store.execute('UPDATE org_runs SET mission=? WHERE id=?',(encode(mission),rid))
        org.store.execute('INSERT INTO org_plan_revisions VALUES(?,?,?,?,?,?,?)',(root,len(prior)+1,request['run_id'],rid,request['id'],encode(revision),now()))
        for applied in pending:org.store.execute("UPDATE org_assistance SET status='replanned' WHERE id=?",(applied['id'],))
        current_id=rid
    if current_id!=root:
        result=current.get('result')
        if result:result={**result,'effective_run_id':result.get('effective_run_id',current_id),'plan_revisions':org.store.query('SELECT round,parent_id,run_id,request_id,decision FROM org_plan_revisions WHERE root_id=? ORDER BY round',(root,))}
        org.store.execute('UPDATE org_runs SET status=?,result=?,error=? WHERE id=?',(current['status'],encode(result) if result else None,current['error'],root))
    return org.inspect(root)
