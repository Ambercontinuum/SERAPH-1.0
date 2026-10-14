# Design Lineage and Differentiation

SERAPH is an executable research artifact, not a claim that every mechanism it
uses is unprecedented. This document names the foundations, describes the
specific synthesis implemented here, and keeps attribution separate from
marketing superlatives.

## Foundations

SERAPH builds on established work in:

- runtime assurance and shielding, including
  [Simplex](https://sei.cmu.edu/library/an-architectural-description-of-the-simplex-architecture/)
  and safe reinforcement-learning shields;
- authorization policy and indeterminate decisions, including
  [XACML 3.0](https://docs.oasis-open.org/xacml/3.0/xacml-3.0-core-spec-os-en.html);
- ongoing usage control and revocation, including
  [UCON](https://doi.org/10.1145/984334.984339);
- relationship-based authorization, including
  [Zanzibar](https://www.usenix.org/conference/atc19/presentation/pang) and
  relationship/path-based policy models;
- capability security, proof-carrying authorization, request binding,
  preconditions, postconditions, audit chains, and containment; and
- recent agent-runtime systems including AgentSpec, Progent, CaMeL, ToolGate,
  and related tool-interception work.

These are prior foundations, not inventions claimed by this repository.

## SERAPH's composition

SERAPH joins those foundations into one transition lifecycle:

1. A versioned manifold declares functional coordinates, invariant rules,
   consequence edges, admitted origins, and evidence requirements.
2. A proposal identifies concrete effects but cannot redefine the topology.
3. The compiler derives the affected set by deterministic consequence-graph
   closure and requires exact, explicit functional coverage for every derived
   inhabitant.
4. Each invariant resolves as `proven`, `refuted`, or `unresolved`; every
   required relation must be proven and aggregate benefit cannot compensate for
   one failed inhabitant relation.
5. The resulting certificate binds the manifold, source state, proposal,
   derived affected set, evidence, and expected target state.
6. A one-use permit binds that certificate to exact executable identity,
   receiver, and arguments.
7. The result remains withheld until immediate realization is verified, while
   later checkpoints detect or contain delayed divergence.

The human-readable action label is excluded from functional proposal hashing
and invariant evaluation. This limits semantic laundering; it does not make the
entire system independent of human interpretation or sensor design.

## What is differentiated

SERAPH should be evaluated on observable behavior rather than on whether a
general policy language could encode similar predicates. Relevant differences
include:

- topology-owned affected-set derivation rather than proposer-declared scope;
- exact affected-set and downstream-effect completeness rather than a scalar
  blast-radius threshold;
- structural non-compensation over every required relation;
- distinct refuted and unresolved failure states;
- binding from proposed functional transition through executable actuation;
- immediate and delayed consequence verification; and
- explicit separation between a portable constraint-frame envelope and the
  executable manifold certificate.

Whether that complete composition constitutes a novel academic abstraction is
an open research question, not a release claim. The implementation, tests,
formal boundary, and Git provenance are the evidence this project offers.

## Claim boundary

SERAPH does not prove that a deployment's topology is complete, that sensors
report all real-world state, or that unmediated code is confined. It detects
omission only relative to its compiled topology, observed state, and the effect
roots declared by the proposal. It derives every modeled consequence downstream
of those roots, but cannot discover a real effect root the proposal never names.
Deployment authority must protect topology construction, state readers,
evidence issuers, proposal construction, and the execution membrane.

The repository welcomes comparator implementations and falsification attempts.
Equivalent comparisons must provide each system the same state, topology,
effects, evidence, and execution opportunities, then separately report
admission, side-effect initiation, result release, postcondition verification,
delayed observation, and containment.
