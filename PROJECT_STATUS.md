# Collective 101 - aim, implementation status, and next work

Last reviewed: **29 October 2026 (Asia/Kuala_Lumpur)**.
Current stage: **Milestone 1 - locally verified orchestration foundation**.
Main project: **`C:\New folder\Desktop\collective101`** (explicit user choice).
Overall assessment: the execution foundation exists; the broad autonomous departmental organization remains to be implemented. There is no measured completion percentage or supported winning-probability estimate.

This is the living project record. Read it before every project work session and update it before handoff. `AGENTS.md` makes that maintenance part of the project workflow.

## 1. What we aim to build

**An adaptive organization of 101 persistent AI-agent identities that takes a user mission, distributes it across relevant departments, lets departments propose and execute useful contributions, obtains appropriate tools, verifies outcomes, and improves future allocation using evidence.**

The user's intended product is broad: departments should identify what they can do to make progress, help another department, or improve the outcome. The product should support different mission types rather than remain tied to an event-planning demonstration or a software-only company.

The target mission lifecycle is:

1. Understand the user's outcome, constraints, permitted actions, and completion conditions.
2. Distribution identifies relevant departments and asks for contribution proposals.
3. Departments propose deliverables, dependencies, needed capabilities, estimated effort, and acceptance checks. A department can decline when it cannot contribute usefully.
4. Select a coherent plan and a responsible mission owner; form a temporary team across permanent departments.
5. Department leads coordinate specialists. Teams can request help, challenge assumptions, and propose bounded improvements.
6. Tools & Infrastructure resolves capability requests through a registry of skills, local tools, APIs, MCP servers, and supported integrations, with executable permissions enforced by the runtime.
7. Execute work, produce artifacts, and independently check the user's completion conditions.
8. Recover from failures and replan the affected work when conditions change.
9. Deliver the integrated result with evidence and explicit unresolved limitations.
10. Retain useful experience and evaluate contributions for better future assignments and responsibility growth.

### Decisions to preserve

- 101 is the registered roster size, not a requirement for 101 simultaneous calls or universal participation in every mission.
- Use reusable department and role templates with individual identities, capabilities, and histories; do not hand-maintain 101 separate programs.
- Combine permanent departments with temporary mission teams.
- Keep role, rank, reputation, memory, task ownership, and tool permissions separate.
- Each mission and task needs a clear owner and checkable completion conditions.
- Give departments bounded autonomy to propose useful work without encouraging endless busywork or unbounded spending.
- Keep specialist and leadership progression separate. Reward checked contribution, useful error discovery, efficient work, and coordination quality.
- A promotion or larger resource allowance must not automatically grant unrelated tool access.
- Build a useful, observable organization whose results justify its coordination cost. Relative performance must be measured.

## 2. Current department allocation

| Department | Registered identities |
| --- | ---: |
| Distribution & Coordination | 8 |
| Research & Intelligence | 10 |
| Strategy & Planning | 8 |
| Engineering & Automation | 16 |
| Data & Analytics | 10 |
| Design & Media | 8 |
| Operations & Delivery | 8 |
| Communications & Documentation | 6 |
| Tools & Infrastructure | 10 |
| Verification & Evaluation | 16 |
| Organization-level mission director | 1 |
| **Total** | **101** |

This allocation is implemented in `collective101/registry.py`. It is an initial roster proposal, not an empirically optimized staffing plan. Some departments currently have no executable capability. The director is recorded as the mission owner, but has no active director reasoning loop. Department leads exist as profiles and are excluded from the current worker selector.

## 3. Idea versus actual implementation

Status definitions: **Implemented locally** means working code with local evidence; **Partial** means only part of the intended behavior exists; **Unverified live** means an adapter or path exists without real service evidence; **Not implemented** means the behavior is absent.

