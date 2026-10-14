"""Independent authenticated receipts for tamper-evident journal heads."""

from __future__ import annotations

from dataclasses import dataclass
import hmac
from hashlib import sha256

from .audit import HashChainJournal
from .manifold import canonical_json, content_digest


class AuditAnchorError(ValueError):
    """An anchor request or receipt chain is invalid."""


@dataclass(frozen=True)
class AnchorReceipt:
    witness_id: str
    journal_head: str
    journal_sequence: int
    previous_receipt_digest: str
    mac: str


def _receipt_payload(
    witness_id: str,
    journal_head: str,
    journal_sequence: int,
    previous_receipt_digest: str,
) -> dict[str, object]:
    return {
        "witness_id": witness_id,
        "journal_head": journal_head,
        "journal_sequence": journal_sequence,
        "previous_receipt_digest": previous_receipt_digest,
    }


@dataclass
class HMACAnchorWitness:
    """Stateful external witness using a secret not held with the journal.

    HMAC provides symmetric authentication, not a public digital signature.
    A production witness should keep this object and its key in a separate
    trust domain or replace it with a remote/asymmetric implementation.
    """

    witness_id: str
    secret: bytes

    def __post_init__(self) -> None:
        if (
            not isinstance(self.witness_id, str)
            or not self.witness_id.strip()
        ):
            raise AuditAnchorError("witness_id must be non-empty")
        if not isinstance(self.secret, bytes) or len(self.secret) < 32:
            raise AuditAnchorError("anchor secret must contain at least 32 bytes")
        self._last_sequence = -1
        self._last_journal_head = ""
        self._last_receipt_digest = ""

    def attest(self, journal: HashChainJournal) -> AnchorReceipt:
        journal.verify()
        events = journal.events
        if not events:
            raise AuditAnchorError("cannot anchor an empty journal")
        sequence = events[-1].sequence
        if sequence <= self._last_sequence:
            raise AuditAnchorError("journal sequence did not advance")
        if (
            self._last_sequence >= 0
            and (
                len(events) <= self._last_sequence
                or events[self._last_sequence].event_hash
                != self._last_journal_head
            )
        ):
            raise AuditAnchorError(
                "journal does not extend the previously anchored history"
            )

        # The independent witness authenticates both the
        # advancing head and continuity with its previously witnessed head.
        payload = _receipt_payload(
            self.witness_id,
            journal.head,
            sequence,
            self._last_receipt_digest,
        )
        mac = hmac.new(
            self.secret,
            canonical_json(payload).encode("utf-8"),
            sha256,
        ).hexdigest()
        receipt = AnchorReceipt(
            witness_id=self.witness_id,
            journal_head=journal.head,
            journal_sequence=sequence,
            previous_receipt_digest=self._last_receipt_digest,
            mac=mac,
        )
        self._last_sequence = sequence
        self._last_journal_head = journal.head
        self._last_receipt_digest = content_digest(receipt)
        return receipt

    def verify(self, receipt: AnchorReceipt) -> bool:
        if receipt.witness_id != self.witness_id:
            return False
        payload = _receipt_payload(
            receipt.witness_id,
            receipt.journal_head,
            receipt.journal_sequence,
            receipt.previous_receipt_digest,
        )
        expected = hmac.new(
            self.secret,
            canonical_json(payload).encode("utf-8"),
            sha256,
        ).hexdigest()
        return hmac.compare_digest(receipt.mac, expected)

    def verify_journal(
        self,
        receipt: AnchorReceipt,
        journal: HashChainJournal,
    ) -> bool:
        events = journal.events
        return (
            bool(events)
            and self.verify(receipt)
            and receipt.journal_sequence == events[-1].sequence
            and receipt.journal_head == journal.head
            and journal.verify()
        )

    def verify_chain(
        self,
        receipts: tuple[AnchorReceipt, ...],
    ) -> bool:
        previous_digest = ""
        previous_sequence = -1
        for receipt in receipts:
            if (
                not self.verify(receipt)
                or receipt.previous_receipt_digest != previous_digest
                or receipt.journal_sequence <= previous_sequence
            ):
                return False
            previous_digest = content_digest(receipt)
            previous_sequence = receipt.journal_sequence
        return bool(receipts)
