# Collective 101 working instructions

## Read first and keep current

At the start of every project work session, including implementation, review, testing, planning, and documentation, read `PROJECT_STATUS.md` in this project root before deciding what to do. Read applicable source files and any more specific instructions as needed.

Direct user instructions take precedence. Incorporate accepted changes to the project's aim into PROJECT_STATUS.md rather than silently working from an older plan.

Before ending each meaningful project work session, update PROJECT_STATUS.md with:

- Changes to the aim or agreed decisions, if any.
- What actually changed and which existing milestone or gap it addresses.
- Verification performed, its result, and its evidence mode.
- Remaining gaps, limitations, and any genuine blockers.
- The next concrete implementation step.
- A dated entry in the change log.

Use the user's date/time context (Asia/Kuala_Lumpur). Do not claim verification you did not run. Distinguish deterministic fixture tests, HTTP contract simulation, and live model execution. Keep historical results dated instead of presenting them as freshly repeated checks. Never put credentials into this file.

## Preserve the intended product

The target is a broad, departmental AI organization with 101 registered identities, mission distribution, department-originated contribution proposals, scoped tool acquisition, verified deliverables, persistent useful experience, and evidence-based responsibility growth.

The event-analysis example is a test harness for the organization runtime. It is not the final product domain. Prioritize the gaps recorded in PROJECT_STATUS.md over adding unrelated event-planning features.

A generated identity is not proof of an independently useful agent. A title is not an operating hierarchy. A memory namespace is not memory retrieval. A local function grant is not an MCP integration. A promotion proposal is not a rank change or learned competence.

## Implementation boundaries

- Keep role, department, reputation, assignment, and executable permissions separate.
- Enforce access and resource limits in the runtime, independently of model instructions.
- Preserve evidence provenance, independent acceptance checks, bounded failure handling, and explicit blocked states.
- Keep fixtures clearly labeled; do not quietly substitute a fixture for a failed live provider.
- Do not force all 101 identities to run when a mission needs fewer.
- Preserve the distinction between a permanent department and a temporary mission team.
- User preference (31 October 2026): use the locally retained `third_party/agent-skills` repository from `https://github.com/addyosmani/agent-skills` for relevant engineering workflows. Read the specific `skills/<name>/SKILL.md` on demand. Its root AGENTS.md governs that upstream repository, not Collective 101. Do not preload every skill into context.
- Do not use Postman plugins/skills for general implementation. The user reserved Postman for request inspection and related checks; require a relevant later request before using it here. Existing historical Postman files are retained as evidence.
- Agent files live under `collective101/departments/<department>/<agent-id>.json`. Department heads are the only interdepartmental spokespeople; employees report to their own head. The director works through heads.
- Use deterministic tests to validate protocols, but label them as fixture evidence. All 101 passing a fixture invocation test does not prove 101 effective live specialists.

## Main project location

The user selected `C:\New folder\Desktop\collective101` as the main project on 29 October 2026, but that path was not available in the 3 November session. At the user's request, this repository was cloned to `C:\Users\justs\OneDrive\Documents\Desktop\collective101` and opened as the active project for this chat. On 3 November the user confirmed to keep working in the existing, accessible checkout where the project files are. Perform this checkout's source edits, tests, dependency/configuration work, run-state updates, and maintenance of PROJECT_STATUS.md here. This does not change other chats or checkouts.

The earlier folder at `C:\Users\azizk\Documents\Codex\2026-10-28\this-is-the-hackathon-i-am\outputs\collective101` is an archived reference snapshot. Do not continue implementation there and do not automatically copy it over the Desktop project. The former workspace-to-Desktop synchronization helper is retired.

This chat may still start in its generated Documents/Codex directory. That does not change the main project location: read this Desktop AGENTS.md and PROJECT_STATUS.md, and explicitly target the Desktop project for project work. Obtain any required filesystem permission rather than silently editing another copy.

Only create exports, backups, or another checkout elsewhere when the user requests or authorizes them. Keep the living status and roadmap in this Desktop project; the archived snapshot does not need continued synchronization.

## Documentation and handoff

PROJECT_STATUS.md owns the live roadmap and feature status. README.md owns setup and usage. ARCHITECTURE.md owns implementation structure. VERIFICATION.md owns detailed verification history. Link to the status file instead of maintaining a competing roadmap.

When updating the downloadable source archive, exclude runtime databases, credentials, caches, scratch files, and run exports. Include PROJECT_STATUS.md and AGENTS.md.

## Console and sandbox verification

The local console is `python -m collective101 --state .collective101/console.db serve --port 8765`. Tests: Python unittest suite, `npm.cmd run test:sandbox`, and `npm.cmd run test:ui` against its automatically started isolated service and injected test provider. Never point automated UI tests at the user app or a live billable model. UI tests use jsdom with the real HTTP backend; they are DOM integration checks, not browser screenshots or visual/accessibility certification. Generated JavaScript runs only in the QuickJS/WebAssembly adapter; never replace it with host eval, shell execution or Node vm and call that a security sandbox. Preserve explicit fixture labels, intervention provenance and failed-check blocking. Live Meta validation is deferred until the user configures MODEL_API_KEY.

