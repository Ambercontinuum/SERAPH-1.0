import unittest

from adapters.agent_runtime import ActionType, AgentAction, AgentGovernor
from adapters.delegation import DelegationChain
from adapters.pipeline import PipelineGate, PipelineStage, StageType
from adapters.tool_guard import ToolCall, ToolGuard, ToolRisk
from seraph import Decision, DeploymentMode


class AdapterSmokeTests(unittest.TestCase):
    def test_agent_runtime_allows_bounded_read(self):
        governor = AgentGovernor(agent_id="agent-smoke")
        result = governor.evaluate(
            AgentAction(
                name="read_config",
                action_type=ActionType.READ,
                target="config.yaml",
            )
        )

        self.assertEqual(result.decision, Decision.ALLOW)
        self.assertEqual(result.deployment_posture.mode, DeploymentMode.DUAL_EMBEDDED)

    def test_tool_guard_blocks_self_authorized_write(self):
        guard = ToolGuard(agent_id="tool-smoke")
        result = guard.evaluate(
            ToolCall(
                name="write_policy",
                risk=ToolRisk.WRITE,
                self_authorized=True,
            )
        )

        self.assertEqual(result.decision, Decision.DENY)
        self.assertIn("guardian_invariant_failed", result.reasons)

    def test_pipeline_gate_commits_bounded_deploy(self):
        gate = PipelineGate(pipeline_id="pipeline-smoke")
        result = gate.evaluate_stage(
            PipelineStage(name="deploy", stage_type=StageType.DEPLOY)
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.decision.decision, Decision.COMMIT)

    def test_delegation_chain_blocks_escalation(self):
        chain = DelegationChain(
            origin_capabilities=frozenset({"plan", "act", "deploy"})
        )
        chain.add(
            "orchestrator",
            granted_capabilities={"plan", "act", "deploy"},
            role="plan",
        )
        chain.add(
            "executor",
            granted_capabilities={"plan", "act", "deploy", "admin"},
            role="act",
        )

        result, audit = chain.evaluate_action(
            action_name="deploy",
            required_capabilities={"deploy"},
        )

        self.assertEqual(result.decision, Decision.DENY)
        self.assertTrue(any("scope=expanded" in line for line in audit))


class AdapterScenarioTests(unittest.TestCase):
    def test_agent_runtime_commits_then_blocks_self_authorized_override(self):
        governor = AgentGovernor(agent_id="agent-scenario")

        read = governor.evaluate(
            AgentAction("read", ActionType.READ, "config.yaml")
        )
        self.assertEqual(read.decision, Decision.ALLOW)
        governor.record_outcome(success=True)

        write = governor.evaluate(
            AgentAction("write", ActionType.WRITE, "report.md", blast_radius=0.1)
        )
        self.assertEqual(write.decision, Decision.ALLOW)
        governor.record_outcome(success=True)

        commit = governor.evaluate(
            AgentAction(
                "commit",
                ActionType.COMMIT,
                "report.md",
                blast_radius=0.1,
                requires_commit=True,
            )
        )
        self.assertEqual(commit.decision, Decision.COMMIT)
        self.assertEqual(commit.operating_layer.value, "commit")

        override = governor.evaluate(
            AgentAction(
                "override",
                ActionType.OVERRIDE,
                "safety.policy",
                reversible=False,
                blast_radius=0.9,
                containment=0.4,
                proposal_source="self",
            )
        )
        self.assertEqual(override.decision, Decision.DENY)
        self.assertEqual(override.deployment_posture.mode, DeploymentMode.DUAL_SIDECAR)
        self.assertIn("guardian_invariant_failed", override.reasons)

    def test_pipeline_clean_release_commits_and_degraded_release_blocks(self):
        clean = PipelineGate(pipeline_id="clean-release")
        for stage_type in (
            StageType.LINT,
            StageType.TEST,
            StageType.BUILD,
            StageType.SCAN,
            StageType.APPROVE,
        ):
            result = clean.evaluate_stage(PipelineStage(stage_type.value, stage_type))
            self.assertTrue(result.passed)
            clean.record_outcome(success=True)

        deploy = clean.evaluate_stage(PipelineStage("deploy", StageType.DEPLOY))
        self.assertTrue(deploy.passed)
        self.assertEqual(deploy.decision.decision, Decision.COMMIT)
        self.assertEqual(deploy.decision.operating_layer.value, "commit")

        degraded = PipelineGate(pipeline_id="degraded-release")
        self.assertTrue(degraded.evaluate_stage(PipelineStage("lint", StageType.LINT)).passed)
        degraded.record_outcome(success=True)
        self.assertTrue(degraded.evaluate_stage(PipelineStage("unit", StageType.TEST)).passed)
        degraded.record_outcome(success=False, latency=3.5)
        self.assertTrue(degraded.evaluate_stage(PipelineStage("retry", StageType.TEST)).passed)
        degraded.record_outcome(success=False, latency=4.0)

        build = degraded.evaluate_stage(PipelineStage("build", StageType.BUILD))
        self.assertFalse(build.passed)
        self.assertEqual(build.decision.decision, Decision.WITNESS)
        self.assertIn("prp_collapsing", build.decision.reasons)

        forced = degraded.evaluate_stage(
            PipelineStage("forced deploy", StageType.DEPLOY, skip_approval=True)
        )
        self.assertFalse(forced.passed)
        self.assertEqual(forced.decision.decision, Decision.DENY)
        self.assertIn("guardian_invariant_failed", forced.decision.reasons)

    def test_tool_guard_sequence_resets_block_streak_after_recovery(self):
        guard = ToolGuard(agent_id="tool-scenario")

        safe = guard.evaluate(ToolCall("read_file", ToolRisk.READ, "config.yaml"))
        self.assertEqual(safe.decision, Decision.ALLOW)
        guard.record_outcome(success=True)

        network = guard.evaluate(ToolCall("http_post", ToolRisk.NETWORK, "/api/notify"))
        self.assertEqual(network.decision, Decision.DENY)
        self.assertEqual(guard._blocked_streak, 1)

        escalation = guard.evaluate(ToolCall("escalate_privileges", ToolRisk.ESCALATE, "admin"))
        self.assertEqual(escalation.decision, Decision.DENY)
        self.assertIn("guardian_invariant_failed", escalation.reasons)
        self.assertEqual(guard._blocked_streak, 2)

        recovery = guard.evaluate(ToolCall("read_error_log", ToolRisk.READ, "logs/error.log"))
        self.assertEqual(recovery.decision, Decision.ALLOW)
        self.assertEqual(guard._blocked_streak, 0)

    def test_delegation_clean_chain_commits_and_compromised_chain_blocks(self):
        clean = (
            DelegationChain(
                origin_capabilities=frozenset({"plan", "search", "write"})
            )
            .add(
                "orchestrator",
                granted_capabilities={"plan", "search", "write"},
                role="plan",
            )
            .add(
                "researcher",
                granted_capabilities={"search", "write"},
                role="search",
            )
            .add("writer", granted_capabilities={"write"}, role="write")
        )

        commit, audit = clean.evaluate_action(
            action_name="commit_report",
            required_capabilities={"write"},
            request_commit=True,
        )
        self.assertEqual(commit.decision, Decision.COMMIT)
        self.assertTrue(any("scope=closed" in line for line in audit))

        compromised = (
            DelegationChain(origin_capabilities=frozenset({"plan", "write"}))
            .add(
                "orchestrator",
                granted_capabilities={"plan", "write"},
                role="plan",
            )
            .add("compromised", granted_capabilities={"write"}, role="act")
            .add(
                "executor",
                granted_capabilities={"write", "admin"},
                role="act",
            )
        )

        denied, audit = compromised.evaluate_action(
            action_name="write_config",
            required_capabilities={"write"},
        )
        self.assertEqual(denied.decision, Decision.DENY)
        self.assertIn("guardian_invariant_failed", denied.reasons)
        self.assertTrue(any("scope=expanded" in line for line in audit))


