import json,tempfile,unittest
from pathlib import Path
from collective101.department_runtime import DepartmentOrganization
from collective101.department_fixture import DepartmentFixtureProvider
from collective101.provider import Completion
from collective101 import repairs,budgets
ROOT=Path(__file__).resolve().parents[1]
def mission():
    return {'objective':'Draft a research note','departments':['research'],'inputs':{'fixture_scenario':'research'},'acceptance_criteria':['Include the correction'],'allowed_capabilities':['draft_artifact'],'artifact_checks':[{'type':'contains','path':'research/brief.md','text':'CORRECTED'}]}
class RepairProvider(DepartmentFixtureProvider):
    def complete(self,messages,tools=None):
        ctx=json.loads(messages[1]['content']);value=json.loads(super().complete(messages,tools).message['content'])
        if ctx['phase']=='work' and ctx['mission'].get('repair_feedback'):
            value['artifacts'][0]['content']+=' CORRECTED'
        return Completion({'role':'assistant','content':json.dumps(value)})
class SelectiveRepairProvider(DepartmentFixtureProvider):
    def __init__(self):self.work_calls=[]
    def complete(self,messages,tools=None):
        ctx=json.loads(messages[1]['content']);value=json.loads(super().complete(messages,tools).message['content'])
        if ctx['phase']=='assess' and ctx['department']=='research':
            value['tasks']=[
                {'key':'primary','title':'Draft the primary note','instructions':'Draft the primary note.',
                 'assignee':'research-003','depends_on':[],'requires':['draft_artifact'],'outputs':['brief.md']},
                {'key':'independent','title':'Draft an independent appendix','instructions':'Draft an independent appendix.',
                 'assignee':'research-004','depends_on':[],'requires':['draft_artifact'],'outputs':['appendix.md']},
                {'key':'dependent','title':'Draft dependent findings','instructions':'Use the primary note to draft findings.',
                 'assignee':'research-005','depends_on':['primary'],'requires':['draft_artifact'],'outputs':['findings.md']},
            ]
        elif ctx['phase']=='work':
            task_key=ctx['task']['key']
            repairing=bool(ctx['mission'].get('repair_feedback'))
            self.work_calls.append((repairing,task_key))
            if repairing and task_key in {'primary','dependent'}:
                value['artifacts'][0]['content']+=' CORRECTED'
        return Completion({'role':'assistant','content':json.dumps(value)})

class CrossDepartmentRepairProvider(DepartmentFixtureProvider):
    def __init__(self):self.work_calls=[]
    def complete(self,messages,tools=None):
        ctx=json.loads(messages[1]['content']);department=ctx.get('department')
        if ctx['phase']=='assess' and department=='research':
            value={'decision':'contribute','reason':'FIXTURE: prepare primary and independent research.',
                'depends_on':[],'tasks':[
                    {'key':'primary','title':'Draft primary note','instructions':'Draft primary note.',
                     'assignee':'research-003','depends_on':[],'requires':['draft_artifact'],'outputs':['brief.md']},
                    {'key':'independent','title':'Draft independent appendix','instructions':'Draft independent appendix.',
                     'assignee':'research-004','depends_on':[],'requires':['draft_artifact'],'outputs':['appendix.md']}]}
        elif ctx['phase']=='assess' and department=='strategy':
            value={'decision':'contribute','reason':'FIXTURE: plan from research.',
                'depends_on':['research'],'tasks':[
                    {'key':'options','title':'Compare options','instructions':'Use the research findings.',
                     'assignee':'strategy-004','depends_on':[],'requires':['draft_artifact'],'outputs':['options.md']}]}
        elif ctx['phase']=='work':
            value=json.loads(super().complete(messages,tools).message['content'])
            department=ctx['agent_id'].split('-',1)[0]
            task_key=ctx['task']['key'];repairing=bool(ctx['mission'].get('repair_feedback'))
            self.work_calls.append((repairing,department,task_key))
            if repairing:value['artifacts'][0]['content']+=' CORRECTED'
        else:
            value=json.loads(super().complete(messages,tools).message['content'])
        return Completion({'role':'assistant','content':json.dumps(value)})

