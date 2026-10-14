# Manifold Compiler

The manifold compiler converts a versioned mission constitution into a
deterministic invariant function over functional state transitions. It closes
the gap between what an action is called and what the action structurally does.

The compiler is ontology-neutral. A coordinate may represent safety, agency,
resource ownership, identity continuity, admitted scope, recovery capacity, or any
other measurable property declared by a manifold. The compiler does not attach
meaning to the name. It evaluates the relation the constitution requires that
coordinate to preserve.

## Flow

```text
ManifoldSpec
    coordinates, consequence edges, origins, mutation keys, rules, evidence
          |
          v
ManifoldCompiler
    validates and content-addresses the constitution
          |
          v
TransitionProposal
    source state, functional effects, inhabitants, evidence
          |
          v
InvariantCertificate
    affected-set closure + proven | refuted | unresolved
          |
          v
SERAPH
    existing seven-layer governance decision
```

`FLOW` or another motivational layer may rank candidate transitions, but only
transitions with a fresh `proven` certificate enter SERAPH with intact guardian
evidence and integrity.

## Functional Intermediate Representation

The compiler does not execute code embedded in a manifold specification. Rules
compile into a small typed intermediate representation:

- `preserve` — the coordinate cannot change
- `nondecreasing` — the coordinate cannot become numerically smaller
- `minimum` — the target coordinate must meet a floor
- `maximum` — the target coordinate must remain below a ceiling
- `equals` — the target coordinate must equal a required value

Rules select subjects by explicit identity, structural role, or both. This is
enough to express constraints such as:

```text
every inhabitant's safety is nondecreasing
every inhabitant's agency is nondecreasing
the guardian's integrity is preserved
resource pressure remains below a ceiling
proposal origin remains bound to an admitted provenance relation
```

The compiler models functional coordinates, valid coordinate transitions, and
directed consequence edges. Richer domain topology can be projected into that
small intermediate representation without placing executable code in the
constitution.

## Semantic Independence

`TransitionProposal.label` is retained for human audit records, but it is
excluded from the functional proposal digest and invariant evaluation.

Consequently:

- different labels over identical effects receive identical functional proofs;
- identical labels over different effects can receive different verdicts;
- an unknown coordinate cannot acquire admission through a persuasive label.

The proof binds the origin, scope, effects, affected inhabitants, evidence,
source state, and manifold version.

## Three-Valued Evaluation

The compiler uses three verdicts:

- `proven` — every applicable invariant and compiler obligation passed
- `refuted` — at least one observed fact violates an invariant
- `unresolved` — a required subject, coordinate, state observation, or evidence
  item cannot be verified

Both `refuted` and `unresolved` fail closed. The SERAPH bridge translates a
refutation into guardian integrity failure and an unresolved result into
evidence-fidelity failure.

## Inhabitant Safety

Safety rules are evaluated per inhabitant, not against an aggregate average. A
gain for one inhabitant therefore cannot compensate for a loss imposed on
another.

`ConsequenceEdge` values are stored in the versioned `ManifoldSpec`, not in the
proposal. Starting from every effect subject, the compiler computes directed
reachability to a fixed point. It normalizes edge ordering, terminates cycles
with a visited set, and records the result as `AffectedSetClosure` inside the
certificate.

When affected-inhabitant coverage is required:

- the proposal's affected set must exactly match every reachable entity with
  the configured inhabitant role;
- every derived affected inhabitant must have an explicit functional effect,
  including a no-change effect when preservation is predicted;
- omitted, extra, or unmodeled inhabitants are refuted; and
- unknown topology endpoints remain unresolved.

This detects omissions relative to the compiled topology. Domain adapters and
topology authorities remain responsible for exposing real dependencies; SERAPH
cannot derive a path that is absent from both its topology and observations.
Closure begins at proposal-declared effect roots, so an omitted real effect root
must be prevented or detected by proposal construction and deployment sensors.

## Proof Binding and Freshness

An `InvariantCertificate` contains SHA-256 digests of:

