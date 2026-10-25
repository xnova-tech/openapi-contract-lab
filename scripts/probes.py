"""Deterministic requests covering the documented operations and errors."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Probe:
    label: str
    method: str
    path: str
    path_template: str
    status: int
    body: object | None = None
    query: tuple[tuple[str, str], ...] = ()


BASELINE_PROBES = (
    Probe("health", "get", "/health", "/health", 200),
    Probe("list", "get", "/orders", "/orders", 200),
    Probe("create", "post", "/orders", "/orders", 201, {"external_id": "ORD-{run_id}", "quantity": 2}),
    Probe("get", "get", "/orders/{order_id}", "/orders/{order_id}", 200),
    Probe("query", "get", "/orders", "/orders", 200, query=(("status", "new"),)),
    Probe(
        "duplicate",
        "post",
        "/orders",
        "/orders",
        409,
        {"external_id": "ORD-{run_id}", "quantity": 2},
    ),
    Probe(
        "invalid quantity",
        "post",
        "/orders",
        "/orders",
        422,
        {"external_id": "ORD-invalid-{run_id}", "quantity": 0},
    ),
    Probe(
        "confirm",
        "patch",
        "/orders/{order_id}/status",
        "/orders/{order_id}/status",
        200,
        {"status": "confirmed"},
    ),
    Probe(
        "invalid transition",
        "patch",
        "/orders/{order_id}/status",
        "/orders/{order_id}/status",
        409,
        {"status": "new"},
    ),
    Probe(
        "invalid status",
        "patch",
        "/orders/{order_id}/status",
        "/orders/{order_id}/status",
        422,
        {"status": "unknown"},
    ),
    Probe("missing order", "get", "/orders/999", "/orders/{order_id}", 404),
    Probe(
        "missing change",
        "patch",
        "/orders/999/status",
        "/orders/{order_id}/status",
        404,
        {"status": "cancelled"},
    ),
    Probe("filtered list", "get", "/orders", "/orders", 200, query=(("status", "confirmed"),)),
)

PREFIX_PROBE = Probe(
    "new external ID rule",
    "post",
    "/orders",
    "/orders",
    422,
    {"external_id": "legacy-{run_id}", "quantity": 1},
)
