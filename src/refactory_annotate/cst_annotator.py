"""libcst transformer that inserts PEP 484 type annotations."""

from __future__ import annotations

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

from refactory_annotate.models import AnnotationKind
from refactory_annotate.pyright_lsp import collect_required_imports

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_annotations(
    source: str,
    annotations: dict[tuple[int, int], tuple[AnnotationKind, str]],
) -> str:
    """Insert annotations into *source* and return the modified code.

    Args:
        source: Original Python source text.
        annotations: Mapping of ``(pyright_line, column)`` to
            ``(kind, type_string)`` pairs.  Positions use 0-indexed
            lines (LSP convention).

    Returns:
        Modified source with annotations inserted.  The function is
        idempotent: already-annotated locations are left unchanged.
    """
    if not annotations:
        return source

    tree = cst.parse_module(source)
    wrapper = MetadataWrapper(tree)
    transformer = _AnnotationTransformer(annotations)
    new_tree = wrapper.visit(transformer)
    new_source = new_tree.code

    # Add any required typing imports
    type_strings = [t for _, t in annotations.values()]
    required = collect_required_imports(type_strings)
    if required:
        new_source = _add_typing_imports(new_source, required)

    return new_source


# ---------------------------------------------------------------------------
# CST transformer
# ---------------------------------------------------------------------------


class _AnnotationTransformer(cst.CSTTransformer):
    """Insert missing type annotations at the given positions."""

    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(
        self,
        annotations: dict[tuple[int, int], tuple[AnnotationKind, str]],
    ) -> None:
        super().__init__()
        self._annotations = annotations

    def leave_FunctionDef(
        self, original: cst.FunctionDef, updated: cst.FunctionDef
    ) -> cst.FunctionDef:
        if updated.returns is not None:
            return updated  # already annotated

        name_pos = self.get_metadata(PositionProvider, original.name)
        key = (name_pos.start.line - 1, name_pos.start.column)
        entry = self._annotations.get(key)
        if entry is None or entry[0] != AnnotationKind.RETURN:
            return updated

        return updated.with_changes(
            returns=cst.Annotation(
                annotation=cst.parse_expression(entry[1]),
                whitespace_before_indicator=cst.SimpleWhitespace(" "),
                whitespace_after_indicator=cst.SimpleWhitespace(" "),
            )
        )

    def leave_Param(
        self, original: cst.Param, updated: cst.Param
    ) -> cst.Param:
        if updated.annotation is not None:
            return updated  # already annotated
        if updated.name.value in ("self", "cls"):
            return updated

        name_pos = self.get_metadata(PositionProvider, original.name)
        key = (name_pos.start.line - 1, name_pos.start.column)
        entry = self._annotations.get(key)
        if entry is None or entry[0] != AnnotationKind.PARAM:
            return updated

        return updated.with_changes(
            annotation=cst.Annotation(
                annotation=cst.parse_expression(entry[1]),
            )
        )


# ---------------------------------------------------------------------------
# Import insertion helper
# ---------------------------------------------------------------------------


def _add_typing_imports(source: str, names: list[str]) -> str:
    """Ensure ``from typing import <names>`` is present in *source*.

    Merges new names into an existing ``from typing import ...`` statement
    if one is present; otherwise inserts a new statement near the top of
    the file (after the module docstring and any ``from __future__`` imports).
    """
    try:
        tree = cst.parse_module(source)
    except cst.ParserSyntaxError:
        return source  # don't corrupt the file

    # Collect names already imported from typing
    existing: set[str] = set()
    for stmt in tree.body:
        names_to_add = _extract_typing_imports(stmt)
        existing.update(names_to_add)

    to_add = [n for n in names if n not in existing]
    if not to_add:
        return source

    # Try to merge into an existing "from typing import ..." statement
    transformer = _ImportMerger(to_add)
    new_tree = tree.visit(transformer)
    if transformer.merged:
        return new_tree.code

    # No existing from-typing import; insert one
    return _insert_typing_import(source, to_add)


def _extract_typing_imports(stmt: cst.BaseStatement) -> list[str]:
    """Return names imported from 'typing' in *stmt*, or empty list."""
    if not isinstance(stmt, cst.SimpleStatementLine):
        return []
    for small in stmt.body:
        if (
            isinstance(small, cst.ImportFrom)
            and isinstance(small.names, (list, tuple))
            and small.module is not None
            and _dotted_name(small.module) == "typing"
        ):
            return [
                alias.name.value
                for alias in small.names
                if isinstance(alias.name, cst.Name)
            ]
    return []


def _dotted_name(node: cst.BaseExpression) -> str:
    """Return dotted name string from an Attribute or Name node."""
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        return f"{_dotted_name(node.value)}.{node.attr.value}"
    return ""


class _ImportMerger(cst.CSTTransformer):
    """Merge new names into an existing 'from typing import ...' statement."""

    def __init__(self, names_to_add: list[str]) -> None:
        super().__init__()
        self._names = names_to_add
        self.merged = False

    def leave_ImportFrom(
        self, original: cst.ImportFrom, updated: cst.ImportFrom
    ) -> cst.ImportFrom:
        if updated.module is None or _dotted_name(updated.module) != "typing":
            return updated
        if not isinstance(updated.names, (list, tuple)):
            return updated  # "from typing import *" — don't touch

        existing_names = {
            alias.name.value
            for alias in updated.names
            if isinstance(alias.name, cst.Name)
        }
        new_aliases = list(updated.names)
        added_any = False
        for name in self._names:
            if name not in existing_names:
                # Add a comma-separated alias with leading whitespace
                new_aliases.append(
                    cst.ImportAlias(
                        name=cst.Name(name),
                        comma=cst.MaybeSentinel.DEFAULT,
                    )
                )
                added_any = True

        if not added_any:
            return updated

        # Fix commas: all but last get a comma
        fixed: list[cst.ImportAlias] = []
        for i, alias in enumerate(new_aliases):
            if i < len(new_aliases) - 1:
                alias = alias.with_changes(
                    comma=cst.Comma(
                        whitespace_after=cst.SimpleWhitespace(" ")
                    )
                )
            else:
                alias = alias.with_changes(comma=cst.MaybeSentinel.DEFAULT)
            fixed.append(alias)

        self.merged = True
        return updated.with_changes(names=fixed)


def _insert_typing_import(source: str, names: list[str]) -> str:
    """Insert 'from typing import ...' into *source* at the right position."""
    names_str = ", ".join(sorted(names))
    import_line = f"from typing import {names_str}\n"

    lines = source.splitlines(keepends=True)
    insert_at = 0

    # Skip: encoding cookie, module docstring, __future__ imports
    # Strategy: insert after the last "from __future__" import, or before the
    # first non-comment, non-blank, non-docstring, non-future-import line.
    i = 0
    # Skip blank lines and comments at the top
    while i < len(lines) and (
        lines[i].strip() == "" or lines[i].lstrip().startswith("#")
    ):
        i += 1
    # Skip module docstring (triple-quoted string literal)
    if i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith(('"""', "'''")):
            quote = stripped[:3]
            if stripped.count(quote) >= 2 and len(stripped) > 6:
                # Single-line docstring
                i += 1
            else:
                i += 1
                while i < len(lines) and quote not in lines[i]:
                    i += 1
                i += 1  # consume closing quote line
    # Skip __future__ imports
    last_future = i
    while i < len(lines):
        if lines[i].startswith("from __future__"):
            last_future = i + 1
            i += 1
        else:
            break

    insert_at = last_future

    lines.insert(insert_at, import_line)
    return "".join(lines)
