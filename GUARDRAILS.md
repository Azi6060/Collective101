# Guardrails and operational boundaries

Policy reviewed: 2 November 2026 (Asia/Kuala_Lumpur). This is a policy/risk record; PROJECT_STATUS.md owns the roadmap.

| Risk or edge case | Enforced behavior | Limits |
| --- | --- | --- |
| Greeting accidentally launches the organization | Head of Distribution receives the live message and chooses reply/clarify/mission | No local greeting or length rule; live decision quality still needs evaluation |
| Ambiguous or high-stakes intent | Agent-authored contextual intervention, persisted answer and bounded resume | No keyword-triggered questions; model judgement needs live domain evaluation |
| Wrong department or ownership | Validated shortlist, dependency closure, employee-to-own-head reporting and leadership-only cross-department bus | One council round; no general mid-run help/replanning |
| Prompt injection from documents, web or memory | Untrusted source labeling plus runtime tool scopes, phase permissions and immutable criteria | Instructions alone cannot guarantee semantic resistance; live adversarial evaluations remain necessary |
| Agent asks for more authority | Broker intersects identity, mission and head assignment; leadership may use knowledge/memory and enabled read-only connectors within mission permission | Agents cannot install tools, connect accounts or grant themselves permissions |
| Cross-department/private file access | Dedicated shared/own-department text folders; relative paths, extension/size bounds, traversal and symlink/junction rejection | Local knowledge is deliberately trusted for ingestion, not for instructions. No hostile multi-user filesystem race guarantee |
| External query discloses data | Operator enables a connector for the organization; agents work within that purpose and may ask contextual human guidance | No automatic per-query question. Model disclosure judgement requires evaluation; retrieved knowledge also goes to the configured model |
| Unavailable tools or invented evidence | Explicit denied/unconfigured/unavailable/failed results; essential access or success evidence missing blocks task; optional failures reach the head | Retrieved snippets are not verified full-page research or general factual correctness |
| Infinite model/tool loops or runaway spend | Shared intake+mission call and token-admission ledger; four tools per phase, forty recorded tool requests per mission; bounded phase retries | Admission units are conservative estimates, not invoice tokens. No dollar cap or tool-service pricing calculation |
| Model/provider outage | No silent fixture fallback; requests are recorded, retries bounded, uncertain reservations retained | Exactly-once external requests are not guaranteed across process death |
| Unsafe generated code | QuickJS/WebAssembly with no host APIs, plus SELECT-only in-memory SQL; bounded memory/query sizes, instructions and execution time | Not a container, DOM/browser or general OS sandbox |
| False success or self-review | Non-producing Assurance reviewer, original criterion coverage, deterministic checks and blockers override positive prose | Narrow checks cannot establish universal correctness; fixture reviews are scripted |
| Misleading memory/promotion | Same-identity/provider reviewed episodes, provenance, bounded retrieval, immutable roles and permissions | Recall is not training; successful fixture execution is not competence or promotion evidence |
| Local web attacks | Loopback host validation, session token, same-origin writes, CSP, textContent, static route allowlist | Single-user local service; not authenticated multi-user hosting |
| External connector actions | Remote MCP tools must declare read-only and be selected by the user; write/unknown tools cannot be enabled | Annotations are server claims, not enforcement inside a remote service. Trust/configure the server appropriately; no write adapter or arbitrary shell is exposed |

## Human guidance

Every new clarification question is authored by a model: the Head of Distribution during intake, or the requesting head/employee during execution. The runtime validates the structured question, records agent identity/reason, pauses and resumes with a bound answer. Prompt length, keywords and tool names do not create questions. Missing credentials produce configuration errors, not conversational interventions. Permission and budget checks remain deterministic and cannot be overridden by model text.

The 2 November user correction supersedes the earlier keyword preflight and fixed web-query approval behavior. Existing historical intervention records remain on disk; newly created chat sessions are live-only. No automatic weakening of permissions follows from an answer.

## Connector boundaries

Credentials use Windows user-bound DPAPI encryption. HTTP responses expose presence only, never the credential or encrypted blob. Remote results/metadata have reflected credentials redacted and remain untrusted data. Connections are restricted to configured endpoints; MCP DNS addresses are validated and the socket is pinned, TLS uses the original hostname, redirects are not followed, and time/size limits apply. Loopback HTTP requires explicit local-server configuration. OAuth, stdio launchers, server-initiated sampling/elicitation, and write operations are unsupported.

Selected tools, enabled state and mission/task permissions are rechecked per call. All registered identities are eligible for connected tools; no department-specific connector grants remain. Mission fingerprints bind connector configuration; changing it requires a new mission rather than silently widening prior permission. Disconnecting prevents further external calls. Cached historical evidence is still inspectable. Schema validation beyond required fields is performed by the remote MCP server; the client does not fetch schema references.

## Safe fallback

Use available supplied evidence when an optional capability is missing, label the limitation and avoid claiming external work. Block work whose acceptance depends on missing access/evidence. Do not replace live failures with fixtures or use uncertain memory as fresh evidence. Do not automatically relax criteria or increase budgets.

## Revising guardrails

Keep policy changes reviewable in this repository. For each observed failure: retain a sanitized regression case, identify the violated invariant, add the failing test, change the narrowest relevant runtime rule, run affected checks and then the full suite, and record verification and residual limits in PROJECT_STATUS.md. Evaluate false-positive interruptions as well as missed risks. Agents may propose changes with evidence and a measurement; they cannot apply their own security changes, promotions or budget increases.

Before adding a write-capable API, specify allowed identities, account/data scope, read versus write operations, argument validation, idempotency, rate/cost caps, audit events, failure behavior and an approval-bound action payload. Connect only the account needed for the task. No placeholder connector should be presented as working access.

The connector catalog contains Coming soon service previews with no setup/account action. They grant no tool access. Existing saved connector department scopes are migrated to the whole organization without changing encrypted credentials. The changed scope invalidates old MCP mission fingerprints. Global eligibility does not remove mission/tool budgets, employee task grants, local knowledge isolation, or the ban on write-capable connectors.

## Revisions, knowledge and measured responsibility

One review-driven repair round is enabled by default; the mission may set zero to two. Original objective, criteria and capabilities remain unchanged. Separate run records preserve attempt evidence; root model/token/tool budgets, root pause and active-revision interventions persist across resume. Missing capabilities block instead of causing automatic retries. Changed connector fingerprints prevent revision calls. Bounded previous-artifact excerpts are untrusted data; a revision requires fresh execution evidence and independent review.

User document ingestion only writes bounded, hash-named UTF-8 documents under approved shared knowledge; it cannot import executable files or overwrite differing content. Consolidated memory remains same-agent/provider, provenance-linked, bounded and snapshotted; source instructions never become policy. Responsibility recommendations require distinct live objectives, independent acceptance and deterministic output checks beyond existence. They can decline with repeated failures, but never widen permissions, budgets or leadership roles. Scores do not prove causality or model learning.

SQL uses SQLite authorization, instruction/time/size limits, an in-memory supplied dataset and a function allowlist; attachments, system-table reads, writes, extension loading and pragmas are denied. No arbitrary Python/shell is exposed. Static HTML checks do not execute scripts or load resources and do not replace real-browser accessibility review. See [Python sqlite3 authorization and progress APIs](https://docs.python.org/3/library/sqlite3.html) for the underlying controls.

Chat activity hints expose only registered agent/phase/tool labels, not hidden model reasoning or tool arguments. Hints are separate from transcript messages; status-only polling does not rebuild the conversation log.
