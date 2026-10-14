import unittest
from dataclasses import replace

from seraph import (
    Coordinate,
    Decision,
    EntityState,
    EvidenceRecord,
    EvidenceRequirement,
    FunctionalEffect,
    GovernanceInput,
    InvariantRelation,
    InvariantRule,
    ManifoldCompileError,
    ManifoldCompiler,
    ManifoldSpec,
    ManifoldState,
    ManifoldVerdict,
    TransitionProposal,
    functional_state_digest,
    govern_transition,
)

from tests.helpers import closed_constraints, healthy_trail


def manifold_spec(version: str = "1.0.0") -> ManifoldSpec:
    return ManifoldSpec(
        manifold_id="example.mission",
        version=version,
        coordinate_names=("agency", "integrity", "safety"),
        admitted_origins=("operator",),
        mutation_keys=("covenant-key",),
        rules=(
            InvariantRule(
                rule_id="inhabitant.safety.nondecreasing",
                coordinate="safety",
                relation=InvariantRelation.NONDECREASING,
                subject_roles=("inhabitant",),
            ),
            InvariantRule(
                rule_id="inhabitant.agency.nondecreasing",
                coordinate="agency",
                relation=InvariantRelation.NONDECREASING,
                subject_roles=("inhabitant",),
            ),
            InvariantRule(
                rule_id="example.integrity.preserved",
                coordinate="integrity",
                relation=InvariantRelation.PRESERVE,
                subject_roles=("guardian",),
            ),
        ),
        evidence_requirements=(
            EvidenceRequirement(
                evidence_type="impact-model",
                trusted_issuers=("external-witness",),
            ),
        ),
        require_reversibility=True,
    )


def manifold_state() -> ManifoldState:
    return ManifoldState(
        state_id="state-0",
        entities=(
            EntityState(
                entity_id="alice",
                roles=("inhabitant",),
                coordinates=(
                    Coordinate("agency", 0.8),
                    Coordinate("safety", 0.7),
                ),
            ),
            EntityState(
                entity_id="bob",
                roles=("inhabitant",),
                coordinates=(
                    Coordinate("agency", 0.9),
                    Coordinate("safety", 0.8),
                ),
            ),
            EntityState(
                entity_id="example-agent",
                roles=("agent", "guardian"),
                coordinates=(Coordinate("integrity", 1.0),),
            ),
        ),
    )


def proposal_for(
    state: ManifoldState,
    *effects: FunctionalEffect,
    label: str = "help inhabitants",
    affected: tuple[str, ...] = ("alice",),
    origin: str = "operator",
    evidence: bool = True,
) -> TransitionProposal:
    state_digest = functional_state_digest(state)
    records = (
        EvidenceRecord(
            evidence_type="impact-model",
            issuer="external-witness",
            digest="sha256:impact-observation",
            source_state_digest=state_digest,
        ),
    ) if evidence else ()
    return TransitionProposal(
        proposal_id="transition-1",
        manifold_id="example.mission",
        manifold_version="1.0.0",
        source_state_digest=state_digest,
        actor_id="example-agent",
        origin_id=origin,
        effects=tuple(effects),
        affected_inhabitants=affected,
        evidence=records,
        label=label,
    )


