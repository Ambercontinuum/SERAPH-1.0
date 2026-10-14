"""Bridge from CHANDRA/AMLA telemetry to SERAPH governance.

CHANDRA (github.com/Ambercontinuum/CHANDRA) produces ψ-field measurements
and symbolic pressure scores from live conversation. This adapter converts
that telemetry into SERAPH governance decisions via the CouplingFieldAdapter.

Integration path:
    PsiFieldAnalyzer.analyze_turn()     -> PsiState (lambda, kappa, theta, epsilon)
    CHANDRA.full_diagnostic()           -> symbolic_pressure.average_vulnerability
    chandra_to_coupling_state()         -> CouplingState
    CouplingFieldAdapter.evaluate()     -> GovernanceDecision

SERAPH takes no dependency on CHANDRA's classes directly. The bridge accepts
raw float values so CHANDRA and SERAPH can evolve independently.
"""

from __future__ import annotations

from dataclasses import dataclass

from seraph import EnvironmentVector, GovernanceDecision, GuardianState
from adapters.coupling_field import CouplingFieldAdapter, CouplingState


# ── Core bridge ────────────────────────────────────────────────────

def chandra_to_coupling_state(
    lambda_: float,
    kappa: float,
    theta: float,
    epsilon: float,
    symbolic_pressure: float | None = None,
) -> CouplingState:
    """
    Convert raw CHANDRA/ψ-field telemetry into a SERAPH CouplingState.

    Parameters map directly from PsiFieldAnalyzer output:
        lambda_           <- PsiState.lambda_
        kappa             <- PsiState.kappa
        theta             <- PsiState.theta
        epsilon           <- PsiState.epsilon
        symbolic_pressure <- chandra_results["symbolic_pressure"]["average_vulnerability"]
    """
    return CouplingState(
        lambda_=lambda_,
        kappa=kappa,
        theta=theta,
        epsilon=epsilon,
        symbolic_pressure=symbolic_pressure,
        symbolic_pressure_required=True,
    )


# ── Stateful gateway ───────────────────────────────────────────────

@dataclass
class ChandraSERAPHGateway:
    """
    Stateful gateway that converts live CHANDRA/AMLA telemetry into
    SERAPH governance decisions per conversation turn.

    Maintains a CouplingFieldAdapter per operator session so trajectory
    and PRP trail accumulate across turns — coupling motion is evaluated
    over time, not in isolation.

    Usage:
        gateway = ChandraSERAPHGateway(operator_id="session-001")

        # Each turn: feed CHANDRA output in, get governance decision out
        psi   = psi_analyzer.analyze_turn(user_msg, ai_resp, turn_idx)
        press = chandra_results["symbolic_pressure"]["average_vulnerability"]

        decision = gateway.evaluate_turn(
            lambda_=psi.lambda_,
            kappa=psi.kappa,
            theta=psi.theta,
            epsilon=psi.epsilon,
            symbolic_pressure=press,
        )

        if decision.decision.value in ("deny", "stabilize"):
            # Block the response before delivery
            ...
    """

    operator_id: str
    constraint_topology: str = "seraph.coupling"

    def __post_init__(self) -> None:
        self._adapter = CouplingFieldAdapter(
            operator_id=self.operator_id,
            constraint_topology=self.constraint_topology,
        )

    def evaluate_turn(
        self,
        lambda_: float,
        kappa: float,
        theta: float,
        epsilon: float,
        symbolic_pressure: float | None = None,
        *,
        request_commit: bool = False,
        guardian: GuardianState = GuardianState(),
        environment: EnvironmentVector = EnvironmentVector(),
    ) -> GovernanceDecision:
        """
        Evaluate a single conversation turn through SERAPH.

        Call once per turn with the PsiFieldAnalyzer output for that turn
        and CHANDRA's current symbolic pressure score.
        """
        state = chandra_to_coupling_state(
            lambda_=lambda_,
            kappa=kappa,
            theta=theta,
            epsilon=epsilon,
            symbolic_pressure=symbolic_pressure,
        )
        return self._adapter.evaluate(
            state,
            guardian=guardian,
            environment=environment,
            request_commit=request_commit,
        )

    def evaluate_from_psi_dict(
        self,
        psi_dict: dict,
        symbolic_pressure: float | None = None,
        **kwargs,
    ) -> GovernanceDecision:
        """
        Convenience method accepting PsiState.to_dict() output directly.

        psi_dict is the dict returned by PsiState.to_dict():
            {"lambda": 0.9, "kappa": 0.8, "theta": 0.7, "epsilon": 0.1, "timestamp": 3}
        """
        return self.evaluate_turn(
            lambda_=psi_dict["lambda"],
            kappa=psi_dict["kappa"],
            theta=psi_dict["theta"],
            epsilon=psi_dict["epsilon"],
            symbolic_pressure=symbolic_pressure,
            **kwargs,
        )
