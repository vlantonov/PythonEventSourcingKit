from __future__ import annotations

import pytest

from event_sourcing.sqlite_store import SQLiteEventStore


@pytest.fixture
def store() -> SQLiteEventStore:
    """In-memory SQLiteEventStore; isolated per test."""
    return SQLiteEventStore(":memory:")
