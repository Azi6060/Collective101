"""Run the held-out protocol missions and print a concise fixture report."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from heldout_missions import load_pack, run_case


def case_passed(result, case):
    expected = case.get("expected_status", "reviewed")
    expected_checks = len(case["mission"].get("execution_checks", []))
    checks = sum(item["checks"] for item in result["execution_checks"])
    execution_passed = (
        checks == expected_checks
        and all(item["passed"] for item in result["execution_checks"])
    )
    if expected == "blocked":
        execution_passed = (
            checks == expected_checks
            and any(not item["passed"] for item in result["execution_checks"])
            and any(
                case.get("expected_error", "") in error
                for error in result["check_errors"]
            )
        )
    return (
        result["status"] == expected
        and set(result["selected_departments"]) == set(case["expected_departments"])
        and set(result["artifact_paths"]) == set(case["expected_paths"])
        and result["dependency_edges"]
        == sorted(case.get("expected_dependency_edges", []))
        and (
            execution_passed
            if expected_checks
            else (
                not result["check_errors"]
                if expected == "reviewed"
                else any(
                    case.get("expected_error", "") in error
                    for error in result["check_errors"]
                )
            )
        )
    )


def main():
    pack = load_pack()
    results = [run_case(case) for case in pack["cases"]]
    cases = {case["id"]: case for case in pack["cases"]}
    for result in results:
        checks = sum(item["checks"] for item in result["execution_checks"])
        case = cases[result["id"]]
        expected = case.get("expected_status", "reviewed")
        passed = case_passed(result, case)
        print(
            f"{result['id']}: {'PASS' if passed else 'FAIL'} "
            f"(status={result['status']}, expected={expected}); "
            f"departments={len(result['selected_departments'])}; "
            f"artifacts={len(result['artifact_paths'])}; "
            f"runtime_checks={checks}; calls={result['calls']}"
        )
    passed_cases = sum(
        case_passed(result, cases[result["id"]]) for result in results
    )
    print(
        json.dumps(
            {
                "evidence_mode": pack["evidence_mode"],
                "warning": pack["warning"],
                "passed": passed_cases,
                "total": len(results),
                "results": results,
            },
            indent=2,
        )
    )
    return int(passed_cases != len(results))


if __name__ == "__main__":
    raise SystemExit(main())
