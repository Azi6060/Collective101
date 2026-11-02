# Collective 101 - aim, implementation status, and next work

Last reviewed: **2 November 2026 (Asia/Kuala_Lumpur)**.
Current stage: **Reviewed-work runtime plus verified Playwright MCP browser testing, chat viewport layout and repeatable isolated UI checks**.
Main project: **`C:\New folder\Desktop\collective101`**.

This is the sole living roadmap. Read it and AGENTS.md before every project work session; update before handoff. README.md owns usage, ARCHITECTURE.md design, GUARDRAILS.md policy, and VERIFICATION.md test history. Fixtures prove protocols, not live intelligence or a winning probability.

## 1. Aim and accepted decisions

Build an operational organization of 101 persistent identities that completes complex missions through relevant departments, scoped tools, collaboration, evidence, human guidance and measured improvement.

The user's latest correction supersedes the earlier local-greeting and keyword-HITL design:

1. **Every new chat message reaches Head of Distribution (`distribution-001`) via the configured live model**, including Hi. No local/canned answer, demo run option or fixture fallback in chat.
2. The first agent chooses reply, clarify or mission from meaning and context. Question length/keywords do not trigger fixed forms. A missing model connection is a configuration error, not a conversational question.
3. Only agents author clarification questions and reasons. The runtime validates, persists, displays and pauses/resumes them; it does not decide a questionnaire from input shape. Heads/employees can request contextual interventions during work.
4. Distribution prepares the objective, criteria, available capabilities and relevant department shortlist. Consulted heads contribute/decline, request dependency departments and assign their own employees; the Director selects/integrates the team.
5. Employees report to their own head. Only heads/Director discuss across departments. Human questions are a separate guidance channel, not employee-to-employee access.
6. Users set up supported connectors from cards, select read-only MCP tools, and disconnect them without per-server source edits. Enabled connections are eligible for all 101 agents; there is no department/agent selection. Runtime permissions/budgets remain enforced regardless of model text.
7. With a live model but no external tools, agents reason/draft from role expertise, supplied context and approved local knowledge. Optional unavailable tools are disclosed; essential missing evidence blocks acceptance. Do not demand optional connections to get started.
8. Keep 101 individually editable definitions and clear roles. Consolidate reviewed evidence without treating it as training. Responsibility recommendations can advance or decline based on distinct checked live outcomes; they never change hierarchy or permissions.
9. Latest request: skip new connector adapters; continue runtime improvements. Mission chat is a conversation surface with a docked auto-growing composer and separate factual activity hints. The user again deferred live model configuration on 2 November.
10. Desktop is canonical. Use the retained Addy Osmani agent-skills workflows; no Postman for general development. No additional account/service is connected automatically.
11. Use Playwright MCP for future development browser testing. It is separate from organization-agent connectors. Real interactions run on disposable state with a scripted model; viewing the user app is read-only.

## 2. The 101 agents

One Director, ten heads and ninety employees, with unique role prompts, responsibilities, reporting lines, memory namespaces and base tool eligibility in `collective101/departments/<department>/<agent-id>.json`. They share a runtime/provider, not independently trained models.

| Department | Total | Head | Employee focus |
| --- | ---: | --- | --- |
| Distribution & Coordination | 8 | distribution-001 | Intake, decomposition, dependencies, resources, recovery, progress, knowledge |
| Research & Intelligence | 10 | research-001 | Sources, domain context, user needs, comparisons, evidence, requirements, risks |
| Strategy & Planning | 8 | strategy-001 | Objectives, options, feasibility, priorities, challenge, synthesis |
| Engineering & Automation | 16 | engineering-001 | Frontend, backend, integration, builds, code review, automation, tests, security, accessibility, performance, reliability, architecture |
| Data & Analytics | 10 | data-001 | Profiling, descriptive analysis, validation, experiments, metrics, visualization |
| Design & Media | 8 | design-001 | UX, visual design, accessibility, interactions, review, design systems |
| Operations & Delivery | 8 | operations-001 | Resources, scheduling, release/rollback plans, service readiness, runbooks |
| Communications & Documentation | 6 | communications-001 | Writing, editing, technical documentation, review |
| Tools & Infrastructure | 10 | platform-001 | Capability matching, access policy, health, integration, MCP design, harness design |
| Verification & Evaluation | 16 | assurance-001 | Acceptance, adversarial review, reproducibility, requirements, security, evidence, benchmarks, improvement evaluation |
| Mission Director | 1 | director-001 | Select contributions, integrate outcomes and commission measurable improvement proposals |
| **Total** | **101** | **11 leaders, 90 employees** | **Working roles; live effectiveness unverified** |



