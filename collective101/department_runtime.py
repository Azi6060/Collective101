"""Department-led organization with a replaceable, bounded artifact-drafting harness."""
import hashlib
import json
import uuid
from pathlib import Path
from .agent_harness import AgentHarness, LeadershipBus, HumanInputRequired, RunPaused
from . import org_contracts as contracts
from .registry import build_roster, DEPARTMENT_MAP
from .store import Store, encode, now
from . import budgets
from . import progress
from . import repairs
from . import learning
from . import assistance,replanning
from .agent_tools import SCHEMA as TOOL_SCHEMA, ToolBroker, eligible_tools
from .connectors import ConnectorManager
from .runtime_core import POLICY_SCHEMA,policy,run_dag,validate_concurrency

SCHEMA = '''
CREATE TABLE IF NOT EXISTS org_interventions(
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL, step_key TEXT NOT NULL, agent_id TEXT NOT NULL,
 question TEXT NOT NULL, reason TEXT NOT NULL, options TEXT NOT NULL, status TEXT NOT NULL,
 answer TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS org_controls(run_id TEXT PRIMARY KEY, pause_requested INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS org_executions(
 run_id TEXT NOT NULL, path TEXT NOT NULL, input_hash TEXT NOT NULL, result TEXT NOT NULL,
 created_at TEXT NOT NULL, PRIMARY KEY(run_id,path));
CREATE TABLE IF NOT EXISTS org_runs(
 id TEXT PRIMARY KEY, provider TEXT NOT NULL, status TEXT NOT NULL,
 mission TEXT NOT NULL, roster TEXT NOT NULL, max_calls INTEGER NOT NULL,
 calls INTEGER NOT NULL DEFAULT 0, tokens INTEGER NOT NULL DEFAULT 0,
 result TEXT, error TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS org_calls(
 run_id TEXT NOT NULL REFERENCES org_runs(id), step_key TEXT NOT NULL, attempt INTEGER NOT NULL,
 agent_id TEXT NOT NULL, phase TEXT NOT NULL, input_hash TEXT NOT NULL, input TEXT NOT NULL,
 status TEXT NOT NULL, output TEXT, error TEXT, created_at TEXT NOT NULL,
 PRIMARY KEY(run_id,step_key,attempt));
CREATE TABLE IF NOT EXISTS org_messages(
 run_id TEXT NOT NULL REFERENCES org_runs(id), message_key TEXT NOT NULL, sender TEXT NOT NULL,
 recipient TEXT NOT NULL, kind TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(run_id,message_key));
CREATE TABLE IF NOT EXISTS org_artifacts(
 run_id TEXT NOT NULL REFERENCES org_runs(id), id TEXT NOT NULL, agent_id TEXT NOT NULL,
 task_key TEXT NOT NULL, path TEXT NOT NULL, content TEXT NOT NULL, sha256 TEXT NOT NULL,
 PRIMARY KEY(run_id,id), UNIQUE(run_id,path));
CREATE TABLE IF NOT EXISTS org_experience(
 run_id TEXT NOT NULL REFERENCES org_runs(id), agent_id TEXT NOT NULL, provider TEXT NOT NULL,
 content TEXT NOT NULL, PRIMARY KEY(run_id,agent_id));
'''


