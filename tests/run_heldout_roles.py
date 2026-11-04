"""Audit all 101 role definitions against structural and permission contracts."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from heldout_roles import evaluate_roles


def main():
    result = evaluate_roles()
    print(
        f"all-101-role-definitions: "
        f"{'PASS' if result['passed'] else 'FAIL'} "
        f"(agents={result['agent_count']}, issues={len(result['issues'])})"
    )
    print(json.dumps(result, indent=2))
    return int(not result["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
