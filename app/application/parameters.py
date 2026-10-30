"""Parámetros de un resumen y la regla de precedencia: la configuración centralizada gana
al .env, pero solo con valores válidos. Una errata en Consul no rompe los resúmenes."""

import math
from collections.abc import Callable
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class SummaryParameters:
    model: str
    max_tokens: int
    temperature: float
    max_prompt_chars: int


def _non_blank_text(raw: str) -> str | None:
    return raw or None


def _positive_int(raw: str) -> int | None:
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def _temperature(raw: str) -> float | None:
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if math.isfinite(value) and 0 <= value <= 2 else None


# Solo estos nombres se leen de fuera. La API key no está a propósito: nunca va en Consul.
PARSERS: dict[str, Callable[[str], object | None]] = {
    "model": _non_blank_text,
    "max_tokens": _positive_int,
    "temperature": _temperature,
    "max_prompt_chars": _positive_int,
}


def apply_overrides(defaults: SummaryParameters, overrides: dict[str, str]) -> SummaryParameters:
    """Los valores de `overrides` válidos sustituyen a los de `defaults`; el resto se ignora."""
    changes = {}
    for name, raw in overrides.items():
        parse = PARSERS.get(name)
        value = parse(raw.strip()) if parse else None
        if value is not None:
            changes[name] = value
    return replace(defaults, **changes)
