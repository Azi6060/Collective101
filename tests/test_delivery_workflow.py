"""Regression evidence for useful handoffs and bounded corrective delivery.

All outputs below are scripted fixtures, not live agent-competence evidence.
"""
import json
import tempfile
import unittest
from pathlib import Path

from collective101.department_fixture import DepartmentFixtureProvider
from collective101.department_runtime import DepartmentOrganization
from collective101.provider import Completion
from collective101 import repairs, budgets

ROOT=Path(__file__).resolve().parents[1]


def landing_mission(repair_rounds=0):
    return {
        'objective':'Produce a grocery landing page copy draft using the supplied design slots.',
        'departments':['design','communications'],
        'inputs':{},'constraints':['No real business facts or external actions.'],
        'acceptance_criteria':['Deliver concise grocery copy in a single draft.'],
        'allowed_capabilities':['draft_artifact'],
        'artifact_checks':[{'type':'contains','path':'communications/landing-copy.md','text':'Final grocery copy'}],
        'max_repair_rounds':repair_rounds,
    }


class DeliveryFixture(DepartmentFixtureProvider):
    """Design is ready to hand off, even when final integrated copy is pending."""
    def __init__(self,soft_design_blocker=False,block_copy_once=False,missing_capability=False,local_dependency_failure=False):
        self.soft_design_blocker=soft_design_blocker
        self.block_copy_once=block_copy_once
        self.missing_capability=missing_capability
        self.local_dependency_failure=local_dependency_failure
        self.work=[]
        self.copy_briefings=[]

    @staticmethod
    def task(key,assignee,path,dependencies=(),requires=('draft_artifact',)):
        return {'key':key,'title':'Produce the assigned useful deliverable',
                'instructions':'Use supplied context and produce exactly the requested file.',
                'assignee':assignee,'depends_on':list(dependencies),
                'requires':list(requires),'tools':[],'outputs':[path]}

    def complete(self,messages,tools=None):
        ctx=json.loads(messages[1]['content']);phase=ctx['phase'];mission=ctx['mission']
        if phase=='assess':
            department=ctx['department']
            if department=='design':
                tasks=[self.task('structure','design-003','structure.md')]
                if self.local_dependency_failure:
                    tasks.append(self.task('dependent-design','design-004','dependent.md',['structure']))
                value={'decision':'contribute','reason':'Provide useful ready design slots.','depends_on':[],'tasks':tasks}
            elif department=='communications':
                requirements=['draft_artifact','web_search'] if self.missing_capability else ['draft_artifact']
                value={'decision':'contribute','reason':'Fill design slots with concise grocery copy.','depends_on':['design'],
                       'tasks':[self.task('landing-copy','communications-003','landing-copy.md',requires=requirements)]}
            else:
                value={'decision':'decline','reason':'No additional contribution needed.','depends_on':[],'tasks':[]}
        elif phase=='work':
            agent=ctx['agent_id'];self.work.append(agent)
            blocked=(self.local_dependency_failure and agent=='design-003') or (
                self.block_copy_once and agent=='communications-003' and not mission.get('repair_feedback'))
            if agent=='communications-003':self.copy_briefings.append(ctx['head_briefing'])
            if blocked:
                value={'status':'blocked','summary':'Need to revise the bounded copy/layout interpretation.',
                       'limitations':['Quality/coordination correction needed; supplied capabilities are sufficient.'],
                       'capability_requests':[],'artifacts':[]}
            else:
                content='Final grocery copy: Fresh choices for your neighborhood.' if agent=='communications-003' else 'Ready design slots: hero, value, categories, visit, contact.'
                value={'status':'produced','summary':'Assigned deliverable produced.','limitations':[],
                       'capability_requests':[],'artifacts':[{'path':p,'content':content} for p in ctx['task']['outputs']]}
        elif phase=='report':
            value={'summary':'Useful own artifacts are ready; integrate other departments separately.',
                   'artifact_ids':ctx['artifact_ids'],'blockers':[], 'improvements':[]}
            if ctx['department']=='design' and self.soft_design_blocker:
                value['blockers']=['Final integrated copy is pending Communications. The design structure is ready.']
        else:
            return super().complete(messages,tools)
        return Completion({'role':'assistant','content':json.dumps(value)},7)


