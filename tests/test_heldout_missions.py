import unittest

from heldout_missions import load_pack, run_case


class HeldoutMissionTests(unittest.TestCase):
    def test_predeclared_missions_against_deterministic_runtime_fixture(self):
        pack = load_pack()
        self.assertEqual(pack["evidence_mode"], "deterministic_fixture")
        self.assertEqual(len(pack["cases"]), 7)

        for case in pack["cases"]:
            with self.subTest(mission=case["id"]):
                result = run_case(case)
                self.assertEqual(result["evidence_mode"], "heldout-fixture")
                expected_status = case.get("expected_status", "reviewed")
                self.assertEqual(result["status"], expected_status, result)
                self.assertEqual(
                    set(result["selected_departments"]),
                    set(case["expected_departments"]),
                    result,
                )
                self.assertEqual(
                    set(result["artifact_paths"]),
                    set(case["expected_paths"]),
                    result,
                )
                self.assertEqual(
                    result["dependency_edges"],
                    sorted(case.get("expected_dependency_edges", [])),
                    result,
                )
                if expected_status == "reviewed":
                    self.assertFalse(result["check_errors"], result)
                else:
                    self.assertTrue(
                        any(case.get("expected_error", "") in error for error in result["check_errors"]),
                        result,
                    )
                self.assertTrue(result["calls"] > 0, result)
                if case["id"] == "javascript-calculator":
                    self.assertTrue(result["execution_checks"][0]["passed"], result)
                    self.assertEqual(result["execution_checks"][0]["checks"], 3)
                if case["id"] == "sales-sql-summary":
                    self.assertTrue(result["execution_checks"][0]["passed"], result)
                    self.assertEqual(result["execution_checks"][0]["checks"], 1)
                if case["id"] == "incorrect-code-is-blocked":
                    self.assertTrue(result["execution_checks"], result)
                    self.assertTrue(any(not check["passed"] for check in result["execution_checks"]), result)
                    self.assertEqual(
                        sum(check["checks"] for check in result["execution_checks"]),
                        len(case["mission"]["execution_checks"]),
                        result,
                    )
                elif result["execution_checks"]:
                    self.assertTrue(all(check["passed"] for check in result["execution_checks"]), result)


if __name__ == "__main__":
    unittest.main()
