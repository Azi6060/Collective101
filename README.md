# Collective 101

Main project: `C:\Users\justs\OneDrive\Documents\Desktop\collective101`.

An AI organization with **101 individually configured agents: one Mission Director, ten department heads and ninety employees**. Heads decide whether they can contribute, coordinate with other heads, assign their own employees, collect results and report to the director. The runtime enforces the reporting hierarchy.

Read [PROJECT_STATUS.md](PROJECT_STATUS.md) for the living aim, verified status, limitations and next work. [AGENTS.md](AGENTS.md) governs project maintenance. Browse [all departments and agent files](collective101/departments/README.md).

The organization produces and reviews code/text artifacts and can now execute **pure JavaScript acceptance checks in a QuickJS/WebAssembly sandbox**. Eligible agents can also read/search approved knowledge, recall reviewed episodes, and request configured public web search. It can connect compatible remote MCP tools through the Connectors tab. It does not deploy websites or provide a full browser/DOM. The included fixture demonstrations exercise the real organization control flow with scripted model responses; they do not perform AI inference.

## Open the mission-control UI

From the Desktop project:

```powershell
npm.cmd ci --ignore-scripts
python -m collective101 --state .collective101/console.db serve --port 8765
```

Open **http://127.0.0.1:8765**. `Start Collective101.cmd` is a double-click launcher for the server. Bootstrap CSS is bundled locally; the UI does not require a CDN.

- **Overview:** organization counts, provider/sandbox readiness and mission history.
- **Organization:** ten departments, all 101 agents, individual responsibilities, reporting lines and role instructions.
- **Mission chat:** describe the outcome, answer clarification questions, inspect the brief, and start the organization. Live chat requires a configured model; credentials can be saved in Connectors.
- **Connectors:** browse a searchable card catalog. Gmail, Slack, Canva, GitHub, Google Drive and Google Calendar are clearly marked Coming soon. Set up the live model, Web search or Custom MCP from their cards; enabled tools are shared with all 101 agents.
- **Activity & evidence:** agent actions and status, leadership messages, artifact contents/downloads, and actual sandbox results. Filter by agent and mission. The page polls persisted state every 1.5 seconds; it does not display hidden model reasoning.

Every chat message, including "Hi", goes to **Head of Distribution (`distribution-001`)** through the configured live model. The agent chooses a direct reply, a contextual clarification, or a mission with relevant departments. There are no canned greetings, keyword/length question rules or demo run option in chat. Missing configuration or provider failure produces an error, never a scripted fallback. Historical demo chats remain on disk but are hidden from normal chat history.

Clarification questions come from the agent's JSON response and carry its identity and reason. The runtime validates and persists the question, pauses, binds the answer to that chat/phase, and resumes the requesting agent with the answer. Employees/heads may ask at runtime through the same intervention contract. Code still enforces permission, budget, ownership and evidence rules; those controls do not manufacture questions. Answered simple conversations accept follow-up messages in the same thread.

Pause takes effect before the next agent phase. A running provider call is allowed to finish. Resume is explicit after a server interruption. Rejected final results still need a new mission; automatic rework is not implemented.

During a mission, a department head may propose one additional task for a selected department that has not started yet, if more selected departments remain. The mission pauses and shows you the proposed employee, task, dependencies, tools and output path. **The task does not run unless you choose “Approve task.”** Approving adds only that task under the existing permissions and budget; declining continues the original plan. The runtime rejects proposals that add departments, change mission criteria or permissions, use the wrong employee, conflict with existing paths, or exceed the department's task limit. A report cannot request passive support and a task addition at the same time. The decision is recorded in Activity & evidence. This is a bounded first step toward replanning, not general task reassignment or automatic scope expansion.

This server binds only to `127.0.0.1`. Mutation endpoints require the local session token and same-origin requests. It is a single-user development application, not a public production server. Stop it with Ctrl+C in its terminal. Live keys belong only in the process environment; restart the server after changing configuration.

### JavaScript execution example

```powershell
python -m collective101 organization --mission examples/javascript-mission.json --provider fixture
```

The example uses scripted agent responses, but its three JavaScript checks actually run. Add `javascript_sandbox` to a mission's `allowed_capabilities` and define `execution_checks` with `path`, `expression` and a primitive `expected` result. The runtime fixes these checks when the mission is created and records source/check hashes, observed values, errors and duration. A failed check blocks acceptance even if a reviewer says yes.

