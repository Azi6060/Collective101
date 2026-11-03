import json, time, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from collective101.console import MissionConsole
from collective101.department_runtime import DepartmentOrganization
from collective101.department_fixture import DepartmentFixtureProvider

from chat_test_provider import ChatTestProvider
ROOT=Path(__file__).resolve().parents[1]
class ConsoleCase(unittest.TestCase):
    def setUp(self):
        root=ROOT/'work'/'routing-tests'; root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root)
        self.console=MissionConsole(Path(self.temp.name)/'state.db',provider_factory=lambda mode:ChatTestProvider())
    def tearDown(self):
        self.console.close(); self.temp.cleanup()
    def settle(self,chat):
        end=time.monotonic()+30
        while chat['id'] in self.console.active and time.monotonic()<end: time.sleep(.02)
        self.assertNotIn(chat['id'],self.console.active)
        return self.console.chat(chat['id'])
class RoutingTests(ConsoleCase):
    def test_hi_uses_live_intake_without_department_mission(self):
        chat=self.settle(self.console.submit('Hi!','meta','greeting-001'))
        self.assertEqual(chat['status'],'answered');self.assertIsNone(chat['run_id'])
        self.assertEqual(chat['budget']['calls'],1)
    def test_greeting_prefix_does_not_swallow_a_task(self):
        chat=self.settle(self.console.submit('Hi, build a website','meta','prefix-001'))
        self.assertEqual(chat['status'],'clarifying')
    def test_research_chat_consults_only_selected_heads(self):
        chat=self.settle(self.console.submit('Compare three approaches to improving team onboarding with a decision brief, evidence and a summary for our engineering manager.','meta','routing-001'))
        self.assertEqual(chat['status'],'reviewed',chat['error'])
        calls=self.console.activity(chat['run_id'])['calls']
        heads={c['agent_id'] for c in calls if c['phase']=='assess'}
        self.assertEqual(heads,{'research-001','strategy-001','communications-001'})
        self.assertLess(chat['run']['calls'],30)
    def test_department_dependency_activates_omitted_head(self):
        org=DepartmentOrganization(Path(self.temp.name)/'dependency.db',DepartmentFixtureProvider())
        try:
            mission=json.loads((ROOT/'examples/research-mission.json').read_text())
            mission['departments']=['communications']
            run=org.run(org.create(mission))
            self.assertEqual(run['status'],'reviewed',run['error'])
            self.assertEqual(set(run['result']['consulted_departments']),{'research','strategy','communications'})
        finally: org.close()

class GuardrailTests(ConsoleCase):
    def test_clarification_is_authored_by_provider_not_keyword_gate(self):
        chat=self.settle(self.console.submit('Recommend an insulin dose for my child','meta','risk-001'))
        self.assertEqual(chat['status'],'clarifying')
        self.assertEqual(chat['questions'],['Who will use this website?','Which features must the first version include?'])
        self.assertEqual(chat['intake']['agent_id'],'distribution-001')
    def test_admission_budget_prevents_provider_call(self):
        from collective101.budgets import create_budget, reserve
        from collective101.store import CallBudgetExceeded
        create_budget(self.console.store,'small',max_calls=2,max_tokens=4500)
        reserve(self.console.store,'small',[{'role':'user','content':'hello'}])
        with self.assertRaises(CallBudgetExceeded): reserve(self.console.store,'small',[{'role':'user','content':'hello'}])
    def test_direct_mission_has_no_keyword_generated_intervention(self):
        mission=json.loads((ROOT/'examples/research-mission.json').read_text());mission['objective']='Research insulin education documents'
        org=self.console.organization;org.provider=DepartmentFixtureProvider()
        run=org.run(org.create(mission))
        self.assertEqual(run['status'],'reviewed',run['error'])
        self.assertEqual(org.store.query('SELECT * FROM org_interventions WHERE run_id=?',(run['id'],)),[])

    def test_live_simple_reply_never_creates_department_run(self):
        from collective101.provider import Completion
        class ReplyProvider:
            name='simulation'
            def complete(self,messages):
                return Completion({'role':'assistant','content':json.dumps({'action':'reply','answer':'A dependency is work that another task needs first.'})},42)
        self.console.provider_factory=lambda mode:ReplyProvider()
        chat=self.settle(self.console.submit('What is a task dependency?','meta','simple-001'))
        self.assertEqual(chat['status'],'answered',chat['error'])
        self.assertIsNone(chat['run_id'])
        self.assertEqual(chat['budget']['calls'],1)
        self.assertEqual(chat['budget']['reported_tokens'],42)

