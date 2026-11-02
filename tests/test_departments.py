import copy
import json
import tempfile
import unittest
from pathlib import Path

from collective101.agent_harness import AgentHarness, LeadershipBus
from collective101.department_fixture import DepartmentFixtureProvider
from collective101.department_runtime import DepartmentOrganization
from collective101 import org_contracts as contracts
from collective101.provider import Completion
from collective101.registry import build_roster, DEPARTMENTS

ROOT = Path(__file__).resolve().parents[1]


def example(name='website'):
    return json.loads((ROOT/'examples'/f'{name}-mission.json').read_text(encoding='utf-8'))


class MutatingProvider(DepartmentFixtureProvider):
    def __init__(self, mutate):
        self.mutate = mutate

    def complete(self, messages, tools=None):
        context = json.loads(messages[1]['content'])
        output = json.loads(super().complete(messages,tools).message['content'])
        return Completion({'role':'assistant','content':json.dumps(self.mutate(context,output))})


class DepartmentOrganizationTest(unittest.TestCase):
    def setUp(self):
        self.root = (ROOT/'work'/'department-tests').resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=self.root)
        self.db = Path(self.temp.name)/'state.db'
        self.org = DepartmentOrganization(self.db,DepartmentFixtureProvider())

    def tearDown(self):
        self.org.close()
        if not Path(self.temp.name).resolve().is_relative_to(self.root):
            raise RuntimeError('Cleanup escaped project test root')
        self.temp.cleanup()

    def test_101_definitions_have_specific_roles_and_valid_managers(self):
        roster = build_roster()
        self.assertEqual(len(roster),101)
        self.assertEqual(len({a['system_prompt'] for a in roster}),101)
        self.assertEqual(sum(a['role']=='department_lead' for a in roster),10)
        self.assertEqual(sum(a['role']=='mission_director' for a in roster),1)
        for dept in DEPARTMENTS:
            members = [a for a in roster if a['department']==dept.id]
            self.assertEqual(len(members),dept.count)
            self.assertEqual(sum(a['reports_to']==dept.id+'-001' for a in members),dept.count-1)

    def test_all_101_agents_invoke_the_shared_harness_with_their_own_prompt(self):
        rid = self.org.create(example(),max_calls=120)
        harness = AgentHarness(self.org.store,self.org.provider,self.org.roster)
        task = {'outputs':['draft.md'],'instructions':'Write a bounded draft.'}
        for agent in self.org.roster.values():
            if agent['role']=='mission_director':
                context={'mission':example(),'proposals':{'design':{'decision':'contribute'}}}
                phase='select'
                validate=lambda v: contracts.selection(v,{'design':{'decision':'contribute','depends_on':[]}})
            elif agent['role']=='department_lead':
                context={'mission':example(),'department':agent['department']}
                phase='assess'
                validate=lambda v,d=agent['department']: contracts.proposal(v,d,self.org.roster)
            else:
                context={'mission':example(),'task':task}
                phase='work'
                validate=lambda v: contracts.worker_result(v,task)
            harness.invoke(rid,agent['id'],agent['id'],phase,context,validate)
        calls=self.org.store.query('SELECT agent_id,input FROM org_calls WHERE run_id=?',(rid,))
        self.assertEqual(len({c['agent_id'] for c in calls}),101)
        for c in calls:
            self.assertIn(self.org.roster[c['agent_id']]['system_prompt'],json.loads(c['input'])[0]['content'])

    def test_website_heads_choose_employees_and_create_artifacts(self):
        rid=self.org.create(example())
        run=self.org.run(rid)
        self.assertEqual(run['status'],'reviewed',run['error'])
        self.assertEqual(run['calls'],36)
        self.assertEqual(run['result']['artifact_count'],6)
        self.assertEqual(run['result']['proposals']['data']['decision'],'decline')
        ops=run['result']['proposals']['operations']['tasks'][0]
        self.assertEqual(ops['assignee'],'operations-005')
        calls=self.org.store.query("SELECT agent_id FROM org_calls WHERE run_id=? AND phase='work'",(rid,))
        self.assertNotIn(run['result']['reviewer'],{x['agent_id'] for x in calls})
        messages=self.org.store.query('SELECT * FROM org_messages WHERE run_id=?',(rid,))
        for m in messages:
            a,b=self.org.roster[m['sender']],self.org.roster[m['recipient']]
            if a['department'] != b['department']:
                self.assertIn(a['role'],('mission_director','department_lead'))
                self.assertIn(b['role'],('mission_director','department_lead'))
        path=self.org.export(rid,Path(self.temp.name)/'export')
        self.assertTrue(path.exists())
        self.assertIn('<main>',(path.parent/'artifacts'/'engineering'/'index.html').read_text())

    def test_two_mission_families_have_different_teams_and_graphs(self):
        web=self.org.run(self.org.create(example()))
        research=self.org.run(self.org.create(example('research')))
        self.assertEqual(research['status'],'reviewed',research['error'])
        self.assertNotEqual(web['result']['selected_departments'],research['result']['selected_departments'])
        self.assertEqual(set(research['result']['selected_departments']),{'research','strategy','communications'})
        self.assertEqual(research['result']['artifact_count'],3)

    def test_cross_department_employee_and_director_bypass_denied(self):
        rid=self.org.create(example())
        bus=LeadershipBus(self.org.store,self.org.roster)
        for sender,recipient in [('engineering-003','operations-005'),('engineering-003','operations-001'),
                                 ('director-001','engineering-003'),('engineering-003','engineering-004')]:
            with self.assertRaises(PermissionError):
                bus.send(rid,sender+recipient,sender,recipient,'test',{})
        bus.send(rid,'valid','engineering-003','engineering-001','result',{})
        bus.send(rid,'heads','engineering-001','operations-001','handoff',{})

    def test_employee_cannot_run_leadership_phase(self):
        rid=self.org.create(example())
        harness=AgentHarness(self.org.store,self.org.provider,self.org.roster)
        with self.assertRaises(PermissionError):
            harness.invoke(rid,'bad','engineering-003','select',{},lambda v:v)
        self.assertEqual(self.org.inspect(rid)['calls'],0)

    def test_head_cannot_assign_other_department_worker(self):
        def mutate(c,v):
            if c['phase']=='assess' and c['department']=='design':
                v['tasks'][0]['assignee']='engineering-003'
            return v
        self.org.provider=MutatingProvider(mutate)
        result=self.org.run(self.org.create(example()))
        self.assertEqual(result['status'],'blocked')
        self.assertIn('own department',result['error'])

    def test_missing_capability_blocks_without_worker_call_or_false_success(self):
        def mutate(c,v):
            if c['phase']=='assess' and c['department']=='engineering':
                v['tasks'][0]['requires'].append('deploy_website')
            return v
        self.org.provider=MutatingProvider(mutate)
        rid=self.org.create(example())
        result=self.org.run(rid)
        self.assertEqual(result['status'],'blocked',result['error'])
        self.assertTrue(result['result']['blocked_tasks'])
        self.assertFalse(self.org.store.query("SELECT * FROM org_calls WHERE run_id=? AND step_key='work:engineering:deliverable'",(rid,)))
        self.assertTrue(result['result']['check_errors'])

    def test_fabricated_artifact_reference_is_rejected(self):
        def mutate(c,v):
            if c['phase']=='report':
                v['artifact_ids']=['invented']
            return v
        self.org.provider=MutatingProvider(mutate)
        result=self.org.run(self.org.create(example()))
        self.assertEqual(result['status'],'blocked')
        self.assertIn('unknown artifacts',result['error'])

    def test_review_cannot_omit_or_replace_original_criteria(self):
        def mutate(c,v):
            if c['phase']=='review':
                v['criteria']=[]
            return v
        self.org.provider=MutatingProvider(mutate)
        result=self.org.run(self.org.create(example()))
        self.assertEqual(result['status'],'blocked')
        self.assertIn('every acceptance criterion',result['error'])

    def test_independent_rejection_blocks_and_does_not_save_accepted_memory(self):
        def mutate(c,v):
            if c['phase']=='review':
                v['accepted']=False
                v['reason']='Missing actual user requirement'
                v['criteria'][0]['met']=False
            return v
        self.org.provider=MutatingProvider(mutate)
        rid=self.org.create(example())
        result=self.org.run(rid)
        self.assertEqual(result['status'],'blocked')
        self.assertEqual(self.org.store.query('SELECT * FROM org_experience WHERE run_id=?',(rid,)),[])

    def test_local_checks_override_positive_model_review(self):
        mission=example()
        mission['artifact_checks'].append({'type':'contains','path':'engineering/index.html','text':'missing literal'})
        result=self.org.run(self.org.create(mission))
        self.assertEqual(result['status'],'blocked')
        self.assertTrue(result['result']['review']['accepted'])
        self.assertTrue(result['result']['check_errors'])

    def test_budget_and_resume_preserve_completed_steps(self):
        rid=self.org.create(example(),max_calls=5)
        first=self.org.run(rid)
        self.assertEqual(first['status'],'blocked')
        self.assertEqual(first['calls'],5)
        second=self.org.run(rid)
        self.assertEqual(second['calls'],5)
        self.assertEqual(second['status'],'blocked')

    def test_completed_resume_is_idempotent_across_reopen(self):
        rid=self.org.create(example())
        first=self.org.run(rid)
        self.org.close()
        self.org=DepartmentOrganization(self.db,DepartmentFixtureProvider())
        second=self.org.run(rid)
        self.assertEqual(first['calls'],second['calls'])
        self.assertEqual(first['result'],second['result'])

    def test_accepted_experience_retrieved_with_provenance(self):
        first=self.org.run(self.org.create(example()))
        second=self.org.run(self.org.create(example()))
        calls=self.org.store.query("SELECT input FROM org_calls WHERE run_id=? AND agent_id='engineering-003'",(second['id'],))
        ctx=json.loads(json.loads(calls[0]['input'])[1]['content'])
        self.assertEqual(ctx['prior_experience'][0]['run_id'],first['id'])
        self.assertIn('not proof',ctx['prior_experience'][0]['content'])

    def test_export_refuses_existing_changed_file(self):
        rid=self.org.create(example())
        self.org.run(rid)
        output=Path(self.temp.name)/'export'
        self.org.export(rid,output)
        target=output/'artifacts'/'engineering'/'index.html'
        target.write_text('user changes')
        with self.assertRaises(FileExistsError):
            self.org.export(rid,output)
        self.assertEqual(target.read_text(),'user changes')

    def test_malformed_paths_and_cycles_fail_closed(self):
        for path in ('../escape','/absolute','x/../../escape','x\\escape','NUL.txt','x/./y','.env','x:evil','x//y'):
            with self.assertRaises(ValueError,msg=path):
                contracts.safe_path(path)
        with self.assertRaisesRegex(ValueError,'Cyclic'):
            contracts.topological({'design':['engineering'],'engineering':['design']})
        with self.assertRaisesRegex(ValueError,'Unknown'):
            contracts.topological({'design':['engineering']})

    def test_windows_artifact_collisions_are_rejected_before_execution(self):
        roster={a['id']:a for a in build_roster()}
        base={'decision':'contribute','reason':'Test collision handling','depends_on':[],
              'tasks':[{'key':'draft','title':'Draft','instructions':'Produce files',
                        'assignee':'engineering-003','depends_on':[],'requires':['draft_artifact'],
                        'outputs':['Index.html','index.html']}]}
        with self.assertRaisesRegex(ValueError,'overlap'):
            contracts.proposal(base,'engineering',roster)
        base['tasks'][0]['outputs']=['assets','assets/style.css']
        with self.assertRaisesRegex(ValueError,'overlap'):
            contracts.proposal(base,'engineering',roster)

    def test_hierarchy_tampering_rejected(self):
        from shutil import copytree
        root=Path(self.temp.name)/'definitions'
        copytree(ROOT/'collective101'/'departments',root)
        target=root/'engineering'/'engineering-003.json'
        config=json.loads(target.read_text())
        config['reports_to']='operations-001'
        target.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError,'own head'):
            build_roster(root)


if __name__=='__main__':
    unittest.main()