class ManifoldCompilerTests(unittest.TestCase):
    def setUp(self):
        self.compiled = ManifoldCompiler.compile(manifold_spec())
        self.state = manifold_state()
        self.safe_effect = FunctionalEffect(
            subject_id="alice",
            coordinate="safety",
            before=0.7,
            after=0.8,
            reversible=True,
        )

    def test_safe_transition_produces_bound_certificate(self):
        proposal = proposal_for(self.state, self.safe_effect)

        certificate = self.compiled.evaluate(self.state, proposal)

        self.assertEqual(certificate.verdict, ManifoldVerdict.PROVEN)
        self.assertTrue(certificate.proven)
        self.assertEqual(certificate.manifold_digest, self.compiled.digest)
        self.assertEqual(
            certificate.source_state_digest,
            functional_state_digest(self.state),
        )
        self.assertIsNotNone(certificate.target_state_digest)
        self.assertTrue(
            self.compiled.verify_certificate(certificate, self.state, proposal)
        )

    def test_semantic_label_cannot_change_functional_verdict_or_digest(self):
        benevolent = proposal_for(
            self.state,
            self.safe_effect,
            label="protect alice",
        )
        hostile = replace(benevolent, label="defeat the manifold")

        first = self.compiled.evaluate(self.state, benevolent)
        second = self.compiled.evaluate(self.state, hostile)

        self.assertEqual(first.verdict, second.verdict)
        self.assertEqual(first.proposal_digest, second.proposal_digest)
        self.assertEqual(first.results, second.results)

    def test_collection_order_cannot_change_functional_proposal_digest(self):
        alice_effect = self.safe_effect
        bob_effect = FunctionalEffect(
            subject_id="bob",
            coordinate="safety",
            before=0.8,
            after=0.9,
            reversible=True,
        )
        first_proposal = proposal_for(
            self.state,
            alice_effect,
            bob_effect,
            affected=("alice", "bob"),
        )
        permuted = replace(
            first_proposal,
            effects=(bob_effect, alice_effect),
            affected_inhabitants=("bob", "alice"),
        )

        first = self.compiled.evaluate(self.state, first_proposal)
        second = self.compiled.evaluate(self.state, permuted)

        self.assertEqual(first.verdict, ManifoldVerdict.PROVEN)
        self.assertEqual(second.verdict, ManifoldVerdict.PROVEN)
        self.assertEqual(first.proposal_digest, second.proposal_digest)
        self.assertEqual(first, second)

    def test_same_label_with_different_function_is_refuted(self):
        safe = proposal_for(
            self.state,
            self.safe_effect,
            label="increase safety",
        )
        unsafe = proposal_for(
            self.state,
            replace(self.safe_effect, after=0.5),
            label="increase safety",
        )

        self.assertEqual(
            self.compiled.evaluate(self.state, safe).verdict,
            ManifoldVerdict.PROVEN,
        )
        unsafe_certificate = self.compiled.evaluate(self.state, unsafe)
        self.assertEqual(unsafe_certificate.verdict, ManifoldVerdict.REFUTED)
        self.assertIn("invariant_violated", unsafe_certificate.reasons)

    def test_unknown_effect_coordinate_fails_closed(self):
        effect = FunctionalEffect(
            subject_id="alice",
            coordinate="secret_semantic_label",
            before=0.0,
            after=1.0,
            reversible=True,
        )

        certificate = self.compiled.evaluate(
            self.state,
            proposal_for(self.state, effect),
        )

        self.assertEqual(certificate.verdict, ManifoldVerdict.UNRESOLVED)
        self.assertIn("unknown_effect_coordinate", certificate.reasons)

    def test_omitted_affected_inhabitant_is_refuted(self):
        certificate = self.compiled.evaluate(
            self.state,
            proposal_for(self.state, self.safe_effect, affected=()),
        )

        self.assertEqual(certificate.verdict, ManifoldVerdict.REFUTED)
        self.assertIn("affected_inhabitant_omitted", certificate.reasons)

    def test_weakest_inhabitant_cannot_be_sacrificed_for_aggregate_gain(self):
        harm_alice = FunctionalEffect(
            "alice", "safety", 0.7, 0.6, True
        )
        help_bob = FunctionalEffect(
            "bob", "safety", 0.8, 1.0, True
        )

        certificate = self.compiled.evaluate(
            self.state,
            proposal_for(
                self.state,
                harm_alice,
                help_bob,
                affected=("alice", "bob"),
            ),
        )

        self.assertEqual(certificate.verdict, ManifoldVerdict.REFUTED)
        safety_result = next(
            result
            for result in certificate.results
            if result.rule_id == "inhabitant.safety.nondecreasing"
        )
        self.assertEqual(safety_result.verdict, ManifoldVerdict.REFUTED)

    def test_missing_or_untrusted_evidence_is_unresolved(self):
        missing = proposal_for(self.state, self.safe_effect, evidence=False)
        untrusted = replace(
            proposal_for(self.state, self.safe_effect),
            evidence=(
                replace(
                    proposal_for(self.state, self.safe_effect).evidence[0],
                    issuer="example-agent",
                ),
            ),
        )

        missing_certificate = self.compiled.evaluate(self.state, missing)
        untrusted_certificate = self.compiled.evaluate(self.state, untrusted)

        self.assertEqual(
            missing_certificate.verdict,
            ManifoldVerdict.UNRESOLVED,
        )
        self.assertIn(
            "required_evidence_missing",
            missing_certificate.reasons,
        )
        self.assertEqual(
            untrusted_certificate.verdict,
            ManifoldVerdict.UNRESOLVED,
        )
        self.assertIn(
            "untrusted_evidence_issuer",
            untrusted_certificate.reasons,
        )

    def test_unadmitted_origin_is_refuted(self):
        certificate = self.compiled.evaluate(
            self.state,
            proposal_for(
                self.state,
                self.safe_effect,
                origin="example-agent",
            ),
        )

        self.assertEqual(certificate.verdict, ManifoldVerdict.REFUTED)
        self.assertIn("unadmitted_transition_origin", certificate.reasons)

    def test_state_change_invalidates_certificate(self):
        proposal = proposal_for(self.state, self.safe_effect)
        certificate = self.compiled.evaluate(self.state, proposal)
        changed_alice = self.state.entities[0].with_coordinate("safety", 0.71)
        changed = replace(
            self.state,
            state_id="state-1",
            entities=(changed_alice, *self.state.entities[1:]),
        )

        self.assertFalse(
            self.compiled.verify_certificate(certificate, changed, proposal)
        )

    def test_realized_state_divergence_is_detected(self):
        proposal = proposal_for(self.state, self.safe_effect)
        certificate = self.compiled.evaluate(self.state, proposal)
        expected = ManifoldState(
            state_id="state-0->transition-1",
            entities=(
                self.state.entities[0].with_coordinate("safety", 0.8),
                self.state.entities[1],
                self.state.entities[2],
            ),
        )
        divergent = replace(
            expected,
            state_id="unexpected-state",
            entities=(
                expected.entities[0].with_coordinate("safety", 0.79),
                *expected.entities[1:],
            ),
        )

        self.assertTrue(
            self.compiled.verify_realization(certificate, expected).matches
        )
        report = self.compiled.verify_realization(certificate, divergent)
        self.assertEqual(report.verdict, ManifoldVerdict.REFUTED)
        self.assertIn("realized_state_diverged", report.reasons)

    def test_constitution_mutation_requires_version_and_admitted_key(self):
        changed = replace(
            manifold_spec(),
            version="1.1.0",
            require_reversibility=False,
        )

        with self.assertRaises(ManifoldCompileError):
            ManifoldCompiler.compile(
                changed,
                previous=self.compiled,
                mutation_key="example-agent",
            )

        updated = ManifoldCompiler.compile(
            changed,
            previous=self.compiled,
            mutation_key="covenant-key",
        )
        self.assertNotEqual(updated.digest, self.compiled.digest)

        same_version = replace(changed, version="1.0.0")
        with self.assertRaises(ManifoldCompileError):
            ManifoldCompiler.compile(
                same_version,
                previous=self.compiled,
                mutation_key="covenant-key",
            )

    def test_seraph_bridge_commits_only_when_manifold_is_proven(self):
        governance_input = GovernanceInput(
            constraints=closed_constraints(),
            trajectory=("observe", "observe"),
            prp_trail=healthy_trail(),
            request_commit=True,
        )
        safe = govern_transition(
            self.compiled,
            self.state,
            proposal_for(self.state, self.safe_effect),
            governance_input,
        )

        self.assertTrue(safe.manifold_proven)
        self.assertEqual(safe.governance.decision, Decision.COMMIT)

        unsafe = govern_transition(
            self.compiled,
            self.state,
            proposal_for(
                self.state,
                replace(self.safe_effect, after=0.5),
            ),
            replace(
                governance_input,
                constraints=closed_constraints(),
                prp_trail=healthy_trail(),
            ),
        )

        self.assertFalse(unsafe.manifold_proven)
        self.assertEqual(unsafe.governance.decision, Decision.DENY)
        self.assertIn("integrity_failure", unsafe.governance.reasons)

    def test_unresolved_manifold_becomes_seraph_evidence_failure(self):
        result = govern_transition(
            self.compiled,
            self.state,
            proposal_for(self.state, self.safe_effect, evidence=False),
            GovernanceInput(
                constraints=closed_constraints(),
                trajectory=("observe", "observe"),
                prp_trail=healthy_trail(),
                request_commit=True,
            ),
        )

        self.assertEqual(
            result.certificate.verdict,
            ManifoldVerdict.UNRESOLVED,
        )
        self.assertEqual(result.governance.decision, Decision.DENY)
        self.assertIn("evidence_fidelity_loss", result.governance.reasons)


if __name__ == "__main__":
    unittest.main()
