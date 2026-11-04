# Collective 101

Main project: `C:\New folder\Desktop\collective101`.

An AI organization with **101 individually configured agents: one Mission Director, ten department heads and ninety employees**. Heads decide whether they can contribute, coordinate with other heads, assign their own employees, collect results and report to the director. The runtime enforces the reporting hierarchy.

Read [PROJECT_STATUS.md](PROJECT_STATUS.md) for the living aim, verified status, limitations and next work. [AGENTS.md](AGENTS.md) governs project maintenance. Browse [all departments and agent files](collective101/departments/README.md).

The organization produces and reviews code/text artifacts and can now execute **pure JavaScript acceptance checks in a QuickJS/WebAssembly sandbox**. Eligible agents can also read/search approved knowledge, recall reviewed episodes, and request configured public web search. It can connect compatible remote MCP tools through the Connectors tab. Eligible agents can preview saved static projects in isolated Chromium. Python/Node runtime checks require a configured offline Docker profile; the current machine has no such runner. Deployment remains unavailable. The included fixture demonstrations exercise the real organization control flow with scripted model responses; they do not perform AI inference.

## Structured-output recovery (0.13)

Meta-backed phases use automatic native result submission and a matching strict JSON-content fallback. Assigned files travel as literal file fields; the runtime owns their paths. Internal organization messages remain structured, while users see readable replies. Invalid results stop with sanitized diagnostics; raw rejected output and secrets are not logged. A blocked validation step may receive an explicit **Retry** after a protocol correction, preserving previous calls, usage and completed steps. There is no automatic replay of historical failed chats. Cyclic department prerequisites receive bounded head-led correction before work starts.

The recovered seven-file RAG example in the existing chat is an offline TF-IDF demo with a browser-tested frontend and **unexecuted backend source**. Download its ZIP from the chat and follow engineering/README.md. Open Preview to try the frontend's local fallback. A Preview pass does not prove backend API execution.

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

Pause takes effect before the next agent phase. A running provider call is allowed to finish. Resume is explicit after a server interruption. Repairable quality failures receive bounded head-led correction; unavailable essential capabilities remain blocked. Failed histories are never silently replayed.

This server binds only to `127.0.0.1`. Mutation endpoints require the local session token and same-origin requests. It is a single-user development application, not a public production server. Stop it with Ctrl+C in its terminal. Configure live keys in Connectors (Windows DPAPI-encrypted) or the server process environment; environment changes require a restart.

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

The existing Meta chat-completions adapter never falls back to fixtures. Provider/model/endpoint provenance is retained. Active chats and departments have no aggregate API-call or token spending ceiling at the user's request. Counters still record requests, conservative serialized-input/output reservations and provider-reported tokens; zero in stored allowance fields means unlimited. Usage is not reset when a chat is migrated. Cancellation, permissions, request/context limits and bounded recovery remain. Positive finite allowances are retained for historical/programmatic test compatibility; the normal UI has no spending-limit controls.

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
npm.cmd run test:sandbox
# Starts an isolated local service with an injected test model; no real API spend:
npm.cmd run test:ui
# Real Chrome through Playwright MCP, disposable state and scripted model:
npm.cmd run test:browser
# Read-only page inspection of the running app on port 8765:
npm.cmd run browser:inspect
```

### Playwright MCP for development

The official `@playwright/mcp` server (0.0.84) and MCP SDK (1.32.2) are pinned in the npm lockfile. Run `npm.cmd ci` after cloning; Node 24 and installed Google Chrome were used for verification. No browser download is needed on this machine. The server launches on demand over stdio with headless, isolated Chrome and closes when each command finishes.

`test:browser` starts its own ephemeral loopback server and disposable SQLite state, injects the scripted test provider, and checks layout, greeting, activity hints, clarification/resume, organization and connector navigation. It does not target your running app or call a paid model. `browser:inspect` reads `/chat` and `/connectors` on `http://127.0.0.1:8765`, waits for application readiness and saves screenshots, snapshots and metrics under ignored `work/playwright/`. To inspect another local port, set `COLLECTIVE101_BROWSER_URL`. Inspection may record visible mission/connector names; keep these local artifacts private.

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