class DeliveryWorkflowTests(unittest.TestCase):
    def setUp(self):
        parent=ROOT/'work'/'delivery-workflow-tests';parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent)
        self.provider=DeliveryFixture()
        self.org=DepartmentOrganization(Path(self.temp.name)/'state.db',self.provider)

    def tearDown(self):
        self.org.close();self.temp.cleanup()

    def test_soft_upstream_integration_blocker_does_not_suppress_ready_copy_work(self):
        self.provider.soft_design_blocker=True
        rid=self.org.create(landing_mission());self.org.run(rid)
        artifacts=self.org.store.query('SELECT path,content FROM org_artifacts WHERE run_id=?',(rid,))
        self.assertIn('communications-003',self.provider.work,
                      'A design report awaiting copy must not prevent the copy department from supplying it')
        self.assertIn('communications/landing-copy.md',{a['path'] for a in artifacts})
        self.assertIn('Final grocery copy',next(a['content'] for a in artifacts if a['path']=='communications/landing-copy.md'))
        upstream=self.provider.copy_briefings[0]['design']
        self.assertTrue(upstream['published_artifacts'],'The head-mediated handoff must retain available design artifacts')

    def test_repairable_worker_blocker_runs_one_revision_with_same_budget_and_original_evidence(self):
        self.provider.block_copy_once=True
        rid=self.org.create(landing_mission(1));run=self.org.run(rid)
        ids=repairs.run_ids(self.org.store,rid)
        self.assertEqual(len(ids),2,'A model-authored quality blocker must reach bounded correction rather than skip repairs')
        self.assertEqual(run['status'],'reviewed',run['error'])
        self.assertFalse(self.org.store.query("SELECT path FROM org_artifacts WHERE run_id=? AND path='communications/landing-copy.md'",(rid,)))
        self.assertTrue(self.org.store.query("SELECT path FROM org_artifacts WHERE run_id=? AND path='communications/landing-copy.md'",(ids[1],)))
        binding=self.org.store.query('SELECT budget_id FROM org_run_budgets WHERE run_id=?',(ids[1],))[0]
        self.assertEqual(binding['budget_id'],rid)
        used=budgets.inspect_budget(self.org.store,rid)['calls']
        self.org.run(rid)
        self.assertEqual(budgets.inspect_budget(self.org.store,rid)['calls'],used,'Reopening accepted work cannot rerun paid calls')

    def test_completed_peer_handoff_can_clear_an_outdated_integration_concern(self):
        class Reconciled(DeliveryFixture):
            def complete(self,messages,tools=None):
                value=super().complete(messages,tools);ctx=json.loads(messages[1]['content'])
                if ctx['phase']=='report' and ctx['department']=='design' and ctx.get('integration_review'):
                    self.asserted_peer_files=bool(ctx['head_reports']['communications']['published_artifacts'])
                    data=json.loads(value.message['content']);data['blockers']=[]
                    return Completion({'role':'assistant','content':json.dumps(data)},5)
                return value
        provider=Reconciled(soft_design_blocker=True);self.org.provider=provider
        run=self.org.run(self.org.create(landing_mission()))
        self.assertEqual(run['status'],'reviewed',run['error'])
        self.assertTrue(provider.asserted_peer_files)
        self.assertFalse(run['result']['reports']['design']['blockers'])

    def test_missing_essential_capability_stays_blocked_without_blind_repair(self):
        self.provider.missing_capability=True
        rid=self.org.create(landing_mission(2));run=self.org.run(rid)
        self.assertEqual(run['status'],'blocked')
        self.assertNotIn('communications-003',self.provider.work)
        self.assertEqual(repairs.run_ids(self.org.store,rid),[rid])
        self.assertTrue(any('web_search' in b['capability_requests'] for b in run['result']['blocked_tasks']))

    def test_failed_explicit_local_task_dependency_is_not_erased_by_ready_artifacts(self):
        self.provider.local_dependency_failure=True
        rid=self.org.create(landing_mission());run=self.org.run(rid)
        self.assertEqual(run['status'],'blocked')
        self.assertNotIn('design-004',self.provider.work,'A failed explicit task dependency remains authoritative')
        self.assertTrue(any(b['task']=='dependent-design' for b in run['result']['blocked_tasks']))


if __name__=='__main__':unittest.main()
