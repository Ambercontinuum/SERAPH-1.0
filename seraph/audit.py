"""Tamper-evident, deterministic audit chain for governance events."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from threading import Lock
from typing import Any

from .manifold import canonical_json, content_digest


GENESIS_HASH = "0" * 64


class AuditChainError(ValueError):
    """An audit chain is malformed, discontinuous, or has been altered."""


@dataclass(frozen=True)
class AuditEvent:
    sequence: int
    event_type: str
    payload_json: str
    payload_digest: str
    previous_hash: str
    event_hash: str


def _event_hash(
    sequence: int,
    event_type: str,
    payload_digest: str,
    previous_hash: str,
) -> str:
    return content_digest(
        {
            "sequence": sequence,
            "event_type": event_type,
            "payload_digest": payload_digest,
            "previous_hash": previous_hash,
        }
    )


@dataclass
class HashChainJournal:
    """Append-only audit events with optional fsynced JSONL persistence.

    The chain is tamper-evident, not tamper-proof.  Protecting or externally
    anchoring the journal file remains a deployment responsibility.
    """

    path: Path | None = None

    def __post_init__(self) -> None:
        if self.path is not None:
            self.path = Path(self.path)
        self._events: list[AuditEvent] = []
        self._lock = Lock()
        if self.path is not None and self.path.exists():
            self._events = self._read_file()
            self.verify()

    @property
    def events(self) -> tuple[AuditEvent, ...]:
        with self._lock:
            return tuple(self._events)

    @property
    def head(self) -> str:
        with self._lock:
            return self._events[-1].event_hash if self._events else GENESIS_HASH

    def append(self, event_type: str, payload: Any) -> AuditEvent:
        if not isinstance(event_type, str) or not event_type.strip():
            raise AuditChainError("event_type must be a non-empty string")
        try:
            payload_json = canonical_json(payload)
        except (TypeError, ValueError) as exc:
            raise AuditChainError("audit payload is not canonical") from exc

        with self._lock:
            # Each canonical event commits to its payload and predecessor;
            # optional persistence is flushed
            # and fsynced before it becomes the in-memory head.
            sequence = len(self._events)
            previous_hash = (
                self._events[-1].event_hash
                if self._events
                else GENESIS_HASH
            )
            payload_digest = content_digest(json.loads(payload_json))
            event = AuditEvent(
                sequence=sequence,
                event_type=event_type,
                payload_json=payload_json,
                payload_digest=payload_digest,
                previous_hash=previous_hash,
                event_hash=_event_hash(
                    sequence,
                    event_type,
                    payload_digest,
                    previous_hash,
                ),
            )
            if self.path is not None:
                self._persist(event)
            self._events.append(event)
            return event

    def verify(self) -> bool:
        with self._lock:
            previous_hash = GENESIS_HASH
            for sequence, event in enumerate(self._events):
                if event.sequence != sequence:
                    raise AuditChainError("audit sequence discontinuity")
                if event.previous_hash != previous_hash:
                    raise AuditChainError("audit previous-hash mismatch")
                try:
                    payload = json.loads(event.payload_json)
                except json.JSONDecodeError as exc:
                    raise AuditChainError("audit payload is invalid JSON") from exc
                if canonical_json(payload) != event.payload_json:
                    raise AuditChainError("audit payload is not canonical")
                payload_digest = content_digest(payload)
                if event.payload_digest != payload_digest:
                    raise AuditChainError("audit payload digest mismatch")
                expected_hash = _event_hash(
                    event.sequence,
                    event.event_type,
                    event.payload_digest,
                    event.previous_hash,
                )
                if event.event_hash != expected_hash:
                    raise AuditChainError("audit event hash mismatch")
                previous_hash = event.event_hash
            return True

    def _persist(self, event: AuditEvent) -> None:
        assert self.path is not None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            asdict(event),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(line + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _read_file(self) -> list[AuditEvent]:
        assert self.path is not None
        events: list[AuditEvent] = []
        try:
            with self.path.open("r", encoding="utf-8") as stream:
                for line_number, line in enumerate(stream, start=1):
                    if not line.strip():
                        raise AuditChainError(
                            f"empty audit line:{line_number}"
                        )
                    raw = json.loads(line)
                    if set(raw) != {
                        "sequence",
                        "event_type",
                        "payload_json",
                        "payload_digest",
                        "previous_hash",
                        "event_hash",
                    }:
                        raise AuditChainError(
                            f"invalid audit fields:{line_number}"
                        )
                    events.append(AuditEvent(**raw))
        except (json.JSONDecodeError, TypeError) as exc:
            raise AuditChainError("audit journal is malformed") from exc
        return events
