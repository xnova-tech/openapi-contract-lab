"""Application assembly with an independently authored Swagger document."""

from pathlib import Path

import yaml
from fastapi import FastAPI

from app.routes import install_routes, install_validation_handler
from app.store import OrderStore

SPEC_PATH = Path(__file__).resolve().parents[1] / "spec" / "openapi.yaml"


def create_app(store: OrderStore | None = None) -> FastAPI:
    orders = store if store is not None else OrderStore.fresh()
    api = FastAPI(title="Order Contract Lab", version="1.0.0")

    def authored_openapi() -> dict[str, object]:
        with SPEC_PATH.open(encoding="utf-8") as source:
            document: dict[str, object] = yaml.safe_load(source)
        return document

    api.openapi = authored_openapi  # type: ignore[method-assign]
    install_validation_handler(api)
    install_routes(api, orders)
    return api


app = create_app()
