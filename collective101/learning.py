"""Evidence-based memory and responsibility, separated from tool permissions."""
import hashlib,json,re,uuid
from datetime import datetime,timedelta,timezone
from .store import encode,now

SCHEMA='''CREATE TABLE IF NOT EXISTS org_memory_cards(
 agent_id TEXT NOT NULL,provider TEXT NOT NULL,topic TEXT NOT NULL,content TEXT NOT NULL,
 sources TEXT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(agent_id,provider,topic));
CREATE TABLE IF NOT EXISTS org_contribution_evidence(
 root_id TEXT NOT NULL,agent_id TEXT NOT NULL,provider TEXT NOT NULL,objective_hash TEXT NOT NULL,
 accepted INTEGER NOT NULL,checked INTEGER NOT NULL,live INTEGER NOT NULL,repaired INTEGER NOT NULL,
 evidence_run TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(root_id,agent_id));
CREATE TABLE IF NOT EXISTS org_lessons(
 id TEXT PRIMARY KEY,agent_id TEXT NOT NULL,provider TEXT NOT NULL,evidence_run TEXT NOT NULL,
 situation TEXT NOT NULL,action TEXT NOT NULL,outcome TEXT NOT NULL,limitations TEXT NOT NULL,
 status TEXT NOT NULL,created_at TEXT NOT NULL,expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS org_lesson_reviews(
 id TEXT PRIMARY KEY,lesson_id TEXT NOT NULL,accepted INTEGER NOT NULL,note TEXT NOT NULL,created_at TEXT NOT NULL);'''

def propose_lesson(store,agent,provider,run_id,situation,action,outcome,limitations):
    from .org_contracts import text
    for value,label in [(situation,'situation'),(action,'action'),(outcome,'outcome'),(limitations,'limitations')]:text(value,label,2000)
    runs=store.query('SELECT provider,status FROM org_runs WHERE id=?',(run_id,))
    owns=store.query('SELECT agent_id FROM org_artifacts WHERE run_id=? AND agent_id=? UNION SELECT agent_id FROM org_calls WHERE run_id=? AND agent_id=? AND status IN (\'accepted\',\'failed\')',(run_id,agent,run_id,agent))
    if not runs or runs[0]['provider']!=provider or not owns or runs[0]['status'] not in {'reviewed','blocked'}:raise ValueError('Lesson needs the same agent/provider and recorded completed or failed source evidence')
    id='lesson_'+uuid.uuid4().hex[:12];created=now();expires=(datetime.now(timezone.utc)+timedelta(days=90)).isoformat()
    store.execute('INSERT INTO org_lessons VALUES(?,?,?,?,?,?,?,?,?,?,?)',(id,agent,provider,run_id,situation,action,outcome,limitations,'proposed',created,expires))
    return store.query('SELECT * FROM org_lessons WHERE id=?',(id,))[0]

def review_lesson(store,id,accepted,note):
    if type(accepted) is not bool or not isinstance(note,str) or not 1<=len(note.strip())<=2000:raise ValueError('Lesson review requires a verdict and an evidence note')
    if not store.query('SELECT id FROM org_lessons WHERE id=?',(id,)):raise ValueError('Unknown lesson')
    with store.transaction() as db:
        db.execute('INSERT INTO org_lesson_reviews VALUES(?,?,?,?,?)',('lesson_review_'+uuid.uuid4().hex[:12],id,int(accepted),note.strip(),now()))
        db.execute('UPDATE org_lessons SET status=? WHERE id=?',('approved' if accepted else 'rejected',id))
    return store.query('SELECT * FROM org_lessons WHERE id=?',(id,))[0]

def recall_lessons(store,agent,provider,query):
    terms=set(re.findall(r'\w{3,}',query.lower()));ranked=[]
    for row in store.query("SELECT * FROM org_lessons WHERE agent_id=? AND provider=? AND status='approved' AND expires_at>? ORDER BY created_at DESC LIMIT 100",(agent,provider,now())):
        score=len(terms&set(re.findall(r'\w{3,}',row['situation'].lower())))
        if score:ranked.append((score,{**row,'kind':'reviewed_lesson_not_policy','learning_claim':'Human-reviewed reference; benefit requires held-out evaluation'}))
    return [row for _,row in sorted(ranked,key=lambda item:-item[0])[:3]]

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
