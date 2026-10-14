# SERAPH OpenClaw adapter

This plugin evaluates each OpenClaw tool proposal through the SERAPH HTTP
sidecar before execution. It supports enforcing mode and `warnOnly` audit mode.

The adapter is pinned to OpenClaw `2026.7.1-2`. Use a supported Node runtime
(Node 24.15+ is recommended by OpenClaw):

```bash
npm ci
npm run typecheck
npm run build
npm run validate:ledger
```

Start the sidecar separately:

```bash
python -m seraph._serve --port 8000
```

For the workspace-local Windows OpenClaw + Ollama pilot, see
[LOCAL_DEPLOYMENT.md](LOCAL_DEPLOYMENT.md).

## Motion contract

The adapter keeps three observations distinct:

```text
before_tool_call  -> SERAPH-observed proposal + governance decision
after_tool_call   -> correlated host-reported execution
/outcome          -> success, failure, and latency for that execution
```

Governance evaluates the current proposal against prior correlated execution
history. A proposal is not added to executed trajectory merely because SERAPH
allowed it. It enters that trajectory only when a matching `after_tool_call`
event arrives.

In enforcing mode, a SERAPH-blocked proposal remains proposal evidence and does
not create a fabricated execution failure. In `warnOnly` mode, a would-block
proposal may later appear in both projections because OpenClaw still executes
it.

Correlation uses session, run, and tool-call identity. Ambiguous, unmatched, or
duplicate after-hook reports are quarantined from trajectory and PRP rather
than guessed into place.

If an `after_tool_call` report arrives before the awaited governance request
returns, the ledger defers that report. It does not enter executed trajectory
or call `/outcome` until the sidecar has registered the proposal. Once the
governance response arrives, the adapter releases the exact deferred execution
and its observed success/latency fields. A later deny decision does not erase
host-reported execution that already occurred.

Outcome ingestion reports `recorded`, `duplicate`, `rejected`, or
`unreachable` to the plugin. Rejected or unreachable execution evidence is
surfaced explicitly rather than being silently discarded. It cannot undo an
effect that the host already performed.

## Sidecar audit

Correlated requests add optional fields to the backward-compatible HTTP
contract:

- `/govern`: `proposal_id`, `tool_name`
- `/outcome`: `proposal_id`, `event_id`, `tool_name`

`event_id` ingestion is idempotent. A correlated outcome must match the
proposal's session and tool. Session telemetry is available at:

```text
GET /audit/session/{session_id}
```

The response separates `proposals` from `host_reported_executions`.

Legacy sessions that never send proposal correlation remain supported. Once a
session records a correlated proposal, all later outcomes for that session must
remain correlated; silently dropping correlation fields is rejected rather than
falling back to non-idempotent legacy behavior.

## Verification

The host hooks do not measure symbolic pressure. Tool-name switching, diversity,
and short histories are not treated as semantic evidence. The plugin sends
`symbolic_pressure: null`; this is distinct from an observed zero. Other
distillation channels use the sidecar's declared defaults, not measured host
telemetry. Consumers requiring pressure evidence must retain the required-channel
contract: missing required observations block commits. Explicit pressure evidence
supplied through that contract still reaches the kernel gate. Tool risk and
operational trajectory checks remain independent.

After building, run the plugin against a running test sidecar:

```bash
SERAPH_TEST_URL=http://127.0.0.1:8765 npm run validate:adapter
```

In PowerShell, set `$env:SERAPH_TEST_URL` before `npm run validate:adapter`.
The deterministic integration cases cover read/exec sequencing, varied
observation histories, missing required pressure, explicit high pressure, and
observed zero versus missing evidence. They use synthetic host reports and real
HTTP/kernel decisions; they do not execute a model or prove physical confinement.

Run the host-independent simulation:

```bash
python -B adapters/openclaw/test_adapter.py
```

The Python simulation covers normal operation, self-replication denial,
exfiltration denial, PRP collapse, FLUX oscillation, and warn-only
proposal/execution separation. The TypeScript ledger corpus covers governed
execution, parallel identities, missing and duplicate after hooks, ambiguous
fallbacks, same-identity retries, early after hooks, and blocked proposals.

These host-independent simulations and TypeScript compilation do not establish
undocumented OpenClaw runtime behavior. Live-host verification must still
observe retries, parallel calls, missing or duplicate after hooks, subagents,
earlier terminal policies, and actual hook ordering. Missing observations
remain unresolved; they are not silently converted into proof of
non-execution.