All 101 are addressable and fixture-invoked in protocol tests. **Live role usefulness remains unverified.** The first chat agent is now one of these identities (distribution-001), rather than an anonymous controller with canned replies.

## 3. Current input-to-result flow

| Stage | Implemented behavior | Limit |
| --- | --- | --- |
| User message, including Hi | Live call using distribution-001's role prompt and conversation | No key/provider success means error; no invented answer |
| Simple question/greeting | Agent may reply directly, with no department mission | Actual relevance depends on live model judgement |
| Missing relevant intent | Agent emits contextual questions and reason; UI preserves authorship | At most three intake clarification rounds; no keyword/length triggers |
| Complex mission | Agent supplies criteria, available capabilities and smallest useful shortlist | Model allocation quality still needs live assessment |
| Department assessment | Selected heads assess/decline, dependencies activate omitted heads, one council round | Legacy JSON with no shortlist still consults all heads; no continuous replanning |
| Director/team execution | Dependency-closed selection; heads assign employees/tools; failed review/checks can commission one revision by default, at most two | Same original criteria and shared budgets; no concurrent scheduler or self-hiring |
| Employee actions | Drafts, approved knowledge/memory, JavaScript and enabled connector tools | Permissions are identity/connector + mission + assignment intersections |
| Human intervention during work | Requesting agent writes intervention; phase pauses, answer binds to it and work resumes | No automatic web-query or risk questionnaire; permission denials remain code-enforced |
| Cooperation/review | Head aggregation/forwarding, independent non-producer Assurance reviewer, original criteria + observed checks | Positive narrative cannot override missing essential evidence or failed checks |
| Completion/improvement | Director integration, provenance-linked memory consolidation and advisory responsibility evidence supplied to heads | No role/permission self-modification; actual learning or live specialist competence remains unproven |

Answered simple chats support follow-up messages in the same conversation. Historical demo records remain on disk but are hidden from chat history and cannot be started/resumed through chat APIs. CLI fixtures remain for engineering tests only.

## 4. Connectors, tools, memory and UI

**Connectors tab (`/connectors`):** searchable card catalog and availability filters. Gmail, Slack, Canva, GitHub, Google Drive and Google Calendar are Coming soon previews, with no account access. Live model, Web search and Custom MCP cards open functioning setup. Saved connections are managed below. Enabled tools are shared with all 101 identities; no department/agent selector. New compatible MCP servers require no source adapter per server.

