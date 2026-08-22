"""Private JSON helpers for SQLiteEventStore. Not part of the public API."""
from __future__ import annotations

import json
from typing import Any


def encode(data: dict[str, Any]) -> str:
    return json.dumps(data)


def decode(text: str) -> dict[str, Any]:
    result: dict[str, Any] = json.loads(text)
    return result
