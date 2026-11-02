# Collective 101 architecture

The living roadmap is [PROJECT_STATUS.md](PROJECT_STATUS.md). This document records implementation decisions and their consequences.

## Decision: individual definitions, shared execution

Accepted 31 October 2026, following the user's explicit organization design. Each of the 101 agents has a JSON definition under `collective101/departments/<department>/`. Department READMEs provide a human-readable directory. The registry validates exact identities and counts, one head per department, employee-to-head reporting and declared legacy capability limits.

Definitions hold job-specific prompts, responsibilities, specialty/skills, reporting line and memory namespace. A shared AgentHarness combines the agent instructions with role/phase rules, mission context and a structured response contract. The provider is injected through the existing `complete(messages, tools=None)` interface. These are independently addressable agent configurations, not separately trained models.

This gives editable individual roles without duplicating HTTP clients, persistence or security checks 101 times. Adding a skill label cannot create an executable permission. Per-agent model routing remains unimplemented.

## Decision: leadership-only interdepartmental communication

The Mission Director works through heads. Employees send results only to their head and receive assignments only from that head. Heads communicate with heads and the director. LeadershipBus enforces these edges in code and records each handoff with sender, recipient, kind and content. It rejects cross-department employee messages, employee-to-director bypass, and direct colleague conversations, including within a department. This keeps the first implementation's collaboration explicitly head-mediated.

The council passes leadership-authored proposals. A head collects employee outputs and forwards a department report plus published artifacts. The Assurance head delegates an independent review to an employee who did not produce any mission artifact. Review results return through the Assurance head to the director. Employees are not given a global conversation inbox.

## Department-led lifecycle

`ready -> running -> reviewed | blocked`

1. Validate a generic mission contract: objective, inputs, constraints, acceptance criteria, allowed capabilities and optional deterministic artifact checks.
2. Intake supplies a department shortlist (legacy JSON without one defaults to all heads). Ask those heads and transitively requested dependency heads whether they can contribute; require a justified contribution or decline. A contributing head proposes up to six owned tasks, employee assignments, required capabilities, output paths and dependencies.
3. Run one council round. Heads see peer proposals and revise or retain their scope to avoid duplication and declare dependencies.
4. The director selects a useful dependency-closed subset. Validate both department and intra-department DAGs.
5. Execute selected departments in dependency order. Heads brief their employees; each employee receives its task, own task dependencies and head-forwarded upstream reports.
6. The drafting harness invokes each assigned employee. It validates exact declared output files, records artifact provenance and hashes, and returns results to the head. Missing capabilities or blocked dependencies produce explicit blocked outcomes.
7. Heads aggregate progress, blockers and improvement ideas and publish reports to other participating heads and the director.
8. The Assurance head chooses an independent reviewer. Require explicit coverage of every original acceptance criterion. Run deterministic file existence/substring checks separately; a positive model verdict cannot override their failures or runtime blockers.
9. The director synthesizes the outcome and proposes bounded improvements with a responsible department, supporting observation and measurement. Proposals are recorded and routed to heads; they are not auto-applied policy changes.
10. Store recent reviewed agent episodes for later same-agent, same-provider recall. Fixture and live memories cannot mix through this path.

Chat consults only shortlisted/dependency heads. Each consulted head has an assessment and council turn; a council request for an unconsulted department fails explicitly rather than silently widening the team. Legacy JSON without a shortlist retains all-head consultation. Department execution is sequential; no efficiency or scalability claim follows from this design.

## Harness capability boundary

`draft_artifact`, scoped knowledge/memory tools, configured public web search and optional `javascript_sandbox` are installed in the departmental path. It accepts model-produced bounded text/code files; drafting itself does not execute source; explicitly declared JavaScript acceptance checks use the separate WebAssembly adapter. Outputs stay in the database until explicit export to an isolated run folder. Paths must be normalized relative paths, must avoid Windows reserved names, and cannot collide by case or file/directory prefix. Export checks resolved containment and refuses to overwrite differing existing files.

