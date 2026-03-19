"""Data models for refactory-annotate."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class AnnotationKind(str, Enum):  # noqa: UP042
    """Kind of annotation location."""

    PARAM = "param"
    RETURN = "return"
    VARIABLE = "variable"


@dataclass
class InferredType:
    """A type inferred by pyright at a specific source location."""

    file: Path
    line: int  # 0-indexed (LSP convention)
    column: int  # 0-indexed (LSP convention)
    kind: AnnotationKind
    name: str
    type_string: str  # The type annotation string to insert


@dataclass
class AnnotationPlan:
    """Types to insert, grouped by file."""

    by_file: dict[Path, list[InferredType]] = field(default_factory=dict)

    def add(self, inferred: InferredType) -> None:
        """Add an InferredType to this plan."""
        self.by_file.setdefault(inferred.file, []).append(inferred)

    def is_empty(self) -> bool:
        """Return True if the plan has no annotations to insert."""
        return all(len(v) == 0 for v in self.by_file.values())


@dataclass
class UnannotatableLocation:
    """A location that could not be annotated (pyright returned Unknown)."""

    file: Path
    line: int  # 0-indexed
    column: int  # 0-indexed
    name: str
    kind: AnnotationKind
    reason: str


@dataclass
class AnnotationReport:
    """Summary of the annotation run."""

    files_processed: int = 0
    inserted: int = 0
    skipped_already_annotated: int = 0
    unannotatable: list[UnannotatableLocation] = field(default_factory=list)
    mypy_errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """True if there are no mypy errors."""
        return len(self.mypy_errors) == 0