class SupportReplanProvider(DepartmentFixtureProvider):
    def __init__(self,change_permissions=False,target='strategy',decision='accept',note=None):
        self.change_permissions=change_permissions;self.target=target;self.decision=decision;self.note=note
        self.replan_calls=0;self.strategy_instructions=[];self.strategy_passive_insights=[]
    def complete(self,messages,tools=None):
        ctx=json.loads(messages[1]['content'])
        if ctx['phase']=='report' and ctx['department']=='research':
            value=json.loads(super().complete(messages,tools).message['content'])
            value['support_request']={'department':self.target,'reason':'Include the new accessibility finding in the pending options.'}
        elif ctx['phase']=='replan':
            self.replan_calls+=1
            value={'decision':self.decision,'reason':'This response is recorded as passive insight only.',
                'task_key':ctx['own_proposal']['tasks'][0]['key'] if self.decision=='accept' else None,
                'passive_insight':self.note if self.note is not None else 'The accessibility finding may affect the options.' if self.decision=='accept' else ''}
            if self.change_permissions:value['requires']=['web_search']
        else:
            value=json.loads(super().complete(messages,tools).message['content'])
            if ctx['phase']=='work' and ctx['agent_id']=='strategy-004':
                self.strategy_instructions.append(ctx['task']['instructions'])
                self.strategy_passive_insights.append(ctx.get('passive_insight'))
        return Completion({'role':'assistant','content':json.dumps(value)})

class UnmappedReviewProvider(DepartmentFixtureProvider):
    def complete(self,messages,tools=None):
        ctx=json.loads(messages[1]['content']);value=json.loads(super().complete(messages,tools).message['content'])
        if ctx['phase']=='review':
            value['accepted']=False
            value['criteria'][0]={'criterion':ctx['mission']['acceptance_criteria'][0],
                'met':False,'evidence':'The deliverable is not sufficiently supported.'}
        return Completion({'role':'assistant','content':json.dumps(value)})

def plan_change_request():
    return {'kind':'add_task','department':'strategy',
        'reason':'Research found a material accessibility issue that needs a follow-up.',
        'task':{'key':'accessibility_followup','title':'Assess the accessibility finding',
            'instructions':'Assess the new accessibility finding and document its effect on the options.',
            'assignee':'strategy-005','depends_on':['deliverable'],
            'requires':['draft_artifact'],'tools':[],'outputs':['accessibility.md']}}

class PlanChangeProvider(DepartmentFixtureProvider):
    def __init__(self,request=None):
        self.request=plan_change_request() if request is None else request
        self.work_calls=[]
    def complete(self,messages,tools=None):
        ctx=json.loads(messages[1]['content'])
        value=json.loads(super().complete(messages,tools).message['content'])
        if ctx['phase']=='report' and ctx['department']=='research' and self.request is not None:
            value['change_request']=self.request
        if ctx['phase']=='work':
            self.work_calls.append((ctx['agent_id'].split('-',1)[0],ctx['task']['key']))
        return Completion({'role':'assistant','content':json.dumps(value)})

