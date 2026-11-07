"""Validation and display rules for untrusted config and action inputs."""

from __future__ import annotations

import html
import math
import re
from decimal import Decimal, InvalidOperation

MAX_CONFIG_BYTES = 1_000_000
MAX_CONFIG_DEPTH = 25
MAX_CONFIG_NODES = 10_000
SENSITIVE_KEY_PARTS = (
    "api_key", "apikey", "access_key", "secret", "password", "passwd", "token", "credential",
)
SECRET_PATTERNS = tuple(re.compile(pattern) for pattern in (
    r"gh[pousr]_[A-Za-z0-9]{20,}", r"github_pat_[A-Za-z0-9_]{20,}",
    r"AKIA[0-9A-Z]{16}", r"sk-[A-Za-z0-9_-]{20,}", r"hf_[A-Za-z0-9]{20,}",
    r"xox[abprs]-[A-Za-z0-9-]{10,}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*",
))


class ConfigError(ValueError):
    """A value-free diagnostic safe to show in reports."""


def looks_sensitive(value: object) -> bool:
    return isinstance(value, str) and any(p.search(value) for p in SECRET_PATTERNS)


def safe_text(value: object) -> str:
    text = str(value)
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[redacted]", text)
    return "".join(c if c.isprintable() else " " for c in text)


def markdown(value: object) -> str:
    text = html.escape(safe_text(value), quote=True)
    return re.sub(r"([\\`*_{}\[\]()#+!|~])", r"\\\1", text)


def number(value: object, field: str, *, integer: bool = False, allow_zero: bool = False) -> int | float:
    """Accept numeric scalars without truncating fractions or accepting booleans."""
    try:
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ValueError
        text = str(value).strip()
        if "," in text:
            if not re.fullmatch(r"[+-]?\d{1,3}(,\d{3})+(\.\d+)?", text):
                raise ValueError
            text = text.replace(",", "")
        decimal = Decimal(text)
        if not decimal.is_finite() or decimal < 0 or (not allow_zero and decimal == 0):
            raise ValueError
        if integer and decimal != decimal.to_integral_value():
            raise ValueError
        result = float(decimal)
        if not math.isfinite(result) or (decimal != 0 and result == 0):
            raise ValueError
        return int(decimal) if integer else result
    except (InvalidOperation, ValueError, TypeError, OverflowError):
        kind = "integer" if integer else "number"
        bound = "non-negative" if allow_zero else "positive"
        raise ConfigError(f"Invalid {safe_text(field)}: expected a finite {bound} {kind}.") from None
