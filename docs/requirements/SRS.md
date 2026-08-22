# Software Requirements Specification

**Project:** PythonEventSourcingKit  
**Version:** 0.1.0-draft  
**Date:** 2026-08-23  
**Status:** Draft — awaiting System Architect review

---

## Table of Contents

1. [Purpose & Scope](#1-purpose--scope)
2. [Functional Requirements](#2-functional-requirements)
3. [Non-Functional Requirements](#3-non-functional-requirements)
4. [Backend Choice & Trade-off](#4-backend-choice--trade-off)
5. [Out of Scope](#5-out-of-scope)
6. [Glossary](#6-glossary)
7. [Open Questions](#7-open-questions)
8. [Acceptance Criteria Summary](#8-acceptance-criteria-summary)

---

## 1. Purpose & Scope

### 1.1 Purpose

`PythonEventSourcingKit` is a minimal, reusable Python library that provides the core building blocks needed to implement the Event Sourcing pattern in an application. It is intended as a portfolio demonstration of the pattern's key mechanics: durable event storage, aggregate rehydration from an event log, and snapshot-based optimisation.

### 1.2 In Scope

- A backend-agnostic `EventStore` interface together with one concrete SQLite implementation.
- An `AggregateRoot` base class that supports event application and version tracking.
- A rehydration algorithm that reconstructs aggregate state by replaying stored events.
- A snapshot mechanism that persists and restores intermediate aggregate state to avoid full replays.
- A `BankAccount` worked example aggregate that exercises all of the above.
- An automated `pytest` test suite that validates every requirement.
- Semver-tagged commits at the completion of each implementation stage.

### 1.3 Not In Scope

See [Section 5](#5-out-of-scope).

---

## 2. Functional Requirements

### 2.1 Event Store Interface

**FR-01** The library shall expose an `EventStore` abstract base class (or `Protocol`) that declares the following operations without coupling to any concrete backend:

| Operation | Description |
|-----------|-------------|
| `append(aggregate_id, events, expected_version)` | Persist one or more events for an aggregate. |
| `load(aggregate_id, after_version=0)` | Retrieve all stored events for an aggregate, optionally starting after a given version number. |
| `save_snapshot(snapshot)` | Persist a snapshot of an aggregate at a specific version. |
| `load_snapshot(aggregate_id)` | Retrieve the most recent snapshot for an aggregate, or `None` if none exists. |

**FR-02** The `EventStore` interface shall be importable from the library's top-level package so consumers need not reference internal sub-modules.

### 2.2 Append Semantics

**FR-03** The `append` operation shall write events atomically: either all events in a single call are persisted or none are (all-or-nothing transaction).

**FR-04** Each persisted event shall be assigned a monotonically increasing, per-aggregate integer version number starting at `1`. The version number shall be stored alongside the event and returned when events are loaded.

**FR-05** The `append` operation shall accept an `expected_version` integer parameter. If the aggregate's current highest stored version does not equal `expected_version` at the moment of write, the operation shall raise an `OptimisticConcurrencyError` without persisting any events. This is the optimistic-concurrency check.

**FR-06** When `expected_version` is `0`, the `append` operation shall treat the aggregate as new and succeed only if no events have previously been stored for that `aggregate_id`.

### 2.3 Event Retrieval

**FR-07** The `load` operation shall return events in ascending version order.

**FR-08** The `load` operation shall accept an optional `after_version` parameter (default `0`). When supplied, only events whose version number is strictly greater than `after_version` shall be returned. This enables snapshot-aware partial replays.

**FR-09** Events returned by `load` shall carry at minimum: `aggregate_id`, `version`, `event_type` (a string name), `payload` (a serialisable mapping), and `occurred_at` (a UTC timestamp).

### 2.4 Snapshot Save & Load

**FR-10** The `save_snapshot` operation shall persist a snapshot object that contains at minimum: `aggregate_id`, `version` (the aggregate version at snapshot time), `state` (a serialisable mapping of the aggregate's full state), and `taken_at` (a UTC timestamp).

**FR-11** The `load_snapshot` operation shall return the snapshot with the highest version number for the given `aggregate_id`, or `None` if no snapshot exists.

**FR-12** Saving a new snapshot shall not delete or alter any previously stored events.

### 2.5 Aggregate Base Class

**FR-13** The library shall provide an `AggregateRoot` base class. Concrete aggregates shall inherit from it.

**FR-14** `AggregateRoot` shall maintain an integer `version` property, initialised to `0`, that increments by `1` each time an event is applied.

**FR-15** `AggregateRoot` shall maintain a list of uncommitted (in-memory) events raised since the last load or snapshot restore. This list shall be accessible via a `pending_events` property and cleared by an explicit `clear_pending_events()` method.

**FR-16** `AggregateRoot` shall expose an `apply(event)` method that (a) dispatches to a typed handler method on the concrete subclass and (b) increments `version`.

**FR-17** Concrete aggregate subclasses shall register event handlers using a discoverable convention (e.g., a method named `on_<EventClassName>` or a decorator-based registry). The specific convention is a design decision deferred to the System Architect, but it must be consistently enforced across the worked example.

### 2.6 Rehydration Algorithm

**FR-18** The library shall provide a `rehydrate(aggregate_class, aggregate_id, event_store)` function (or equivalent repository method) that reconstructs an aggregate by:

1. Calling `event_store.load_snapshot(aggregate_id)`.
2. If a snapshot exists, restoring the aggregate state from it and setting `version` accordingly.
3. Calling `event_store.load(aggregate_id, after_version=snapshot.version)` (or `after_version=0` if no snapshot).
4. Applying each returned event to the aggregate in order via `apply`.
5. Returning the fully rehydrated aggregate instance.

**FR-19** If no events and no snapshot exist for an `aggregate_id`, `rehydrate` shall raise an `AggregateNotFoundError`.

### 2.7 BankAccount Worked Example

**FR-20** The library shall include a `BankAccount` aggregate in an `examples` package (or module). It shall support the following domain operations, each of which records a corresponding event:

| Domain Operation | Event Recorded |
|-----------------|----------------|
| `open_account(owner, initial_balance)` | `AccountOpened` |
| `deposit(amount)` | `MoneyDeposited` |
| `withdraw(amount)` | `MoneyWithdrawn` |
| `close_account()` | `AccountClosed` |

**FR-21** `BankAccount.withdraw` shall raise a `InsufficientFundsError` if `amount` exceeds the current balance. No event shall be recorded in this case.

**FR-22** `BankAccount.deposit` and `BankAccount.withdraw` shall raise a `AccountClosedError` if the account has already been closed. No event shall be recorded in this case.

**FR-23** The `BankAccount` example shall be exercisable end-to-end: open an account, perform multiple deposits and withdrawals, take a snapshot, close the account, rehydrate from the store (exercising the snapshot path), and assert that the final state matches expectations.

### 2.8 Test Coverage Expectations

**FR-24** The `pytest` test suite shall include tests covering:

- Successful `append` and `load` round-trip for multiple events.
- `OptimisticConcurrencyError` on a stale-version write (FR-05).
- Correct `after_version` filtering in `load` (FR-08).
- Snapshot save and load round-trip (FR-10, FR-11).
- Rehydration without a snapshot (full replay).
- Rehydration with a snapshot (partial replay from snapshot version).
- `AggregateNotFoundError` on missing aggregate (FR-19).
- All `BankAccount` domain operations including guard conditions (FR-21, FR-22).
- The full BankAccount end-to-end scenario (FR-23).

**FR-25** Each implementation stage shall be committed with a semver tag (`v0.1.0`, `v0.2.0`, etc.) before the next stage begins. The commit message shall indicate which requirements the tag satisfies.

---

## 3. Non-Functional Requirements

**NFR-01 Python Version.** The library shall support Python ≥ 3.11. No compatibility shims for older versions are required.

**NFR-02 Dependencies.** Runtime dependencies shall be pure-Python and minimal. Heavy ORMs (SQLAlchemy, Django ORM, Tortoise ORM) are prohibited. The SQLite backend shall use the standard-library `sqlite3` module only. Test dependencies (`pytest`, `pytest-cov`) are permitted as dev-only extras.

**NFR-03 Type Hints.** All public APIs (function signatures, class attributes, return types) shall include PEP 484 type annotations. The codebase shall pass `mypy --strict` or equivalent without errors on the public package.

**NFR-04 Project Packaging.** The library shall be packaged with a `pyproject.toml` (PEP 517/518). No legacy `setup.py` is required.

**NFR-05 Test Runner.** All automated tests shall be runnable with `pytest` from the repository root with no additional configuration arguments.

**NFR-06 Serialisation.** Event payloads and snapshot state shall be serialised to JSON before storage. The serialisation layer shall handle standard Python primitives and `datetime` objects (ISO-8601 strings). Custom serialisation hooks are out of scope for this version.

**NFR-07 Thread Safety.** The SQLite backend is not required to be safe for concurrent access from multiple threads or processes. Single-writer use is the only supported scenario for this portfolio release.

**NFR-08 Error Messages.** All library-defined exceptions shall include a human-readable message that identifies the `aggregate_id` and, where applicable, the conflicting version numbers.

---

## 4. Backend Choice & Trade-off

### Decision: SQLite via the standard-library `sqlite3` module

#### Why SQLite wins for this portfolio scope

| Criterion | SQLite | PostgreSQL | MariaDB/MySQL | Plain log file |
|-----------|--------|------------|---------------|----------------|
| Zero infrastructure | Yes — single file, no server | No — server required | No — server required | Yes |
| ACID transactions | Full | Full | Full (InnoDB) | No |
| Optimistic concurrency via SQL | Yes (`SELECT … FOR UPDATE` emulated via version check + unique constraint) | Yes | Yes | Requires file locking |
| Atomic multi-row insert | Yes | Yes | Yes | Fragile |
| Snapshot storage in same DB | Yes | Yes | Yes | Separate file needed |
| Standard library, no install | Yes | No (`psycopg2`/`asyncpg`) | No (`PyMySQL`/`mysqlclient`) | Yes |
| Reviewable by any engineer | Yes — single `.db` file | No | No | Yes but unstructured |
| CI/CD friendly | Yes — no service container needed | Requires Docker/service | Requires Docker/service | Yes |

**PostgreSQL** is the production-grade choice for any real event store because it offers row-level locking, rich indexing, logical replication, and a strong concurrency story. A reader of this portfolio project will understand that the author is aware of these advantages; the decision log shall make this explicit.

**Plain log file** lacks transactions and makes the optimistic-concurrency check impossible to implement correctly without external locking, so it is unsuitable for demonstrating the pattern correctly.

**SQLite** provides all the correctness properties needed (ACID, CHECK constraints, unique indexes for version enforcement) with zero infrastructure cost, making the project immediately runnable by any reviewer who clones the repository. This directly serves the portfolio goal of lowering friction for evaluation.

#### Documented limitation

SQLite does not support multiple concurrent writers. If this library were to be adapted for a multi-process or web-service context, the `EventStore` interface allows swapping in a PostgreSQL backend without changing application code — demonstrating the value of the abstraction layer.

---

## 5. Out of Scope

The following topics are explicitly deferred and shall not be designed for or implemented in this version:

- **Projections / Read Models** — building query-optimised views from the event stream.
- **Sagas / Process Managers** — coordinating multi-aggregate workflows.
- **Message Bus / Event Bus** — publishing events to external subscribers (RabbitMQ, Kafka, etc.).
- **Async I/O** — `asyncio`-compatible variants of the store or repository.
- **Schema migrations** — versioning and migrating the shape of stored event payloads.
- **Multi-tenancy** — namespace isolation between tenants within a single store.
- **Encryption at rest** — encrypting event payloads before storage.
- **PostgreSQL / MariaDB backends** — concrete implementations beyond SQLite.
- **CLI tooling** — no command-line interface for inspecting or replaying events.

---

## 6. Glossary

| Term | Definition |
|------|-----------|
| **Event** | An immutable record of something that has already happened within a domain (past tense: `AccountOpened`, `MoneyDeposited`). An event carries the data that describes the change but does not prescribe how state should be updated. |
| **Aggregate** | A cluster of domain objects treated as a single unit for the purpose of data changes. All mutations to an aggregate are expressed as events. |
| **AggregateRoot** | The single entity within an aggregate that external code holds a reference to. In this library, `AggregateRoot` is also the base class all concrete aggregates inherit from. |
| **Snapshot** | A serialised representation of an aggregate's complete state at a specific version number. Used to avoid replaying the entire event log from version 1 during rehydration. |
| **EventStore** | The durable persistence layer responsible for appending events and retrieving them by `aggregate_id`. Also stores and retrieves snapshots. |
| **Version / Sequence Number** | A per-aggregate monotonically increasing integer assigned to each event at append time. Version `0` means the aggregate does not yet exist. The version after applying `n` events is `n`. |
| **Rehydration** | The process of reconstructing an aggregate's current state by loading its snapshot (if any) and replaying subsequent events from the `EventStore`. |
| **Optimistic Concurrency** | A conflict-detection strategy in which a writer asserts the version it last observed (`expected_version`). If another writer has changed the aggregate in the meantime, the store rejects the write with `OptimisticConcurrencyError` rather than silently overwriting data. |
| **Pending Events** | Events raised by an aggregate during a business operation that have not yet been persisted to the `EventStore`. They are held in memory on the aggregate until the application layer saves them. |

---

## 7. Open Questions

| # | Question | Impact if unresolved |
|---|----------|----------------------|
| OQ-01 | Should the `AggregateRoot` base class use a `on_<ClassName>` naming convention or a decorator-based registry for event handlers? | Affects the design of `apply()` and the BankAccount example; deferred to System Architect. |
| OQ-02 | Should snapshots be triggered automatically (every N events) by the repository, or manually by application code? | Automatic triggers require the repository to know a threshold; manual keeps the library simpler. Deferred to System Architect. |
| OQ-03 | Should `EventStore` be defined as an `ABC` or a `typing.Protocol`? | `Protocol` allows structural subtyping (no explicit inheritance needed); `ABC` enforces inheritance. Either is acceptable; deferred to System Architect. |
| OQ-04 | What is the precise wire format for `payload` in the SQLite schema — a JSON column (`TEXT`) or a `BLOB`? | Affects query debuggability; `TEXT`/JSON is preferred for inspectability but is a design detail. |
| OQ-05 | Is `aggregate_id` always a UUID string, or should the type be `str` to allow other id schemes? | Keeping it `str` is more general; the BankAccount example can use UUIDs internally. |

---

## 8. Acceptance Criteria Summary

The implementation is considered complete for version `1.0.0` when all of the following hold:

1. `pytest` exits with code `0` and all tests listed in FR-24 pass.
2. `mypy --strict` reports no errors on the public package (NFR-03).
3. The repository can be cloned and `pytest` run with no steps beyond `pip install -e .[dev]` (NFR-02, NFR-05).
4. A `BankAccount` end-to-end scenario (FR-23) is present and passing, exercising the snapshot path.
5. Each implementation stage has a corresponding semver commit tag (FR-25).
6. `docs/requirements/SRS.md` (this document) is present and referenced in the project `README`.

---

*Requirements are ready for the System Architect agent to design against.*