The sandbox exposes no host filesystem, network, process, module loader or credentials. It applies a 16 MiB guest memory limit, a 512 KiB guest stack limit and a cooperative 500 ms deadline across checks, with an eight-second outer process timeout. Garbage collection/native allocations can delay cooperative interruption; the outer timeout is the final bound. This is JavaScript execution only, not a full browser, Python environment or operating-system container.

## Run a department-led mission

Python 3.11+; no third-party Python dependencies for source execution. Run from the main project folder:

```powershell
python -m collective101 organization --mission examples/website-mission.json --provider fixture
python -m collective101 organization --mission examples/research-mission.json --provider fixture
```

Each prints a mission ID and path to `runs/<mission-id>/REPORT.md`. The same folder contains `organization.json` with recorded leadership messages, and `artifacts/<department>/` with draft files. A successful draft run is `reviewed`; incomplete/failed work is `blocked`. Exit code is 0 for reviewed, 2 for blocked/error.

The website fixture selects Design, Engineering, Operations, Communications, Platform and Assurance. The research fixture selects Research, Strategy and Communications. These choices are deliberately scripted fixture data. Live mode asks model-powered heads to make those decisions from their charters, employee definitions and mission.

Inspect an agent or resume a run:

```powershell
python -m collective101 agent operations-001
python -m collective101 agent engineering-003
python -m collective101 registry
python -m collective101 organization-resume ORG_MISSION_ID --provider fixture
```

`--state PATH` is a global option and goes before the subcommand. `--max-calls` defaults to 160 for a new organization mission. `--output PATH` chooses an export directory. Completed reviewed runs replay without new provider calls. Cached phase outputs preserve progress; invalid responses retain a two-attempt limit; bounded tool requests use additional calls from the same task budget. Failed semantic review does not automatically launch a rework round. Export refuses to overwrite a differing existing file; use a new output directory when exporting a changed result.

## Your own mission

Copy an example JSON and edit these fields:

- `objective`: user outcome.
- `inputs`: supplied facts/documents as a JSON object; `fixture_scenario` is only a deterministic test selector and can be removed for live missions.
- `constraints`: bounded requirements and limits.
- `acceptance_criteria`: ordered requirements that the independent reviewer must evaluate individually.
- `departments`: initial shortlist; omitted legacy JSON missions retain the original all-heads consultation. Chat always supplies a shortlist.
- `allowed_capabilities`: `draft_artifact`, `javascript_sandbox`, `knowledge_read`, `knowledge_search`, `memory_search`, `web_search` as needed. Role eligibility and assignment scopes still apply.
- `artifact_checks`: optional `exists` or `contains` checks against paths such as `engineering/index.html`.
- `execution_checks`: optional pure JavaScript expressions with expected primitive results, evaluated against the specified `.js` artifact.

Heads may decline, select their own employees, declare dependencies and request unavailable capabilities. Unknown capabilities block the affected work. No head or director can grant executable access by including it in a prompt.

## Tools and knowledge

All 101 definitions now contain an editable `tool_allowlist`, constrained by code ceilings and the current phase. Heads/director can use read-only knowledge/memory and enabled connector tools within mission permission. Connected MCP and web search tools are eligible for all 101 agents without per-department configuration; employees still need mission permission and the head's `tools`/`requires` assignment. Built-in local tool ceilings remain role-specific. `requires` means essential: missing access, readiness or observed success blocks the task. Optional failures are disclosed and forwarded to the head.

Place approved UTF-8 reference files under `knowledge/shared/` or `knowledge/<department>/`; see [knowledge instructions](knowledge/README.md). These documents are sent to the configured model when retrieved. Agents cannot read arbitrary host files or another department's folder. Local documents are ignored by Git by default. Organization includes a Shared knowledge uploader for bounded text documents.

Open **http://127.0.0.1:8765/connectors**. Use search and availability filters to browse cards; Coming soon services cannot connect or access accounts yet. There is no department or agent selector. Existing saved connections now share enabled tools across the organization; credential ciphertext is preserved, and old MCP mission bindings with changed scope require a new mission. Model settings can use the existing MODEL_API_KEY environment setting or a saved key. Saved credentials use Windows user-bound DPAPI encryption, are never echoed to the browser, and can be replaced by editing the connection. Saving is configuration; actual provider/tool success is established only by an observed request.