class DepartmentOrganization:
    def __init__(self, db_path, provider,concurrency=1,memory_enabled=True):
        self.concurrency=validate_concurrency(concurrency)
        if type(memory_enabled) is not bool:raise ValueError('memory_enabled must be boolean')
        self.memory_enabled=memory_enabled
        self.roster = {a['id']:a for a in build_roster()}
        self.db_path=Path(db_path)
        self.store = Store(Path(db_path))
        with self.store.transaction() as db:
            db.executescript(SCHEMA + budgets.SCHEMA + TOOL_SCHEMA + progress.SCHEMA + repairs.SCHEMA + learning.SCHEMA+POLICY_SCHEMA+assistance.SCHEMA)
            from .model_requests import ensure_columns
            ensure_columns(db,'org_calls')
        self.provider = provider

    @property
    def provider_signature(self):
        return encode({'mode':self.provider.name, 'model':getattr(self.provider,'model',None),
                       'url':getattr(self.provider,'url',None)})

    def close(self):
        self.store.close()

    def create(self, mission, max_calls=0, max_tokens=0, budget_id=None):
        mission = contracts.mission_contract(mission)
        if type(max_calls) is not int or max_calls<0:
            raise ValueError('max_calls must be nonnegative; zero means unlimited')
        run_id = 'org_' + uuid.uuid4().hex[:12]
        self.store.execute('INSERT INTO org_runs(id,provider,status,mission,roster,max_calls,created_at) VALUES(?,?,?,?,?,?,?)',
            (run_id,self.provider_signature,'ready',encode(mission),encode(self.roster),max_calls,now()))
        budget_id = budget_id or run_id
        budgets.create_budget(self.store,budget_id,max_calls,max_tokens)
        self.store.execute('INSERT INTO org_run_budgets VALUES(?,?)',(run_id,budget_id))
        self.store.execute('INSERT INTO org_execution_policy VALUES(?,?,?)',(run_id,self.concurrency,int(self.memory_enabled)))
        ConnectorManager(self.store,self.roster).bind(run_id,mission['allowed_capabilities'])
        return run_id

    def inspect(self, run_id):
        rows = self.store.query('SELECT * FROM org_runs WHERE id=?', (run_id,))
        if not rows:
            raise ValueError('Unknown departmental mission')
        run = rows[0]
        for field in ('mission','roster','result','provider'):
            run[field] = json.loads(run[field]) if run[field] else None
        return run

    def run(self, run_id):
        return replanning.run(self,run_id)

    def _run_once(self, run_id):
        run = self.inspect(run_id)
        if encode(run['provider']) != self.provider_signature:
            raise ValueError('Resume requires the original provider mode, model and endpoint')
        if run['status'] == 'reviewed':
            return run
        self.roster = run['roster']  # Frozen definitions keep historical work reproducible.
        frozen_policy=policy(self.store,run_id);self.concurrency=frozen_policy['concurrency'];self.memory_enabled=bool(frozen_policy['memory_enabled'])
        self.harness = AgentHarness(self.store, self.provider, self.roster)
        self.bus = LeadershipBus(self.store, self.roster)
        self.harness.help_handler=lambda *args:assistance.resolve(self,*args)
        self.store.execute("UPDATE org_runs SET status='running',error=NULL WHERE id=?", (run_id,))
        try:
            result = self._cycle(run_id, run['mission'])
            status = 'reviewed' if result['accepted'] else 'blocked'
            self.store.execute('UPDATE org_runs SET status=?,result=? WHERE id=?', (status,encode(result),run_id))
        except assistance.ReplanRequired:
            self.store.execute("UPDATE org_runs SET status='replanning',error=NULL WHERE id=?",(run_id,))
        except HumanInputRequired:
            self.store.execute("UPDATE org_runs SET status='needs_input' WHERE id=?", (run_id,))
        except RunPaused:
            self.store.execute("UPDATE org_runs SET status='paused' WHERE id=?", (run_id,))
        except Exception as error:
            self.store.execute("UPDATE org_runs SET status='blocked',error=? WHERE id=?", (str(error),run_id))
        return self.inspect(run_id)

    def _employees(self, department,provider_signature=None):
        broker=ToolBroker(self.store,self.roster)
        signature=self.provider_signature if provider_signature is None else provider_signature
        return [{**{k:a[k] for k in ('id','name','role','skills','responsibilities')},'responsibility_evidence':learning.responsibility(self.store,a['id'],signature),'eligible_tools':[t['name'] for t in broker.catalog(a['id']) if t['available']]}
                for a in self.roster.values() if a['department'] == department and a['role'] != 'department_lead']

    def _cycle(self, run_id, mission):
        call = lambda key, aid, phase, ctx, validator: self.harness.invoke(run_id,key,aid,phase,{'mission':mission,**ctx},validator)
        def validate_proposal(value,department):
            result=contracts.proposal(value,department,self.roster)
            assigned={department+'/'+path for task in result['tasks'] for path in task['outputs']}
            required={d['path'] for d in mission.get('deliverables',[]) if d['path'].startswith(department+'/')}
            if required-assigned:raise ValueError('Head must assign declared source deliverables: '+', '.join(sorted(required-assigned))+
                '. Assigned paths: '+(', '.join(sorted(assigned)) or '(none)')+'. task.outputs must use department-relative paths, e.g. index.html for engineering/index.html.')
            return result
        def validate_selection(value,proposals):
            result=contracts.selection(value,proposals)
            owners={d['path'].split('/')[0] for d in mission.get('deliverables',[])}
            if owners-set(result['departments']):raise ValueError('Director must include declared delivery owners: '+', '.join(sorted(owners-set(result['departments']))))
            return result
        send = lambda key, sender, recipient, kind, data: self.bus.send(run_id,key,sender,recipient,kind,data)
        proposals = {}
        queue = list(mission.get('departments', DEPARTMENT_MAP))
        while queue:
            department = queue.pop(0)
            if department in proposals:
                continue
            head = department+'-001'
            send('brief:'+department,'director-001',head,'mission.brief',mission)
            context = {'department':department, 'employees':self._employees(department),
                       'required_outputs':[d['path'].removeprefix(department+'/') for d in mission.get('deliverables',[]) if d['path'].startswith(department+'/')],
                       'available_capabilities':mission['allowed_capabilities'],'tool_catalog':ToolBroker(self.store,self.roster).catalog(),
                       'instruction':'Ask what useful contribution this department can make. You may decline unless you own a declared deliverable. Prefer one to three concrete tasks; at most six for complex work. Prioritize implementing declared source and integrating content over writing supporting plans or internal review documents. draft_artifact is a built-in JSON file-output capability, not an available_tools entry; no external tool is required for it. Assign optional tools in each task tools list only when useful; requires lists essential capabilities. Match tools to the employee eligible_tools and mission permissions. Request missing capabilities honestly.'}
            proposals[department] = call('assess:'+department,head,'assess',context,
                lambda v,d=department: validate_proposal(v,d))
            send('proposal:'+department,head,'director-001','department.proposal',proposals[department])
            queue.extend(d for d in proposals[department]['depends_on'] if d not in proposals)
        # An explicit head-to-head council: each receives only leadership-authored proposals.
        initial = proposals.copy()
        for department in initial:
            head = department+'-001'
            peers = {d:p for d,p in initial.items() if d != department}
            for peer, content in peers.items():
                send('council:'+peer+':'+department,peer+'-001',head,'council.proposal',content)
            proposals[department] = call('coordinate:'+department,head,'coordinate',{
                'department':department,'employees':self._employees(department),'own_proposal':initial[department],
                'required_outputs':[d['path'].removeprefix(department+'/') for d in mission.get('deliverables',[]) if d['path'].startswith(department+'/')],
                'head_proposals':peers,'instruction':'Revise or retain your proposal after discussing other heads proposals. Remove duplicated work. Declare department dependencies and use your own employees only. Decline if unnecessary.'},
                lambda v,d=department: validate_proposal(v,d))
            if set(proposals[department]['depends_on']) - set(initial):
                raise ValueError('Council requested an unconsulted department; revise the mission shortlist')
            send('coordinated:'+department,head,'director-001','department.coordinated',proposals[department])
        chosen = call('select','director-001','select',{'proposals':proposals,
            'instruction':'Select a coherent useful subset. Include every transitive department dependency; do not select a declined department. Verification will happen independently even if assurance does not propose deliverables.'},
            lambda v: validate_selection(v,proposals))
        order = contracts.topological({d:proposals[d]['depends_on'] for d in chosen['departments']})
        reports,blockers,workers=self._execute_team(run_id,mission,order,proposals,chosen,call,send)
        execution_results = self._execute_checks(run_id, mission)
        # One final leadership pass can resolve a concern that was true when an
        # upstream report was written but fulfilled by later departments.
        for department in order:
            if not reports[department]['blockers'] or any(b['department']==department for b in blockers):continue
            peers={d:r for d,r in reports.items() if d!=department}
            head=department+'-001';previous=reports[department]
            for peer,content in peers.items():send('integration-handoff:'+peer+':'+department,peer+'-001',head,'integration.handoff',content)
            employee_results={r['message_key'].split(':',2)[-1]:json.loads(r['content']) for r in self.store.query("SELECT message_key,content FROM org_messages WHERE run_id=? AND recipient=? AND kind='task.result' ORDER BY rowid",(run_id,head))}
            final_report=call('final_report:'+department,head,'report',{'department':department,'integration_review':True,
                'employee_results':employee_results,'artifact_ids':previous['artifact_ids'],'execution_evidence':execution_results,
                'saved_files':previous['published_artifacts'],'previous_report':previous,'head_reports':peers,
                'instruction':'All selected departments have finished this attempt. Reassess only your earlier integration concerns against the actual saved peer files and original acceptance criteria. Clear waiting-for-copy/source or pending-execution concerns only when the supplied current execution_evidence and peer sources actually fulfill them. Retain failed execution and missing evidence. Retain real unresolved original requirements. Do not invent extra requirements or claim unexecuted browser tests; optional unavailable tools are disclosed limitations. You cannot erase runtime task failures or missing permissions.'},
                lambda v,refs=previous['artifact_ids']:contracts.report(v,refs))
            reports[department]={**previous,**final_report,'integration_checked':True}
            send('integration-report:'+department,head,'director-001','department.final_report',reports[department])
        # Heads supply artifacts; the independent reviewer never bypasses its head.
        review_head = 'assurance-001'
        for department, content in reports.items():
            if department != 'assurance':
                send('verification-handoff:'+department,department+'-001',review_head,'verification.handoff',content)
        candidates = [a for a in self._employees('assurance') if a['id'] not in workers]
        def validate_assignment(value):
            if value.get('reviewer_id') not in {a['id'] for a in candidates}:
                raise ValueError('Assurance must choose an independent own-department employee')
            contracts.text(value.get('reason'),'review assignment reason',4000)
            return value
        assignment = call('review_assignment',review_head,'review_assignment',{'candidates':candidates,'head_reports':reports},validate_assignment)
        reviewer = assignment['reviewer_id']
        send('review-assignment',review_head,reviewer,'review.assignment',{'head_reports':reports,'acceptance_criteria':mission['acceptance_criteria']})
        verdict = call('review',reviewer,'review',{'head_reports':reports,'execution_evidence':execution_results,
            'instruction':'Inspect observed execution evidence where provided. Independently inspect saved artifacts against every original criterion; do not invent extra acceptance requirements. Only recorded sandbox checks count as execution; deployment and external verification are unavailable. A missing optional browser or hosting tool is a disclosed limitation, not proof that no source file exists. Give a reason and evidence for every original criterion.'},
            lambda v: contracts.review(v,mission['acceptance_criteria']))
        send('review-result',reviewer,review_head,'review.result',verdict)
        send('review-director',review_head,'director-001','verification.report',verdict)
        artifacts = self.store.query('SELECT id,path,content,sha256,agent_id FROM org_artifacts WHERE run_id=? ORDER BY path',(run_id,))
        check_errors = self._check_artifacts(mission,artifacts)
        check_errors.extend('Execution failed: '+e['path'] for e in execution_results if not e['result']['passed'])
        if any(r['blockers'] for r in reports.values()):
            check_errors.append('Department heads reported unresolved blockers')
        retrospective = call('retrospective','director-001','retrospective',{
            'head_reports':reports,'independent_review':verdict,'runtime_check_errors':check_errors,'blocked_tasks':blockers,
            'instruction':'Integrate the evidence and propose bounded, measurable organizational improvements. These are hypotheses, not permission, promotion, or automatic self-modification. Also return user_summary: a short, friendly reply to the user in plain language. Describe what was built, useful features, important limitations and any next action (such as replacing placeholder contact details). Do not include hashes, internal task IDs, Integrated outcome wording, department audit prose or acceptance-criterion counts in user_summary; keep technical evidence in summary and reports. Be candid when incomplete. Source inspection is not browser verification; never imply that preview, deployment, a backend or browser tests occurred without recorded evidence. Saved files and Preview are available through Files & activity when HTML exists.'},contracts.retrospective)
        for index, improvement in enumerate(retrospective['improvements']):
            send('improvement:'+str(index),'director-001',improvement['department']+'-001','improvement.proposed',improvement)
        return {'accepted':verdict['accepted'] and not blockers and not check_errors and bool(artifacts),
            'evidence_mode':self.provider.name,'scope':'Artifact review plus recorded JavaScript/SQL checks where requested; HTML checks are static; no deployment',
            'execution_results':execution_results,
            'consulted_departments':list(proposals),'selected_departments':chosen['departments'],'proposals':proposals,'reports':reports,
            'blocked_tasks':blockers,'reviewer':reviewer,'review':verdict,'check_errors':check_errors,
            'retrospective':retrospective,'artifact_count':len(artifacts)}

    def _execute_team(self,run_id,mission,order,proposals,chosen,call,send):
        jobs={};dependencies={}
        def begin(department,done):
            head=department+'-001';spec=proposals[department]
            send('selected:'+department,'director-001',head,'department.selected',{'reason':chosen['reason'],'proposal':spec})
            upstream={d:done['report:'+d] for d in spec['depends_on']}
            for peer,content in upstream.items():send('handoff:'+peer+':'+department,peer+'-001',head,'department.handoff',content)
            return upstream
        def work(department,task,done):
            head=department+'-001';agent_id=task['assignee'];key=task['key']
            upstream=done['begin:'+department]
            own={k:done['task:'+department+':'+k]['outcome'] for k in task['depends_on']}
            briefing={'task':task,'head_briefing':upstream,'own_dependencies':own}
            send('assignment:'+department+':'+key,head,agent_id,'task.assignment',briefing)
            broker=ToolBroker(self.store,self.roster)
            ready={item['name'] for item in broker.catalog(agent_id) if item['available']}
            missing=sorted(set(task['requires'])-set(mission['allowed_capabilities']))+sorted(set(task['requires'])-{'draft_artifact'}-ready)
            failed=any(v['status']=='blocked' for v in own.values());worker=None
            if missing or failed:
                reason='Required capabilities unavailable: '+', '.join(missing) if missing else 'Required task dependencies blocked: '+', '.join(k for k,v in own.items() if v['status']=='blocked')
                outcome={'status':'blocked','summary':reason,'limitations':missing or ['Dependency is blocked'],'capability_requests':missing,'artifacts':[]}
            else:
                worker=agent_id
                outcome=call('work:'+department+':'+key,agent_id,'work',briefing,lambda v:contracts.worker_result(v,task,department))
            prefix='work:'+department+':'+key+':tool:'
            evidence=self.store.query('SELECT name,arguments,result,created_at FROM org_tool_calls WHERE run_id=? AND substr(call_key,1,?)=? ORDER BY rowid',(run_id,len(prefix),prefix))
            for item in evidence:item['arguments']=json.loads(item['arguments']);item['result']=json.loads(item['result'])
            observed={item['name'] for item in evidence if item['result']['status']=='ok'}
            unobserved=set(task['requires'])-{'draft_artifact'}-observed
            if outcome['status']=='produced' and unobserved:outcome={'status':'blocked','summary':'Required tool evidence is missing','limitations':sorted(unobserved),'capability_requests':sorted(unobserved),'artifacts':[]}
            unavailable=[item['name']+': '+item['result']['status'] for item in evidence if item['result']['status'] not in {'ok','needs_input'} and item['name'] not in observed]
            outcome={**outcome,'limitations':list(dict.fromkeys(outcome['limitations']+unavailable)),'tool_evidence':evidence}
            send('result:'+department+':'+key,agent_id,head,'task.result',outcome)
            blocker={'department':department,'task':key,'reason':outcome['summary'],'kind':'missing_capability' if outcome['capability_requests'] else 'dependency' if failed else 'quality','capability_requests':outcome['capability_requests']} if outcome['status']=='blocked' else None
            ids=[]
            for artifact in outcome['artifacts']:
                path=department+'/'+artifact['path'];aid=department+':'+key+':'+artifact['path']
                self.store.execute('INSERT OR IGNORE INTO org_artifacts VALUES(?,?,?,?,?,?,?)',(run_id,aid,agent_id,key,path,artifact['content'],hashlib.sha256(artifact['content'].encode()).hexdigest()));ids.append(aid)
            return {'outcome':outcome,'worker':worker,'blocker':blocker,'artifact_ids':ids}
        def report(department,keys,done):
            head=department+'-001';items={k:done['task:'+department+':'+k] for k in keys}
            outcomes={k:v['outcome'] for k,v in items.items()};ids=[aid for v in items.values() for aid in v['artifact_ids']]
            blockers=[v['blocker'] for v in items.values() if v['blocker']]
            value=call('report:'+department,head,'report',{'department':department,'employee_results':outcomes,'artifact_ids':ids,
                'saved_files':self.store.query('SELECT id,path,sha256 FROM org_artifacts WHERE run_id=? AND path LIKE ? ORDER BY path',(run_id,department+'/%')),
                'instruction':'Collect every employee result, report actual progress, blockers and bounded improvements. Reference only supplied artifact IDs. Do not conceal failed tasks.'},lambda v:contracts.report(v,ids))
            value={**value,'tool_evidence':[e for v in outcomes.values() for e in v.get('tool_evidence',[])],
                'blockers':value['blockers']+[b['task']+': '+b['reason'] for b in blockers],
                'published_artifacts':self.store.query('SELECT id,path,content,sha256 FROM org_artifacts WHERE run_id=? AND path LIKE ? ORDER BY id',(run_id,department+'/%'))}
            send('report:'+department,head,'director-001','department.report',value)
            for peer in order:
                if peer!=department:send('progress:'+department+':'+peer,head,peer+'-001','department.progress',value)
            return value
        for department in order:
            bkey='begin:'+department
            jobs[bkey]=lambda done,d=department:begin(d,done)
            dependencies[bkey]=['report:'+d for d in proposals[department]['depends_on']]
            tasks={t['key']:t for t in proposals[department]['tasks']}
            keys=contracts.topological({k:t['depends_on'] for k,t in tasks.items()})
            for key in keys:
                job='task:'+department+':'+key;task=tasks[key]
                jobs[job]=lambda done,d=department,t=task:work(d,t,done)
                dependencies[job]=[bkey]+['task:'+department+':'+k for k in task['depends_on']]
            jobs['report:'+department]=lambda done,d=department,keys=keys:report(d,keys,done)
            dependencies['report:'+department]=['task:'+department+':'+k for k in keys]
        results=run_dag(jobs,dependencies,self.concurrency)
        reports={d:results['report:'+d] for d in order}
        workers={v['worker'] for key,v in results.items() if key.startswith('task:') and v['worker']}
        blockers=[v['blocker'] for key,v in results.items() if key.startswith('task:') and v['blocker']]
        return reports,blockers,workers

    def _execute_checks(self, run_id, mission):
        progress.record(self.store,run_id,None,'checks')
        from .sandbox import execute_javascript
        groups = {}
        for check in mission.get('execution_checks', []):
            groups.setdefault(check['path'], []).append({'expression':check['expression'],'expected':check.get('expected')})
        evidence = []
        for path, checks in groups.items():
            rows = self.store.query('SELECT content FROM org_artifacts WHERE run_id=? AND path=?', (run_id,path))
            source = rows[0]['content'] if rows else None
            digest = hashlib.sha256(encode({'source':source,'checks':checks}).encode()).hexdigest()
            prior = self.store.query('SELECT * FROM org_executions WHERE run_id=? AND path=?',(run_id,path))
            if prior:
                if prior[0]['input_hash'] != digest:
                    raise ValueError('Execution evidence input changed during resume')
                result = json.loads(prior[0]['result'])
            else:
                result = execute_javascript(source,checks) if source is not None else {'passed':False,'status':'missing_artifact','checks':[],'error':'Required source artifact is missing'}
                self.store.execute('INSERT INTO org_executions VALUES(?,?,?,?,?)',(run_id,path,digest,encode(result),now()))
            evidence.append({'path':path,'input_hash':digest,'result':result})
        data_groups={}
        for check in mission.get('data_checks',[]):data_groups.setdefault(check['path'],[]).append(check)
        from .data_execution import execute_sql
        for path,checks in data_groups.items():
            rows=self.store.query('SELECT content FROM org_artifacts WHERE run_id=? AND path=?',(run_id,path))
            source=rows[0]['content'] if rows else None
            digest=hashlib.sha256(encode({'source':source,'checks':checks}).encode()).hexdigest()
            prior=self.store.query('SELECT * FROM org_executions WHERE run_id=? AND path=?',(run_id,path))
            if prior:
                if prior[0]['input_hash']!=digest:raise ValueError('SQL evidence changed during resume')
                result=json.loads(prior[0]['result'])
            else:
                observed=[]
                for check in checks:
                    try:value=execute_sql(source,check['tables'])
                    except (ValueError,TypeError):value={'status':'failed','error':'Invalid or missing SQL artifact/data'}
                    observed.append({'passed':value['status']=='ok' and value.get('rows')==check['expected_rows'],
                        'expected':check['expected_rows'],'observed':value})
                result={'engine':'SQLite / in-memory read-only','passed':all(c['passed'] for c in observed),'checks':observed}
                self.store.execute('INSERT INTO org_executions VALUES(?,?,?,?,?)',(run_id,path,digest,encode(result),now()))
            evidence.append({'path':path,'input_hash':digest,'result':result})
        from .execution_adapters import execute_browser,execute_container
        files=self.store.query('SELECT path,content FROM org_artifacts WHERE run_id=? ORDER BY path',(run_id,))
        for kind,check in [('browser',c) for c in mission.get('browser_checks',[])]+[(c['profile'],c) for c in mission.get('runtime_checks',[])]:
            path=check['path'];entry=next((f for f in files if f['path']==path),None)
            # Acceptance uses only saved source, never arbitrary host paths.
            selected=[f for f in files if f['path'].split('/')[0]==path.split('/')[0]]
            digest=hashlib.sha256(encode({'files':selected,'check':check}).encode()).hexdigest();key=kind+':'+path
            prior=self.store.query('SELECT * FROM org_executions WHERE run_id=? AND path=?',(run_id,key))
            if prior:
                if prior[0]['input_hash']!=digest:raise ValueError('Runtime evidence inputs changed during resume')
                result=json.loads(prior[0]['result'])
            else:
                if not entry:result={'passed':False,'status':'missing_artifact','error':'Required saved runtime entry is missing'}
                elif kind=='browser':result=execute_browser(selected,path,check['checks'])
                else:
                    root=path.rsplit('/',1)[0]+'/'
                    project=[{'path':f['path'].removeprefix(root),'content':f['content']} for f in selected if f['path'].startswith(root)]
                    result=execute_container(kind,project,path.removeprefix(root))
                    if kind=='python':result={**result,'passed':bool(result['passed'] and result.get('stdout')==check['expected_stdout'])}
                self.store.execute('INSERT INTO org_executions VALUES(?,?,?,?,?)',(run_id,key,digest,encode(result),now()))
            evidence.append({'path':path,'kind':kind,'input_hash':digest,'result':result})
        return evidence

    @staticmethod
    def _check_artifacts(mission, artifacts):
        by_path = {a['path']:a for a in artifacts}
        errors = []
        declared=[{'path':d['path'],'type':'html' if d['kind']=='html' else 'exists'} for d in mission.get('deliverables',[])]
        for artifact in artifacts:
            if artifact['path'].endswith('.py'):
                import ast
                try:ast.parse(artifact['content'],filename=artifact['path'])
                except (SyntaxError,ValueError) as error:errors.append(artifact['path']+': Python source syntax is invalid'+(' at line '+str(error.lineno) if isinstance(error,SyntaxError) else ''))
            elif artifact['path'].endswith('.json'):
                try:json.loads(artifact['content'],parse_constant=lambda value:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
                except (ValueError,TypeError):errors.append(artifact['path']+': JSON source is invalid')
        for check in mission['artifact_checks']+declared:
            artifact = by_path.get(check['path'])
            if not artifact:
                errors.append('Missing required artifact: '+check['path'])
            elif check['type'] == 'contains' and check['text'] not in artifact['content']:
                errors.append('Required text missing from '+check['path'])
            elif check['type']=='html':
                from .html_checks import check_html
                errors.extend(check['path']+': '+error for error in check_html(artifact['content']))
        return errors

    def _remember(self, run_id, result):
        for row in self.store.query("SELECT agent_id,phase,output FROM org_calls WHERE run_id=? AND status='accepted'",(run_id,)):
            # Bounded episodic recall, not automatic skill/rank updates. Only reviewed missions qualify.
            output = json.loads(row['output'])
            summary = output.get('summary',output.get('reason','Reviewed contribution'))[:3000]
            content = encode({'phase':row['phase'],'summary':summary,'evidence_run':run_id,
                'objective':self.inspect(run_id)['mission']['objective'][:1500],
                'scope':'Prior reviewed work; not proof of executable capability or independent learning'})
            self.store.execute('INSERT OR REPLACE INTO org_experience VALUES(?,?,?,?)',
                (run_id,row['agent_id'],self.provider_signature,content))
            learning.consolidate(self.store,row['agent_id'],self.provider_signature,content,run_id)

    def export(self, run_id, output):
        run = self.inspect(run_id)
        run_id=repairs.run_ids(self.store,run_id)[-1]
        root = Path(output).resolve()
        root.mkdir(parents=True,exist_ok=True)
        # No existing artifact or source can be silently overwritten. Paths are rechecked after resolve.
        def write(relative, content):
            contracts.safe_path(relative)
            target = root.joinpath(*relative.split('/'))
            resolved = target.resolve()
            if not resolved.is_relative_to(root) or resolved == root:
                raise ValueError('Export target escaped output directory')
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():
                if target.read_text(encoding='utf-8') == content:
                    return
                raise FileExistsError('Export refuses to overwrite differing file: '+relative)
            with target.open('x',encoding='utf-8') as handle:
                handle.write(content)
        artifacts = self.store.query('SELECT * FROM org_artifacts WHERE run_id=? ORDER BY path',(run_id,))
        for artifact in artifacts:
            write('artifacts/'+artifact['path'],artifact['content'])
        messages = self.store.query('SELECT sender,recipient,kind,content FROM org_messages WHERE run_id=? ORDER BY rowid',(run_id,))
        for message in messages:
            message['content'] = json.loads(message['content'])
        run.pop('roster')
        write('organization.json',json.dumps({'run':run,'messages':messages,'artifacts':artifacts},indent=2))
        result = run.get('result') or {}
        content = '# Collective 101 organizational run\n\n'+f"Mode: {self.provider.name}. Status: {run['status']}. Calls: {run['calls']}.\n\n"+run['mission']['objective']+'\n\n'
        content += 'Scope: artifact review; inspect execution_results for observed JavaScript/SQL checks and tool_evidence for connector activity. No deployment.\n\n'
        content += result.get('retrospective',{}).get('summary',run.get('error') or 'No integrated result')+'\n\n'
        for department, report in result.get('reports',{}).items():
            content += '## '+department+'\n\n'+report['summary']+'\n\n'
        content += '## Artifacts\n\n'+'\n'.join('- '+a['path'] for a in artifacts)+'\n'
        write('REPORT.md',content)
        return root/'REPORT.md'
