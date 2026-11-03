"""Search worker response regressions; scripted Meta/Brave boundaries only.

The observed Bukit Jalil run never reached a recorded tool call. Rejected raw
model text was not stored, so these tests reproduce independently established
empty/non-JSON response handling defects without claiming its exact raw output.
"""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collective101.agent_harness import AgentHarness
from collective101.department_runtime import DepartmentOrganization
from collective101.org_contracts import worker_result
from collective101.provider import MetaProvider, ProviderError, parse_object
from collective101 import budgets

ROOT=Path(__file__).resolve().parents[1]


def response(content, tokens=31):
    return io.BytesIO(json.dumps({'choices':[{'message':{'role':'assistant','content':content},
        'finish_reason':'stop'}],'usage':{'total_tokens':tokens}}).encode())


class SearchResponseRegressions(unittest.TestCase):
    def test_muse_requests_constrain_json_without_changing_native_legacy_tool_protocol(self):
        provider=MetaProvider(api_key='test-placeholder-not-a-key')
        with patch('collective101.provider.urllib.request.build_opener') as opener:
            opener.return_value.open.return_value=response('{"action":"reply","answer":"hi"}')
            provider.complete([{'role':'user','content':'Return a JSON reply'}])
            payload=json.loads(opener.return_value.open.call_args.args[0].data)
        self.assertEqual(payload['response_format']['type'],'json_schema')
        self.assertEqual(payload['response_format']['json_schema']['schema']['type'],'object')
    def test_empty_model_completion_is_retryable_provider_failure_with_usage(self):
        provider=MetaProvider(api_key='test-placeholder-not-a-key')
        with patch('collective101.provider.urllib.request.build_opener') as opener:
            opener.return_value.open.return_value=response('',tokens=47)
            with self.assertRaises(ProviderError) as failure:
                provider.complete([{'role':'user','content':'Search public cafe information.'}])
        self.assertEqual(failure.exception.kind,'empty_output')
        self.assertTrue(failure.exception.retryable)
        self.assertEqual(failure.exception.tokens,47)
        self.assertRegex(str(failure.exception).lower(),r'empty|blank|missing.*content')

    def test_non_json_agent_text_has_actionable_diagnostic_without_echoing_response(self):
        rejected='I will search now. private-test-canary-should-not-be-echoed'
        with self.assertRaises(ValueError) as failure:parse_object(rejected)
        self.assertIn('JSON',str(failure.exception))
        self.assertIn('tool_request',str(failure.exception))
        self.assertNotIn('private-test-canary',str(failure.exception))
        diagnostic=getattr(failure.exception,'diagnostic',None)
        self.assertIsInstance(diagnostic,dict)
        shape=diagnostic.get('response_shape',diagnostic)
        self.assertTrue(shape.get('category'))
        self.assertEqual(shape.get('characters'),len(rejected))
        self.assertNotIn('private-test-canary',json.dumps(diagnostic))

    def test_object_parser_accepts_bom_and_uppercase_json_fence_without_extracting_prose(self):
        expected={'tool_request':{'name':'web_search','arguments':{'query':'Bukit Jalil cafes'}}}
        for value in ['\ufeff'+json.dumps(expected),'\ufeff```JSON\n'+json.dumps(expected)+'\n```']:
            with self.subTest(value=value):self.assertEqual(parse_object(value),expected)

    def test_malformed_work_records_bounded_response_shape_instead_of_raw_model_text(self):
        parent=ROOT/'work'/'search-response-regressions';parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as temporary:
            provider=MetaProvider(api_key='test-placeholder-not-a-key')
            org=DepartmentOrganization(Path(temporary)/'state.db',provider)
            mission={'objective':'Find public cafes and cite sources.', 'inputs':{},'constraints':[],
                'acceptance_criteria':['Provide cited findings'],'allowed_capabilities':['draft_artifact'],'artifact_checks':[]}
            task={'outputs':['cafes.md'],'instructions':'Produce cited findings.',
                'requires':['draft_artifact'],'tools':[]}
            rejected='I will search now. private-diagnostic-canary-must-not-be-stored'
            try:
                rid=org.create(mission)
                with patch('collective101.provider.urllib.request.build_opener') as opener:
                    opener.return_value.open.side_effect=[response(rejected),response(rejected)]
                    with self.assertRaises(RuntimeError):
                        AgentHarness(org.store,provider,org.roster).invoke(rid,
                            'work:research:find-cafes','research-004','work',{'mission':mission,'task':task},
                            lambda value:worker_result(value,task,'research'))
                calls=org.store.query('SELECT output,error FROM org_calls WHERE run_id=? ORDER BY attempt',(rid,))
                self.assertEqual(len(calls),2)
                for call in calls:
                    self.assertIsNotNone(call['output'])
                    diagnostic=json.loads(call['output']);shape=diagnostic['response_shape']
                    self.assertTrue(shape.get('category'))
                    self.assertEqual(shape['characters'],len(rejected))
                    self.assertNotIn('private-diagnostic-canary',json.dumps(call))
                    self.assertLess(len(call['output']),2000)
            finally:org.close()

    def test_empty_completion_then_search_and_result_keep_separate_failure_budget_and_evidence(self):
        parent=ROOT/'work'/'search-response-regressions';parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as temporary:
            provider=MetaProvider(api_key='test-placeholder-not-a-key')
            org=DepartmentOrganization(Path(temporary)/'state.db',provider)
            mission={'objective':'Find public cafe information in Bukit Jalil and cite observed search results.',
                'inputs':{},'constraints':[], 'acceptance_criteria':['Provide evidence-linked findings'],
                'allowed_capabilities':['draft_artifact','web_search'],'artifact_checks':[]}
            task={'outputs':['cafes.md'],'instructions':'Search public cafe information, cite retrieved results.',
                'requires':['draft_artifact'],'tools':['web_search']}
            good={'status':'produced','summary':'Scripted findings from observed search results.',
                'limitations':['Scripted test evidence only.'],'capability_requests':[],
                'artifacts':[{'path':'cafes.md','content':'Observed fixture reference: https://example.com/cafe'}]}
            tool={'tool_request':{'name':'web_search','arguments':{'query':'Bukit Jalil cafes'}}}
            try:
                rid=org.create(mission)
                with patch.dict('os.environ',{'BRAVE_SEARCH_API_KEY':'test-search-placeholder'}), \
                     patch('collective101.provider.urllib.request.build_opener') as opener, \
                     patch('collective101.agent_tools.web_search',return_value={
                         'status':'ok','results':[{'title':'Fixture cafe','url':'https://example.com/cafe','snippet':'Scripted public result'}]}) as search:
                    opener.return_value.open.side_effect=[response(''),response(json.dumps(tool)),response(json.dumps(good))]
                    result=AgentHarness(org.store,provider,org.roster).invoke(rid,
                        'work:research:find-bukit-jalil-cafes','research-004','work',
                        {'mission':mission,'task':task},lambda value:worker_result(value,task,'research'))
                self.assertEqual(result,good)
                self.assertEqual(search.call_count,1)
                calls=org.store.query('SELECT status,error_kind FROM org_calls WHERE run_id=? ORDER BY attempt',(rid,))
                self.assertEqual([row['status'] for row in calls],['failed','tool_result','accepted'])
                self.assertEqual(calls[0]['error_kind'],'empty_output')
                tools=org.store.query('SELECT name,result FROM org_tool_calls WHERE run_id=?',(rid,))
                self.assertEqual(len(tools),1)
                self.assertEqual(tools[0]['name'],'web_search')
                self.assertEqual(json.loads(tools[0]['result'])['status'],'ok')
                budget_id=org.store.query('SELECT budget_id FROM org_run_budgets WHERE run_id=?',(rid,))[0]['budget_id']
                budget=budgets.inspect_budget(org.store,budget_id)
                self.assertEqual(budget['calls'],3)
                self.assertEqual(budget['reported_tokens'],93)
            finally:org.close()


if __name__=='__main__':unittest.main()
