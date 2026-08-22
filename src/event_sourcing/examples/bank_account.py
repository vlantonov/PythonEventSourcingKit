from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from event_sourcing.aggregate import AggregateRoot
from event_sourcing.exceptions import AccountClosedError, InsufficientFundsError


class BankAccount(AggregateRoot):

    def __init__(self, aggregate_id: str) -> None:
        super().__init__(aggregate_id)
        self._owner: str = ""
        self._balance: Decimal = Decimal(0)
        self._is_closed: bool = False

    # ── factory ──────────────────────────────────────────────────────────────

    @classmethod
    def open_account(
        cls,
        owner: str,
        initial_balance: Decimal = Decimal(0),
    ) -> BankAccount:
        """Generate a UUID aggregate_id, record AccountOpened, return instance."""
        if initial_balance < Decimal(0):
            raise ValueError(
                f"initial_balance cannot be negative, got {initial_balance}"
            )
        account = cls(str(uuid.uuid4()))
        account.record(
            "AccountOpened",
            {"owner": owner, "initial_balance": str(initial_balance)},
        )
        return account

    # ── domain operations ────────────────────────────────────────────────────

    def deposit(self, amount: Decimal) -> None:
        """Raises AccountClosedError if closed; raises ValueError if amount <= 0."""
        if self._is_closed:
            raise AccountClosedError(self.aggregate_id)
        if amount <= Decimal(0):
            raise ValueError(f"Deposit amount must be positive, got {amount}")
        self.record("MoneyDeposited", {"amount": str(amount)})

    def withdraw(self, amount: Decimal) -> None:
        """Raises AccountClosedError if closed; raises ValueError if amount <= 0;
        raises InsufficientFundsError if amount > balance.
        """
        if self._is_closed:
            raise AccountClosedError(self.aggregate_id)
        if amount <= Decimal(0):
            raise ValueError(f"Withdrawal amount must be positive, got {amount}")
        if amount > self._balance:
            raise InsufficientFundsError(self.aggregate_id, self._balance, amount)
        self.record("MoneyWithdrawn", {"amount": str(amount)})

    def close_account(self) -> None:
        """Raises AccountClosedError if already closed; records AccountClosed."""
        if self._is_closed:
            raise AccountClosedError(self.aggregate_id)
        self.record("AccountClosed", {})

    # ── event handlers (on_<EventType> convention) ───────────────────────────

    def on_AccountOpened(self, payload: dict[str, Any]) -> None:
        self._owner = payload["owner"]
        self._balance = Decimal(payload["initial_balance"])
        self._is_closed = False

    def on_MoneyDeposited(self, payload: dict[str, Any]) -> None:
        self._balance += Decimal(payload["amount"])

    def on_MoneyWithdrawn(self, payload: dict[str, Any]) -> None:
        self._balance -= Decimal(payload["amount"])

    def on_AccountClosed(self, payload: dict[str, Any]) -> None:
        self._is_closed = True

    # ── snapshot support ─────────────────────────────────────────────────────

    def snapshot_state(self) -> dict[str, Any]:
        return {
            "owner": self._owner,
            "balance": str(self._balance),
            "is_closed": self._is_closed,
        }

    def _restore_from_snapshot(self, state: dict[str, Any]) -> None:
        self._owner = state["owner"]
        self._balance = Decimal(state["balance"])
        self._is_closed = bool(state["is_closed"])

    # ── properties ───────────────────────────────────────────────────────────

    @property
    def owner(self) -> str:
        return self._owner

    @property
    def balance(self) -> Decimal:
        return self._balance

    @property
    def is_closed(self) -> bool:
        return self._is_closed
