"""Evidence-based memory and responsibility, separated from tool permissions."""
import hashlib,json,re
from .store import encode,now

SCHEMA='''CREATE TABLE IF NOT EXISTS org_memory_cards(
 agent_id TEXT NOT NULL,provider TEXT NOT NULL,topic TEXT NOT NULL,content TEXT NOT NULL,
 sources TEXT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(agent_id,provider,topic));
CREATE TABLE IF NOT EXISTS org_contribution_evidence(
 root_id TEXT NOT NULL,agent_id TEXT NOT NULL,provider TEXT NOT NULL,objective_hash TEXT NOT NULL,
 accepted INTEGER NOT NULL,checked INTEGER NOT NULL,live INTEGER NOT NULL,repaired INTEGER NOT NULL,
 evidence_run TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(root_id,agent_id));
CREATE TABLE IF NOT EXISTS org_team_outcomes(
 root_id TEXT PRIMARY KEY,provider TEXT NOT NULL,evidence_mode TEXT NOT NULL,live INTEGER NOT NULL,
 objective_terms TEXT NOT NULL,departments TEXT NOT NULL,accepted INTEGER NOT NULL,
 evidence_run TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS org_task_evidence(
 root_id TEXT NOT NULL,department TEXT NOT NULL,task_key TEXT NOT NULL,agent_id TEXT NOT NULL,
 provider TEXT NOT NULL,task_terms TEXT NOT NULL,evidence_run TEXT NOT NULL,created_at TEXT NOT NULL,
 PRIMARY KEY(root_id,department,task_key));'''

STOP_WORDS={'about','after','again','also','and','are','build','can','for','from','have','into',
    'mission','need','our','should','that','the','their','then','this','through','with','would',
    'your','you','them','they','what','when','where','which','while','will'}

def provider_signature(provider):
    return encode({'mode':provider.name,'model':getattr(provider,'model',None),
        'url':getattr(provider,'url',None)})

def _terms(value):
    return {hashlib.sha256(term.encode()).hexdigest()
        for term in re.findall(r'\w{3,}',value.lower())
        if term not in STOP_WORDS}

def transcript_query(transcript):
    return ' '.join(message.get('content','') for message in transcript
        if message.get('role')=='user' and isinstance(message.get('content'),str))

def record_team_outcome(org,root,effective,result):
    mission=org.inspect(root)['mission']
    terms=_terms(mission['objective'])
    departments=result.get('selected_departments',[])
    if not terms or not departments:
        return
    live=org.provider.name=='meta'
    org.store.execute('''INSERT INTO org_team_outcomes VALUES(?,?,?,?,?,?,?,?,?)
        ON CONFLICT(root_id) DO UPDATE SET provider=excluded.provider,evidence_mode=excluded.evidence_mode,
        live=excluded.live,objective_terms=excluded.objective_terms,departments=excluded.departments,
        accepted=excluded.accepted,evidence_run=excluded.evidence_run,created_at=excluded.created_at''',
        (root,org.provider_signature,org.provider.name,int(live),encode(sorted(terms)),
         encode(departments),int(bool(result['accepted'])),effective,now()))
    org.store.execute('''DELETE FROM org_team_outcomes WHERE root_id IN (
        SELECT root_id FROM org_team_outcomes WHERE provider=? ORDER BY created_at DESC,root_id
        LIMIT -1 OFFSET 500)''',(org.provider_signature,))

def team_recommendations(store,provider,query,limit=3):
    if provider.name!='meta':
        return []
    query_terms=_terms(query)
    if len(query_terms)<2:
        return []
    rows=store.query('''SELECT root_id,objective_terms,departments,accepted,evidence_run
        FROM org_team_outcomes WHERE provider=? AND live=1 AND evidence_mode='meta'
        ORDER BY created_at DESC,root_id LIMIT 500''',(provider_signature(provider),))
    matches=[]
    for row in rows:
        prior_terms=set(json.loads(row['objective_terms']))
        common=len(query_terms & prior_terms)
        ratio=common/max(1,min(len(query_terms),len(prior_terms)))
        if common<2 or ratio<0.25:
            continue
        matches.append((common,ratio,row))
    matches.sort(key=lambda item:(-item[0],-item[1],item[2]['root_id']))
    return [{
        'outcome':'accepted' if row['accepted'] else 'not_accepted',
        'departments':json.loads(row['departments']),
        'matched_objective_terms':common,
        'evidence_run':row['evidence_run'],
    } for common,_,row in matches[:limit]]

def assignment_evidence(store,agent_id,provider,query,limit=3):
    if provider.name!='meta':
        return None
    query_terms=_terms(query)
    if len(query_terms)<2:
        return None
    rows=store.query('''SELECT task_terms,evidence_run FROM org_task_evidence
        WHERE agent_id=? AND provider=? ORDER BY created_at DESC,evidence_run LIMIT 200''',
        (agent_id,provider_signature(provider)))
    matches=[]
    for row in rows:
        terms=set(json.loads(row['task_terms']))
        common=len(query_terms & terms)
        ratio=common/max(1,min(len(query_terms),len(terms)))
        if common>=2 and ratio>=0.25:
            matches.append((common,ratio,row['evidence_run']))
    matches.sort(key=lambda item:(-item[0],-item[1],item[2]))
    evidence_runs=list(dict.fromkeys(item[2] for item in matches))
    if not evidence_runs:
        return None
    return {
        'similar_verified_tasks':len(matches),
        'verified_missions':len(evidence_runs),
        'history_strength':'repeated' if len(evidence_runs)>=2 else 'limited',
        'evidence_runs':evidence_runs[:limit],
        'scope':'Positive independently checked task evidence only; not a rank or permission',
    }

def record_task_evidence(org,root,effective,result):
    if not result.get('accepted') or org.provider.name!='meta':
        return
    mission=org.inspect(root)['mission']
    artifacts=org.store.query('SELECT agent_id,path,content FROM org_artifacts WHERE run_id=?',(effective,))
    by_path={row['path']:row for row in artifacts}
    checked_paths=set()
    for check in mission.get('artifact_checks',[]):
        artifact=by_path.get(check['path'])
        if not artifact:
            continue
        if check['type']=='contains' and check['text'] in artifact['content']:
            checked_paths.add(check['path'])
        elif check['type']=='html':
            from .html_checks import check_html
            if not check_html(artifact['content']):
                checked_paths.add(check['path'])
    checked_paths.update(
        execution['path'] for execution in result.get('execution_results',[])
        if execution['result'].get('passed'))
    for department,spec in result.get('proposals',{}).items():
        for task in spec.get('tasks',[]):
            task_terms=_terms(task['title']+' '+task['instructions'])
            if len(task_terms)<2:
                continue
            task_paths={department+'/'+path for path in task['outputs']}
            if not any(row['agent_id']==task['assignee'] and row['path'] in checked_paths
                    for row in artifacts if row['path'] in task_paths):
                continue
            org.store.execute('''INSERT OR IGNORE INTO org_task_evidence
                VALUES(?,?,?,?,?,?,?,?)''',(root,department,task['key'],task['assignee'],
                org.provider_signature,encode(sorted(task_terms)),effective,now()))
    org.store.execute('''DELETE FROM org_task_evidence WHERE rowid IN (
        SELECT rowid FROM org_task_evidence WHERE provider=?
        ORDER BY created_at DESC,root_id,department,task_key
        LIMIT -1 OFFSET 2000)''',(org.provider_signature,))

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
