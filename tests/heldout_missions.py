"""Fixture-backed held-out missions for runtime protocol and check coverage."""
import json
import tempfile
from pathlib import Path

from collective101.department_runtime import DepartmentOrganization
from collective101.provider import Completion

ROOT = Path(__file__).resolve().parents[1]
PACK_PATH = ROOT / "tests" / "fixtures" / "heldout_missions.json"


def load_pack():
    return json.loads(PACK_PATH.read_text(encoding="utf-8"))


class HeldoutFixtureProvider:
    """Scripts mission phases; outputs are not evidence of model competence."""

    name = "heldout-fixture"

    def __init__(self, case):
        self.case = case

    def complete(self, messages, tools=None):
        context = json.loads(messages[1]["content"])
        phase = context["phase"]
        department = context.get("department")
        plans = self.case["plans"]

        if phase in {"assess", "coordinate"}:
            plan = plans.get(department)
            if not plan:
                value = {
                    "decision": "decline",
                    "reason": "FIXTURE: no distinct contribution is assigned in this case.",
                    "depends_on": [],
                    "tasks": [],
                }
            else:
                value = {
                    "decision": "contribute",
                    "reason": "FIXTURE: provide the predeclared case contribution.",
                    "depends_on": plan["depends_on"],
                    "tasks": plan["tasks"],
                }
        elif phase == "select":
            value = {
                "departments": [
                    name for name, proposal in context["proposals"].items()
                    if proposal["decision"] == "contribute"
                ],
                "reason": "FIXTURE: select only the declared held-out case contributions.",
            }
        elif phase == "work":
            task = context["task"]
            content = self.case["artifacts"][task["key"]]
            value = {
                "status": "produced",
                "summary": "FIXTURE: produced the declared test artifact.",
                "limitations": ["Scripted held-out fixture; not model-generated evidence."],
                "capability_requests": [],
                "artifacts": [
                    {"path": path, "content": content}
                    for path in task["outputs"]
                ],
            }
        elif phase == "report":
            value = {
                "summary": "FIXTURE: reported assigned task outcomes.",
                "artifact_ids": context["artifact_ids"],
                "blockers": [],
                "improvements": [],
                "support_request": None,
            }
        elif phase == "review_assignment":
            value = {
                "reviewer_id": context["candidates"][0]["id"],
                "reason": "FIXTURE: select the first eligible independent reviewer.",
            }
        elif phase == "review":
            value = {
                "accepted": True,
                "reason": "FIXTURE: protocol verdict only; deterministic checks are reported separately.",
                "criteria": [
                    {
                        "criterion": criterion,
                        "met": True,
                        "evidence": "FIXTURE verdict; inspect deterministic artifact and execution checks.",
                    }
                    for criterion in context["mission"]["acceptance_criteria"]
                ],
            }
        elif phase == "retrospective":
            value = {
                "summary": "FIXTURE: held-out runtime case completed.",
                "improvements": [],
            }
        else:
            raise AssertionError(f"Unexpected held-out phase: {phase}")

        return Completion({"role": "assistant", "content": json.dumps(value)})


def run_case(case):
    with tempfile.TemporaryDirectory(prefix="collective101-heldout-") as directory:
        provider = HeldoutFixtureProvider(case)
        organization = DepartmentOrganization(Path(directory) / "state.db", provider)
        try:
            run = organization.run(organization.create(case["mission"], max_calls=100))
            result = run["result"] or {}
            artifacts = organization.store.query(
                "SELECT path FROM org_artifacts WHERE run_id=? ORDER BY path",
                (run["id"],),
            )
            execution = result.get("execution_results", [])
            return {
                "id": case["id"],
                "status": run["status"],
                "calls": run["calls"],
                "selected_departments": result.get("selected_departments", []),
                "dependency_edges": sorted(
                    [dependency, department]
                    for department, proposal in result.get("proposals", {}).items()
                    if department in result.get("selected_departments", [])
                    for dependency in proposal.get("depends_on", [])
                    if dependency in result.get("selected_departments", [])
                ),
                "artifact_paths": [item["path"] for item in artifacts],
                "check_errors": result.get("check_errors", []),
                "execution_checks": [
                    {
                        "passed": item["result"]["passed"],
                        "checks": len(item["result"].get("checks", [])),
                    }
                    for item in execution
                ],
                "evidence_mode": run["result"].get("evidence_mode"),
            }
        finally:
            organization.close()