For **Brave Search**, choose the Web search card, enter the key, and choose Save and enable. All agents are eligible to use it without a fixed per-query questionnaire. The agent should ask human guidance if a proposed disclosure exceeds the configured purpose. Missing essential access blocks work; optional access is not required to reason or draft.

For **remote MCP**, choose the Custom MCP card, enter an HTTPS endpoint and optional bearer token, save, discover tools, select the desired read-only tools, and enable organization-wide access. This performs real protocol discovery and invocation without adding per-server source code. Explicit localhost access permits loopback HTTP for a local server. Private/link-local/metadata endpoints and redirects are rejected; TLS validates the configured hostname. Tool selection, enabled state and mission/task permissions are rechecked on every call; changed configuration invalidates existing mission bindings.

Supported transport: Streamable HTTP with JSON or SSE responses and initialization/session headers. OAuth sign-in, stdio command launchers, write-capable tools and arbitrary REST API imports are not implemented. The server must declare read-only tools and the user must select them; annotations are a server claim, not a guarantee. Connect only servers you trust. Tool descriptions/results never become policy. Full JSON Schema validation is delegated to the MCP server; the client bounds arguments and checks required fields.

References: [MCP transport](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports), [MCP tool discovery](https://modelcontextprotocol.io/specification/2025-06-18/server/tools), [Brave API](https://api-dashboard.search.brave.com/api-reference/web/search/get).

The Activity filter **Tool requests & results** shows grants denied, unavailable tools, pending approvals and observed results. Exploratory employee JavaScript checks appear here; fixed mission acceptance checks remain under **Sandbox checks**. Only recorded evidence establishes execution.

[GUARDRAILS.md](GUARDRAILS.md) records enforced rules, risk signals, edge cases and the procedure for revising policies. Compatible remote MCP servers can expose read-only APIs/databases/calendar tools after configuration. No external account is connected by default. Direct OAuth account connectors and write-capable actions still need explicit implementations; a role prompt cannot create access.

## Live model execution

Set `MODEL_API_KEY` securely in the process environment, then:

```powershell
python -m collective101 organization --mission examples/website-mission.json --provider meta
```

`META_MODEL` overrides the adapter's configured default. No `.env` file is loaded automatically. No key belongs in source, command arguments, reports or Git. The model selected in the development chat does not configure this application's provider.

The existing Meta chat-completions adapter is reused unchanged. It never falls back to fixtures. A run records provider mode, model and endpoint and requires those to match on resume. A shared persistent budget includes intake and mission provider calls. The chat UI lets you lower the 160-call and 2,000,000-token-admission-unit defaults. Before each call the runtime charges serialized request UTF-8 bytes plus the 4,096-output-token allowance; reservations remain charged after failures or restarts. Provider-reported usage is tracked separately. This is conservative admission control, not an exact tokenizer, billing ceiling or dollar estimate. The legacy run counter still shows department calls only; the UI also shows the combined task ledger. Live execution of the new department cycle remains unverified.

## Structure

```text
collective101/
  departments/
    organization/director-001.json
    operations/operations-001.json   # Head of Operations
    operations/operations-002.json   # Operations Coordinator
    ...                             # 101 JSON definitions total
  registry.py                       # Validate/load identities and reporting lines
  agent_harness.py                  # Role-aware calls, retry/cache, leadership message policy
  org_contracts.py                   # Mission/decision/assignment/result validation
  department_runtime.py             # Department-led mission cycle and persistence
  department_fixture.py             # Explicit scripted test responses
  provider.py                       # Existing model adapter
  runtime.py                        # Original event-tool regression workflow
```

An agent definition contains its job-specific system prompt, responsibilities, reporting line, skills and memory namespace. Shared runtime code provides execution and enforces boundaries. This avoids 101 independently maintained client programs. The system ranks up to 100 reviewed same-agent, same-provider episodes by lexical relevance and supplies three with provenance, and records improvement proposals; neither mechanism proves learned competence.

[ARCHITECTURE.md](ARCHITECTURE.md) explains decisions and execution boundaries. The user-selected [agent-skills library](https://github.com/addyosmani/agent-skills) is retained locally under `third_party/agent-skills`; [provenance and usage](third_party/README.md) explain which development workflows were applied. It is not automatically a product tool or a globally enabled host plugin.

## Verify

```powershell
python -m unittest discover -s tests -p 'test_*.py' -v
python tests\run_heldout.py
python tests\run_heldout_learning.py
python tests\run_heldout_roles.py
npm.cmd run test:sandbox
# Starts an isolated local service with an injected test model; no real API spend:
npm.cmd run test:ui
# Real Chrome through Playwright MCP, disposable state and scripted model:
npm.cmd run test:browser
# Read-only page inspection of the running app on port 8765:
npm.cmd run browser:inspect
```

The held-out runners use deterministic fixtures only. They validate runtime and evidence-handling contracts, not live-model quality or demonstrated agent learning. The role audit checks all 101 definitions and role-phase boundaries; mission fixtures check small-team handoffs and outputs.

### Playwright MCP for development

The official `@playwright/mcp` server (0.0.84) and MCP SDK (1.32.2) are pinned in the npm lockfile. Run `npm.cmd ci` after cloning; Node 24 and installed Google Chrome were used for verification. No browser download is needed on this machine. The server launches on demand over stdio with headless, isolated Chrome and closes when each command finishes.

`test:browser` starts its own ephemeral loopback server and disposable SQLite state, injects the scripted test provider, and checks layout across five views at seven mobile, tablet, laptop and desktop viewport sizes, plus accessibility smoke checks for landmarks, headings, control names, form labels, image alt text and the skip link. It also checks greeting, activity hints, clarification/resume, organization and connector navigation. It does not target your running app or call a paid model. These automated checks are not a full WCAG audit, assistive-technology test, or validation on physical devices. `browser:inspect` reads `/chat` and `/connectors` on `http://127.0.0.1:8765`, waits for application readiness and saves screenshots, snapshots and metrics under ignored `work/playwright/`. To inspect another local port, set `COLLECTIVE101_BROWSER_URL`. Inspection may record visible mission/connector names; keep these local artifacts private.

`.codex/config.toml` also contains a project-scoped `playwright` MCP entry for this Desktop path. Native Codex tool loading requires opening this folder as a trusted project and restarting/reloading the client. During setup, the current client did **not** discover that entry (`codex mcp get playwright` returned not found); the SDK commands above were independently verified and work without native tool registration. No global trust settings were changed. See [Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp).

Browser launches use an isolated profile, browser sandbox and localhost origin restriction; service workers and page-provided WebMCP tools are disabled. The native entry disables unsafe code, uploads and drop tools. Origin restrictions are defense in depth, not a complete network security boundary. This is a developer testing tool, not a browser capability granted to the 101 agents, and it does not use your signed-in browser profile. See the [official Playwright MCP repository](https://github.com/microsoft/playwright-mcp).

The earlier 31 October agent-foundation verification passed 40 tests: organization hierarchy, all-101 fixture invocation, two distinct mission teams, ownership/routing denial, missing capabilities, independent rejection, artifact checks, path validation, persistence, memory provenance, and the 21 original event-runtime tests. See [VERIFICATION.md](VERIFICATION.md) for exact evidence and its limits.

## Original event-tool demonstration

The original bounded demonstration is retained for regression coverage. It uses five real local calculation/assembly tools and a distinct workflow:

```powershell
python -m collective101 demo --inject-outage --inject-bad-cost
python -m collective101 revise MISSION_ID --provider fixture --budget 260 --capacity 35
python -m collective101 resume MISSION_ID --provider fixture
python -m collective101 report MISSION_ID
```

Its static HTML report and numerical acceptance checks remain available. The five event tools are not automatically callable from the new drafting harness. The earlier HTTP contract and Postman stand-ins remain historical request-verification assets; they were not used in the department implementation session. The maintained product roadmap is only in PROJECT_STATUS.md.

## Reviewed work, memory and evaluation

Mission chat is a conversation surface with a docked composer. It grows with input up to 200 px, then scrolls internally; manual resizing is disabled. Enter sends and Shift+Enter inserts a line. Runtime action labels appear in a separate status region, not transcript messages or model reasoning. Mission details and budgets are collapsed; full records remain under Activity. The composer stays visible while work runs.

Missions now allow `max_repair_rounds` from 0 to 2 (default 1). Rejected review or failed deterministic artifact/execution checks can trigger a fresh departmental revision. Heads receive the previous verdict and bounded artifact excerpts, assign corrections and refresh dependencies, and an independent reviewer checks the revision against unchanged criteria. Missing-capability task blockers do not trigger blind retries. Attempts retain separate artifacts, tool results, checks and model calls; Activity aggregates calls and shows the latest artifacts. Pause and human guidance apply to the active revision. All attempts share the original model/token/tool budget. A connector change invalidates repair access rather than silently granting a changed connection.

Under Organization, **Shared knowledge** accepts explicit UTF-8 TXT/MD/CSV/JSON uploads up to 64 KiB. Hash-prefixed filenames deduplicate matching imports without overwriting other files. Agents use their existing knowledge tools; uploaded documents are reference data and may be sent to the configured model when read.

Accepted same-agent/provider experience is consolidated into at most 50 exact-match memory cards with up to 20 source runs each; up to three relevant cards are retrieved and snapshotted per invocation. This is bounded recall, not model training or proof of learning. Raw historical evidence is retained.

Responsibility is advisory and visible in each agent's role inspector and in head assignment context. Three distinct live missions with independently accepted, deterministically checked contributions allow `trusted_contributor`; eight with no failures in the last five recorded contributions allow `senior_contributor`. Two recent failures return the recommendation to `developing`. Fixture/simulation runs, duplicate objectives, and mere file existence do not qualify. These levels do not change titles, reporting lines, tool permissions or budgets. No live agent has earned a level through the test suite.

For team routing, completed reviewed or blocked missions record the selected departments, outcome, provider identity and hashed objective terms rather than mission text. Before a live mission, Distribution receives up to three similar outcomes from the same model/provider configuration. A prior unaccepted team is an advisory signal to prefer a different useful shortlist; no department is automatically excluded. Results are attributed to the whole selected team, not to an individual department, and the Mission brief shows the evidence run IDs. Fixture/simulation evidence is retained for testing but never influences live recommendations. This is lexical matching and prompt guidance, not model training; similarity and recommendation quality have not been evaluated on live missions.

For employee assignment, department heads receive optional history for employees with prior **live, accepted tasks whose own artifacts passed deterministic content, static HTML, JavaScript or SQL checks**. Matching is lexical: hashed terms from the mission objective are compared with hashed terms from prior task titles/instructions. The lookup is bounded to recent evidence and returns up to three source run IDs; the Mission brief shows this evidence and the head's proposed assignment. Only positive verified work is stored for this purpose: a failed team mission is not used to label an employee, and a missing history means unknown. Heads still assign based on current task fit, skills, availability and permissions; history is advisory and does not change role, rank or tool access. Fixture/simulation evidence is excluded. No live assignment benefit has been measured.

### Additional checks

`sql_sandbox` runs a SELECT-only query over explicitly supplied JSON tables in an in-memory SQLite database. It denies attachments, writes, pragmas, system tables, extension loading and functions outside a small allowlist. Bounds: eight tables, 1,000 input rows, 200 output rows, query/result size and VM instruction/time limits. It does not connect to your databases and is not a general Python or OS sandbox. Eligible engineering/data/assurance/platform definitions can request it with mission and task grants.

A mission may declare `data_checks`: `[{"path":"data/query.sql","tables":{"sales":[{"amount":2},{"amount":3}]},"expected_rows":[[5]]}]` with `sql_sandbox` in allowed capabilities. The runtime executes the generated query and compares observed rows in order. `artifact_checks` also supports `{"path":"engineering/index.html","type":"html"}` for static language/title/main/heading/viewport/image-alt/duplicate-ID checks. These do not render a page or establish full accessibility.

### Live evaluation

After configuring the live model, run from this Desktop project:

```powershell
python -m collective101 --state .collective101/console.db evaluate --max-calls 80
```

This explicitly makes billable live requests. It uses isolated evaluation state under `work/evaluations`, reuses the actual intake prompt, tests four intake decisions and two specialist outputs, and compares a single specialist with departmental execution on the same three JavaScript checks. The JSON report records outputs, pass/fail evidence, latency, calls and reported tokens; answer accuracy, question relevance and role usefulness still need independent human review. The total call/token admission limit spans the evaluation, and failures never become fixture results. This small suite is not an evaluation of all 101 specialists or a dollar-cost estimate. Live evaluation was deferred by the user on 2 November; no live effectiveness result is claimed.
