"""Explicit checkpoint monitoring for delayed postcondition divergence."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from secrets import token_urlsafe
from threading import Lock
from typing import Callable

from .audit import HashChainJournal
from .manifold import (
    CompiledManifold,
    InvariantCertificate,
    ManifoldState,
    RealizationReport,
    content_digest,
)


class ConsequenceMonitorError(ValueError):
    """A monitor ticket is invalid, consumed, or not applicable."""


class ConsequenceStatus(Enum):
    ACTIVE = "active"
    COMPLETE = "complete"
    DIVERGED = "diverged"
    MISSED = "missed"


@dataclass(frozen=True)
class ConsequenceTicket:
    ticket_id: str
    certificate_digest: str
    expected_state_digest: str
    total_checkpoints: int


@dataclass(frozen=True)
class ConsequenceObservation:
    status: ConsequenceStatus
    remaining_checkpoints: int
    report: RealizationReport | None
    audit_head: str


@dataclass(frozen=True)
class _MonitorSession:
    ticket: ConsequenceTicket
    certificate: InvariantCertificate
    remaining_checkpoints: int


@dataclass
class ConsequenceMonitor:
    """Verify a certified target across domain-scheduled checkpoints."""

    compiled: CompiledManifold
    state_reader: Callable[[], ManifoldState] | None = None
    journal: HashChainJournal = field(default_factory=HashChainJournal)
    on_failure: Callable[[ConsequenceObservation], None] | None = None
    _sessions: dict[str, _MonitorSession] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def start(
        self,
        certificate: InvariantCertificate,
        *,
        checkpoints: int,
    ) -> ConsequenceTicket:
        if (
            not certificate.proven
            or certificate.manifold_digest != self.compiled.digest
            or certificate.target_state_digest is None
        ):
            raise ConsequenceMonitorError(
                "monitor requires an applicable proven certificate"
            )
        if (
            not isinstance(checkpoints, int)
            or isinstance(checkpoints, bool)
            or checkpoints <= 0
        ):
            raise ConsequenceMonitorError("checkpoints must be positive")

        ticket = ConsequenceTicket(
            ticket_id=token_urlsafe(32),
            certificate_digest=content_digest(certificate),
            expected_state_digest=certificate.target_state_digest,
            total_checkpoints=checkpoints,
        )
        session = _MonitorSession(
            ticket=ticket,
            certificate=certificate,
            remaining_checkpoints=checkpoints,
        )
        with self._lock:
            self.journal.append(
                "consequence.monitor_started",
                {
                    "ticket_digest": content_digest(ticket),
                    "certificate_digest": ticket.certificate_digest,
                    "expected_state_digest": ticket.expected_state_digest,
                    "checkpoints": checkpoints,
                },
            )
            self._sessions[ticket.ticket_id] = session
        return ticket

    def observe(
        self,
        ticket: ConsequenceTicket,
        state: ManifoldState | None = None,
    ) -> ConsequenceObservation:
        """Read one controlled checkpoint and close on uncertainty/divergence.

        ``state`` remains only as a fail-closed compatibility trap: direct
        caller-supplied observations are never accepted as evidence.
        """

        if state is not None:
            return self.miss(
                ticket,
                reason_code="direct_observation_not_trusted",
            )
        if self.state_reader is None:
            return self.miss(
                ticket,
                reason_code="state_reader_not_configured",
            )
        try:
            observed_state = self.state_reader()
        except Exception as exc:
            return self.miss(
                ticket,
                reason_code=f"state_reader_failed:{type(exc).__name__}",
            )
        if not isinstance(observed_state, ManifoldState):
            return self.miss(
                ticket,
                reason_code="state_reader_returned_invalid_type",
            )

        # Every supplied checkpoint re-verifies the certified target; a
        # mismatch closes the session before later observations can launder it.
        failure: ConsequenceObservation | None = None
        with self._lock:
            session = self._sessions.get(ticket.ticket_id)
            if session is None:
                self._reject(ticket, "unknown_or_consumed_ticket")
            assert session is not None
            if session.ticket != ticket:
                self._sessions.pop(ticket.ticket_id, None)
                self._reject(ticket, "ticket_contents_changed")

            report = self.compiled.verify_realization(
                session.certificate,
                observed_state,
            )
            if not report.matches:
                self._sessions.pop(ticket.ticket_id, None)
                event = self.journal.append(
                    "consequence.delayed_divergence",
                    {
                        "ticket_digest": content_digest(ticket),
                        "expected_state_digest": report.expected_state_digest,
                        "realized_state_digest": report.realized_state_digest,
                    },
                )
                failure = ConsequenceObservation(
                    status=ConsequenceStatus.DIVERGED,
                    remaining_checkpoints=0,
                    report=report,
                    audit_head=event.event_hash,
                )
                observation = failure
            else:
                remaining = session.remaining_checkpoints - 1
                status = (
                    ConsequenceStatus.COMPLETE
                    if remaining == 0
                    else ConsequenceStatus.ACTIVE
                )
                if remaining == 0:
                    self._sessions.pop(ticket.ticket_id, None)
                else:
                    self._sessions[ticket.ticket_id] = _MonitorSession(
                        ticket=session.ticket,
                        certificate=session.certificate,
                        remaining_checkpoints=remaining,
                    )
                event = self.journal.append(
                    "consequence.checkpoint_verified",
                    {
                        "ticket_digest": content_digest(ticket),
                        "realized_state_digest": report.realized_state_digest,
                        "remaining_checkpoints": remaining,
                        "status": status.value,
                    },
                )
                observation = ConsequenceObservation(
                    status=status,
                    remaining_checkpoints=remaining,
                    report=report,
                    audit_head=event.event_hash,
                )

        if failure is not None and self.on_failure is not None:
            self.on_failure(failure)
        return observation

    def miss(
        self,
        ticket: ConsequenceTicket,
        *,
        reason_code: str,
    ) -> ConsequenceObservation:
        """Fail closed when the domain scheduler cannot supply a checkpoint."""

        # Missing observation is uncertainty, not evidence of continued
        # closure.  It therefore follows the same containment callback path.
        if not isinstance(reason_code, str) or not reason_code.strip():
            raise ConsequenceMonitorError("reason_code must be non-empty")
        with self._lock:
            session = self._sessions.pop(ticket.ticket_id, None)
            if session is None or session.ticket != ticket:
                self._reject(ticket, "unknown_changed_or_consumed_ticket")
            event = self.journal.append(
                "consequence.checkpoint_missed",
                {
                    "ticket_digest": content_digest(ticket),
                    "reason_code": reason_code,
                    "remaining_checkpoints": (
                        session.remaining_checkpoints
                    ),
                },
            )
            observation = ConsequenceObservation(
                status=ConsequenceStatus.MISSED,
                remaining_checkpoints=0,
                report=None,
                audit_head=event.event_hash,
            )
        if self.on_failure is not None:
            self.on_failure(observation)
        return observation

    def _reject(self, ticket: ConsequenceTicket, reason: str) -> None:
        self.journal.append(
            "consequence.ticket_rejected",
            {
                "ticket_digest": content_digest(ticket),
                "reason": reason,
            },
        )
        raise ConsequenceMonitorError(reason)
