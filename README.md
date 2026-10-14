# SERAPH

SERAPH is a deterministic runtime-governance kernel for autonomous and agentic
systems. It evaluates the geometry of a proposed transition while the system is
moving: scoped constraints, trajectory coherence, recovery, containment,
coupling authenticity, and relocation.

This is the domain-neutral public research repository, migrated from a reviewed
source snapshot with fresh history. Private research archives and deployment
state are excluded. See [publication provenance](docs/publication.md).
Proprietary mission topologies and downstream products integrate through
SERAPH's contracts but are not part of the public architecture.

## Current status

The Python distribution is the `0.1.0` public research alpha, installable from
source; no PyPI or npm release is implied by this repository. The
constraint-frame wire contract is independently versioned at `1.0.0`; that
contract version is not a claim that the Python package has reached a stable
`1.0.0` release.

SERAPH includes:

- a Python governance kernel and three-valued manifold constraint layer
- a versioned manifold compiler with bound transition certificates
- registered capabilities and one-use execution permits
- postcondition and delayed-consequence monitoring
- a tamper-evident audit journal with witness anchoring
- embedded and sidecar deployment paths
- adapters for agents, pipelines, tools, delegation, coupling telemetry, and
  OpenClaw proposal/execution correlation
- a deterministic OpenClaw host-event corpus for correlation races and
  ambiguity handling
- a scenario corpus and regression suite
- Lean 4 models for constraint closure and the invariant stack

It is a research artifact and formalized prototype, not a certified production
safety system.

## Constraint model

SERAPH does not model authority as a global possession, actor class, or scalar
that can be traded between dimensions. It evaluates a versioned
`ConstraintFrame` for one transition.

Each required `ConstraintObservation` names:

- the relation being tested
- its topology and scope
- its consequence horizon
- its evidence reference
- one resolution: `proven`, `refuted`, or `unresolved`

A frame carries the topology's `required_relations` separately from its
observations. A frame closes only when every required name has a proven
observation; an omitted sensitive gate is unresolved, never silently absent.
Refuted and unresolved remain distinct so containment and recovery can respond differently.
The final execution gate is Boolean because an event either commits or does not;
that local disposition is not a binary ontology of who possesses authority.

Cross-process consumers use `ConstraintEvaluationEnvelope.evaluate(frame)`.
The envelope publishes contract version `1.0.0`, a deterministic contract
fingerprint, the complete frame and result, and separate content digests for
both. Consumers must pin the fingerprint, recompute the result, and bind the
frame identity to the event they are evaluating; the envelope does not carry
transferable authority.

```text
proposal + current topology
            |
            v
versioned constraint frame
            |
            v
proven | refuted | unresolved
            |
            v
motion + recovery + guardian + environment + coupling + relocation
            |
            v
allow | witness | repair | stabilize | commit | deny
```

## Invariant stack

```text
constraint graph   MCC              scoped transition closure
motion             FLUX             trajectory coherence
recovery           SENTINEL / PRP   perturbation response
guardian           SERAPH           protective coherence
environment        ENV              containment and reversibility
coupling           DISTILLATION     authenticity under pressure
non-traversal      RELOCATION       admissible layer transfer
```

The commit rule is:

```text
commit iff constraint_frame_closed
       and trajectory_coherent
       and recovery_not_degraded
       and guardian_coherent
       and environment_safe
       and distillation_safe
       and relocation_admissible
       and commit_requested
```

## Proposal and execution evidence

The OpenClaw adapter keeps proposed motion separate from host-reported
execution:

```text
before_tool_call  -> observed proposal + governance decision
after_tool_call   -> correlated host-reported execution
/outcome          -> success, failure, and latency for that execution
```

An allowed proposal does not enter executed trajectory merely because SERAPH
allowed it. It enters only after a matching host execution report arrives.
Ambiguous, unmatched, and duplicate reports are quarantined rather than guessed
into trajectory or recovery evidence. See
[`adapters/openclaw/README.md`](adapters/openclaw/README.md).

This is an observation and correlation contract, not proof of undocumented host
behavior. Live-host verification must still test retries, parallel calls,
missing hooks, ordering, subagents, and terminal-policy interactions.

## Quick start

```bash
python -m pip install -e ".[serve,test]"
python -m seraph --pretty
python -m seraph_demo
python -m pytest -q
```

