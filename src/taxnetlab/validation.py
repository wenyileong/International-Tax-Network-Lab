"""Validation reports.

Issues carry a stable ``code`` and ``params`` so that the interface can translate them
(see ``web/locales``). The English ``message`` is a fallback for the CLI and notebooks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ERROR = "error"      # blocks import or execution
WARNING = "warning"  # visible, does not block
INFO = "info"

_LEVEL_ORDER = {ERROR: 0, WARNING: 1, INFO: 2}


@dataclass(frozen=True)
class Issue:
    level: str
    code: str
    message: str
    table: str | None = None
    row: int | None = None  # 1-based data row number (header excluded)
    column: str | None = None
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "code": self.code,
            "message": self.message,
            "table": self.table,
            "row": self.row,
            "column": self.column,
            "params": dict(self.params),
        }


@dataclass
class ValidationReport:
    issues: list[Issue] = field(default_factory=list)

    def add(self, level: str, code: str, message: str, **kwargs: Any) -> None:
        params = kwargs.pop("params", {})
        self.issues.append(Issue(level, code, message, params=params, **kwargs))

    def error(self, code: str, message: str, **kwargs: Any) -> None:
        self.add(ERROR, code, message, **kwargs)

    def warning(self, code: str, message: str, **kwargs: Any) -> None:
        self.add(WARNING, code, message, **kwargs)

    def info(self, code: str, message: str, **kwargs: Any) -> None:
        self.add(INFO, code, message, **kwargs)

    def extend(self, other: "ValidationReport") -> None:
        self.issues.extend(other.issues)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == ERROR]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == WARNING]

    @property
    def ok(self) -> bool:
        return not self.errors

    def sorted(self) -> list[Issue]:
        return sorted(
            self.issues,
            key=lambda i: (_LEVEL_ORDER.get(i.level, 9), i.table or "", i.row or 0, i.code),
        )

    def summary(self) -> dict[str, int]:
        return {
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "info": sum(1 for i in self.issues if i.level == INFO),
        }

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "summary": self.summary(), "issues": [i.to_dict() for i in self.sorted()]}

    def format_text(self, limit: int = 50) -> str:
        lines = []
        for issue in self.sorted()[:limit]:
            where = ""
            if issue.table:
                where = f" [{issue.table}"
                if issue.row is not None:
                    where += f" row {issue.row}"
                if issue.column:
                    where += f", {issue.column}"
                where += "]"
            lines.append(f"{issue.level.upper():7} {issue.code}{where}: {issue.message}")
        extra = len(self.issues) - limit
        if extra > 0:
            lines.append(f"... and {extra} more")
        return "\n".join(lines) if lines else "No issues."


class ValidationError(Exception):
    """Raised when an operation is blocked by validation errors."""

    def __init__(self, report: ValidationReport, message: str = "Validation failed"):
        super().__init__(f"{message}: {len(report.errors)} error(s)")
        self.report = report
