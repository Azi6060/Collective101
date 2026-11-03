"""Provider reliability regression cases; all HTTP responses are local mocks.

These exercise the actual Meta adapter and persisted agent harness without
using a real credential, external endpoint, or the user's running service.
"""
import io
import http.client
import json
import socket
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from collective101.agent_harness import AgentHarness
from collective101.console import MissionConsole
from collective101.department_runtime import DepartmentOrganization
from collective101.org_contracts import worker_result
from collective101.provider import MetaProvider, ProviderError
from collective101.store import CallBudgetExceeded
from collective101 import budgets

ROOT = Path(__file__).resolve().parents[1]
TEST_SECRET = 'provider-regression-placeholder-not-a-real-key'


def response(value=None, *, finish='stop', tokens=80):
    body = {'choices': [{'message': {'role': 'assistant',
             'content': json.dumps(value) if value is not None else '{"partial":'},
             'finish_reason': finish}], 'usage': {'total_tokens': tokens}}
    return io.BytesIO(json.dumps(body).encode('utf-8'))


class ProviderReliabilityTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / 'work' / 'provider-reliability-tests'
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.provider = MetaProvider(api_key=TEST_SECRET)
        self.org = DepartmentOrganization(Path(self.temp.name) / 'state.db', self.provider)
        self.mission = {'objective': 'Write accessibility requirements for a grocery landing page.',
                        'inputs': {}, 'constraints': [],
                        'acceptance_criteria': ['Provide complete accessibility requirements.'],
                        'allowed_capabilities': ['draft_artifact'], 'artifact_checks': []}
        self.task = {'outputs': ['requirements.md'],
                     'instructions': 'Write bounded accessibility requirements.',
                     'requires': ['draft_artifact'], 'tools': []}
        self.good = {'status': 'produced', 'summary': 'Requirements supplied.',
                     'limitations': [], 'capability_requests': [],
                     'artifacts': [{'path': 'requirements.md', 'content': 'Use landmarks and labelled controls.'}]}

    def tearDown(self):
        self.org.close()
        self.temp.cleanup()

    def invoke(self, run_id=None):
        run_id = run_id or self.org.create(self.mission)
        result = AgentHarness(self.org.store, self.provider, self.org.roster).invoke(
            run_id, 'work:design:a11y-requirements', 'design-005', 'work',
            {'mission': self.mission, 'task': self.task},
            lambda value: worker_result(value, self.task))
        return run_id, result

    @staticmethod
    def output_limit(request):
        payload = json.loads(request.data)
        return payload.get('max_completion_tokens', payload.get('max_tokens'))

    def test_timeout_then_truncation_recovers_on_third_recorded_budgeted_request(self):
        seen = []
        outcomes = [socket.timeout(), response(finish='length', tokens=4096), response(self.good)]
        def open_request(request, timeout):
            seen.append((request, timeout))
            outcome = outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        with patch('collective101.provider.urllib.request.build_opener') as build:
            build.return_value.open.side_effect = open_request
            run_id, result = self.invoke()
        self.assertEqual(result, self.good)
        self.assertEqual(len(seen), 3)
        self.assertGreaterEqual(seen[0][1], 120)
        self.assertGreater(seen[1][1], seen[0][1])
        self.assertGreater(self.output_limit(seen[2][0]), self.output_limit(seen[1][0]))
        calls = self.org.store.query('SELECT status,error FROM org_calls WHERE run_id=? ORDER BY attempt', (run_id,))
        self.assertEqual([call['status'] for call in calls], ['failed', 'failed', 'accepted'])
        self.assertIn('truncat', calls[1]['error'].lower())
        budget_id = self.org.store.query('SELECT budget_id FROM org_run_budgets WHERE run_id=?', (run_id,))[0]['budget_id']
        budget = budgets.inspect_budget(self.org.store, budget_id)
        self.assertEqual(budget['calls'], 3)
        self.assertEqual(budget['reported_tokens'], 4176)
        run = self.org.store.query('SELECT calls,tokens FROM org_runs WHERE id=?', (run_id,))[0]
        self.assertEqual(run, {'calls': 3, 'tokens': 4176})

    def test_http_401_is_recorded_once_without_retry_or_fallback(self):
        run_id = self.org.create(self.mission)
        with patch('collective101.provider.urllib.request.build_opener') as build:
            build.return_value.open.side_effect = urllib.error.HTTPError(
                'https://api.meta.ai/v1/chat/completions', 401, 'Unauthorized', {}, None)
            with self.assertRaisesRegex(ProviderError, '401'):
                self.invoke(run_id)
            self.assertEqual(build.return_value.open.call_count, 1)
        rows = self.org.store.query('SELECT status,output,error FROM org_calls WHERE run_id=?', (run_id,))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['status'], 'failed')
        self.assertIsNone(rows[0]['output'])
        self.assertNotIn(TEST_SECRET, json.dumps(rows))

    def test_truncated_response_never_becomes_a_completed_result(self):
        with patch('collective101.provider.urllib.request.build_opener') as build:
            build.return_value.open.return_value = response(self.good, finish='length', tokens=123)
            with self.assertRaises(ProviderError) as failure:
                self.provider.complete([{'role': 'user', 'content': 'Write a file.'}])
        self.assertEqual(failure.exception.kind, 'truncated')
        self.assertEqual(failure.exception.tokens, 123)
        self.assertTrue(failure.exception.retryable)

    def test_request_profiles_raise_limits_within_operator_caps(self):
        provider = MetaProvider(api_key=TEST_SECRET, timeout=120, max_output_tokens=20000)
        intake = provider.request_options('intake')
        work = provider.request_options('work')
        retry = provider.request_options('work', output_retries=2, transport_retries=3)
        self.assertGreater(work['max_tokens'], intake['max_tokens'])
        self.assertGreater(work['timeout'], intake['timeout'])
        self.assertEqual(retry['max_tokens'], 20000)
        self.assertLessEqual(retry['timeout'], 300)
        self.assertEqual(intake['reasoning_effort'], 'low')

    def test_phase_output_reservation_can_block_before_sending_http(self):
        run_id = self.org.create(self.mission)
        # Leave enough admission units for the old 4096 cap but not a work
        # request's 16384 output reservation, regardless of context size.
        binding = self.org.store.query('SELECT budget_id FROM org_run_budgets WHERE run_id=?', (run_id,))[0]
        self.org.store.execute('UPDATE org_budgets SET max_tokens=16000 WHERE id=?', (binding['budget_id'],))
        with patch('collective101.provider.urllib.request.build_opener') as build:
            build.return_value.open.return_value = response(self.good)
            with self.assertRaises(CallBudgetExceeded):
                self.invoke(run_id)
            self.assertEqual(build.return_value.open.call_count, 0)

    def test_three_transient_failures_stop_with_provider_specific_diagnosis(self):
        run_id = self.org.create(self.mission)
        with patch('collective101.provider.urllib.request.build_opener') as build:
            build.return_value.open.side_effect = socket.timeout()
            with self.assertRaises(Exception) as failure:
                self.invoke(run_id)
            self.assertEqual(build.return_value.open.call_count, 3)
        message = str(failure.exception).lower()
        self.assertIn('timeout', message)
        self.assertNotIn('failed validation', message)
        self.assertEqual(self.org.store.query('SELECT COUNT(*) AS n FROM org_calls WHERE run_id=?', (run_id,))[0]['n'], 3)
        # Restarting/resuming the same step must not reset retry allowances.
        with patch('collective101.provider.urllib.request.build_opener') as build:
            with self.assertRaises(Exception):
                self.invoke(run_id)
            self.assertEqual(build.return_value.open.call_count, 0)

    def test_intake_timeout_then_truncation_uses_same_bounded_budgeted_recovery(self):
        console = MissionConsole(Path(self.temp.name) / 'intake.db',
                                 provider_factory=lambda mode: self.provider)
        outcomes = [socket.timeout(), response(finish='length', tokens=4096),
                    response({'action': 'reply', 'answer': 'A complete test reply.'}, tokens=20)]
        seen = []
        def open_request(request, timeout):
            seen.append((request, timeout))
            outcome = outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        try:
            with patch('collective101.provider.urllib.request.build_opener') as build:
                build.return_value.open.side_effect = open_request
                chat = console.submit('Hi', 'meta', 'provider-reliability-intake')
                end = time.monotonic() + 15
                while chat['id'] in console.active and time.monotonic() < end:
                    time.sleep(.02)
                chat = console.chat(chat['id'])
            self.assertEqual(chat['status'], 'answered', chat['error'])
            self.assertEqual(chat['transcript'][-1]['content'], 'A complete test reply.')
            self.assertEqual(chat['budget']['calls'], 3)
            self.assertEqual(chat['budget']['reported_tokens'], 4116)
            self.assertGreater(seen[1][1], seen[0][1])
            self.assertGreater(self.output_limit(seen[2][0]), self.output_limit(seen[1][0]))
            records = console.store.query('SELECT status FROM console_intake_calls WHERE chat_id=? ORDER BY sequence', (chat['id'],))
            self.assertEqual([r['status'] for r in records], ['failed', 'failed', 'accepted'])
        finally:
            console.close()

    def test_repeated_truncation_stops_at_operator_cap_without_accepting_partial_work(self):
        self.provider = MetaProvider(api_key=TEST_SECRET, max_output_tokens=20000)
        run_id = self.org.create(self.mission)
        limits = []
        def open_request(request, timeout):
            limits.append(self.output_limit(request))
            return response(self.good, finish='length', tokens=123)
        with patch('collective101.provider.urllib.request.build_opener') as build:
            build.return_value.open.side_effect = open_request
            with self.assertRaisesRegex(RuntimeError, 'truncat'):
                self.invoke(run_id)
        self.assertEqual(limits, [16384, 20000])
        records = self.org.store.query('SELECT status,output,error_kind FROM org_calls WHERE run_id=? ORDER BY attempt', (run_id,))
        self.assertEqual([r['error_kind'] for r in records], ['truncated', 'truncated'])
        self.assertTrue(all(r['status'] == 'failed' and r['output'] is None for r in records))
        budget_id = self.org.store.query('SELECT budget_id FROM org_run_budgets WHERE run_id=?', (run_id,))[0]['budget_id']
        self.assertEqual(budgets.inspect_budget(self.org.store, budget_id)['reported_tokens'], 246)
        with patch('collective101.provider.urllib.request.build_opener') as build:
            with self.assertRaisesRegex(RuntimeError, 'truncat'):
                self.invoke(run_id)
            self.assertEqual(build.return_value.open.call_count, 0)

    def test_truncation_escalation_is_denied_before_a_second_http_request_when_budget_is_too_small(self):
        run_id = self.org.create(self.mission)
        budget_id = self.org.store.query('SELECT budget_id FROM org_run_budgets WHERE run_id=?', (run_id,))[0]['budget_id']
        def open_request(request, timeout):
            # Retain room for an old 4096-token retry, but not the new 32768
            # reservation. The next request must be denied, not down-capped.
            self.org.store.execute('UPDATE org_budgets SET max_tokens=charged_tokens+10000 WHERE id=?', (budget_id,))
            return response(finish='length', tokens=123)
        with patch('collective101.provider.urllib.request.build_opener') as build:
            build.return_value.open.side_effect = open_request
            with self.assertRaises(CallBudgetExceeded):
                self.invoke(run_id)
            self.assertEqual(build.return_value.open.call_count, 1)
        budget = budgets.inspect_budget(self.org.store, budget_id)
        self.assertEqual(budget['calls'], 1)
        self.assertEqual(budget['reported_tokens'], 123)
        self.assertLess(budget['charged_tokens'], budget['max_tokens'])
        self.assertEqual(self.org.store.query('SELECT COUNT(*) AS n FROM org_calls WHERE run_id=?', (run_id,))[0]['n'], 1)

    def test_valid_reported_usage_is_retained_when_provider_response_contract_is_malformed(self):
        for choices in [[], [{'message': {'role': 'user', 'content': 'Wrong role.'}, 'finish_reason': 'stop'}]]:
            with self.subTest(choices=choices):
                run_id = self.org.create(self.mission)
                malformed = {'choices': choices, 'usage': {'total_tokens': 123}}
                with patch('collective101.provider.urllib.request.build_opener') as build:
                    build.return_value.open.return_value = io.BytesIO(json.dumps(malformed).encode())
                    with self.assertRaises(ProviderError) as failure:
                        self.invoke(run_id)
                    self.assertEqual(build.return_value.open.call_count, 1)
                self.assertEqual(failure.exception.kind, 'invalid_response')
                self.assertEqual(failure.exception.tokens, 123)
                budget_id = self.org.store.query('SELECT budget_id FROM org_run_budgets WHERE run_id=?', (run_id,))[0]['budget_id']
                self.assertEqual(budgets.inspect_budget(self.org.store, budget_id)['reported_tokens'], 123)
                self.assertEqual(self.org.store.query('SELECT tokens FROM org_runs WHERE id=?', (run_id,))[0]['tokens'], 123)

    def test_interrupted_response_reads_are_retryable_connection_failures_without_partial_results(self):
        class InterruptedRead:
            def __init__(self, error):
                self.error = error
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, *args):
                raise self.error
        failures = [ConnectionResetError('Connection reset during response read'),
                    http.client.IncompleteRead(b'{"choices":[', 100)]
        for error in failures:
            with self.subTest(error=type(error).__name__):
                with patch('collective101.provider.urllib.request.build_opener') as build:
                    build.return_value.open.return_value = InterruptedRead(error)
                    with self.assertRaises(ProviderError) as caught:
                        self.provider.complete([{'role': 'user', 'content': 'Produce a complete file.'}])
                    self.assertEqual(build.return_value.open.call_count, 1)
                self.assertEqual(caught.exception.kind, 'connection')
                self.assertTrue(caught.exception.retryable)
                self.assertEqual(caught.exception.tokens, 0)
                self.assertNotIn('{"choices"', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
