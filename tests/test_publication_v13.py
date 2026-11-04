"""New work publication must distinguish genuine blockers from empty placeholders.

These are isolated, deterministic harness tests. Existing accepted historical
outputs remain replayable and are not retroactively revalidated by the new guard.
"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from collective101.agent_harness import AgentHarness
from collective101.department_runtime import DepartmentOrganization
from collective101.org_contracts import worker_result
from collective101.provider import Completion
from collective101.store import encode, now
from collective101.budgets import inspect_budget


PLACEHOLDER = {'status': 'blocked', 'summary': 'Placeholder: retrying the correct publication transport.',
               'limitations': [], 'capability_requests': [], 'artifacts': []}
PRODUCED = {'status': 'produced', 'summary': 'Published the assigned local files.',
            'limitations': [], 'capability_requests': [],
            'artifacts': [{'path': 'corpus.json', 'content': '[{"id":"one","text":"local demo"}]'},
                          {'path': 'notes.md', 'content': '# Local corpus\n\nSource-only test fixture.\n'}]}


class PublicationFixture:
    name = 'fixture'
    structured_transport = 'function'
    def __init__(self, results):
        self.results = results
        self.inputs = []
    def request_options(self, phase='work', output_retries=0, transport_retries=0):
        return {'max_tokens': 4096, 'timeout': 120, 'reasoning_effort': 'high',
                'phase': phase, 'structured_transport': 'function', 'file_submission': 'flat'}
    def complete_with_options(self, messages, options):
        self.inputs.append(json.loads(messages[1]['content']))
        value = self.results[min(len(self.inputs)-1, len(self.results)-1)]
        return Completion({'role': 'assistant', 'content': json.dumps(value)}, 17)


class PublicationGuardTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / 'work' / 'publication-v13-tests'
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.provider = PublicationFixture([PLACEHOLDER, PRODUCED])
        self.org = DepartmentOrganization(Path(self.temp.name) / 'state.db', self.provider)
        self.rid = self.org.create({'objective': 'Publish an assigned local corpus and note.',
            'departments': ['data'], 'inputs': {}, 'constraints': [],
            'acceptance_criteria': ['Both requested source files are supplied.'],
            'allowed_capabilities': ['draft_artifact'], 'max_repair_rounds': 0})
        self.task = {'key': 'corpus', 'title': 'Prepare corpus', 'instructions': 'Create both assigned source files.',
                     'assignee': 'data-008', 'outputs': ['corpus.json', 'notes.md'],
                     'depends_on': [], 'requires': ['draft_artifact'], 'tools': []}
        self.ctx = {'mission': self.org.inspect(self.rid)['mission'], 'task': self.task}
        self.key = 'work:data:corpus'

    def tearDown(self):
        self.org.close()
        self.temp.cleanup()

    def invoke(self):
        harness = AgentHarness(self.org.store, self.provider, self.org.roster)
        return harness.invoke(self.rid, self.key, 'data-008', 'work', self.ctx,
                              lambda value: worker_result(value, self.task, 'data'))

    def test_empty_placeholder_retries_with_native_publication_guidance_and_usage(self):
        result = self.invoke()
        self.assertEqual(result, PRODUCED)
        self.assertEqual(len(self.provider.inputs), 2)
        first = self.provider.inputs[0]
        self.assertEqual(first['available_tools'], [])
        delivery = first['artifact_delivery']
        self.assertTrue(delivery['available'])
        self.assertEqual(delivery['submission_function'], 'submit_completed_work')
        self.assertEqual(delivery['native_file_fields'], {'file_1': 'corpus.json', 'file_2': 'notes.md'})
        self.assertIn('submit_completed_work', self.provider.inputs[1]['previous_error'])
        calls = self.org.store.query('SELECT status,error_kind FROM org_calls WHERE run_id=? ORDER BY attempt', (self.rid,))
        self.assertEqual([r['status'] for r in calls], ['failed', 'accepted'])
        self.assertEqual(calls[0]['error_kind'], 'validation')
        budget = inspect_budget(self.org.store, self.rid)
        self.assertEqual(budget['calls'], 2)
        self.assertEqual(budget['reported_tokens'], 34)

    def test_persistent_empty_blocked_response_stops_after_two_validation_failures(self):
        self.provider.results = [PLACEHOLDER]
        with self.assertRaises(RuntimeError) as raised:
            self.invoke()
        self.assertIn('2 invalid agent output', str(raised.exception))
        self.assertEqual(len(self.provider.inputs), 2)
        calls = self.org.store.query('SELECT status FROM org_calls WHERE run_id=?', (self.rid,))
        self.assertEqual([r['status'] for r in calls], ['failed', 'failed'])

    def test_new_genuine_blocker_with_a_limitation_is_accepted_without_forced_success(self):
        blocked = {**PLACEHOLDER, 'summary': 'Required private source was not provided.',
                   'limitations': ['The requested corpus depends on an unavailable user document.']}
        self.provider.results = [blocked]
        self.assertEqual(self.invoke(), blocked)
        self.assertEqual(len(self.provider.inputs), 1)

    def test_historical_accepted_empty_blocker_replays_unchanged_without_new_calls(self):
        digest = hashlib.sha256(encode({'agent': self.org.roster['data-008'], 'phase': 'work', 'context': self.ctx}).encode()).hexdigest()
        historical_input = [{'role': 'system', 'content': 'Recorded historical fixture context.'},
                            {'role': 'user', 'content': encode(self.ctx)}]
        self.org.store.execute('INSERT INTO org_calls(run_id,step_key,attempt,agent_id,phase,input_hash,input,status,output,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
            (self.rid, self.key, 1, 'data-008', 'work', digest, encode(historical_input), 'accepted', encode(PLACEHOLDER), now()))
        before = self.org.store.query('SELECT * FROM org_calls WHERE run_id=?', (self.rid,))
        self.assertEqual(self.invoke(), PLACEHOLDER)
        self.assertEqual(self.provider.inputs, [])
        self.assertEqual(self.org.store.query('SELECT * FROM org_calls WHERE run_id=?', (self.rid,)), before)


if __name__ == '__main__':
    unittest.main()