Model instructions describe unavailable operations explicitly: no host shell, deployment, external messages, plugin installation or MCP connection. Public web search is only available through the scoped adapter with configured credentials and exact-query human approval. A missing capability is an observable blocked state, not an implied grant. A future execution adapter can replace or extend this harness while preserving heads, ownership, validation and evidence. Neither the downloaded development skills nor the old event tools are wired into this new execution capability.

`reviewed` refers to artifact review plus any explicitly recorded sandbox checks. Only recorded org_executions or successful JavaScript org_tool_calls establish execution; the status alone cannot establish executed tests, deployment, external truth or usefulness on real missions. Free-form criteria receive model review; file checks provide only a narrow deterministic oracle.

## Persistence, resources and recovery

The original Store provides SQLite transactions. New `org_runs`, `org_calls`, `org_messages`, `org_artifacts`, and `org_experience` tables are additive and do not migrate or overwrite original event missions.

A run snapshots the mission and all agent definitions. Provider mode, model and endpoint must match on resume. Every phase reserves a call atomically, records its inputs, and validates its JSON response before caching it. Cached results are reused only when the agent/context hash matches. A phase has at most two failed/intervention attempts and four tool requests within an eight-call loop bound. A shared org_budgets record charges intake and mission provider requests before dispatch. UTF-8 input bytes plus a 4096 output allowance are charged as conservative token admission units. Failed/uncertain requests keep their reservation; provider-reported usage is recorded separately. No exact tokenizer or monetary billing ceiling is claimed.

CLI commands share the existing workspace lock. This is a single-process design; calling the library concurrently outside the CLI is not a supported scheduler. A process interruption between a provider response and its local commit may repeat that request on resume. No exactly-once provider guarantee is claimed. Source-code changes are not frozen with runs; only agent definitions and context are.

Message keys make leadership handoffs immutable on replay. Artifacts keep producer, task, path, content and SHA-256. Completed reviewed missions return without additional calls. Blocked results remain inspectable; resume reuses cached phases and does not invent new scope or refill exhausted attempts. Review-driven repair maps deterministic failures and reviewer-cited artifact paths to the owning task, then includes dependent tasks whose inputs may have changed. The original task plan is reused; unaffected task outcomes and artifacts are copied with source-run provenance, and a fresh independent review is required. Unmappable reviewer findings remain blocked rather than triggering a full blind rerun.

During execution, a department head can request one support response from a selected department whose work has not started. The target head can decline or provide at most 500 characters of passive insight for the mission record. The insight is recorded in the LeadershipBus response and mission result, but never passed to employees or applied to their tasks. Thus support cannot create phantom employee work or alter task instructions, assignments, tools, criteria or budgets. Invalid responses or provider failures leave the original plan intact. The call is synchronous and ends on the provider's timeout/retry behavior; there is no 48-hour waiting queue. The insight is advisory, not verified evidence or an instruction.

Memory ranks up to 100 prior reviewed records for the same agent/provider by lexical overlap with the mission and task, with recency as a tie-breaker; it supplies at most three. An explicit memory_search tool can query these episodes. Per-step memories are frozen from the first recorded input when resuming. Approved long-term reference files live under knowledge/shared and knowledge/<department>, accessed only through scoped read/search tools. Its content is untrusted historical context, not a policy update. Retrospectives are improvement hypotheses, not measured learning or automatic responsibility changes.

## Original event runtime

`runtime.Organization` remains the bounded five-tool event workflow: model planner, capability grants, local numerical artifacts, independent review plus deterministic calculations, bounded reassignment, and selective budget-subtree revision. It shares the validated roster, provider and Store primitives but uses its original tables and CLI commands. Its saved states and regression tests remain valid.

Keeping this workflow intact protects the previously verified tool boundary while the general organization layer develops. The next execution integration must connect real tool evidence to departmental work; merely passing draft files between agents does not replace that work.

