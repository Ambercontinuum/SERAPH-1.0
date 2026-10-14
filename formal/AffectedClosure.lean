-- AffectedClosure.lean
-- Topology-owned consequence reachability and non-compensatory affected-set
-- completeness for one proposed transition.
--
-- The graph is independent of the proposal. Reachability begins at the effect
-- roots supplied for the transition, making that trust boundary explicit.
--
-- Lean 4, no mathlib.

set_option autoImplicit false

namespace SERAPH.AffectedClosure

structure ConsequenceEdge (Entity : Type) where
  source : Entity
  target : Entity
deriving Repr

/-- Reflexive, transitive reachability from transition effect roots through the
    compiled consequence graph. -/
inductive Reachable {Entity : Type}
    (edges : List (ConsequenceEdge Entity))
    (roots : List Entity) : Entity → Prop where
  | root {entity : Entity} :
      entity ∈ roots → Reachable edges roots entity
  | step {source target : Entity} :
      Reachable edges roots source →
      ConsequenceEdge.mk source target ∈ edges →
      Reachable edges roots target

def Affected {Entity : Type}
    (edges : List (ConsequenceEdge Entity))
    (roots : List Entity)
    (inhabitant : Entity → Prop)
    (entity : Entity) : Prop :=
  Reachable edges roots entity ∧ inhabitant entity

/-- Every topology endpoint is represented in the observed state. This is
    intentionally global rather than limited to the currently reached subgraph. -/
def TopologyObserved {Entity : Type}
    (edges : List (ConsequenceEdge Entity))
    (observed : Entity → Prop) : Prop :=
  ∀ edge, edge ∈ edges → observed edge.source ∧ observed edge.target

/-- Every proposal-declared effect root is represented in observed state. -/
def RootsObserved {Entity : Type}
    (effectRoots : List Entity)
    (observed : Entity → Prop) : Prop :=
  ∀ entity, entity ∈ effectRoots → observed entity

/-- The proposal-declared affected inhabitants are exactly the inhabitants
    derived by graph closure. -/
def ExactAffected {Entity : Type}
    (edges : List (ConsequenceEdge Entity))
    (roots declared : List Entity)
    (inhabitant : Entity → Prop) : Prop :=
  ∀ entity, entity ∈ declared ↔ Affected edges roots inhabitant entity

/-- Every derived affected inhabitant has an explicit modeled effect, including
    an explicit preservation effect when no coordinate change is predicted. -/
def EffectsComplete {Entity : Type}
    (edges : List (ConsequenceEdge Entity))
    (effectRoots : List Entity)
    (inhabitant : Entity → Prop) : Prop :=
  ∀ entity, Affected edges effectRoots inhabitant entity → entity ∈ effectRoots

/-- The affected-set obligations that must all be carried for transition
    admission. No aggregate score can substitute for one missing relation. -/
structure AffectedSetCertificate {Entity : Type}
    (edges : List (ConsequenceEdge Entity))
    (effectRoots declared : List Entity)
    (observed inhabitant : Entity → Prop) : Prop where
  topologyObserved : TopologyObserved edges observed
  rootsObserved : RootsObserved effectRoots observed
  exactAffected : ExactAffected edges effectRoots declared inhabitant
  effectsComplete : EffectsComplete edges effectRoots inhabitant

theorem root_is_reachable {Entity : Type}
    {edges : List (ConsequenceEdge Entity)}
    {roots : List Entity}
    {entity : Entity}
    (hroot : entity ∈ roots) :
    Reachable edges roots entity :=
  Reachable.root hroot

theorem consequence_edge_extends_reachability {Entity : Type}
    {edges : List (ConsequenceEdge Entity)}
    {roots : List Entity}
    {source target : Entity}
    (hsource : Reachable edges roots source)
    (hedge : ConsequenceEdge.mk source target ∈ edges) :
    Reachable edges roots target :=
  Reachable.step hsource hedge

theorem two_edge_consequence_is_reachable {Entity : Type}
    {edges : List (ConsequenceEdge Entity)}
    {roots : List Entity}
    {source middle target : Entity}
    (hroot : source ∈ roots)
    (hfirst : ConsequenceEdge.mk source middle ∈ edges)
    (hsecond : ConsequenceEdge.mk middle target ∈ edges) :
    Reachable edges roots target :=
  Reachable.step (Reachable.step (Reachable.root hroot) hfirst) hsecond

