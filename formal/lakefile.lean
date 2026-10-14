import Lake
open Lake DSL

package «SeraphFormal» where

-- Ten modules, no mathlib dependency.
-- Proofs use only Lean 4 core tactics: simp, omega, exact, refine, decide.
-- @[default_target] so a bare `lake build` (no explicit target) builds
-- this library -- without it, Lake has no target to select by default.
@[default_target]
lean_lib «SeraphFormal» where
  roots := #[`Flux, `ConstraintGraph, `AffectedClosure, `Governance, `PRP, `Distillation,
             `Relocation, `Environment, `Guardian, `Mediation, `SeraphFormal]
