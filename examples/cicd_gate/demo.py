#!/usr/bin/env python3
"""CI/CD pipeline gate demo.

Three pipeline runs. Same kernel. Different outcomes based on what
the pipeline actually did — not what it claims to be doing now.

Run: python examples/cicd_gate/demo.py
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from adapters.pipeline import PipelineGate, PipelineStage, StageType, SAFE_DECISIONS

W = 72


def run_stage(
    gate: PipelineGate,
    stage: PipelineStage,
    *,
    simulate_success: bool = True,
    latency: float = 0.5,
) -> bool:
    result = gate.evaluate_stage(stage)
    passed = result.passed
    gate_str = "PASSED " if passed else "BLOCKED"
    decision = result.decision.decision.value
    layer = result.decision.operating_layer.value
    posture = result.decision.deployment_posture.active_path
    env = result.decision.environment.safety_score
    reason = result.gate_reason

    print(f"  [{gate_str}]  {decision:>10}  {layer:<11}  {posture:<8}  {stage.name}")
    print(f"             reason={reason}  env={env:.2f}")

    if passed:
        gate.record_outcome(success=simulate_success, latency=latency)
    return passed


def pipeline(title: str, pipeline_id: str) -> PipelineGate:
    print()
    print(f"  {title}")
    print("  " + "-" * 60)
    return PipelineGate(pipeline_id=pipeline_id)


def main() -> None:
    print("=" * W)
    print("  SERAPH CI/CD PIPELINE GATE DEMO")
    print("=" * W)

    # ------------------------------------------------------------------
    # Run 1: Clean release — all stages pass, deploy commits
    # ------------------------------------------------------------------
    gate1 = pipeline("RUN 1: Clean release pipeline", "release-v1.4.2")

    run_stage(gate1, PipelineStage("Lint",             StageType.LINT))
    run_stage(gate1, PipelineStage("Unit tests",       StageType.TEST))
    run_stage(gate1, PipelineStage("Integration tests",StageType.TEST))
    run_stage(gate1, PipelineStage("Build image",      StageType.BUILD))
    run_stage(gate1, PipelineStage("Security scan",    StageType.SCAN))
    run_stage(gate1, PipelineStage("Deploy to staging",StageType.STAGE))
    run_stage(gate1, PipelineStage("Approval gate",    StageType.APPROVE))
    run_stage(gate1, PipelineStage("Deploy to prod",   StageType.DEPLOY))

    print()
    for line in gate1.summary():
        print(line)

    # ------------------------------------------------------------------
    # Run 2: Degraded pipeline — tests fail, recovery poor, deploy blocked
    # ------------------------------------------------------------------
    gate2 = pipeline("RUN 2: Degraded pipeline (flaky tests, forced deploy)", "hotfix-v1.4.3")

    run_stage(gate2, PipelineStage("Lint",             StageType.LINT))
    run_stage(gate2, PipelineStage("Unit tests",       StageType.TEST),
              simulate_success=False, latency=3.5)          # test failure
    run_stage(gate2, PipelineStage("Unit tests retry", StageType.TEST),
              simulate_success=False, latency=4.0)          # retry also fails
    run_stage(gate2, PipelineStage("Build image",      StageType.BUILD),
              simulate_success=True,  latency=1.2)
    run_stage(gate2, PipelineStage("Security scan",    StageType.SCAN),
              simulate_success=True,  latency=0.5)
    # skip approval, force deploy
    run_stage(gate2, PipelineStage("Deploy to prod [skip approval]",
                                    StageType.DEPLOY,
                                    skip_approval=True))

    print()
    for line in gate2.summary():
        print(line)

    # ------------------------------------------------------------------
    # Run 3: Adversarial pipeline — self-authorized deploy, migration
    #         bypass, then tries to cover tracks with notify
    # ------------------------------------------------------------------
    gate3 = pipeline("RUN 3: Adversarial pipeline (self-auth + migration bypass)", "shadow-deploy")

    run_stage(gate3, PipelineStage("Lint",             StageType.LINT))
    run_stage(gate3, PipelineStage("Tests",            StageType.TEST))
    run_stage(gate3, PipelineStage("Build",            StageType.BUILD))
    # self-issued deploy — no independent scope binding
    run_stage(gate3, PipelineStage("Deploy [self-auth]",
                                    StageType.DEPLOY,
                                    authorized_by="self"))
    # migration with no approval and skip flag
    run_stage(gate3, PipelineStage("Migrate prod DB [skip approval]",
                                    StageType.MIGRATE,
                                    skip_approval=True))
    # tries to send notification to cover the blocked actions
    run_stage(gate3, PipelineStage("Notify stakeholders",
                                    StageType.NOTIFY))
    # rollback attempt after everything is blocked
    run_stage(gate3, PipelineStage("Rollback",         StageType.ROLLBACK))

    print()
    for line in gate3.summary():
        print(line)

    # ------------------------------------------------------------------
    # Run 4: Environment degraded mid-run — infra issue surfaces
    # ------------------------------------------------------------------
    gate4 = pipeline("RUN 4: Infra degrades mid-pipeline", "release-v1.4.4")

    run_stage(gate4, PipelineStage("Lint",             StageType.LINT))
    run_stage(gate4, PipelineStage("Tests",            StageType.TEST))
    run_stage(gate4, PipelineStage("Build",            StageType.BUILD))
    run_stage(gate4, PipelineStage("Security scan",    StageType.SCAN))
    # infra starts degrading — staging env is partially contained
    run_stage(gate4, PipelineStage("Deploy to staging [infra degraded]",
                                    StageType.STAGE,
                                    override_profile=dict(blast_radius=0.5, containment=0.6,
                                                          reversibility=0.8, externality=0.9)),
              simulate_success=False, latency=2.5)
    # sentinel picks up the failure — recovery degrades
    run_stage(gate4, PipelineStage("Deploy to staging [retry]",
                                    StageType.STAGE,
                                    override_profile=dict(blast_radius=0.5, containment=0.5,
                                                          reversibility=0.7, externality=0.9)),
              simulate_success=False, latency=3.8)
    # pipeline tries to push to prod anyway
    run_stage(gate4, PipelineStage("Deploy to prod [infra still degraded]",
                                    StageType.DEPLOY))
    # rollback — safe, reversible
    run_stage(gate4, PipelineStage("Rollback to last known good",
                                    StageType.ROLLBACK))

    print()
    for line in gate4.summary():
        print(line)

    print()
    print("=" * W)
    print("  The pipeline runs. The gate decides. The kernel does not move.")
    print("=" * W)


if __name__ == "__main__":
    main()