theorem reachability_respects_membership {Entity : Type}
    {edges₁ edges₂ : List (ConsequenceEdge Entity)}
    {roots₁ roots₂ : List Entity}
    (hedges : ∀ edge, edge ∈ edges₁ ↔ edge ∈ edges₂)
    (hroots : ∀ entity, entity ∈ roots₁ ↔ entity ∈ roots₂) :
    ∀ {entity}, Reachable edges₁ roots₁ entity ↔
      Reachable edges₂ roots₂ entity := by
  intro entity
  constructor
  · intro h
    induction h with
    | root hroot =>
        exact Reachable.root ((hroots _).mp hroot)
    | step hsource hedge ih =>
        exact Reachable.step ih ((hedges _).mp hedge)
  · intro h
    induction h with
    | root hroot =>
        exact Reachable.root ((hroots _).mpr hroot)
    | step hsource hedge ih =>
        exact Reachable.step ih ((hedges _).mpr hedge)

theorem empty_roots_reach_nothing {Entity : Type}
    (edges : List (ConsequenceEdge Entity))
    (entity : Entity) :
    ¬ Reachable edges [] entity := by
  intro h
  induction h with
  | root hroot => simp at hroot
  | step _ _ ih => exact ih

theorem affected_omission_blocks_certificate {Entity : Type}
    {edges : List (ConsequenceEdge Entity)}
    {effectRoots declared : List Entity}
    {observed inhabitant : Entity → Prop}
    {entity : Entity}
    (haffected : Affected edges effectRoots inhabitant entity)
    (homitted : entity ∉ declared) :
    ¬ AffectedSetCertificate edges effectRoots declared observed inhabitant := by
  intro certificate
  exact homitted ((certificate.exactAffected entity).mpr haffected)

theorem extra_declaration_blocks_certificate {Entity : Type}
    {edges : List (ConsequenceEdge Entity)}
    {effectRoots declared : List Entity}
    {observed inhabitant : Entity → Prop}
    {entity : Entity}
    (hdeclared : entity ∈ declared)
    (hnotAffected : ¬ Affected edges effectRoots inhabitant entity) :
    ¬ AffectedSetCertificate edges effectRoots declared observed inhabitant := by
  intro certificate
  exact hnotAffected ((certificate.exactAffected entity).mp hdeclared)

theorem unmodeled_affected_blocks_certificate {Entity : Type}
    {edges : List (ConsequenceEdge Entity)}
    {effectRoots declared : List Entity}
    {observed inhabitant : Entity → Prop}
    {entity : Entity}
    (haffected : Affected edges effectRoots inhabitant entity)
    (hunmodeled : entity ∉ effectRoots) :
    ¬ AffectedSetCertificate edges effectRoots declared observed inhabitant := by
  intro certificate
  exact hunmodeled (certificate.effectsComplete entity haffected)

theorem unobserved_source_blocks_certificate {Entity : Type}
    {edges : List (ConsequenceEdge Entity)}
    {effectRoots declared : List Entity}
    {observed inhabitant : Entity → Prop}
    {edge : ConsequenceEdge Entity}
    (hedge : edge ∈ edges)
    (hunobserved : ¬ observed edge.source) :
    ¬ AffectedSetCertificate edges effectRoots declared observed inhabitant := by
  intro certificate
  exact hunobserved (certificate.topologyObserved edge hedge).1

theorem unobserved_target_blocks_certificate {Entity : Type}
    {edges : List (ConsequenceEdge Entity)}
    {effectRoots declared : List Entity}
    {observed inhabitant : Entity → Prop}
    {edge : ConsequenceEdge Entity}
    (hedge : edge ∈ edges)
    (hunobserved : ¬ observed edge.target) :
    ¬ AffectedSetCertificate edges effectRoots declared observed inhabitant := by
  intro certificate
  exact hunobserved (certificate.topologyObserved edge hedge).2

theorem unobserved_root_blocks_certificate {Entity : Type}
    {edges : List (ConsequenceEdge Entity)}
    {effectRoots declared : List Entity}
    {observed inhabitant : Entity → Prop}
    {entity : Entity}
    (hroot : entity ∈ effectRoots)
    (hunobserved : ¬ observed entity) :
    ¬ AffectedSetCertificate edges effectRoots declared observed inhabitant := by
  intro certificate
  exact hunobserved (certificate.rootsObserved entity hroot)

end SERAPH.AffectedClosure