class ToolTests(ConsoleCase):
    def test_file_scopes_and_path_escape(self):
        from collective101.agent_tools import ToolBroker
        base=Path(self.temp.name)/'knowledge'
        (base/'shared').mkdir(parents=True); (base/'operations').mkdir()
        (base/'shared'/'guide.md').write_text('Team onboarding checklist: pair with a mentor.')
        (base/'operations'/'private.md').write_text('Operations-only data')
        broker=ToolBroker(self.console.store,self.console.organization.roster,base)
        mission={'allowed_capabilities':['knowledge_read','knowledge_search']}
        task={'tools':['knowledge_read','knowledge_search'],'requires':[]}
        result=broker.execute('none','scope1','engineering-003','work',mission,task,{'name':'knowledge_read','arguments':{'path':'shared/guide.md'}})
        self.assertEqual(result['status'],'ok'); self.assertIn('mentor',result['content'])
        for name in ['operations/private.md','../AGENTS.md','shared/../../.env','C:/secret','shared/.env']:
            result=broker.execute('none','scope'+name,'engineering-003','work',mission,task,{'name':'knowledge_read','arguments':{'path':name}})
            self.assertNotEqual(result['status'],'ok',name)
    def test_tools_require_role_mission_and_assignment_permission(self):
        from collective101.agent_tools import ToolBroker
        broker=ToolBroker(self.console.store,self.console.organization.roster,Path(self.temp.name)/'knowledge')
        for agent,allowed,task in [('communications-003',['javascript_sandbox'],{'tools':['javascript_sandbox']}),('engineering-003',[],{'tools':['javascript_sandbox']}),('engineering-003',['javascript_sandbox'],{'tools':[]})]:
            result=broker.execute('none',agent+str(allowed)+str(task),agent,'work',{'allowed_capabilities':allowed},task,{'name':'javascript_sandbox','arguments':{}})
            self.assertEqual(result['status'],'denied')
    def test_unconfigured_search_does_not_fabricate_evidence(self):
        from collective101.agent_tools import ToolBroker
        broker=ToolBroker(self.console.store,self.console.organization.roster,Path(self.temp.name)/'knowledge')
        with patch.dict('os.environ',{'BRAVE_SEARCH_API_KEY':''}):
            result=broker.execute('none','search','research-003','work',{'allowed_capabilities':['web_search']},{'tools':['web_search']},{'name':'web_search','arguments':{'query':'AI organization'}})
        self.assertEqual(result['status'],'unconfigured')
        self.assertNotIn('results',result)
    def test_employee_tool_result_reaches_head_and_reviewer_and_resume_reuses_it(self):
        from collective101.provider import Completion
        class ToolProvider(DepartmentFixtureProvider):
            def complete(self,messages,tools=None):
                ctx=json.loads(messages[1]['content'])
                value=json.loads(super().complete(messages,tools).message['content'])
                if ctx['phase']=='assess' and ctx['department']=='engineering':
                    value['tasks'][0]['tools']=['javascript_sandbox']
                if ctx['phase']=='work' and ctx['agent_id']=='engineering-003' and not ctx.get('tool_results'):
                    value={'tool_request':{'name':'javascript_sandbox','arguments':{'source':'function add(a,b){return a+b}','checks':[{'expression':'add(7,8)','expected':15}]}}}
                return Completion({'role':'assistant','content':json.dumps(value)})
        org=DepartmentOrganization(Path(self.temp.name)/'tools.db',ToolProvider())
        try:
            mission=json.loads((ROOT/'examples/javascript-mission.json').read_text());mission['departments']=['engineering'];mission['artifact_checks']=[c for c in mission['artifact_checks'] if c['path'].startswith(('engineering/','design/'))]
            run=org.run(org.create(mission))
            self.assertEqual(run['status'],'reviewed',run['error'])
            rows=org.store.query('SELECT * FROM org_tool_calls WHERE run_id=?',(run['id'],))
            self.assertEqual(len(rows),1)
            self.assertEqual(json.loads(rows[0]['result'])['execution']['checks'][0]['actual'],15)
            reports=run['result']['reports']['engineering']
            self.assertIn('tool_evidence',reports)
            self.assertEqual(org.run(run['id'])['calls'],run['calls'])
        finally:org.close()
    def test_configured_search_does_not_manufacture_human_questions(self):
        from collective101.agent_tools import ToolBroker
        broker=ToolBroker(self.console.store,self.console.organization.roster,Path(self.temp.name)/'knowledge')
        with patch.dict('os.environ',{'BRAVE_SEARCH_API_KEY':'test-placeholder'}),patch('collective101.agent_tools.web_search',return_value={'status':'ok','results':[]}) as search:
            result=broker.execute('test-run','work:research:t:tool:1','research-003','work',{'allowed_capabilities':['web_search']},{'tools':['web_search']},{'name':'web_search','arguments':{'query':'public onboarding practices'}})
        self.assertEqual(result['status'],'ok');self.assertEqual(search.call_count,1)
        self.assertEqual(self.console.store.query("SELECT * FROM org_interventions WHERE run_id='test-run'"),[])
    def test_relevance_memory_respects_identity_and_provider(self):
        from collective101.agent_tools import recall
        from collective101.store import encode
        for rid,aid,provider,content in [('old','engineering-003','fixture','onboarding accessibility'),('new','engineering-003','fixture','unrelated recent task'),('other','data-003','fixture','onboarding accessibility'),('live','engineering-003','meta','onboarding accessibility')]:
            # Real run rows satisfy the experience provenance foreign key.
            self.console.store.execute("INSERT INTO org_runs(id,provider,status,mission,roster,max_calls,created_at) VALUES(?,?,'reviewed','{}','{}',10,'test')",(rid,provider))
            self.console.store.execute('INSERT INTO org_experience VALUES(?,?,?,?)',(rid,aid,provider,encode({'summary':content})))
        rows=recall(self.console.store,'engineering-003','fixture','current','onboarding accessibility')
        self.assertEqual([r['run_id'] for r in rows],['old','new'])
    def test_web_transport_is_bounded_and_does_not_follow_redirects(self):
        import io
        from collective101.agent_tools import web_search
        body=json.dumps({'web':{'results':[{'title':'Reference','url':'https://example.com/doc','description':'Observed snippet'},{'url':'javascript:alert(1)'}]}}).encode()
        class Opener:
            def open(self,request,timeout):
                self_request=request
                self_test.assertTrue(request.full_url.startswith('https://api.search.brave.com/res/v1/web/search?'))
                self_test.assertEqual(timeout,10)
                return io.BytesIO(body)
        self_test=self
        def build(handler):
            self.assertIsNone(handler.redirect_request(None,None,302,'',{},'http://localhost/private'))
            return Opener()
        with patch.dict('os.environ',{'BRAVE_SEARCH_API_KEY':'test-placeholder'}),patch('urllib.request.build_opener',side_effect=build):
            result=web_search('public research')
        self.assertEqual(result['status'],'ok');self.assertEqual(len(result['results']),1)
    def test_required_unavailable_tool_blocks_instead_of_inventing_work(self):
        from collective101.provider import Completion
        class RequiredToolProvider(DepartmentFixtureProvider):
            def complete(self,messages,tools=None):
                ctx=json.loads(messages[1]['content']);value=json.loads(super().complete(messages,tools).message['content'])
                if ctx['phase']=='assess' and ctx['department']=='research': value['tasks'][0]['requires'].append('web_search')
                return Completion({'role':'assistant','content':json.dumps(value)})
        org=DepartmentOrganization(Path(self.temp.name)/'required.db',RequiredToolProvider())
        try:
            mission=json.loads((ROOT/'examples/research-mission.json').read_text());mission['allowed_capabilities'].append('web_search')
            with patch.dict('os.environ',{'BRAVE_SEARCH_API_KEY':''}):run=org.run(org.create(mission))
            self.assertEqual(run['status'],'blocked')
            self.assertTrue(run['result']['blocked_tasks'])
            self.assertEqual(org.store.query("SELECT * FROM org_calls WHERE run_id=? AND agent_id='research-003'",(run['id'],)),[])
        finally:org.close()

    def test_head_can_read_scoped_knowledge_but_cannot_self_grant_execution(self):
        from collective101.agent_tools import ToolBroker
        broker=ToolBroker(self.console.store,self.console.organization.roster,Path(self.temp.name)/'knowledge')
        grants=broker.grants('engineering-001','assess',{'allowed_capabilities':['knowledge_read','javascript_sandbox']},{'tools':['javascript_sandbox']})
        self.assertEqual(grants,['knowledge_read'])
    def test_repeated_tool_requests_hit_step_limit_without_unbounded_loop(self):
        from collective101.provider import Completion
        class LoopProvider(DepartmentFixtureProvider):
            def complete(self,messages,tools=None):
                ctx=json.loads(messages[1]['content'])
                if ctx['phase']=='work':
                    return Completion({'role':'assistant','content':json.dumps({'tool_request':{'name':'shell','arguments':{'command':'echo forbidden'}}})})
                return super().complete(messages,tools)
        org=DepartmentOrganization(Path(self.temp.name)/'loop.db',LoopProvider())
        try:
            mission=json.loads((ROOT/'examples/research-mission.json').read_text());mission['departments']=['research']
            run=org.run(org.create(mission))
            self.assertEqual(run['status'],'blocked')
            self.assertIn('tool limit',run['error'])
            tool_rows=org.store.query('SELECT result FROM org_tool_calls WHERE run_id=?',(run['id'],))
            self.assertEqual(len(tool_rows),4)
            self.assertTrue(all(json.loads(r['result'])['status']=='denied' for r in tool_rows))
        finally:org.close()