### Chat workspace and source delivery

Chat uses a collapsible navigation rail with **New chat** and readable saved-chat titles. The conversation has no workspace bar, visible status badge or redundant chat heading. A top-right **Files & activity** panel contains saved source files, line counts, additions/removals across revisions, diagnostics, plan/limits and pause/resume controls. Status text and elapsed time below the conversation reflect recorded runtime actions; they are not model reasoning. The composer stays docked and grows to 200 px.

Open any saved file to inspect its source as plain text, or use **Download ZIP** to retrieve all files saved so far, including partial work. The ZIP preserves department folders, merges previous builds/repair files by path with the newest version winning, and includes a provenance/status manifest. Open `engineering/index.html` after extraction for a static website. Generated HTML is never executed inside the console. Archives contain source artifacts only, not databases or credentials; session authorization, normalized paths, case/prefix collision rejection and a 20 MiB export bound apply. Counts measure saved lines/revision diffs, not keystrokes or tokens. Existing files absent from a partial repair are retained.

For a build, Distribution declares `delivery_type` and concrete department-owned `deliverables`. Website delivery requires Engineering and an engineering-owned HTML source path. The owner's head must assign that file, the Director must retain its owner in the team, and deterministic HTML checks require the actual source even if the model reviewer approves. Supporting plans alone cannot satisfy the declared delivery. `draft_artifact` is built-in JSON file output, not a missing external tool; heads receive persisted file hashes.

Published paths include the department (`engineering/index.html`); task outputs and worker artifact paths use the relative filename (`index.html`). Version 0.7.1 accepts either equivalent form for the same department and normalizes it once before assignment/delivery checks. Duplicate aliases, unsafe paths and missing or genuinely different deliverables are still rejected. Heads also receive explicit `required_outputs`. Future rejected planning records retain bounded attempted-path metadata and the validation reason in Activity, without saving invalid files as completed work. Older failures whose candidate outputs were not recorded cannot be reconstructed retroactively.

An upstream head's soft integration concern does not automatically suppress downstream employees. Explicit failed local task dependencies and essential missing tool permissions remain blockers. After all departments finish, heads with soft concerns receive one bounded reconciliation pass with completed peer files; fulfilled handoffs can be cleared. Actual runtime task failures cannot be erased. Repairable quality/dependency failures may then enter the existing correction rounds under the original criteria and shared budget. True missing capabilities remain blocked without blind retries.

You can send follow-ups to completed or blocked chats. The original conversation, prior file excerpts, diagnostics and shared budget remain available to Distribution; a new build starts only if the model decides to create it. Full chat history remains in SQLite. Per request, up to 3,000,000 UTF-8 bytes of conversation are considered. Large Meta requests use the documented token-count endpoint with output space and an 8,192-token format margin reserved. If needed, the runtime preserves the complete latest intent, initial request and labeled earlier user excerpts while fitting older history. Full originals remain saved. These excerpts are incomplete reference, not lossless semantic memory. Source context supplied to a continuation is explicitly bounded and labeled if truncated.

| Active application limit | Value |
| --- | ---: |
| User message | 500,000 characters |
| Serialized model input | 4,000,000 UTF-8 text bytes per request |
| Chat-history window sent | 3,000,000 UTF-8 bytes |
| Default work generation allowance | 65,536 tokens; 131,072 on truncation recovery |
| Default generation ceiling | 131,072 tokens, including reasoning |
| Default work timeout / retry maximum | 600 / 900 seconds |
| Aggregate API-call / admission spending ceiling | Unlimited; usage recorded |
| File content | 80,000 characters per artifact |
| Correction rounds | 1 default, 2 maximum |

