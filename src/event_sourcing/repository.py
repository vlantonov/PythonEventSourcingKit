from __future__ import annotations

from datetime import datetime, timezone
from typing import TypeVar

from event_sourcing.aggregate import AggregateRoot
from event_sourcing.domain import SnapshotRecord
from event_sourcing.exceptions import AggregateNotFoundError
from event_sourcing.store import EventStore

AggregateT = TypeVar("AggregateT", bound=AggregateRoot)


class Repository:

    def __init__(
        self,
        store: EventStore,
        snapshot_threshold: int = 50,
    ) -> None:
        """
        snapshot_threshold: auto-save a new snapshot after this many events
        have been replayed since the last snapshot (or since version 0 if none).
        """
        self._store = store
        self._snapshot_threshold = snapshot_threshold

    def rehydrate(
        self,
        aggregate_class: type[AggregateT],
        aggregate_id: str,
    ) -> AggregateT:
        """Load snapshot + events, rehydrate the aggregate.

        Triggers an automatic snapshot if event count since last snapshot
        meets or exceeds snapshot_threshold.
        Raises AggregateNotFoundError if no snapshot and no events exist.
        """
        snapshot = self._store.load_snapshot(aggregate_id)
        after_version = snapshot.version if snapshot is not None else 0
        events = self._store.load(aggregate_id, after_version=after_version)

        if snapshot is None and len(events) == 0:
            raise AggregateNotFoundError(aggregate_id)

        aggregate = aggregate_class.rehydrate(aggregate_id, events, snapshot)

        events_since_snapshot = len(events)
        if events_since_snapshot >= self._snapshot_threshold:
            self._store.save_snapshot(
                SnapshotRecord(
                    aggregate_id=aggregate_id,
                    version=aggregate.version,
                    state=aggregate.snapshot_state(),
                    taken_at=datetime.now(timezone.utc),
                )
            )

        return aggregate

    def save(self, aggregate: AggregateRoot) -> None:
        """Append pending_events to the store and clear them on success.

        expected_version is derived as aggregate.version - len(pending_events).
        Propagates OptimisticConcurrencyError from EventStore.append.
        """
        pending = aggregate.pending_events
        if not pending:
            return
        expected_version = aggregate.version - len(pending)
        self._store.append(aggregate.aggregate_id, pending, expected_version)
        aggregate.clear_pending_events()
