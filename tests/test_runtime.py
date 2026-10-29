import copy
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from collective101.planning import fixture_plan, validate_plan
from collective101.provider import Completion, FixtureProvider, MetaProvider, parse_object
from collective101.registry import build_roster
from collective101.report import export_report
from collective101.runtime import Organization
from collective101.store import CallBudgetExceeded
from collective101.tools import ToolDenied, money_cents, validate_constraints, validate_rows

ROWS = [{"event": "A", "registered": 64, "attended": 48},
        {"event": "B", "registered": 88, "attended": 66},
        {"event": "C", "registered": 72, "attended": 54},
        {"event": "D", "registered": 96, "attended": 72}]
CONSTRAINTS = {"budget": 500, "capacity": 100, "fixed_cost": 100, "per_person": 5}


class OrganizationTest(unittest.TestCase):
    def setUp(self):
        self.temp_root = (Path.cwd() / "work" / "tests").resolve()
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=self.temp_root)
        self.org = Organization(Path(self.temp.name) / "state.db", FixtureProvider())

    def tearDown(self):
        self.org.close()
        if not Path(self.temp.name).resolve().is_relative_to(self.temp_root):
            raise RuntimeError("Test cleanup target escaped its workspace")
        self.temp.cleanup()

    def create(self, max_calls=64):
        return self.org.create("Analyze records and plan an event", ROWS, CONSTRAINTS, max_calls)

    def events(self, mission, kind):
        return [json.loads(row["data"]) for row in self.org.store.query(
            "SELECT data FROM events WHERE mission_id=? AND kind=?", (mission, kind))]

    def test_end_to_end_artifacts_and_revoked_grants(self):
        mission = self.create()
        self.assertEqual(self.org.run(mission)["status"], "completed")
        tasks = self.org.store.tasks(mission)
        self.assertTrue(all(task["agent_id"] != task["reviewer_id"] for task in tasks))
        self.assertEqual(len(tasks), 5)
        plan = next(task for task in tasks if task["key"] == "budget")["result"]["evidence"][0]["data"]
        self.assertEqual(plan["planned_attendees"], 60)
        self.assertEqual(plan["total_cost_cents"], 40000)
        self.assertEqual(self.org.store.query("SELECT * FROM grants WHERE active=1"), [])
        self.assertEqual(self.org.store.mission(mission)["calls"], 21)

    def test_real_scheduler_recovers_from_one_tool_outage(self):
        self.org.gateway.fail_once = True
        mission = self.create()
        self.assertEqual(self.org.run(mission)["status"], "completed")
        assignments = [event for event in self.events(mission, "task.assigned") if event["task"] == "budget"]
        self.assertEqual(len(assignments), 2)
        self.assertNotEqual(assignments[0]["agent"], assignments[1]["agent"])
        self.assertEqual(len(self.events(mission, "fault.injected")), 1)

    def test_bad_cost_is_rejected_before_acceptance(self):
        self.org.reject_once = True
        mission = self.create()
        self.assertEqual(self.org.run(mission)["status"], "completed")
        rejected = self.events(mission, "task.rejected")
        self.assertEqual(len(rejected), 1)
        self.assertTrue(rejected[0]["errors"])
        history = self.org.store.query("SELECT verdict FROM result_history WHERE mission_id=? AND task_id=? ORDER BY id", (mission, mission + ":budget"))
        self.assertEqual([json.loads(row["verdict"])["accepted"] for row in history], [False, True])

    def test_revise_preserves_independent_data_work(self):
        mission = self.create()
        self.org.run(mission)
        old = {task["key"]: task for task in self.org.store.tasks(mission)}
        constraints = {**CONSTRAINTS, "budget": 260, "capacity": 35}
        affected = self.org.revise(mission, constraints)
        self.assertEqual(set(affected), {"budget", "brief", "delivery"})
        self.assertEqual(self.org.run(mission)["status"], "completed")
        new = {task["key"]: task for task in self.org.store.tasks(mission)}
        for key in ("profile", "attendance"):
            self.assertEqual(new[key]["result"], old[key]["result"])
        plan = new["budget"]["result"]["evidence"][0]["data"]
        self.assertEqual(plan["planned_attendees"], 32)
        self.assertEqual(plan["total_cost_cents"], 26000)
        self.assertEqual(self.org.store.mission(mission)["version"], 2)
        self.assertEqual(len(self.org.store.query("SELECT * FROM artifacts WHERE mission_id=?", (mission,))), 8)

    def test_model_call_budget_is_atomic(self):
        mission = self.create(max_calls=5)
        def reserve(_):
            try:
                self.org.store.reserve_call(mission)
                return True
            except CallBudgetExceeded:
                return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(reserve, range(20)))
        self.assertEqual(sum(results), 4)  # Planning has already consumed one call.
        self.assertEqual(self.org.store.mission(mission)["calls"], 5)

    def test_exhausted_budget_blocks_without_false_completion(self):
        mission = self.create(max_calls=2)
        self.assertEqual(self.org.run(mission)["status"], "blocked")
        self.assertLessEqual(self.org.store.mission(mission)["calls"], 2)
        self.assertFalse(self.events(mission, "mission.completed"))

    def test_cross_department_and_cross_task_grants_denied(self):
        mission_id = self.create()
        mission = self.org.store.mission(mission_id)
        task = self.org.store.tasks(mission_id)[0]
        research = next(agent for agent in self.org.roster if agent["id"] == "research-002")
        self.org.store.execute("UPDATE tasks SET status='running',agent_id=? WHERE id=?", (research["id"], task["id"]))
        with self.assertRaises(ToolDenied):
            self.org.gateway.grant(mission, task, research, "event_planning")
        self.org.gateway.grant(mission, task, research, "dataset_inspection")
        other = self.org.store.tasks(mission_id)[1]
        with self.assertRaises(ToolDenied):
            self.org.gateway.invoke(mission, other, research, "profile_dataset", {}, {})
        self.org.gateway.revoke(task["id"], research["id"])
        with self.assertRaises(ToolDenied):
            self.org.gateway.invoke(mission, task, research, "profile_dataset", {}, {})

    def test_fixture_work_never_proposes_promotions(self):
        for _ in range(3):
            mission = self.create()
            self.org.run(mission)
        self.assertEqual(self.org.store.query("SELECT * FROM events WHERE kind='promotion.proposed'"), [])

    def test_persisted_run_reopens_without_reexecution(self):
        mission = self.create()
        self.org.run(mission)
        calls = self.org.store.mission(mission)["calls"]
        self.org.close()
        self.org = Organization(Path(self.temp.name) / "state.db", FixtureProvider())
        self.assertEqual(self.org.run(mission)["calls"], calls)

    def test_interrupted_task_is_recovered_with_revoked_access(self):
        mission = self.create()
        task = self.org.store.tasks(mission)[0]
        self.org.store.execute("UPDATE tasks SET status='running',agent_id='research-002',attempts=1 WHERE id=?", (task["id"],))
        self.org.store.execute("INSERT INTO grants VALUES(?,?,?,?,1)", (mission, task["id"], "research-002", "dataset_inspection"))
        self.org.close()
        self.org = Organization(Path(self.temp.name) / "state.db", FixtureProvider())
        self.assertEqual(self.org.run(mission)["status"], "completed")
        self.assertEqual(len(self.events(mission, "task.interruption_recovered")), 1)
        self.assertFalse(self.org.store.query("SELECT * FROM grants WHERE active=1"))

    def test_reviewer_rejection_cannot_be_overridden_by_passing_math(self):
        class RejectingReviewer(FixtureProvider):
            def complete(self, messages, tools=None):
                if json.loads(messages[1]["content"])["phase"] == "review":
                    return Completion({"role": "assistant", "content": json.dumps({"accepted": False, "reason": "Required explanation is missing"})})
                return super().complete(messages, tools)
        self.org.provider = RejectingReviewer()
        mission = self.create()
        self.assertEqual(self.org.run(mission)["status"], "blocked")
        self.assertFalse(any(task["status"] == "accepted" for task in self.org.store.tasks(mission)))
        self.assertFalse(self.org.store.query("SELECT * FROM grants WHERE active=1"))

    def test_report_escapes_user_text(self):
        mission = self.org.create("<script>alert('x')</script>", ROWS, CONSTRAINTS)
        self.org.run(mission)
        report = export_report(self.org, mission, Path(self.temp.name) / "export")
        source = report.read_text(encoding="utf-8")
        self.assertNotIn("<script>alert", source)
        self.assertIn("&lt;script&gt;", source)
        self.assertIn("DETERMINISTIC FIXTURE", source)

    def test_infeasible_mission_stops_with_reason(self):
        mission = self.org.create("Plan an event", ROWS, {**CONSTRAINTS, "budget": 10})
        self.assertEqual(self.org.run(mission)["status"], "blocked")
        task = next(task for task in self.org.store.tasks(mission) if task["key"] == "budget")
        self.assertIn("infeasible", task["error"])


