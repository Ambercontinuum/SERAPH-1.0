"""Adversarial coverage for adapters/capability_runtime.py.

Treats the module's own safety claims as unproven and looks for concrete
counterexamples. Added 2026-07-24 per explicit adversarial-review request;
implementation is NOT modified by this file.
"""

import unittest
from dataclasses import replace

from adapters.capability_runtime import (
    CapabilityDenied,
    CapabilityRegistry,
    CapabilityRuntime,
    CapabilityScope,
    RegisteredCapability,
)
from adapters.certified_tool_guard import CertifiedToolGuard
from seraph import GovernanceInput

from tests.helpers import closed_constraints, healthy_trail
from tests.test_manifold_compiler import manifold_spec, manifold_state, proposal_for
from seraph import ManifoldCompiler


class _SequencedStateReader:
    """Returns a fixed sequence of states; the last state repeats after that.

    Models exactly what CapabilityRuntime.authorize() actually does: it calls
    `self.guard.state_reader()` once for _validate_scope, and
    CertifiedToolGuard.authorize() independently calls the *same* callable
    again for its own governance read. If those two calls can observe two
    different snapshots, scope enforcement and governance enforcement are not
    evaluated against the same reality.
    """

    def __init__(self, states):
        self._states = list(states)
        self.calls = 0

    def __call__(self):
        index = min(self.calls, len(self._states) - 1)
        self.calls += 1
        return self._states[index]


class CapabilityScopeToctouTests(unittest.TestCase):
    """`_validate_scope` and the guard's governance check read state
    independently and under different locks. The claim in
    capability_runtime.py ("every declared effect must fit the immutable
    scope of the registered callable before the manifold sees the
    transition") implies one consistent observation; nothing enforces that.
    """

    def setUp(self):
        self.__seraph_binding__ = "capability-scope-toctou-test"

        base = manifold_state()
        alice_privileged = base.entities[0].with_coordinate(
            "safety", base.entities[0].coordinate_map()["safety"]
        )
        alice_privileged = replace(
            alice_privileged,
            roles=("inhabitant", "trusted-operator"),
        )
        self.state_privileged = replace(
            base,
            state_id="state-privileged",
            entities=(alice_privileged, *base.entities[1:]),
        )

        alice_demoted = replace(alice_privileged, roles=("inhabitant",))
        self.state_demoted = replace(
            base,
            state_id="state-demoted",
            entities=(alice_demoted, *base.entities[1:]),
        )

        self.compiled = ManifoldCompiler.compile(manifold_spec())

    @staticmethod
    def _governance_input():
        return GovernanceInput(
            constraints=closed_constraints(),
            trajectory=("observe", "observe"),
            prp_trail=healthy_trail(),
            request_commit=True,
        )

    def _set_alice_safety(self, value):
        alice = self.state_demoted.entities[0].with_coordinate("safety", value)
        self.state_demoted = replace(
            self.state_demoted,
            state_id="state-demoted->executed",
            entities=(alice, *self.state_demoted.entities[1:]),
        )
        return value

    def test_scope_check_reading_stale_state_lets_a_demoted_entity_through(self):
        """Capability is scoped to 'trusted-operator' only. Alice holds that
        role in the FIRST state the reader will return (read by
        CapabilityRuntime._validate_scope) but not in the SECOND state (read
        by CertifiedToolGuard.authorize()'s own governance check, which is
        what the proposal is actually bound to). No InvariantRule in this
        manifold references 'trusted-operator', so nothing downstream of the
        scope check would ever catch the demotion.

        A correct implementation must deny this: by the time of the real,
        proposal-bound observation, Alice is not a trusted-operator, so a
        capability scoped to that role must not be authorized against her.
        """
        reader = _SequencedStateReader([self.state_privileged, self.state_demoted])
        guard = CertifiedToolGuard(
            compiled=self.compiled,
            state_reader=reader,
            governance_input_reader=self._governance_input,
        )
        registry = CapabilityRegistry(
            (
                RegisteredCapability(
                    capability_id="trusted_operator.increase_safety",
                    fn=self._set_alice_safety,
                    scopes=(
                        CapabilityScope(
                            coordinate="safety",
                            subject_roles=("trusted-operator",),
                        ),
                    ),
                ),
            )
        )
        runtime = CapabilityRuntime(registry=registry, guard=guard)

        proposal = proposal_for(
            self.state_demoted,
            __import__("seraph").FunctionalEffect(
                subject_id="alice",
                coordinate="safety",
                before=0.7,
                after=0.8,
                reversible=True,
            ),
        )

        with self.assertRaises(CapabilityDenied):
            runtime.authorize(
                "trusted_operator.increase_safety",
                proposal,
                (0.8,),
            )


if __name__ == "__main__":
    unittest.main()
