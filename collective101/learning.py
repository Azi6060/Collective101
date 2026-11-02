"""Evidence-based memory and responsibility, separated from tool permissions."""
import hashlib,json,re
from .store import encode,now

SCHEMA='''CREATE TABLE IF NOT EXISTS org_memory_cards(
 agent_id TEXT NOT NULL,provider TEXT NOT NULL,topic TEXT NOT NULL,content TEXT NOT NULL,
 sources TEXT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(agent_id,provider,topic));
CREATE TABLE IF NOT EXISTS org_contribution_evidence(
 root_id TEXT NOT NULL,agent_id TEXT NOT NULL,provider TEXT NOT NULL,objective_hash TEXT NOT NULL,
 accepted INTEGER NOT NULL,checked INTEGER NOT NULL,live INTEGER NOT NULL,repaired INTEGER NOT NULL,
 evidence_run TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(root_id,agent_id));'''

def consolidate(store,agent,provider,content,run_id):
    data=json.loads(content)
    topic=hashlib.sha256(encode({k:data.get(k) for k in ('objective','phase','summary')}).encode()).hexdigest()
    prior=store.query('SELECT sources FROM org_memory_cards WHERE agent_id=? AND provider=? AND topic=?',(agent,provider,topic))
    sources=json.loads(prior[0]['sources']) if prior else []
    sources=list(dict.fromkeys(sources+[run_id]))[-20:]
    store.execute('INSERT INTO org_memory_cards VALUES(?,?,?,?,?,?) ON CONFLICT(agent_id,provider,topic) DO UPDATE SET sources=excluded.sources,updated_at=excluded.updated_at',
        (agent,provider,topic,content,encode(sources),now()))
    store.execute('DELETE FROM org_memory_cards WHERE agent_id=? AND provider=? AND topic NOT IN (SELECT topic FROM org_memory_cards WHERE agent_id=? AND provider=? ORDER BY updated_at DESC,topic LIMIT 50)',(agent,provider,agent,provider))

def recall_cards(store,agent,provider,run_id,query):
    terms=set(re.findall(r'\w{3,}',query.lower()))
    rows=store.query('SELECT content,sources FROM org_memory_cards WHERE agent_id=? AND provider=? ORDER BY updated_at DESC LIMIT 50',(agent,provider))
    ranked=[]
    for row in rows:
        sources=json.loads(row['sources'])
        if run_id in sources:continue
        score=len(terms&set(re.findall(r'\w{3,}',row['content'].lower())))
        if score:ranked.append((score,{'content':row['content'],'evidence_runs':sources,'kind':'reviewed_memory_not_policy'}))
    return [r for _,r in sorted(ranked,key=lambda p:-p[0])[:3]]

def record_contributions(org,root,effective,result):
    mission=org.inspect(root)['mission']
    objective=hashlib.sha256(' '.join(mission['objective'].lower().split()).encode()).hexdigest()
    live=org.provider.name=='meta'
    artifacts=org.store.query('SELECT agent_id,path FROM org_artifacts WHERE run_id=?',(effective,))
    # Only successful checks on this employee's artifacts count as measured output.
    checked_paths={c['path'] for c in mission['artifact_checks'] if c['type']=='contains'} if not result['check_errors'] else set()
    checked_paths.update(e['path'] for e in result['execution_results'] if e['result']['passed'])
    for agent in {a['agent_id'] for a in artifacts}:
        checked=any(a['agent_id']==agent and a['path'] in checked_paths for a in artifacts)
        org.store.execute('INSERT OR IGNORE INTO org_contribution_evidence VALUES(?,?,?,?,?,?,?,?,?,?)',
            (root,agent,org.provider_signature,objective,int(result['accepted']),int(checked),int(live),int(root!=effective),effective,now()))

def responsibility(store,agent,provider=None):
    sql='SELECT * FROM org_contribution_evidence WHERE agent_id=? AND live=1'
    args=[agent]
    if provider is not None:sql+=' AND provider=?';args.append(provider)
    rows=store.query(sql+' ORDER BY created_at DESC LIMIT 20',args)
    successes={r['objective_hash'] for r in rows if r['accepted'] and r['checked']}
    recent_failures=sum(not r['accepted'] for r in rows[:5])
    level='developing'
    if len(successes)>=3 and recent_failures<2:level='trusted_contributor'
    if len(successes)>=8 and recent_failures==0:level='senior_contributor'
    return {'level':level,'distinct_verified_missions':len(successes),'recent_failures':recent_failures,
        'evidence_runs':[r['evidence_run'] for r in rows],
        'scope':'Advisory assignment responsibility; no change to role, reporting line, tools or budgets'}