Start the HTTP sidecar:

```bash
seraph-serve
```

Minimal Python use:

```python
from seraph import ConstraintFrame, GovernanceInput, PRPScore, PRPTrail, govern

trail = PRPTrail()
trail.push(PRPScore(0.0, 1.0, 1.0))

decision = govern(
    GovernanceInput(
        constraints=ConstraintFrame.closed(
            "release",
            topology_id="example.release",
            evidence_ref="release-checks",
        ),
        trajectory=("review", "review", "commit", "commit"),
        prp_trail=trail,
        request_commit=True,
    )
)
print(decision.decision.value)
```

`ConstraintFrame.closed()` is a convenience for trusted local fixtures and
declared adapter profiles. It does not prove that a declaration corresponds to
reality. Production mediation must bind observations to independent evidence,
current state, executable identity, arguments, and realized postconditions.

## Repository map

- `seraph/` — kernel, constraint layer, manifold compiler, server, audit
- `seraph/examples/` — installable governance decision fixtures
- `adapters/` — agent, pipeline, tool, capability, delegation, telemetry, and
  [OpenClaw](adapters/openclaw/README.md) adapters
- `formal/` — Lean 4 model, aggregated by `SeraphFormal.lean`
- `tests/` — executable regression and mediation tests
- `validation/` — installable runtime-governance evidence harness
- `seraph_demo/scenarios/` — installable expected-outcome governance traces
- `seraph_demo/` — scenario runner and operator trace
- `docs/architecture.md` — component boundaries and data flow
- `docs/spec.md` — canonical runtime contract
- `docs/manifold_compiler.md` — compiler and trust-boundary details
- `docs/validation.md` — bounded adversarial corpus, evidence contract, and
  claim boundaries
- `docs/design_lineage.md` — foundations, differentiation, and honest claim
  boundaries
- `docs/demo/` — static proof-surface demo backed by generated SERAPH evidence

## Reproducible validation

Run the public runtime-governance corpus:

```console
python -m validation.runtime_governance
python -m validation.runtime_governance --json
python -m seraph_demo.web_export
```

The web exporter regenerates `docs/demo/seraph-demo-data.js` by running the
actual manifold compiler and consequence monitor. The static page renders that
fixture and does not reimplement adjudication in JavaScript.

The current corpus exercises safe admission, semantic laundering, unknown
effects, direct and topology-derived inhabitant omission, exact affected-set
closure, aggregate compensation, evidence absence,
unadmitted origin, permit replay, callable and argument substitution, stale state,
immediate and delayed postcondition divergence, missed observations, and
audit-receipt tampering.
OWASP identifiers in its report mark relevant control surfaces, not complete
threat-class mitigation or certification. See
[`docs/validation.md`](docs/validation.md) for the comparison contract and
explicit limits.

## Formal verification

Install [Elan](https://lean-lang.org/install/), then run:

```console
cd formal
lake build
lake env leanchecker
```

Elan selects the Lean version pinned in `formal/lean-toolchain`. CI performs a
cache-cold Lake build and independently replays the newly generated proof
artifacts with `leanchecker`; `.lake` artifacts are not restored across formal
CI runs.

`formal/AffectedClosure.lean` models topology-owned directed reachability,
proposal-declared roots, exact affected-inhabitant coverage, explicit effect
coverage, and whole-topology observation. It proves that any one omitted,
extra, unmodeled, or unobserved relation prevents an affected-set certificate.
The proof relation is independent of list presentation order.

## Verification boundary

The Python suite validates implemented runtime behavior. The Lean model proves
properties of its formal definitions. A Lean proof is not by itself a proof
that arbitrary Python execution or external side effects correspond to that
model, nor does the current model prove that Python's fixed-point algorithm
refines Lean's inductive reachability relation. Certified mediation narrows this
gap by binding code, arguments, state, certificate, and result, but
deployment-level confinement and evidence quality remain explicit trust
boundaries.

## License

Copyright (C) 2026 Amber Anson / Ambercontinuum Research.

The kernel, adapters, tests, and tooling are AGPL-3.0. Commercial use requires a
separate license. Lean proofs in `formal/` are additionally available under
CC BY 4.0 for academic use with attribution.

Required attribution:

> Amber Anson / Ambercontinuum Research — SERAPH: Invariant Architecture for AI-Era Governance
