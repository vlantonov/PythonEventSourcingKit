from __future__ import annotations

from abc import ABC, abstractmethod

from event_sourcing.domain import SnapshotRecord, StoredEvent


class EventStore(ABC):

    @abstractmethod
    def append(
        self,
        aggregate_id: str,
        events: list[StoredEvent],
        expected_version: int,
    ) -> None:
        """Atomically persist events.

        Raises OptimisticConcurrencyError if the aggregate's current
        highest stored version != expected_version.
        When expected_version == 0 the aggregate must not yet exist.
        """

    @abstractmethod
    def load(
        self,
        aggregate_id: str,
        after_version: int = 0,
    ) -> list[StoredEvent]:
        """Return events in ascending version order, version > after_version."""

    @abstractmethod
    def save_snapshot(self, snapshot: SnapshotRecord) -> None:
        """Persist a snapshot; must not alter existing events."""

    @abstractmethod
    def load_snapshot(self, aggregate_id: str) -> SnapshotRecord | None:
        """Return the highest-version snapshot, or None."""