| Intended capability | Current status | What exists and what is still missing | Source evidence |
| --- | --- | --- | --- |
| 101-agent organization | Partial | 101 unique generated profiles are persisted. Only selected identities are invoked; there is no evidence that all 101 are useful or a scalable organization. | `registry.py`, `runtime.py`, `store.py` |
| Per-agent configuration | Partial | IDs, role labels, specialty labels, charters, rank labels, capabilities, and memory namespaces exist. Runtime instructions use role and charter. Specialties do not drive selection or distinct expert policies. All agents share the chosen provider/model. | `registry.py`, `runtime.py:choose_agent`, `runtime.py:execute_task` |
| Distribution department | Partial | A single planner identity produces a validated task graph. The validator requires the same five tools exactly once, with fixed capability/check types and restricted department mappings. | `planning.py`, `runtime.py:create` |
| Broad mission intake | Not implemented | The actual input contract requires event attendance records and event operating constraints. An arbitrary prompt cannot change the supported workflow. | `cli.py`, `planning.py`, `tools.py:validate_rows` |
| Autonomous departmental contributions | Not implemented | No proposal-request phase, contribution selection, negotiated work scope, or department-originated improvement loop. | `runtime.py` has planning, execution, and review phases only |
| Department management hierarchy | Partial | Lead/coordinator/specialist/reviewer/curator labels exist. Leads do not break down work or supervise specialists; the central runtime assigns workers. | `registry.py`, `runtime.py:choose_agent` |
| Cross-department collaboration | Partial | Accepted dependency artifacts are passed to downstream tasks. No peer request protocol, event subscriptions, conflict resolution, or temporary team object. | `runtime.py:execute_task` |
| Persistent mission board | Implemented locally | SQLite stores missions, tasks, events, scoped grants, tool artifacts, evaluations, and result history. | `store.py` |
| Execution and recovery | Implemented locally | Ready tasks run in parallel with bounded concurrency; selected failures get at most three attempts and can be reassigned. Interrupted tasks can be recovered. | `runtime.py`, `locking.py`, `tests/test_runtime.py` |
| Tools department | Partial | A deterministic capability broker checks the current assignment and department charter, grants registered local functions, and revokes grants after each attempt. `platform-002` is an audit label, not a separate model-driven broker. | `tools.py:ToolGateway` |
| Actual MCP/plugin acquisition | Not implemented | No MCP client, server connection lifecycle, remote discovery, authenticated integration, plugin installation, or new-tool construction. | Five local tools in `planning.py` and `tools.py` |
| Independent verification | Partial | A different reviewer identity plus runtime structural/numerical checks gates acceptance. Local checks work; open-domain factual correctness and model quality are unproven. Fixture reviews are deterministic. | `runtime.py:execute_task`, `tools.py:check_artifact` |
| Adapting to changed constraints | Partial | CLI revisions invalidate the operating-plan task and its descendants while retaining independent data artifacts. No general mission replanning or topology adaptation. | `runtime.py:revise` |
| Persistent individual learning | Not implemented | Namespaces and historical records exist, but there is no memory retrieval, consolidation, procedural improvement, or learned routing. | `registry.py`, `store.py`, `runtime.py:choose_agent` |
| Reputation, promotion, and raises | Partial | Evaluations persist. An initial rule can emit a senior-specialist proposal after at least five live-mode evaluations over two missions and at least 85% acceptance. It does not change rank, resource allowance, role, hierarchy, or permissions. | `runtime.py:evaluate_promotions` |
| Meta model execution | Unverified live | HTTP adapter and tool-message loop exist. The local contract simulation passed historically. No live Meta mission is recorded in the audited state. | `provider.py`, `tests/check_http_simulation.py`, `VERIFICATION.md` |
| Organizational resource management | Partial | Hard model-request count, per-request output limit, bounded worker turns, and concurrency controls exist. Dollar ceilings, total token ceilings, scheduling deadlines, and department resource negotiations are absent. | `provider.py`, `runtime.py`, `store.py:reserve_call` |
| Organization interface | Partial | CLI and static HTML/JSON run reports exist. There is no live mission-control UI, user chat, intervention panel, or streaming org graph. | `cli.py`, `report.py` |
| Proven benefit of 101 agents | Not implemented | No baseline comparison, measured scaling benefit, coordination-cost study, or held-out mission evaluation. | No benchmark harness yet |

Source paths in this table are within `collective101/` unless a different folder is named. Code presence does not establish live effectiveness.

## 4. What is demonstrably done

- [x] Generate and persist exactly 101 unique profiles with the agreed department counts.
- [x] Run the supported five-task mission through the organization runtime.
- [x] Compute real local attendance and operating-cost artifacts from the example CSV.
- [x] Validate task dependencies and reject cycles, unsupported tools, inappropriate capabilities, and weakened check types.
- [x] Enforce mission/task/agent tool grants in code and revoke access after attempts.
- [x] Require worker and reviewer identities to differ; require both reviewer approval and deterministic checks for acceptance.
- [x] Recover and reassign work after an explicitly injected local tool outage.
- [x] Reject an explicitly corrupted operating cost and complete a corrected attempt.
- [x] Persist state across restarts and recover interrupted tasks within the attempt limit.
- [x] Recompute only affected tasks after the supported constraint revision.
- [x] Export inspectable HTML, task artifacts, and a JSON execution trail with clear fixture labels.
- [x] Exclude fixture and loopback-simulation evaluations from live promotion eligibility.
- [x] Provide a Meta HTTP adapter, consumer contract, and local Postman stand-ins.
- [x] Add this status file and project instructions requiring ongoing maintenance.

### Verification and evidence modes

