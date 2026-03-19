"""libcst visitor that finds unannotated locations in Python source."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

from refactory_annotate.models import AnnotationKind


@dataclass
class AnnotationLocation:
    """A source location that needs a type annotation."""

    file: Path
    line: int  # 0-indexed (pyright convention: libcst_line - 1)
    column: int  # 0-indexed
    kind: AnnotationKind
    name: str  # identifier name (parameter, function, or variable name)


def find_unannotated_locations(
    source: str, path: Path
) -> list[AnnotationLocation]:
    """Parse *source* and return all locations that lack type annotations.

    Discovers:
    - Function parameters that have no annotation (excluding ``self``/``cls``).
    - Function/method definitions that have no return-type annotation.

    Returns a list of :class:`AnnotationLocation` instances with
    positions in LSP (0-indexed) convention.
    """
    tree = cst.parse_module(source)
    wrapper = MetadataWrapper(tree)
    visitor = _LocationVisitor(path)
    wrapper.visit(visitor)
    return visitor.locations


class _LocationVisitor(cst.CSTVisitor):
    """Collect unannotated parameter and return-type locations."""

    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, path: Path) -> None:
        self.locations: list[AnnotationLocation] = []
        self._path = path

    # ------------------------------------------------------------------
    # Visitor methods
    # ------------------------------------------------------------------

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        if node.returns is not None:
            # Return type already annotated — skip
            return

        name_pos = self.get_metadata(PositionProvider, node.name)
        self.locations.append(
            AnnotationLocation(
                file=self._path,
                line=name_pos.start.line - 1,  # convert to 0-indexed
                column=name_pos.start.column,
                kind=AnnotationKind.RETURN,
                name=node.name.value,
            )
        )

    def visit_Param(self, node: cst.Param) -> None:
        if node.annotation is not None:
            # Already annotated — skip
            return

        param_name = node.name.value
        if param_name in ("self", "cls"):
            # Never annotate implicit self/cls parameters
            return

        # Skip *args and **kwargs whose star handling is outside the name node
        name_pos = self.get_metadata(PositionProvider, node.name)
        self.locations.append(
            AnnotationLocation(
                file=self._path,
                line=name_pos.start.line - 1,  # convert to 0-indexed
                column=name_pos.start.column,
                kind=AnnotationKind.PARAM,
                name=param_name,
            )
        )