class ContractTest(unittest.TestCase):
    def test_101_unique_agents_and_department_counts(self):
        roster = build_roster()
        self.assertEqual(len(roster), 101)
        self.assertEqual(len({agent["id"] for agent in roster}), 101)
        self.assertEqual(sum(agent["department"] == "platform" for agent in roster), 10)
        self.assertEqual(sum(agent["department"] == "assurance" for agent in roster), 16)

    def test_cycle_rejected(self):
        plan = fixture_plan()
        plan["tasks"][0]["depends_on"] = ["delivery"]
        with self.assertRaisesRegex(ValueError, "Cyclic"):
            validate_plan(plan)

    def test_unknown_dependency_rejected(self):
        plan = fixture_plan()
        plan["tasks"][0]["depends_on"] = ["unknown"]
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_planner_cannot_weaken_verification_or_grant_tools(self):
        for field, value in (("check", "nonempty"), ("tool", "run_shell"), ("department", "engineering")):
            plan = fixture_plan()
            plan["tasks"][0][field] = value
            with self.assertRaises(ValueError):
                validate_plan(plan)

    def test_invalid_rows_rejected(self):
        for invalid in ([], [{"event": "bad", "registered": 1, "attended": 2}],
                        [{"event": "bad", "registered": "3.5", "attended": 1}]):
            with self.assertRaises(ValueError):
                validate_rows(invalid)

    def test_nonfinite_constraints_rejected(self):
        for invalid in (float("nan"), float("inf"), -1):
            with self.assertRaises(ValueError):
                validate_constraints({**CONSTRAINTS, "budget": invalid})
        self.assertEqual(money_cents("0.29"), 29)

    def test_meta_mode_requires_key_and_secure_endpoint(self):
        with self.assertRaisesRegex(ValueError, "MODEL_API_KEY"):
            MetaProvider(api_key="")
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            MetaProvider(api_key="dummy", base_url="http://public.example/v1")
        with self.assertRaises(ValueError):
            MetaProvider(api_key="dummy", base_url="https://example.com/v1?key=secret")
        self.assertEqual(MetaProvider(api_key="dummy", base_url="http://127.0.0.1:4010/meta/v1").name, "simulation")

    def test_json_output_must_be_an_object(self):
        with self.assertRaises(ValueError):
            parse_object("[1,2,3]")
        self.assertEqual(parse_object('```json\n{"ok":true}\n```'), {"ok": True})


if __name__ == "__main__":
    unittest.main()
