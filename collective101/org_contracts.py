"""Contracts for generic departmental missions; model decisions are untrusted input."""
import re
from pathlib import PurePosixPath
from .registry import DEPARTMENT_MAP
from .connectors import is_connector_tool


def text(value, field, limit=12000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{field} must be nonempty text of at most {limit} characters")
    return value


def strings(value, field, maximum=32):
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(f"Invalid {field} list")
    for item in value:
        text(item, field, 4000)
    if len(set(value)) != len(value):
        raise ValueError(f"Duplicate {field}")
    return value


def safe_path(value):
    text(value, "artifact path", 180)
    parts = PurePosixPath(value).parts
    safe_dotfiles={'.env.example','.gitignore','.dockerignore'}
    if (not parts or PurePosixPath(value).is_absolute() or "\\" in value or ":" in value
            or any(p in (".", "..") or (p.startswith(".") and p not in safe_dotfiles) or p.endswith((".", " ")) for p in parts)
            or value != "/".join(parts)):
        raise ValueError("Artifact path must be a normalized relative path")
    for part in parts:
        if part not in safe_dotfiles and not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_. -]*", part):
            raise ValueError("Unsafe artifact filename")
        if part.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]}:
            raise ValueError("Reserved artifact filename")
    return value


def department_path(value,department):
    """Accept either a relative file or the same department's qualified path."""
    path=safe_path(value)
    prefix=department+'/'
    return safe_path(path[len(prefix):]) if path.startswith(prefix) else path


