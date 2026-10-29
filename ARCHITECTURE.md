# Architecture decisions and next implementation gates

The living product aim, implementation audit, and prioritized roadmap are in [PROJECT_STATUS.md](PROJECT_STATUS.md). Read it before continuing project work and update it according to [AGENTS.md](AGENTS.md).

## Mission lifecycle

`planning → ready → running → completed | blocked`

Distribution produces a plan. Runtime validation rejects unknown tools, inappropriate departments, weak check types, unknown dependencies, and cycles. Ready tasks are assigned to available identities; independent tasks may run concurrently. Accepted dependency artifacts are passed to downstream workers. An agent's completion statement cannot create tool evidence or bypass acceptance checks.

Worker loop: request capability → receive a task-scoped grant → call the exposed tool → cite actual evidence → submit candidate result. Reviewer and deterministic checks must both accept the candidate. Unsupported tool access fails closed. Each task has at most three attempts and six worker turns per attempt. Missions have a request-count limit enforced atomically across worker threads.

## Source of authority

| Decision | Authority |
| --- | --- |
| Mission constraints | User input validated by runtime |
| Suggested plan and instructions | Planner model in live mode; explicit fixture in demo mode |
| Allowed departments, tools, check types | Runtime registry and plan validator |
| Tool grants and revocation | Runtime capability broker |
| Local calculated facts | Tool artifacts, reconciled against immutable input |
| Semantic review | Independent reviewer identity |
| Numerical/structural acceptance | Deterministic checks |
| Promotion eligibility | Persisted live evaluation evidence; proposal only |

Ranks never authorize tools. Fixture scores and loopback-simulation scores are not competence evidence. Promotion proposals do not change role, rank, or permissions.

## Revision and recovery

Operating constraints affect the budget task and its descendants. Revisions increment the mission version, clear affected current results, revoke grants, and preserve the historical artifacts and verification snapshots. Unaffected accepted data-analysis artifacts remain reusable because the input snapshot is unchanged. Dataset replacement is not supported; create a new mission for new data.

CLI access is serialized with an OS-released workspace lock. SQLite operations are protected by a reentrant lock for worker threads. This is a single-process orchestration foundation, not a distributed queue or production deployment.

## Capability integration boundary

The current gateway exposes local functions only. A future MCP adapter should implement the same broker boundary: capability lookup, connection readiness, policy decision, scoped grant, invocation, observed result, revocation. It must preserve the difference between supported-but-unconfigured, unauthorized, unavailable, and unknown capabilities.

There is no arbitrary shell execution or dynamic plugin installation in this milestone. Tool outputs and dataset text remain untrusted data; function argument validation and runtime allowlists enforce executable boundaries independently of prompts.

## Milestone acceptance

Milestone 1 is accepted when the offline end-to-end mission produces reconciled artifacts, survives an injected outage, rejects an injected wrong cost, and selectively reexecutes after changed constraints. Adapter verification requires real HTTP requests through the client against a documented stand-in. Live Meta authorization and inference are a separate gate.

Milestone 2 should establish department proposal selection and real Meta behavior before adding more mission types. Broad autonomy and all 101 agents participating are not claims made by this foundation.