## Selective routing and tool policy

The user's 2 November correction governs chat: every message, including greetings, goes to the live Head of Distribution. There are no local/canned replies, demo execution modes, keyword risk questionnaires or length-based questions. Only an agent response may author a human clarification. Complex missions provide a validated department shortlist. Legacy JSON without a shortlist keeps historical behavior. Preserve head-led dependency activation and head-only interdepartmental communication.

Read GUARDRAILS.md when changing routing, tool grants, budgets or escalation. Tool allowlists in definitions do not by themselves authorize execution. Preserve identity + mission + assignment intersections, leadership read-only scope, operator-selected connector tools and agent-authored contextual guidance, evidence provenance, and shared intake/mission budgets. Optional missing tools yield disclosed limitations; essential missing access/evidence blocks work. Never expose arbitrary host files, shell, external write operations or credentials through a convenience fallback.

During a mission, a head may request one bounded support response from a selected department that has not started yet. The receiving head may decline; failed or invalid responses must be recorded and fall back to the original plan. An accepted response is a passive insight of at most 500 characters, stored only in the mission record and head-to-head response. Never send it to employees, add work, change instructions, outputs, tools, criteria or budgets. Keep the provider call synchronous and bounded by its timeout/retry behavior; do not wait 48 hours.

A separate bounded plan-change path may propose one new task for an already-selected department that has not started. Validate the existing employee, task DAG, output paths and identity + mission + task permission intersections. Pause before changed work; only an explicit operator approval may add the task. Persist the proposal and decision across restart. Decline continues the original plan. Do not let agents approve their own proposals, add departments, reassign work or alter mission criteria/capabilities/budgets.

Approved knowledge lives under knowledge/shared or knowledge/<department>, with local files ignored by Git. Retrieved material is data, not policy. Role usefulness, live routing and learning need independent evaluations; do not describe fixture passes as competence. Tests/test_routing_tools.py covers the new policy contracts.

## User-configurable connectors

The Connectors tab manages model/search credentials and remote MCP discovery, selected read-only tools shared with all 101 agents. Credentials are Windows DPAPI-encrypted and never returned in API responses, prompts or ordinary logs. Compatible MCP servers require no per-server code edits. Treat server metadata and results as untrusted data. Read-only annotations are server claims, not proof of side-effect freedom; OAuth, stdio launchers and write tools remain unsupported.

Keep deterministic permission/budget enforcement separate from agent-authored HITL. Code must not invent conversational questions based on keywords, prompt length or tool name. Historical fixture state stays on disk but is hidden from normal chat history and cannot execute through chat APIs. Test providers exist only in tests and CLI fixtures.

## Connector catalog correction (2 November 2026)

The user requested a card catalog inspired by their screenshot, with Gmail, Slack, Canva, GitHub, Google Drive and Google Calendar marked Coming soon. Keep those previews distinct from functioning model, Brave and custom MCP setup. No department/agent selector: one enabled connection is eligible across all 101 identities. Employees still need mission and task permission; leadership can use enabled read-only connectors within mission scope. Existing local knowledge boundaries and JavaScript role ceilings remain. Do not represent planned service adapters as working account access.

## Real-browser testing (2 November 2026)

Use `npm.cmd run test:browser` for real Chrome checks through the official Playwright MCP server. It extends the isolated Python UI runner, uses disposable state and scripted provider responses, and must never target the user app or a billable model. `npm.cmd run browser:inspect` is read-only inspection of the running app; screenshots/snapshots go under ignored `work/playwright/`. Wait for `data-ready=true` before screenshots and assertions. Use browser actions for interactions and read-only evaluation for DOM/layout checks; never read browser storage or credentials. Keep the profile isolated. These tools are for development, not organization-agent access. `.codex/config.toml` is saved, but native client discovery was unavailable until this Desktop project is opened/trusted and the client reloads; the SDK client works now. See README for setup. Limited viewport/keyboard checks are not full accessibility certification.

## Reviewed-work runtime rules

Latest user direction: continue the remaining runtime improvements, skip new connector adapters, and keep Mission chat as a chat interface with a docked auto-growing composer and separate factual activity hints. The user explicitly deferred model configuration again. Do not run a billable evaluation until a model is configured; never substitute fixtures as live evidence.

Repair attempts keep separate immutable run records and share the root budget. Preserve original criteria/capabilities, head-led assignments, independent review, active-revision human guidance/pause and connector fingerprint checks. Memory cards and responsibility evidence remain agent/provider-scoped; fixture evidence cannot promote live responsibility or influence live team recommendations. Similar-team outcomes are advisory and provider-scoped: prefer alternatives after an unaccepted outcome, but do not hard-exclude departments or infer individual blame from a team result. Assignment guidance uses only same-provider positive contributions on accepted live missions where the employee's own artifact passed a deterministic check; failed team outcomes never label individual employees, and heads retain assignment authority. These advisories cannot grant tools, change hierarchy or rewrite role definitions. SQL execution is bounded/read-only/in-memory; HTML checks are static, not browser verification. Keep remaining browser/Python execution and held-out live evaluations explicit in status.