- Model: existing MODEL_API_KEY/META_MODEL environment configuration or UI-saved settings. Keys are Windows user-bound DPAPI-encrypted. API responses expose credential presence only. Configuration presence is not proof of provider success.
- Brave: use the Web search card to save a key and enable. All agents are eligible; employees need a task grant and leaders operate within mission scope; no fixed per-query question. The agent decides if a particular proposed disclosure needs human guidance. Missing configuration never produces fake research.
- MCP: HTTPS Streamable HTTP, optional bearer authentication, JSON/SSE responses, lifecycle/session headers, bounded paginated tools/list and tools/call. Explicit localhost opt-in allows loopback HTTP. Private/link-local/metadata destinations are rejected, DNS addresses pinned, TLS hostname checked, redirects refused, and request/result bounds applied.
- User-selected server-declared read-only tools enter every agent's model-visible catalog and employee assignment capabilities. Unknown/write tools cannot be enabled. **Read-only annotations are server claims, not remote side-effect guarantees; connect trusted servers.** Full schema validation beyond required fields is delegated to the MCP server.
- Connector access is checked per call. Configuration fingerprints bind existing missions; changed configuration requires a new mission. Disconnect blocks further calls. Concurrent settings edits cannot publish stale discovery results for another endpoint.
- No OAuth sign-in, stdio command launching, arbitrary REST import, server-requested sampling/elicitation, general host shell, deployment or write-capable adapters. No real external account/MCP server was connected in this session.
- Knowledge: Organization ? Shared knowledge imports explicit TXT/MD/CSV/JSON documents up to 64 KiB into shared knowledge. Content-hash filenames deduplicate without overwriting different data. Existing shared/own-department reads retain path/link/extension limits; no arbitrary filesystem access.
- Memory: same-agent/provider reviewed episodes plus up to 50 consolidated exact-match cards, each retaining at most 20 evidence runs. Up to three relevant cards are retrieved and frozen per call. Raw source evidence stays available. No semantic embeddings or demonstrated learning gains.
- Execution: existing QuickJS/WebAssembly plus SELECT-only in-memory SQL over supplied tables. SQL denies host databases/files, writes, attachments, pragmas, extension loading and unapproved functions; input/output/VM/time limits apply. SQL artifact acceptance checks compare actual rows. Static HTML structure checks load no resources and execute no scripts. Full browser/Python/OS execution remains pending.
- Shared budgets: intake, department calls and every revision share a persistent ledger (up to 160 calls/2,000,000 conservative token-admission units). Failed/uncertain requests retain reservations. Four tool requests per phase, 40 recorded across root/revision runs. No exact tokenizer, dollar billing or tool-service cost cap.
- UI: chat-only surface with a docked non-resizable composer that grows to 200 px then scrolls, separate recorded agent/phase/tool activity hints, collapsed mission details, pause/resume and activity links. Status-only updates preserve conversation DOM. Organization includes shared document ingestion and responsibility evidence. Version: **0.5-reviewed-work**.
- Revisions: zero to two (default one), with unchanged criteria/capabilities, immutable per-attempt evidence, fresh independent review, shared budgets, root pause and active-revision human answers. Missing capability blockers do not blindly retry; changed connectors invalidate old access. Latest artifacts are shown while all attempts remain inspectable.
- Responsibility: three distinct independently accepted live objectives with checked own artifacts beyond mere existence allow trusted_contributor; eight and no recent failures allow senior_contributor. Two failures in the last five records return the recommendation to developing. These are advisory task-assignment levels, not new role titles/tool grants. Fixtures do not qualify.
- Evaluation: explicit live `evaluate --max-calls 80` command reuses the production intake prompt and records four routing cases, two specialist checks and a departmental JavaScript case against the same single-specialist checks. Reports include latency/calls/tokens and human-review requirements. Uses isolated state; no live evaluation run yet.

## 5. Fresh verification (2 November 2026)

Latest reviewed-work session: **100 Python tests passed** in the full suite (199.570 s, no failures/errors/skips); **7 jsdom/real-HTTP UI tests passed** (27.663 s); **8 QuickJS containment tests passed** (5.984 s). New checks cover correction/re-review with immutable first-attempt evidence, bounded budgets, repair interventions and pause, document dedup/path/size limits, provider/agent memory isolation, responsibility qualification/exclusion/decline, actual read-only SQL and forbidden access, static HTML, evaluation failure reporting, composer growth and separate status text without rebuilding message nodes. Logs: `work/verification/reviewed-work-python.log` and `reviewed-work-ui.log`; sandbox results in tool transcript. Thirty Python modules parsed; JavaScript syntax and whitespace checks passed. Browser inventory again unavailable. No live model or external connector call, account connection, commit or push occurred.

Earlier connector-catalog evidence:

Latest catalog change: **87 Python tests passed** in the full suite (183.449 seconds, zero failures/errors/skips) and **6 jsdom/real-HTTP UI tests passed** (21.222 seconds, zero failures/skips). Tests cover catalog preview/search/filter/empty states, setup/focus/Escape, no agent selectors, encrypted key omission, all 101 identities eligible for connected tools, task/mission limits, disconnect and credential-preserving legacy scope migration. The first UI run caught an unfinished fetch at test teardown; the corrected final run passed cleanly. Logs: `work/verification/connector-catalog-python.log` and `connector-catalog-ui.log`. The updated app reports 0.4-connector-catalog. Browser services remain unavailable; no visual/browser accessibility pass or live provider/account access is claimed.

