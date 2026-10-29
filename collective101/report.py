import html
import json
from pathlib import Path
from .registry import DEPARTMENTS


def export_report(organization, mission_id, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    mission = organization.store.mission(mission_id)
    tasks = organization.store.tasks(mission_id)
    events = organization.store.query("SELECT * FROM events WHERE mission_id=? ORDER BY seq", (mission_id,))
    for event in events:
        event["data"] = json.loads(event["data"])
    invoked = {event["data"]["agent"] for event in events if event["kind"] == "model.requested"}
    bundle = {"mission": mission, "tasks": tasks, "events": events, "roster": organization.roster,
              "mode_notice": {"fixture": "DETERMINISTIC FIXTURE: no AI inference",
                              "simulation": "HTTP CONTRACT SIMULATION: no AI inference",
                              "meta": "META MODEL EXECUTION: model summaries still require independent checking"}[mission["provider"]]}
    (output / "mission.json").write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    artifacts = output / "artifacts"
    artifacts.mkdir(exist_ok=True)
    for task in tasks:
        stale_file = artifacts / f"{task['key']}.json"
        if task["status"] != "accepted" and stale_file.exists():
            stale_file.unlink()
        if task["status"] == "accepted":
            (artifacts / f"{task['key']}.json").write_text(json.dumps(task["result"], indent=2, ensure_ascii=False), encoding="utf-8")
    esc = lambda value: html.escape(str(value), quote=True)
    departments = []
    for department in DEPARTMENTS:
        people = [agent for agent in organization.roster if agent["department"] == department.id]
        cells = "".join(f'<span class="agent {"invoked" if agent["id"] in invoked else ""}" title="{esc(agent["id"])} / {esc(agent["specialty"])}">{index + 1:02}</span>'
                        for index, agent in enumerate(people))
        active = len([agent for agent in people if agent["id"] in invoked])
        departments.append(f'<article class="department"><div class="dept-head"><h3>{esc(department.name)}</h3><span>{department.count:02}</span></div>'
                           f'<p>{esc(department.charter)}</p><div class="agents">{cells}</div><small>{active} identities invoked during this mission</small></article>')
    task_rows = []
    for task in tasks:
        task_rows.append(f'<tr><td><strong>{esc(task["spec"]["title"])}</strong><small>{esc(task["key"])} · {esc(task["spec"]["department"])}</small></td>'
                         f'<td><span class="status {esc(task["status"])}">{esc(task["status"])}</span></td><td>{esc(task["agent_id"] or "—")}</td>'
                         f'<td>{esc(task["reviewer_id"] or "—")}</td><td>{task["attempts"]}</td></tr>')
    details = []
    for task in tasks:
        details.append(f'<details><summary>{esc(task["spec"]["title"])} · evidence & verdict</summary>'
                       f'<pre>{esc(json.dumps({"result": task["result"], "verdict": task["verdict"], "error": task["error"]}, indent=2, ensure_ascii=False))}</pre></details>')
    timeline = "".join(f'<li><span class="event-index">{index + 1:03}</span><div><strong>{esc(event["kind"])}</strong>'
                       f'<p>{esc(json.dumps(event["data"], ensure_ascii=False))}</p><small>{esc(event["created_at"])}</small></div></li>'
                       for index, event in enumerate(events))
    accepted = sum(task["status"] == "accepted" for task in tasks)
    css = """
    :root{color-scheme:dark;--bg:#101419;--panel:#171e25;--border:#2c3741;--muted:#9eafb9;--mint:#a9f3c9;--text:#eff5f2}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 'Segoe UI',system-ui,sans-serif}
    main{max-width:1320px;margin:auto;padding:40px 32px}header{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--border);padding-bottom:22px}
    .brand{font-size:18px;letter-spacing:.12em;font-weight:700}.accent{color:var(--mint)}.tag,small{color:var(--muted);font-size:12px}
    .eyebrow{margin-top:46px;text-transform:uppercase;color:var(--mint);font-size:12px;letter-spacing:.16em}h1{font-size:clamp(32px,5vw,62px);font-weight:500;letter-spacing:-.04em;line-height:1.1;margin:12px 0 18px}
    .intro{max-width:820px;color:var(--muted)}.notice{padding:14px 18px;margin:24px 0;border-left:3px solid #e3bd76;background:#262219;color:#f0d19c}
    .stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:30px 0}.stat{border-top:1px solid var(--border);padding-top:14px}.stat b{display:block;font-size:32px;font-weight:500}.stat span{color:var(--muted)}
    h2{font-size:22px;font-weight:500;margin:40px 0 18px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.department{background:var(--panel);border:1px solid var(--border);padding:20px;border-radius:8px}
    .dept-head{display:flex;justify-content:space-between;gap:12px}.dept-head span{color:var(--mint);font-size:22px}h3{margin:0;font-size:15px;font-weight:600}.department p{color:var(--muted);font-size:13px;min-height:42px}
    .agents{display:flex;flex-wrap:wrap;gap:5px;margin:16px 0 12px}.agent{background:#212b33;border:1px solid #35434c;padding:3px 7px;border-radius:3px;color:#9aabb7;font-size:11px}.agent.invoked{background:#234333;color:var(--mint);border-color:#528b67}
    .table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;text-align:left}th{color:var(--muted);font-weight:400;font-size:12px}th,td{padding:14px 12px;border-bottom:1px solid var(--border)}td small{display:block}.status{font-size:12px;background:#30353a;border-radius:20px;padding:4px 9px}.status.accepted{background:#234333;color:var(--mint)}.status.failed{background:#4c292b;color:#ffc1be}
    details{border:1px solid var(--border);border-radius:6px;margin:10px 0}summary{padding:14px;cursor:pointer}pre{padding:16px;margin:0;background:#0c1014;white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.65 Consolas,monospace}
    .timeline{list-style:none;padding:0;max-height:580px;overflow:auto}.timeline li{display:flex;gap:18px;border-left:1px solid var(--border);padding:0 0 22px 16px}.event-index{color:var(--mint);font:12px Consolas,monospace;padding-top:4px}.timeline strong{font-size:13px}.timeline p{color:var(--muted);font-size:12px;margin:4px 0;overflow-wrap:anywhere}footer{color:var(--muted);border-top:1px solid var(--border);padding-top:18px;margin-top:32px;font-size:12px}
    @media(max-width:900px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){main{padding:24px 16px}.grid{grid-template-columns:1fr}.stats{grid-template-columns:repeat(2,1fr)}header{align-items:start;gap:16px}.tag{text-align:right}}
    """
    document = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Collective 101 · Mission report</title><style>{css}</style></head><body><main>
    <header><div class="brand">COLLECTIVE <span class="accent">101</span></div><div class="tag">ORGANIZATION RUNTIME / v0.1<br>Exported run report · no live controls</div></header>
    <div class="eyebrow">One mission. Coordinated expertise.</div><h1>An organization<br>you can inspect.</h1>
    <p class="intro">{esc(mission['prompt'])}</p><div class="notice">{esc(bundle['mode_notice'])}. Local artifacts are checked; external assumptions are not verified.</div>
    <div class="stats"><div class="stat"><b>101</b><span>Registered identities</span></div><div class="stat"><b>{len(invoked)}</b><span>Identities invoked</span></div>
    <div class="stat"><b>{accepted}/{len(tasks)}</b><span>Accepted tasks · version {mission['version']}</span></div><div class="stat"><b>{mission['calls']}/{mission['max_calls']}</b><span>Provider calls · {esc(mission['status'])}</span></div></div>
    <h2>Departments <span class="tag">/ green identifies an invoked identity</span></h2><div class="grid">{''.join(departments)}</div>
    <p class="tag">The additional organization-level identity is director-001. Broker and scheduling events are runtime policy actions; they are not counted as model invocations.</p>
    <h2>Mission board</h2><div class="table-wrap"><table><thead><tr><th>Assignment</th><th>State</th><th>Worker</th><th>Independent reviewer</th><th>Attempts</th></tr></thead><tbody>{''.join(task_rows)}</tbody></table></div>
    <h2>Artifacts & verification</h2>{''.join(details)}<h2>Execution trail</h2><ol class="timeline">{timeline}</ol>
    <footer>{esc(mission_id)} · {mission['tokens']} provider-reported tokens · Source data supplied by user · Roster size is not a performance claim</footer>
    </main></body></html>'''
    (output / "report.html").write_text(document, encoding="utf-8")
    return output / "report.html"
