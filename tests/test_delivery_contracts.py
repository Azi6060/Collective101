"""Structured delivery must require source ownership, not specifications alone."""
import json
import tempfile
import unittest
from pathlib import Path

from collective101.department_fixture import DepartmentFixtureProvider
from collective101.department_runtime import DepartmentOrganization
from collective101.org_contracts import mission_contract
from collective101.provider import Completion

ROOT=Path(__file__).resolve().parents[1]


def website_mission():
    value=json.loads((ROOT/'examples'/'website-mission.json').read_text(encoding='utf-8'))
    value.update(departments=['design','engineering'],artifact_checks=[],max_repair_rounds=0,
                 delivery_type='website',deliverables=[{'path':'engineering/index.html','kind':'html'}])
    return value


class SourceOwnershipFixture(DepartmentFixtureProvider):
    def __init__(self,omit_assignment=False,omit_owner=False):
        self.omit_assignment=omit_assignment;self.omit_owner=omit_owner;self.work_agents=[]
    def complete(self,messages,tools=None):
        ctx=json.loads(messages[1]['content'])
        value=json.loads(super().complete(messages,tools).message['content'])
        if ctx['phase']=='assess' and ctx['department']=='engineering' and self.omit_assignment:
            value['tasks'][0]['outputs']=['implementation-notes.md']
        if ctx['phase']=='select' and self.omit_owner:
            value={'departments':['design'],'reason':'Only produce useful design specifications.'}
        if ctx['phase']=='work':self.work_agents.append(ctx['agent_id'])
        return Completion({'role':'assistant','content':json.dumps(value)},4)