class Improvements(unittest.TestCase):
    def setUp(self):
        root=ROOT/'work/improvement-tests';root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root);self.org=DepartmentOrganization(Path(self.temp.name)/'state.db',RepairProvider())
    def tearDown(self):self.org.close();self.temp.cleanup()
    def test_repair_keeps_original_evidence_and_rechecks_under_same_budget(self):
        rid=self.org.create(mission());run=self.org.run(rid)
        self.assertEqual(run['status'],'reviewed',run['error']);ids=repairs.run_ids(self.org.store,rid);self.assertEqual(len(ids),2)
        before=self.org.store.query('SELECT content FROM org_artifacts WHERE run_id=?',(rid,))[0]['content']
        after=self.org.store.query('SELECT content FROM org_artifacts WHERE run_id=?',(ids[1],))[0]['content']
        self.assertNotIn('CORRECTED',before);self.assertIn('CORRECTED',after)
        self.assertEqual(self.org.inspect(ids[1])['mission']['acceptance_criteria'],mission()['acceptance_criteria'])
        used=budgets.inspect_budget(self.org.store,rid)['calls'];self.assertGreater(used,run['calls'])
        self.org.run(rid);self.assertEqual(budgets.inspect_budget(self.org.store,rid)['calls'],used)
    def test_selective_repair_reruns_failed_task_and_dependents_only(self):
        provider=SelectiveRepairProvider();self.org.provider=provider
        rid=self.org.create(mission());run=self.org.run(rid)
        self.assertEqual(run['status'],'reviewed',run['error'])
        ids=repairs.run_ids(self.org.store,rid);self.assertEqual(len(ids),2)
        original={row['path']:row['content'] for row in self.org.store.query(
            'SELECT path,content FROM org_artifacts WHERE run_id=?',(ids[0],))}
        repaired={row['path']:row['content'] for row in self.org.store.query(
            'SELECT path,content FROM org_artifacts WHERE run_id=?',(ids[1],))}
        self.assertEqual(original['research/appendix.md'],repaired['research/appendix.md'])
        self.assertIn('CORRECTED',repaired['research/brief.md'])
        self.assertIn('CORRECTED',repaired['research/findings.md'])
        repair_calls=[key for repairing,key in provider.work_calls if repairing]
        self.assertCountEqual(repair_calls,['primary','dependent'])
        self.assertEqual(run['result']['repair_scope'],[
            {'department':'research','key':'dependent'},{'department':'research','key':'primary'}])
        self.assertEqual(run['result']['reused_tasks'],[{'department':'research','key':'independent'}])
        self.assertEqual(self.org.store.query("SELECT COUNT(*) AS count FROM org_calls WHERE run_id=? AND phase='review' AND status='accepted'",
            (ids[1],))[0]['count'],1)
        self.assertEqual(self.org.store.query('SELECT content FROM org_artifacts WHERE run_id=? AND path=?',
            (ids[0],'research/brief.md'))[0]['content'],original['research/brief.md'])
    def test_selective_repair_includes_downstream_departments_only(self):
        provider=CrossDepartmentRepairProvider();self.org.provider=provider
        m=mission();m['departments']=['research','strategy']
        rid=self.org.create(m);run=self.org.run(rid)
        self.assertEqual(run['status'],'reviewed',run['error'])
        ids=repairs.run_ids(self.org.store,rid);self.assertEqual(len(ids),2)
        repair_calls=[(department,key) for repairing,department,key in provider.work_calls if repairing]
        self.assertCountEqual(repair_calls,[('research','primary'),('strategy','options')])
        self.assertEqual(run['result']['repair_scope'],[
            {'department':'research','key':'primary'},{'department':'strategy','key':'options'}])
        self.assertEqual(run['result']['reused_tasks'],[{'department':'research','key':'independent'}])
        original={row['path']:row['content'] for row in self.org.store.query(
            'SELECT path,content FROM org_artifacts WHERE run_id=?',(ids[0],))}
        repaired={row['path']:row['content'] for row in self.org.store.query(
            'SELECT path,content FROM org_artifacts WHERE run_id=?',(ids[1],))}
        self.assertEqual(original['research/appendix.md'],repaired['research/appendix.md'])
        self.assertIn('CORRECTED',repaired['strategy/options.md'])
    def test_mid_mission_support_is_passive_and_never_reaches_worker(self):
        provider=SupportReplanProvider();self.org.provider=provider
        m=mission();m.update(departments=['research','strategy'],artifact_checks=[],max_repair_rounds=0)
        rid=self.org.create(m);run=self.org.run(rid)
        self.assertEqual(run['status'],'reviewed',run['error'])
        self.assertEqual(provider.replan_calls,1)
        self.assertEqual(len(provider.strategy_instructions),1)
        self.assertEqual(provider.strategy_instructions[0],run['result']['proposals']['strategy']['tasks'][0]['instructions'])
        self.assertIsNone(provider.strategy_passive_insights[0])
        self.assertEqual(run['result']['replans'],[{
            'requested_by':'research','department':'strategy',
            'reason':'Include the new accessibility finding in the pending options.',
            'outcome_reason':'This response is recorded as passive insight only.',
            'related_task':'deliverable',
            'passive_insight':'The accessibility finding may affect the options.',
            'employee_action_required':False,'status':'advisory'}])
        self.assertEqual(run['result']['proposals']['strategy']['tasks'][0]['requires'],['draft_artifact'])
        messages=self.org.store.query("SELECT sender,recipient,kind FROM org_messages WHERE run_id=? AND kind LIKE 'department.support.%' ORDER BY rowid",(rid,))
        self.assertEqual([(row['sender'],row['recipient'],row['kind']) for row in messages],[
            ('research-001','strategy-001','department.support.request'),
            ('strategy-001','research-001','department.support.response')])
        response=json.loads(self.org.store.query("SELECT content FROM org_messages WHERE run_id=? AND kind='department.support.response'",(rid,))[0]['content'])
        self.assertFalse(response['employee_action_required'])
        self.assertIn('accessibility finding',response['passive_insight'])
        self.assertEqual(self.org.store.query("SELECT COUNT(*) AS count FROM org_calls WHERE run_id=? AND phase='replan' AND status='accepted'",(rid,))[0]['count'],1)

    def test_mid_mission_support_decline_keeps_original_plan_and_continues(self):
        provider=SupportReplanProvider(decision='decline');self.org.provider=provider
        m=mission();m.update(departments=['research','strategy'],artifact_checks=[],max_repair_rounds=0)
        run=self.org.run(self.org.create(m))
        self.assertEqual(run['status'],'reviewed',run['error'])
        self.assertEqual(provider.strategy_instructions[0],run['result']['proposals']['strategy']['tasks'][0]['instructions'])
        self.assertIsNone(provider.strategy_passive_insights[0])
        self.assertEqual(run['result']['replans'][0]['status'],'declined')
        self.assertEqual(run['result']['replans'][0]['passive_insight'],None)
        message=self.org.store.query("SELECT content FROM org_messages WHERE kind='department.support.response'")[0]
        self.assertEqual(json.loads(message['content'])['decision'],'decline')

    def test_mid_mission_support_rejects_scope_expansion_and_preserves_original_plan(self):
        provider=SupportReplanProvider(note='x'*501);self.org.provider=provider
        m=mission();m.update(departments=['research','strategy'],artifact_checks=[],max_repair_rounds=0)
        run=self.org.run(self.org.create(m))
        self.assertEqual(run['status'],'reviewed',run['error'])
        self.assertEqual(run['result']['replans'][0]['status'],'unavailable')
        self.assertIsNone(run['result']['replans'][0]['passive_insight'])
        self.assertEqual(provider.strategy_instructions[0],run['result']['proposals']['strategy']['tasks'][0]['instructions'])
        self.assertIsNone(provider.strategy_passive_insights[0])

    def test_mid_mission_replan_cannot_expand_tool_permissions(self):
        provider=SupportReplanProvider(change_permissions=True);self.org.provider=provider
        m=mission();m.update(departments=['research','strategy'],artifact_checks=[],max_repair_rounds=0)
        run=self.org.run(self.org.create(m))
        self.assertEqual(run['status'],'reviewed',run['error'])
        self.assertEqual(run['result']['replans'][0]['status'],'unavailable')
        self.assertEqual(run['result']['proposals']['strategy']['tasks'][0]['requires'],['draft_artifact'])
        self.assertEqual(provider.strategy_instructions[0],run['result']['proposals']['strategy']['tasks'][0]['instructions'])
        self.assertIsNone(provider.strategy_passive_insights[0])

    def test_mid_mission_replan_provider_failure_keeps_original_plan_and_continues(self):
        from collective101.provider import ProviderError
        class FailingHead(SupportReplanProvider):
            def __init__(self):
                super().__init__()
                self.failed_attempts=0
            def complete(self,messages,tools=None):
                if json.loads(messages[1]['content'])['phase']=='replan':
                    self.failed_attempts+=1
                    raise ProviderError('provider request timed out',retryable=True)
                return super().complete(messages,tools)
        provider=FailingHead();self.org.provider=provider
        m=mission();m.update(departments=['research','strategy'],artifact_checks=[],max_repair_rounds=0)
        run=self.org.run(self.org.create(m))
        self.assertEqual(run['status'],'reviewed',run['error'])
        self.assertEqual(provider.failed_attempts,2)
        self.assertEqual(run['result']['replans'][0]['status'],'unavailable')
        self.assertEqual(provider.strategy_instructions[0],run['result']['proposals']['strategy']['tasks'][0]['instructions'])
        self.assertIsNone(provider.strategy_passive_insights[0])
        outcome=self.org.store.query("SELECT sender,kind,content FROM org_messages WHERE kind='department.support.outcome'")[0]
        self.assertEqual((outcome['sender'],outcome['kind']),('director-001','department.support.outcome'))
        self.assertIn('original plan was retained',json.loads(outcome['content'])['reason'])

    def test_mid_mission_support_cannot_target_unselected_department(self):
        self.org.provider=SupportReplanProvider(target='assurance')
        m=mission();m.update(departments=['research','strategy'],artifact_checks=[],max_repair_rounds=0)
        run=self.org.run(self.org.create(m))
        self.assertEqual(run['status'],'reviewed',run['error'])
        self.assertEqual(run['result']['replans'][0]['status'],'declined')
        self.assertIn('selected department that has not started',run['result']['replans'][0]['reason'])
        self.assertEqual(self.org.store.query("SELECT * FROM org_calls WHERE phase='replan'"),[])
    def test_mid_mission_replan_resumes_after_head_authored_question(self):
        class AskingHead(SupportReplanProvider):
            def complete(self,messages,tools=None):
                ctx=json.loads(messages[1]['content'])
                if ctx['phase']=='replan' and not ctx['human_answers']:
                    return Completion({'role':'assistant','content':json.dumps({
                        'intervention':{'question':'Should the options include this finding?',
                            'reason':'The answer changes how the pending options are compared.','options':[]}})})
                return super().complete(messages,tools)
        provider=AskingHead();self.org.provider=provider
        m=mission();m.update(departments=['research','strategy'],artifact_checks=[],max_repair_rounds=0)
        rid=self.org.create(m);run=self.org.run(rid)
        self.assertEqual(run['status'],'needs_input',run['error'])
        self.org.store.execute("UPDATE org_interventions SET status='answered',answer='Yes' WHERE run_id=?",(rid,))
        run=self.org.run(rid)
        self.assertEqual(run['status'],'reviewed',run['error'])
        self.assertEqual(provider.replan_calls,1)
        self.assertEqual(len(self.org.store.query("SELECT * FROM org_messages WHERE run_id=? AND kind='department.support.request'",(rid,))),1)
        self.assertIsNone(provider.strategy_passive_insights[0])
        self.assertEqual(run['result']['replans'][0]['status'],'advisory')

    def test_plan_change_waits_for_explicit_human_approval(self):
        provider=PlanChangeProvider();self.org.provider=provider
        m=mission();m.update(departments=['research','strategy'],inputs={'fixture_scenario':'research'},
            artifact_checks=[],max_repair_rounds=0)
        rid=self.org.create(m);run=self.org.run(rid)
        self.assertEqual(run['status'],'needs_approval',run['error'])
        change=run['plan_change_request']
        self.assertEqual(change['status'],'pending')
        self.assertEqual(change['task'],plan_change_request()['task'])
        self.assertEqual(provider.work_calls,[('research','deliverable')])
        with self.assertRaisesRegex(ValueError,'not pending'):
            self.org.decide_plan_change(rid,'change_not_this_run','approve')
        with self.assertRaisesRegex(ValueError,'decision must be'):
            self.org.decide_plan_change(rid,change['id'],'skip')
        calls=run['calls']
        self.assertEqual(self.org.run(rid)['status'],'needs_approval')
        self.assertEqual(self.org.inspect(rid)['calls'],calls)
        self.assertEqual(provider.work_calls,[('research','deliverable')])
        self.assertEqual(self.org.store.query("SELECT COUNT(*) AS n FROM org_messages WHERE run_id=? AND kind='mission.plan_change.proposed'",(rid,))[0]['n'],1)

    def test_pending_plan_change_survives_runtime_reopen(self):
        provider=PlanChangeProvider();self.org.provider=provider
        m=mission();m.update(departments=['research','strategy'],inputs={'fixture_scenario':'research'},
            artifact_checks=[],max_repair_rounds=0)
        rid=self.org.create(m);pending=self.org.run(rid)
        state=self.org.db_path
        self.org.close()
        self.org=DepartmentOrganization(state,provider)
        resumed=self.org.inspect(rid)
        self.assertEqual(resumed['status'],'needs_approval')
        self.assertEqual(resumed['plan_change_request']['id'],pending['plan_change_request']['id'])
        self.assertEqual(resumed['plan_change_request']['status'],'pending')
        self.org.decide_plan_change(rid,resumed['plan_change_request']['id'],'approve')
        self.assertEqual(self.org.run(rid)['status'],'reviewed')
        self.assertIn(('strategy','accessibility_followup'),provider.work_calls)

    def test_approved_plan_change_adds_only_the_reviewed_task(self):
        provider=PlanChangeProvider();self.org.provider=provider
        m=mission();m.update(departments=['research','strategy'],inputs={'fixture_scenario':'research'},
            artifact_checks=[],max_repair_rounds=0)
        rid=self.org.create(m);pending=self.org.run(rid)
        self.org.decide_plan_change(rid,pending['plan_change_request']['id'],'approve')
        run=self.org.run(rid)
        self.assertEqual(run['status'],'reviewed',run['error'])
        self.assertEqual(run['result']['proposals']['strategy']['tasks'][0]['key'],'deliverable')
        self.assertEqual(run['result']['proposals']['strategy']['tasks'][1],plan_change_request()['task'])
        self.assertEqual(provider.work_calls,[('research','deliverable'),('strategy','deliverable'),('strategy','accessibility_followup')])
        self.assertEqual(run['result']['plan_changes'][0]['status'],'approved')
        self.assertEqual(run['mission']['acceptance_criteria'],m['acceptance_criteria'])
        self.assertEqual(run['mission']['allowed_capabilities'],m['allowed_capabilities'])
        decision=self.org.store.query("SELECT sender,recipient,kind,content FROM org_messages WHERE run_id=? AND kind='mission.plan_change.decision'",(rid,))[0]
        self.assertEqual((decision['sender'],decision['recipient']),('human-operator','director-001'))
        self.assertEqual(json.loads(decision['content'])['decision'],'approve')
        with self.assertRaisesRegex(ValueError,'not awaiting'):
            self.org.decide_plan_change(rid,pending['plan_change_request']['id'],'decline')

    def test_declined_plan_change_continues_the_original_plan_unchanged(self):
        provider=PlanChangeProvider();self.org.provider=provider
        m=mission();m.update(departments=['research','strategy'],inputs={'fixture_scenario':'research'},
            artifact_checks=[],max_repair_rounds=0)
        rid=self.org.create(m);pending=self.org.run(rid)
        self.org.decide_plan_change(rid,pending['plan_change_request']['id'],'decline')
        run=self.org.run(rid)
        self.assertEqual(run['status'],'reviewed',run['error'])
        self.assertEqual([task['key'] for task in run['result']['proposals']['strategy']['tasks']],['deliverable'])
        self.assertEqual(provider.work_calls,[('research','deliverable'),('strategy','deliverable')])
        self.assertEqual(run['result']['plan_changes'][0]['status'],'declined')

    def test_invalid_plan_change_is_recorded_and_cannot_expand_scope_or_permissions(self):
        invalid_requests=[]
        request=plan_change_request();request['department']='assurance';invalid_requests.append(request)
        request=plan_change_request();request['task']['assignee']='engineering-003';invalid_requests.append(request)
        request=plan_change_request();request['task']['requires']=['web_search'];invalid_requests.append(request)
        request=plan_change_request();request['task']['outputs']=['options.md'];invalid_requests.append(request)
        request=plan_change_request();request['task']['depends_on']=['unknown'];invalid_requests.append(request)
        for index,request in enumerate(invalid_requests):
            with self.subTest(request=request):
                provider=PlanChangeProvider(request);self.org.provider=provider
                m=mission();m.update(departments=['research','strategy'],inputs={'fixture_scenario':'research'},
                    artifact_checks=[],max_repair_rounds=0)
                run=self.org.run(self.org.create(m))
                self.assertEqual(run['status'],'reviewed',run['error'])
                self.assertIsNone(run['plan_change_request'])
                self.assertEqual(run['result']['plan_changes'][0]['status'],'declined')
                self.assertEqual([task['key'] for task in run['result']['proposals']['strategy']['tasks']],['deliverable'])
                self.assertEqual(provider.work_calls,[('research','deliverable'),('strategy','deliverable')])
    def test_unmapped_review_failure_stays_blocked_without_blind_repair(self):
        self.org.provider=UnmappedReviewProvider();m=mission();m['artifact_checks']=[]
        rid=self.org.create(m);run=self.org.run(rid)
        self.assertEqual(run['status'],'blocked')
        self.assertEqual(repairs.run_ids(self.org.store,rid),[rid])
        self.assertIn('cannot safely identify',run['result']['repair_blocked_reason'])
    def test_failed_repair_is_bounded_and_does_not_create_success_memory(self):
        self.org.provider=DepartmentFixtureProvider();rid=self.org.create(mission());run=self.org.run(rid)
        self.assertEqual(run['status'],'blocked');self.assertEqual(len(repairs.run_ids(self.org.store,rid)),2)
        self.assertEqual(self.org.store.query('SELECT * FROM org_experience'),[])
    def test_repair_cannot_reset_exhausted_budget(self):
        rid=self.org.create(mission(),max_calls=8);self.org.run(rid)
        self.assertLessEqual(budgets.inspect_budget(self.org.store,rid)['calls'],8)
        self.assertNotEqual(self.org.inspect(rid)['status'],'reviewed')
    def test_repair_human_question_resumes_same_revision(self):
        class Asking(RepairProvider):
            def complete(self,messages,tools=None):
                ctx=json.loads(messages[1]['content'])
                if ctx['phase']=='work' and ctx['mission'].get('repair_feedback') and not ctx['human_answers']:
                    return Completion({'role':'assistant','content':json.dumps({'intervention':{'question':'Use the revised wording?','reason':'Confirm the wording change.','options':[]}})})
                return super().complete(messages,tools)
        self.org.provider=Asking();rid=self.org.create(mission());run=self.org.run(rid)
        self.assertEqual(run['status'],'needs_input',run['error']);ids=repairs.run_ids(self.org.store,rid)
        self.org.store.execute("UPDATE org_interventions SET status='answered',answer='Yes' WHERE run_id=?",(ids[-1],))
        run=self.org.run(rid);self.assertEqual(run['status'],'reviewed',run['error']);self.assertEqual(repairs.run_ids(self.org.store,rid),ids)
    def test_progress_contains_action_metadata_not_model_content(self):
        from collective101 import progress
        rid=self.org.create(mission());progress.record(self.org.store,rid,'research-001','assess')
        value=progress.current(self.org.store,rid,self.org.roster)
        self.assertIn('Assessing',value['label']);self.assertEqual(value['agent_id'],'research-001');self.assertNotIn('content',value)

    def test_knowledge_ingestion_is_bounded_deduplicated_and_retrievable(self):
        from collective101.knowledge import ingest
        from collective101.agent_tools import ToolBroker
        root=Path(self.temp.name)/'knowledge';one=ingest('guide.md','Onboarding starts with a welcome meeting.',root)
        self.assertEqual(ingest('guide.md','Onboarding starts with a welcome meeting.',root),one)
        broker=ToolBroker(self.org.store,self.org.roster,root)
        self.assertIn('welcome',broker._read(one['path'],'research')['content'])
        for name in ('../secret.md','x.py','/absolute.md'):
            with self.assertRaises(ValueError):ingest(name,'data',root)
        with self.assertRaises(ValueError):ingest('huge.txt','x'*65537,root)
    def test_memory_consolidation_deduplicates_and_isolates_sources(self):
        from collective101.learning import consolidate,recall_cards
        content=json.dumps({'objective':'onboarding guide','phase':'work','summary':'Reviewed onboarding guidance'})
        for rid in ('a','b','a'):consolidate(self.org.store,'research-003','fixture',content,rid)
        cards=recall_cards(self.org.store,'research-003','fixture','c','onboarding')
        self.assertEqual(len(cards),1);self.assertEqual(cards[0]['evidence_runs'],['a','b'])
        self.assertEqual(recall_cards(self.org.store,'research-004','fixture','c','onboarding'),[])
        self.assertEqual(recall_cards(self.org.store,'research-003','meta','c','onboarding'),[])
    def test_assignment_evidence_uses_only_live_accepted_checked_own_outputs(self):
        from collective101 import learning
        class EvidenceProvider:
            name='meta'
            model='evidence-test'
            url='https://model.example.test/v1'
        self.org.provider=EvidenceProvider()
        objective='Write an accessible onboarding guide for remote team members'
        task={'key':'guide','title':'Write accessible onboarding guide',
            'instructions':'Create an accessible onboarding guide for remote team members.',
            'assignee':'research-003','outputs':['brief.md']}
        unverified={'key':'appendix','title':'Write an accessible onboarding appendix',
            'instructions':'Create an accessible onboarding appendix for remote team members.',
            'assignee':'research-004','outputs':['appendix.md']}
        run_ids=[]
        for index in range(2):
            current_mission=mission();current_mission['objective']=objective
            rid=self.org.create(current_mission);run_ids.append(rid)
            self.org.store.execute('INSERT INTO org_artifacts VALUES(?,?,?,?,?,?,?)',
                (rid,'research:guide:brief.md','research-003','guide','research/brief.md','CORRECTED content','digest'))
            self.org.store.execute('INSERT INTO org_artifacts VALUES(?,?,?,?,?,?,?)',
                (rid,'research:appendix:appendix.md','research-004','appendix','research/appendix.md','Unverified content','digest'))
            result={'accepted':True,'check_errors':[],'execution_results':[],
                'proposals':{'research':{'tasks':[task,unverified]}}}
            learning.record_task_evidence(self.org,rid,rid,result)
        evidence=learning.assignment_evidence(self.org.store,'research-003',self.org.provider,objective)
        self.assertEqual(evidence['similar_verified_tasks'],2)
        self.assertEqual(evidence['verified_missions'],2)
        self.assertEqual(evidence['history_strength'],'repeated')
        self.assertCountEqual(evidence['evidence_runs'],run_ids)
        self.assertIsNone(learning.assignment_evidence(self.org.store,'research-004',self.org.provider,objective))
        self.assertIsNone(learning.assignment_evidence(self.org.store,'research-003',self.org.provider,
            'Create a financial forecast for the next fiscal quarter'))
        different_provider=EvidenceProvider();different_provider.model='other-model'
        self.assertIsNone(learning.assignment_evidence(self.org.store,'research-003',different_provider,objective))
        employee=next(agent for agent in self.org._employees('research',objective) if agent['id']=='research-003')
        self.assertEqual(employee['similar_task_evidence'],evidence)
        self.assertNotIn('similar_task_evidence',
            next(agent for agent in self.org._employees('research',objective) if agent['id']=='research-004'))

        rejected_mission=mission();rejected_mission['objective']=objective
        rejected=self.org.create(rejected_mission)
        learning.record_task_evidence(self.org,rejected,rejected,{'accepted':False,'proposals':{'research':{'tasks':[task]}}})
        self.assertEqual(learning.assignment_evidence(self.org.store,'research-003',self.org.provider,objective)['verified_missions'],2)

        self.org.provider=RepairProvider()
        fixture=self.org.create(rejected_mission)
        learning.record_task_evidence(self.org,fixture,fixture,{'accepted':True,'proposals':{'research':{'tasks':[task]}}})
        self.assertIsNone(learning.assignment_evidence(self.org.store,'research-003',self.org.provider,objective))
    def test_responsibility_ignores_fixtures_and_duplicate_objectives_and_never_grants_tools(self):
        from collective101.learning import responsibility
        for i in range(4):
            self.org.store.execute('INSERT INTO org_contribution_evidence VALUES(?,?,?,?,?,?,?,?,?,?)',(str(i),'research-003','meta',str(i),1,1,0,0,str(i),str(i)))
        self.assertEqual(responsibility(self.org.store,'research-003')['level'],'developing')
        self.org.store.execute('UPDATE org_contribution_evidence SET live=1')
        self.assertEqual(responsibility(self.org.store,'research-003')['level'],'trusted_contributor')
        self.org.store.execute("UPDATE org_contribution_evidence SET objective_hash='same'")
        self.assertEqual(responsibility(self.org.store,'research-003')['level'],'developing')
        self.org.store.execute("UPDATE org_contribution_evidence SET objective_hash=root_id")
        for i in (8,9):self.org.store.execute('INSERT INTO org_contribution_evidence VALUES(?,?,?,?,?,?,?,?,?,?)',(str(i),'research-003','meta',str(i),0,1,1,0,str(i),str(i)))
        self.assertEqual(responsibility(self.org.store,'research-003')['level'],'developing')
        self.assertEqual(self.org.roster['research-003']['reports_to'],'research-001')
    def test_sql_executes_supplied_data_and_denies_host_access_and_writes(self):
        from collective101.data_execution import execute_sql
        tables={'sales':[{'amount':2},{'amount':3}]}
        self.assertEqual(execute_sql('SELECT sum(amount) FROM sales',tables)['rows'],[[5]])
        for query in ("ATTACH DATABASE 'test.db' AS host",'SELECT * FROM sqlite_master','DELETE FROM sales',"SELECT load_extension('x')",'SELECT randomblob(1000000000)','PRAGMA database_list'):
            self.assertEqual(execute_sql(query,tables)['status'],'failed',query)
    def test_sql_acceptance_evidence_is_recorded_and_checked(self):
        class SQLProvider(DepartmentFixtureProvider):
            def complete(self,messages,tools=None):
                ctx=json.loads(messages[1]['content']);value=json.loads(super().complete(messages,tools).message['content'])
                if ctx['phase']=='assess' and ctx['department']=='research':value['tasks'][0]['outputs']=['query.sql']
                if ctx['phase']=='work':value['artifacts']=[{'path':'query.sql','content':'SELECT sum(amount) FROM sales'}]
                return Completion({'role':'assistant','content':json.dumps(value)})
        self.org.provider=SQLProvider();m=mission();m['artifact_checks']=[];m['allowed_capabilities'].append('sql_sandbox')
        m['data_checks']=[{'path':'research/query.sql','tables':{'sales':[{'amount':2},{'amount':3}]},'expected_rows':[[5]]}]
        run=self.org.run(self.org.create(m));self.assertEqual(run['status'],'reviewed',run['error']);self.assertTrue(run['result']['execution_results'][0]['result']['passed'])
    def test_static_html_checks_do_not_execute_scripts(self):
        from collective101.html_checks import check_html
        self.assertIn('Missing page title',check_html('<script>throw new Error()</script><img src="https://example.com">'))
        self.assertEqual(check_html('<html lang="en"><title>Hello</title><meta name="viewport"><main><h1>Hello</h1></main></html>'),[])

    def test_evaluation_runner_records_failures_without_faking_success(self):
        from collective101.evaluations import run_evaluation,MeteredProvider
        class Replies:
            name='simulation'
            def complete(self,messages):return Completion({'role':'assistant','content':json.dumps({'action':'reply','answer':'Test reply'})},5)
        report=run_evaluation(Replies(),Path(self.temp.name)/'evals',max_calls=3)
        result=json.loads(report.read_text());self.assertEqual(result['calls'],3);self.assertEqual(result['total'],7)
        self.assertTrue(any(not c['passed'] for c in result['cases']));self.assertEqual(result['provider'],'simulation')
        self.assertEqual(self.org.store.query('SELECT * FROM org_contribution_evidence'),[])
    def test_repair_pause_is_inherited_from_root(self):
        from collective101.agent_harness import AgentHarness,RunPaused
        rid=self.org.create(mission());run=self.org.run(rid);child=repairs.run_ids(self.org.store,rid)[-1]
        self.org.store.execute('INSERT INTO org_controls VALUES(?,1)',(rid,))
        harness=AgentHarness(self.org.store,self.org.provider,self.org.roster)
        with self.assertRaises(RunPaused):harness.invoke(child,'new-step','research-003','work',{},lambda v:v)
