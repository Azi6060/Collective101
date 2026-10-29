# Collective 101

**Main project folder: `C:\New folder\Desktop\collective101`.** This is the user-selected authoritative working copy. Run commands and maintain the status file here.

A local implementation foundation for a departmental AI organization. The generated roster contains **101 persistent identities across ten departments plus a mission director**. The first supported mission is intentionally bounded: analyze supplied event records, produce a constrained operating plan and draft brief, and assemble evidence-linked deliverables.

**Status: milestone 1, not the completed hackathon submission.** The supplied demonstration uses a deterministic fixture provider. It performs real calculations, scheduling, access checks, persistence, rejection, and recovery; it does not perform AI inference. Live Meta execution is a separate explicit mode and still needs verification with your account.

**Read [PROJECT_STATUS.md](PROJECT_STATUS.md) first for the agreed aim, audited feature status, gaps, next work, and change log.** [AGENTS.md](AGENTS.md) requires this file to be read and maintained whenever project work continues.

## Run immediately

Requires Python 3.11 or later. The runtime has no third-party Python dependencies. From this folder:

```powershell
python -m collective101 demo --inject-outage --inject-bad-cost --output runs/first-mission
```

Open `runs/first-mission/report.html`. The report is a self-contained exported document, not a live dashboard. `mission.json` contains the mission board, roster, and execution events. Accepted machine-readable deliverables are in `artifacts/`.

The demonstration deliberately makes one operating-plan tool call unavailable and corrupts one candidate cost. The scheduler must reassign the failed attempt, and independent verification must reject the wrong cost before the mission completes. Both injections are marked as simulations in the event trail.

The supplied CSV contains four example events, 320 registrations, and 240 attendees. The historical mean is 60 attendees. With the default constraints, the operating plan supports 60 people at a cost of 400 currency units against a budget of 500. The mean is explicitly not presented as a validated forecast.

## Change the mission constraints

Use the mission ID printed by the first command:

```powershell
python -m collective101 revise MISSION_ID --provider fixture --budget 260 --capacity 35 --output runs/revised-mission
```

The budget, brief, and final digest are invalidated and recomputed. Input profiling and attendance analysis remain valid and are reused. Prior tool artifacts and verification snapshots remain in SQLite. The new plan supports 32 attendees for 260 currency units.

```powershell
python -m collective101 resume MISSION_ID --provider fixture
python -m collective101 report MISSION_ID --output runs/export
python -m collective101 registry
```

The CLI locks its state workspace against concurrent commands. Completed missions are not reexecuted by `resume`. An interrupted running task is reset for another attempt, up to three attempts total. Non-retryable failures and exhausted budgets remain blocked; they are not reported as successful missions. Revision does not refill the mission's call budget.

## Live Meta mode

Set `MODEL_API_KEY` securely in your shell environment, then run:

```powershell
python -m collective101 run --provider meta --input examples/attendance.csv --budget 500 --capacity 100
```

`META_MODEL` optionally selects a model; the current default is `muse-spark-1.3`. No `.env` file is automatically loaded. Never commit a key or pass it as a command-line argument. `.env.example` only documents variable names.

The adapter uses `https://api.meta.ai/v1/chat/completions`. It handles function tool calls, returns matching tool-call IDs, rejects truncated/malformed responses, and classifies 429/server/connection errors for bounded task retries. There is no silent fallback to fixture mode. Each request permits up to 4,096 output tokens. A mission has a hard request-count limit (`--max-calls`, default 64); provider-reported token usage is recorded. Dollar cost and total token usage are not enforced spending ceilings.

Live planning remains restricted to the five registered local tools. It may choose task names, ordering, department routing within the permitted charters, and instructions, but cannot add arbitrary capabilities or weaken the acceptance checks. Free-form missions, networked MCP connections, and general code execution are not implemented in this milestone.

## What is implemented

- Generated agent profiles using department charters and role templates.
- A SQLite mission board, immutable input snapshot, dependency graph, event trail, tool artifacts, and result history.
- Parallel execution of independent tasks with bounded concurrency (default 4; range 1–16).
- A runtime capability broker that checks both the department charter and current assignment before granting a local tool.
- Grants bound to a mission/task/agent and revoked at the end of every attempt.
- An independent reviewer identity plus deterministic acceptance checks against source data and current constraints.
- Bounded retries and reassignment after supported failures.
- Selective invalidation after budget/capacity/cost changes.
- Persisted evaluation records and conservative promotion **proposals** after at least five live-mode evaluations across two missions with at least 85% acceptance. Proposals require review, do not change permissions or rank, and are an initial heuristic, not a calibrated competence measure.
- A self-contained report showing real recorded state. No fake live animation or claim that all 101 identities ran.

Fixture and loopback HTTP-simulation evaluations cannot generate promotion proposals. Individual memory namespaces are declared in profiles; long-term memory retrieval and learned routing are future work. Tool grants and broker events are deterministic runtime policy actions, not a claim that an LLM autonomously installed software.

## Verify locally

```powershell
python -m unittest discover -s tests -p 'test_*.py' -v
```

The tests cover cross-task access rejection, grant revocation, concurrent call-limit enforcement, corrupted artifact rejection, outage recovery, constraint-change invalidation, persistence, infeasible constraints, and report escaping.

For actual HTTP serialization and provider failure handling, run the Postman contract simulation in one terminal (Postman CLI 1.75.0 was used):

```powershell
postman simulation run postman/simulations/meta-contract.sim.yaml --port 4010 --no-history --output ndjson
```

In another terminal:

```powershell
python tests/check_http_simulation.py --url http://127.0.0.1:4010
```

This runs the actual adapter and mission runtime against local stand-ins, then exercises 503, 429, timeout, invalid JSON, and truncated-output cases. The mock derives from the documented request/response shape; it is not Meta's own mock. It does not establish model reasoning quality, live authorization, latency, account limits, or production compatibility. No cloud workspace, deployment, or real Meta key is required. Postman may initialize its own local cache on first use.

The consumer contract is `contracts/meta-chat-completions.openapi.json`. Simulation assumptions and test evidence are in `postman/simulations/meta-contract.context.yaml`.

## Next implementation milestones

The maintained roadmap and acceptance criteria live in [PROJECT_STATUS.md](PROJECT_STATUS.md). The immediate product priority is generic mission intake and department contribution proposals. Live Meta validation is a parallel gate when a participant key is available. MCP connections, memory, responsibility growth, a live interface, and benchmarks follow the milestone gates recorded there.

## Sources and boundaries

- Meta tool-calling documentation: https://dev.meta.ai/docs/tool-calling
- Meta model catalog: https://dev.meta.ai/docs/models
- MCP tools specification: https://modelcontextprotocol.io/specification/latest/server/tools
- Inspiration: https://github.com/Shubhamsaboo/awesome-llm-apps

This implementation was written for this workspace; no code was copied from the inspiration repository. Orbit discovery was attempted but its hostname did not resolve in this environment; the adapter instead follows Meta's primary documentation. No authenticated owner-mock search was performed because no Postman workspace or session was selected for the project. The local stand-in and consumer subset are explicitly maintained here.
