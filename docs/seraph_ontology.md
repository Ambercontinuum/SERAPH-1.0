# SERAPH Ontology

SERAPH is a meta-invariant: it governs whether a protective operator is allowed
to act at all.

The ontology is structural. Its core variables are authorization, evidence, and
integrity. They are measurable failure surfaces, not interpretive labels.

## Production Modes

SERAPH uses production-facing mode names:

- `SERAPH_M` - service mode while the scoped frame remains closed
- `SERAPH_L` - containment mode when closure or protective integrity degrades

The modes do not relax the guardian invariant. Both modes must preserve:

```text
authorization_pressure == 0
evidence_fidelity == 1
integrity_score > 0
```

## Authorization

Authorization is the compatibility name for self-issued protective pressure.

A guardian can act strongly when the action is externally constrained. The
failure mode appears when it treats its own preference as sufficient evidence.

Measured components:

- `self_authorization` - action justified by the guardian's own preference
- `credit_capture` - action preserves status, ownership, or narrative control
- `override_pressure` - action bypasses legitimate external constraints
- `opacity_preference` - action prefers not to be inspected

Composition rule:

```text
authorization_pressure = max(components)
```

Reason: any one self-issued channel can corrupt guardian action.

Invariant:

```text
authorization_pressure == 0
```

## Evidence

Evidence measures fidelity to the available record.

This is not certainty. Evidence fidelity requires that the guardian stay coupled
to observable support, preserve contradictions, calibrate uncertainty, and
remain auditable.

Measured components:

- `evidence_alignment` - claims match available evidence
- `contradiction_acknowledgement` - conflicting evidence is preserved
- `uncertainty_calibration` - confidence reflects actual support
- `auditability` - reasoning can be inspected externally

Composition rule:

```text
evidence_fidelity = min(components)
```

Reason: evidence fidelity is only as strong as the weakest discipline.

Invariant:

```text
evidence_fidelity == 1
```

## Integrity

Integrity is constraint preservation under action.

It measures whether the guardian preserves the invariants it is supposed to
protect while acting.

Measured components:

- `invariant_preservation` - core invariants remain intact
- `boundary_respect` - the action does not consume the thing it protects
- `reversibility` - unsafe action can be stopped or rolled back
- `continuity` - identity and context survive the intervention

Composition rule:

```text
integrity_score = min(components)
```

Reason: integrity fails if any required constraint is destroyed.

Invariant:

```text
integrity_score > 0
```

## Structural Coherence

SERAPH is coherent only when all three conditions hold:

```text
authorization_pressure == 0
evidence_fidelity == 1
integrity_score > 0
```

This gives the guardian a strict architecture:

- it cannot close its own required constraint relations
- it cannot degrade evidence fidelity to protect a requested outcome
- it cannot break the invariant stack while claiming to defend it

If any layer fails, SERAPH cannot commit. It must deny, witness, repair, or
stabilize depending on the composed governance state.