| Evidence | Latest established result | Limits |
| --- | --- | --- |
| Fresh source comparison, 29 October 2026 | Workspace and Desktop had 25 matching source/documentation files before this status update; no differences. | Generated run/cache/state files were excluded from that comparison. |
| Tracking-document synchronization, 29 October 2026 | PROJECT_STATUS.md, AGENTS.md, README.md, ARCHITECTURE.md, and VERIFICATION.md were copied to the Desktop project and hash-verified. | Synchronization preserves divergent user edits and does not replace runtime source or run state. |
| Fresh unit-test audit, 29 October 2026 | `python -m unittest discover -s tests -p 'test_*.py' -v`: **21 passed**, no skips, 16.785 seconds. | Uses deterministic fixtures, not live model inference. |
| Persisted demonstration state inspected during this audit | One fixture mission, version 2, completed; 101 registry records, 39 cumulative fixture calls, nine fixture evaluations, zero promotion proposals. | The counter is provider invocations, not proof of AI calls. |
| Exported version 1 demonstration | Five accepted tasks after one injected outage and one injected wrong cost; 27 fixture calls. | Historical run, not freshly rerun during this audit. |
| Exported version 2 demonstration | Budget 260 and capacity 35 led to a plan for 32 attendees costing 260 units; data-analysis artifacts reused. | Historical run and local assumptions, not external event arrangements. |
| Postman HTTP contract simulation, 29 October 2026 | Previously completed 21 real HTTP exchanges and five additional error checks: 503, 429, timeout, malformed JSON, truncated output. | Historical verification record inspected in this audit; HTTP checks were not rerun. No Meta inference occurred. |
| Live Meta account | **Not established.** No live mission in audited state; MODEL_API_KEY was absent in the audit process. | A key configured elsewhere cannot be inferred from this process. |

See `VERIFICATION.md` and `postman/simulations/meta-contract.context.yaml` for detailed evidence. Keep fixture, HTTP simulation, and live results separate in future updates.

## 5. Known gaps that could be mistaken for completed features

1. The current planner is a constrained demonstration workflow. Its validation requires all five registered tools, so it does not yet implement broad distribution or departmental initiative.
2. Generated profile count is not autonomous workforce capability. Specialty labels are currently descriptive, and several departments have no registered execution tool.
3. Hierarchy is mostly declarative. The mission director and department heads do not run the leadership loops described in the idea.
4. Tool provisioning is local and policy-driven. Nothing currently discovers or connects a real MCP server or installs a plugin.
5. Agent memory is not being retrieved. Stored task history alone does not establish individual learning.
6. Promotions are proposals from a simple acceptance-rate heuristic. There is no validated utility score, leadership track, resource raise, demotion, review/approval action, or policy evaluation. Repeated attempts/revisions also require careful treatment before the score can be trusted.
7. The five local tools have no free-form arguments and produce the main artifacts deterministically. Current model workers mostly orchestrate tools and summarize their outputs; this does not yet demonstrate domain-general agent problem solving.
8. Verification shares calculation helpers with the production tools. It catches corruption and constraint inconsistency but cannot by itself rule out a bug shared by both. Narrative correctness, factual grounding, and generalized outcomes need stronger independent oracles.
9. The HTML page is an exported report. It does not control the running organization.
10. No evidence currently establishes that the organization is better than a single strong agent or a smaller team.

## 6. What needs to be done

### P0 - establish live behavior and align execution with the actual idea

- [ ] **M2-A: Live Meta validation.** Configure MODEL_API_KEY securely, run the supported mission with real inference, record actual errors, usage, and timing, and fix compatibility issues found. Never store a key in project documentation or logs.
- [ ] **M2-B: Generic mission contract.** Separate user outcomes, constraints, inputs, permitted actions, and acceptance conditions from the attendance-specific schema. Retain the event example as one test fixture.
- [ ] **M2-C: Department contribution proposals.** Relevant department leads independently propose deliverables, dependencies, needed capabilities, effort, and verification. Support a justified decline and avoid duplicate work.
- [ ] **M2-D: Proposal selection and mission ownership.** Form a temporary team, choose a responsible mission owner, and create a validated task graph from selected proposals. Allow supported plans that do not use all five existing tools.
- [ ] **M2-E: Real role execution.** Make leads, coordinators, and specialists operational; use task requirements and evidence of capability to assign work rather than only historical assignment count.

M2 acceptance: the same core runtime accepts two different supported mission families, creates different justified teams and task graphs, accepts department-originated proposals, and delivers artifacts against explicit mission checks. Fixture tests may develop the protocol; live AI effectiveness remains a separate evidence gate.

### P1 - capability acquisition and department cooperation

