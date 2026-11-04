"""Fixture-backed held-out coverage for memory retrieval and responsibility."""
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from collective101 import learning
from collective101.agent_tools import recall
from collective101.department_runtime import DepartmentOrganization
from collective101.department_fixture import DepartmentFixtureProvider
from collective101.org_contracts import worker_result
from collective101.provider import Completion
from collective101.store import encode
from collective101.agent_harness import AgentHarness

ROOT = Path(__file__).resolve().parents[1]
PACK_PATH = ROOT / "tests" / "fixtures" / "heldout_learning.json"


def load_pack():
    return json.loads(PACK_PATH.read_text(encoding="utf-8"))


def _record_experience(store, episode):
    store.execute(
        """INSERT OR IGNORE INTO org_runs
        (id,provider,status,mission,roster,max_calls,created_at)
        VALUES(?,?,'reviewed','{}','{}',10,'fixture')""",
        (episode["run_id"], episode["provider"]),
    )
    store.execute(
        "INSERT INTO org_experience VALUES(?,?,?,?)",
        (
            episode["run_id"],
            episode["agent_id"],
            episode["provider"],
            encode({"summary": episode["summary"]}),
        ),
    )


def _run_memory_case(store, case):
    if case["type"] == "raw_experience":
        for episode in case["episodes"]:
            _record_experience(store, episode)
        results = recall(
            store,
            case["agent_id"],
            case["provider"],
            case["current_run"],
            case["query"],
        )
        return {
            "id": case["id"],
            "run_ids": [item["run_id"] for item in results],
        }

    for entry in case["entries"]:
        content = encode(entry["content"])
        for source_run in entry["source_runs"]:
            learning.consolidate(
                store,
                entry["agent_id"],
                entry["provider"],
                content,
                source_run,
            )
    cards = learning.recall_cards(
        store,
        case["agent_id"],
        case["provider"],
        case["current_run"],
        case["query"],
    )
    return {
        "id": case["id"],
        "cards": [
            {
                "summary": json.loads(card["content"])["summary"],
                "evidence_runs": card["evidence_runs"],
                "kind": card["kind"],
            }
            for card in cards
        ],
    }


def _run_responsibility_case(store, roster, case):
    agent_id = case["agent_id"]
    agent = roster[agent_id]
    original_identity = {
        "role": agent["role"],
        "reports_to": agent["reports_to"],
        "tool_allowlist": list(agent["tool_allowlist"]),
    }
    base_time = datetime(2026, 11, 3, 4, 14, tzinfo=timezone(timedelta(hours=8)))
    for index, evidence in enumerate(case["evidence"]):
        created_at = (base_time - timedelta(minutes=index)).isoformat()
        store.execute(
            "INSERT INTO org_contribution_evidence VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                f"{case['id']}-{index}",
                agent_id,
                evidence["provider"],
                evidence["objective"],
                int(evidence["accepted"]),
                int(evidence["checked"]),
                int(evidence["live"]),
                0,
                evidence["evidence_run"],
                created_at,
            ),
        )
    result = learning.responsibility(
        store,
        agent_id,
        case.get("provider_filter"),
    )
    return {
        "id": case["id"],
        "level": result["level"],
        "distinct_verified_missions": result["distinct_verified_missions"],
        "recent_failures": result["recent_failures"],
        "evidence_runs": result["evidence_runs"],
        "identity_unchanged": original_identity
        == {
            "role": agent["role"],
            "reports_to": agent["reports_to"],
            "tool_allowlist": list(agent["tool_allowlist"]),
        },
    }


def _run_contribution_case(organization, case):
    objective = "Record checked evidence from a research contribution"
    mission = {
        "objective": objective,
        "departments": ["research"],
        "inputs": {"fixture_scenario": "research"},
        "constraints": ["Use only the deterministic fixture."],
        "acceptance_criteria": ["Provide the assigned research note."],
        "allowed_capabilities": ["draft_artifact"],
        "artifact_checks": [
            {
                "type": "contains",
                "path": "research/brief.md",
                "text": case["check_text"],
            }
        ],
        "max_repair_rounds": 0,
    }
    run_id = organization.create(mission, max_calls=100)
    run = organization.run(run_id)
    rows = organization.store.query(
        "SELECT agent_id,provider,objective_hash,accepted,checked,live,repaired,evidence_run "
        "FROM org_contribution_evidence WHERE root_id=? ORDER BY agent_id",
        (run_id,),
    )
    return {
        "id": case["id"],
        "root_run_id": run_id,
        "status": run["status"],
        "agent_ids": [row["agent_id"] for row in rows],
        "evidence": [
            {
                "accepted": row["accepted"],
                "checked": row["checked"],
                "live": row["live"],
                "repaired": row["repaired"],
                "evidence_run": row["evidence_run"],
                "provider": row["provider"],
                "objective_hash": row["objective_hash"],
            }
            for row in rows
        ],
    }