def mission_contract(value):
    if not isinstance(value, dict):
        raise ValueError("Mission must be an object")
    text(value.get("objective"), "objective")
    strings(value.get("constraints", []), "constraints")
    criteria = strings(value.get("acceptance_criteria"), "acceptance_criteria")
    if not criteria:
        raise ValueError("At least one acceptance criterion is required")
    if not isinstance(value.get("inputs", {}), dict):
        raise ValueError("inputs must be an object")
    import json
    if len(json.dumps(value.get("inputs", {}))) > 600000:
        raise ValueError("Mission inputs exceed the 600,000-character limit")
    allowed = strings(value.get("allowed_capabilities", ["draft_artifact"]), "allowed_capabilities")
    if any(c not in {"draft_artifact", "javascript_sandbox", "sql_sandbox", "browser_sandbox", "python_sandbox", "node_build_sandbox", "knowledge_read", "knowledge_search", "memory_search", "web_search"} and not is_connector_tool(c) for c in allowed):
        raise ValueError("Unknown executable capability")
    checks = value.get("artifact_checks", [])
    if not isinstance(checks, list) or len(checks) > 32:
        raise ValueError("Invalid artifact_checks")
    for check in checks:
        if not isinstance(check, dict) or check.get("type") not in ("exists", "contains", "html"):
            raise ValueError("Supported artifact checks are exists, contains and html")
        safe_path(check.get("path"))
        if check["type"] == "contains":
            text(check.get("text"), "check text", 4000)
        if check['type']=='html' and not check['path'].endswith('.html'):raise ValueError('HTML checks require an HTML document')
    data_checks=value.get('data_checks',[])
    if not isinstance(data_checks,list) or len(data_checks)>4 or len(json.dumps(data_checks,allow_nan=False))>80000:
        raise ValueError('At most four bounded SQL checks are allowed')
    if data_checks and 'sql_sandbox' not in allowed:raise ValueError('Data checks require sql_sandbox permission')
    for check in data_checks:
        if not isinstance(check,dict) or not isinstance(check.get('tables'),dict) or not isinstance(check.get('expected_rows'),list):raise ValueError('SQL checks require tables and expected_rows')
        safe_path(check.get('path'))
        if not check['path'].endswith('.sql'):raise ValueError('SQL checks require a SQL artifact')
    execution = value.get("execution_checks", [])
    if not isinstance(execution, list) or len(execution) > 12:
        raise ValueError("At most 12 execution checks are allowed")
    if execution and "javascript_sandbox" not in allowed:
        raise ValueError("Execution checks require explicit javascript_sandbox permission")
    for check in execution:
        if not isinstance(check, dict):
            raise ValueError("Execution check must be an object")
        safe_path(check.get("path"))
        if not check["path"].endswith(".js"):
            raise ValueError("Execution checks require a JavaScript artifact")
        text(check.get("expression"), "execution expression", 2000)
        expected = check.get("expected")
        if expected is not None and type(expected) not in (str, bool, int, float):
            raise ValueError("Expected execution result must be primitive")
        if isinstance(expected, str) and len(expected) > 4000:
            raise ValueError("Expected result is too long")
        import math
        if isinstance(expected, (int, float)) and not math.isfinite(expected):
            raise ValueError("Expected number must be finite")
    departments = strings(value.get("departments", list(DEPARTMENT_MAP)), "departments", 10)
    browser_checks=value.get('browser_checks',[]);runtime_checks=value.get('runtime_checks',[])
    if not isinstance(browser_checks,list) or len(browser_checks)>3:raise ValueError('At most three saved-page browser check groups are allowed')
    if browser_checks and 'browser_sandbox' not in allowed:raise ValueError('Browser checks require explicit browser_sandbox permission')
    from .execution_adapters import validate_browser_checks
    for check in browser_checks:
        if not isinstance(check,dict):raise ValueError('Browser check must be an object')
        safe_path(check.get('path'))
        if not check['path'].endswith('.html'):raise ValueError('Browser acceptance requires an HTML artifact')
        validate_browser_checks(check.get('checks'))
    if not isinstance(runtime_checks,list) or len(runtime_checks)>3:raise ValueError('At most three isolated runtime check groups are allowed')
    for check in runtime_checks:
        if not isinstance(check,dict) or check.get('profile') not in {'python','node_build'}:raise ValueError('Runtime profile must be python or node_build')
        profile=check['profile'];required='python_sandbox' if profile=='python' else 'node_build_sandbox'
        if required not in allowed:raise ValueError('Runtime checks require explicit '+required+' permission')
        safe_path(check.get('path'))
        if profile=='python' and (not check['path'].endswith('.py') or not isinstance(check.get('expected_stdout'),str) or len(check['expected_stdout'])>4000):raise ValueError('Python checks need a .py entry and bounded expected_stdout (which may be empty)')
        if profile=='node_build' and not check['path'].endswith('/package.json'):raise ValueError('Build check needs a package.json artifact')
    keys=[('browser',c['path']) for c in browser_checks]+[(c['profile'],c['path']) for c in runtime_checks]
    if len(keys)!=len(set(keys)):raise ValueError('Combine repeated runtime checks for the same entry')
    repair_rounds=value.get('max_repair_rounds',1)
    if type(repair_rounds) is not int or not 0<=repair_rounds<=2:
        raise ValueError('max_repair_rounds must be 0 to 2')
    if not departments or set(departments) - set(DEPARTMENT_MAP):
        raise ValueError("Select at least one registered department")
    delivery_type=value.get('delivery_type','generic')
    if value.get('title') is not None:text(value['title'],'chat title',80)
    if delivery_type not in {'website','code','document','analysis','generic'}:raise ValueError('Invalid delivery_type')
    deliverables=value.get('deliverables',[])
    if not isinstance(deliverables,list) or len(deliverables)>16:raise ValueError('At most 16 declared deliverables are allowed')
    paths=set()
    for item in deliverables:
        if not isinstance(item,dict) or item.get('kind') not in {'html','code','document'}:raise ValueError('Invalid deliverable')
        path=safe_path(item.get('path'));owner=path.split('/')[0]
        if owner not in departments or '/' not in path:raise ValueError('Every deliverable needs a selected department owner')
        if path.casefold() in paths:raise ValueError('Duplicate deliverable path')
        paths.add(path.casefold())
        if item['kind']=='html' and not path.endswith('.html'):raise ValueError('HTML deliverable requires an HTML file')
    if delivery_type=='website' and ('engineering' not in departments or not any(d['kind']=='html' and d['path'].startswith('engineering/') for d in deliverables)):
        raise ValueError('Website delivery requires Engineering and an engineering-owned HTML source deliverable')
    return {"departments": departments, "objective": value["objective"], "inputs": value.get("inputs", {}),
            "constraints": value.get("constraints", []), "acceptance_criteria": criteria,
            "allowed_capabilities": allowed, "artifact_checks": checks, "execution_checks": execution,
            "max_repair_rounds":repair_rounds,"data_checks":data_checks,'browser_checks':browser_checks,'runtime_checks':runtime_checks,'delivery_type':delivery_type,'deliverables':deliverables,'title':value.get('title')}


def proposal(value, department, roster):
    if value.get("decision") not in ("contribute", "decline"):
        raise ValueError("Head must contribute or decline")
    text(value.get("reason"), "proposal reason", 4000)
    deps = strings(value.get("depends_on"), "department dependencies", 10)
    if set(deps) - set(DEPARTMENT_MAP) or department in deps:
        raise ValueError("Invalid department dependency")
    tasks = value.get("tasks")
    if not isinstance(tasks, list) or len(tasks) > 6:
        raise ValueError("A department may assign at most six tasks per round")
    if (value["decision"] == "decline" and (tasks or deps)) or (value["decision"] == "contribute" and not tasks):
        raise ValueError("Contributing heads need tasks; declining heads cannot assign work")
    keys, paths = set(), set()
    for task in tasks:
        if not isinstance(task, dict) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", task.get("key", "")):
            raise ValueError("Invalid task key")
        if task["key"] in keys:
            raise ValueError("Duplicate task key")
        keys.add(task["key"])
        text(task.get("title"), "task title", 160)
        text(task.get("instructions"), "task instructions", 4000)
        agent = roster.get(task.get("assignee"))
        if not agent or agent["department"] != department or agent["role"] in ("department_lead", "mission_director"):
            raise ValueError("Heads can assign work only to employees of their own department")
        strings(task.get("depends_on"), "task dependencies", 6)
        strings(task.get("tools",[]), "optional tools", 5)
        required = strings(task.get("requires"), "required capabilities", 8)
        if not required:
            raise ValueError("Task must declare required capabilities")
        outputs = strings(task.get("outputs"), "task outputs", 4)
        if not outputs:
            raise ValueError("Task must declare output files")
        outputs=[department_path(path,department) for path in outputs]
        task['outputs']=outputs
        for path in outputs:
            safe_path(path)
            normalized = path.casefold()
            if any(normalized == old or normalized.startswith(old + "/") or old.startswith(normalized + "/") for old in paths):
                raise ValueError("Artifact paths overlap on case-insensitive filesystems")
            paths.add(normalized)
    topological({t["key"]: t["depends_on"] for t in tasks})
    return value


