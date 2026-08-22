"""Tests for StoredEvent and SnapshotRecord dataclasses (domain.py)."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from event_sourcing.domain import SnapshotRecord, StoredEvent

_NOW = datetime.now(UTC)


def test_stored_event_fields() -> None:
    event = StoredEvent(
        aggregate_id="agg-1",
        version=1,
        event_type="SomethingHappened",
        payload={"key": "value"},
        occurred_at=_NOW,
    )
    assert event.aggregate_id == "agg-1"
    assert event.version == 1
    assert event.event_type == "SomethingHappened"
    assert event.payload == {"key": "value"}
    assert event.occurred_at is _NOW


def test_stored_event_is_frozen() -> None:
    event = StoredEvent(
        aggregate_id="agg-1",
        version=1,
        event_type="Foo",
        payload={},
        occurred_at=_NOW,
    )
    with pytest.raises((AttributeError, TypeError)):
        event.version = 99  # type: ignore[misc]


def test_snapshot_record_fields() -> None:
    snap = SnapshotRecord(
        aggregate_id="agg-1",
        version=5,
        state={"balance": "100.00"},
        taken_at=_NOW,
    )
    assert snap.aggregate_id == "agg-1"
    assert snap.version == 5
    assert snap.state == {"balance": "100.00"}
    assert snap.taken_at is _NOW


def test_snapshot_record_is_frozen() -> None:
    snap = SnapshotRecord(
        aggregate_id="agg-1",
        version=5,
        state={},
        taken_at=_NOW,
    )
    with pytest.raises((AttributeError, TypeError)):
        snap.version = 99  # type: ignore[misc]


def test_stored_event_equality() -> None:
    e1 = StoredEvent("a", 1, "E", {"x": 1}, _NOW)
    e2 = StoredEvent("a", 1, "E", {"x": 1}, _NOW)
    assert e1 == e2


def test_snapshot_record_equality() -> None:
    s1 = SnapshotRecord("a", 1, {"k": "v"}, _NOW)
    s2 = SnapshotRecord("a", 1, {"k": "v"}, _NOW)
    assert s1 == s2
