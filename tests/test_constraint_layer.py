import unittest
from dataclasses import replace

from seraph import (
    CONSTRAINT_FRAME_CONTRACT_VERSION,
    ConstraintEvaluationEnvelope,
    ConstraintFrame,
    ConstraintObservation,
    ConstraintResolution,
    constraint_frame_contract_descriptor,
    constraint_frame_contract_fingerprint,
    evaluate_constraints,
)

from tests.helpers import closed_constraints


class ConstraintLayerTests(unittest.TestCase):
    def test_closed_frame_is_proven_without_scalar_aggregation(self):
        result = evaluate_constraints(closed_constraints())

        self.assertTrue(result.closed)
        self.assertEqual(result.resolution, ConstraintResolution.PROVEN)
        self.assertEqual(result.reason, "constraint_frame_closed")
        self.assertFalse(hasattr(result, "strength"))

    def test_refuted_required_relation_opens_frame(self):
        frame = ConstraintFrame(
            frame_id="refuted",
            topology_id="tests",
            topology_version="1",
            transition_id="t1",
            required_relations=("recovery_viability",),
            observations=(
                ConstraintObservation(
                    "recovery_viability",
                    ConstraintResolution.REFUTED,
                    evidence_ref="test",
                ),
            ),
        )

        result = evaluate_constraints(frame)

        self.assertFalse(result.closed)
        self.assertEqual(result.resolution, ConstraintResolution.REFUTED)
        self.assertEqual(result.refuted, ("recovery_viability",))

    def test_unresolved_required_relation_stays_explicit(self):
        frame = ConstraintFrame(
            frame_id="unresolved",
            topology_id="tests",
            topology_version="1",
            transition_id="t1",
            required_relations=("scope_alignment",),
            observations=(
                ConstraintObservation(
                    "scope_alignment",
                    ConstraintResolution.UNRESOLVED,
                ),
            ),
        )

        result = evaluate_constraints(frame)

        self.assertFalse(result.closed)
        self.assertEqual(result.resolution, ConstraintResolution.UNRESOLVED)
        self.assertEqual(result.unresolved, ("scope_alignment",))

    def test_omitted_required_relation_is_unresolved(self):
        frame = ConstraintFrame(
            frame_id="omitted",
            topology_id="tests",
            topology_version="1",
            transition_id="t1",
            required_relations=("scope_alignment", "sensitive_gate"),
            observations=(
                ConstraintObservation(
                    "scope_alignment",
                    ConstraintResolution.PROVEN,
                    evidence_ref="test",
                ),
            ),
        )

        result = evaluate_constraints(frame)

        self.assertFalse(result.closed)
        self.assertEqual(result.required_count, 2)
        self.assertEqual(result.unresolved, ("sensitive_gate",))

    def test_extra_observation_cannot_replace_required_relation(self):
        frame = ConstraintFrame(
            frame_id="substitution",
            topology_id="tests",
            topology_version="1",
            transition_id="t1",
            required_relations=("sensitive_gate",),
            observations=(
                ConstraintObservation(
                    "easy_unrelated_check",
                    ConstraintResolution.PROVEN,
                    evidence_ref="test",
                ),
            ),
        )

        result = evaluate_constraints(frame)

        self.assertEqual(result.resolution, ConstraintResolution.UNRESOLVED)
        self.assertEqual(result.proven, ())
        self.assertEqual(result.unresolved, ("sensitive_gate",))

    def test_evaluation_envelope_binds_contract_frame_and_result(self):
        frame = closed_constraints()
        envelope = ConstraintEvaluationEnvelope.evaluate(frame)

        self.assertTrue(envelope.valid())
        self.assertTrue(envelope.closed)
        self.assertEqual(envelope.contract_version, CONSTRAINT_FRAME_CONTRACT_VERSION)
        self.assertEqual(
            envelope.contract_fingerprint,
            constraint_frame_contract_fingerprint(),
        )
        self.assertEqual(envelope.frame_digest, frame.digest)
        self.assertEqual(envelope.result_digest, envelope.result.digest)
        self.assertEqual(
            constraint_frame_contract_descriptor()["authority_scope"],
            "event_local_commit",
        )

    def test_evaluation_envelope_wire_shape_is_explicit(self):
        wire = ConstraintEvaluationEnvelope.evaluate(closed_constraints()).to_wire()

        self.assertEqual(
            set(wire),
            {
                "contract_version",
                "contract_fingerprint",
                "frame",
                "result",
                "frame_digest",
                "result_digest",
            },
        )
        self.assertEqual(wire["result"]["resolution"], "proven")
        self.assertEqual(wire["frame"]["transition_id"], "test-transition")

    def test_evaluation_envelope_rejects_tampered_result(self):
        envelope = ConstraintEvaluationEnvelope.evaluate(closed_constraints())
        tampered_result = replace(
            envelope.result,
            transition_id="different-transition",
        )
        tampered = replace(
            envelope,
            result=tampered_result,
            result_digest=tampered_result.digest,
        )

        self.assertFalse(tampered.valid())
        self.assertFalse(tampered.closed)

    def test_evaluation_envelope_rejects_contract_drift(self):
        envelope = ConstraintEvaluationEnvelope.evaluate(closed_constraints())

        self.assertFalse(replace(envelope, contract_version="2.0.0").valid())
        self.assertFalse(replace(envelope, contract_fingerprint="0" * 64).valid())

    def test_evaluation_envelope_invalid_result_type_fails_closed(self):
        envelope = ConstraintEvaluationEnvelope.evaluate(closed_constraints())

        self.assertFalse(replace(envelope, result=object()).valid())


if __name__ == "__main__":
    unittest.main()
