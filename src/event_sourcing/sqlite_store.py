from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Any

from event_sourcing._serialisation import decode, encode
from event_sourcing.domain import SnapshotRecord, StoredEvent
from event_sourcing.exceptions import OptimisticConcurrencyError
from event_sourcing.store import EventStore

_DDL = """
CREATE TABLE IF NOT EXISTS events (
    id            INTEGER  PRIMARY KEY AUTOINCREMENT,
    aggregate_id  TEXT     NOT NULL,
    version       INTEGER  NOT NULL,
    event_type    TEXT     NOT NULL,
    payload       TEXT     NOT NULL,
    occurred_at   TEXT     NOT NULL,
    UNIQUE (aggregate_id, version)
);

CREATE TABLE IF NOT EXISTS snapshots (
    id            INTEGER  PRIMARY KEY AUTOINCREMENT,
    aggregate_id  TEXT     NOT NULL,
    version       INTEGER  NOT NULL,
    state         TEXT     NOT NULL,
    taken_at      TEXT     NOT NULL,
    UNIQUE (aggregate_id, version)
);
"""


class SQLiteEventStore(EventStore):

    def __init__(self, db_path: str | Path) -> None:
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.executescript(_DDL)

    # ── context-manager protocol ─────────────────────────────────────────────

    def __enter__(self) -> SQLiteEventStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._conn.close()

    # ── EventStore interface ─────────────────────────────────────────────────

    def append(
        self,
        aggregate_id: str,
        events: list[StoredEvent],
        expected_version: int,
    ) -> None:
        if not events:
            return
        with self._conn:
            cursor = self._conn.execute(
                "SELECT MAX(version) FROM events WHERE aggregate_id = ?",
                (aggregate_id,),
            )
            raw: Any = cursor.fetchone()[0]
            # NULL from MAX() when no rows exist maps to version 0
            current_version: int = raw if raw is not None else 0
            if current_version != expected_version:
                raise OptimisticConcurrencyError(
                    aggregate_id, expected_version, raw
                )
            try:
                self._conn.executemany(
                    "INSERT INTO events "
                    "(aggregate_id, version, event_type, payload, occurred_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    [
                        (
                            e.aggregate_id,
                            e.version,
                            e.event_type,
                            encode(e.payload),
                            e.occurred_at.isoformat(),
                        )
                        for e in events
                    ],
                )
            except sqlite3.IntegrityError as exc:
                raise OptimisticConcurrencyError(
                    aggregate_id, expected_version, current_version
                ) from exc

    def load(
        self,
        aggregate_id: str,
        after_version: int = 0,
    ) -> list[StoredEvent]:
        cursor = self._conn.execute(
            "SELECT aggregate_id, version, event_type, payload, occurred_at "
            "FROM events "
            "WHERE aggregate_id = ? AND version > ? "
            "ORDER BY version ASC",
            (aggregate_id, after_version),
        )
        return [
            StoredEvent(
                aggregate_id=row[0],
                version=row[1],
                event_type=row[2],
                payload=decode(row[3]),
                occurred_at=datetime.fromisoformat(row[4]),
            )
            for row in cursor.fetchall()
        ]

    def save_snapshot(self, snapshot: SnapshotRecord) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO snapshots (aggregate_id, version, state, taken_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    snapshot.aggregate_id,
                    snapshot.version,
                    encode(snapshot.state),
                    snapshot.taken_at.isoformat(),
                ),
            )

    def load_snapshot(self, aggregate_id: str) -> SnapshotRecord | None:
        cursor = self._conn.execute(
            "SELECT aggregate_id, version, state, taken_at "
            "FROM snapshots "
            "WHERE aggregate_id = ? "
            "ORDER BY version DESC "
            "LIMIT 1",
            (aggregate_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return SnapshotRecord(
            aggregate_id=row[0],
            version=row[1],
            state=decode(row[2]),
            taken_at=datetime.fromisoformat(row[3]),
        )