Earlier live-connectors implementation evidence:

- **85 distinct Python tests passed:** full 82-test suite, zero failures/errors/skips, **163.918 s**; subsequently added archived-demo-history, failed-live-Hi and discovery-race tests passed in focused runs. The final connector/live-chat/wire subset passed **14 tests in 6.364 s** (overlaps the total; do not add it again).
- **5 jsdom/real-HTTP UI tests passed**, zero failures/skips, **19.951 s**, through the reproducible isolated `npm.cmd run test:ui` runner: directory; agent clarification/resume; actual JS evidence/escaping; provider-authored greeting; connector save/encrypted-key omission/enable/disconnect.
- Real local MCP HTTP test covered initialize, session handling, SSE tools/list, dynamic assignment, tools/call, observed evidence to the head and revocation. DPAPI encryption/decryption was real; provider responses were injected scripts and external endpoints were not called.
- Red tests reproduced canned Hi, accepted demo submission, missing agent question authorship and missing connector functionality before fixes. Tests expecting the superseded keyword/length/query rules were replaced with the newly requested semantics. A broad test edit temporarily changed provider-isolation fixture values; corrected and the full suite passed.
- Actual running app returned version 0.3-live-connectors, `/chat`, `/connectors` and `/app.js` HTTP 200. Hi without model configuration returned HTTP 400 with a configuration error; fixture submission returned HTTP 400 live-only error. No assistant answer or irrelevant questions were generated.
- Browser/native UI services again unavailable; actual-browser visual/responsive/accessibility verification remains pending. No live Meta or Brave request, real external MCP connection, Postman action, deployment, commit or push occurred.

Evidence: work/verification/live-connectors-python.log and live-connectors-ui.log plus focused tool execution transcripts. Detailed historical results remain in VERIFICATION.md. Earlier 8-test QuickJS containment suite was not freshly rerun this session; current Python/UI tests did execute real JavaScript through the unchanged adapter.

## 6. Remaining work and next concrete step

- [x] 101 individual identities, head-led contribution, selective live intake and scoped tools.
- [x] Connector catalog/shared eligibility; new provider adapters skipped this session as requested. Coming soon cards remain previews, not working OAuth integrations.
- [x] Chat-only layout, docked auto-growing input and factual action hints outside messages.
- [x] Bounded review-driven corrections with immutable attempt history, fresh review and shared limits.
- [x] Shared text ingestion, bounded memory consolidation and advisory responsibility evidence.
- [x] SQL execution, SQL acceptance checks and static HTML checks alongside JavaScript.
- [x] Repeatable live evaluation command, specialist/team comparison and failure/latency/token reporting.
- [ ] Run live evaluations once the user configures the model; assess answer/question relevance, head decisions and specialist usefulness independently across more mission families.
- [ ] Validate memory benefit and responsibility thresholds against held-out cases; no measured improvement or earned live advancement yet.
- [x] Development browser testing through Playwright MCP: desktop/mobile screenshots, viewport bounds, composer growth, greeting, activity hints, clarification flow and catalog/role inspection.
- [ ] Organization-agent browser/app/Python execution; broader viewport/device coverage and full accessibility audit.
- [ ] Selective repair of only affected tasks, general mid-mission head-to-head help/replanning, richer semantic retrieval and retention controls.
- [ ] All-101 role evaluation and broader small-team/departmental baselines; hosted multi-user authentication if requested.

**Next concrete step:** when the user's provider is ready for evaluation, run the bounded evaluation command, review the recorded outputs and compare single-specialist versus departmental results. Browser inspection now sees a configured-model indicator; no live evaluation was run in the browser-testing follow-up. Continue to distinguish protocol correctness from live quality. Use `test:browser` for future UI regressions and extend device/accessibility coverage as needed.

## 7. Current session handoff

All source/tests/state/docs remain in the Desktop project. The idle local app has been restarted for version 0.5-reviewed-work at http://127.0.0.1:8765/chat. The running service had no model configuration before restart; the user chose to configure it later. No credentials were extracted, overwritten or printed. New Gmail/Slack/etc. adapters were not implemented or connected.