- [ ] **M3-A: Capability registry.** Describe local tools, skills/procedures, API adapters, and MCP connections with readiness, scope, cost, and usage constraints.
- [ ] **M3-B: MCP client integration.** Connect two deliberately chosen, tested MCP servers; implement discovery, invocation, error handling, connection lifecycle, and missing-authorization states.
- [ ] **M3-C: Tools department request handling.** Translate a department's requested outcome into an available capability; distinguish unknown, unsupported, unconfigured, unauthorized, and temporarily unavailable capabilities.
- [ ] **M3-D: Cross-department request protocol.** Persist help requests, answers, decisions, disputes, and resolutions with provenance and clear ownership.
- [ ] **M3-E: General change propagation.** Handle changed assumptions, new evidence, failed tools, and revised user constraints beyond the fixed operating-budget subtree.

M3 acceptance: a department requests a capability it initially lacks, the broker connects a permitted real tool, its observed output feeds an accepted deliverable, and a missing/failed capability causes an explicit alternative or blocked result. Tool access remains independently enforced by the runtime.

### P1 - memory and responsibility growth

- [ ] **M4-A: Per-agent and department memory retrieval.** Retrieve relevant prior results, preserve provenance, and separate private working notes from accepted shared knowledge.
- [ ] **M4-B: Measured contribution.** Account for task difficulty, independent acceptance, rework, cost, useful error discovery, and impact on the integrated mission. Prevent self-grading and simple score farming.
- [ ] **M4-C: Responsibility policy.** Add specialist and leadership tracks, provisional leadership assignments, reviewable promotions/demotions, and resource raises justified by evidence.
- [ ] **M4-D: Evaluated organizational learning.** Demonstrate whether memory or changed assignment policies improve performance on held-out missions. Keep baseline budgets comparable.

M4 acceptance: checked evidence changes a later assignment or approved responsibility level, the decision is explainable and reversible, and it does not grant unrelated tool permissions. A model merely claiming to have learned does not pass this gate.

### P1 - demonstration and user control

- [ ] **M5-A: Live interface.** Mission input, department/agent state, task ownership, tool requests, artifacts, verification, resources, and streaming events.
- [ ] **M5-B: Intervention.** Change constraints, pause/resume supported execution, inspect/reject proposals, and resolve genuinely missing authorization.
- [ ] **M5-C: Demonstration.** Show a broad mission, department-originated contributions, acquisition of a real capability, a mid-run constraint change or failure, and a verified integrated result.

### P2 - prove value and prepare the submission

- [ ] **M6-A: Comparison harness.** Single agent, smaller team, fixed departments, and adaptive departments using comparable model/resource budgets.
- [ ] **M6-B: Metrics.** Accepted mission outcomes, correctness, human interventions, wall time, actual usage/cost, coordination overhead, and recovery effort.
- [ ] **M6-C: Repeatability.** Saved test inputs, documented environment, reproducible traces, and clear separation of simulated/live evidence.
- [ ] **M6-D: Submission package.** README, architecture, limitations, model contribution, benchmark results, and a concise recording of observed behavior.

## 7. Immediate next work and blockers

**Next product implementation target:** M2-B through M2-D: general mission intake and a department-proposal/selection cycle. This closes the largest gap between the code and the user's idea. Build it with checkable fixtures and explicit task graph validation, then validate the behavior with real Meta inference when available.

**Parallel validation target:** M2-A, a live Meta run. MODEL_API_KEY must be available to the execution process. Its absence blocks live validation, not local architectural work.

No background automation has been created. Status maintenance happens as part of each project work session. The latest update changes project-location instructions only; it does not implement new runtime behavior.

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
| 2026-10-29 | Implemented the first local runtime, 101-profile registry, five-tool mission, scoped grants, verification, recovery, revision, Meta adapter, and exported reports. | Initial 21-test gate and local HTTP contract checks recorded in VERIFICATION.md. Live Meta execution unverified. |
| 2026-10-29 | Copied the project to the user's Desktop. | All 53 files in the original handoff copy were hash-verified. The two folders remain separate. |
| 2026-10-29 | Audited source against the full departmental-organization idea; created this living status record and AGENTS.md read/update instructions; linked setup documentation to this roadmap; synchronized five tracking documents to the Desktop project. | Fresh 21-test run passed with no skips in 16.785 seconds. Pre-update source comparison found 25 identical files; synchronized documents were hash-verified. Stored state contains fixture evidence only. HTTP simulation was inspected as historical evidence, not rerun. No runtime behavior changed. |

| 2026-10-29 | User selected the Desktop folder as the authoritative main project. Updated Desktop instructions/status and added redirects to the archived workspace. Retired workspace-to-Desktop synchronization. | Desktop runtime source hashes preserved; documentation checked in the Desktop folder. No tests rerun for this documentation-only change. Future source, tests, and status updates belong in the Desktop project. |
| 2026-10-29 | Initialized the Desktop project as a Git repository and published it to the private `Azi6060/Collective101` repository. | Initial commit `2424f10` pushed successfully to `origin/main`. No runtime tests were rerun; this was repository setup only. |
