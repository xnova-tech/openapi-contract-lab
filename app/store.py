"""Deterministic in-memory order storage."""

from dataclasses import dataclass

from app.models import CreateOrder, Order, OrderStatus
from app.rules import can_transition


class OrderNotFound(Exception):
    pass


class DuplicateExternalId(Exception):
    pass


class InvalidStatusTransition(Exception):
    pass


@dataclass
class OrderStore:
    _orders: dict[int, Order]
    _next_id: int

    @classmethod
    def fresh(cls) -> "OrderStore":
        return cls(_orders={}, _next_id=1)

    def reset(self) -> None:
        self._orders.clear()
        self._next_id = 1

    def list(self, status: OrderStatus | None = None) -> list[Order]:
        return [order.model_copy() for order in self._orders.values() if status is None or order.status == status]

    def get(self, order_id: int) -> Order:
        try:
            return self._orders[order_id].model_copy()
        except KeyError as exc:
            raise OrderNotFound from exc

    def create(self, request: CreateOrder) -> Order:
        if any(order.external_id == request.external_id for order in self._orders.values()):
            raise DuplicateExternalId
        order = Order(
            id=self._next_id,
            external_id=request.external_id,
            quantity=request.quantity,
            status=OrderStatus.NEW,
        )
        self._orders[order.id] = order
        self._next_id += 1
        return order.model_copy()

    def change_status(self, order_id: int, target: OrderStatus) -> Order:
        order = self.get(order_id)
        if not can_transition(order.status, target):
            raise InvalidStatusTransition
        updated = order.model_copy(update={"status": target})
        self._orders[order_id] = updated
        return updated.model_copy()
