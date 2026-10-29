"""A generated roster, not 101 independently maintained programs."""
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


def build_roster() -> list[dict]:
    agents = [{"id": "director-001", "department": "organization", "role": "mission_director",
               "specialty": "mission_ownership", "rank": "lead", "capabilities": [],
               "memory_namespace": "agents/director-001", "charter": "Own mission outcomes and resolve major conflicts."}]
    for department in DEPARTMENTS:
        for index in range(department.count):
            agent_id = f"{department.id}-{index + 1:03}"
            agents.append({"id": agent_id, "department": department.id,
                           "role": "department_lead" if index == 0 else ROLES[(index - 1) % len(ROLES)],
                           "specialty": department.specialties[index % len(department.specialties)],
                           "rank": "lead" if index == 0 else "specialist",
                           "capabilities": list(department.capabilities),
                           "memory_namespace": f"agents/{agent_id}", "charter": department.charter})
    if len(agents) != 101 or len({agent["id"] for agent in agents}) != 101:
        raise RuntimeError("Organization must have exactly 101 unique identities")
    return agents


def department_records() -> list[dict]:
    return [asdict(department) for department in DEPARTMENTS]
