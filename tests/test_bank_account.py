"""Integration tests for BankAccount aggregate (FR-20 – FR-23, FR-24)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from event_sourcing.examples.bank_account import BankAccount
from event_sourcing.exceptions import AccountClosedError, InsufficientFundsError
from event_sourcing.repository import Repository
from event_sourcing.sqlite_store import SQLiteEventStore


@pytest.fixture
def repo(store: SQLiteEventStore) -> Repository:
    return Repository(store, snapshot_threshold=50)


# ── open_account ──────────────────────────────────────────────────────────────

def test_open_account_sets_owner_and_balance() -> None:
    account = BankAccount.open_account("Alice", Decimal(500))
    assert account.owner == "Alice"
    assert account.balance == Decimal(500)
    assert not account.is_closed
    assert account.version == 1
    assert len(account.pending_events) == 1
    assert account.pending_events[0].event_type == "AccountOpened"


def test_open_account_default_balance_is_zero() -> None:
    account = BankAccount.open_account("Bob")
    assert account.balance == Decimal(0)


def test_open_account_negative_initial_balance_raises() -> None:
    with pytest.raises(ValueError):
        BankAccount.open_account("Alice", Decimal(-1))


# ── deposit ───────────────────────────────────────────────────────────────────

def test_deposit_increases_balance() -> None:
    account = BankAccount.open_account("Carol", Decimal(100))
    account.deposit(Decimal(50))
    assert account.balance == Decimal(150)


def test_deposit_zero_raises() -> None:
    account = BankAccount.open_account("Carol", Decimal(100))
    with pytest.raises(ValueError):
        account.deposit(Decimal(0))


def test_deposit_negative_raises() -> None:
    account = BankAccount.open_account("Carol", Decimal(100))
    with pytest.raises(ValueError):
        account.deposit(Decimal(-10))


def test_deposit_on_closed_account_raises() -> None:
    account = BankAccount.open_account("Dan", Decimal(100))
    account.close_account()
    with pytest.raises(AccountClosedError):
        account.deposit(Decimal(10))


# ── withdraw ──────────────────────────────────────────────────────────────────

def test_withdraw_decreases_balance() -> None:
    account = BankAccount.open_account("Eve", Decimal(200))
    account.withdraw(Decimal(80))
    assert account.balance == Decimal(120)


def test_withdraw_exact_balance_succeeds() -> None:
    account = BankAccount.open_account("Eve", Decimal(100))
    account.withdraw(Decimal(100))
    assert account.balance == Decimal(0)


def test_withdraw_overdraft_raises() -> None:
    account = BankAccount.open_account("Eve", Decimal(100))
    with pytest.raises(InsufficientFundsError) as exc_info:
        account.withdraw(Decimal(200))
    assert exc_info.value.aggregate_id == account.aggregate_id


def test_withdraw_zero_raises() -> None:
    account = BankAccount.open_account("Eve", Decimal(100))
    with pytest.raises(ValueError):
        account.withdraw(Decimal(0))


def test_withdraw_negative_raises() -> None:
    account = BankAccount.open_account("Eve", Decimal(100))
    with pytest.raises(ValueError):
        account.withdraw(Decimal(-5))


def test_withdraw_on_closed_account_raises() -> None:
    account = BankAccount.open_account("Frank", Decimal(100))
    account.close_account()
    with pytest.raises(AccountClosedError):
        account.withdraw(Decimal(10))


# ── close_account ─────────────────────────────────────────────────────────────

def test_close_account_sets_is_closed() -> None:
    account = BankAccount.open_account("Grace", Decimal(0))
    account.close_account()
    assert account.is_closed


def test_close_already_closed_raises() -> None:
    account = BankAccount.open_account("Grace", Decimal(0))
    account.close_account()
    with pytest.raises(AccountClosedError):
        account.close_account()


# ── end-to-end persist and reload ─────────────────────────────────────────────

def test_end_to_end_persist_and_reload(
    store: SQLiteEventStore, repo: Repository
) -> None:
    account = BankAccount.open_account("Heidi", Decimal(1000))
    account.deposit(Decimal(200))
    account.withdraw(Decimal(150))
    account.deposit(Decimal(50))
    repo.save(account)

    reloaded = repo.rehydrate(BankAccount, account.aggregate_id)
    assert reloaded.owner == "Heidi"
    assert reloaded.balance == Decimal(1100)
    assert not reloaded.is_closed
    assert reloaded.version == 4
    assert reloaded.pending_events == []


def test_full_event_history(store: SQLiteEventStore, repo: Repository) -> None:
    account = BankAccount.open_account("Ivan", Decimal(0))
    account.deposit(Decimal(100))
    account.withdraw(Decimal(30))
    account.close_account()
    repo.save(account)

    events = store.load(account.aggregate_id)
    assert len(events) == 4
    assert events[0].event_type == "AccountOpened"
    assert events[1].event_type == "MoneyDeposited"
    assert events[2].event_type == "MoneyWithdrawn"
    assert events[3].event_type == "AccountClosed"


def test_snapshot_save_and_reload(store: SQLiteEventStore) -> None:
    repo = Repository(store, snapshot_threshold=3)

    account = BankAccount.open_account("Judy", Decimal(100))
    account.deposit(Decimal(50))
    account.deposit(Decimal(50))
    repo.save(account)

    # First rehydrate: 3 events >= threshold=3 → snapshot created
    loaded1 = repo.rehydrate(BankAccount, account.aggregate_id)
    assert loaded1.balance == Decimal(200)

    snap = store.load_snapshot(account.aggregate_id)
    assert snap is not None
    assert snap.version == 3
    assert snap.state["balance"] == "200"

    # Second rehydrate: uses snapshot, no further replay needed
    loaded2 = repo.rehydrate(BankAccount, account.aggregate_id)
    assert loaded2.balance == Decimal(200)
    assert loaded2.owner == "Judy"
    assert not loaded2.is_closed


def test_snapshot_and_new_events(store: SQLiteEventStore) -> None:
    """Snapshot taken, then more events added — rehydrate applies both."""
    repo = Repository(store, snapshot_threshold=3)

    account = BankAccount.open_account("Karl", Decimal(0))
    account.deposit(Decimal(100))
    account.deposit(Decimal(100))
    repo.save(account)

    # Trigger snapshot creation
    repo.rehydrate(BankAccount, account.aggregate_id)

    # Add more events after snapshot
    account2 = repo.rehydrate(BankAccount, account.aggregate_id)
    account2.withdraw(Decimal(50))
    repo.save(account2)

    final = repo.rehydrate(BankAccount, account.aggregate_id)
    assert final.balance == Decimal(150)


def test_closed_account_round_trip(store: SQLiteEventStore, repo: Repository) -> None:
    account = BankAccount.open_account("Laura", Decimal(500))
    account.close_account()
    repo.save(account)

    reloaded = repo.rehydrate(BankAccount, account.aggregate_id)
    assert reloaded.is_closed
    assert reloaded.owner == "Laura"
