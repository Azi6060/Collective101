"""Parallel evaluation accounting and cancellation, with local fixture calls only."""
import json
import tempfile
import threading
import unittest
from pathlib import Path

from collective101.console import MissionConsole
from collective101.provider import Completion
from collective101.store import encode, now


class BarrierReplyProvider:
    name = 'fixture-parallel-evaluation'

    def __init__(self, stop=None):
        self.barrier = threading.Barrier(4)
        self.lock = threading.Lock()
        self.stop = stop
        self.active = 0
        self.maximum = 0
        self.calls = 0

    def complete(self, messages, tools=None):
        with self.lock:
            self.calls += 1
            self.active += 1
            self.maximum = max(self.maximum, self.active)
        try:
            # Synchronization proves overlap without a wall-clock speed threshold.
            # The timeout bounds a RED serial implementation rather than hanging it.
            try:
                self.barrier.wait(timeout=3)
            except threading.BrokenBarrierError:
                pass
            if self.stop is not None:
                self.stop.set()
            return Completion({'role': 'assistant', 'content': json.dumps({
                'action': 'reply', 'answer': '4'})}, 7)
        finally:
            with self.lock:
                self.active -= 1


class EvaluationParallelTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / 'work' / 'evaluation-parallel-tests'
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.console = MissionConsole(Path(self.temp.name) / 'state.db')
        self.service = self.console.evaluations

    def tearDown(self):
        self.console.close()
        self.temp.cleanup()

    def seed(self, *, repeats=1):
        rid = 'parallel-fixture'
        case = self.service.cases['intake-answer']
        modes = ['specialist', 'generalist', 'memory_off', 'memory_on']
        config = {
            'cases': ['intake-answer'], 'modes': modes, 'trials': repeats,
            'max_calls': 0, 'max_units': 0,
            'per_trial_calls': 0, 'per_trial_units': 0, 'concurrency': 4,
            'case_snapshots': {'intake-answer': case},
            'agent_snapshots': {case['agent_id']: self.console.organization.roster[case['agent_id']]},
            'memory_snapshots': {'intake-answer': []},
        }
        metadata = {'provider': 'fixture-parallel-evaluation', 'suite': 'fixture-parallel-only'}
        with self.console.store.transaction() as db:
            db.execute('INSERT INTO evaluation_runs(id,status,configuration,metadata,created_at) VALUES(?,?,?,?,?)',
                       (rid, 'queued', encode(config), encode(metadata), now()))
            for repeat in range(1, repeats + 1):
                for mode in modes:
                    db.execute('INSERT INTO evaluation_trials(id,run_id,case_id,agent_id,mode,trial,status) VALUES(?,?,?,?,?,?,?)',
                               (f'{mode}-{repeat}', rid, case['id'], case['agent_id'], mode, repeat, 'queued'))
        return rid

    def test_four_independent_trials_overlap_and_keep_own_usage(self):
        rid = self.seed()
        provider = BarrierReplyProvider()
        self.service._run(rid, provider, threading.Event())
        report = self.service.detail(rid)
        self.assertEqual(report['configuration']['concurrency'], 4)
        self.assertGreaterEqual(provider.maximum, 2)
        self.assertLessEqual(provider.maximum, 4)
        self.assertEqual(provider.calls, 4)
        self.assertEqual(report['status'], 'completed', report.get('error'))
        self.assertEqual((report['calls'], report['tokens']), (4, 28))
        self.assertEqual(len(report['trials']), 4)
        for trial in report['trials']:
            self.assertEqual(trial['status'], 'completed')
            self.assertTrue(trial['result']['passed'])
            # Shared-counter differences incorrectly attribute other concurrent
            # requests to this trial. Each own meter must report exactly one.
            self.assertEqual(trial['calls'], 1)
            self.assertEqual(trial['tokens'], 7)
        self.assertEqual(sum(trial['calls'] for trial in report['trials']), report['calls'])
        self.assertEqual(sum(trial['tokens'] for trial in report['trials']), report['tokens'])

    def test_stop_drains_four_inflight_trials_and_does_not_dispatch_second_wave(self):
        rid = self.seed(repeats=2)
        stop = threading.Event()
        provider = BarrierReplyProvider(stop)
        self.service._run(rid, provider, stop)
        report = self.service.detail(rid)
        self.assertEqual(provider.calls, 4)
        self.assertEqual(report['status'], 'cancelled', report.get('error'))
        self.assertEqual((report['calls'], report['tokens']), (4, 28))
        self.assertEqual(provider.active, 0)
        self.assertGreaterEqual(sum(trial['status'] == 'cancelled' for trial in report['trials']), 4)
        self.assertFalse(any(trial['status'] in {'queued', 'running'} for trial in report['trials']))
        self.assertEqual(sum(trial['calls'] for trial in report['trials']), report['calls'])
        self.assertEqual(sum(trial['tokens'] for trial in report['trials']), report['tokens'])


if __name__ == '__main__':
    unittest.main()
