from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from config import MissingValuePolicy, ProjectionConfig


class ValidationFailure(ValueError):
    pass


class OutputValidator:
    def __init__(self, schema_path: str | Path | None = None) -> None:
        path = Path(schema_path) if schema_path else Path(__file__).with_name("candidate_schema.json")
        with path.open(encoding="utf-8") as handle:
            self.schema = json.load(handle)
        Draft202012Validator.check_schema(self.schema)

    def validate_canonical(self, records: list[dict[str, Any]]) -> None:
        self._validate(records, self.schema)

    def validate_projected(self, records: list[dict[str, Any]], config: ProjectionConfig) -> None:
        schema = self._projection_schema(config)
        self._validate(records, schema)

    def _projection_schema(self, config: ProjectionConfig) -> dict[str, Any]:
        canonical_item = self.schema["items"]
        definitions = deepcopy(self.schema.get("$defs", {}))
        fields = list(config.fields)
        if config.include_confidence and "confidence" not in fields:
            fields.append("confidence")
        if config.include_provenance and "provenance" not in fields:
            fields.append("provenance")
        if not config.include_confidence:
            fields = [field for field in fields if field != "confidence"]
        if not config.include_provenance:
            fields = [field for field in fields if field != "provenance"]

        properties: dict[str, Any] = {}
        for field in fields:
            output_name = config.rename.get(field, field)
            field_schema = deepcopy(canonical_item["properties"][field])
            if config.missing_value_policy == MissingValuePolicy.NULL:
                field_schema = {"anyOf": [field_schema, {"type": "null"}]}
            properties[output_name] = field_schema
        required = [] if config.missing_value_policy == MissingValuePolicy.OMIT else list(properties)
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$defs": definitions,
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "properties": properties, "required": required,
            },
        }

    @staticmethod
    def _validate(instance: Any, schema: dict[str, Any]) -> None:
        errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda error: list(error.path))
        if errors:
            details = "; ".join(
                f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
                for error in errors[:10]
            )
            raise ValidationFailure(f"Output failed JSON Schema validation: {details}")

