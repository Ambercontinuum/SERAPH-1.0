# Human Operator Coupling

SERAPH may be paired with a human operator through a bounded coupling profile.
The profile personalizes escalation, review, and adjudication; it does not close
constraint relations.

The coupling field (ψ-field, Anson 2026) measures the live human-AI interaction:

- `lambda`: operator coupling and anchoring
- `kappa`: coherence across the session window
- `theta`: procedural autonomy beyond paraphrase
- `epsilon`: drift from operator intent

These signals may route to witness, repair, stabilization, or escalation. They
cannot substitute for topology, evidence, consequence, recovery, or scope
constraints.

```text
coupling field -> observation and routing evidence
constraint gate -> event-local admission or containment
```

## Profile

A bounded profile may declare:

- operator identity evidence
- admitted scope and domain responsibilities
- risk tolerance by action class
- escalation and review cadence
- delegation relations
- protected boundaries
- uncertainty markers
- revocation and transfer rules

The profile can change how review is requested. It cannot turn a refuted or
unresolved required relation into a proven one.

## Required properties

- explicit consent for profile creation
- auditable updates
- clear revocation
- bounded portability
- no silent scope expansion
- uncertainty routes to witness or escalation
- missing or stale identity evidence routes to containment

The executable bridge is `adapters/coupling_field.py`.
