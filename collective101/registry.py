"""Load the editable, validated 101-agent organization definitions."""
import json
from pathlib import Path
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Department:
    id: str
    name: str
    count: int
    charter: str
    specialties: tuple[str, ...]
    capabilities: tuple[str, ...] = ()


DEPARTMENTS = (
    Department("distribution", "Distribution & Coordination", 8,
               "Decompose missions, route work, manage dependencies and recovery.",
               ("intake", "planning", "routing", "dependencies", "budgets", "recovery")),
    Department("research", "Research & Intelligence", 10,
               "Investigate supplied information; separate evidence from assumptions.",
               ("source_analysis", "domain_research", "evidence_review"), ("dataset_inspection",)),
    Department("strategy", "Strategy & Planning", 8,
               "Compare approaches and assemble coherent, evidence-linked deliverables.",
               ("objectives", "alternatives", "feasibility", "synthesis"), ("report_assembly",)),
    Department("engineering", "Engineering & Automation", 16,
               "Implement and integrate executable systems.",
               ("implementation", "integration", "builds", "automation")),
    Department("data", "Data & Analytics", 10,
               "Compute reproducible analyses and disclose statistical limitations.",
               ("profiling", "attendance_analysis", "validation"), ("attendance_analysis", "dataset_inspection")),
    Department("design", "Design & Media", 8,
               "Create useful and accessible visual communication.",
               ("experience", "visual_design", "accessibility")),
    Department("operations", "Operations & Delivery", 8,
               "Construct feasible operating plans within explicit constraints.",
               ("resource_planning", "scheduling", "delivery"), ("event_planning",)),
    Department("communications", "Communications & Documentation", 6,
               "Explain supported results and prepare clear deliverables.",
               ("writing", "editing", "documentation"), ("brief_generation",)),
    Department("platform", "Tools & Infrastructure", 10,
               "Broker registered capabilities; enforce task-scoped grants in code.",
               ("catalog", "access_policy", "tool_health", "integration")),
    Department("assurance", "Verification & Evaluation", 16,
               "Independently check acceptance conditions and retain evaluation evidence.",
               ("acceptance", "adversarial_review", "evaluation", "reproducibility")),
)
DEPARTMENT_MAP = {department.id: department for department in DEPARTMENTS}
ROLES = ("coordinator", "specialist", "specialist", "specialist", "reviewer", "knowledge_curator")


def build_roster(root=None) -> list[dict]:
    root = Path(root) if root is not None else Path(__file__).parent / "departments"
    agents = []
    for path in sorted(root.glob("*/*.json")):
        agent = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(agent, dict):
            raise ValueError(f"Invalid agent definition: {path.name}")
        for field in ("id", "name", "department", "role", "specialty", "rank", "memory_namespace", "charter", "system_prompt"):
            if not isinstance(agent.get(field), str) or not agent[field].strip():
                raise ValueError(f"Missing {field} in {path.name}")
        if path.stem != agent["id"] or path.parent.name != agent["department"]:
            raise ValueError("Agent identity must match its department folder and filename")
        for field in ("capabilities", "skills", "responsibilities"):
            if not isinstance(agent.get(field), list) or any(not isinstance(x, str) or not x for x in agent[field]):
                raise ValueError(f"Invalid {field} in {path.name}")
        if not agent["responsibilities"]:
            raise ValueError("Each agent needs explicit responsibilities")
        declared=agent.get('tool_allowlist',[])
        if not isinstance(declared,list) or len(set(declared))!=len(declared) or any(t not in {'knowledge_read','knowledge_search','memory_search','web_search','javascript_sandbox','sql_sandbox','browser_sandbox','python_sandbox','node_build_sandbox'} for t in declared):
            raise ValueError('Invalid agent tool allowlist')
        agents.append(agent)
    expected = {"director-001"} | {f"{d.id}-{i:03}" for d in DEPARTMENTS for i in range(1, d.count + 1)}
    if len(agents) != 101 or {a["id"] for a in agents} != expected:
        raise ValueError("Organization must have exactly the 101 expected unique identities")
    for agent in agents:
        if agent["id"] == "director-001":
            if agent["role"] != "mission_director" or agent["department"] != "organization" or agent.get("reports_to") is not None:
                raise ValueError("Invalid mission director hierarchy")
            continue
        department = DEPARTMENT_MAP[agent["department"]]
        is_head = agent["id"] == department.id + "-001"
        parent = "director-001" if is_head else department.id + "-001"
        if agent.get("reports_to") != parent or (agent["role"] == "department_lead") != is_head:
            raise ValueError("Exactly one head per department; employees report to their own head")
        if not is_head and agent["role"] not in ROLES:
            raise ValueError("Unknown employee role")
        if not set(agent["capabilities"]).issubset(department.capabilities):
            raise ValueError("Agent configuration cannot expand department executable permissions")
    return sorted(agents, key=lambda a: (a["id"] != "director-001", a["id"]))


def department_records() -> list[dict]:
    return [asdict(department) for department in DEPARTMENTS]
