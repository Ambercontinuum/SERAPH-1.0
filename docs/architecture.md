# Architecture

SERAPH separates four concerns: describing the manifold, resolving a proposed
transition, mediating execution, and observing consequences.

## Data flow

```text
versioned topology + current state + proposed effects
                         |
                         v
                 ManifoldCompiler
                         |
 affected-set closure + invariant certificate
                         |
                         v
               ConstraintFrame closure
                         |
                         v
 FLUX + PRP + Guardian + Environment + Distillation + Relocation
                         |
                         v
              event-local disposition
                         |
        allow / hold / repair / commit / deny
                         |
                         v
       execution permit + postcondition monitor
```

## Manifold Constraint Closure

The constraint layer is relational and transition-local.

- `ConstraintFrame` identifies the topology version, transition, and the
  topology-declared set of required relation names.
- `ConstraintObservation` identifies a named relation, scope, horizon, evidence,
  and three-state resolution.
- `ConstraintResult` preserves which relations are proven, refuted, and
  unresolved.
- `ConstraintEvaluationEnvelope` binds the public contract fingerprint, exact
  frame, exact result, and their deterministic digests for independent
  cross-process verification.
- no numeric minimum aggregates unlike dimensions
- no fixed list of privileged actor properties defines the ontology
- no global actor class receives an intrinsic right to execute
- omission of a required sensitive gate resolves as `unresolved`

An origin identifier is provenance metadata. Whether a transition is admitted
depends on its relation to the current topology, capability scope, evidence,
effects, and recovery path.

## Compiler boundary

The manifold compiler evaluates coordinate changes rather than semantic action
labels. `ConsequenceEdge` declarations belong to the versioned `ManifoldSpec`,
not the proposal. The compiler starts from the proposal's effect subjects and
computes deterministic directed reachability to a fixed point. Cycles terminate
through a visited set and ordering does not affect the normalized topology or
the resulting closure.

When affected-inhabitant closure is required:

- every reachable entity carrying the configured inhabitant role must appear
  in the proposal's exact affected set;
- every derived affected inhabitant must have an explicit functional effect,
  including an explicit no-change effect when preservation is claimed;
- extra, omitted, unknown, or unmodeled inhabitants prevent admission; and
- topology endpoints missing from observed state resolve as `unresolved`.

The resulting `AffectedSetClosure` is included in the `InvariantCertificate`.
That certificate binds:

- topology identity, version, digest, and derived affected set
- source-state digest
- functional proposal and affected entities
- evidence bundle
- expected target-state digest

Only a proven certificate can enter certified execution. Refuted and unresolved
certificates remain distinct.

`ConstraintEvaluationEnvelope` and `InvariantCertificate` are deliberately
separate. The former is the independently verifiable wire representation of a
`ConstraintFrame`. The latter is the executable transition certificate carried
inside the one-use permit. Neither object silently substitutes for the other.

This closure is only as complete as the topology and observed state supplied by
the deployment. SERAPH detects omitted paths that are present in its compiled
topology; it cannot infer a real-world dependency that the topology authority
failed to declare or a state sensor failed to expose. Closure also begins at the
effect roots declared by the proposal: SERAPH derives every modeled consequence
downstream of those roots, but it cannot discover a real effect root that the
proposal never names.

## Execution boundary

Registered capabilities bind callable identity and effect scope. Certified
permits are one-use and bind the exact code, receiver, arguments, state, and
certificate. A result is withheld until the realized state matches the expected
postcondition.

This narrows proof/execution correspondence. It does not claim that arbitrary
unregistered code or external infrastructure is mechanically confined.

## Consequence boundary

The consequence monitor keeps required checkpoints live after execution.
Missing, late, or divergent observations fail closed. Audit records are
hash-chained and may be independently anchored.

## Deployment posture

Embedded and sidecar paths may both run. Live invariant reads choose the active
path:

- embedded when the complete frame and invariant stack close
- sidecar when a required frame or invariant is open

“Active path” is routing state, not a transfer of metaphysical or global
authority.

## Downstream boundary

SERAPH exposes generic contracts. Proprietary mission topology, policy,
telemetry, product identity, and deployment results remain downstream. An
integration does not enlarge the claims verified by this repository.
