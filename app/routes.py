"""Thin HTTP adapters around the in-memory order store."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.models import ChangeStatus, CreateOrder, ErrorBody, Order, OrderStatus
from app.rules import accepts_external_id
from app.store import DuplicateExternalId, InvalidStatusTransition, OrderNotFound, OrderStore


def _error(status: int, code: str, message: str) -> JSONResponse:
    body = ErrorBody(code=code, message=message)
    return JSONResponse(status_code=status, content=body.model_dump())


def install_validation_handler(api: FastAPI) -> None:
    @api.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return _error(422, "validation_error", "Invalid request data")


def install_routes(api: FastAPI, orders: OrderStore) -> None:
    _install_read_routes(api, orders)
    _install_write_routes(api, orders)


def _install_read_routes(api: FastAPI, orders: OrderStore) -> None:
    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.get("/orders")
    def list_orders(status: OrderStatus | None = None) -> list[Order]:
        return orders.list(status)

    @api.get("/orders/{order_id}", response_model=None)
    def get_order(order_id: int) -> Order | JSONResponse:
        try:
            return orders.get(order_id)
        except OrderNotFound:
            return _error(404, "not_found", "Order not found")


def _install_write_routes(api: FastAPI, orders: OrderStore) -> None:
    @api.post("/orders", status_code=201, response_model=None)
    def create_order(request: CreateOrder) -> Order | JSONResponse:
        if not accepts_external_id(request.external_id):
            return _error(422, "validation_error", "Invalid request data")
        try:
            return orders.create(request)
        except DuplicateExternalId:
            return _error(409, "duplicate_external_id", "External ID already exists")

    @api.patch("/orders/{order_id}/status", response_model=None)
    def change_status(order_id: int, request: ChangeStatus) -> Order | JSONResponse:
        try:
            return orders.change_status(order_id, request.status)
        except OrderNotFound:
            return _error(404, "not_found", "Order not found")
        except InvalidStatusTransition:
            return _error(409, "invalid_status_transition", "Status transition is not allowed")