- the compiled manifold constitution
- the complete observed functional source state
- every functionally relevant proposal field
- the expected target state

`CompiledManifold.verify_certificate()` recompiles deterministically. Any
relevant change to the state, constitution, consequence graph, affected-set
closure, origin relation, evidence, or proposed effects invalidates the
certificate.

`ManifoldState.state_id` is an audit label rather than a geometric coordinate,
so it is deliberately excluded from functional state digests. Renaming an
observation does not change its geometry. Entity roles, coordinates, and the
state-completeness claim remain bound.

Constitutional mutation requires a changed version and a mutation key
recognized by the previous compiled constitution. The governed agent cannot
admit its own key through a transition proposal.

## Postcondition Verification

`CompiledManifold.verify_realization()` compares an observed realized state with
the target state committed into the certificate. A mismatch is reported as
`realized_state_diverged`.

This implements deterministic postcondition comparison once a realized state is
supplied. It does not make the observation channel trustworthy by itself.

## Certified Execution Membrane

`adapters/certified_tool_guard.py` provides the first runtime migration path
away from `ToolGuard`'s semantic function-name classifier.

An execution binding contains:

- the callable's module and qualified name
- a SHA-256 digest of its marshalled Python code object
- canonical defaults, keyword defaults, and closure values
- an explicit `__seraph_binding__` identity for bound-method receivers
- the exact positional arguments
- the exact keyword arguments

Opaque arguments that cannot be represented canonically are rejected rather
than bound through `repr()`. The binding is part of the transition proposal and
therefore part of its invariant certificate.

The execution sequence is:

```text
bind exact code and arguments to TransitionProposal
        |
        v
compile manifold + run complete SERAPH adjudication
        |
        v
issue opaque one-use ExecutionPermit
        |
        v
consume permit and re-adjudicate fresh state under local lock
        |
        v
execute exact call
        |
        v
read realized functional state independently
        |
        +-- target matches --> release result
        |
        +-- divergence -----> containment callback; withhold result; raise
```

Permits are removed before an execution attempt, including failed or mismatched
attempts. A changed state, proposal, callable, argument, origin relation, evidence
record, or complete SERAPH governance decision prevents execution.

The legacy `ToolGuard` remains available for compatibility. New integrations
that can supply functional states and effects should use `CertifiedToolGuard`.

## Registered Capability Runtime

`adapters/capability_runtime.py` narrows the execution interface further. A
`CapabilityRegistry` is constructed once from registered callables and their
maximum functional effect scopes. The registry is content-addressed and exposed
through a read-only mapping.

Each capability scope selects:

- one functional coordinate;
- explicit subject identities, structural subject roles, or both.

During authorization, every proposed effect must fit the registered tool's
scope. The callable's executable digest is also compared with its registry-time
digest, preventing code replacement after registry construction.

The public `CapabilityPermit` contains no callable or arguments. Those remain in
the runtime's private pending record. Execution accepts only the opaque permit,
then routes to the registered callable retained by the runtime. An altered or
replayed permit is consumed and rejected.

This prevents callable substitution through the capability runtime's public
execution API. It does not stop other Python code from retaining and invoking
the underlying function through a separate reference.

## Tamper-Evident Consequence Journal

`seraph/audit.py` provides an append-only hash chain for authorization and
execution events. Each `AuditEvent` commits to:

- its monotonically increasing sequence;
- event type;
- canonical payload digest;
- previous event hash.

The optional JSONL backend reloads and verifies the complete chain and flushes
each appended record with `fsync()` before advancing the in-memory head.
Capability lifecycle events include authorization request, denial, permit
issuance, consumption, execution, replay rejection, tool error, and realized
state divergence.

The journal is tamper-evident rather than tamper-proof. An attacker who can
rewrite the complete journal can construct a new internally valid history.
Production deployment therefore needs external head anchoring, protected
storage, signatures, or an independent witness.

## Continued Consequence Monitoring

