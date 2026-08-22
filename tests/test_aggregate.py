"""Tests for AggregateRoot base class mechanics (FR-13 – FR-17)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from event_sourcing.aggregate import AggregateRoot
from event_sourcing.domain import SnapshotRecord, StoredEvent
from event_sourcing.exceptions import UnknownEventTypeError


# ── test double ──────────────────────────────────────────────────────────────

class SimpleAggregate(AggregateRoot):

    def __init__(self, aggregate_id: str) -> None:
        super().__init__(aggregate_id)
        self.counter: int = 0
        self.last_value: int = 0

    def increment(self, amount: int = 1) -> None:
        self.record("Incremented", {"amount": amount})

    def on_Incremented(self, payload: dict[str, Any]) -> None:
        self.counter += payload["amount"]
        self.last_value = payload["amount"]

    def snapshot_state(self) -> dict[str, Any]:
        return {"counter": self.counter}

    def _restore_from_snapshot(self, state: dict[str, Any]) -> None:
        self.counter = state["counter"]


def _stored(
    aggregate_id: str, version: int, event_type: str, payload: dict[str, Any]
) -> StoredEvent:
    return StoredEvent(
        aggregate_id, version, event_type, payload, datetime.now(timezone.utc)
    )


# ── record() tests ───────────────────────────────────────────────────────────

def test_record_increments_version_by_one() -> None:
    agg = SimpleAggregate("agg-1")
    assert agg.version == 0
    agg.increment()
    assert agg.version == 1
    agg.increment()
    assert agg.version == 2


def test_record_populates_pending_events() -> None:
    agg = SimpleAggregate("agg-1")
    agg.increment(10)
    assert len(agg.pending_events) == 1
    event = agg.pending_events[0]
    assert event.event_type == "Incremented"
    assert event.payload == {"amount": 10}
    assert event.aggregate_id == "agg-1"
    assert event.version == 1


def test_record_multiple_events_all_in_pending() -> None:
    agg = SimpleAggregate("agg-1")
    for i in range(1, 4):
        agg.increment(i)
    pending = agg.pending_events
    assert len(pending) == 3
    assert [e.version for e in pending] == [1, 2, 3]


def test_pending_events_returns_copy() -> None:
    agg = SimpleAggregate("agg-1")
    agg.increment()
    snapshot = agg.pending_events
    snapshot.clear()
    assert len(agg.pending_events) == 1  # original unaffected


# ── dispatch / apply() tests ─────────────────────────────────────────────────

def test_dispatch_calls_correct_handler() -> None:
    agg = SimpleAggregate("agg-1")
    agg.increment(5)
    assert agg.counter == 5


def test_unknown_event_type_raises_error() -> None:
    agg = SimpleAggregate("agg-1")
    with pytest.raises(UnknownEventTypeError) as exc_info:
        agg.record("NoHandlerForThis", {})
    assert "NoHandlerForThis" in str(exc_info.value)


def test_unknown_event_type_does_not_add_to_pending() -> None:
    agg = SimpleAggregate("agg-1")
    with pytest.raises(UnknownEventTypeError):
        agg.record("Ghost", {})
    assert agg.pending_events == []
    assert agg.version == 0


def test_version_unchanged_after_unknown_event() -> None:
    agg = SimpleAggregate("agg-1")
    agg.increment()
    with pytest.raises(UnknownEventTypeError):
        agg.record("Ghost", {})
    assert agg.version == 1


# ── clear_pending_events() tests ─────────────────────────────────────────────

def test_clear_pending_events() -> None:
    agg = SimpleAggregate("agg-1")
    agg.increment()
    agg.increment()
    agg.clear_pending_events()
    assert agg.pending_events == []
    assert agg.version == 2  # version is NOT reset


# ── rehydrate() tests ─────────────────────────────────────────────────────────

def test_rehydrate_from_events_only() -> None:
    events = [
        _stored("agg-1", 1, "Incremented", {"amount": 10}),
        _stored("agg-1", 2, "Incremented", {"amount": 20}),
    ]
    agg = SimpleAggregate.rehydrate("agg-1", events)
    assert agg.version == 2
    assert agg.counter == 30
    assert agg.pending_events == []


def test_rehydrate_from_snapshot_only() -> None:
    snapshot = SnapshotRecord("agg-1", 7, {"counter": 70}, datetime.now(timezone.utc))
    agg = SimpleAggregate.rehydrate("agg-1", [], snapshot)
    assert agg.version == 7
    assert agg.counter == 70
    assert agg.pending_events == []


def test_rehydrate_from_snapshot_and_events() -> None:
    snapshot = SnapshotRecord("agg-1", 3, {"counter": 30}, datetime.now(timezone.utc))
    events = [
        _stored("agg-1", 4, "Incremented", {"amount": 5}),
        _stored("agg-1", 5, "Incremented", {"amount": 5}),
    ]
    agg = SimpleAggregate.rehydrate("agg-1", events, snapshot)
    assert agg.version == 5
    assert agg.counter == 40
    assert agg.pending_events == []


def test_rehydrate_returns_correct_subclass() -> None:
    agg = SimpleAggregate.rehydrate("agg-1", [])
    assert isinstance(agg, SimpleAggregate)


def test_rehydrate_sets_aggregate_id() -> None:
    agg = SimpleAggregate.rehydrate("my-id", [])
    assert agg.aggregate_id == "my-id"


# ── base-class fallback coverage ─────────────────────────────────────────────

def test_base_snapshot_state_returns_empty_dict() -> None:
    """AggregateRoot.snapshot_state base impl returns {}; not overridden here."""

    class NoSnapshotAggregate(AggregateRoot):
        def on_Happened(self, payload: dict[str, Any]) -> None:
            pass

    agg = NoSnapshotAggregate("agg-x")
    assert agg.snapshot_state() == {}
