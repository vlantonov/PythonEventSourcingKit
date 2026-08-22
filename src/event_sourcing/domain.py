from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class StoredEvent:
    aggregate_id: str
    version: int          # per-aggregate monotonically increasing, starts at 1
    event_type: str       # bare class name, e.g. "AccountOpened"
    payload: dict[str, Any]
    occurred_at: datetime  # UTC


@dataclass(frozen=True)
class SnapshotRecord:
    aggregate_id: str
    version: int          # aggregate version at snapshot time
    state: dict[str, Any]  # full serialisable aggregate state
    taken_at: datetime    # UTC