class DeliveryContractTests(unittest.TestCase):
    def setUp(self):
        parent=ROOT/'work'/'delivery-contract-tests';parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent)
        self.org=DepartmentOrganization(Path(self.temp.name)/'state.db',DepartmentFixtureProvider())
    def tearDown(self):self.org.close();self.temp.cleanup()

    def test_legacy_contract_defaults_and_structured_website_contract_are_preserved(self):
        legacy=website_mission();legacy.pop('delivery_type');legacy.pop('deliverables')
        result=mission_contract(legacy)
        self.assertEqual(result['delivery_type'],'generic');self.assertEqual(result['deliverables'],[])
        structured=mission_contract(website_mission())
        self.assertEqual(structured['delivery_type'],'website')
        self.assertEqual(structured['deliverables'],[{'path':'engineering/index.html','kind':'html'}])

    def test_website_requires_engineering_html_and_declared_owners_must_be_selected(self):
        cases=[]
        no_engineering=website_mission();no_engineering['departments']=['design','communications'];cases.append(no_engineering)
        no_html=website_mission();no_html['deliverables']=[{'path':'engineering/plan.md','kind':'document'}];cases.append(no_html)
        design_only_html=website_mission();design_only_html['deliverables']=[{'path':'design/index.html','kind':'html'}];cases.append(design_only_html)
        unselected_owner=website_mission();unselected_owner['delivery_type']='code';unselected_owner['departments']=['research'];cases.append(unselected_owner)
        for value in cases:
            with self.subTest(value=value),self.assertRaises(ValueError):mission_contract(value)

    def test_engineering_proposal_cannot_substitute_implementation_notes_for_declared_source(self):
        provider=SourceOwnershipFixture(omit_assignment=True);self.org.provider=provider
        run=self.org.run(self.org.create(website_mission()))
        self.assertEqual(run['status'],'blocked',run['error'])
        self.assertIsNotNone(run['error'],'Source ownership must be validated before spending worker calls')
        self.assertRegex(run['error'].lower(),r'deliver|assign|index\.html')
        self.assertNotIn('engineering-003',provider.work_agents)

    def test_qualified_planning_and_worker_paths_produce_one_canonical_source_path(self):
        class Qualified(DepartmentFixtureProvider):
            def complete(self,messages,tools=None):
                value=super().complete(messages,tools);ctx=json.loads(messages[1]['content']);data=json.loads(value.message['content'])
                if ctx['phase'] in {'assess','coordinate'}:
                    for task in data['tasks']:task['outputs']=[ctx['department']+'/'+path for path in task['outputs']]
                if ctx['phase']=='work':
                    for file in data['artifacts']:file['path']=ctx['agent_id'].rsplit('-',1)[0]+'/'+file['path']
                return Completion({'role':'assistant','content':json.dumps(data)},5)
        self.org.provider=Qualified();run=self.org.run(self.org.create(website_mission()))
        self.assertEqual(run['status'],'reviewed',run['error'])
        paths=[a['path'] for a in self.org.store.query('SELECT path FROM org_artifacts WHERE run_id=?',(run['id'],))]
        self.assertIn('engineering/index.html',paths)
        self.assertFalse(any('/engineering/' in path for path in paths))

    def test_qualified_and_relative_aliases_cannot_create_duplicate_output_files(self):
        from collective101.org_contracts import proposal
        value={'decision':'contribute','reason':'Build the HTML source','depends_on':[],
            'tasks':[{'key':'build','title':'Build','instructions':'Write source','assignee':'engineering-003',
                'depends_on':[],'requires':['draft_artifact'],'outputs':['index.html','engineering/index.html']}]}
        with self.assertRaisesRegex(ValueError,'overlap|Duplicate'):proposal(value,'engineering',self.org.roster)

    def test_rejected_planning_records_attempted_paths_for_diagnosis(self):
        self.org.provider=SourceOwnershipFixture(omit_assignment=True)
        run=self.org.run(self.org.create(website_mission()))
        row=self.org.store.query("SELECT output,error FROM org_calls WHERE run_id=? AND status='failed' ORDER BY rowid LIMIT 1",(run['id'],))[0]
        self.assertIsNotNone(row['output'])
        self.assertIn('implementation-notes.md',row['output'])
        self.assertIn('index.html',row['error'])

    def test_director_cannot_drop_the_declared_delivery_owner(self):
        provider=SourceOwnershipFixture(omit_owner=True);self.org.provider=provider
        run=self.org.run(self.org.create(website_mission()))
        self.assertEqual(run['status'],'blocked',run['error'])
        self.assertIsNotNone(run['error'])
        self.assertRegex(run['error'].lower(),r'deliver|owner|engineering')
        self.assertEqual(provider.work_agents,[],'Reject the incomplete team before workers execute')

    def test_declared_html_is_checked_even_without_optional_artifact_checks(self):
        mission=mission_contract(website_mission())
        artifacts=[{'path':'design/plan.md','content':'All headings and categories are specified.'}]
        errors=self.org._check_artifacts(mission,artifacts)
        self.assertTrue(errors,'An affirmative model review cannot replace a declared HTML file')
        self.assertIn('engineering/index.html',' '.join(errors))

    def test_department_heads_receive_persisted_file_hashes_and_workers_know_builtin_delivery(self):
        run=self.org.run(self.org.create(website_mission()))
        self.assertEqual(run['status'],'reviewed',run['error'])
        reports=self.org.store.query("SELECT input FROM org_calls WHERE run_id=? AND phase='report' AND status='accepted'",(run['id'],))
        self.assertTrue(reports)
        for report in reports:
            ctx=json.loads(json.loads(report['input'])[1]['content'])
            for f in ctx['saved_files']:
                actual=self.org.store.query('SELECT sha256 FROM org_artifacts WHERE run_id=? AND id=?',(run['id'],f['id']))[0]
                self.assertEqual(f['sha256'],actual['sha256'])
        work=self.org.store.query("SELECT input FROM org_calls WHERE run_id=? AND phase='work' AND status='accepted'",(run['id'],))
        self.assertTrue(all(json.loads(json.loads(row['input'])[1]['content'])['artifact_delivery']['available'] for row in work))


if __name__=='__main__':unittest.main()
