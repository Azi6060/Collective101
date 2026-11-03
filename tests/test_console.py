import json
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from collective101.console import MissionConsole
from collective101.department_runtime import DepartmentOrganization
from collective101.department_fixture import DepartmentFixtureProvider
from collective101.provider import Completion
from collective101.sandbox import execute_javascript
from collective101.web_server import make_server
from collective101 import learning
from chat_test_provider import ChatTestProvider

ROOT=Path(__file__).resolve().parents[1]


class ConsoleTest(unittest.TestCase):
    def setUp(self):
        self.root=(ROOT/'work'/'console-tests').resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=self.root)
        self.state=Path(self.temp.name)/'state.db'
        self.console=MissionConsole(self.state,provider_factory=lambda mode:ChatTestProvider())
    def tearDown(self):
        self.console.close()
        if not Path(self.temp.name).resolve().is_relative_to(self.root):raise RuntimeError('Unsafe test cleanup')
        self.temp.cleanup()
    def settle(self,cid):
        deadline=time.monotonic()+30
        while cid in self.console.active and time.monotonic()<deadline:time.sleep(.03)
        self.assertNotIn(cid,self.console.active)
        return self.console.chat(cid)
    def test_short_chat_pauses_then_runs_after_answers(self):
        chat=self.console.submit('Build a website','meta','clarify-001')
        chat=self.settle(chat['id'])
        self.assertEqual(chat['status'],'clarifying')
        self.assertIsNone(chat['run_id'])
        self.console.answer(chat['id'],['A coffee shop for local residents to browse the menu and find our location.','An accessible responsive page with opening hours and maintenance documentation.'])
        chat=self.settle(chat['id'])
        self.assertEqual(chat['status'],'reviewed',chat['error'])
        self.assertTrue(self.console.activity(chat['run_id'])['calls'])
    def test_duplicate_submission_cannot_start_two_missions(self):
        first=self.console.submit('Build a website','meta','duplicate-001')
        second=self.console.submit('Build a website','meta','duplicate-001')
        self.assertEqual(first['id'],second['id'])
        self.settle(first['id'])
        self.assertEqual(len(self.console.list_chats()),1)
        with self.assertRaises(ValueError):self.console.submit('different mission','meta','duplicate-001')
    def test_answers_are_bound_to_pending_chat(self):
        chat=self.settle(self.console.submit('Build a website','meta','wronganswers-001')['id'])
        with self.assertRaises(ValueError):self.console.answer(chat['id'],[])
        with self.assertRaises(ValueError):self.console.answer(chat['id'],'answer','invented-question')
    def test_live_mode_never_silently_uses_fixture(self):
        from unittest.mock import patch
        self.console.provider_factory=self.console._provider
        with patch.dict('os.environ',{'MODEL_API_KEY':''}):
            with self.assertRaisesRegex(ValueError,'MODEL_API_KEY'):self.console.submit('Build a website','meta','live-missing-001')
        self.assertEqual(self.console.list_chats(),[])
    def test_real_sandbox_evidence_reaches_review(self):
        mission=json.loads((ROOT/'examples/javascript-mission.json').read_text())
        org=DepartmentOrganization(self.state,DepartmentFixtureProvider())
        try:
            run=org.run(org.create(mission))
            self.assertEqual(run['status'],'reviewed',run['error'])
            evidence=run['result']['execution_results'][0]['result']
            self.assertTrue(evidence['passed'])
            self.assertEqual(len(evidence['checks']),3)
            request=org.store.query("SELECT input FROM org_calls WHERE run_id=? AND phase='review'",(run['id'],))[0]
            self.assertIn('execution_evidence',json.loads(json.loads(request['input'])[1]['content']))
            outcome=org.store.query('SELECT evidence_mode,live,accepted,evidence_run FROM org_team_outcomes WHERE root_id=?',(run['id'],))[0]
            self.assertEqual((outcome['evidence_mode'],outcome['live'],outcome['accepted'],outcome['evidence_run']),
                ('fixture',0,1,run['id']))
        finally:org.close()
    def test_failed_execution_overrides_model_acceptance(self):
        mission=json.loads((ROOT/'examples/javascript-mission.json').read_text())
        mission['execution_checks'][0]['expected']=999
        org=DepartmentOrganization(self.state,DepartmentFixtureProvider())
        try:
            run=org.run(org.create(mission))
            self.assertEqual(run['status'],'blocked')
            self.assertTrue(run['result']['review']['accepted'])
            self.assertIn('Execution failed',run['result']['check_errors'][0])
            outcome=org.store.query('SELECT evidence_mode,live,accepted FROM org_team_outcomes WHERE root_id=?',(run['id'],))[0]
            self.assertEqual((outcome['evidence_mode'],outcome['live'],outcome['accepted']),('fixture',0,0))
        finally:org.close()

    def test_similar_live_team_outcomes_are_advisory_and_fixture_history_is_excluded(self):
        class Provider:
            name='meta'
            model='test-model'
            url='https://model.example.test/v1'

        class FixtureProvider:
            name='fixture'

        console=self.console
        class EvidenceRecorder:
            def __init__(self,provider):
                self.store=console.store
                self.provider=provider
                self.provider_signature=learning.provider_signature(provider)
            def inspect(self,root):
                return {'mission':{'objective':'Create an accessible onboarding website for new remote workers with clear guidance.'}}

        live=Provider()
        for root,accepted,departments in (
            ('live-blocked',False,['engineering','design']),
            ('live-accepted',True,['research','communications']),
        ):
            recorder=EvidenceRecorder(live)
            learning.record_team_outcome(recorder,root,root,{'accepted':accepted,'selected_departments':departments})
        fixture=EvidenceRecorder(FixtureProvider())
        learning.record_team_outcome(fixture,'fixture-outcome','fixture-outcome',
            {'accepted':False,'selected_departments':['engineering','design']})

        transcript=[{'role':'user','content':'Build an accessible onboarding website for new remote workers with clear guidance.'}]
        matches=learning.team_recommendations(self.console.store,live,learning.transcript_query(transcript))
        self.assertEqual({item['outcome'] for item in matches},{'accepted','not_accepted'})
        self.assertTrue(all(item['matched_objective_terms']>=2 for item in matches))
        self.assertNotIn('fixture-outcome',{item['evidence_run'] for item in matches})

        messages,_=self.console.intake_messages(transcript,matches)
        prompt=messages[0]['content']
        self.assertIn('Prefer a different smallest-useful team after a prior team was not accepted',prompt)
        self.assertIn('do not prove which department caused success or failure',prompt)
        self.assertIn('Do not exclude any department automatically',prompt)
        self.assertIn('live-blocked',prompt)
        self.assertEqual(learning.team_recommendations(self.console.store,FixtureProvider(),
            learning.transcript_query(transcript)),[])
        different_model=Provider()
        different_model.model='other-model'
        self.assertEqual(learning.team_recommendations(self.console.store,different_model,
            learning.transcript_query(transcript)),[])
    def test_agent_intervention_preserves_work_and_resumes(self):
        class QuestionProvider(ChatTestProvider):
            def complete(self,messages,tools=None):
                context=json.loads(messages[1]['content'])
                if isinstance(context,dict) and context['phase']=='work' and context['agent_id']=='engineering-003' and not context.get('human_answers'):
                    return Completion({'role':'assistant','content':json.dumps({'intervention':{'question':'Should the page be bilingual?','reason':'Content language affects the implementation.','options':['English only','Bilingual']}})})
                return super().complete(messages,tools)
        self.console.provider_factory=lambda mode:QuestionProvider()
        chat=self.console.submit('Build an accessible website for our neighborhood coffee shop with a menu opening hours location and operations documentation.','meta','agent-question-001')
        chat=self.settle(chat['id']);self.assertEqual(chat['status'],'needs_input',chat['error'])
        rid=chat['run_id'];calls=chat['run']['calls']
        question=next(q for q in chat['interventions'] if q['status']=='pending')
        self.console.answer(chat['id'],'English only',question['id'])
        chat=self.settle(chat['id'])
        self.assertEqual(chat['status'],'reviewed',chat['error']);self.assertEqual(chat['run_id'],rid)
        self.assertGreater(chat['run']['calls'],calls)
        self.assertEqual(self.console.store.query("SELECT COUNT(*) n FROM org_calls WHERE run_id=? AND step_key='select'",(rid,))[0]['n'],1)
    def test_pause_before_phase_then_resume(self):
        org=DepartmentOrganization(self.state,DepartmentFixtureProvider())
        try:
            rid=org.create(json.loads((ROOT/'examples/research-mission.json').read_text()))
            org.store.execute('INSERT INTO org_controls VALUES(?,1)',(rid,))
            self.assertEqual(org.run(rid)['status'],'paused')
            self.assertEqual(org.inspect(rid)['calls'],0)
            org.store.execute('UPDATE org_controls SET pause_requested=0 WHERE run_id=?',(rid,))
            self.assertEqual(org.run(rid)['status'],'reviewed')
        finally:org.close()
    def test_http_session_host_origin_and_input_validation(self):
        server=make_server(self.state,0,self.console)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        def request(path,body=None,headers=None):
            req=urllib.request.Request(base+path,data=None if body is None else json.dumps(body).encode(),headers=headers or {})
            with urllib.request.urlopen(req,timeout=3) as response:return json.load(response)
        try:
            token=request('/api/session')['token']
            with self.assertRaises(urllib.error.HTTPError):request('/api/organization')
            self.assertEqual(len(request('/api/organization',headers={'X-Console-Token':token})['agents']),101)
            headers={'X-Console-Token':token,'Content-Type':'application/json','Origin':'https://evil.example'}
            with self.assertRaises(urllib.error.HTTPError):request('/api/chats',{'message':'short','mode':'meta','request_id':'forbidden-001'},headers)
            headers['Origin']=base
            chat=request('/api/chats',{'message':'Build a website','mode':'meta','request_id':'http-001'},headers)
            self.assertEqual(self.settle(chat['id'])['status'],'clarifying')
            with self.assertRaises(urllib.error.HTTPError):request('/api/session',headers={'Host':'evil.example'})
            with self.assertRaises(urllib.error.HTTPError):request('/../PROJECT_STATUS.md')
        finally:server.shutdown();server.server_close();thread.join()
    def test_sandbox_does_not_receive_host_secret(self):
        from unittest.mock import patch
        with patch.dict('os.environ',{'MODEL_API_KEY':'test-secret-not-real','NODE_OPTIONS':'--invalid-host-option'}):
            result=execute_javascript('',[{'expression':'typeof process','expected':'undefined'}])
        self.assertTrue(result['passed'],result)


if __name__=='__main__':unittest.main()
