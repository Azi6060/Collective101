"""Public-runtime RED regressions for head-mediated mid-mission help.

All responses are deterministic fixtures. No live providers or user state.
"""
import json
import tempfile
import unittest
from pathlib import Path

from collective101.department_fixture import DepartmentFixtureProvider
from collective101.department_runtime import DepartmentOrganization
from collective101.provider import Completion

SENTINEL = 'HELP_EVIDENCE_SENTINEL_42'
REQUEST = {'department':'research','question':'Which pure function should add two finite numbers?',
           'reason':'Need scoped expert confirmation without external tools.','needs_replan':False}


def help_mission():
    return {'objective':'Implement a verified add function using appropriate departmental help.',
            'departments':['engineering'],'inputs':{},'constraints':['Pure JavaScript only.'],
            'acceptance_criteria':['add(2,3) returns 5.'],
            'allowed_capabilities':['draft_artifact','javascript_sandbox'],
            'artifact_checks':[{'type':'contains','path':'engineering/calculator.js','text':'function add'}],
            'execution_checks':[{'path':'engineering/calculator.js','expression':'add(2,3)','expected':5}],
            'max_repair_rounds':0}


class HeadHelpFixture(DepartmentFixtureProvider):
    def __init__(self,repeat=False,needs_replan=False):
        self.calls=0;self.work_inputs=[];self.repeat=repeat;self.needs_replan=needs_replan
    def complete(self,messages,tools=None):
        self.calls+=1
        ctx=json.loads(messages[1]['content']);phase=ctx['phase']
        if phase=='assess':
            if ctx['department']=='engineering':
                value={'decision':'contribute','reason':'Implement the finite-number add function.',
                       'depends_on':['research'] if ctx['mission'].get('replan_context') else [],'tasks':[{'key':'implement','title':'Implement add','instructions':'Use the received specialist advice and create the assigned pure function.',
                       'assignee':'engineering-003','depends_on':[],'requires':['draft_artifact'],'tools':[],'outputs':['calculator.js']}]}
            elif ctx['department']=='research' and ctx['mission'].get('replan_context'):
                value={'decision':'contribute','reason':'Supply the scoped implementation confirmation requested by the other head.','depends_on':[],
                       'tasks':[{'key':'confirm','title':'Confirm add','instructions':'Confirm finite-number addition from supplied domain; no external tools.',
                       'assignee':'research-003','depends_on':[],'requires':['draft_artifact'],'tools':[],'outputs':['research-note.md']}]}
            else:
                value={'decision':'decline','reason':'No separate output initially required.','depends_on':[],'tasks':[]}
        elif phase=='work':
            self.work_inputs.append(ctx)
            if ctx['agent_id']=='research-003':
                value={'status':'produced','summary':'Confirmed the supplied arithmetic domain.','limitations':[], 'capability_requests':[],
                       'artifacts':[{'path':'research-note.md','content':SENTINEL+': addition uses a+b for finite numbers.'}]}
            elif self.repeat or (SENTINEL not in json.dumps(ctx) and not ctx['mission'].get('replan_context')):
                value={'help_request':{**REQUEST,'needs_replan':self.needs_replan}}
            else:value={'status':'produced','summary':'Created add using the head-mediated scoped answer.','limitations':[],
                        'capability_requests':[],'artifacts':[{'path':'calculator.js','content':'function add(a,b) { return a+b; }\n'}]}
        elif phase=='help_decision':
            value={'approved':True,'reason':'The other head can resolve a scoped implementation question.'}
        elif phase=='help':
            answer=SENTINEL+': Use a+b for the finite-number domain; no new capability needed.'
            value={'answer':answer,'summary':answer,'recommendations':[answer],'limitations':[],
                   'needs_replan':self.needs_replan,'reason':'A research deliverable is needed.' if self.needs_replan else 'The scoped answer is sufficient.'}
        elif phase=='replan':
            value={'approved':True,'departments':['engineering','research'],'reason':'Add a Research-owned confirmation without changing the requested function or checks.'}
        else:
            return super().complete(messages,tools)
        return Completion({'role':'assistant','content':json.dumps(value)},7)


class MidMissionHelpTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'work'/'midmission-v12-tests';root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root);self.provider=HeadHelpFixture()
        self.org=DepartmentOrganization(Path(self.temp.name)/'state.db',self.provider)
    def tearDown(self):self.org.close();self.temp.cleanup()
    def start(self):
        mission=help_mission();rid=self.org.create(mission);return mission,rid,self.org.run(rid)
    def test_employee_gets_scoped_head_to_head_help_and_produces_checked_source(self):
        mission,rid,run=self.start()
        self.assertEqual(run['status'],'reviewed',run['error'])
        artifacts=self.org.store.query('SELECT content FROM org_artifacts WHERE run_id=?',(rid,))
        self.assertTrue(any('function add' in a['content'] for a in artifacts))
        self.assertTrue(any(SENTINEL in json.dumps(c) for c in self.provider.work_inputs),'The requesting worker must receive the recorded answer')
        self.assertEqual(run['mission']['allowed_capabilities'],mission['allowed_capabilities'])
        self.assertEqual(run['mission']['acceptance_criteria'],mission['acceptance_criteria'])
        self.assertTrue(run['result']['execution_results'][0]['result']['passed'])
        messages=self.org.store.query('SELECT sender,recipient FROM org_messages WHERE run_id=?',(rid,))
        self.assertTrue(any(m['sender']=='engineering-001' and m['recipient']=='research-001' for m in messages))
        self.assertTrue(any(m['sender']=='research-001' and m['recipient']=='engineering-001' for m in messages))
        for m in messages:
            a,b=self.org.roster[m['sender']],self.org.roster[m['recipient']]
            if a['department']!=b['department']:
                self.assertIn(a['role'],{'department_lead','mission_director'})
                self.assertIn(b['role'],{'department_lead','mission_director'})
    def test_completed_help_is_replayed_without_new_calls_or_changed_step_hash(self):
        _,rid,run=self.start();self.assertEqual(run['status'],'reviewed',run['error'])
        before=self.provider.calls
        records=self.org.store.query('SELECT step_key,input_hash FROM org_calls WHERE run_id=? ORDER BY rowid',(rid,))
        self.org.run(rid);self.assertEqual(self.provider.calls,before)
        grouped={}
        for row in records:grouped.setdefault(row['step_key'],set()).add(row['input_hash'])
        self.assertTrue(all(len(hashes)==1 for hashes in grouped.values()),'A continuation needs its own recorded step identity; old inputs cannot be rewritten')
        self.assertFalse(self.org.store.query("SELECT step_key FROM org_calls WHERE run_id=? AND status='failed' AND error_kind='validation'",(rid,)))
    def test_midmission_replan_adds_department_in_child_without_mutating_original(self):
        self.provider.needs_replan=True
        mission,rid,run=self.start()
        self.assertEqual(run['status'],'reviewed',run['error'])
        rows=self.org.store.query('SELECT id,mission FROM org_runs ORDER BY rowid')
        children=[{'id':r['id'],'mission':json.loads(r['mission'])} for r in rows if r['id']!=rid]
        self.assertEqual(len(children),1,'One scoped assistance-triggered revision should add the missing department')
        revised=children[0]['mission'];self.assertEqual(set(revised['departments']),{'engineering','research'})
        self.assertTrue(revised.get('replan_context'),'The child records why the mid-mission scope changed')
        for key in ('objective','acceptance_criteria','allowed_capabilities','artifact_checks','execution_checks'):
            self.assertEqual(revised[key],mission[key],key+' cannot be weakened or expanded by replanning')
        self.assertEqual(self.org.inspect(rid)['mission']['departments'],['engineering'])
        bindings=self.org.store.query('SELECT DISTINCT budget_id FROM org_run_budgets')
        self.assertEqual(len(bindings),1,'A revision shares the original spending ledger instead of resetting usage')
        sources=self.org.store.query('SELECT path FROM org_artifacts WHERE run_id=?',(children[0]['id'],))
        self.assertIn('research/research-note.md',{r['path'] for r in sources})
        self.assertIn('engineering/calculator.js',{r['path'] for r in sources})
        before=self.provider.calls;self.org.run(rid);self.assertEqual(self.provider.calls,before)
    def test_same_scope_revision_can_retask_the_team_without_expanding_permissions(self):
        self.provider.needs_replan=True;mission=help_mission();mission['departments']=['engineering','research']
        rid=self.org.create(mission);run=self.org.run(rid);self.assertEqual(run['status'],'reviewed',run['error'])
        revisions=self.org.store.query('SELECT run_id FROM org_plan_revisions');self.assertEqual(len(revisions),1)
        child=self.org.inspect(revisions[0]['run_id']);self.assertEqual(child['mission']['departments'],mission['departments']);self.assertEqual(child['mission']['allowed_capabilities'],mission['allowed_capabilities'])
    def test_repeated_assistance_requests_terminate_without_infinite_conversation(self):
        self.provider.repeat=True
        _,rid,run=self.start()
        self.assertEqual(run['status'],'blocked')
        self.assertLess(self.provider.calls,30)
        self.assertIn('help',str(run['error']).lower())
        self.assertFalse(self.org.store.query('SELECT id FROM org_artifacts WHERE run_id=?',(rid,)))

