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
