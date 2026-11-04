"""Run held-out memory and responsibility fixtures and print a concise report."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from heldout_learning import load_pack, run_pack


def main():
    pack = load_pack()
    result = run_pack()
    wiring_case = pack["memory_wiring_case"]
    wiring = result["memory_wiring"]
    wiring_passed = (
        wiring["id"] == wiring_case["id"]
        and wiring["status"] == "produced"
        and wiring["attempts"] == wiring_case["expected_attempts"]
        and len(wiring["attempt_contexts"]) == wiring_case["expected_attempts"]
        and wiring["attempt_contexts"][0] == wiring["attempt_contexts"][1]
        and wiring["attempt_contexts"][0]["prior_experience_runs"]
        == wiring_case["expected_prior_experience_runs"]
        and wiring["attempt_contexts"][0]["memory_card_sources"]
        == wiring_case["expected_memory_card_sources"]
        and wiring_case["late_run"]
        not in wiring["attempt_contexts"][1]["prior_experience_runs"]
    )
    print(f"{wiring['id']}: {'PASS' if wiring_passed else 'FAIL'}")
    memory_cases = {case["id"]: case for case in pack["memory_cases"]}
    responsibility_cases = {
        case["id"]: case for case in pack["responsibility_cases"]
    }
    passed = int(wiring_passed)

    for actual in result["memory"]:
        expected = memory_cases[actual["id"]]
        if expected["type"] == "raw_experience":
            matches = actual["run_ids"] == expected["expected_run_ids"]
        else:
            matches = actual["cards"] == expected["expected_cards"]
        passed += int(matches)
        print(f"{actual['id']}: {'PASS' if matches else 'FAIL'}")

    for actual in result["responsibility"]:
        expected = responsibility_cases[actual["id"]]["expected"]
        observed = {
            key: actual[key]
            for key in (
                "level",
                "distinct_verified_missions",
                "recent_failures",
                "evidence_runs",
            )
        }
        matches = observed == expected and actual["identity_unchanged"]
        passed += int(matches)
        print(
            f"{actual['id']}: {'PASS' if matches else 'FAIL'} "
            f"(level={actual['level']}, "
            f"verified={actual['distinct_verified_missions']}, "
            f"recent_failures={actual['recent_failures']})"
        )

    for actual in result["contribution_recording"]:
        case = next(
            item
            for item in pack["contribution_recording_cases"]
            if item["id"] == actual["id"]
        )
        matches = (
            actual["status"] == case["expected_status"]
            and actual["agent_ids"] == ["research-003"]
            and len(actual["evidence"]) == 1
            and all(
                actual["evidence"][0][key] == value
                for key, value in case["expected"].items()
            )
            and json.loads(actual["evidence"][0]["provider"]).get("mode")
            == "fixture"
            and actual["evidence"][0]["evidence_run"] == actual["root_run_id"]
        )
        passed += int(matches)
        print(
            f"{actual['id']}: {'PASS' if matches else 'FAIL'} "
            f"(status={actual['status']})"
        )

    total = (
        1
        + len(result["memory"])
        + len(result["responsibility"])
        + len(result["contribution_recording"])
    )
    print(
        json.dumps(
            {
                "evidence_mode": result["evidence_mode"],
                "warning": result["warning"],
                "passed": passed,
                "total": total,
            },
            indent=2,
        )
    )
    return int(passed != total)


if __name__ == "__main__":
    raise SystemExit(main())
