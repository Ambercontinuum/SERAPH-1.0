import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from adapters.capability_runtime import (
    CapabilityDenied,
    CapabilityRegistry,
    CapabilityRegistryError,
    CapabilityRuntime,
    CapabilityScope,
    RegisteredCapability,
)
from adapters.certified_tool_guard import (
    CertifiedToolGuard,
    PostconditionDivergence,
)
from seraph import (
    AuditChainError,
    FunctionalEffect,
    GovernanceInput,
    HashChainJournal,
    ManifoldCompiler,
)

from tests.helpers import closed_constraints, healthy_trail
from tests.test_manifold_compiler import (
    manifold_spec,
    manifold_state,
    proposal_for,
)


class CapabilityRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.__seraph_binding__ = "capability-runtime-test"
        self.state = manifold_state()
        compiled = ManifoldCompiler.compile(manifold_spec())
        guard = CertifiedToolGuard(
            compiled=compiled,
            state_reader=lambda: self.state,
            governance_input_reader=self._governance_input,
        )
        self.registry = CapabilityRegistry(
            (
                RegisteredCapability(
                    capability_id="inhabitant.increase_safety",
                    fn=self._set_alice_safety,
                    scopes=(
                        CapabilityScope(
                            coordinate="safety",
                            subject_roles=("inhabitant",),
                        ),
                    ),
                ),
            )
        )
        self.runtime = CapabilityRuntime(
            registry=self.registry,
            guard=guard,
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
            state_id=f"{self.state.state_id}->capability",
            entities=(alice, *self.state.entities[1:]),
        )
        return value

    def _do_nothing(self, value):
        return value

    def _proposal(self, coordinate="safety", before=0.7, after=0.8):
        return proposal_for(
            self.state,
            FunctionalEffect(
                subject_id="alice",
                coordinate=coordinate,
                before=before,
                after=after,
                reversible=True,
            ),
        )

    def test_registered_capability_executes_without_returning_callable(self):
        permit = self.runtime.authorize(
            "inhabitant.increase_safety",
            self._proposal(),
            (0.8,),
        )

        result = self.runtime.execute(permit)

        self.assertEqual(result.capability_id, "inhabitant.increase_safety")
        self.assertEqual(result.execution.result, 0.8)
        self.assertEqual(self.state.entities[0].coordinate_map()["safety"], 0.8)
        self.assertEqual(result.audit_head, self.runtime.journal.head)
        self.assertFalse(hasattr(permit, "fn"))
        self.assertFalse(hasattr(permit, "call_args"))

    def test_effect_outside_registered_scope_is_denied_and_audited(self):
        proposal = self._proposal(
            coordinate="agency",
            before=0.8,
            after=0.9,
        )

        with self.assertRaisesRegex(CapabilityDenied, "scope"):
            self.runtime.authorize(
                "inhabitant.increase_safety",
                proposal,
                (0.9,),
            )

        self.assertEqual(
            self.runtime.journal.events[-1].event_type,
            "capability.authorization_denied",
        )

    def test_unknown_capability_is_denied_and_audited(self):
        with self.assertRaisesRegex(CapabilityDenied, "unknown"):
            self.runtime.authorize(
                "unregistered.shell",
                self._proposal(),
                (0.8,),
            )

        self.assertEqual(
            self.runtime.journal.events[-1].event_type,
            "capability.authorization_denied",
        )

    def test_tampered_permit_is_rejected_and_original_is_consumed(self):
        permit = self.runtime.authorize(
            "inhabitant.increase_safety",
            self._proposal(),
            (0.8,),
        )
        tampered = replace(permit, capability_id="unregistered.shell")

        with self.assertRaises(CapabilityDenied):
            self.runtime.execute(tampered)
        with self.assertRaises(CapabilityDenied):
            self.runtime.execute(permit)
        self.assertEqual(self.state.entities[0].coordinate_map()["safety"], 0.7)

    def test_permit_replay_is_rejected_and_journal_remains_valid(self):
        permit = self.runtime.authorize(
            "inhabitant.increase_safety",
            self._proposal(),
            (0.8,),
        )
        self.runtime.execute(permit)

        with self.assertRaises(CapabilityDenied):
            self.runtime.execute(permit)

        self.assertTrue(self.runtime.journal.verify())
        event_types = tuple(
            event.event_type for event in self.runtime.journal.events
        )
        self.assertEqual(
            event_types[:4],
            (
                "capability.authorization_requested",
                "capability.authorized",
                "capability.permit_consumed",
                "capability.executed",
            ),
        )
        self.assertEqual(
            event_types[-1],
            "capability.permit_rejected",
        )

    def test_divergence_is_recorded_in_hash_chain(self):
        registry = CapabilityRegistry(
            (
                RegisteredCapability(
                    capability_id="broken.safety",
                    fn=self._do_nothing,
                    scopes=(
                        CapabilityScope(
                            coordinate="safety",
                            subject_roles=("inhabitant",),
                        ),
                    ),
                ),
            )
        )
        runtime = CapabilityRuntime(
            registry=registry,
            guard=self.runtime.guard,
        )
        permit = runtime.authorize(
            "broken.safety",
            self._proposal(),
            (0.8,),
        )

        with self.assertRaises(PostconditionDivergence):
            runtime.execute(permit)

        self.assertEqual(
            runtime.journal.events[-1].event_type,
            "capability.execution_diverged",
        )
        self.assertTrue(runtime.journal.verify())

    def test_duplicate_capability_ids_are_rejected(self):
        capability = RegisteredCapability(
            capability_id="duplicate",
            fn=self._set_alice_safety,
            scopes=(
                CapabilityScope(
                    coordinate="safety",
                    subject_roles=("inhabitant",),
                ),
            ),
        )

        with self.assertRaises(CapabilityRegistryError):
            CapabilityRegistry((capability, capability))


class HashChainJournalTests(unittest.TestCase):
    def test_persistent_chain_reloads_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "governance.jsonl"
            journal = HashChainJournal(path)
            journal.append("authorization", {"proposal": "p1"})
            journal.append("execution", {"result": "matched"})

            reloaded = HashChainJournal(path)
            self.assertTrue(reloaded.verify())
            self.assertEqual(reloaded.head, journal.head)

            lines = path.read_text(encoding="utf-8").splitlines()
            first = json.loads(lines[0])
            first["payload_json"] = '{"proposal":"tampered"}'
            lines[0] = json.dumps(
                first,
                sort_keys=True,
                separators=(",", ":"),
            )
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            with self.assertRaises(AuditChainError):
                HashChainJournal(path)

    def test_noncanonical_payload_fails_closed(self):
        journal = HashChainJournal()

        with self.assertRaises(AuditChainError):
            journal.append("opaque", {"value": object()})


if __name__ == "__main__":
    unittest.main()
