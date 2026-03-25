"""Validate pasted YAML specifications against bundled JSON Schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"

_SCHEMA_TRIPLES: tuple[tuple[str, str, str], ...] = (
    ("product.yaml", "product_yaml", "Product.1.0.0.0_json_schema.json"),
    ("architecture.yaml", "architecture_yaml", "Architecture.1.0.0.0_json_schema.json"),
    ("catalog.yaml", "catalog_yaml", "Catalog.1.0.0.0_json_schema.json"),
)


def _load_schema(name: str) -> dict[str, Any]:
    path = _SCHEMA_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"Missing schema file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_spec_bodies(
    product_yaml: str,
    architecture_yaml: str,
    catalog_yaml: str,
) -> list[str]:
    """
    Parse YAML and validate against Product / Architecture / Catalog schemas.
    Returns a list of human-readable errors (empty if all valid).
    """
    bodies = {
        "product_yaml": product_yaml,
        "architecture_yaml": architecture_yaml,
        "catalog_yaml": catalog_yaml,
    }
    errors: list[str] = []
    for label, key, schema_file in _SCHEMA_TRIPLES:
        raw = bodies[key]
        if not raw or not str(raw).strip():
            errors.append(f"{label}: empty")
            continue
        try:
            data = yaml.safe_load(raw)
        except yaml.YAMLError as e:
            errors.append(f"{label}: invalid YAML ({e})")
            continue
        if not isinstance(data, dict):
            errors.append(f"{label}: root must be a mapping (object)")
            continue
        schema = _load_schema(schema_file)
        validator = Draft202012Validator(schema)
        for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
            loc = ".".join(str(p) for p in err.path) if err.path else "(root)"
            errors.append(f"{label}: {err.message} (at {loc})")
    return errors
