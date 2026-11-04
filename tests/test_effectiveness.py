import tempfile,time,unittest
from unittest.mock import patch
from pathlib import Path
from collective101.console import MissionConsole
from chat_test_provider import ChatTestProvider

ROOT=Path(__file__).resolve().parents[1]

class EffectivenessTests(unittest.TestCase):
    def setUp(self):
        parent=ROOT/'work'/'effectiveness-tests';parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent)
        self.console=MissionConsole(Path(self.temp.name)/'state.db',provider_factory=lambda mode:ChatTestProvider())
    def tearDown(self):self.console.close();self.temp.cleanup()
    def test_all_agents_start_untested_and_cases_describe_real_criteria(self):
        page=self.console.evaluations.overview()
        self.assertEqual(len(page['agents']),101)
        self.assertTrue(all(a['verdict']=='untested' for a in page['agents']))
        self.assertTrue(all(c['criteria'] and c['version'] and c['agent_id'] for c in page['cases']))
        self.assertTrue(any(c['agent_id']=='assurance-003' for c in page['cases']))
        self.assertTrue(any(c['agent_id']=='engineering-001' for c in page['cases']))
        from collective101.benchmarks import grade
        case=self.console.evaluations.cases['intake-answer']
        self.assertFalse(grade(case,{'action':'reply','answer':4},self.console.organization.roster)['passed'])
    def test_live_run_requires_confirmation_and_fixture_evidence_never_rates_agents(self):
        with self.assertRaises(ValueError):self.console.evaluations.start({'cases':['intake-greeting'],'trials':1})
        job=self.console.evaluations.start({'cases':['intake-greeting'],'trials':1,'confirm_live':True,'max_calls':10})
        end=time.monotonic()+20
        while time.monotonic()<end:
            report=self.console.evaluations.detail(job['id'])
            if report['status'] not in {'queued','running'}:break
            time.sleep(.02)
        self.assertEqual(report['status'],'completed',report)
        self.assertEqual(len(report['trials']),1)
        self.assertEqual(report['trials'][0]['passed'],True)
        self.assertEqual(self.console.evaluations.overview()['agents'][0]['verdict'],'untested')
        self.assertNotIn('secret',str(report).lower())
    def test_scorecard_separates_unknowns_infrastructure_and_critical_failures(self):
        from collective101.effectiveness import scorecard
        rows=[{'case_id':'case-'+str(i%4),'passed':True,'failure_kind':None,'evidence_mode':'meta','human_pending':False,'critical':False} for i in range(24)]
        score=scorecard(rows)
        self.assertEqual(score['verdict'],'meets_benchmark')
        self.assertGreater(score['confidence_low'],.8)
        self.assertEqual(scorecard(rows[:2])['verdict'],'insufficient_evidence')
        infra=[{**r,'passed':False,'failure_kind':'provider'} for r in rows]
        self.assertEqual(scorecard(infra)['verdict'],'insufficient_evidence')
        self.assertEqual(scorecard(infra)['graded_trials'],0)
        self.assertEqual(scorecard([{**rows[0],'critical':True,'passed':False}])['verdict'],'needs_improvement')
        self.assertEqual(scorecard([{**r,'evidence_mode':'fixture'} for r in rows])['verdict'],'untested')
    def test_run_validation_does_not_start_unbounded_or_unknown_cases(self):
        for payload in [{'cases':['intake-greeting'],'trials':0}, {'cases':['missing'],'trials':1}, {'cases':[],'trials':1}, {'cases':['intake-greeting'],'trials':1,'max_calls':-1}]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):self.console.evaluations.start({**payload,'confirm_live':True})

    def test_all_registered_cases_can_be_queued_with_bounded_modes_trials_and_spend(self):
        service=self.console.evaluations;cases=list(service.cases)
        self.assertGreater(len(cases),12)
        modes=['specialist','generalist','memory_off','memory_on']
        with patch.object(service.pool,'submit') as dispatch:
            report=service.start({'cases':cases,'modes':modes,'trials':3,'confirm_live':True,'max_calls':160,'max_units':2_000_000})
        self.assertEqual(len(report['trials']),len(cases)*len(modes)*3)
        self.assertEqual(set(report['configuration']['case_snapshots']),set(cases))
        self.assertEqual(report['configuration']['max_calls'],160)
        self.assertEqual(report['configuration']['max_units'],2_000_000)
        self.assertEqual(report['calls'],0);dispatch.assert_called_once()

    def test_all_case_support_does_not_allow_malformed_ids_or_unsupported_team_comparisons(self):
        service=self.console.evaluations
        payloads=[{'cases':[['intake-greeting']]},{'cases':['intake-greeting',23]},
                  {'cases':['intake-greeting','intake-greeting']},
                  {'cases':list(service.cases),'modes':['specialist','organization']}]
        with patch.object(service.pool,'submit') as dispatch:
            for payload in payloads:
                with self.subTest(payload=payload),self.assertRaises(ValueError):service.start({**payload,'confirm_live':True})
            dispatch.assert_not_called()
    def test_comparison_pairs_matching_trials_and_excludes_infrastructure(self):
        from collective101.effectiveness import paired_comparison
        trials=[{'case_id':'a','trial':1,'mode':'memory_off','tokens':20,'seconds':2,'result':{'passed':False}},
            {'case_id':'a','trial':1,'mode':'memory_on','tokens':25,'seconds':1,'result':{'passed':True,'memory_sources':[['source-1']]}},
            {'case_id':'b','trial':1,'mode':'memory_off','tokens':10,'seconds':1,'result':{'passed':None,'failure_kind':'provider'}},
            {'case_id':'b','trial':1,'mode':'memory_on','tokens':20,'seconds':1,'result':{'passed':True}}]
        result=paired_comparison(trials,'memory_off','memory_on')
        self.assertEqual(result['paired_trials'],1);self.assertEqual(result['wins'],1)
        self.assertEqual(result['mean_token_difference'],5);self.assertEqual(result['mean_seconds_difference'],-1)
        self.assertEqual(result['memory_sources'],1)
    def test_human_review_cannot_approve_failed_automatic_prerequisites(self):
        from collective101.store import encode,now
        self.console.store.execute('INSERT INTO evaluation_runs(id,status,configuration,metadata,created_at) VALUES(?,?,?,?,?)',('manual','completed','{}','{}',now()))
        result={'passed':False,'automatic_passed':False,'requires_human':True,'human_pending':True}
        self.console.store.execute('INSERT INTO evaluation_trials VALUES(?,?,?,?,?,?,?,?,?,?,?)',('human-case','manual','copy-facts','communications-003','specialist',1,'completed',encode(result),1,5,.1))
        report=self.console.evaluations.review('human-case',True,'Readable, but the required business name is missing')
        self.assertFalse(report['trials'][0]['passed']);self.assertEqual(len(report['trials'][0]['reviews']),1)

if __name__=='__main__':unittest.main()
