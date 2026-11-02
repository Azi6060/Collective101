import argparse
import csv
import json
import sys
from pathlib import Path
from .locking import workspace_lock
from .provider import FixtureProvider, MetaProvider
from .registry import build_roster, department_records
from .report import export_report
from .runtime import Organization

DEFAULT_PROMPT = "Analyze supplied attendance records and deliver a constrained event plan, a draft brief, and an evidence-linked report."


def main(argv=None):
    parser = argparse.ArgumentParser(description="Collective 101 local organization runtime")
    parser.add_argument("--state", type=Path, default=Path(".collective101/state.db"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("registry", help="Print the configured 101-agent roster")
    agent_parser = sub.add_parser("agent", help="Inspect an individual agent definition and effective system prompt")
    agent_parser.add_argument("agent_id")
    org_parser = sub.add_parser("organization", help="Run a generic department-led draft-artifact mission")
    org_parser.add_argument("--mission", type=Path, required=True)
    org_parser.add_argument("--provider", choices=("fixture", "meta"), default="meta")
    org_parser.add_argument("--max-calls", type=int, default=160)
    org_parser.add_argument("--output", type=Path)
    org_resume = sub.add_parser("organization-resume", help="Resume a recorded department-led mission")
    org_resume.add_argument("mission_id")
    org_resume.add_argument("--provider", choices=("fixture", "meta"), default="meta")
    org_resume.add_argument("--output", type=Path)
    web_parser = sub.add_parser("serve", help="Open the local organization console")
    web_parser.add_argument("--port",type=int,default=8765)
    eval_parser=sub.add_parser('evaluate',help='Run bounded live routing, specialist and departmental evaluations in isolated state')
    eval_parser.add_argument('--max-calls',type=int,default=80)
    for command in ("demo", "run", "resume", "revise", "report"):
        item = sub.add_parser(command)
        item.add_argument("--output", type=Path)
        if command in ("resume", "revise", "report"):
            item.add_argument("mission_id")
        if command != "report":
            item.add_argument("--provider", choices=("fixture", "meta"), default="fixture" if command == "demo" else "meta")
            item.add_argument("--concurrency", type=int, default=4)
            item.add_argument("--inject-outage", action="store_true")
            item.add_argument("--inject-bad-cost", action="store_true")
        if command in ("demo", "run"):
            item.add_argument("--input", type=Path, default=Path(__file__).parent.parent / "examples" / "attendance.csv")
            item.add_argument("--prompt", default=DEFAULT_PROMPT)
            item.add_argument("--max-calls", type=int, default=64)
        if command in ("demo", "run", "revise"):
            item.add_argument("--budget", type=float, default=None if command == "revise" else 500)
            item.add_argument("--capacity", type=int, default=None if command == "revise" else 100)
            item.add_argument("--fixed-cost", type=float, default=None if command == "revise" else 100)
            item.add_argument("--per-person", type=float, default=None if command == "revise" else 5)
    args = parser.parse_args(argv)
    if args.command=='evaluate':
        from .evaluations import run_evaluation
        from .store import Store
        from .connectors import ConnectorManager
        store=Store(args.state)
        try:
            provider=ConnectorManager(store,{a['id']:a for a in build_roster()}).model_provider()
            report=run_evaluation(provider,Path(__file__).resolve().parents[1]/'work/evaluations',args.max_calls)
            print(str(report));return 0
        except (ValueError,RuntimeError,OSError) as error:
            print(str(error),file=sys.stderr);return 2
        finally:store.close()
    if args.command == "serve":
        from .web_server import serve
        serve(args.state,args.port)
        return 0
    if args.command == "registry":
        print(json.dumps({"departments": department_records(), "agents": build_roster()}, indent=2))
        return 0
    if args.command == "agent":
        from .agent_harness import BASE_PROMPT, PHASES
        found = next((a for a in build_roster() if a["id"] == args.agent_id), None)
        if not found:
            print("Unknown agent: " + args.agent_id, file=sys.stderr)
            return 2
        group = found["role"] if found["role"] in PHASES else "employee"
        print(json.dumps({"definition": found, "phases": sorted(PHASES[group]),
            "system_prompt": BASE_PROMPT + "\n" + found["system_prompt"],
            "departmental_harness_capabilities": ["draft_artifact"]}, indent=2))
        return 0
    if args.command in ("organization", "organization-resume"):
        return departmental_command(args)
    organization = None
    try:
        with workspace_lock(args.state.with_suffix(".lock")):
            provider = FixtureProvider() if args.command == "report" or args.provider == "fixture" else MetaProvider()
            organization = Organization(args.state, provider, getattr(args, "concurrency", 4),
                                        getattr(args, "inject_outage", False), getattr(args, "inject_bad_cost", False))
            if args.command in ("demo", "run"):
                with args.input.open(encoding="utf-8-sig", newline="") as handle:
                    if args.input.stat().st_size > 5_000_000:
                        raise ValueError("Input CSV exceeds the 5 MB limit")
                    rows = list(csv.DictReader(handle))
                mission_id = organization.create(args.prompt, rows,
                    {"budget": args.budget, "capacity": args.capacity, "fixed_cost": args.fixed_cost, "per_person": args.per_person}, args.max_calls)
            else:
                mission_id = args.mission_id
            if args.command == "revise":
                constraints = organization.store.mission(mission_id)["constraints"]
                for key in ("budget", "capacity", "fixed_cost", "per_person"):
                    value = getattr(args, key)
                    if value is not None:
                        constraints[key] = value
                affected = organization.revise(mission_id, constraints)
                print("Invalidated tasks: " + ", ".join(affected))
            if args.command != "report":
                organization.run(mission_id)
            output = args.output or Path("runs") / mission_id
            report = export_report(organization, mission_id, output)
            mission = organization.store.mission(mission_id)
            print(json.dumps({"mission_id": mission_id, "status": mission["status"], "provider": mission["provider"],
                              "version": mission["version"], "calls": mission["calls"], "report": str(report.resolve())}, indent=2))
            return 0 if mission["status"] == "completed" else 2
    except (ValueError, OSError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    finally:
        if organization:
            organization.close()


def departmental_command(args):
    from .department_fixture import DepartmentFixtureProvider
    from .department_runtime import DepartmentOrganization
    organization = None
    try:
        with workspace_lock(args.state.with_suffix(".lock")):
            provider = DepartmentFixtureProvider() if args.provider == "fixture" else MetaProvider()
            organization = DepartmentOrganization(args.state, provider)
            if args.command == "organization":
                if args.mission.stat().st_size > 100000:
                    raise ValueError("Mission file exceeds 100 KB")
                mission_id = organization.create(json.loads(args.mission.read_text(encoding="utf-8-sig")), args.max_calls)
            else:
                mission_id = args.mission_id
            run = organization.run(mission_id)
            output = args.output or Path("runs") / mission_id
            report = organization.export(mission_id, output)
            print(json.dumps({"mission_id": mission_id, "status": run["status"], "provider": run["provider"]["mode"],
                "calls": run["calls"], "error": run["error"], "report": str(report),
                "scope": "Reviewed artifacts with recorded checks where requested; no deployment"}, indent=2))
            return 0 if run["status"] == "reviewed" else 2
    except (ValueError, OSError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    finally:
        if organization:
            organization.close()
