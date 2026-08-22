from __future__ import annotations


class EventSourcingError(Exception):
    """Base exception for all event-sourcing library errors."""


class OptimisticConcurrencyError(EventSourcingError):
    def __init__(self, aggregate_id: str, expected: int, actual: int | None) -> None:
        actual_str = (
            str(actual) if actual is not None else "None (aggregate does not exist)"
        )
        super().__init__(
            f"Concurrency conflict for aggregate '{aggregate_id}': "
            f"expected version {expected}, actual {actual_str}."
        )
        self.aggregate_id = aggregate_id
        self.expected = expected
        self.actual = actual


class AggregateNotFoundError(EventSourcingError):
    def __init__(self, aggregate_id: str) -> None:
        super().__init__(f"Aggregate '{aggregate_id}' not found.")
        self.aggregate_id = aggregate_id


class UnknownEventTypeError(EventSourcingError):
    def __init__(self, event_type: str) -> None:
        super().__init__(f"No handler registered for event type '{event_type}'.")
        self.event_type = event_type


class InsufficientFundsError(EventSourcingError):
    def __init__(self, aggregate_id: str, balance: object, amount: object) -> None:
        super().__init__(
            f"Insufficient funds in account '{aggregate_id}': "
            f"balance={balance}, requested={amount}."
        )
        self.aggregate_id = aggregate_id


class AccountClosedError(EventSourcingError):
    def __init__(self, aggregate_id: str) -> None:
        super().__init__(f"Account '{aggregate_id}' is already closed.")
        self.aggregate_id = aggregate_id