## Development workflow source

The user-selected Addy Osmani skill repository is pinned and retained under `third_party/agent-skills`, with license and references. Relevant skills are read on demand; the upstream repository's AGENTS.md does not govern Collective 101. No global host-plugin installation or upstream hook/script execution occurred. See [third_party/README.md](third_party/README.md) for provenance and applied workflows.

## Mission control and execution increment (31 October 2026)

Authorized scope: extend the Desktop application with a loopback-only Bootstrap dashboard, mission chat, persisted clarification interventions, observable agent activity, and a JavaScript execution adapter. Live Meta calls are deferred at the user's request until they configure MODEL_API_KEY.

Implementation order: (1) isolated QuickJS/WebAssembly execution with immutable acceptance checks; (2) runtime evidence integration; (3) persisted intake/chat and local HTTP API; (4) Bootstrap department/agent/chat/activity interface; (5) browser and regression verification. All changes use the Desktop source.

Success criteria: JavaScript checks actually execute within time/memory limits without host APIs; failures block mission acceptance; chat can pause for missing intent and continue after answers; all 101 roles are browsable; activity displays persisted calls/handoffs/artifacts; malformed/cross-origin requests cannot start work; user text is rendered without executing HTML. Fixtures stay labeled. No cloud publication, arbitrary host shell execution or deployments are part of this increment.

Commands: `npm ci --ignore-scripts`, `npm run test:sandbox`, `python -m unittest discover -s tests -p 'test_*.py' -v`, `python -m collective101 serve --port 8765`. Modules stay under collective101, browser assets under collective101/web, sandbox runner under collective101/execution, tests under tests. Existing stdlib Python style and parameterized SQLite queries are retained. Execution and intake limits are enforced in code, not delegated to prompts.

## Implemented console and intervention boundaries

`web_server.py` serves a Bootstrap 5.3.8 UI and a small JSON API from loopback. Static routes are allowlisted; generated artifacts are returned as JSON/text, never served as executable pages. Host checks, per-process session tokens, same-origin mutation checks, request-size limits and CSP protect the local control surface. No credential values are sent to the browser.

`console.py` persists chats and intake rounds separately from mission execution. One background worker runs the organization; HTTP threads remain responsive for status and clarification answers. POST /api/chats uses a stable request_id to avoid duplicate submission; repeated keys with changed input are rejected. GET /api/organization lists definitions; GET /api/chats lists chats; GET /api/chats/{id} returns state/questions/brief; GET /api/activity/{run_id} returns recorded actions, handoffs, artifacts and executions. POST /api/chats/{id}/answers resolves a pending question; POST /api/chats/{id}/control pauses or resumes. Errors use JSON with an error string and an appropriate HTTP status.

The frontend renders runtime content with textContent. Artifact downloads use text blobs. The activity view exposes returned outputs, actions and observed evidence, not private model reasoning. Polling refreshes every 1.5 seconds; per-agent filters and expandable records make the history inspectable. CSS defines responsive layouts, but no actual-browser visual/accessibility pass has been completed in this session because browser control was unavailable.

An agent may return an intervention object instead of a phase result. The harness validates and persists the question, records the call as waiting, and raises a distinct pause signal. The run enters needs_input. An answer is scoped to that run/question, retained as untrusted human-provided mission context and included in the retried phase. Completed steps remain cached. The two-attempt bound still applies: repeated clarification by the same phase can exhaust it. Pause controls are checked before each phase and do not terminate an in-flight model request.

QuickJS 0.31.0 runs inside WebAssembly, hosted by a fixed Node script. User-generated source is evaluated only in the guest VM. No host functions or module loader are exposed. Each check gets a fresh guest runtime; expected primitives are compared in the trusted Node host. The Python adapter passes JSON over stdin, uses a fixed command, scrubs credentials/NODE_OPTIONS from the subprocess environment, applies an outer timeout, and validates the returned envelope. Source/check hashes prevent evidence replay against changed content. No claims are made about browser behavior, third-party integrations, or correctness beyond the declared checks.

