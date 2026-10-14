"""Narrow integration between compiled manifold proofs and SERAPH governance."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .invariant_model import (
    GovernanceDecision,
    GovernanceInput,
    govern,
)
from .manifold import (
    CompiledManifold,
    InvariantCertificate,
    ManifoldState,
    ManifoldVerdict,
    TransitionProposal,
)


@dataclass(frozen=True)
class ManifoldGovernanceDecision:
    """A manifold proof and the SERAPH decision it conditions."""

    certificate: InvariantCertificate
    governance: GovernanceDecision

    @property
    def manifold_proven(self) -> bool:
        return self.certificate.verdict is ManifoldVerdict.PROVEN


def govern_transition(
    compiled: CompiledManifold,
    state: ManifoldState,
    proposal: TransitionProposal,
    governance_input: GovernanceInput,
) -> ManifoldGovernanceDecision:
    """Compile a transition and condition SERAPH on the resulting proof.

    A refuted invariant becomes a guardian integrity failure.  An unresolved
    invariant becomes an evidence-fidelity failure.  Only a proven manifold
    transition reaches SERAPH with its original guardian state intact; all
    seven existing SERAPH layers still apply afterward.
    """

    # No non-proven manifold result reaches the existing kernel
    # with healthy guardian evidence and integrity.
    certificate = compiled.evaluate(state, proposal)
    guardian = governance_input.guardian
    if certificate.verdict is ManifoldVerdict.REFUTED:
        guardian = replace(guardian, integrity=0.0)
    elif certificate.verdict is ManifoldVerdict.UNRESOLVED:
        guardian = replace(guardian, evidence_fidelity=0.0)

    decision = govern(replace(governance_input, guardian=guardian))
    return ManifoldGovernanceDecision(
        certificate=certificate,
        governance=decision,
    )