class HelpResumeTests(unittest.TestCase):
    setUp=MidMissionHelpTests.setUp
    tearDown=MidMissionHelpTests.tearDown
    def test_head_clarification_resumes_the_same_help_request(self):
        class QuestionFixture(HeadHelpFixture):
            def complete(self,messages,tools=None):
                ctx=json.loads(messages[1]['content'])
                if ctx['phase']=='help_decision' and not ctx.get('human_answers'):
                    self.calls+=1
                    return Completion({'role':'assistant','content':json.dumps({'intervention':{'question':'May I use the supplied finite-number domain?','reason':'Confirm the actual input domain.','options':['Yes','No']}})},2)
                return super().complete(messages,tools)
        provider=QuestionFixture();self.org.provider=provider
        mission=help_mission();rid=self.org.create(mission);run=self.org.run(rid);self.assertEqual(run['status'],'needs_input',run['error'])
        q=self.org.store.query("SELECT id FROM org_interventions WHERE status='pending'")[0]['id']
        self.org.store.execute("UPDATE org_interventions SET status='answered',answer='Yes' WHERE id=?",(q,))
        run=self.org.run(rid);self.assertEqual(run['status'],'reviewed',run['error'])
        self.assertEqual(len(self.org.store.query('SELECT id FROM org_assistance')),1)
    def test_root_pause_reaches_a_replanned_child_and_resumes_without_new_revision(self):
        parent=self
        class PausingFixture(HeadHelpFixture):
            paused=False
            def complete(self,messages,tools=None):
                ctx=json.loads(messages[1]['content'])
                if ctx['phase']=='work' and ctx['mission'].get('replan_context') and not self.paused:
                    self.paused=True;parent.org.store.execute('INSERT OR REPLACE INTO org_controls VALUES(?,1)',(parent.root,))
                return super().complete(messages,tools)
        provider=PausingFixture(needs_replan=True);self.org.provider=provider
        self.root=self.org.create(help_mission());run=self.org.run(self.root);self.assertEqual(run['status'],'paused',run['error'])
        self.org.store.execute('UPDATE org_controls SET pause_requested=0 WHERE run_id=?',(self.root,));run=self.org.run(self.root)
        self.assertEqual(run['status'],'reviewed',run['error']);self.assertEqual(len(self.org.store.query('SELECT run_id FROM org_plan_revisions')),1)

class ReplanPriorityTests(unittest.TestCase):
    def test_pending_human_guidance_takes_precedence_over_a_parallel_replan(self):
        from collective101.runtime_core import run_dag
        from collective101.assistance import ReplanRequired
        from collective101.agent_harness import HumanInputRequired
        from threading import Barrier
        barrier=Barrier(2,timeout=5)
        def replan(_):
            barrier.wait();raise ReplanRequired('revision ready')
        def human(_):
            barrier.wait();raise HumanInputRequired('guidance pending')
        with self.assertRaises(HumanInputRequired):run_dag({'replan':replan,'human':human},{'replan':[],'human':[]},2)

if __name__=='__main__':unittest.main()
