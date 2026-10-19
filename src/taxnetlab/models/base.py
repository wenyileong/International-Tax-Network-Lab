from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class ModelResult:
    model_id: str
    model_version: str
    status: str
    outputs: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()

class SpecificationNotValidatedError(NotImplementedError):
    pass