Input admission units are conservative byte-based accounting, not exact token counts. Meta documents a 1,048,576-token Muse Spark context window; the app uses its own text transport guard and provider token measurement for large requests. Transport bytes and tokens are different units. See [Meta long-context guidance](https://dev.meta.ai/docs/cookbook/long-context). Provider failures, truncated output and invalid agent output have separate limits (3 / 2 / 2) and twelve total requests per step; no indefinite retry loop exists. Chat's Plan and limits section shows current values and saved-history usage.

**Temperature** is now optional in Connectors → Live model → Model request limits, or via `MODEL_TEMPERATURE`; allowed values are 0–2, default 1.0. It controls sampling, not agent training or orchestration correctness. All agent phases now request **high** reasoning, including intake, work, reviews and retries. Meta recommends the default temperature for Muse Spark; see [Chat Completions parameters](https://dev.meta.ai/docs/protocols/chat-completions).

Refresh the console after an update. A frontend connected to an older backend disables new submissions and asks for a restart, preventing requests from silently using outdated delivery logic. Version **0.8-static-preview** adds local website previews. Automatic dependency installation, full-stack runtimes and deployment remain outside this local drafting harness.


### Attachments and specialist conversations (4 November 2026)

Chat now accepts text/Markdown/CSV/JSON and source files, DOCX, PDF, PNG/JPG/JPEG/WebP/GIF, and WAV/MP3 audio. The browser can also decode supported M4A/OGG/WebM files and converts audio/recordings to mono 24 kHz 16-bit WAV. Use the paperclip menu to choose **File**, **Folder** or **Photo**, or use the microphone to record, stop, replay and send. Images show thumbnails before and after Send; select a sent image to enlarge it. Voice uses play/pause, seeking and time before and after Send. Polling preserves existing playback. Folder paths are retained; private, hidden, cache and unsupported files are skipped with feedback. Voice-only sends ask the organization to respond to the spoken request. Leaving chat cancels capture. File validation errors are shown before sending.

Uploads are stored locally until Send. Supplied text and DOCX are read locally; images/PDFs are interpreted by the configured Meta model, and WAV uses `muse-voice-transcribe-1.0` on `/asr/transcribe`. Native MP3 uses Spark 1.2 because Meta documents degraded Spark 1.3 audio understanding. These use the existing saved Meta key and endpoint; model access can still depend on the account. No second key was needed in live image/PDF/voice tests. This implements understanding/transcription, not generated images or synthesized voice replies. Originals remain available through authenticated attachment downloads; media never executes on the console origin.

Technical bounds: 25 MiB per file, 50 MiB per turn, 400,000 extracted UTF-8 text bytes per document, and up to 200,000 bytes of current attachment source excerpts (newest first). Excerpts and model interpretations are explicitly attributed and incomplete where applicable. Meta PDF input covers at most the first 100 text pages and first 50 visual pages. Important facts require verification; uploading does not make a file trusted policy. Failed historical files are not automatically reprocessed on unrelated follow-ups. These are transport/context safeguards, not spending quotas.

Organization ? department ? agent now shows responsibilities, reporting relationships and available capability count. **Chat with this agent** opens a persistent, role-specific advisory conversation; **Ask the organization** starts a fresh organization chat with the relevant request for coordinated execution. Direct conversations do not run tools, assign employees or claim saved output. The selected specialist handles direct follow-ups; ordinary organization chat continues through Distribution and relevant heads. Operational accepted experience and role instructions remain separate from per-chat history; saved memory is not model training.

Live evidence includes document/image/PDF/voice understanding, a 990,270-byte high-reasoning request (162,212 measured input tokens; 65,536 output allowance), and a fresh 10-call, five-identity organization run producing a reviewed 245-line grocery website. Mobile browser checks support an explicit bounded viewport per check; final head reconciliation receives completed execution evidence before independent acceptance. This scoped result does not establish general production app reliability.

### Preview generated websites

Open a chat, expand **Files & activity**, then select **Preview ↗** beside Download ZIP or beside an HTML file. A new browser tab opens on a separate loopback port, selects `engineering/index.html` when available, and offers other saved HTML pages in a Page selector. No ZIP extraction or terminal command is required. If a popup is blocked, use the **Open website preview** link shown in the file panel.

The preview shows saved static HTML/CSS/JavaScript, including partial work. **Refresh** reloads the latest saved files; **Auto-refresh** checks for saved revisions every two seconds while the preview tab is visible. Turn it off to keep the current view while agents work. No HTML yet means a disabled Preview button with an explanation. A build-dependent project without HTML is identified as needing a build/runtime. A visible page is not proof of acceptance or browser quality verification by the organization.

Relative local assets and inline interaction scripts are supported. Root-relative URLs (such as `/styles.css`), CDN resources, network-backed features, server routes and unbuilt JSX/TSX need adaptation or a future runtime. External resource loads, fetch/WebSocket connections and form submissions are restricted. Generated documents run in an opaque-origin sandbox inside the preview; they cannot access the console or preview toolbar. No shell, package install, environment key, host file or external write API is exposed. Preview URLs are local bearer links: keep them private and reopen Preview after a server restart. Up to eight distinct chat previews and 20 MiB of saved files per preview are admitted.

Chat completions use a short agent-authored `user_summary` when available, with a readable fallback for older results. Failed runtime checks override positive prose. Assistant replies render Markdown paragraphs, lists, emphasis, links, code and tables; user input remains plain text. Markdown files open in **Preview**, with a **Source** tab showing exact saved text. The file viewer has no fingerprint/details section; integrity hashes and review records remain internal. Successful replies no longer carry a prior turn's error banner. No extra model request rewrites historical messages.

Markdown uses locally served, pinned Marked 18.1.3 and DOMPurify 3.4.17 bundles under `collective101/web/vendor`, with their licenses retained. [Marked recommends sanitizing its output](https://marked.js.org/using_advanced); the console uses a restricted tag/attribute allowlist, inert raw HTML, no remote Markdown images and safe link protocols. This renders documents; executable website Preview remains separately isolated. Source/downloads preserve original content.

### Model configuration and request reliability

Connectors shows the active model, endpoint host, credential source (**Server environment**, **Saved connector**, or missing), settings source and request limits. Chat also identifies the model/source. `MODEL_API_KEY` injected by a secrets manager is detected as a server-environment credential; the app cannot identify the supplying extension. A saved connector key takes precedence over an environment key. Disconnecting a saved model prevents environment fallback until enabled again. Credential presence does not test authentication, connectivity or available credits, and keys are never returned to the browser.

Live model setup includes optional **Model request limits**. Defaults: a 131,072-token generation ceiling and a 600-second work-request timeout. Blank settings inherit `MODEL_MAX_OUTPUT_TOKENS` / `MODEL_REQUEST_TIMEOUT_SECONDS` or defaults. Supported settings are 1,024-131,072 tokens and 10-900 seconds. The output allowance includes reasoning; a higher maximum does not force the model to use it.

| Phase | Initial generation allowance | Initial timeout | Reasoning effort |
| --- | ---: | ---: | --- |
| Intake | 16,384 | Configured timeout (600 seconds by default) | High |
| Employee work | 65,536 | Configured timeout (600 seconds by default) | High |
| Leadership and review | 32,768 | Configured timeout (600 seconds by default) | High |

Initial allowances are clamped to the operator ceiling. A truncated response is rejected in full; recovery doubles its allowance up to 131,072 and increases the deadline. Transport failures also increase the deadline, with short bounded backoff, to at most 900 seconds. Three provider/transport failures, two truncated responses, two invalid outputs, or twelve requests stop a step; authentication/non-retryable errors stop immediately. Four tool turns per step and permission/execution guards remain. Aggregate call/token spending is unlimited. Intake retries now receive the exact validation error from that conversation turn.

Every retry reserves request bytes plus its actual generation allowance before contacting the provider. Truncated and malformed responses retain valid reported usage; timeouts with unknown usage retain their conservative reservation. Retry state and request options persist with call records, and Activity shows the failure category and request limits. No partial result becomes a completed artifact. Intake follows the same policy. The evaluation meter also accounts for actual request allowances. A larger per-request cap can use more credits; these limits are admission controls, not dollar-cost estimates.

The adapter uses Chat Completions `max_completion_tokens` and explicit reasoning effort. Meta documents that reasoning consumes the same generation budget as visible output; see [Chat Completions](https://dev.meta.ai/docs/protocols/chat-completions) and [reasoning](https://dev.meta.ai/docs/reasoning). JSON-agent requests use buffered SSE streaming with observed usage and a complete finish marker; native tool protocol requests retain JSON transport. Partial streams never become accepted files. Provider-side time limits and outages can still stop a bounded attempt. Restart the local server through the same secrets-manager launch configuration after code changes, then refresh the page. Failed historical missions are not automatically relaunched.

Mission chat is a conversation surface with a docked composer. It grows with input up to 200 px, then scrolls internally; manual resizing is disabled. Enter sends and Shift+Enter inserts a line. Runtime action labels appear in a separate status region, not transcript messages or model reasoning. Mission details and budgets are collapsed; full records remain under Activity. The composer stays visible while work runs.

Missions now allow `max_repair_rounds` from 0 to 2 (default 1). Rejected review or failed deterministic artifact/execution checks can trigger a fresh departmental revision. Heads receive the previous verdict and bounded artifact excerpts, assign corrections and refresh dependencies, and an independent reviewer checks the revision against unchanged criteria. Missing-capability task blockers do not trigger blind retries. Attempts retain separate artifacts, tool results, checks and model calls; Activity aggregates calls and shows the latest artifacts. Pause and human guidance apply to the active revision. All attempts share the original model/token/tool budget. A connector change invalidates repair access rather than silently granting a changed connection.

Under Organization, **Shared knowledge** accepts explicit UTF-8 TXT/MD/CSV/JSON uploads up to 64 KiB. Hash-prefixed filenames deduplicate matching imports without overwriting other files. Agents use their existing knowledge tools; uploaded documents are reference data and may be sent to the configured model when read.

Accepted same-agent/provider experience is consolidated into at most 50 exact-match memory cards with up to 20 source runs each; up to three relevant cards are retrieved and snapshotted per invocation. This is bounded recall, not model training or proof of learning. Raw historical evidence is retained.

Responsibility is advisory and visible in each agent's role inspector and in head assignment context. Three distinct live missions with independently accepted, deterministically checked contributions allow `trusted_contributor`; eight with no failures in the last five recorded contributions allow `senior_contributor`. Two recent failures return the recommendation to `developing`. Fixture/simulation runs, duplicate objectives, and mere file existence do not qualify. These levels do not change titles, reporting lines, tool permissions or budgets. No live agent has earned a level through the test suite.

### Additional checks

`sql_sandbox` runs a SELECT-only query over explicitly supplied JSON tables in an in-memory SQLite database. It denies attachments, writes, pragmas, system tables, extension loading and functions outside a small allowlist. Bounds: eight tables, 1,000 input rows, 200 output rows, query/result size and VM instruction/time limits. It does not connect to your databases and is not a general Python or OS sandbox. Eligible engineering/data/assurance/platform definitions can request it with mission and task grants.

A mission may declare `data_checks`: `[{"path":"data/query.sql","tables":{"sales":[{"amount":2},{"amount":3}]},"expected_rows":[[5]]}]` with `sql_sandbox` in allowed capabilities. The runtime executes the generated query and compares observed rows in order. `artifact_checks` also supports `{"path":"engineering/index.html","type":"html"}` for static language/title/main/heading/viewport/image-alt/duplicate-ID checks. These do not render a page or establish full accessibility.

### Live evaluation

The Effectiveness page and its navigation entry were removed on 4 November at the user's request. Developer evaluation services, CLI commands, historical trials and human-review provenance remain intact; no new benchmark is scheduled automatically. The initial roles-v1.0 set contains 23 cases covering 15 identities. This is limited evidence, not proof of all 101 identities. See PROJECT_STATUS.md and the dated verification reports.

Scorecards distinguish untested, insufficient evidence, meets benchmark and needs improvement. The initial published policy requires at least nine graded live trials over three distinct cases, a descriptive 95% Wilson lower bound of at least 80%, and no recorded critical failure. If the upper bound is below the target, the verdict is needs improvement; inconclusive evidence stays unrated. Repeated trials are correlated, so this interval is descriptive rather than a general statistical guarantee. Human-pending output, provider failures and unavailable runtimes are excluded from quality rates. The small suites do not establish all-role capability or security certification. File/protocol fixture passes do not count toward the score.

Compare specialist/generalist output, memory off/on, or the departmental team on the addition case. Select any/all registered cases (currently 23) with Select all/Clear; the selector shows the finite planned trial count. Departmental team mode requires the addition case alone. Trials and batches have unlimited aggregate API-call/token spending by default, and the UI has no spending controls or repeat-count ceiling. Stop prevents queued work and drains in-flight work. Four workers execute independent trials, each with separate usage accounting; the request/retry/sandbox protections remain. The evaluator distinguishes complete, pending-review, failed, cancelled and legacy budget-limited outcomes. Model/role/case/settings/memory snapshots and a new harness fingerprint separate this release from earlier capped runs. Memory arms do not train on benchmark answers. Human-pending output remains unrated, and neither repetition nor a benchmark pass automatically promotes an agent.

Under Reviewed memory, propose a structured lesson using its agent ID and a recorded source run from Activity. A different agent/model's evidence is rejected. Lessons carry situation/action/outcome/limitations, start proposed, require a human evidence note to approve, expire after 90 days, and can be revoked. Approval permits reference retrieval; it does not prove benefit or change model weights. Director improvement hypotheses appear as proposed experiments with their evidence and measurement plan; they never rewrite roles, prompts or permissions automatically.

### Departmental concurrency and compatibility

New console work defaults to two dependency-ready jobs at a time. Set `COLLECTIVE101_CONCURRENCY` from 1 to 4 before starting the server. Policy is stored per run and preserved across repairs; older runs without a policy retain serial behavior. Department/task dependencies, leadership-only handoffs, unique source ownership, shared request budgets, independent review and bounded retries remain enforced. Tool admission is reserved atomically before dispatch so parallel requests cannot exceed the shared execution cap. An incomplete recorded dispatch is not silently repeated.

The canonical engine is `department_runtime.py`, using the shared scheduler/policy in `runtime_core.py`. The older event-planning engine lives under `legacy/runtime.py`; `runtime.py` keeps compatible imports for earlier callers and CLI commands. Historical databases/readers and existing commands remain supported. This isolates legacy maintenance; it does not claim that both engines have already been fully merged.

### Browser, Python and Node execution adapters

`browser_sandbox` can check supplied static files in isolated system Chrome on Windows, using Playwright from the workspace's full `npm ci --ignore-scripts` installation. It does not use your personal browser session. Generated HTML stays inside the preview's opaque-origin iframe; requests are limited to that ephemeral preview, downloads/service workers are disabled and arbitrary navigation/evaluation is not exposed. A Windows Job Object owns the process tree, with a 1 GiB committed-memory cap, a 30-second outer deadline and bounded output. The Chrome renderer sandbox stays enabled. This is static project checking, not unrestricted browsing or an OS/container guarantee.

Assignments need the normal identity, mission and head grants. A mission can independently require saved-file checks, for example:

```json
{
  "allowed_capabilities": ["draft_artifact", "browser_sandbox"],
  "browser_checks": [{
    "path": "engineering/index.html",
    "checks": [{"selector": "h1", "contains": "Shop"}, {"selector": "#menu", "action": "click"}]
  }]
}
```

This is a fragment to add to a complete mission contract. Checks support click/fill, contains/equals text, visibility and element count. Observed failed checks override a positive model review and participate in the existing bounded repair path. Browser execution evidence is cached against exact saved inputs; a human preview alone is not such evidence.

`python_sandbox` and `node_build_sandbox` have fixed offline Docker profiles. They require a local Linux Docker engine and operator-supplied digest-pinned images in `COLLECTIVE101_PYTHON_IMAGE` / `COLLECTIVE101_NODE_IMAGE`. Docker is not installed on the current machine, so these adapters report unavailable; real container execution has not been verified. There is no host-code fallback or automatic image pull. The Node image must already contain project dependencies, optionally at `/opt/collective101/node_modules`; builds use offline npm and return bounded text output. The initial Python profile runs an isolated standard-library entry script. These profiles do not provide general full-stack hosting or install dependencies from the network.

Container commands drop capabilities, run as UID 65534, disable networking, use a read-only root/input, bound memory/CPU/processes/tmp space and clean their uniquely named container after success/failure/timeout. Only supplied text files enter a temporary workspace; host/project files, API keys, Docker sockets and user-selected commands are not mounted. Python acceptance may declare `runtime_checks` with profile `python`, a `.py` path and exact `expected_stdout`; offline Node checks use profile `node_build` and a `package.json` path. The relevant sandbox capability is required. Runtime readiness is configuration presence, not proof that the image/daemon/build works.

### Search response recovery

The recorded Bukit Jalil failure occurred before any Brave request: research returned two answers that failed JSON parsing, with zero tool calls recorded. Rejected raw content was not retained, so its exact form cannot be reconstructed. Muse requests now use Meta's documented JSON-schema output mode for structured responses; native legacy function-call requests keep their existing protocol. Blank answers are retryable `empty_output` provider failures with usage retained. Non-JSON responses get actionable JSON/tool-request feedback and bounded shape/position/digest diagnostics, without saving raw rejected text. BOM/JSON fences are handled; partial JSON and prose surrounding JSON remain rejected. Retries/budgets were not enlarged and old failed chats are not automatically replayed. See [Meta structured output](https://dev.meta.ai/docs/cookbook/structured-output).

### CLI evaluation compatibility

After configuring the live model, run from this Desktop project:

```powershell
python -m collective101 --state .collective101/console.db evaluate
```

This explicitly makes billable live requests. It uses isolated evaluation state under `work/evaluations`, reuses the actual intake prompt, tests four intake decisions and two specialist outputs, and compares a single specialist with departmental execution on the same three JavaScript checks. The JSON report records outputs, pass/fail evidence, latency, calls and reported tokens; answer accuracy, question relevance and role usefulness still need independent human review. Aggregate spending is unlimited by default; request/permission/retry safeguards remain, and failures never become fixture results. This small suite is not an evaluation of all 101 specialists or a dollar-cost estimate. The 4 November live comparisons and feature smoke tests are documented with their actual scope in VERIFICATION.md.


### Organization assistance and retrieval (0.12, 4 November 2026)

A worker can ask its own head for help from another department. Its head approves or declines, consults the named head, then returns attributed guidance to the worker. Employees never contact another department directly. If work needs a new workstream or a concrete approach correction, the Director can approve an immutable plan revision. It preserves the objective, original departments, deliverables, acceptance criteria, checks, connector bindings and permissions. Existing source is supplied as reference; new work receives fresh independent review. At most two head-help requests per step and two plan revisions per root prevent loops. Human questions and operator pauses retain priority. Review-driven repairs also remain available.

All 101 definitions now have department-specific working methods, specialty checks and richer role instructions. The small set of control roles enforces hierarchy and authorization; `specialty` describes individual expertise. Prompts and structural tests do not establish all-101 live competence.

Approved knowledge and reviewed memory use local hybrid keyword/embedding retrieval. It matches related meaning as well as words, within the existing agent/provider/department/review boundaries. It does not train the model. This installation has **BAAI/bge-small-en-v1.5** configured (English, 384 dimensions); no embedding API key is required. A clean source installation can enable it explicitly:

```powershell
python -m pip install -e ".[semantic]"
python scripts/setup_embeddings.py
python scripts/setup_embeddings.py --check
```

The public model is downloaded during setup; chat execution uses local files only. If missing or disabled with `COLLECTIVE101_EMBEDDINGS=off`, keyword retrieval stays available. Local model weights and knowledge are intentionally excluded from source archives. Relevance gains are not proof of improved task performance; held-out comparisons remain necessary.

### Complex source projects and clean distribution

A source-only backend project can be delivered through **Download ZIP**, including entrypoints, manifests, tests and setup instructions. This does not mean the backend ran. Declared HTML receives automatic isolated Chromium smoke checks when the browser adapter is ready, including HTML in a backend MVP. Python source is parsed for syntax and JSON for valid structure without importing or executing generated code. Backend execution still requires the configured offline, digest-pinned Docker profiles; no host execution fallback exists.

Build a distributable project archive with `python scripts/package_source.py`. The default is `dist/collective101-source.zip`. This allowlisted archive excludes databases, connector settings, uploaded files, run exports, caches, dependencies and embedding weights. It includes the current source, setup instructions and status. Do not zip the entire live workspace. The 0.12 release replaces the older Desktop archive that included runtime state. Saved connector secrets remain encrypted in the private live database, which is never distributed.
