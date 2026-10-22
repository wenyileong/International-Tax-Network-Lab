"""Engine interface (plan v2.1, s 4.2) and status ladders (s 3)."""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any

from taxnetlab.datasets import Dataset
from taxnetlab.validation import ValidationReport

# Tracks
REPRODUCTION = "reproduction"   # published methods
ORIGINAL = "original"           # the author's own models
DEMONSTRATION = "demonstration"  # pipeline demonstrations; never a research method

TRACKS = (REPRODUCTION, ORIGINAL, DEMONSTRATION)

STATUSES = {
    REPRODUCTION: ("interface", "specified", "implemented", "verified", "replicated", "replicated_with_discrepancies"),
    ORIGINAL: ("interface", "specified", "implemented", "verified", "robust", "empirically_tested"),
    DEMONSTRATION: ("interface", "implemented", "verified"),
}
VERIFIED_OR_ABOVE = {"verified", "replicated", "replicated_with_discrepancies", "robust", "empirically_tested"}

# Outcome states (s 6.3): engines never return a plausible-looking number in place of a failure.
OK = "ok"
NO_SOLUTION = "no_solution_found"
NOT_CONVERGED = "not_converged"
CORNER = "corner_solution"
INVALID_INPUT = "invalid_input"
OUTCOMES = (OK, NO_SOLUTION, NOT_CONVERGED, CORNER, INVALID_INPUT)


class SpecificationNotValidatedError(NotImplementedError):
    """Raised by engines at ``interface`` status: no published specification has been transcribed."""


@dataclass(frozen=True)
class Parameter:
    name: str
    type: str  # "bool" | "choice" | "date" | "float" | "int" | "text" | "overrides"
    default: Any
    choices: tuple[str, ...] | None = None
    minimum: float | None = None
    maximum: float | None = None
    unit: str | None = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "type": self.type, "default": self.default, "choices": list(self.choices or []),
                "minimum": self.minimum, "maximum": self.maximum, "unit": self.unit, "description": self.description}


@dataclass(frozen=True)
class Measure:
    name: str          # namespaced, e.g. "demo.outbound_links"
    definition: str
    numerator: str
    denominator: str   # "none" where the measure is a level, not a ratio
    unit: str
    source_ref: str

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class EngineSpec:
    engine_id: str
    display_name: str
    track: str
    variant: str
    version: str
    status: str
    spec_ref: str
    purpose: str
    boundary: str
    next_step: str
    input_schema: tuple[str, ...]
    parameters: tuple[Parameter, ...] = ()
    measures: tuple[Measure, ...] = ()
    outputs: dict[str, tuple[str, ...]] = field(default_factory=dict)  # output table -> columns (and order)
    output_keys: dict[str, tuple[str, ...]] = field(default_factory=dict)  # output table -> primary key

    def __post_init__(self) -> None:
        if self.track not in TRACKS:
            raise ValueError(f"unknown track {self.track}")
        if self.status not in STATUSES[self.track]:
            raise ValueError(f"status {self.status} is not on the {self.track} ladder")

    @property
    def runnable(self) -> bool:
        return self.status != "interface"

    @property
    def verified(self) -> bool:
        return self.status in VERIFIED_OR_ABOVE

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine_id": self.engine_id, "display_name": self.display_name, "track": self.track,
            "variant": self.variant, "version": self.version, "status": self.status, "spec_ref": self.spec_ref,
            "purpose": self.purpose, "boundary": self.boundary, "next_step": self.next_step,
            "input_schema": list(self.input_schema), "parameters": [p.to_dict() for p in self.parameters],
            "measures": [m.to_dict() for m in self.measures], "runnable": self.runnable,
            "verified": self.verified, "outputs": {k: list(v) for k, v in self.outputs.items()},
        }


@dataclass
class EngineResult:
    outcome: str
    outputs: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    trace: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError(f"unknown outcome {self.outcome}")


class Engine:
    """Base class. Subclasses set ``spec`` and implement :meth:`_run`."""

    spec: EngineSpec

    def resolve_parameters(self, params: dict[str, Any] | None) -> tuple[dict[str, Any], ValidationReport]:
        report = ValidationReport()
        params = dict(params or {})
        known = {p.name for p in self.spec.parameters}
        for name in sorted(set(params) - known):
            report.error("unknown_parameter", f"unknown parameter '{name}'", params={"name": name})
        resolved: dict[str, Any] = {}
        for p in self.spec.parameters:
            value = params.get(p.name, p.default)
            try:
                value = _coerce(p, value)
            except (TypeError, ValueError) as exc:
                report.error("bad_parameter", f"{p.name}: {exc}", params={"name": p.name})
                continue
            resolved[p.name] = value
        return resolved, report

    def validate(self, dataset: Dataset, params: dict[str, Any]) -> ValidationReport:
        """Engine-specific checks of inputs. Errors block execution."""
        return ValidationReport()

    def run(self, dataset: Dataset, params: dict[str, Any]) -> EngineResult:
        if not self.spec.runnable:
            raise SpecificationNotValidatedError(
                f"{self.spec.engine_id} is at 'interface' status: {self.spec.next_step}")
        return self._run(dataset, params)

    def _run(self, dataset: Dataset, params: dict[str, Any]) -> EngineResult:  # pragma: no cover
        raise NotImplementedError


def _coerce(p: Parameter, value: Any) -> Any:
    if p.type == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in ("true", "false"):
            return value.lower() == "true"
        raise ValueError("expected true or false")
    if p.type == "choice":
        if value not in (p.choices or ()):
            raise ValueError(f"expected one of {list(p.choices or ())}")
        return value
    if p.type == "date":
        if value in (None, ""):
            return None
        return _dt.date.fromisoformat(str(value)).isoformat()
    if p.type == "text":
        if value is None:
            return None
        if not isinstance(value, str) or len(value) > 200:
            raise ValueError("expected text of at most 200 characters")
        return value.strip() or None
    if p.type == "overrides":
        # Scenario overrides: a list of small objects; their meaning is checked by the engine's validate().
        if value in (None, ""):
            return []
        if isinstance(value, str):
            import json
            value = json.loads(value)
        if not isinstance(value, list) or not all(isinstance(v, dict) for v in value) or len(value) > 500:
            raise ValueError("expected a list of override objects")
        return [dict(v) for v in value]
    if p.type in ("float", "int"):
        if isinstance(value, bool):
            raise ValueError("expected a number")
        number = float(value) if p.type == "float" else int(value)
        if p.type == "int" and isinstance(value, float) and not value.is_integer():
            raise ValueError("expected a whole number")
        if p.type == "float" and (number != number or number in (float("inf"), float("-inf"))):
            raise ValueError("expected a finite number")
        if p.minimum is not None and number < p.minimum:
            raise ValueError(f"must be at least {p.minimum}")
        if p.maximum is not None and number > p.maximum:
            raise ValueError(f"must be at most {p.maximum}")
        return number
    raise ValueError(f"unknown parameter type {p.type}")