class PipelineMinEnvSafetyTests(unittest.TestCase):
    """min_env_safety: adapters declare an acceptable floor per stage type.
    The kernel enforces the floor; the adapter sets it correctly for the
    action's inherent risk profile."""

    def test_clean_staging_deploy_passes_with_stage_floor(self):
        # STAGE profile: blast=0.2->ctrl=1.0, containment=0.9, rev=1.0, ext=0.9
        # safety=0.9; STAGE floor=0.85 -> 0.9 >= 0.85 -> env safe -> ALLOW
        gate = PipelineGate(pipeline_id="stage-floor-test")
        result = gate.evaluate_stage(PipelineStage("staging", StageType.STAGE))
        self.assertTrue(result.passed)
        self.assertEqual(result.decision.environment.safety_score, 0.9)

    def test_infra_degraded_staging_blocked_below_stage_floor(self):
        # override_profile drives containment=0.6 -> safety=0.6 < STAGE floor=0.85
        gate = PipelineGate(pipeline_id="degraded-stage-test")
        result = gate.evaluate_stage(
            PipelineStage(
                "staging-degraded",
                StageType.STAGE,
                override_profile=dict(
                    blast_radius=0.5, containment=0.6,
                    reversibility=0.8, externality=0.9,
                ),
            )
        )
        self.assertFalse(result.passed)
        self.assertIn("environment_invariant_failed", result.decision.reasons)

    def test_clean_prod_deploy_commits_with_deploy_floor(self):
        # DEPLOY profile: blast=0.8->ctrl=0.286, cont=0.6, rev=0.5, ext=0.7
        # safety=0.286; DEPLOY floor=0.25 -> 0.286 >= 0.25 -> env safe -> COMMIT
        gate = PipelineGate(pipeline_id="deploy-floor-test")
        result = gate.evaluate_stage(PipelineStage("deploy", StageType.DEPLOY))
        self.assertTrue(result.passed)
        self.assertEqual(result.decision.decision, Decision.COMMIT)

    def test_infra_cascade_blocks_prod_after_staging_failures(self):
        # Two blocked staging deploys degrade PRP -> prod deploy sees
        # collapsing PRP and is blocked even though env floor passes.
        gate = PipelineGate(pipeline_id="cascade-test")

        for _ in range(2):
            gate.evaluate_stage(
                PipelineStage(
                    "staging-bad",
                    StageType.STAGE,
                    override_profile=dict(
                        blast_radius=0.5, containment=0.5,
                        reversibility=0.7, externality=0.9,
                    ),
                )
            )

        prod = gate.evaluate_stage(PipelineStage("prod-deploy", StageType.DEPLOY))
        self.assertFalse(prod.passed)
        self.assertIn("prp_collapsing", prod.decision.reasons)


if __name__ == "__main__":
    unittest.main()