class IntegratedPolicyTests(ConsoleCase):
    def mission_provider(self,allow_web=False):
        from collective101.provider import Completion
        mission=json.loads((ROOT/'examples/research-mission.json').read_text())
        mission['departments']=['research']
        mission['artifact_checks']=[c for c in mission['artifact_checks'] if c['path'].startswith('research/')]
        mission['delivery_type']='document';mission['deliverables']=[{'path':mission['artifact_checks'][0]['path'],'kind':'document'}]
        if allow_web: mission['allowed_capabilities'].append('web_search')
        class Provider(DepartmentFixtureProvider):
            def complete(self,messages,tools=None):
                context=json.loads(messages[1]['content'])
                if isinstance(context,list):
                    return Completion({'role':'assistant','content':json.dumps({'ready':True,'questions':[],'mission':mission})},25)
                value=json.loads(super().complete(messages,tools).message['content'])
                if allow_web and context['phase']=='assess' and context['department']=='research':
                    value['tasks'][0]['requires'].append('web_search')
                if allow_web and context['phase']=='work' and not any(t['status']=='ok' for t in context.get('tool_results',[])):
                    value={'tool_request':{'name':'web_search','arguments':{'query':'public onboarding research'}}}
                return Completion({'role':'assistant','content':json.dumps(value)},25)
        self.console.provider_factory=lambda mode:Provider()
    def test_intake_and_department_requests_share_the_same_cap(self):
        self.mission_provider()
        chat=self.settle(self.console.submit('Compare onboarding options with a brief','meta','shared-budget-001',max_calls=1))
        self.assertEqual(chat['status'],'blocked')
        self.assertEqual(chat['budget']['calls'],1)
        self.assertEqual(chat['run']['calls'],0)
        self.assertIn('budget exhausted',chat['error'])
    def test_controller_cannot_enable_web_without_user_opt_in(self):
        self.mission_provider(allow_web=True)
        chat=self.settle(self.console.submit('Compare onboarding options with a brief','meta','permission-001'))
        self.assertEqual(chat['status'],'blocked')
        self.assertIsNone(chat['run_id'])
        self.assertIn('permissions',chat['error'])
    def test_configured_web_work_completes_without_fixed_approval_question(self):
        self.mission_provider(allow_web=True)
        with patch.dict('os.environ',{'BRAVE_SEARCH_API_KEY':'test-placeholder'}),patch('collective101.agent_tools.web_search',return_value={'status':'ok','results':[{'url':'https://example.com','snippet':'simulated response'}]}) as search:
            chat=self.settle(self.console.submit('Compare onboarding options with a brief','meta','web-run-001'))
        self.assertEqual(chat['status'],'reviewed',chat['error']);self.assertEqual(search.call_count,1)
        self.assertEqual(chat['interventions'],[])
