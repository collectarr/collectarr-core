from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PartialDateValue(BaseModel):
    """A catalog date with independently optional components."""

    model_config = ConfigDict(extra="forbid")

    year: int | None = Field(default=None, ge=1, le=9999)
    month: int | None = Field(default=None, ge=1, le=12)
    day: int | None = Field(default=None, ge=1, le=31)

    @model_validator(mode="before")
    @classmethod
    def parse_raw_value(cls, value: Any) -> Any:
        if isinstance(value, cls):
            return value
        if isinstance(value, date):
            return {"year": value.year, "month": value.month, "day": value.day}
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None
            try:
                decoded = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                decoded = None
            if isinstance(decoded, dict):
                return decoded
            parts = raw.split("-")
            if len(parts) in (1, 2, 3) and all(part.isdigit() for part in parts):
                return {
                    key: int(part)
                    for key, part in zip(("year", "month", "day"), parts, strict=False)
                }
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
            return {"year": parsed.year, "month": parsed.month, "day": parsed.day}
        return value

    @property
    def is_empty(self) -> bool:
        return self.year is None and self.month is None and self.day is None

    @property
    def iso_string(self) -> str | None:
        if self.year is None:
            return None
        value = f"{self.year:04d}"
        if self.month is None:
            return value
        value += f"-{self.month:02d}"
        if self.day is not None:
            value += f"-{self.day:02d}"
        return value

    @property
    def as_date(self) -> date | None:
        """Concrete date projection; missing components are never guessed."""
        if self.year is None or self.month is None or self.day is None:
            return None
        try:
            return date(self.year, self.month, self.day)
        except ValueError:
            return None

    def json_value(self) -> str | None:
        if self.is_empty:
            return None
        return json.dumps(self.model_dump(exclude_none=True), separators=(",", ":"))


def partial_date_from_storage(value: str | None) -> PartialDateValue | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        parsed = value
    try:
        result = PartialDateValue.model_validate(parsed)
    except ValueError:
        result = PartialDateValue.model_validate(value)
    return None if result.is_empty else result


def partial_date_storage(value: PartialDateValue | date | str | None) -> str | None:
    if value is None:
        return None
    parsed = PartialDateValue.model_validate(value)
    return parsed.json_value()
