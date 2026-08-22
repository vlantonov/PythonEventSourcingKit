# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **GitHub Actions CI** (`.github/workflows/ci.yml`) — automated test pipeline triggered on every push and pull request. Runs a matrix across Python 3.11, 3.12, and 3.13; installs dev dependencies, lints with `ruff`, type-checks with `mypy`, and executes the full `pytest` suite with `--cov` coverage reporting. `fail-fast: false` ensures all matrix legs run to completion.

### Fixed

- **Ruff linting violations** — resolved all issues reported by `ruff check` on first CI run: sorted `__all__` alphabetically in `__init__.py` (RUF022); replaced `timezone.utc` with the `UTC` alias throughout source and tests (UP017); replaced `Decimal("0")` string literals with `Decimal(0)` in `bank_account.py` (FURB157); updated `SQLiteEventStore.__enter__` return annotation to `Self` (PYI034).

## [0.1.0] - 2026-08-23

### Added

- **`EventStore` ABC** (`store.py`) — backend-agnostic interface declaring `append`, `load`, `save_snapshot`, and `load_snapshot` with full PEP 484 type annotations.
- **`SQLiteEventStore`** (`sqlite_store.py`) — fully ACID-compliant concrete implementation using the standard-library `sqlite3` module. Enforces per-aggregate monotonically increasing version numbers via a `UNIQUE(aggregate_id, version)` constraint; translates `IntegrityError` to `OptimisticConcurrencyError`.
- **`AggregateRoot`** (`aggregate.py`) — base class with integer `version` tracking, `pending_events` collection, `record()` / `apply()` / `clear_pending_events()` lifecycle methods, `on_<EventType>` handler dispatch convention, and `snapshot_state()` / `_restore_from_snapshot()` hooks.
- **`Repository`** (`repository.py`) — orchestration layer that loads the latest snapshot, fetches subsequent events, calls `AggregateRoot.rehydrate()`, auto-triggers snapshot saves when the post-snapshot event count reaches the configurable `snapshot_threshold` (default 50), and persists pending events via `save()`.
- **`StoredEvent` and `SnapshotRecord`** (`domain.py`) — immutable `frozen=True` dataclasses carrying `aggregate_id`, `version`, `event_type`/`state`, `payload`, and a UTC `occurred_at`/`taken_at` timestamp.
- **Exception hierarchy** (`exceptions.py`) — `EventSourcingError` base; `OptimisticConcurrencyError`, `AggregateNotFoundError`, `UnknownEventTypeError`, `InsufficientFundsError`, `AccountClosedError` concrete exceptions, all with human-readable messages identifying the `aggregate_id` and, where applicable, conflicting version numbers.
- **`BankAccount` worked example** (`examples/bank_account.py`) — concrete aggregate demonstrating `AccountOpened`, `MoneyDeposited`, `MoneyWithdrawn`, and `AccountClosed` events; enforces `InsufficientFundsError` and `AccountClosedError` guard conditions; implements `snapshot_state()` / `_restore_from_snapshot()` for snapshot-aware rehydration.
- **Full `pytest` test suite** — 69 tests across `test_sqlite_store.py`, `test_aggregate.py`, `test_rehydration.py`, `test_domain.py`, and `test_bank_account.py`; 100% line coverage of the `event_sourcing` package.
- **`pyproject.toml` packaging** — PEP 517/518 build configuration via Hatchling; `dev` extras for `pytest` and `pytest-cov`; `src/` layout with `event_sourcing` as the sole wheel package; `requires-python = ">=3.11"`.

### Architecture

- SQLite (stdlib `sqlite3`) was chosen as the sole backend for this release to provide zero-infrastructure, fully ACID, CI/CD-friendly event storage. The `EventStore` interface is designed so a PostgreSQL or other server-backed implementation can be substituted without changing application code. See `docs/requirements/SRS.md` §4 for the full trade-off analysis.

### Documentation

- `docs/requirements/SRS.md` — Software Requirements Specification covering functional requirements (FR-01 – FR-25), non-functional requirements, backend trade-off analysis, out-of-scope items, glossary, and acceptance criteria.
- `docs/design/DESIGN.md` — Architecture and design document covering the three-layer architecture, module responsibilities, key interfaces (with full type-hinted pseudocode), SQLite schema, rehydration algorithm, snapshot strategy, and concurrency model.

[Unreleased]: https://github.com/vladiant/PythonEventSourcingKit/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/vladiant/PythonEventSourcingKit/releases/tag/v0.1.0
