"""Fixture-backed structural and permission evaluation for all 101 roles."""
from collections import Counter

from collective101.agent_tools import eligible_tools
from collective101.registry import DEPARTMENTS, ROLES, build_roster

COMMON_TOOLS = {"knowledge_read", "knowledge_search", "memory_search"}
EXECUTION_DEPARTMENTS = {"engineering", "data", "assurance", "platform"}
BROWSER_DEPARTMENTS = {"engineering", "design", "assurance", "platform"}
NODE_BUILD_DEPARTMENTS = {"engineering", "assurance", "platform"}
SEARCH_DEPARTMENTS = {"research", "strategy", "assurance", "platform"}


def evaluate_roles():
    roster = build_roster()
    departments = {department.id: department for department in DEPARTMENTS}
    issues = []
    counts = Counter()
    for agent in roster:
        agent_id = agent["id"]
        counts[agent["department"]] += 1
        if agent_id == "director-001":
            expected_department = "organization"
            expected_role = "mission_director"
            expected_manager = None
            ceiling = COMMON_TOOLS
        else:
            department = departments.get(agent["department"])
            if department is None:
                issues.append(f"{agent_id}: unknown department")
                continue
            is_head = agent_id == f"{agent['department']}-001"
            expected_department = department.id
            expected_role = "department_lead" if is_head else None
            expected_manager = "director-001" if is_head else f"{department.id}-001"
            ceiling = set(COMMON_TOOLS)
            # Independent expectations for the current bounded execution profiles;
            # do not derive the oracle from eligible_tools(), which it checks.
            if department.id in EXECUTION_DEPARTMENTS:
                ceiling.update({"javascript_sandbox", "sql_sandbox", "python_sandbox"})
            if department.id in BROWSER_DEPARTMENTS:
                ceiling.add("browser_sandbox")
            if department.id in NODE_BUILD_DEPARTMENTS:
                ceiling.add("node_build_sandbox")
            if department.id in SEARCH_DEPARTMENTS:
                ceiling.add("web_search")
            if not is_head and agent["role"] not in ROLES:
                issues.append(f"{agent_id}: unknown employee role {agent['role']}")
            if not is_head:
                expected_role = agent["role"]

        if agent["department"] != expected_department:
            issues.append(f"{agent_id}: unexpected department")
        if agent["role"] != expected_role:
            issues.append(f"{agent_id}: unexpected role")
        if agent.get("reports_to") != expected_manager:
            issues.append(f"{agent_id}: unexpected reporting line")
        if not agent.get("system_prompt", "").strip():
            issues.append(f"{agent_id}: missing role prompt")
        if not agent.get("responsibilities"):
            issues.append(f"{agent_id}: missing responsibilities")
        if not agent.get("skills"):
            issues.append(f"{agent_id}: missing skills")
        if len(set(agent.get("tool_allowlist", []))) != len(agent.get("tool_allowlist", [])):
            issues.append(f"{agent_id}: duplicate tool permissions")
        if set(agent.get("tool_allowlist", [])) - ceiling:
            issues.append(f"{agent_id}: allowlist exceeds department ceiling")
        if set(eligible_tools(agent)) != set(agent.get("tool_allowlist", [])) & ceiling:
            issues.append(f"{agent_id}: effective tools do not match the permission intersection")
        if not set(agent.get("capabilities", [])).issubset(
            set(departments[agent["department"]].capabilities)
            if agent["department"] in departments
            else set()
        ):
            issues.append(f"{agent_id}: capabilities exceed department charter")

    expected_counts = {department.id: department.count for department in DEPARTMENTS}
    expected_counts["organization"] = 1
    for department, expected in expected_counts.items():
        if counts[department] != expected:
            issues.append(
                f"{department}: expected {expected} identities, found {counts[department]}"
            )
    if len({agent["system_prompt"] for agent in roster}) != len(roster):
        issues.append("Role prompts are not unique across the roster")

    return {
        "evidence_mode": "deterministic_fixture",
        "agent_count": len(roster),
        "department_counts": dict(sorted(counts.items())),
        "issues": issues,
        "passed": not issues and len(roster) == 101,
    }
