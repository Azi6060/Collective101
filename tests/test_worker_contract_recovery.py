"""Blocked worker recovery and bounded diagnostics; scripted provider only.

These reproduce the independently established blocked/files contradiction and
lost blocker metadata. They do not claim the unlogged original worker rationale
or contact the user's Meta/Brave connectors.
"""
import copy
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collective101.agent_harness import AgentHarness
from collective101.department_runtime import DepartmentOrganization
from collective101.org_contracts import worker_result
from collective101.provider import Completion

ROOT = Path(__file__).resolve().parents[1]


class ScriptedBlockedWorker:
    name = 'fixture-worker-contract-recovery'

    def __init__(self, rejected, *, repair=False):
        self.rejected = rejected
        self.repair = repair

    def complete(self, messages, tools=None):
        context = json.loads(messages[1]['content'])
        feedback = context.get('previous_error') or ''
        corrected = self.repair and re.search(r'artifacts\s*(?:=|:)\s*\[\s*\]', feedback)
        value = copy.deepcopy(self.rejected)
        if corrected:
            value['artifacts'] = []
        return Completion({'role': 'assistant', 'content': json.dumps(value)}, 7)


class WorkerContractRecoveryTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / 'work' / 'worker-contract-recovery'
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.mission = {
            'objective': 'Find evidence-linked public cafe information.',
            'inputs': {}, 'constraints': [],
            'acceptance_criteria': ['Provide cited findings or disclose unavailable evidence.'],
            'allowed_capabilities': ['draft_artifact'], 'artifact_checks': [],
        }
        self.task = {
            'outputs': ['cafes.md'], 'instructions': 'Provide verified cafe findings.',
            'requires': ['draft_artifact'], 'tools': [],
        }
        self.blocked = {
            'status': 'blocked', 'summary': 'Current cafe details could not be verified.',
            'limitations': ['No successful public source observation is available.'],
            'capability_requests': ['Current public search evidence'],
            'artifacts': [{'path': 'cafes.md', 'content': 'unpublished-file-content-canary'}],
        }
        self.org = DepartmentOrganization(
            Path(self.temp.name) / 'state.db', ScriptedBlockedWorker(self.blocked))

    def tearDown(self):
        self.org.close()
        self.temp.cleanup()

    def invoke(self, provider=None):
        provider = provider or self.org.provider
        run_id = self.org.create(self.mission)
        self.run_id = run_id
        return AgentHarness(self.org.store, provider, self.org.roster).invoke(
            run_id, 'work:research:bukit-jalil-scan', 'research-004', 'work',
            {'mission': self.mission, 'task': self.task},
            lambda value: worker_result(value, self.task, 'research'))

    def test_blocked_worker_cannot_publish_files_but_can_report_an_empty_result(self):
        with self.assertRaisesRegex(ValueError, 'Blocked workers cannot publish'):
            worker_result(copy.deepcopy(self.blocked), self.task, 'research')
        legal = copy.deepcopy(self.blocked)
        legal['artifacts'] = []
        self.assertEqual(worker_result(legal, self.task, 'research')['status'], 'blocked')
        self.assertEqual(legal['artifacts'], [])

    def test_rejected_work_retains_blocker_diagnostics_without_artifact_content(self):
        with self.assertRaises(RuntimeError):
            self.invoke()
        calls = self.org.store.query(
            'SELECT status,output FROM org_calls WHERE run_id=? ORDER BY attempt', (self.run_id,))
        self.assertEqual(len(calls), 2)
        for call in calls:
            self.assertEqual(call['status'], 'failed')
            diagnostic = json.loads(call['output'])
            state = diagnostic.get('worker_state')
            self.assertIsInstance(state, dict, 'Retain why the worker says it was blocked.')
            self.assertEqual(state, {key: self.blocked[key] for key in
                                    ('status', 'summary', 'limitations', 'capability_requests')})
            self.assertEqual(diagnostic['artifact_paths'], ['cafes.md'])
            self.assertNotIn('unpublished-file-content-canary', call['output'])
            self.assertLessEqual(len(call['output']), 8192)
        self.assertEqual(self.org.store.query(
            'SELECT * FROM org_artifacts WHERE run_id=?', (self.run_id,)), [])

    def test_rejected_blocker_metadata_is_bounded_and_omits_nested_objects(self):
        oversized = copy.deepcopy(self.blocked)
        oversized['summary'] = 'reason ' * 1500
        oversized['limitations'] = ['limitation ' * 1000] * 30 + [{'raw': 'nested-private-canary'}]
        oversized['capability_requests'] = [{'raw': 'nested-private-canary'}] + ['capability ' * 1000] * 20
        with self.assertRaises(RuntimeError):
            self.invoke(ScriptedBlockedWorker(oversized))
        for call in self.org.store.query(
                'SELECT output FROM org_calls WHERE run_id=?', (self.run_id,)):
            self.assertLessEqual(len(call['output']), 8192)
            self.assertNotIn('nested-private-canary', call['output'])
            self.assertNotIn('unpublished-file-content-canary', call['output'])
            state = json.loads(call['output']).get('worker_state')
            self.assertIsInstance(state, dict)
            self.assertEqual(state['status'], 'blocked')
            self.assertIsInstance(state['summary'], str)
            self.assertLess(len(state['summary']), len(oversized['summary']))
            for field, maximum in [('limitations', 12), ('capability_requests', 8)]:
                self.assertIsInstance(state[field], list)
                self.assertLessEqual(len(state[field]), maximum)
                self.assertTrue(all(isinstance(item, str) for item in state[field]))

    def test_retry_teaches_legal_blocked_shape_without_promoting_or_publishing(self):
        result = self.invoke(ScriptedBlockedWorker(self.blocked, repair=True))
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['artifacts'], [])
        self.assertEqual(result['capability_requests'], self.blocked['capability_requests'])
        calls = self.org.store.query(
            'SELECT status,output FROM org_calls WHERE run_id=? ORDER BY attempt', (self.run_id,))
        self.assertEqual([call['status'] for call in calls], ['failed', 'accepted'])
        self.assertEqual(json.loads(calls[1]['output'])['status'], 'blocked')
        self.assertEqual(self.org.store.query(
            'SELECT * FROM org_artifacts WHERE run_id=?', (self.run_id,)), [])

    def test_terminal_validation_failure_also_identifies_observed_search_failure(self):
        base=self.org.provider
        class SearchThenBlocked:
            name='fixture-search-then-blocked'
            def complete(self,messages,tools=None):
                context=json.loads(messages[1]['content'])
                if not context['tool_results']:
                    return Completion({'content':json.dumps({'tool_request':{
                        'name':'web_search','arguments':{'query':'Bukit Jalil cafes'}}})},7)
                return base.complete(messages,tools)
        self.mission['allowed_capabilities'].append('web_search')
        self.task['tools']=['web_search']
        with patch.dict('os.environ',{'BRAVE_SEARCH_API_KEY':'fixture-key'}), patch(
            'collective101.agent_tools.web_search',return_value={'status':'unavailable',
                'error_kind':'rate_limited','http_status':429,'error':'Brave rate or usage limit reached (HTTP 429).'}) as search:
            with self.assertRaisesRegex(RuntimeError,r'web_search.*429'):
                self.invoke(SearchThenBlocked())
        self.assertEqual(search.call_count,1)
        self.assertEqual(self.org.store.query('SELECT * FROM org_artifacts WHERE run_id=?',(self.run_id,)),[])


if __name__ == '__main__':
    unittest.main()
