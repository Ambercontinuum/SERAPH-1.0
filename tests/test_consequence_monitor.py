import unittest
from dataclasses import replace

from seraph import (
    AuditAnchorError,
    ConsequenceMonitor,
    ConsequenceMonitorError,
    ConsequenceStatus,
    FunctionalEffect,
    HMACAnchorWitness,
    HashChainJournal,
    ManifoldCompiler,
    ManifoldState,
)

from tests.test_manifold_compiler import (
    manifold_spec,
    manifold_state,
    proposal_for,
)


class ConsequenceMonitorTests(unittest.TestCase):
    def setUp(self):
        self.compiled = ManifoldCompiler.compile(manifold_spec())
        self.source = manifold_state()
        effect = FunctionalEffect(
            "alice", "safety", 0.7, 0.8, True
        )
        self.proposal = proposal_for(self.source, effect)
        self.certificate = self.compiled.evaluate(
            self.source,
            self.proposal,
        )
        self.expected = ManifoldState(
            state_id="post-execution",
            entities=(
                self.source.entities[0].with_coordinate("safety", 0.8),
                *self.source.entities[1:],
            ),
        )
        self.failures = []
        self.observed = self.expected
        self.monitor = ConsequenceMonitor(
            compiled=self.compiled,
            state_reader=lambda: self.observed,
            on_failure=self.failures.append,
        )

    def test_multiple_checkpoints_complete_and_are_audited(self):
        ticket = self.monitor.start(self.certificate, checkpoints=2)

        first = self.monitor.observe(ticket)
        second = self.monitor.observe(ticket)

        self.assertEqual(first.status, ConsequenceStatus.ACTIVE)
        self.assertEqual(first.remaining_checkpoints, 1)
        self.assertEqual(second.status, ConsequenceStatus.COMPLETE)
        self.assertEqual(second.remaining_checkpoints, 0)
        self.assertEqual(second.audit_head, self.monitor.journal.head)
        self.assertTrue(self.monitor.journal.verify())
        self.assertEqual(self.failures, [])

    def test_delayed_effect_divergence_closes_ticket_and_contains(self):
        ticket = self.monitor.start(self.certificate, checkpoints=3)
        self.monitor.observe(ticket)
        delayed_change = replace(
            self.expected,
            state_id="delayed-effect",
            entities=(
                self.expected.entities[0].with_coordinate("safety", 0.79),
                *self.expected.entities[1:],
            ),
        )

        self.observed = delayed_change
        observation = self.monitor.observe(ticket)

        self.assertEqual(
            observation.status,
            ConsequenceStatus.DIVERGED,
        )
        self.assertEqual(len(self.failures), 1)
        self.assertEqual(
            self.monitor.journal.events[-1].event_type,
            "consequence.delayed_divergence",
        )
        with self.assertRaises(ConsequenceMonitorError):
            self.monitor.observe(ticket)

    def test_missed_checkpoint_fails_closed(self):
        ticket = self.monitor.start(self.certificate, checkpoints=2)

        observation = self.monitor.miss(
            ticket,
            reason_code="observer_unavailable",
        )

        self.assertEqual(observation.status, ConsequenceStatus.MISSED)
        self.assertEqual(len(self.failures), 1)
        self.assertEqual(
            self.monitor.journal.events[-1].event_type,
            "consequence.checkpoint_missed",
        )
        with self.assertRaises(ConsequenceMonitorError):
            self.monitor.observe(ticket)

    def test_tampered_ticket_is_rejected_and_original_is_consumed(self):
        ticket = self.monitor.start(self.certificate, checkpoints=2)
        tampered = replace(ticket, expected_state_digest="0" * 64)

        with self.assertRaises(ConsequenceMonitorError):
            self.monitor.observe(tampered)
        with self.assertRaises(ConsequenceMonitorError):
            self.monitor.observe(ticket)

    def test_non_proven_certificate_cannot_start_monitor(self):
        harmful = proposal_for(
            self.source,
            FunctionalEffect(
                "alice", "safety", 0.7, 0.5, True
            ),
        )
        certificate = self.compiled.evaluate(self.source, harmful)

        with self.assertRaises(ConsequenceMonitorError):
            self.monitor.start(certificate, checkpoints=1)


class AuditAnchorTests(unittest.TestCase):
    def setUp(self):
        self.journal = HashChainJournal()
        self.journal.append("authorization", {"proposal": "p1"})
        self.witness = HMACAnchorWitness(
            witness_id="independent-witness",
            secret=b"a" * 32,
        )

    def test_receipts_authenticate_journal_and_form_chain(self):
        first = self.witness.attest(self.journal)
        self.journal.append("execution", {"result": "matched"})
        second = self.witness.attest(self.journal)

        self.assertTrue(self.witness.verify(first))
        self.assertTrue(self.witness.verify(second))
        self.assertTrue(self.witness.verify_chain((first, second)))
        self.assertTrue(self.witness.verify_journal(second, self.journal))

    def test_receipt_tampering_and_alternate_history_are_detected(self):
        receipt = self.witness.attest(self.journal)
        tampered = replace(receipt, journal_head="f" * 64)
        alternate = HashChainJournal()
        alternate.append("authorization", {"proposal": "different"})

        self.assertFalse(self.witness.verify(tampered))
        self.assertFalse(self.witness.verify_journal(receipt, alternate))

    def test_wrong_witness_cannot_verify_receipt(self):
        receipt = self.witness.attest(self.journal)
        wrong = HMACAnchorWitness(
            witness_id="independent-witness",
            secret=b"b" * 32,
        )

        self.assertFalse(wrong.verify(receipt))

    def test_witness_rejects_nonadvancing_head(self):
        self.witness.attest(self.journal)

        with self.assertRaises(AuditAnchorError):
            self.witness.attest(self.journal)

    def test_witness_rejects_longer_forked_history(self):
        self.witness.attest(self.journal)
        fork = HashChainJournal()
        fork.append("authorization", {"proposal": "fork"})
        fork.append("execution", {"result": "fork"})

        with self.assertRaisesRegex(AuditAnchorError, "extend"):
            self.witness.attest(fork)

    def test_short_anchor_secret_is_rejected(self):
        with self.assertRaises(AuditAnchorError):
            HMACAnchorWitness("weak-witness", b"short")


if __name__ == "__main__":
    unittest.main()
