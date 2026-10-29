"""Small approved local capability catalog, with task-scoped access enforcement."""
import math
import threading
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from .planning import TOOL_CAPABILITIES
from .store import encode, now


class ToolDenied(RuntimeError):
    pass


class ToolUnavailable(RuntimeError):
    pass


def validate_rows(rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 10000:
        raise ValueError("Supply 1 to 10,000 event records")
    cleaned = []
    for row in rows:
        if not isinstance(row, dict) or not {"event", "registered", "attended"} <= row.keys():
            raise ValueError("CSV requires event, registered, attended columns")
        try:
            registered, attended = int(row["registered"]), int(row["attended"])
        except (ValueError, TypeError, OverflowError):
            raise ValueError("Attendance values must be whole numbers") from None
        if str(registered) != str(row["registered"]) or str(attended) != str(row["attended"]):
            raise ValueError("Attendance values must be whole numbers")
        if registered <= 0 or not 0 <= attended <= registered:
            raise ValueError("Each event needs positive registration and attendance between zero and registration")
        if not isinstance(row["event"], str) or not 1 <= len(row["event"]) <= 200:
            raise ValueError("Event label must contain 1 to 200 characters")
        cleaned.append({"event": row["event"], "registered": registered, "attended": attended})
    return cleaned


def money_cents(value):
    try:
        decimal = Decimal(str(value))
        if not decimal.is_finite() or decimal < 0 or decimal > Decimal("100000000"):
            raise ValueError("Money must be finite, nonnegative, and at most 100 million units")
        return int((decimal * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError):
        raise ValueError("Invalid money value") from None


def validate_constraints(value):
    if not isinstance(value, dict):
        raise ValueError("Constraints must be an object")
    if set(value) != {"budget", "capacity", "fixed_cost", "per_person"}:
        raise ValueError("Constraints require budget, capacity, fixed_cost, per_person")
    capacity = value["capacity"]
    if isinstance(capacity, bool) or not isinstance(capacity, int) or not 1 <= capacity <= 100000:
        raise ValueError("Capacity must be an integer between 1 and 100,000")
    for field in ("budget", "fixed_cost", "per_person"):
        money_cents(value[field])
    if money_cents(value["per_person"]) <= 0:
        raise ValueError("Per-person cost must be positive")
    return value


def attendance(rows):
    registered = sum(row["registered"] for row in rows)
    attended = sum(row["attended"] for row in rows)
    return {"events": len(rows), "registered": registered, "attended": attended,
            "mean_attendance": attended / len(rows), "attendance_rate": attended / registered,
            "method": "Descriptive historical mean, not a validated predictive forecast."}


def operating_plan(rows, constraints):
    analysis = attendance(rows)
    budget, fixed, unit = (money_cents(constraints[key]) for key in ("budget", "fixed_cost", "per_person"))
    if budget < fixed:
        raise ValueError("Mission is infeasible: the budget is below the fixed operating cost")
    planned = min(math.ceil(analysis["mean_attendance"]), constraints["capacity"], (budget - fixed) // unit)
    return {"planned_attendees": planned, "total_cost_cents": fixed + unit * planned,
            "budget_cents": budget, "capacity": constraints["capacity"],
            "fixed_cost_cents": fixed, "per_person_cents": unit,
            "limitations": "Planning assumption uses the historical mean. Venue availability and prices are user supplied, not externally verified."}


def dependency_data(dependencies, tool):
    for task in dependencies.values():
        for evidence in task["result"]["evidence"]:
            if evidence["tool"] == tool:
                return evidence["data"]
    raise ValueError(f"Missing accepted dependency evidence for {tool}")


def tool_definition(name):
    if name == "request_capability":
        return {"type": "function", "function": {
            "name": name, "description": "Request an approved task-scoped capability. This does not install software.",
            "parameters": {"type": "object", "properties": {"capability": {"type": "string"}},
                           "required": ["capability"], "additionalProperties": False}}}
    if name == "read_evidence":
        description = "Read accepted outputs of this task's declared dependencies."
    else:
        description = {
            "profile_dataset": "Inspect supplied immutable event records; return columns and record count.",
            "analyze_attendance": "Compute historical attendance totals and rates from supplied event records.",
            "build_event_plan": "Produce a costed plan within current mission budget and capacity using attendance evidence.",
            "draft_event_brief": "Create a draft brief from the accepted operating plan; no external communication is sent.",
            "assemble_report": "Assemble an evidence-linked digest of all accepted dependency artifacts.",
        }[name]
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}}


class ToolGateway:
    def __init__(self, store, fail_once=False):
        self.store = store
        self.fail_once = fail_once
        self.lock = threading.Lock()

    def grant(self, mission, task, agent, capability):
        current = self.store.query("SELECT status,agent_id FROM tasks WHERE id=?", (task["id"],))
        if (not current or current[0]["status"] != "running" or current[0]["agent_id"] != agent["id"]
                or capability != task["spec"]["capability"] or capability not in agent["capabilities"]):
            self.store.event(mission["id"], "capability.denied", task=task["key"], agent=agent["id"], capability=capability)
            raise ToolDenied("Capability is outside this agent's current assignment or charter")
        self.store.execute("INSERT OR REPLACE INTO grants VALUES(?,?,?,?,1)", (mission["id"], task["id"], agent["id"], capability))
        self.store.event(mission["id"], "capability.granted", task=task["key"], agent=agent["id"],
                         capability=capability, broker="platform-002", expires="end_of_task_attempt", mechanism="runtime_policy")
        return {"granted": capability, "tool": task["spec"]["tool"], "scope": task["id"]}

    def definitions(self, mission, task, agent):
        definitions = [tool_definition("request_capability"), tool_definition("read_evidence")]
        grants = self.store.query("SELECT capability FROM grants WHERE mission_id=? AND task_id=? AND agent_id=? AND active=1",
                                  (mission["id"], task["id"], agent["id"]))
        if task["spec"]["capability"] in {row["capability"] for row in grants}:
            definitions.append(tool_definition(task["spec"]["tool"]))
        return definitions

    def revoke(self, task_id, agent_id):
        self.store.execute("UPDATE grants SET active=0 WHERE task_id=? AND agent_id=?", (task_id, agent_id))

    def invoke(self, mission, task, agent, name, arguments, dependencies):
        if not isinstance(arguments, dict):
            raise ToolDenied("Tool arguments must be an object")
        if name == "request_capability":
            if set(arguments) != {"capability"} or not isinstance(arguments["capability"], str):
                raise ToolDenied("Capability request requires exactly one string capability")
            return self.grant(mission, task, agent, arguments["capability"])
        if arguments:
            raise ToolDenied("This milestone's local tools accept no arguments")
        if name == "read_evidence":
            return {"dependencies": {key: task["result"] for key, task in dependencies.items()}}
        capability = TOOL_CAPABILITIES.get(name)
        allowed = self.store.query("SELECT 1 FROM grants WHERE mission_id=? AND task_id=? AND agent_id=? AND capability=? AND active=1",
                                   (mission["id"], task["id"], agent["id"], capability))
        current = self.store.query("SELECT status,agent_id FROM tasks WHERE id=?", (task["id"],))
        if (not capability or name != task["spec"]["tool"] or not allowed or not current
                or current[0]["status"] != "running" or current[0]["agent_id"] != agent["id"]):
            self.store.event(mission["id"], "tool.denied", task=task["key"], agent=agent["id"], tool=name)
            raise ToolDenied("Tool call has no valid grant for this running assignment")
        with self.lock:
            previous = self.store.query("SELECT seq FROM events WHERE mission_id=? AND kind='fault.injected'", (mission["id"],))
            if self.fail_once and name == "build_event_plan" and not previous:
                self.store.event(mission["id"], "fault.injected", tool=name, simulated=True,
                                 detail="One local tool invocation deliberately unavailable")
                raise ToolUnavailable("Injected temporary tool outage")
        rows, constraints = mission["input"]["rows"], mission["constraints"]
        if name == "profile_dataset":
            data = {"row_count": len(rows), "columns": ["event", "registered", "attended"], "source": "user_supplied_csv"}
        elif name == "analyze_attendance":
            data = attendance(rows)
        elif name == "build_event_plan":
            historical = dependency_data(dependencies, "analyze_attendance")
            if historical != attendance(rows):
                raise ValueError("Dependency analysis is inconsistent with mission input")
            data = operating_plan(rows, constraints)
        elif name == "draft_event_brief":
            plan = dependency_data(dependencies, "build_event_plan")
            data = {"plan": plan, "markdown": (
                f"# Event operating brief\n\nPlan for {plan['planned_attendees']} attendees within a capacity of {plan['capacity']}.\n\n"
                f"Operating cost: {plan['total_cost_cents'] / 100:.2f} currency units; "
                f"budget: {plan['budget_cents'] / 100:.2f}.\n\n{plan['limitations']}\n\n"
                "This is a draft. No venue has been booked and no messages have been sent.")}
        else:
            data = {"deliverables": [{"task": key, "evidence_ids": item["result"]["evidence_ids"]}
                                      for key, item in dependencies.items()],
                    "conclusion": "Local event-analysis deliverables assembled; external assumptions remain unverified."}
        evidence = {"evidence_id": "ev_" + uuid.uuid4().hex[:16], "tool": name, "data": data,
                    "task_id": task["id"], "mission_version": mission["version"]}
        self.store.execute("INSERT INTO artifacts VALUES(?,?,?,?,?,?)", (evidence["evidence_id"], mission["id"],
                           task["id"], mission["version"], encode(evidence), now()))
        self.store.event(mission["id"], "tool.executed", task=task["key"], agent=agent["id"],
                         tool=name, evidence_id=evidence["evidence_id"])
        return evidence


def check_artifact(mission, task, result, dependencies):
    """Acceptance is independent of the worker's completion claim."""
    errors = []
    evidence = result.get("evidence", [])
    if len(evidence) != 1 or evidence[0].get("tool") != task["spec"]["tool"]:
        return ["Exactly one authoritative artifact from the assigned tool is required"]
    item = evidence[0]
    if item.get("task_id") != task["id"] or item.get("mission_version") != mission["version"]:
        return ["Evidence belongs to a different task or mission version"]
    if result.get("evidence_ids") != [item["evidence_id"]]:
        errors.append("Completion must cite its actual tool evidence")
    data, rows = item["data"], mission["input"]["rows"]
    check = task["spec"]["check"]
    if check == "profile":
        if data.get("row_count") != len(rows) or data.get("columns") != ["event", "registered", "attended"]:
            errors.append("Dataset profile does not match the supplied records")
    elif check == "attendance":
        if data != attendance(rows):
            errors.append("Historical attendance calculation does not reconcile")
    elif check == "budget":
        if data != operating_plan(rows, mission["constraints"]):
            errors.append("Operating plan violates or misstates the current mission constraints")
    elif check == "brief":
        plan = operating_plan(rows, mission["constraints"])
        if data.get("plan") != plan or not isinstance(data.get("markdown"), str) or not data["markdown"].strip():
            errors.append("Brief must include the current accepted plan and nonempty text")
    elif check == "report":
        expected = [{"task": key, "evidence_ids": value["result"]["evidence_ids"]} for key, value in dependencies.items()]
        if data.get("deliverables") != expected:
            errors.append("Final digest does not reference every accepted dependency")
    return errors
