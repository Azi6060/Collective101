"""Raised chat allowance preserves finite bounds and existing spent reservations."""
import tempfile
import unittest
from pathlib import Path

from collective101 import budgets
from collective101.console import MissionConsole
from collective101.store import CallBudgetExceeded


class AdmissionCapTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'work'/'admission-cap-tests'
        root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root)
        self.console=MissionConsole(Path(self.temp.name)/'state.db')

    def tearDown(self):
        self.console.close();self.temp.cleanup()

    def test_larger_default_supports_work_beyond_old_cap_and_still_stops_at_limit(self):
        store=self.console.store;budgets.create_budget(store,'larger')
        self.assertEqual(budgets.inspect_budget(store,'larger')['max_tokens'],10_000_000)
        messages=[{'role':'user','content':'x'*100_000}]
        for _ in range(24):budgets.reserve(store,'larger',messages,output_tokens=16384)
        spent=budgets.inspect_budget(store,'larger')
        self.assertGreater(spent['charged_tokens'],2_000_000)
        self.assertEqual(spent['calls'],24)
        while True:
            before=budgets.inspect_budget(store,'larger')
            try:budgets.reserve(store,'larger',messages,output_tokens=16384)
            except CallBudgetExceeded:break
        self.assertEqual(budgets.inspect_budget(store,'larger'),before)
        self.assertLessEqual(before['charged_tokens'],10_000_000)
        with self.assertRaises(ValueError):budgets.create_budget(store,'excessive',max_tokens=10_000_001)

    def test_existing_lower_budget_and_usage_do_not_automatically_reset(self):
        store=self.console.store;budgets.create_budget(store,'existing',max_tokens=2_000_000)
        budgets.reserve(store,'existing',[{'role':'user','content':'saved work'}])
        budgets.record_usage(store,'existing',17)
        before=budgets.inspect_budget(store,'existing')
        budgets.create_budget(store,'existing')
        self.assertEqual(budgets.inspect_budget(store,'existing'),before)

    def test_public_limit_matches_new_budget_ceiling(self):
        self.assertEqual(self.console.health()['limits']['max_admission_units_per_chat'],10_000_000)