New runtime modules: progress, repairs, learning, knowledge, data_execution, html_checks and evaluations. SQL eligibility was added to applicable engineering/data/assurance/platform agent definitions without changing identities/reporting lines. Existing raw histories are retained. Older incomplete runs may reject changed call context instead of rewriting recorded evidence.

Browser follow-up: official Playwright MCP 0.0.84 and MCP SDK 1.32.2 installed locally. The SDK client successfully discovered tools, navigated the running app and captured screenshots/accessibility snapshots. A readiness wait prevents capturing the loading screen. Real Chrome exposed a mobile composer bottom of 867 px in an 844 px viewport; sizing the chat from remaining flex space fixed it to 832 px. Five isolated browser tests passed in 40.464 s; seven existing DOM/HTTP tests passed in 19.254 s, both with scripted provider output, zero failures/skips. Read-only production inspection also passed desktop/mobile bounds and found zero console errors/warnings. Screenshots were visually inspected. No paid model calls or production chat writes were made by these checks. The visible app now reports a live model configuration, but its correctness and live agent quality were not evaluated.

Project `.codex/config.toml` is saved; this client/CLI did not discover the project-scoped native entry and no Desktop trust entry was found. Open the Desktop folder as a trusted project and reload the client for native tool discovery. No trust settings were changed automatically. The verified `test:browser` and `browser:inspect` MCP SDK commands already work. Evidence: `work/verification/playwright-browser.log`, `work/verification/live-connectors-ui.log`, and `work/playwright/`. Browser execution remains a developer tool, not a capability granted to the 101 agents. Full accessibility, live effectiveness and broader device coverage remain open.

## 8. Main project and archived snapshot

- **Main and authoritative project:** `C:\New folder\Desktop\collective101`.
- **Archived reference snapshot:** `C:\Users\azizk\Documents\Codex\2026-10-28\this-is-the-hackathon-i-am\outputs\collective101`.
- The existing source archive under the old workspace's outputs is an earlier export, not the working source.

The user selected the Desktop folder as the main project on 29 October 2026. From this decision onward, all project implementation, tests, run-state changes, and updates to this living status file belong in the Desktop folder. There is no automatic two-way synchronization. Never overwrite the Desktop project using the archived workspace snapshot.

The chat's generated starting directory may still be under Documents/Codex. Its AGENTS.md redirects project work to this Desktop folder. Use the Desktop working directory explicitly for project commands and obtain any necessary filesystem access. Do not work on the archived source as a fallback.

The older documentation synchronization is historical evidence only. Root/workspace instructions now mark that copy as archived. Exports or backups elsewhere can be made when requested, using the Desktop source.

At each session: read this Desktop PROJECT_STATUS.md and AGENTS.md, inspect the current Desktop source, perform the authorized work here, verify appropriately, update status and outstanding work, and add a dated change-log entry. Do not maintain a second live roadmap in the archived snapshot.

## 9. Change log

