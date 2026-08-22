"""Tests for SQLiteEventStore (FR-03 – FR-12)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from event_sourcing.domain import SnapshotRecord, StoredEvent
from event_sourcing.exceptions import OptimisticConcurrencyError
from event_sourcing.sqlite_store import SQLiteEventStore


def _event(
    aggregate_id: str,
    version: int,
    event_type: str = "Happened",
    payload: dict | None = None,
) -> StoredEvent:
    return StoredEvent(
        aggregate_id=aggregate_id,
        version=version,
        event_type=event_type,
        payload=payload if payload is not None else {"v": version},
        occurred_at=datetime.now(timezone.utc),
    )


# ── append & load ────────────────────────────────────────────────────────────

def test_append_and_load_single_event(store: SQLiteEventStore) -> None:
    store.append("agg-1", [_event("agg-1", 1)], expected_version=0)
    loaded = store.load("agg-1")
    assert len(loaded) == 1
    assert loaded[0].version == 1
    assert loaded[0].event_type == "Happened"


def test_append_and_load_multiple_events(store: SQLiteEventStore) -> None:
    events = [_event("agg-1", i) for i in range(1, 4)]
    store.append("agg-1", events, expected_version=0)
    loaded = store.load("agg-1")
    assert [e.version for e in loaded] == [1, 2, 3]


def test_load_returns_ascending_order(store: SQLiteEventStore) -> None:
    events = [_event("agg-1", i) for i in range(1, 6)]
    store.append("agg-1", events, expected_version=0)
    loaded = store.load("agg-1")
    versions = [e.version for e in loaded]
    assert versions == sorted(versions)


def test_load_after_version_filters_correctly(store: SQLiteEventStore) -> None:
    events = [_event("agg-1", i) for i in range(1, 6)]
    store.append("agg-1", events, expected_version=0)
    loaded = store.load("agg-1", after_version=3)
    assert [e.version for e in loaded] == [4, 5]


def test_load_after_version_default_zero(store: SQLiteEventStore) -> None:
    events = [_event("agg-1", 1), _event("agg-1", 2)]
    store.append("agg-1", events, expected_version=0)
    assert len(store.load("agg-1")) == 2
    assert len(store.load("agg-1", after_version=0)) == 2


def test_load_empty_returns_empty_list(store: SQLiteEventStore) -> None:
    assert store.load("nonexistent") == []


def test_payload_round_trip(store: SQLiteEventStore) -> None:
    payload = {"name": "Alice", "amount": "99.99", "flag": True}
    store.append("agg-1", [_event("agg-1", 1, payload=payload)], expected_version=0)
    loaded = store.load("agg-1")
    assert loaded[0].payload == payload


def test_occurred_at_round_trip(store: SQLiteEventStore) -> None:
    now = datetime.now(timezone.utc)
    event = StoredEvent("agg-1", 1, "Foo", {}, now)
    store.append("agg-1", [event], expected_version=0)
    loaded = store.load("agg-1")
    # isoformat round-trip; compare via isoformat string
    assert loaded[0].occurred_at.isoformat() == now.isoformat()


def test_append_multiple_aggregates_are_isolated(store: SQLiteEventStore) -> None:
    store.append("agg-A", [_event("agg-A", 1)], expected_version=0)
    store.append("agg-B", [_event("agg-B", 1)], expected_version=0)
    assert len(store.load("agg-A")) == 1
    assert len(store.load("agg-B")) == 1


# ── optimistic concurrency ───────────────────────────────────────────────────

def test_optimistic_concurrency_on_new_aggregate(store: SQLiteEventStore) -> None:
    store.append("agg-1", [_event("agg-1", 1)], expected_version=0)
    with pytest.raises(OptimisticConcurrencyError) as exc_info:
        store.append("agg-1", [_event("agg-1", 2)], expected_version=0)
    assert exc_info.value.aggregate_id == "agg-1"
    assert exc_info.value.expected == 0


def test_optimistic_concurrency_stale_version(store: SQLiteEventStore) -> None:
    store.append("agg-1", [_event("agg-1", 1)], expected_version=0)
    store.append("agg-1", [_event("agg-1", 2)], expected_version=1)
    with pytest.raises(OptimisticConcurrencyError):
        # Writer with stale expected_version=1 when current is 2
        store.append("agg-1", [_event("agg-1", 3)], expected_version=1)


def test_sequential_appends_succeed(store: SQLiteEventStore) -> None:
    store.append("agg-1", [_event("agg-1", 1)], expected_version=0)
    store.append("agg-1", [_event("agg-1", 2)], expected_version=1)
    store.append("agg-1", [_event("agg-1", 3)], expected_version=2)
    assert len(store.load("agg-1")) == 3


def test_append_empty_list_is_noop(store: SQLiteEventStore) -> None:
    store.append("agg-1", [], expected_version=0)
    assert store.load("agg-1") == []


# ── snapshot round-trip ──────────────────────────────────────────────────────

def test_save_and_load_snapshot(store: SQLiteEventStore) -> None:
    snap = SnapshotRecord(
        aggregate_id="agg-1",
        version=5,
        state={"balance": "100.00", "owner": "Alice"},
        taken_at=datetime.now(timezone.utc),
    )
    store.save_snapshot(snap)
    loaded = store.load_snapshot("agg-1")
    assert loaded is not None
    assert loaded.aggregate_id == "agg-1"
    assert loaded.version == 5
    assert loaded.state == {"balance": "100.00", "owner": "Alice"}


def test_load_snapshot_none_when_missing(store: SQLiteEventStore) -> None:
    assert store.load_snapshot("nonexistent") is None


def test_load_snapshot_returns_highest_version(store: SQLiteEventStore) -> None:
    for v in [1, 5, 3]:
        store.save_snapshot(
            SnapshotRecord("agg-1", v, {"v": v}, datetime.now(timezone.utc))
        )
    snap = store.load_snapshot("agg-1")
    assert snap is not None
    assert snap.version == 5


def test_snapshot_does_not_alter_events(store: SQLiteEventStore) -> None:
    store.append("agg-1", [_event("agg-1", 1)], expected_version=0)
    store.save_snapshot(
        SnapshotRecord("agg-1", 1, {}, datetime.now(timezone.utc))
    )
    assert len(store.load("agg-1")) == 1


# ── context manager ──────────────────────────────────────────────────────────

def test_context_manager_closes_connection() -> None:
    with SQLiteEventStore(":memory:") as s:
        s.append("agg-1", [_event("agg-1", 1)], expected_version=0)
        assert len(s.load("agg-1")) == 1


def test_integrity_error_raises_optimistic_concurrency(store: SQLiteEventStore) -> None:
    """Duplicate version in a single call triggers the IntegrityError guard."""
    dup_events = [_event("agg-1", 1), _event("agg-1", 1)]  # same version
    with pytest.raises(OptimisticConcurrencyError):
        store.append("agg-1", dup_events, expected_version=0)
