"""Department-led organization with a replaceable, bounded artifact-drafting harness."""
import hashlib
import json
import uuid
from pathlib import Path
from .agent_harness import AgentHarness, LeadershipBus, HumanInputRequired, RunPaused
from . import org_contracts as contracts
from .registry import build_roster, DEPARTMENT_MAP
from .store import Store, encode, now, CallBudgetExceeded
from . import budgets
from . import progress
from . import repairs
from . import learning
from .agent_tools import SCHEMA as TOOL_SCHEMA, ToolBroker, eligible_tools
from .connectors import ConnectorManager

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
CREATE TABLE IF NOT EXISTS org_plan_changes(
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES org_runs(id), requested_by TEXT NOT NULL,
 proposal TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, decided_at TEXT);
'''


class PlanChangeApprovalRequired(RuntimeError):
    pass


class DepartmentOrganization:
    def __init__(self, db_path, provider):
        self.db_path=Path(db_path)
        self.store = Store(Path(db_path))
        with self.store.transaction() as db:
            db.executescript(SCHEMA + budgets.SCHEMA + TOOL_SCHEMA + progress.SCHEMA + repairs.SCHEMA + learning.SCHEMA)
        self.provider = provider
        self.roster = {a['id']:a for a in build_roster()}

    @property
    def provider_signature(self):
        return learning.provider_signature(self.provider)

    def close(self):
        self.store.close()

    def create(self, mission, max_calls=160, max_tokens=2000000, budget_id=None):
        mission = contracts.mission_contract(mission)
        if type(max_calls) is not int or not 1 <= max_calls <= 1000:
            raise ValueError('max_calls must be 1 to 1000')
        run_id = 'org_' + uuid.uuid4().hex[:12]
        self.store.execute('INSERT INTO org_runs(id,provider,status,mission,roster,max_calls,created_at) VALUES(?,?,?,?,?,?,?)',
            (run_id,self.provider_signature,'ready',encode(mission),encode(self.roster),max_calls,now()))
        budget_id = budget_id or run_id
        budgets.create_budget(self.store,budget_id,min(max_calls,160),max_tokens)
        self.store.execute('INSERT INTO org_run_budgets VALUES(?,?)',(run_id,budget_id))
        ConnectorManager(self.store,self.roster).bind(run_id,mission['allowed_capabilities'])
        return run_id

    def inspect(self, run_id):
        rows = self.store.query('SELECT * FROM org_runs WHERE id=?', (run_id,))
        if not rows:
            raise ValueError('Unknown departmental mission')
        run = rows[0]
        for field in ('mission','roster','result','provider'):
            run[field] = json.loads(run[field]) if run[field] else None
        changes=self.store.query('SELECT * FROM org_plan_changes WHERE run_id=?',(run_id,))
        run['plan_change_request']=None
        if changes:
            change=changes[0]
            run['plan_change_request']={**json.loads(change['proposal']),
                'id':change['id'],'requested_by':change['requested_by'],
                'status':change['status'],'created_at':change['created_at'],
                'decided_at':change['decided_at']}
        return run

    def run(self, run_id):
        return repairs.run_with_repairs(self,run_id)

    def decide_plan_change(self, run_id, change_id, decision):
        contracts.text(change_id,'plan change id',64)
        if not isinstance(decision,str) or decision not in {'approve','decline'}:
            raise ValueError('Plan change decision must be approve or decline')
        with self.store.transaction() as db:
            run=db.execute('SELECT status FROM org_runs WHERE id=?',(run_id,)).fetchone()
            if not run:
                raise ValueError('Unknown departmental mission')
            if run['status']!='needs_approval':
                raise ValueError('Mission is not awaiting plan-change approval')
            change=db.execute('SELECT proposal,status FROM org_plan_changes WHERE id=? AND run_id=?',
                (change_id,run_id)).fetchone()
            if not change or change['status']!='pending':
                raise ValueError('Plan change is not pending for this mission')
            status='approved' if decision=='approve' else 'declined'
            updated=db.execute('UPDATE org_plan_changes SET status=?,decided_at=? WHERE id=? AND status=?',
                (status,now(),change_id,'pending')).rowcount
            if updated!=1:
                raise ValueError('Plan change was already decided')
            db.execute('INSERT INTO org_messages VALUES(?,?,?,?,?,?,?)',
                (run_id,'plan-change-decision:'+change_id,'human-operator','director-001',
                 'mission.plan_change.decision',encode({'change_id':change_id,'decision':decision,
                     'proposal':json.loads(change['proposal'])}),now()))
        return self.inspect(run_id)

    def _run_once(self, run_id):
        run = self.inspect(run_id)
        if encode(run['provider']) != self.provider_signature:
            raise ValueError('Resume requires the original provider mode, model and endpoint')
        if run['status'] == 'reviewed':
            return run
        self.roster = run['roster']  # Frozen definitions keep historical work reproducible.
        self.harness = AgentHarness(self.store, self.provider, self.roster)
        self.bus = LeadershipBus(self.store, self.roster)
        self.store.execute("UPDATE org_runs SET status='running',error=NULL WHERE id=?", (run_id,))
        try:
            result = self._cycle(run_id, run['mission'])
            status = 'reviewed' if result['accepted'] else 'blocked'
            self.store.execute('UPDATE org_runs SET status=?,result=? WHERE id=?', (status,encode(result),run_id))
        except HumanInputRequired:
            self.store.execute("UPDATE org_runs SET status='needs_input' WHERE id=?", (run_id,))
        except RunPaused:
            self.store.execute("UPDATE org_runs SET status='paused' WHERE id=?", (run_id,))
        except PlanChangeApprovalRequired:
            self.store.execute("UPDATE org_runs SET status='needs_approval' WHERE id=?", (run_id,))
        except Exception as error:
            self.store.execute("UPDATE org_runs SET status='blocked',error=? WHERE id=?", (str(error),run_id))
        return self.inspect(run_id)

    def _employees(self, department, query=None):
        employees=[]
        for agent in self.roster.values():
            if agent['department']!=department or agent['role']=='department_lead':
                continue
            employee={**{key:agent[key] for key in ('id','name','role','skills','responsibilities')},
                'responsibility_evidence':learning.responsibility(self.store,agent['id'],self.provider_signature),
                'eligible_tools':[tool['name'] for tool in ToolBroker(self.store,self.roster).catalog(agent['id']) if tool['available']]}
            if query:
                evidence=learning.assignment_evidence(self.store,agent['id'],self.provider,query)
                if evidence:
                    employee['similar_task_evidence']=evidence
            employees.append(employee)
        return employees

    def _cycle(self, run_id, mission):
        repair_context=mission.get('_repair_context')
        public_mission={key:value for key,value in mission.items() if not key.startswith('_')}
        call = lambda key, aid, phase, ctx, validator: self.harness.invoke(run_id,key,aid,phase,{'mission':public_mission,**ctx},validator)
        send = lambda key, sender, recipient, kind, data: self.bus.send(run_id,key,sender,recipient,kind,data)
        proposals = {}
        assignment_evidence = []
        source_result=None
        affected_tasks=set()
        if repair_context:
            source_run=self.inspect(repair_context['source_run_id'])
            source_result=source_run['result']
            if not source_result or source_run['status']!='blocked':
                raise ValueError('Selective repair source is not a blocked run with review evidence')
            proposals=source_result.get('proposals',{})
            selected=source_result.get('selected_departments',[])
            if not proposals or not selected:
                raise ValueError('Selective repair source is missing its original department plan')
            chosen={'departments':selected,'reason':'Preserve the original selected department plan during selective repair.'}
            assignment_evidence.extend(source_result.get('assignment_evidence',[]))
            valid_tasks={(department,task['key']) for department,spec in proposals.items()
                for task in spec.get('tasks',[])}
            affected_tasks={(item['department'],item['key']) for item in repair_context.get('tasks',[])}
            if (not affected_tasks or affected_tasks-valid_tasks
                    or affected_tasks-{(department,task['key']) for department in selected
                        for task in proposals[department].get('tasks',[])}):
                raise ValueError('Selective repair scope does not match the original task plan')
            source_reports=source_result.get('reports',{})
        else:
            queue = list(mission.get('departments', DEPARTMENT_MAP))
            while queue:
                department = queue.pop(0)
                if department in proposals:
                    continue
                head = department+'-001'
                send('brief:'+department,'director-001',head,'mission.brief',public_mission)
                employees=self._employees(department,mission['objective'])
                assignment_evidence.extend({'department':department,'agent_id':employee['id'],
                    **employee['similar_task_evidence']} for employee in employees
                    if 'similar_task_evidence' in employee)
                context = {'department':department, 'employees':employees,
                           'available_capabilities':mission['allowed_capabilities'],'tool_catalog':ToolBroker(self.store,self.roster).catalog(),
                           'instruction':'Ask what useful contribution this department can make. You may decline. Assign at most six tasks to appropriate employees. Use similar_task_evidence only as advisory evidence when it fits the proposed task; it contains positive independently checked work, not a rank or guarantee. Lack of evidence means unknown, not poor performance. Choose the employee whose current skills and assignment fit best; you make the assignment. Assign optional tools in each task tools list only when useful; requires lists essential capabilities. Match tools to the employee eligible_tools and mission permissions. Request missing capabilities honestly.'}
                proposals[department] = call('assess:'+department,head,'assess',context,
                    lambda v,d=department: contracts.proposal(v,d,self.roster))
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
                    'department':department,'employees':self._employees(department,mission['objective']),'own_proposal':initial[department],
                    'head_proposals':peers,'instruction':'Revise or retain your proposal after discussing other heads proposals. Remove duplicated work. Use similar_task_evidence only as advisory evidence when it fits the proposed task; lack of evidence means unknown, not poor performance. Choose the employee whose current skills and assignment fit best; you make the assignment. Declare department dependencies and use your own employees only. Decline if unnecessary.'},
                    lambda v,d=department: contracts.proposal(v,d,self.roster))
                if set(proposals[department]['depends_on']) - set(initial):
                    raise ValueError('Council requested an unconsulted department; revise the mission shortlist')
                send('coordinated:'+department,head,'director-001','department.coordinated',proposals[department])
            chosen = call('select','director-001','select',{'proposals':proposals,
                'instruction':'Select a coherent useful subset. Include every transitive department dependency; do not select a declined department. Verification will happen independently even if assurance does not propose deliverables.'},
                lambda v: contracts.selection(v,proposals))
        order = contracts.topological({d:proposals[d]['depends_on'] for d in chosen['departments']})
        if repair_context:
            for artifact in self.store.query('SELECT * FROM org_artifacts WHERE run_id=? ORDER BY path',(repair_context['source_run_id'],)):
                ref=(artifact['path'].split('/',1)[0],artifact['task_key'])
                if ref in affected_tasks:
                    continue
                self.store.execute('INSERT INTO org_artifacts VALUES(?,?,?,?,?,?,?)',
                    (run_id,artifact['id'],artifact['agent_id'],artifact['task_key'],artifact['path'],artifact['content'],artifact['sha256']))
        reports, blockers, workers, replans, plan_changes = {}, [], set(), [], []
        for department_index, department in enumerate(order):
            head = department+'-001'
            spec = proposals[department]
            if repair_context and not any(item[0]==department for item in affected_tasks):
                if department not in source_reports:
                    raise ValueError('Selective repair source is missing an unaffected department report')
                for task in spec['tasks']:
                    if source_reports[department].get('employee_results',{}).get(task['key'],{}).get('status')=='produced':
                        workers.add(task['assignee'])
                head_report={**source_reports[department],'reused_from_run':repair_context['source_run_id']}
                reports[department]=head_report
                send('report:'+department,head,'director-001','department.report.reused',head_report)
                for peer in order:
                    if peer != department:
                        send('progress:'+department+':'+peer,head,peer+'-001','department.progress',head_report)
                continue
            send('selected:'+department,'director-001',head,'department.selected',{'reason':chosen['reason'],'proposal':spec})
            upstream = {d:reports[d] for d in spec['depends_on']}
            for peer, content in upstream.items():
                send('handoff:'+peer+':'+department,peer+'-001',head,'department.handoff',content)
            outcomes, department_artifacts = {}, []
            tasks = {t['key']:t for t in spec['tasks']}
            for key in contracts.topological({k:t['depends_on'] for k,t in tasks.items()}):
                task = tasks[key]
                agent_id = task['assignee']
                dependencies = {k:outcomes[k] for k in task['depends_on']}
                briefing = {'task':task,'head_briefing':upstream,'own_dependencies':dependencies}
                reused=bool(repair_context and (department,key) not in affected_tasks)
                if reused:
                    prior_outcomes=source_reports.get(department,{}).get('employee_results',{})
                    if key not in prior_outcomes:
                        raise ValueError('Selective repair source is missing an unaffected task result')
                    outcome={**prior_outcomes[key],'reused_from_run':repair_context['source_run_id']}
                    if outcome['status']=='produced':
                        workers.add(agent_id)
                else:
                    send('assignment:'+department+':'+key,head,agent_id,'task.assignment',briefing)
                    missing = sorted(set(task['requires']) - set(mission['allowed_capabilities']))
                    broker=ToolBroker(self.store,self.roster)
                    ready={item['name'] for item in broker.catalog(agent_id) if item['available']}
                    missing += sorted(set(task['requires']) - {'draft_artifact'} - ready)
                    failed_dependencies = any(v['status'] == 'blocked' for v in dependencies.values()) or any(reports[d]['blockers'] for d in spec['depends_on'])
                    if missing or failed_dependencies:
                        outcome = {'status':'blocked','summary':'Missing permitted capability or blocked dependency',
                            'limitations':missing or ['Dependency is blocked'], 'capability_requests':missing,'artifacts':[]}
                    else:
                        workers.add(agent_id)
                        outcome = call('work:'+department+':'+key,agent_id,'work',briefing,
                            lambda v,t=task: contracts.worker_result(v,t))
                    evidence=self.store.query("SELECT name,arguments,result,created_at FROM org_tool_calls WHERE run_id=? AND substr(call_key,1,?)=? ORDER BY rowid",(run_id,len('work:'+department+':'+key+':tool:'),'work:'+department+':'+key+':tool:'))
                    for item in evidence:
                        item['arguments']=json.loads(item['arguments']); item['result']=json.loads(item['result'])
                    observed={item['name'] for item in evidence if item['result']['status']=='ok'}
                    unobserved=set(task['requires'])-{'draft_artifact'}-observed
                    if outcome['status']=='produced' and unobserved:
                        outcome={'status':'blocked','summary':'Required tool evidence is missing','limitations':sorted(unobserved),'capability_requests':sorted(unobserved),'artifacts':[]}
                    unavailable=[item['name']+': '+item['result']['status'] for item in evidence if item['result']['status'] not in {'ok','needs_input'} and item['name'] not in observed]
                    outcome={**outcome,'limitations':list(dict.fromkeys(outcome['limitations']+unavailable)),'tool_evidence':evidence}
                outcomes[key] = outcome
                if not reused:
                    send('result:'+department+':'+key,agent_id,head,'task.result',outcome)
                if outcome['status'] == 'blocked':
                    blockers.append({'department':department,'task':key,'reason':outcome['summary'],
                                     'capability_requests':outcome['capability_requests']})
                if not reused:
                    for artifact in outcome['artifacts']:
                        path = department+'/'+artifact['path']
                        aid = department+':'+key+':'+artifact['path']
                        payload = (run_id,aid,agent_id,key,path,artifact['content'],hashlib.sha256(artifact['content'].encode()).hexdigest())
                        self.store.execute('INSERT OR IGNORE INTO org_artifacts VALUES(?,?,?,?,?,?,?)',payload)
                department_artifacts.extend(row['id'] for row in self.store.query(
                    'SELECT id FROM org_artifacts WHERE run_id=? AND task_key=? AND path LIKE ? ORDER BY id',
                    (run_id,key,department+'/%')))
            change_request_available=not repair_context and not replans and not plan_changes and bool(order[department_index+1:])
            def validate_report(value):
                result=contracts.report(value,department_artifacts,order[department_index+1:],
                    not repair_context and not replans and bool(order[department_index+1:]))
                request=result.get('change_request')
                if request is not None:
                    try:
                        if not change_request_available:
                            raise ValueError('Plan changes are unavailable after repair or when no selected departments remain')
                        if result.get('support_request'):
                            raise ValueError('A report may request passive support or a plan change, not both')
                        target=request.get('department') if isinstance(request,dict) else None
                        task=request.get('task') if isinstance(request,dict) else None
                        permitted=[]
                        if isinstance(task,dict) and isinstance(task.get('assignee'),str):
                            permitted=[item['name'] for item in ToolBroker(self.store,self.roster).catalog(
                                task['assignee']) if item['available']]
                        result={**result,'change_request':contracts.plan_change_request(
                            request,order[department_index+1:],chosen['departments'],proposals,
                            mission,self.roster,set(permitted)&set(mission['allowed_capabilities']))}
                    except (ValueError,TypeError,KeyError) as error:
                        result={**result,'change_request':None,
                            'change_request_status':{'status':'declined','reason':str(error)}}
                return result
            head_report = call('report:'+department,head,'report',{'department':department,
                'employee_results':outcomes, 'artifact_ids':department_artifacts,
                'pending_departments':order[department_index+1:],
                'support_request_available':change_request_available,
                'change_request_available':change_request_available,
                'instruction':'Collect every employee result and report actual progress, blockers and bounded improvements. Reference only supplied artifact IDs. Do not conceal failed tasks. If useful, either request passive support from one pending department or propose exactly one add_task change for an already-selected department in pending_departments; do not do both. The task must use that department’s existing employees and its current mission/tool permissions. A valid proposal pauses the mission for explicit human approval; it does not change the plan unless approved. You cannot change existing tasks, dependencies, mission criteria, capabilities, assignments, or budgets. Omit both requests when no change is necessary.'},
                validate_report)
            # Runtime blockers cannot be erased by a positive narrative.
            head_report = {**head_report,'employee_results':outcomes,'tool_evidence':[e for v in outcomes.values() for e in v.get('tool_evidence',[])],'blockers':head_report['blockers'] + [b['task']+': '+b['reason'] for b in blockers if b['department']==department],
                           'published_artifacts':self.store.query('SELECT id,path,content,sha256 FROM org_artifacts WHERE run_id=? AND path LIKE ? ORDER BY id',(run_id,department+'/%'))}
            reports[department] = head_report
            send('report:'+department,head,'director-001','department.report',head_report)
            rejected_change=head_report.get('change_request_status')
            if rejected_change:
                plan_changes.append({'requested_by':department,'status':'declined',
                    'reason':rejected_change['reason']})
            change_request=head_report.get('change_request')
            if change_request:
                existing=self.store.query('SELECT * FROM org_plan_changes WHERE run_id=?',(run_id,))
                if existing:
                    saved=existing[0]
                    if saved['requested_by']!=department or saved['proposal']!=encode(change_request):
                        raise ValueError('Recorded plan-change request changed during resume')
                    status=saved['status']
                    change_id=saved['id']
                else:
                    change_id='change_'+uuid.uuid4().hex[:12]
                    self.store.execute('INSERT INTO org_plan_changes VALUES(?,?,?,?,?,?,?)',
                        (change_id,run_id,department,encode(change_request),'pending',now(),None))
                    self.store.execute('INSERT INTO org_messages VALUES(?,?,?,?,?,?,?)',
                        (run_id,'plan-change-request:'+change_id,'director-001','human-operator',
                         'mission.plan_change.proposed',encode({'change_id':change_id,
                             'requested_by':department,'proposal':change_request}),now()))
                    status='pending'
                if status=='pending':
                    raise PlanChangeApprovalRequired('A department proposed a plan change; human approval is required')
                plan_changes.append({'id':change_id,'requested_by':department,
                    'status':status,'proposal':change_request})
                if status=='approved':
                    target=change_request['department']
                    original=proposals[target]
                    updated={**original,'tasks':[*original['tasks'],change_request['task']]}
                    proposals[target]=contracts.proposal(updated,target,self.roster)
            rejected_support=head_report.get('support_request_status')
            if rejected_support:
                send('support-outcome:'+department,'director-001',head,'department.support.outcome',rejected_support)
                replans.append({'requested_by':department,'department':None,'reason':rejected_support['reason'],
                    'related_task':None,'passive_insight':None,'employee_action_required':False,'status':'declined'})
            support_request=head_report.get('support_request')
            if support_request:
                target=support_request['department']
                target_head=target+'-001'
                send('support-request:'+department+':'+target,head,target_head,'department.support.request',{
                    'request':support_request,
                    'report':{'summary':head_report['summary'],'blockers':head_report['blockers'],
                        'artifact_ids':head_report['artifact_ids']}})
                original_proposal=proposals[target]
                try:
                    response=call('replan:'+department+':'+target,target_head,'replan',{
                        'department':target,'own_proposal':original_proposal,'support_request':support_request,
                        'requesting_department':department,
                        'requesting_report':{'summary':head_report['summary'],'blockers':head_report['blockers'],
                            'artifact_ids':head_report['artifact_ids']},
                        'instruction':"Decide whether to accept this request and provide a passive insight for the mission record, or decline it. An accepted insight must be a non-actionable observation of at most 500 characters about one existing task. It is not a work instruction, task context, assignment, or request for employees to act. Do not change any work, instructions, employees, task/dependency structure, tools, outputs, criteria or budgets."},
                        lambda v,p=original_proposal: contracts.support_response(v,p))
                except (HumanInputRequired,RunPaused,CallBudgetExceeded):
                    raise
                except (RuntimeError,ValueError,TypeError):
                    response=None
                if response is None:
                    outcome={'status':'unavailable','reason':'The receiving head could not provide a valid scoped response; the original plan was retained.'}
                    send('support-outcome:'+department,'director-001',head,'department.support.outcome',outcome)
                    replans.append({'requested_by':department,'department':target,'reason':support_request['reason'],
                        'related_task':None,'passive_insight':None,'employee_action_required':False,'status':'unavailable'})
                else:
                    if response['decision']=='accept':
                        passive_insight=response['passive_insight']
                        related_task=response['task_key']
                        status='advisory'
                    else:
                        passive_insight=None
                        related_task=None
                        status='declined'
                    send('support-replan:'+department+':'+target,target_head,head,'department.support.response',{
                        'department':target,'decision':response['decision'],'reason':response['reason'],
                        'related_task':related_task,'passive_insight':passive_insight,
                        'employee_action_required':False})
                    replans.append({'requested_by':department,'department':target,'reason':support_request['reason'],
                        'outcome_reason':response['reason'],'related_task':related_task,
                        'passive_insight':passive_insight,'employee_action_required':False,'status':status})
            for peer in order:
                if peer != department:
                    send('progress:'+department+':'+peer,head,peer+'-001','department.progress',head_report)
        execution_results = self._execute_checks(run_id, mission)
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
            'instruction':'Inspect observed execution evidence where provided. Independently inspect artifacts against every original criterion. Only recorded sandbox checks count as execution; deployment and external verification are unavailable. Give a reason and evidence for every criterion. For each unmet criterion, cite the exact artifact path or artifact ID that demonstrates the failure so a bounded repair can target it.'},
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
            'replans':replans,'approved_plan_changes':plan_changes,
            'instruction':'Integrate the evidence and propose bounded, measurable organizational improvements. These are hypotheses, not permission, promotion, or automatic self-modification.'},contracts.retrospective)
        for index, improvement in enumerate(retrospective['improvements']):
            send('improvement:'+str(index),'director-001',improvement['department']+'-001','improvement.proposed',improvement)
        result={'accepted':verdict['accepted'] and not blockers and not check_errors and bool(artifacts),
            'evidence_mode':self.provider.name,'scope':'Artifact review plus recorded JavaScript/SQL checks where requested; HTML checks are static; no deployment',
            'execution_results':execution_results,
            'consulted_departments':list(proposals),'selected_departments':chosen['departments'],'proposals':proposals,'reports':reports,
            'assignment_evidence':assignment_evidence,
            'blocked_tasks':blockers,'reviewer':reviewer,'review':verdict,'check_errors':check_errors,
            'replans':replans,'plan_changes':plan_changes,
            'retrospective':retrospective,'artifact_count':len(artifacts)}
        if repair_context:
            result['repair_scope']=[{'department':department,'key':key}
                for department,key in sorted(affected_tasks)]
            result['reused_tasks']=[{'department':department,'key':task['key']}
                for department in order for task in proposals[department]['tasks']
                if (department,task['key']) not in affected_tasks]
        return result

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
        return evidence

    @staticmethod
    def _check_artifacts(mission, artifacts):
        by_path = {a['path']:a for a in artifacts}
        errors = []
        for check in mission['artifact_checks']:
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
        if result.get('plan_changes'):
            content += '## Plan changes\n\n'
            for change in result['plan_changes']:
                task=change.get('proposal',{}).get('task',{})
                label=task.get('title') or change.get('reason') or 'Plan change'
                content += f"- {change['status']}: {label}\n"
            content += '\n'
        for department, report in result.get('reports',{}).items():
            content += '## '+department+'\n\n'+report['summary']+'\n\n'
        content += '## Artifacts\n\n'+'\n'.join('- '+a['path'] for a in artifacts)+'\n'
        write('REPORT.md',content)
        return root/'REPORT.md'