def topological(graph):
    remaining = {k: set(v) for k, v in graph.items()}
    if any(deps - set(graph) for deps in remaining.values()):
        raise ValueError("Unknown or unselected dependency")
    ordered = []
    while remaining:
        ready = sorted(k for k, deps in remaining.items() if not deps)
        if not ready:
            raise ValueError("Cyclic dependencies")
        ordered.extend(ready)
        for key in ready:
            del remaining[key]
        for deps in remaining.values():
            deps.difference_update(ready)
    return ordered


def selection(value, proposals):
    chosen = strings(value.get("departments"), "selected departments", 10)
    text(value.get("reason"), "selection reason", 4000)
    if not chosen or any(d not in proposals or proposals[d]["decision"] != "contribute" for d in chosen):
        raise ValueError("Director must select contributing departments")
    topological({d: proposals[d]["depends_on"] for d in chosen})
    return value


def worker_result(value, task, department=None):
    if value.get("status") not in ("produced", "blocked"):
        raise ValueError("Worker status must be produced or blocked")
    text(value.get("summary"), "worker summary", 4000)
    strings(value.get("limitations"), "worker limitations", 12)
    strings(value.get("capability_requests"), "capability requests", 8)
    artifacts = value.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) > 4:
        raise ValueError("Invalid artifacts")
    if value["status"] == "blocked" and artifacts:
        raise ValueError('Blocked workers cannot publish completed artifacts. Keep status blocked and return artifacts=[]; explain the missing evidence in summary, limitations and capability_requests. Do not change status to produced unless the assignment is actually complete.')
    if department:
        for artifact in artifacts:
            if not isinstance(artifact,dict):raise ValueError('Artifact must be an object')
            artifact['path']=department_path(artifact.get('path'),department)
    if value["status"] == "produced" and {a.get("path") for a in artifacts if isinstance(a, dict)} != set(task["outputs"]):
        raise ValueError("Worker must provide exactly the assigned outputs")
    paths = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise ValueError("Artifact must be an object")
        safe_path(artifact.get("path"))
        text(artifact.get("content"), "artifact content", 80000)
        paths.append(artifact["path"])
    if len(set(paths)) != len(paths):
        raise ValueError("Duplicate artifact paths")
    return value


def report(value, artifact_ids):
    text(value.get("summary"), "department summary", 6000)
    refs = strings(value.get("artifact_ids"), "artifact references", 24)
    if set(refs) - set(artifact_ids):
        raise ValueError("Head cited unknown artifacts")
    strings(value.get("blockers"), "blockers", 12)
    strings(value.get("improvements"), "improvements", 8)
    return value


def review(value, criteria):
    if type(value.get("accepted")) is not bool:
        raise ValueError("Review requires a boolean accepted verdict")
    text(value.get("reason"), "review reason", 6000)
    checks = value.get("criteria")
    if not isinstance(checks, list) or len(checks) != len(criteria):
        raise ValueError("Review must cover every acceptance criterion")
    for index, check in enumerate(checks):
        if not isinstance(check, dict) or check.get("criterion") != criteria[index] or type(check.get("met")) is not bool:
            raise ValueError("Review criteria cannot be replaced or omitted")
        text(check.get("evidence"), "review evidence", 4000)
    if value["accepted"] and not all(c["met"] for c in checks):
        raise ValueError("Unmet criteria cannot be accepted")
    return value


def retrospective(value):
    text(value.get("summary"), "director summary", 6000)
    if 'user_summary' in value:text(value['user_summary'],'user-facing summary',4000)
    improvements = value.get("improvements")
    if not isinstance(improvements, list) or len(improvements) > 8:
        raise ValueError("Invalid improvements")
    for item in improvements:
        if not isinstance(item, dict) or item.get("department") not in DEPARTMENT_MAP:
            raise ValueError("Improvement needs a responsible department")
        for field in ("change", "evidence", "measure"):
            text(item.get(field), field, 3000)
    return value
