import tempfile
import unittest
from pathlib import Path

from collective101.agent_harness import AgentHarness
from collective101.department_fixture import DepartmentFixtureProvider
from collective101.department_runtime import DepartmentOrganization
from heldout_roles import evaluate_roles


class HeldoutRoleTests(unittest.TestCase):
    def test_all_101_role_definitions_fit_hierarchy_and_permission_ceilings(self):
        result = evaluate_roles()
        self.assertEqual(result["evidence_mode"], "deterministic_fixture")
        self.assertEqual(result["agent_count"], 101)
        self.assertTrue(result["passed"], result["issues"])
        self.assertEqual(result["issues"], [])

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
