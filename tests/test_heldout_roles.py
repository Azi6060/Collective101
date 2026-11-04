import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collective101.agent_harness import AgentHarness
from collective101.agent_tools import eligible_tools
from collective101.department_fixture import DepartmentFixtureProvider
from collective101.department_runtime import DepartmentOrganization
from collective101.registry import build_roster
from heldout_roles import evaluate_roles


class HeldoutRoleTests(unittest.TestCase):
    def test_all_101_role_definitions_fit_hierarchy_and_permission_ceilings(self):
        result = evaluate_roles()
        self.assertEqual(result["evidence_mode"], "deterministic_fixture")
        self.assertEqual(result["agent_count"], 101)
        self.assertTrue(result["passed"], result["issues"])
        self.assertEqual(result["issues"], [])

    def test_execution_profiles_remain_department_scoped_even_if_every_identity_requests_them(self):
        expected_departments = {
            "browser_sandbox": {"engineering", "design", "assurance", "platform"},
            "python_sandbox": {"engineering", "data", "assurance", "platform"},
            "node_build_sandbox": {"engineering", "assurance", "platform"},
        }
        for agent in build_roster():
            requested = {**agent, "tool_allowlist": list(expected_departments)}
            expected = {tool for tool, departments in expected_departments.items() if agent["department"] in departments}
            with self.subTest(agent=agent["id"]):
                self.assertEqual(set(eligible_tools(requested)), expected)

    def test_evaluator_rejects_execution_permissions_added_to_the_wrong_department(self):
        cases = [
            ("design-002", "python_sandbox"),
            ("design-002", "node_build_sandbox"),
            ("data-002", "browser_sandbox"),
            ("data-002", "node_build_sandbox"),
            ("research-002", "browser_sandbox"),
            ("communications-002", "python_sandbox"),
            ("operations-002", "node_build_sandbox"),
            ("director-001", "browser_sandbox"),
        ]
        for agent_id, tool in cases:
            roster = build_roster()
            agent = next(item for item in roster if item["id"] == agent_id)
            self.assertNotIn(tool, agent["tool_allowlist"])
            agent["tool_allowlist"].append(tool)
            with self.subTest(agent=agent_id, tool=tool), patch("heldout_roles.build_roster", return_value=roster):
                result = evaluate_roles()
                self.assertFalse(result["passed"])
                self.assertIn(f"{agent_id}: allowlist exceeds department ceiling", result["issues"])
                self.assertNotIn(tool, eligible_tools(agent))

    def test_evaluator_detects_runtime_permissions_exceeding_the_independent_expectation(self):
        def overbroad_tools(agent):
            actual = eligible_tools(agent)
            return actual + ["browser_sandbox"] if agent["id"] == "communications-002" else actual

        with patch("heldout_roles.eligible_tools", side_effect=overbroad_tools):
            result = evaluate_roles()
        self.assertFalse(result["passed"])
        self.assertIn("communications-002: effective tools do not match the permission intersection", result["issues"])

    def test_all_101_reject_a_phase_outside_their_role(self):
        with tempfile.TemporaryDirectory(prefix="collective101-heldout-roles-") as directory:
            organization = DepartmentOrganization(
                Path(directory) / "state.db",
                DepartmentFixtureProvider(),
            )
            try:
                mission = {
                    "objective": "Validate role phase boundaries.",
                    "departments": ["research"],
                    "inputs": {},
                    "constraints": [],
                    "acceptance_criteria": ["Respect role phase permissions."],
                    "allowed_capabilities": ["draft_artifact"],
                    "artifact_checks": [],
                }
                run_id = organization.create(mission)
                harness = AgentHarness(
                    organization.store,
                    organization.provider,
                    organization.roster,
                )
                for agent in organization.roster.values():
                    if agent["role"] == "mission_director":
                        phase = "assess"
                    elif agent["role"] == "department_lead":
                        phase = "work"
                    else:
                        phase = "retrospective"
                    with self.subTest(agent=agent["id"], phase=phase):
                        with self.assertRaises(PermissionError):
                            harness.invoke(
                                run_id,
                                f"unauthorized:{agent['id']}",
                                agent["id"],
                                phase,
                                {"mission": mission},
                                lambda value: value,
                            )
                self.assertEqual(
                    organization.store.query(
                        "SELECT agent_id FROM org_calls WHERE run_id=?",
                        (run_id,),
                    ),
                    [],
                )
            finally:
                organization.close()


if __name__ == "__main__":
    unittest.main()