class _RetryMemoryProvider:
    name = "fixture"

    def __init__(self, store, case, provider_signature):
        self.store = store
        self.case = case
        self.provider_signature = provider_signature
        self.contexts = []
        self.late_run_id = None

    def complete(self, messages, tools=None):
        context = json.loads(messages[1]["content"])
        self.contexts.append(context)
        if len(self.contexts) == 1:
            case = self.case
            self.store.execute(
                """INSERT INTO org_runs
                (id,provider,status,mission,roster,max_calls,created_at)
                VALUES(?,?,'reviewed','{}','{}',10,'fixture')""",
                (case["late_run"], self.provider_signature),
            )
            self.store.execute(
                "INSERT INTO org_experience VALUES(?,?,?,?)",
                (
                    case["late_run"],
                    case["agent_id"],
                    self.provider_signature,
                    encode({"summary": "Onboarding accessibility late experience."}),
                ),
            )
            learning.consolidate(
                self.store,
                case["agent_id"],
                self.provider_signature,
                encode(
                    {
                        "objective": "Onboarding accessibility late note",
                        "phase": "work",
                        "summary": "Onboarding accessibility late card.",
                    }
                ),
                case["late_run"],
            )
            return Completion(
                {
                    "role": "assistant",
                    "content": json.dumps({"status": "invalid"}),
                }
            )
        return Completion(
            {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "status": "produced",
                        "summary": "FIXTURE: retry completed.",
                        "limitations": [
                            "Synthetic harness test, not model-generated work."
                        ],
                        "capability_requests": [],
                        "artifacts": [
                            {"path": "memory.md", "content": "Fixture output."}
                        ],
                    }
                ),
            }
        )


def _run_memory_wiring_case(organization, case):
    provider_signature = encode(
        {"mode": case["provider_mode"], "model": None, "url": None}
    )
    organization.provider = _RetryMemoryProvider(
        organization.store,
        case,
        provider_signature,
    )
    seed_mission = {
        "objective": case["objective"],
        "departments": ["engineering"],
        "inputs": {},
        "constraints": [],
        "acceptance_criteria": ["Create a bounded fixture artifact."],
        "allowed_capabilities": ["draft_artifact"],
        "artifact_checks": [],
    }
    for run_id, agent_id, provider, summary in (
        (
            case["seed_run"],
            case["agent_id"],
            provider_signature,
            "Onboarding accessibility prior experience.",
        ),
        (
            "other-agent-run",
            case["other_agent"],
            provider_signature,
            "Onboarding accessibility belongs to another identity.",
        ),
        (
            "other-provider-run",
            case["agent_id"],
            case["other_provider"],
            "Onboarding accessibility belongs to another provider.",
        ),
    ):
        organization.store.execute(
            """INSERT INTO org_runs
            (id,provider,status,mission,roster,max_calls,created_at)
            VALUES(?,?,'reviewed','{}','{}',10,'fixture')""",
            (run_id, provider),
        )
        organization.store.execute(
            "INSERT INTO org_experience VALUES(?,?,?,?)",
            (run_id, agent_id, provider, encode({"summary": summary})),
        )
    learning.consolidate(
        organization.store,
        case["agent_id"],
        provider_signature,
        encode(
            {
                "objective": "Onboarding accessibility checklist",
                "phase": "work",
                "summary": "Prior onboarding accessibility checklist.",
            }
        ),
        case["seed_run"],
    )
    learning.consolidate(
        organization.store,
        case["agent_id"],
        case["other_provider"],
        encode(
            {
                "objective": "Onboarding accessibility other provider",
                "phase": "work",
                "summary": "Other-provider onboarding accessibility card.",
            }
        ),
        "other-provider-source",
    )
    current_run = organization.create(seed_mission, max_calls=20)
    task = {
        "key": "memory-work",
        "instructions": case["task_instructions"],
        "outputs": ["memory.md"],
        "requires": ["draft_artifact"],
    }
    context = {"mission": seed_mission, "task": task}
    validator = lambda value: worker_result(value, task)
    provider = organization.provider
    result = AgentHarness(
        organization.store,
        provider,
        organization.roster,
    ).invoke(
        current_run,
        "work:engineering:memory-work",
        case["agent_id"],
        "work",
        context,
        validator,
    )
    calls = organization.store.query(
        "SELECT input,status FROM org_calls WHERE run_id=? "
        "AND step_key=? ORDER BY attempt",
        (current_run, "work:engineering:memory-work"),
    )
    snapshots = [
        json.loads(json.loads(call["input"])[1]["content"])
        for call in calls
    ]
    return {
        "id": case["id"],
        "status": result["status"],
        "attempts": len(calls),
        "provider_signature": provider_signature,
        "late_run_id": provider.late_run_id or case["late_run"],
        "attempt_contexts": [
            {
                "prior_experience_runs": [
                    item["run_id"] for item in snapshot["prior_experience"]
                ],
                "memory_card_sources": [
                    card["evidence_runs"]
                    for card in snapshot["consolidated_memory"]
                ],
            }
            for snapshot in snapshots
        ],
    }


def run_pack():
    pack = load_pack()
    # This inherited overlap-ranking fixture now exercises BM25 fallback.
    # Equal-length eligible summaries deliberately tie query scores so the
    # existing newest-first expectation checks tie order plus access scopes.
    # Actual local semantic ranking has its own dedicated retrieval tests.
    with patch('collective101.retrieval.readiness', return_value={'available':False}), tempfile.TemporaryDirectory(prefix="collective101-heldout-learning-") as directory:
        organization = DepartmentOrganization(
            Path(directory) / "state.db",
            DepartmentFixtureProvider(),
        )
        try:
            return {
                "evidence_mode": pack["evidence_mode"],
                "retrieval_mode": "keyword_fallback_fixture",
                "warning": pack["warning"],
                "memory": [
                    _run_memory_case(organization.store, case)
                    for case in pack["memory_cases"]
                ],
                "responsibility": [
                    _run_responsibility_case(
                        organization.store,
                        organization.roster,
                        case,
                    )
                    for case in pack["responsibility_cases"]
                ],
                "contribution_recording": [
                    _run_contribution_case(organization, case)
                    for case in pack["contribution_recording_cases"]
                ],
                "memory_wiring": _run_memory_wiring_case(
                    organization,
                    pack["memory_wiring_case"],
                ),
            }
        finally:
            organization.close()
