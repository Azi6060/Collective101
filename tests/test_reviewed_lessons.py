import hashlib,json,tempfile,unittest
from pathlib import Path
from collective101.department_runtime import DepartmentOrganization
from collective101.department_fixture import DepartmentFixtureProvider
from collective101 import learning

ROOT=Path(__file__).resolve().parents[1]

class ReviewedLessonsTests(unittest.TestCase):
    def setUp(self):
        parent=ROOT/'work'/'lesson-tests';parent.mkdir(parents=True,exist_ok=True);self.temp=tempfile.TemporaryDirectory(dir=parent)
        self.org=DepartmentOrganization(Path(self.temp.name)/'state.db',DepartmentFixtureProvider())
        self.mission={'objective':'Build an accessible grocery page','inputs':{},'constraints':[],
            'acceptance_criteria':['Provide source'],'allowed_capabilities':['draft_artifact'],'artifact_checks':[]}
        self.rid=self.org.create(self.mission)
        self.org.store.execute("UPDATE org_runs SET status='reviewed' WHERE id=?",(self.rid,))
        self.org.store.execute('INSERT INTO org_artifacts VALUES(?,?,?,?,?,?,?)',(self.rid,'page','engineering-003','build','engineering/index.html','page',hashlib.sha256(b'page').hexdigest()))
    def tearDown(self):self.org.close();self.temp.cleanup()
    def test_lesson_requires_review_and_remains_agent_provider_scoped(self):
        lesson=learning.propose_lesson(self.org.store,'engineering-003',self.org.provider_signature,self.rid,
            'A grocery landing page','Use semantic landmarks','Static checks passed','Browser appearance was not checked')
        self.assertEqual(lesson['status'],'proposed')
        self.assertFalse(learning.recall_lessons(self.org.store,'engineering-003',self.org.provider_signature,'grocery page'))
        learning.review_lesson(self.org.store,lesson['id'],True,'Verified against the saved artifact')
        found=learning.recall_lessons(self.org.store,'engineering-003',self.org.provider_signature,'grocery page')
        self.assertEqual(found[0]['evidence_run'],self.rid)
        self.assertFalse(learning.recall_lessons(self.org.store,'research-004',self.org.provider_signature,'grocery page'))
        self.assertFalse(learning.recall_lessons(self.org.store,'engineering-003','different model','grocery page'))
        learning.review_lesson(self.org.store,lesson['id'],False,'Replaced by a more precise lesson')
        self.assertFalse(learning.recall_lessons(self.org.store,'engineering-003',self.org.provider_signature,'grocery page'))
    def test_lesson_cannot_claim_another_agents_evidence_or_automatic_learning(self):
        with self.assertRaises(ValueError):learning.propose_lesson(self.org.store,'research-004',self.org.provider_signature,self.rid,'context','action','result','limits')
        with self.assertRaises(ValueError):learning.propose_lesson(self.org.store,'engineering-003','wrong provider',self.rid,'context','action','result','limits')
    def test_memory_disabled_blocks_both_automatic_retrieval_and_memory_tool(self):
        from collective101.agent_tools import ToolBroker
        from collective101.runtime_core import policy
        disabled=DepartmentOrganization(Path(self.temp.name)/'off.db',DepartmentFixtureProvider(),memory_enabled=False)
        try:
            mission={**self.mission,'allowed_capabilities':['draft_artifact','memory_search']};rid=disabled.create(mission)
            self.assertFalse(policy(disabled.store,rid)['memory_enabled'])
            grants=ToolBroker(disabled.store,disabled.roster).grants('engineering-003','work',mission,{'tools':['memory_search'],'requires':[]},run_id=rid)
            self.assertNotIn('memory_search',grants)
        finally:disabled.close()

if __name__=='__main__':unittest.main()
