"""Load and inspect an independently authored OpenAPI 3.1 document."""

from collections.abc import Hashable, Iterator, Mapping
from pathlib import Path
from typing import cast

import yaml
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate
from openapi_spec_validator.exceptions import OpenAPIError


class ContractError(ValueError):
    """The authored contract cannot be used for a reliable check."""


def as_mapping(value: object, location: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ContractError(f"{location}: expected an object with string keys")
    return cast(Mapping[str, object], value)


def member(source: Mapping[str, object], key: str, location: str) -> object:
    try:
        return source[key]
    except KeyError as exc:
        raise ContractError(f"{location}: missing {key!r}") from exc


def at_path(source: object, *parts: str) -> object:
    current = source
    for part in parts:
        current = member(as_mapping(current, "/".join(parts)), part, "/".join(parts))
    return current


def _references(value: object) -> Iterator[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "$ref":
                if not isinstance(child, str):
                    raise ContractError("$ref must be a string")
                yield child
            else:
                yield from _references(child)
    elif isinstance(value, list):
        for child in value:
            yield from _references(child)


def _resolve_pointer(document: Mapping[str, object], reference: str) -> object:
    if not reference.startswith("#/"):
        raise ContractError(f"Only local $ref values are supported: {reference}")
    current: object = document
    for escaped in reference[2:].split("/"):
        part = escaped.replace("~1", "/").replace("~0", "~")
        current = member(as_mapping(current, reference), part, reference)
    return current


def resolve_schema(document: Mapping[str, object], schema: object) -> Mapping[str, object]:
    """Inline this lab's local schema references for Draft 2020-12 validation."""

    def visit(value: object, seen: frozenset[str]) -> object:
        if isinstance(value, list):
            return [visit(child, seen) for child in value]
        if isinstance(value, dict):
            if "$ref" in value:
                reference = value["$ref"]
                if not isinstance(reference, str):
                    raise ContractError("$ref must be a string")
                if reference in seen:
                    raise ContractError(f"Cyclic schema reference: {reference}")
                target = visit(_resolve_pointer(document, reference), seen | {reference})
                return {
                    **as_mapping(target, reference),
                    **{key: visit(child, seen) for key, child in value.items() if key != "$ref"},
                }
            return {str(key): visit(child, seen) for key, child in value.items()}
        return value

    resolved = as_mapping(visit(schema, frozenset()), "response schema")
    Draft202012Validator.check_schema(resolved)
    return resolved


def load_contract(path: Path) -> Mapping[str, object]:
    try:
        with path.open(encoding="utf-8") as source:
            document = as_mapping(yaml.safe_load(source), str(path))
        if document.get("openapi") != "3.1.0":
            raise ContractError("Expected OpenAPI 3.1.0")
        for reference in _references(document):
            _resolve_pointer(document, reference)
        validate(cast(Mapping[Hashable, object], document))
        schemas = as_mapping(at_path(document, "components", "schemas"), "components/schemas")
        for schema in schemas.values():
            resolve_schema(document, schema)
        return document
    except (OSError, yaml.YAMLError, ValueError, TypeError, OpenAPIError) as exc:
        if isinstance(exc, ContractError):
            raise
        raise ContractError(f"Invalid OpenAPI document {path}: {exc}") from exc


def response_contract(
    document: Mapping[str, object], path_template: str, method: str, status: int
) -> tuple[str, Mapping[str, object]]:
    response = as_mapping(
        at_path(document, "paths", path_template, method, "responses", str(status)),
        f"{method.upper()} {path_template} {status}",
    )
    if "$ref" in response:
        reference = response["$ref"]
        if not isinstance(reference, str):
            raise ContractError("response $ref must be a string")
        response = as_mapping(_resolve_pointer(document, reference), reference)
    description = response.get("description")
    if not isinstance(description, str):
        raise ContractError(f"{method.upper()} {path_template} {status}: missing description")
    schema = at_path(response, "content", "application/json", "schema")
    return description, resolve_schema(document, schema)