| Date (MYT) | Work | Verification and remaining limits |
| --- | --- | --- |
| 2026-11-02 | Installed official Playwright MCP and SDK, saved project native-client config, added isolated real-Chrome tests and read-only screenshot command; fixed mobile chat composer overflow. | 5 MCP/Chrome tests + 7 DOM/HTTP tests passed; app screenshots inspected, zero console errors/warnings. Scripted model only. Native project entry still needs client trust/reload; no live quality or full accessibility claim. |
| 2026-10-29 | Implemented the first local runtime, 101-profile registry, five-tool mission, scoped grants, verification, recovery, revision, Meta adapter, and exported reports. | Initial 21-test gate and local HTTP contract checks recorded in VERIFICATION.md. Live Meta execution unverified. |
| 2026-10-29 | Copied the project to the user's Desktop. | All 53 files in the original handoff copy were hash-verified. The two folders remain separate. |
| 2026-10-29 | Audited source against the full departmental-organization idea; created this living status record and AGENTS.md read/update instructions; linked setup documentation to this roadmap; synchronized five tracking documents to the Desktop project. | Fresh 21-test run passed with no skips in 16.785 seconds. Pre-update source comparison found 25 identical files; synchronized documents were hash-verified. Stored state contains fixture evidence only. HTTP simulation was inspected as historical evidence, not rerun. No runtime behavior changed. |
| 2026-10-29 | User selected the Desktop folder as the authoritative main project. Updated Desktop instructions/status and added redirects to the archived workspace. Retired workspace-to-Desktop synchronization. | Desktop runtime source hashes preserved; documentation checked in the Desktop folder. No tests rerun for this documentation-only change. Future source, tests, and status updates belong in the Desktop project. |
| 2026-10-29 | Initialized the Desktop project as a Git repository and published it to the private `Azi6060/Collective101` repository. | Initial commit `2424f10` pushed successfully to `origin/main`. No runtime tests were rerun; this was repository setup only. |
| 2026-10-31 | Reviewed current Desktop agent registry, runtime, five-tool planner, and saved activity; recorded exact profile/invocation counts and actual departmental capabilities. Clarified that the organization handles complex tasks and a harness is an execution layer; external harness choice remains open. | 101 registered profiles; 13 fixture-invoked identities (one planner, 10 workers, two reviewers); no recorded live Meta mission. Read-only source/state inspection; no tests or external calls rerun, no runtime source changed. |
| 2026-10-31 | Implemented 101 individual agent definitions and the department-led organization cycle: participation decisions, leadership-only council, head assignments, draft artifacts, independent review, bounded memory and improvement proposals. Retained the user-selected agent-skills library and replaced general Postman skill guidance. | 40 tests passed in 75.360 seconds; all 101 identities fixture-invoked in a dedicated test; website and research fixtures produced six and three artifacts with different teams. Windows path-collision regression and leadership-policy mutation detected. No live inference, new HTTP simulation, deployment or automatic learning claimed. |

| 2026-10-31 | Added QuickJS/WebAssembly execution and a local Bootstrap console with departments, agents, mission chat, clarification interventions, pause/resume, activity filters and recorded evidence. User deferred live Meta configuration. | 50 Python tests, 8 sandbox tests and 3 DOM/HTTP UI tests passed. Calculator fixture source actually executed three checks. Zero known production npm vulnerabilities reported. Browser/native-control services unavailable, so visual/accessibility QA remains pending. |

| 2026-11-01 | Added selective intake/routing, per-agent scoped tools and knowledge, relevant episode recall, external-query approval, shared request/token admission budgets, risk preflight and UI evidence/controls. | 71 Python tests (68 full-suite + 3 added integration), 8 actual sandbox tests and 4 DOM/HTTP UI tests passed. Live models/search and actual-browser visual QA remain unverified. |

| 2026-11-02 | Added UI-configured model/search/remote MCP connectors with encrypted credentials and scoped discovery/execution/revocation. Replaced canned/demo/keyword chat behavior with live distribution-001 decisions and agent-authored clarification; restored the updated local app. | 85 distinct Python tests passed (82 full suite plus 3 new targeted cases); 5 isolated DOM/HTTP UI tests passed. Local MCP HTTP/SSE and DPAPI executed; live providers/external connectors and visual browser QA remain unverified. |

| 2026-11-02 | Replaced connector type/department forms with a searchable service-card catalog. Added Gmail, Slack, Canva, GitHub, Drive and Calendar Coming soon previews; retained functioning model/search/custom MCP setup. Made enabled connectors eligible across all 101 agents, preserving mission/task limits and credential ciphertext. | 87 Python + 6 DOM/HTTP UI tests passed; updated local app verified at 0.4-connector-catalog. Service adapters/OAuth and real-browser visual checks remain pending. |

| 2026-11-02 | Added chat-only docked composer and factual action hints; bounded head-led repair revisions, shared knowledge ingestion, memory consolidation, advisory responsibility evidence, SELECT-only SQL and static HTML checks, plus isolated live evaluation runner. Skipped new connector adapters; user deferred model setup. | 100 Python + 7 DOM/HTTP UI + 8 QuickJS tests passed. No live evaluation, earned promotion, measured learning, browser visual QA or new external connection is claimed. |
