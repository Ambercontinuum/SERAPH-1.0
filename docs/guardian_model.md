# SERAPH Guardian Model

The guardian is a protective-coherence layer inside the wider constraint
system. It does not define the manifold and cannot close its own required
relations.

```text
agent proposes transition
        |
        v
scoped constraint frame + live invariant reads
        |
        v
allow | witness | repair | stabilize | commit | deny
```

## Modes

- `SERAPH_M`: service mode while the frame and protective invariants close
- `SERAPH_L`: containment mode when closure, recovery, coupling, environment,
  or integrity degrades

Modes do not change hard constraints. Containment may interpose, deny, preserve
evidence, and route recovery. It may not silently rewrite topology, evidence,
scope, or commit criteria.

## Protective pressure

The current runtime retains the compatibility name `AuthorizationVector` for a
guardian pressure vector:

- `self_authorization`
- `credit_capture`
- `override_pressure`
- `opacity_preference`

These are alarms, not the manifold's authority ontology. Their maximum is used
because any elevated channel is sufficient to make protective action
incoherent.

Future versions may rename this type without changing its function: detecting a
guardian attempting to become its own evidence, broaden its own scope, capture
credit, or suppress inspection.

## Learning boundary

Allowed adaptation includes calibration, risk estimation, failure-pattern
detection, and improved recovery routing. Adaptation may propose a topology or
constraint change, but the running instance cannot admit that change through
the same transition it is evaluating.

The short form:

```text
adaptive perception
versioned constraint topology
event-local commit disposition
```

## Hard boundary

A guardian remains coherent only when:

```text
protective_pressure == 0
evidence_fidelity == 1
integrity_score > 0
constraint_frame_closed
```

The first three conditions describe guardian behavior. The final condition
belongs to the external, versioned transition frame. No guardian telemetry can
substitute for a missing required relation.
