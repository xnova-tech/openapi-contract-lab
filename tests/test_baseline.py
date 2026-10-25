"""Behavioral tests for the baseline service and displayed contract."""

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from app.models import CreateOrder, OrderStatus
from app.store import OrderNotFound, OrderStore

ROOT = Path(__file__).resolve().parents[1]


def test_authored_spec_is_displayed(client: TestClient) -> None:
    authored = yaml.safe_load((ROOT / "spec" / "openapi.yaml").read_text(encoding="utf-8"))
    assert client.get("/openapi.json").json() == authored
    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "/openapi.json" in docs.text


def test_order_lifecycle_and_filters(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/orders").json() == []
    created = client.post("/orders", json={"external_id": "ORD-1", "quantity": 2})
    assert created.status_code == 201
    assert created.json() == {"id": 1, "external_id": "ORD-1", "quantity": 2, "status": "new"}
    assert client.get("/orders/1").json() == created.json()
    assert len(client.get("/orders", params={"status": "new"}).json()) == 1
    assert client.get("/orders", params={"status": "confirmed"}).json() == []
    confirmed = client.patch("/orders/1/status", json={"status": "confirmed"})
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"
    assert client.get("/orders", params={"status": "confirmed"}).json() == [confirmed.json()]
    cancelled = client.patch("/orders/1/status", json={"status": "cancelled"})
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_error_paths_have_one_shape(client: TestClient) -> None:
    request = {"external_id": "ORD-2", "quantity": 1}
    assert client.post("/orders", json=request).status_code == 201
    examples = [
        (client.post("/orders", json=request), 409, "duplicate_external_id"),
        (client.post("/orders", json={"external_id": "x", "quantity": 0}), 422, "validation_error"),
        (
            client.post("/orders", json={"external_id": "x", "quantity": "1"}),
            422,
            "validation_error",
        ),
        (client.get("/orders/99"), 404, "not_found"),
        (client.get("/orders/not-an-int"), 422, "validation_error"),
        (
            client.patch("/orders/1/status", json={"status": "new"}),
            409,
            "invalid_status_transition",
        ),
        (client.patch("/orders/1/status", json={"status": "other"}), 422, "validation_error"),
    ]
    for response, status, code in examples:
        assert response.status_code == status
        assert response.json()["code"] == code
        assert isinstance(response.json()["message"], str)
        assert set(response.json()) == {"code", "message"}


def test_store_reset_is_deterministic() -> None:
    store = OrderStore.fresh()
    store.create(CreateOrder(external_id="ORD-3", quantity=1))
    store.reset()
    assert store.list() == []
    assert store.create(CreateOrder(external_id="ORD-3", quantity=1)).id == 1
    assert store.get(1).status is OrderStatus.NEW
    try:
        store.get(99)
    except OrderNotFound:
        pass
    else:
        raise AssertionError("Unknown order must fail")
