"""Head evaluator/context and partial-budget regressions; scripted providers only."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from collective101.console import MissionConsole
from collective101.evaluations import MeteredProvider
from collective101.provider import Completion

ROOT=Path(__file__).resolve().parents[1]


class HeadProvider:
    name='fixture-head-evaluation-recovery'
    model='scripted'
    url=None

    def __init__(self,foreign_assignee=None):
        self.contexts=[]
        self.foreign_assignee=foreign_assignee

    def complete(self,messages,tools=None):
        context=json.loads(messages[1]['content']);self.contexts.append(context)
        value={'decision':'contribute','reason':'Scripted useful bounded onboarding draft.',
               'depends_on':[],'tasks':[{'key':'draft','title':'Draft onboarding notes',
                'instructions':'Draft the assigned onboarding outline using supplied information.',
                'assignee':self.foreign_assignee or context['employees'][0]['id'],
                'depends_on':[],'requires':['draft_artifact'],'tools':[],'outputs':['onboarding.md']}]}
        return Completion({'role':'assistant','content':json.dumps(value)},11)


class GreetingProvider:
    name='fixture-head-budget-recovery'
    calls=0

    def complete(self,messages,tools=None):
        self.calls+=1
        return Completion({'role':'assistant','content':json.dumps({'action':'reply','answer':'Hello.'})},7)


class HeadEvaluationRecoveryTests(unittest.TestCase):
    def setUp(self):
        root=ROOT/'work'/'head-evaluation-recovery';root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root)
        self.provider=HeadProvider()
        self.console=MissionConsole(Path(self.temp.name)/'state.db',provider_factory=lambda mode:self.provider)

    def tearDown(self):
        self.console.close();self.temp.cleanup()

    def test_all_ten_heads_reach_current_provider_with_only_own_employee_context(self):
        service=self.console.evaluations
        heads=[case for case in service.cases.values() if case['kind']=='head']
        self.assertEqual(len(heads),10)
        self.assertIsNone(self.console.organization.provider)
        for case in heads:
            with self.subTest(case=case['id']):
                meter=MeteredProvider(self.provider,max_calls=40,max_units=1_000_000)
                result=service._trial(case,'specialist',meter,'test-'+case['id'],threading.Event(),'test-run')
                self.assertTrue(result['passed'])
                self.assertTrue(result['human_pending'])
                self.assertIsNone(result['failure_kind'])
                self.assertEqual(meter.calls,1)
                context=self.provider.contexts[-1]
                expected={agent['id'] for agent in self.console.organization.roster.values()
                          if agent['department']==case['department'] and agent['role']!='department_lead'}
                self.assertEqual({employee['id'] for employee in context['employees']},expected)
                self.assertTrue(context['employees'])
                self.assertIsNone(self.console.organization.provider,'Evaluation must not rebind the live console organization.')

    def test_invalid_foreign_assignment_is_quality_failure_after_model_not_pre_dispatch_infrastructure(self):
        self.provider=HeadProvider(foreign_assignee='engineering-003')
        service=self.console.evaluations
        with patch.object(service.pool,'submit'):
            report=service.start({'cases':['head-assurance'],'trials':1,'confirm_live':True})
        service._run(report['id'],self.provider,service.stops[report['id']])
        current=service.detail(report['id']);trial=current['trials'][0]
        self.assertEqual(trial['calls'],1)
        self.assertEqual(trial['result']['failure_kind'],'quality')
        self.assertFalse(trial['result']['passed'])
        self.assertIsNone(self.console.organization.provider)

    def test_legacy_finite_batch_reports_admission_exhaustion_below_nominal_limit(self):
        # The next reservation cannot fit even though consumed units are below max_units.
        # Explicit finite budgets are compatibility controls; production defaults may be unlimited.
        self.provider=GreetingProvider();service=self.console.evaluations
        messages=[{'role':'system','content':'Return the reply contract.'},{'role':'user','content':'Hi'}]
        with patch.object(self.console,'intake_messages',return_value=(messages,[])),patch.object(service.pool,'submit'):
            report=service.start({'cases':['intake-greeting'],'trials':3,'confirm_live':True,
                                  'max_calls':10,'max_units':10_000})
            service._run(report['id'],self.provider,service.stops[report['id']])
        current=service.detail(report['id'])
        self.assertEqual(current['calls'],2)
        self.assertLess(current['units'],10_000)
        self.assertEqual(current['status'],'budget_exhausted')
        self.assertTrue(any(trial['status']=='budget_exhausted' or
                            (trial.get('result') or {}).get('failure_kind')=='budget'
                            for trial in current['trials']))


if __name__=='__main__':unittest.main()
