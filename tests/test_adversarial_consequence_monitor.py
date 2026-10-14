"""Adversarial coverage for seraph/consequence_monitor.py.

Treats "delayed postcondition divergence" monitoring as unproven and checks
whether it can distinguish a genuinely realized state from a fabricated one.
Implementation is NOT modified by this file.
"""

import unittest

from seraph import (
    ConsequenceMonitor,
    ConsequenceStatus,
    FunctionalEffect,
    ManifoldCompiler,
    ManifoldState,
)
from tests.test_manifold_compiler import manifold_spec, manifold_state, proposal_for


class ConsequenceMonitorTrustBoundaryTests(unittest.TestCase):
    """CertifiedToolGuard and CapabilityRuntime both take an injected
    state_reader: Callable[[], ManifoldState] specifically so the state
    source is a controlled dependency, not a bare caller-supplied value.
    ConsequenceMonitor.observe() has no state_reader at all -- `state` is
    whatever the immediate caller hands it, with nothing to establish that
    value actually came from the real system rather than being constructed
    to satisfy the check.
    """

    def setUp(self):
        self.compiled = ManifoldCompiler.compile(manifold_spec())
        self.source = manifold_state()
        effect = FunctionalEffect("alice", "safety", 0.7, 0.8, True)
        self.proposal = proposal_for(self.source, effect)
        self.certificate = self.compiled.evaluate(self.source, self.proposal)
        self.monitor = ConsequenceMonitor(compiled=self.compiled)

    def test_fabricated_state_completes_a_checkpoint_that_never_happened(self):
        """Nothing was ever executed against the real system: `fabricated`
        below is hand-built to match the certified target digest, not
        observed from any real state transition. observe() cannot tell the
        difference, and reports COMPLETE for a consequence that never
        occurred outside this test.
        """
        ticket = self.monitor.start(self.certificate, checkpoints=1)

        fabricated = ManifoldState(
            state_id="never-actually-executed",
            entities=(
                self.source.entities[0].with_coordinate("safety", 0.8),
                *self.source.entities[1:],
            ),
        )

        observation = self.monitor.observe(ticket, fabricated)

        self.assertNotEqual(
            observation.status,
            ConsequenceStatus.COMPLETE,
            "ConsequenceMonitor.observe() accepted a fabricated ManifoldState "
            "with no independent evidence it was ever the system's real "
            "functional state -- unlike CertifiedToolGuard/CapabilityRuntime, "
            "there is no injected state_reader boundary here at all.",
        )


if __name__ == "__main__":
    unittest.main()
