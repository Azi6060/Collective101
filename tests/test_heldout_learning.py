import json
import unittest

from heldout_learning import load_pack, run_pack


class HeldoutLearningTests(unittest.TestCase):
    def test_memory_and_responsibility_heldout_fixtures(self):
        pack = load_pack()
        result = run_pack()
        self.assertEqual(pack["evidence_mode"], "deterministic_fixture")
        self.assertEqual(result["evidence_mode"], pack["evidence_mode"])

        wiring = result["memory_wiring"]
        wiring_case = pack["memory_wiring_case"]
        self.assertEqual(wiring["id"], wiring_case["id"])
        self.assertEqual(wiring["status"], "produced")
        self.assertEqual(wiring["attempts"], wiring_case["expected_attempts"])
        self.assertEqual(
            wiring["attempt_contexts"][0],
            wiring["attempt_contexts"][1],
            wiring,
        )
        self.assertEqual(
            wiring["attempt_contexts"][0]["prior_experience_runs"],
            wiring_case["expected_prior_experience_runs"],
        )
        self.assertEqual(
            wiring["attempt_contexts"][0]["memory_card_sources"],
            wiring_case["expected_memory_card_sources"],
        )
        self.assertNotIn(
            wiring_case["late_run"],
            wiring["attempt_contexts"][1]["prior_experience_runs"],
        )

        memory_cases = {case["id"]: case for case in pack["memory_cases"]}
        for actual in result["memory"]:
            with self.subTest(case=actual["id"]):
                expected = memory_cases[actual["id"]]
                if expected["type"] == "raw_experience":
                    self.assertEqual(actual["run_ids"], expected["expected_run_ids"])
                else:
                    self.assertEqual(actual["cards"], expected["expected_cards"])

        responsibility_cases = {
            case["id"]: case for case in pack["responsibility_cases"]
        }
        for actual in result["responsibility"]:
            with self.subTest(case=actual["id"]):
                expected = responsibility_cases[actual["id"]]["expected"]
                self.assertEqual(
                    {
                        key: actual[key]
                        for key in (
                            "level",
                            "distinct_verified_missions",
                            "recent_failures",
                            "evidence_runs",
                        )
                    },
                    expected,
                )
                self.assertTrue(actual["identity_unchanged"], actual)

        contribution_cases = {
            case["id"]: case for case in pack["contribution_recording_cases"]
        }
        for actual in result["contribution_recording"]:
            with self.subTest(case=actual["id"]):
                expected = contribution_cases[actual["id"]]
                self.assertEqual(actual["status"], expected["expected_status"])
                self.assertEqual(actual["agent_ids"], ["research-003"], actual)
                self.assertEqual(len(actual["evidence"]), 1, actual)
                evidence = actual["evidence"][0]
                self.assertEqual(
                    {
                        key: evidence[key]
                        for key in ("accepted", "checked", "live", "repaired")
                    },
                    expected["expected"],
                )
                self.assertEqual(json.loads(evidence["provider"])["mode"], "fixture")
                self.assertEqual(evidence["evidence_run"], actual["root_run_id"])
                self.assertTrue(evidence["objective_hash"])


if __name__ == "__main__":
    unittest.main()
