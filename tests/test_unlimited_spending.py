"""Unlimited spending is explicit accounting, not disabled execution safety.

All providers are local fakes and state is disposable. No API or production
database is accessed. Zero ceilings denote unlimited calls/admission units.
"""
import tempfile
import unittest
from pathlib import Path

from collective101 import budgets
from collective101.context_limits import MAX_INPUT_BYTES
from collective101.evaluations import MeteredProvider
from collective101.provider import Completion
from collective101.store import Store, CallBudgetExceeded


class CountingProvider:
    name = 'fixture-unlimited-accounting'

    def __init__(self):
        self.calls = 0

    def complete(self, messages, tools=None):
        self.calls += 1
        return Completion({'role': 'assistant', 'content': '{}'}, 7)


class UnlimitedSpendingTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / 'work' / 'unlimited-spending-tests'
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.store = Store(Path(self.temp.name) / 'state.db')
        with self.store.transaction() as db:
            db.executescript(budgets.SCHEMA)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_new_budget_defaults_to_unlimited_call_and_admission_accounting(self):
        budgets.create_budget(self.store, 'default')
        value = budgets.inspect_budget(self.store, 'default')
        self.assertEqual(value['max_calls'], 0)
        self.assertEqual(value['max_tokens'], 0)

    def test_unlimited_budget_records_usage_beyond_both_previous_ceilings(self):
        budgets.create_budget(self.store, 'unlimited', max_calls=0, max_tokens=0)
        messages = [{'role': 'user', 'content': 'x' * 60000}]
        charged = 0
        for _ in range(200):
            charged += budgets.reserve(self.store, 'unlimited', messages)
            budgets.record_usage(self.store, 'unlimited', 7)
        value = budgets.inspect_budget(self.store, 'unlimited')
        self.assertEqual(value['calls'], 200)
        self.assertGreater(value['charged_tokens'], 10_000_000)
        self.assertEqual(value['charged_tokens'], charged)
        self.assertEqual(value['reported_tokens'], 1400)

    def test_explicit_legacy_budget_still_stops_without_charging_rejected_request(self):
        budgets.create_budget(self.store, 'limited', max_calls=1, max_tokens=5000)
        budgets.reserve(self.store, 'limited', [{'role': 'user', 'content': 'hello'}])
        before = budgets.inspect_budget(self.store, 'limited')
        with self.assertRaises(CallBudgetExceeded):
            budgets.reserve(self.store, 'limited', [{'role': 'user', 'content': 'again'}])
        self.assertEqual(budgets.inspect_budget(self.store, 'limited'), before)

    def test_unlimited_spend_does_not_bypass_input_or_output_request_checks(self):
        budgets.create_budget(self.store, 'technical', max_calls=0, max_tokens=0)
        before = budgets.inspect_budget(self.store, 'technical')
        with self.assertRaises(ValueError):
            budgets.reserve(self.store, 'technical', [{'role': 'user', 'content': 'x' * MAX_INPUT_BYTES}])
        for allowance in [0, -1, 131073, True]:
            with self.subTest(allowance=allowance), self.assertRaises(ValueError):
                budgets.reserve(self.store, 'technical', [], output_tokens=allowance)
        self.assertEqual(budgets.inspect_budget(self.store, 'technical'), before)

    def test_meter_defaults_to_unlimited_with_separate_recorded_usage(self):
        meter = MeteredProvider(CountingProvider())
        self.assertEqual(meter.max_calls, 0)
        self.assertEqual(meter.max_units, 0)

    def test_unlimited_meter_passes_old_call_and_evaluation_unit_caps(self):
        provider = CountingProvider()
        meter = MeteredProvider(provider, max_calls=0, max_units=0)
        messages = [{'role': 'user', 'content': 'x' * 12000}]
        for _ in range(200):
            meter.complete(messages)
        self.assertEqual(provider.calls, 200)
        self.assertEqual(meter.calls, 200)
        self.assertGreater(meter.units, 2_000_000)
        self.assertEqual(meter.tokens, 1400)

    def test_explicit_meter_budget_remains_compatible_and_preserves_charged_usage(self):
        provider = CountingProvider()
        meter = MeteredProvider(provider, max_calls=1, max_units=5000)
        meter.complete([{'role': 'user', 'content': 'hello'}])
        before = (meter.calls, meter.units, meter.tokens)
        with self.assertRaisesRegex(RuntimeError, 'budget'):
            meter.complete([{'role': 'user', 'content': 'again'}])
        self.assertEqual((meter.calls, meter.units, meter.tokens), before)
        self.assertEqual(provider.calls, 1)

    def test_unlimited_meter_still_honors_cancellation_before_dispatch(self):
        provider = CountingProvider()
        meter = MeteredProvider(provider, max_calls=0, max_units=0, should_stop=lambda: True)
        with self.assertRaisesRegex(RuntimeError, 'cancelled'):
            meter.complete([{'role': 'user', 'content': 'cancelled'}])
        self.assertEqual(provider.calls, 0)
        self.assertEqual((meter.calls, meter.units, meter.tokens), (0, 0, 0))


if __name__ == '__main__':
    unittest.main()
