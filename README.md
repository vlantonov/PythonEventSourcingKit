# PythonEventSourcingKit

> Minimal, self-contained Python library demonstrating the Event Sourcing pattern with a SQLite backend — zero infrastructure required.

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-69%20passed-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)

---

## What it is

Event Sourcing is an architectural pattern in which every change to application state is recorded as an immutable event rather than overwritten in place. The current state of any object is derived by replaying its event history from the beginning (or from a snapshot).

`PythonEventSourcingKit` provides the core building blocks to implement this pattern:

- **`EventStore` ABC** — a backend-agnostic interface for appending and loading events, plus snapshot save/load.
- **`SQLiteEventStore`** — a fully ACID-compliant concrete implementation backed by the standard-library `sqlite3` module. No server, no extra dependencies.
- **`AggregateRoot`** — a base class with version tracking, an `on_<EventType>` dispatch convention, pending-event collection, and snapshot hooks.
- **`Repository`** — wires store and aggregate together; handles rehydration (snapshot + partial replay) and auto-snapshot triggering.
- **`BankAccount` example** — a runnable aggregate demonstrating all four operations (`AccountOpened`, `MoneyDeposited`, `MoneyWithdrawn`, `AccountClosed`) including optimistic-concurrency protection and guard conditions.

---

## Backend choice & trade-off

SQLite was chosen over PostgreSQL, MariaDB, or a plain log file for this portfolio release. The key criteria (from [`docs/requirements/SRS.md`](docs/requirements/SRS.md) §4):

| Criterion | SQLite | PostgreSQL | Plain log file |
|-----------|--------|------------|----------------|
| Zero infrastructure | ✅ | ❌ server required | ✅ |
| Full ACID transactions | ✅ | ✅ | ❌ |
| Optimistic concurrency via SQL | ✅ | ✅ | ❌ fragile |
| Standard library, no install | ✅ | ❌ `psycopg2`/`asyncpg` | ✅ |
| CI/CD friendly (no Docker service) | ✅ | ❌ | ✅ |

**PostgreSQL** is the production-grade choice for a real event store — row-level locking, rich indexing, logical replication. The `EventStore` interface is designed so swapping in a PostgreSQL backend requires no changes to application code, demonstrating the value of the abstraction.

**Plain log file** cannot enforce the optimistic-concurrency check correctly without external locking and provides no ACID guarantees, making it unsuitable for a correct demonstration of the pattern.

**SQLite** provides all required correctness properties with zero friction for any reviewer who clones the repo — no server to start, no Docker Compose file to understand.

> **Documented limitation:** SQLite does not support concurrent writers. For multi-process or web-service use, replace `SQLiteEventStore` with a server-backed implementation of `EventStore`.

---

## Installation

**Editable install with dev dependencies (recommended for development and testing):**

```bash
pip install -e ".[dev]"
```

**Plain install (library only, no test tools):**

```bash
pip install .
```

Requires **Python ≥ 3.11**. Runtime dependencies are stdlib-only (`sqlite3`, `json`, `uuid`, `dataclasses`, `abc`).

---

## Quick start

```python
from decimal import Decimal

from event_sourcing import Repository, SQLiteEventStore
from event_sourcing.examples.bank_account import BankAccount

# Use ":memory:" for a transient store, or a file path like "events.db" for persistence.
store = SQLiteEventStore(":memory:")
repo = Repository(store)

# Create a new account and record some transactions.
account = BankAccount.open_account("Alice", initial_balance=Decimal("100.00"))
account.deposit(Decimal("50.00"))
account.withdraw(Decimal("30.00"))

account_id = account.aggregate_id  # save the id before handing off to the repo

# Persist the pending events to the store.
repo.save(account)

# Rehydrate from the store — reconstructs state by replaying the event log.
reloaded = repo.rehydrate(BankAccount, account_id)

print(reloaded.owner)    # Alice
print(reloaded.balance)  # Decimal('120.00')
```

---

## Architecture overview

The library is structured in three layers. See [`docs/design/DESIGN.md`](docs/design/DESIGN.md) for the full design document including the SQLite schema, rehydration algorithm, snapshot strategy, and concurrency model.

```
event_sourcing/
├── __init__.py          # public re-exports — import everything from here
├── domain.py            # StoredEvent, SnapshotRecord (frozen dataclasses)
├── exceptions.py        # EventSourcingError hierarchy
├── store.py             # EventStore ABC
├── aggregate.py         # AggregateRoot base class
├── repository.py        # Repository — orchestrates store + aggregate I/O
├── sqlite_store.py      # SQLiteEventStore — concrete SQLite backend
├── _serialisation.py    # JSON helpers (private; datetime ↔ ISO-8601)
└── examples/
    └── bank_account.py  # BankAccount — worked example aggregate
```

**Dependency rule:** domain and persistence layers never import from `repository`; `_serialisation` is only imported by `sqlite_store`; `examples` imports only from the public `event_sourcing` package.

### Public API

Everything needed for normal use is importable directly from `event_sourcing`:

```python
from event_sourcing import (
    AggregateRoot,
    EventStore,
    Repository,
    SQLiteEventStore,
    StoredEvent,
    SnapshotRecord,
    EventSourcingError,
    OptimisticConcurrencyError,
    AggregateNotFoundError,
    UnknownEventTypeError,
    InsufficientFundsError,
    AccountClosedError,
)
```

### Event-handler convention

Concrete aggregates register handlers by defining methods named `on_<EventType>`. The `AggregateRoot.apply()` dispatcher resolves the handler via `getattr` — no metaclass, decorator, or registry required.

```python
class BankAccount(AggregateRoot):
    def on_MoneyDeposited(self, payload: dict) -> None:
        self._balance += Decimal(payload["amount"])
```

---

## Running the tests

```bash
# Run the full suite with verbose output
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=event_sourcing
```

The suite contains **69 tests** and achieves **100% line coverage**. No additional configuration is needed beyond `pip install -e ".[dev]"`.

---

## Out of scope

The following are explicitly deferred and not implemented in this release:

- **Projections / Read Models** — query-optimised views derived from the event stream.
- **Sagas / Process Managers** — coordinating multi-aggregate workflows.
- **Message Bus / Event Bus** — publishing events to external subscribers (Kafka, RabbitMQ, etc.).
- **Async I/O** — `asyncio`-compatible store or repository variants.
- **Additional backends** — PostgreSQL, MariaDB, or Redis implementations.
- **Schema migrations** — versioning or migrating stored event payload shapes.

---

## License

[MIT](LICENSE) © 2026 Vladislav Antonov
