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

    def test_unlimited_default_records_work_beyond_old_cap(self):
        store=self.console.store;budgets.create_budget(store,'larger')
        self.assertEqual(budgets.inspect_budget(store,'larger')['max_tokens'],0)
        for _ in range(100):budgets.reserve(store,'larger',[{'role':'user','content':'x'*100000}],output_tokens=16384)
        spent=budgets.inspect_budget(store,'larger')
        self.assertGreater(spent['charged_tokens'],10_000_000)
        self.assertEqual(spent['calls'],100)
        with self.assertRaises(ValueError):budgets.create_budget(store,'invalid',max_tokens=-1)

    def test_existing_lower_budget_and_usage_do_not_automatically_reset(self):
        store=self.console.store;budgets.create_budget(store,'existing',max_tokens=2_000_000)
        budgets.reserve(store,'existing',[{'role':'user','content':'saved work'}])
        budgets.record_usage(store,'existing',17)
        before=budgets.inspect_budget(store,'existing')
        budgets.create_budget(store,'existing')
        self.assertEqual(budgets.inspect_budget(store,'existing'),before)

    def test_public_limit_matches_new_budget_ceiling(self):
        self.assertIsNone(self.console.health()['limits']['max_admission_units_per_chat'])
