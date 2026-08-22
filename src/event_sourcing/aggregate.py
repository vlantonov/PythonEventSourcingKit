from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Self

from event_sourcing.domain import SnapshotRecord, StoredEvent
from event_sourcing.exceptions import UnknownEventTypeError


class AggregateRoot:
    aggregate_id: str
    version: int
    _pending_events: list[StoredEvent]

    def __init__(self, aggregate_id: str) -> None:
        self.aggregate_id = aggregate_id
        self.version = 0
        self._pending_events: list[StoredEvent] = []

    # ── public read API ──────────────────────────────────────────────────────

    @property
    def pending_events(self) -> list[StoredEvent]:
        """Uncommitted events raised since last load or clear."""
        return list(self._pending_events)

    def clear_pending_events(self) -> None:
        """Called by Repository.save() after a successful append."""
        self._pending_events.clear()

    # ── event lifecycle ──────────────────────────────────────────────────────

    def apply(self, event: StoredEvent) -> None:
        """Dispatch to on_<event.event_type>(payload) and update version.

        Used internally by record() and rehydrate().
        Raises UnknownEventTypeError if no handler method is found.
        """
        handler_name = f"on_{event.event_type}"
        handler = getattr(self, handler_name, None)
        if handler is None:
            raise UnknownEventTypeError(event.event_type)
        handler(event.payload)
        self.version = event.version

    def record(self, event_type: str, payload: dict[str, Any]) -> None:
        """Create a StoredEvent, apply it, and add it to pending_events.

        Domain methods on concrete subclasses call this to raise events.
        """
        next_version = self.version + 1
        event = StoredEvent(
            aggregate_id=self.aggregate_id,
            version=next_version,
            event_type=event_type,
            payload=payload,
            occurred_at=datetime.now(timezone.utc),
        )
        self.apply(event)  # validates handler exists; updates self.version
        self._pending_events.append(event)

    # ── snapshot hooks ───────────────────────────────────────────────────────

    def snapshot_state(self) -> dict[str, Any]:
        """Return a serialisable dict of the full aggregate state.

        Concrete subclasses must override this to participate in snapshots.
        """
        return {}

    def _restore_from_snapshot(self, state: dict[str, Any]) -> None:
        """Apply snapshot state to self; called only by rehydrate().

        Concrete subclasses must override this to restore their fields.
        """

    # ── rehydration ──────────────────────────────────────────────────────────

    @classmethod
    def rehydrate(
        cls,
        aggregate_id: str,
        events: list[StoredEvent],
        snapshot: SnapshotRecord | None = None,
    ) -> Self:
        """Reconstruct an aggregate instance from a snapshot and/or events.

        Does NOT touch the EventStore. The Repository is responsible for
        fetching snapshot and events before calling this.
        Returned instance always has empty pending_events.
        """
        instance = cls(aggregate_id)
        if snapshot is not None:
            instance._restore_from_snapshot(snapshot.state)
            instance.version = snapshot.version
        for event in events:
            instance.apply(event)
        instance.clear_pending_events()
        return instance