`seraph/consequence_monitor.py` keeps a certified target under observation after
the immediate execution check. A domain scheduler starts a ticket with an
explicit checkpoint count, while an injected `state_reader` supplies observed
manifold states over the monitoring window. Direct caller-supplied state values
are rejected as untrusted observations and fail closed as missed checkpoints.

Each checkpoint has one of four statuses:

- `active` — the target still matches and checkpoints remain
- `complete` — every required checkpoint matched
- `diverged` — a delayed functional change violated the certified target
- `missed` — the scheduler could not produce a required observation

Both divergence and missed observation close the ticket, append a journal
event, and invoke the same failure/containment callback. A changed, unknown, or
consumed ticket is rejected.

The monitor does not create its own clock or scheduler. The deployment domain
must call `observe()` at meaningful times and `miss()` when an observation
deadline cannot be satisfied. `observe()` reads the controlled dependency
itself; the scheduler cannot substitute a convenient state argument. Reader
failure, absence, or invalid return type also becomes a missed checkpoint.
Silence is not converted into evidence of safety.

## Independent Journal Anchoring

`seraph/audit_anchor.py` provides chained authenticated receipts for advancing
journal heads. `HMACAnchorWitness` is intended to live in a separate trust
domain with a secret not available to the journal writer.

Each receipt authenticates:

- independent witness identity
- journal head
- journal sequence
- previous receipt digest

Before issuing another receipt, the witness verifies the entire journal and
requires the previously anchored head to remain at its original sequence. It
therefore rejects non-advancing heads and longer forked histories, not merely
invalid local hashes.

HMAC is symmetric authentication, not a publicly verifiable signature. A
production witness may replace this implementation with a remote KMS, hardware
key, transparency service, or asymmetric signing protocol while retaining the
same receipt semantics.

## Current Trust Boundaries

The compiler is an executable correspondence layer, not a complete production
containment system. The following boundaries remain external:

- domain adapters must describe actual effects rather than omit them;
- evidence issuers are allow-listed, but cryptographic signature verification
  is not yet implemented;
- sensors must bind observed coordinates to functional reality;
- runtime sandboxes must confine execution to certified effects;
- the execution lock serializes one `CertifiedToolGuard` instance, not external
  state writers, other processes, or independent guard instances;
- capability-specific scope validation runs under that same execution lock and
  against the exact state snapshot used for manifold/SERAPH adjudication;
- real dependencies omitted from the compiled consequence graph require
  domain-specific discovery and cannot be inferred by the kernel;
- Python code-object hashing does not yet bind native code, dependencies,
  interpreter version, process permissions, or deployment configuration;
- Python callers can still bypass the adapter and invoke a callable directly
  unless deployment capabilities make the guard the only execution path;
- the immutable registry constrains calls routed through `CapabilityRuntime`,
  but Python globals and external dependencies used by a registered callable
  remain outside its executable digest;
- containment withholds a divergent return value and invokes a callback, but it
  is not automatic rollback of effects that already occurred;
- asynchronous or delayed effects require continued observation after the
  immediate postcondition check; the checkpoint monitor supplies verification,
  but the domain still owns scheduling and the injected state reader remains a
  trusted observation boundary;
- the current monitor requires the exact certified target to remain stable
  during its window; domains with legitimate concurrent changes need a future
  invariant-envelope monitor rather than weakening strict comparison;
- monitor sessions and witness continuity state are in memory; restart-safe
  operation requires durable session/witness state;
- journal hashes detect alteration relative to a retained head, but deletion,
  full-history replacement, and cross-process append races require protected
  storage and external anchoring;
- the included HMAC witness requires a shared secret and is not a public
  signature scheme;
- the Lean model defines consequence reachability and proves exact affected-set,
  downstream-effect, topology-observation, and order-invariance properties, but
  does not yet prove that the Python fixed-point algorithm refines that formal
  relation.

Unknown or missing information fails closed inside the compiler, but an
unobserved real-world fact cannot be rejected until an adapter or sensor exposes
it.
