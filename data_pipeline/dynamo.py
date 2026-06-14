"""DynamoDB helpers shared by upload/sync scripts."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def to_dynamo_value(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {str(key): to_dynamo_value(child) for key, child in value.items()}
    if isinstance(value, list):
        return [to_dynamo_value(child) for child in value]
    return value


def from_dynamo_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    if isinstance(value, dict):
        return {key: from_dynamo_value(child) for key, child in value.items()}
    if isinstance(value, list):
        return [from_dynamo_value(child) for child in value]
    return value

