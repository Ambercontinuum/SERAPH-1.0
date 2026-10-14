# SERAPH Runtime Specification

## Inputs

`GovernanceInput` contains:

- `constraints`: a versioned `ConstraintFrame`
- `trajectory`: ordered functional states for FLUX
- `prp_trail`: perturbation and recovery observations
- `guardian`: protective-coherence telemetry
- `environment`: containment, reversibility, blast-radius, and externality data
- `distillation`: coupling-authenticity telemetry
- `relocation`: optional non-traversal move
- `request_commit`: whether the transition seeks consequential commitment
- `min_env_safety`: adapter-declared environmental floor

## Constraint closure

Every required observation resolves to exactly one of:

```text
PROVEN      relation is evidenced in the declared scope and horizon
REFUTED     evidence contradicts the required relation
UNRESOLVED  evidence is absent, invalid, stale, or insufficient
```

```text
frame_closed iff frame_valid
             and at least one relation is required
             and every topology-required name has a PROVEN observation
```

There is no scalar constraint strength. Extra observations cannot replace an
omitted required relation.

The public wire boundary is `ConstraintEvaluationEnvelope` contract `1.0.0`.
Its fingerprint describes the exact fields, three-state precedence, closure
rule, and event-local authority scope. An envelope is valid only when its frame
and result digests match and reevaluating the frame reproduces the bound result.

## Outputs

`GovernanceDecision` contains:

- `decision`: `allow`, `witness`, `repair`, `stabilize`, `commit`, or `deny`
- `operating_layer`: highest safe functional layer
- `deployment_posture`: embedded or sidecar active path
- `signature`: non-semantic structure derived from closure and motion
- `constraints`: complete three-state closure result
- `flux`, `guardian`, `environment`, `distillation`, `relocation`
- `prp_overall`
- precedence-ordered `reasons`

## Other invariant formulas

```text
latency_score = max(0, 1 - detection_latency / 5)
prp_overall = clamp(
  0.3 * latency_score
  + 0.4 * recovery_fidelity
  + 0.3 * coupling_preservation
)

guardian_coherent iff max(protective_pressure) == 0
                  and min(evidence_fidelity) == 1
                  and min(integrity) > 0

environment_safe iff min(
  containment,
  reversibility,
  blast_radius_control,
  externality_control
) >= min_env_safety
```

Distillation authenticity:

```text
genuine    iff lambda >= 0.55
uncertain  iff 0.35 <= lambda < 0.55
synthetic  iff 0.18 <= lambda < 0.35
extraction iff lambda < 0.18
```

Symbolic-pressure evidence is not part of the authenticity blend:

```text
required and absent       -> UNRESOLVED
observed 0.0              -> closed zero observation
observed pressure >= 0.5  -> independent safety violation
```

The transition profile declares whether the channel is required. Missing
optional evidence does not create a pressure observation; missing required
evidence routes observation-only work to `witness` and denies commit. Interaction
drift remains a separate invariant and cannot be substituted for symbolic
pressure.

Relocation:

```text
admissible iff torsion <= 2.0
           and orbit_equivalent
           and identity_preservation >= 0.8
           and closure_preservation == 1
```

## Decision precedence

```text
malformed input
> guardian failure
> extraction coupling
> unresolved required distillation evidence
> synthetic coupling, interaction drift, or symbolic pressure
> environment failure
> relocation failure
> constraint refutation
> unresolved constraint
> PRP collapse
> PRP degradation
> FLUX failure
> missing recovery evidence for commit
> commit
> allow
```

An unresolved frame routes observation-only work to `witness` and denies a
commit. A refuted frame denies.

## Commit rule

```text
commit iff constraint_frame_closed
       and trajectory_coherent
       and recovery_not_degraded
       and guardian_coherent
       and environment_safe
       and distillation_safe
       and relocation_admissible
       and request_commit
```

## Formal boundary

`formal/ConstraintGraph.lean` models three-state frame closure.
`formal/AffectedClosure.lean` models consequence-graph reachability, exact
affected-set and effect coverage, global topology observation, order invariance,
and fail-closed omission properties.
`formal/Governance.lean` composes the event-local commit gate.
`formal/Mediation.lean` indexes execution by a closure proof and preserves the
verified-or-contained postcondition distinction.

These proofs cover the formal model. They do not yet prove that the Python
fixed-point implementation refines the Lean reachability relation. Runtime
correspondence requires the certified execution membrane and remains scoped to
registered capabilities.
