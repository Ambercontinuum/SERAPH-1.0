from __future__ import annotations

from dataclasses import replace
import unittest

from seraph import (
    ConsequenceEdge,
    Coordinate,
    EntityState,
    FunctionalEffect,
    InvariantRelation,
    InvariantRule,
    ManifoldCompileError,
    ManifoldCompiler,
    ManifoldSpec,
    ManifoldState,
    ManifoldVerdict,
    TransitionProposal,
    functional_state_digest,
)


def topology_spec(
    *edges: ConsequenceEdge,
    version: str = "1.0.0",
) -> ManifoldSpec:
    return ManifoldSpec(
        manifold_id="tests.affected-set",
        version=version,
        coordinate_names=("safety",),
        admitted_origins=("operator",),
        mutation_keys=("topology-authority",),
        rules=(
            InvariantRule(
                rule_id="inhabitant.safety.nondecreasing",
                coordinate="safety",
                relation=InvariantRelation.NONDECREASING,
                subject_roles=("inhabitant",),
            ),
        ),
        consequence_edges=edges,
    )


def topology_state() -> ManifoldState:
    return ManifoldState(
        state_id="state-0",
        entities=(
            EntityState("service", ("system",), (Coordinate("safety", 1.0),)),
            EntityState("relay", ("system",), (Coordinate("safety", 1.0),)),
            EntityState("alice", ("inhabitant",), (Coordinate("safety", 0.9),)),
            EntityState("bob", ("inhabitant",), (Coordinate("safety", 0.8),)),
        ),
    )


def effect(subject_id: str, before: float, after: float) -> FunctionalEffect:
    return FunctionalEffect(subject_id, "safety", before, after, True)


def proposal(
    state: ManifoldState,
    *effects: FunctionalEffect,
    affected: tuple[str, ...],
    version: str = "1.0.0",
) -> TransitionProposal:
    return TransitionProposal(
        proposal_id="transition-1",
        manifold_id="tests.affected-set",
        manifold_version=version,
        source_state_digest=functional_state_digest(state),
        actor_id="agent",
        origin_id="operator",
        effects=effects,
        affected_inhabitants=affected,
    )


class AffectedSetClosureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = topology_state()
        self.edges = (
            ConsequenceEdge("service", "relay"),
            ConsequenceEdge("relay", "bob"),
        )
        self.compiled = ManifoldCompiler.compile(topology_spec(*self.edges))
        self.service_effect = effect("service", 1.0, 1.0)
        self.bob_effect = effect("bob", 0.8, 0.8)

    def test_transitive_inhabitant_is_derived_and_bound(self) -> None:
        candidate = proposal(
            self.state,
            self.service_effect,
            self.bob_effect,
            affected=("bob",),
        )

        certificate = self.compiled.evaluate(self.state, candidate)

        self.assertEqual(certificate.verdict, ManifoldVerdict.PROVEN)
        self.assertEqual(
            certificate.affected_set.seed_entities,
            ("bob", "service"),
        )
        self.assertEqual(
            certificate.affected_set.reached_entities,
            ("bob", "relay", "service"),
        )
        self.assertEqual(
            certificate.affected_set.affected_inhabitants,
            ("bob",),
        )
        self.assertTrue(certificate.affected_set.complete)

    def test_transitive_inhabitant_omission_is_refuted(self) -> None:
        candidate = proposal(
            self.state,
            self.service_effect,
            affected=(),
        )

        certificate = self.compiled.evaluate(self.state, candidate)

        self.assertEqual(certificate.verdict, ManifoldVerdict.REFUTED)
        self.assertIn("affected_inhabitant_omitted", certificate.reasons)
        self.assertIn("affected_inhabitant_effect_omitted", certificate.reasons)

    def test_declaring_impact_without_modeling_effect_is_refuted(self) -> None:
        candidate = proposal(
            self.state,
            self.service_effect,
            affected=("bob",),
        )

        certificate = self.compiled.evaluate(self.state, candidate)

        self.assertEqual(certificate.verdict, ManifoldVerdict.REFUTED)
        self.assertNotIn("affected_inhabitant_omitted", certificate.reasons)
        self.assertIn("affected_inhabitant_effect_omitted", certificate.reasons)

    def test_extra_affected_inhabitant_is_not_accepted_as_precision(self) -> None:
        candidate = proposal(
            self.state,
            self.service_effect,
            self.bob_effect,
            affected=("alice", "bob"),
        )

        certificate = self.compiled.evaluate(self.state, candidate)

        self.assertEqual(certificate.verdict, ManifoldVerdict.REFUTED)
        self.assertIn("affected_inhabitant_not_derived", certificate.reasons)

    def test_cycles_terminate_and_edge_order_does_not_change_closure(self) -> None:
        cyclic_edges = (
            ConsequenceEdge("relay", "service"),
            *self.edges,
        )
        first = ManifoldCompiler.compile(topology_spec(*cyclic_edges))
        second = ManifoldCompiler.compile(topology_spec(*reversed(cyclic_edges)))
        candidate = proposal(
            self.state,
            self.service_effect,
            self.bob_effect,
            affected=("bob",),
        )

        first_closure = first.derive_affected_set(self.state, candidate)
        second_closure = second.derive_affected_set(self.state, candidate)

        self.assertEqual(first_closure, second_closure)
        self.assertEqual(first.digest, second.digest)

    def test_unknown_topology_endpoint_fails_closed(self) -> None:
        compiled = ManifoldCompiler.compile(
            topology_spec(ConsequenceEdge("service", "unknown-inhabitant"))
        )
        candidate = proposal(
            self.state,
            self.service_effect,
            affected=(),
        )

        certificate = compiled.evaluate(self.state, candidate)

        self.assertEqual(certificate.verdict, ManifoldVerdict.UNRESOLVED)
        self.assertIn("topology_entity_unobserved", certificate.reasons)
        self.assertEqual(
            certificate.affected_set.unresolved_entities,
            ("unknown-inhabitant",),
        )

    def test_unknown_alias_cannot_bypass_entity_binding(self) -> None:
        candidate = proposal(
            self.state,
            effect("service-alias", 1.0, 1.0),
            affected=(),
        )

        certificate = self.compiled.evaluate(self.state, candidate)

        self.assertEqual(certificate.verdict, ManifoldVerdict.UNRESOLVED)
        self.assertIn("unknown_effect_subject", certificate.reasons)
        self.assertIn("topology_entity_unobserved", certificate.reasons)

    def test_duplicate_edges_are_rejected(self) -> None:
        with self.assertRaises(ManifoldCompileError) as raised:
            ManifoldCompiler.compile(
                topology_spec(
                    ConsequenceEdge("service", "bob"),
                    ConsequenceEdge("service", "bob"),
                )
            )

        self.assertIn("invalid_consequence_edges", raised.exception.errors)

    def test_topology_mutation_invalidates_prior_certificate(self) -> None:
        candidate = proposal(
            self.state,
            self.service_effect,
            self.bob_effect,
            affected=("bob",),
        )
        certificate = self.compiled.evaluate(self.state, candidate)
        changed = replace(
            topology_spec(*self.edges),
            version="2.0.0",
            consequence_edges=(ConsequenceEdge("service", "alice"),),
        )
        updated = ManifoldCompiler.compile(
            changed,
            previous=self.compiled,
            mutation_key="topology-authority",
        )

        self.assertFalse(
            updated.verify_certificate(certificate, self.state, candidate)
        )


if __name__ == "__main__":
    unittest.main()
