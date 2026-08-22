"""Tests for Repository rehydration algorithm (FR-18, FR-19, FR-24)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from event_sourcing.aggregate import AggregateRoot
from event_sourcing.domain import SnapshotRecord, StoredEvent
from event_sourcing.exceptions import AggregateNotFoundError
from event_sourcing.repository import Repository
from event_sourcing.sqlite_store import SQLiteEventStore


# ── test double ──────────────────────────────────────────────────────────────

class Counter(AggregateRoot):

    def __init__(self, aggregate_id: str) -> None:
        super().__init__(aggregate_id)
        self.count: int = 0

    def tick(self) -> None:
        self.record("Ticked", {})

    def on_Ticked(self, payload: dict[str, Any]) -> None:
        self.count += 1

    def snapshot_state(self) -> dict[str, Any]:
        return {"count": self.count}

    def _restore_from_snapshot(self, state: dict[str, Any]) -> None:
        self.count = state["count"]


@pytest.fixture
def repo(store: SQLiteEventStore) -> Repository:
    return Repository(store, snapshot_threshold=50)


# ── full replay (no snapshot) ─────────────────────────────────────────────────

def test_rehydrate_full_replay(store: SQLiteEventStore, repo: Repository) -> None:
    agg = Counter("agg-1")
    for _ in range(3):
        agg.tick()
    repo.save(agg)

    loaded = repo.rehydrate(Counter, "agg-1")
    assert loaded.count == 3
    assert loaded.version == 3
    assert loaded.pending_events == []


# ── partial replay from snapshot ─────────────────────────────────────────────

def test_rehydrate_with_snapshot(store: SQLiteEventStore, repo: Repository) -> None:
    # Seed events v1–v3, then a snapshot, then events v4–v5
    first_events = [
        StoredEvent("agg-1", i, "Ticked", {}, datetime.now(timezone.utc))
        for i in range(1, 4)
    ]
    store.append("agg-1", first_events, expected_version=0)
    store.save_snapshot(
        SnapshotRecord("agg-1", 3, {"count": 3}, datetime.now(timezone.utc))
    )
    store.append(
        "agg-1",
        [
            StoredEvent("agg-1", 4, "Ticked", {}, datetime.now(timezone.utc)),
            StoredEvent("agg-1", 5, "Ticked", {}, datetime.now(timezone.utc)),
        ],
        expected_version=3,
    )

    loaded = repo.rehydrate(Counter, "agg-1")
    assert loaded.count == 5
    assert loaded.version == 5


def test_rehydrate_from_snapshot_only(
    store: SQLiteEventStore, repo: Repository
) -> None:
    store.save_snapshot(
        SnapshotRecord("agg-1", 10, {"count": 10}, datetime.now(timezone.utc))
    )
    loaded = repo.rehydrate(Counter, "agg-1")
    assert loaded.count == 10
    assert loaded.version == 10


# ── AggregateNotFoundError ────────────────────────────────────────────────────

def test_rehydrate_missing_aggregate_raises(repo: Repository) -> None:
    with pytest.raises(AggregateNotFoundError) as exc_info:
        repo.rehydrate(Counter, "ghost-id")
    assert "ghost-id" in str(exc_info.value)


# ── auto-snapshot trigger ─────────────────────────────────────────────────────

def test_auto_snapshot_triggered_at_threshold(store: SQLiteEventStore) -> None:
    repo = Repository(store, snapshot_threshold=3)
    agg = Counter("agg-1")
    for _ in range(3):
        agg.tick()
    repo.save(agg)

    # First rehydration: 3 events >= threshold=3, snapshot should be created
    repo.rehydrate(Counter, "agg-1")

    snap = store.load_snapshot("agg-1")
    assert snap is not None
    assert snap.version == 3
    assert snap.state == {"count": 3}


def test_auto_snapshot_not_triggered_below_threshold(store: SQLiteEventStore) -> None:
    repo = Repository(store, snapshot_threshold=10)
    agg = Counter("agg-1")
    for _ in range(5):
        agg.tick()
    repo.save(agg)

    repo.rehydrate(Counter, "agg-1")

    assert store.load_snapshot("agg-1") is None


# ── save() ───────────────────────────────────────────────────────────────────

def test_save_appends_events_and_clears_pending(
    store: SQLiteEventStore, repo: Repository
) -> None:
    agg = Counter("agg-1")
    agg.tick()
    agg.tick()
    repo.save(agg)

    assert agg.pending_events == []
    assert len(store.load("agg-1")) == 2


def test_save_noop_when_no_pending(store: SQLiteEventStore, repo: Repository) -> None:
    agg = Counter("agg-1")
    # save with zero pending events — should not raise
    repo.save(agg)
    assert store.load("agg-1") == []


def test_save_then_rehydrate_full_cycle(
    store: SQLiteEventStore, repo: Repository
) -> None:
    agg = Counter("agg-1")
    for _ in range(4):
        agg.tick()
    repo.save(agg)

    reloaded = repo.rehydrate(Counter, "agg-1")
    assert reloaded.count == 4
    assert reloaded.aggregate_id == "agg-1"
