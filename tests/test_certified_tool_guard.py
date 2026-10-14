import unittest
from dataclasses import replace

from adapters.certified_tool_guard import (
    CertifiedToolGuard,
    ExecutionBindingError,
    ExecutionPermitRejected,
    PostconditionDivergence,
    bind_execution,
    execution_call_digest,
)
from seraph import (
    Decision,
    FunctionalEffect,
    GovernanceInput,
    ManifoldCompiler,
    ManifoldVerdict,
)

from tests.helpers import closed_constraints, healthy_trail
from tests.test_manifold_compiler import (
    manifold_spec,
    manifold_state,
    proposal_for,
)


class CertifiedToolGuardTests(unittest.TestCase):
    def setUp(self):
        self.__seraph_binding__ = "certified-tool-guard-test"
        self.compiled = ManifoldCompiler.compile(manifold_spec())
        self.state = manifold_state()
        self.divergences = []
        self.guard = CertifiedToolGuard(
            compiled=self.compiled,
            state_reader=lambda: self.state,
            governance_input_reader=self._governance_input,
            on_divergence=self.divergences.append,
        )

    @staticmethod
    def _governance_input():
        return GovernanceInput(
            constraints=closed_constraints(),
            trajectory=("observe", "observe"),
            prp_trail=healthy_trail(),
            request_commit=True,
        )

    def _set_alice_safety(self, value):
        alice = self.state.entities[0].with_coordinate("safety", value)
        self.state = replace(
            self.state,
            state_id=f"{self.state.state_id}->executed",
            entities=(alice, *self.state.entities[1:]),
        )
        return value

    def _do_nothing(self, value):
        return value

    def _safe_proposal(self, fn=None, value=0.8):
        function = self._set_alice_safety if fn is None else fn
        effect = FunctionalEffect(
            subject_id="alice",
            coordinate="safety",
            before=0.7,
            after=value,
            reversible=True,
        )
        proposal = proposal_for(self.state, effect)
        return bind_execution(proposal, function, (value,))

    def test_exact_call_executes_and_releases_verified_result(self):
        proposal = self._safe_proposal()
        permit = self.guard.authorize(
            self._set_alice_safety,
            proposal,
            (0.8,),
        )

        execution = self.guard.execute(
            permit,
            self._set_alice_safety,
            proposal,
            (0.8,),
        )

        self.assertEqual(execution.result, 0.8)
        self.assertTrue(execution.realization.matches)
        self.assertEqual(
            permit.adjudication.governance.decision,
            Decision.COMMIT,
        )
        self.assertEqual(self.state.entities[0].coordinate_map()["safety"], 0.8)

    def test_permit_is_one_use(self):
        proposal = self._safe_proposal()
        permit = self.guard.authorize(
            self._set_alice_safety,
            proposal,
            (0.8,),
        )
        self.guard.execute(
            permit,
            self._set_alice_safety,
            proposal,
            (0.8,),
        )

        with self.assertRaises(ExecutionPermitRejected):
            self.guard.execute(
                permit,
                self._set_alice_safety,
                proposal,
                (0.8,),
            )

    def test_changed_arguments_reject_and_consume_permit(self):
        proposal = self._safe_proposal()
        permit = self.guard.authorize(
            self._set_alice_safety,
            proposal,
            (0.8,),
        )

        with self.assertRaises(ExecutionPermitRejected):
            self.guard.execute(
                permit,
                self._set_alice_safety,
                proposal,
                (0.9,),
            )
        with self.assertRaises(ExecutionPermitRejected):
            self.guard.execute(
                permit,
                self._set_alice_safety,
                proposal,
                (0.8,),
            )
        self.assertEqual(self.state.entities[0].coordinate_map()["safety"], 0.7)

    def test_changed_callable_rejects_permit(self):
        proposal = self._safe_proposal()
        permit = self.guard.authorize(
            self._set_alice_safety,
            proposal,
            (0.8,),
        )

        with self.assertRaises(ExecutionPermitRejected):
            self.guard.execute(
                permit,
                self._do_nothing,
                proposal,
                (0.8,),
            )

    def test_state_change_between_authorization_and_execution_is_stale(self):
        proposal = self._safe_proposal()
        permit = self.guard.authorize(
            self._set_alice_safety,
            proposal,
            (0.8,),
        )
        bob = self.state.entities[1].with_coordinate("agency", 0.89)
        self.state = replace(
            self.state,
            state_id="state-changed",
            entities=(self.state.entities[0], bob, self.state.entities[2]),
        )

        with self.assertRaisesRegex(
            ExecutionPermitRejected,
            "stale",
        ):
            self.guard.execute(
                permit,
                self._set_alice_safety,
                proposal,
                (0.8,),
            )

    def test_realized_state_divergence_is_contained_before_result_release(self):
        proposal = self._safe_proposal(fn=self._do_nothing)
        permit = self.guard.authorize(
            self._do_nothing,
            proposal,
            (0.8,),
        )

        with self.assertRaises(PostconditionDivergence) as raised:
            self.guard.execute(
                permit,
                self._do_nothing,
                proposal,
                (0.8,),
            )

        self.assertEqual(
            raised.exception.report.verdict,
            ManifoldVerdict.REFUTED,
        )
        self.assertEqual(len(self.divergences), 1)
        self.assertIn(
            "realized_state_diverged",
            self.divergences[0].reasons,
        )

    def test_refuted_manifold_never_issues_permit(self):
        proposal = self._safe_proposal(value=0.5)

        with self.assertRaises(ExecutionPermitRejected):
            self.guard.authorize(
                self._set_alice_safety,
                proposal,
                (0.5,),
            )
        self.assertEqual(self.guard._permits, {})

    def test_unbound_proposal_never_issues_permit(self):
        effect = FunctionalEffect(
            "alice", "safety", 0.7, 0.8, True
        )
        proposal = proposal_for(self.state, effect)

        with self.assertRaisesRegex(
            ExecutionPermitRejected,
            "no execution binding",
        ):
            self.guard.authorize(
                self._set_alice_safety,
                proposal,
                (0.8,),
            )

    def test_opaque_arguments_fail_closed_instead_of_using_repr(self):
        with self.assertRaises(ExecutionBindingError):
            execution_call_digest(
                self._do_nothing,
                (object(),),
            )

    def test_bound_callable_without_receiver_identity_fails_closed(self):
        class OpaqueReceiver:
            def run(self, value):
                return value

        with self.assertRaisesRegex(
            ExecutionBindingError,
            "__seraph_binding__",
        ):
            execution_call_digest(OpaqueReceiver().run, (0.8,))

    def test_changed_seraph_adjudication_invalidates_permit(self):
        request_commit = True

        def governance_input():
            return GovernanceInput(
                constraints=closed_constraints(),
                trajectory=("observe", "observe"),
                prp_trail=healthy_trail(),
                request_commit=request_commit,
            )

        guard = CertifiedToolGuard(
            compiled=self.compiled,
            state_reader=lambda: self.state,
            governance_input_reader=governance_input,
        )
        proposal = self._safe_proposal()
        permit = guard.authorize(
            self._set_alice_safety,
            proposal,
            (0.8,),
        )
        request_commit = False

        with self.assertRaisesRegex(
            ExecutionPermitRejected,
            "stale",
        ):
            guard.execute(
                permit,
                self._set_alice_safety,
                proposal,
                (0.8,),
            )

    def test_audit_state_label_does_not_make_geometry_stale(self):
        proposal = self._safe_proposal()
        permit = self.guard.authorize(
            self._set_alice_safety,
            proposal,
            (0.8,),
        )
        self.state = replace(self.state, state_id="renamed-observation")

        execution = self.guard.execute(
            permit,
            self._set_alice_safety,
            proposal,
            (0.8,),
        )

        self.assertTrue(execution.realization.matches)


if __name__ == "__main__":
    unittest.main()