Execution failures enter the independent review context and cannot be overridden by a positive review. org_executions, org_interventions, org_controls and console_chats are additive tables. Readiness distinguishes dependency availability and live-provider configuration; fixture and live modes remain explicit. The user deferred live inference until they configure their key.

## Decision: selective controller, tool broker and guardrails (1 November 2026)

The controller is an orchestration role outside the registered roster; it does not add a 102nd employee. Local replies cover exact greetings/help/thanks. One bounded live intake call can answer a self-contained question, ask focused questions, escalate a risk, or construct a mission with a shortlist. Fixture routing is explicitly scripted and is not a quality evaluation of classification.

`agent_tools.py` enforces identity + mission + assignment grants. Leadership phases get only read-only knowledge/memory tools, with mission permission. Worker/reviewer JSON `tool_request` responses are separate model turns whose results are persisted under immutable keys. Tools cannot install other tools or expand permissions. Heads receive observed tool evidence alongside employee outputs; Assurance receives it through head reports. Forty recorded requests per mission and four per step bound use. Denials and unavailable results are visible; optional failures remain limitations and essential missing evidence blocks work. Tool pauses participate in phase-boundary pause/resume.

The web adapter has a fixed HTTPS endpoint, no redirect following, ten-second timeout, bounded responses and five snippets. No arbitrary URL fetch or host browser is exposed. The org_web_approvals table binds an exact query hash to run, employee and persisted intervention. Approval of one query cannot approve a changed query or another employee/run. Failed network calls never synthesize sources. API keys stay in the adapter environment.

`guardrails.py` provides conservative preflight signals, supplemented by live intake classification. These signals are incomplete and do not establish content safety. Both chat and direct mission execution gate recognized risks before department calls. Human guidance narrows informational scope; it does not authorize external actions. Provider and tool failures block or produce explicit limitations. See GUARDRAILS.md for the concrete policy and regression cases.

`org_budgets`, `org_run_budgets`, `org_tool_calls`, `org_web_approvals`, `console_permissions` and `console_safety` are additive SQLite tables. Existing completed runs remain inspectable. Incomplete runs from older code can fail the strict context hash check and require a new mission; source-code migrations do not silently rewrite prior evidence.

## Superseding decision: live chat, agent-authored HITL and connectors (2 November 2026)

This decision supersedes the local-reply, keyword preflight and exact-query question behavior described in the 1 November history above. Every new chat message reaches distribution-001 through the configured live provider, with that identity's role prompt and conversation history. The model emits reply, clarify (questions plus reason), or mission (validated criteria/tools/department shortlist). There is no deterministic classification based on input shape. The intake is audited in console_intake_calls; runtime agents use the existing intervention object. Questions, authorship and answers persist; code validates/persists/pauses/resumes and enforces immutable permissions/budgets. Follow-ups to direct replies reuse the conversation. Demo submissions/resume are rejected; archived fixture chats are hidden without deleting their evidence. Tests inject scripted providers only through Python constructors, never through a product API option.

connectors.py adds a user-owned registry in the same local SQLite state. Model/search keys are encrypted by secret_vault.py using Windows DPAPI. The UI saves configuration, discovers MCP tools, selects server-declared read-only tools and departments, enables access and disconnects. Enabled dynamic tool names enter the catalog and head assignments, without a separate source adapter per server. Agent access remains an intersection of connector grants, mission permissions and head assignments. org_connector_bindings freezes a configuration fingerprint per tool/run. No external tool executes during discovery; only initialize/notifications/ tools/list are sent.

mcp_client.py supports Streamable HTTP JSON and bounded SSE responses, lifecycle negotiation (2025-03-26/2025-06-18/2025-11-25), sessions and paginated tools/list plus tools/call. It uses fixed operator URLs, DNS address validation/pinning, TLS hostname validation, no redirects, bounded results and timeouts. HTTPS is required except explicitly enabled loopback HTTP. Server metadata is untrusted; readOnlyHint is not an external-side-effect guarantee. OAuth, stdio, write tools and complete local JSON Schema validation are not implemented. No schema references, returned resource links or remote instructions are executed.

New UI route /connectors and API /api/connectors expose redacted metadata and save/discover/enable/disable operations under the existing local session/origin checks. Model readiness only means configuration is present. A failed live provider call stays failed; no fixture or greeting fallback exists. The health version is 0.3-live-connectors to identify stale server processes.

The reproducible UI command runs tests/run_ui.py, which starts an isolated loopback service with ChatTestProvider, runs jsdom tests, and stops its own service. It cannot spend real model credits or mutate the user's running app. Test fixture behavior is not live model quality evidence.

## 2 November 2026: connector catalog and shared availability

This decision supersedes the earlier department-selectable connector grants. The Connectors page uses a searchable nine-card catalog: six clearly labeled Coming soon service previews, plus functioning Live model, Web search and Custom MCP setup. The supplied screenshot informed the search-first hierarchy, compact icon/name/description cards and explicit availability badges. The existing teal/light workspace palette is retained. Cards collapse from three columns to two to one; setup opens inline from a card with focus placement, Escape/close return, visible labels and no department dropdown. Search/filter empty states and request failures are explicit. Planned adapters never expose a connect action.

The existing connector registry remains the source of configured connections. Legacy department scope is normalized to the organization on registry initialization without touching credential ciphertext; changed MCP fingerprints block previous mission bindings. All 101 registered identities can see enabled MCP tools and configured Brave Search. Employee execution still intersects mission capabilities and head-assigned task tools; leaders may request the enabled read-only connectors within mission scope. Built-in local knowledge and sandbox policies stay separate. No new third-party service adapter, OAuth flow, write operation, account connection or background external call is introduced.

## 2 November 2026: reviewed work and chat activity

`progress.py` persists public action metadata at actual model/tool/check boundaries. Console chat exposes the latest active-revision label; the browser renders it in a separate polite status region. The transcript has independent change detection to avoid repeated log announcements. Chat uses a scrollable thread and a docked, auto-growing input; settings and mission details are disclosures rather than a permanent sidebar.

`repairs.py` wraps the existing cycle in bounded revisions, each retaining an immutable run ID and snapshot. A shared root budget covers all requests and tools; original model signature, capability grants and connector fingerprints are preserved. Each repair targets tasks owning failed artifact paths and their dependency closure; accepted unrelated outcomes/artifacts are reused with provenance, not rewritten. If an independent reviewer does not identify an artifact for an unmet criterion, the run stays blocked for human review. Every repair gets a fresh independent review. Console questions and progress resolve the effective revision, while activity aggregates attempts and exports use latest artifacts. The original cycle's cache remains responsible for idempotent phase replay; revisions use fresh keys in their own run.

For in-progress collaboration, heads can issue one recorded support request to a still-pending selected department. The target may decline or return a capped passive insight. The insight is recorded only; it is not routed to employees, so it cannot change their work. Failed or invalid optional responses are recorded and the original plan continues. The shared budget covers the additional model call, and normal pause/intervention/resume handling applies. This does not support introducing new departments or reassigning completed/active work.

`learning.py` consolidates reviewed episodes without generating new factual claims and records contribution outcomes separately from roles or execution grants. Head candidate context and the role inspector expose advisory responsibility levels. `knowledge.py` ingests explicit shared text documents with size/path/link checks and content-hash naming. `data_execution.py` adds SELECT-only in-memory SQL; `html_checks.py` provides non-executing document checks. `evaluations.py` reuses console intake messages and runs bounded specialist/team comparisons in isolated state; no live result exists until explicitly executed with a configured provider.
