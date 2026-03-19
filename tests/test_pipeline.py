"""Tests for the annotation pipeline modules."""

from __future__ import annotations

import textwrap
from pathlib import Path

from refactory_annotate.cst_annotator import _add_typing_imports, apply_annotations
from refactory_annotate.location_finder import (
    find_unannotated_locations,
)
from refactory_annotate.models import (
    AnnotationKind,
    AnnotationPlan,
    AnnotationReport,
    InferredType,
)
from refactory_annotate.pyright_lsp import (
    _contains_unknown,
    collect_required_imports,
    parse_hover_param_type,
    parse_hover_return_type,
)

# ---------------------------------------------------------------------------
# models.py
# ---------------------------------------------------------------------------


class TestAnnotationPlan:
    def test_add_and_retrieve(self, tmp_path: Path) -> None:
        plan = AnnotationPlan()
        f = tmp_path / "a.py"
        it = InferredType(
            file=f,
            line=0,
            column=4,
            kind=AnnotationKind.RETURN,
            name="add",
            type_string="int",
        )
        plan.add(it)
        assert not plan.is_empty()
        assert plan.by_file[f] == [it]

    def test_is_empty(self) -> None:
        plan = AnnotationPlan()
        assert plan.is_empty()

    def test_annotation_report_success(self) -> None:
        report = AnnotationReport()
        assert report.success is True
        report.mypy_errors = ["some error"]
        assert report.success is False


# ---------------------------------------------------------------------------
# pyright_lsp.py — parsing helpers
# ---------------------------------------------------------------------------


class TestParseHoverReturnType:
    def test_simple_int(self) -> None:
        hover = "(function) def add(\n    x: int,\n    y: int\n) -> int"
        assert parse_hover_return_type(hover) == "int"

    def test_single_line(self) -> None:
        hover = "(function) def greet(name: str) -> str"
        assert parse_hover_return_type(hover) == "str"

    def test_none_return(self) -> None:
        hover = "(method) def __init__(self: Self@Counter) -> None"
        assert parse_hover_return_type(hover) == "None"

    def test_generic_return(self) -> None:
        hover = "(function) def get_items() -> list[int]"
        assert parse_hover_return_type(hover) == "list[int]"

    def test_complex_return(self) -> None:
        hover = "(function) def f(x: str) -> dict[str, list[int]]"
        assert parse_hover_return_type(hover) == "dict[str, list[int]]"

    def test_unknown_return_is_none(self) -> None:
        hover = "(function) def add(x: Unknown, y: Unknown) -> Unknown"
        assert parse_hover_return_type(hover) is None

    def test_method_prefix(self) -> None:
        hover = "(method) def increment(self: Self@Counter) -> int"
        assert parse_hover_return_type(hover) == "int"

    def test_not_a_function(self) -> None:
        hover = "(parameter) x: int"
        assert parse_hover_return_type(hover) is None


class TestParseHoverParamType:
    def test_simple_int(self) -> None:
        hover = "(parameter) x: int"
        assert parse_hover_param_type(hover) == "int"

    def test_str(self) -> None:
        hover = "(parameter) name: str"
        assert parse_hover_param_type(hover) == "str"

    def test_generic(self) -> None:
        hover = "(parameter) items: list[str]"
        assert parse_hover_param_type(hover) == "list[str]"

    def test_unknown_is_none(self) -> None:
        hover = "(parameter) x: Unknown"
        assert parse_hover_param_type(hover) is None

    def test_not_a_param(self) -> None:
        hover = "(function) def add(x: int) -> int"
        assert parse_hover_param_type(hover) is None


class TestContainsUnknown:
    def test_plain_unknown(self) -> None:
        assert _contains_unknown("Unknown") is True

    def test_union_with_unknown(self) -> None:
        assert _contains_unknown("Unknown | None") is True

    def test_no_unknown(self) -> None:
        assert _contains_unknown("int") is False
        assert _contains_unknown("dict[str, list[int]]") is False


class TestCollectRequiredImports:
    def test_no_imports_needed(self) -> None:
        assert collect_required_imports(["int", "str", "list[int]"]) == []

    def test_any_needed(self) -> None:
        assert collect_required_imports(["Any"]) == ["Any"]

    def test_callable_needed(self) -> None:
        result = collect_required_imports(["Callable[[int], str]"])
        assert "Callable" in result

    def test_multiple(self) -> None:
        type_strings = ["Any", "Callable[[int], str]", "Literal[42]"]
        result = collect_required_imports(type_strings)
        assert "Any" in result
        assert "Callable" in result
        assert "Literal" in result


# ---------------------------------------------------------------------------
# location_finder.py
# ---------------------------------------------------------------------------


class TestFindUnannotatedLocations:
    def test_unannotated_function(self, tmp_path: Path) -> None:
        src = "def add(x, y):\n    return x + y\n"
        path = tmp_path / "f.py"
        locs = find_unannotated_locations(src, path)
        names = {loc.name for loc in locs}
        kinds = {loc.kind for loc in locs}
        assert "x" in names
        assert "y" in names
        assert "add" in names
        assert AnnotationKind.PARAM in kinds
        assert AnnotationKind.RETURN in kinds

    def test_fully_annotated_function(self, tmp_path: Path) -> None:
        src = "def add(x: int, y: int) -> int:\n    return x + y\n"
        path = tmp_path / "f.py"
        locs = find_unannotated_locations(src, path)
        assert locs == []

    def test_skip_self_cls(self, tmp_path: Path) -> None:
        src = textwrap.dedent("""\
            class C:
                def method(self):
                    pass
                @classmethod
                def cm(cls):
                    pass
        """)
        path = tmp_path / "f.py"
        locs = find_unannotated_locations(src, path)
        names = {loc.name for loc in locs}
        assert "self" not in names
        assert "cls" not in names

    def test_partial_annotation(self, tmp_path: Path) -> None:
        src = "def greet(name: str):\n    return f'Hello {name}'\n"
        path = tmp_path / "f.py"
        locs = find_unannotated_locations(src, path)
        kinds = {loc.kind for loc in locs}
        assert AnnotationKind.RETURN in kinds
        # param is already annotated
        names = {loc.name for loc in locs}
        assert "name" not in names

    def test_positions_are_zero_indexed(self, tmp_path: Path) -> None:
        src = "def add(x, y):\n    return x + y\n"
        path = tmp_path / "f.py"
        locs = find_unannotated_locations(src, path)
        for loc in locs:
            assert loc.line >= 0  # 0-indexed

        ret_loc = next(loc for loc in locs if loc.kind == AnnotationKind.RETURN)
        assert ret_loc.line == 0  # first line (0-indexed)
        assert ret_loc.column == 4  # 'add' starts at column 4


# ---------------------------------------------------------------------------
# cst_annotator.py
# ---------------------------------------------------------------------------


class TestApplyAnnotations:
    def test_add_param_and_return(self) -> None:
        src = "def add(x, y):\n    return x + y\n"
        ann: dict[tuple[int, int], tuple[AnnotationKind, str]] = {
            (0, 4): (AnnotationKind.RETURN, "int"),
            (0, 8): (AnnotationKind.PARAM, "int"),
            (0, 11): (AnnotationKind.PARAM, "int"),
        }
        result = apply_annotations(src, ann)
        assert "def add(x: int, y: int) -> int:" in result

    def test_no_annotations_unchanged(self) -> None:
        src = "def add(x, y):\n    return x + y\n"
        result = apply_annotations(src, {})
        assert result == src

    def test_idempotent(self) -> None:
        src = "def add(x, y):\n    return x + y\n"
        ann: dict[tuple[int, int], tuple[AnnotationKind, str]] = {
            (0, 4): (AnnotationKind.RETURN, "int"),
            (0, 8): (AnnotationKind.PARAM, "int"),
            (0, 11): (AnnotationKind.PARAM, "int"),
        }
        first = apply_annotations(src, ann)
        # Second pass should not change already-annotated code
        locs_after = find_unannotated_locations(first, Path("f.py"))
        assert locs_after == []

    def test_preserves_formatting(self) -> None:
        src = textwrap.dedent("""\
            def greet(name):
                # say hello
                return f"Hello, {name}"
        """)
        ann: dict[tuple[int, int], tuple[AnnotationKind, str]] = {
            (0, 4): (AnnotationKind.RETURN, "str"),
            (0, 10): (AnnotationKind.PARAM, "str"),
        }
        result = apply_annotations(src, ann)
        assert "# say hello" in result
        assert 'f"Hello, {name}"' in result

    def test_adds_typing_import(self) -> None:
        src = "def f(x):\n    return x\n"
        ann: dict[tuple[int, int], tuple[AnnotationKind, str]] = {
            (0, 4): (AnnotationKind.RETURN, "Any"),
            (0, 6): (AnnotationKind.PARAM, "Any"),
        }
        result = apply_annotations(src, ann)
        assert "from typing import Any" in result

    def test_none_return_type(self) -> None:
        src = "def reset(self):\n    self.x = 0\n"
        ann: dict[tuple[int, int], tuple[AnnotationKind, str]] = {
            (0, 4): (AnnotationKind.RETURN, "None"),
        }
        result = apply_annotations(src, ann)
        assert "-> None" in result


class TestAddTypingImports:
    def test_inserts_import_when_missing(self) -> None:
        src = "def f() -> Any:\n    ...\n"
        result = _add_typing_imports(src, ["Any"])
        assert "from typing import Any" in result

    def test_merges_into_existing(self) -> None:
        src = "from typing import List\n\ndef f() -> Any:\n    ...\n"
        result = _add_typing_imports(src, ["Any"])
        assert "from typing import" in result
        assert "Any" in result

    def test_no_duplicate_import(self) -> None:
        src = "from typing import Any\n\ndef f() -> Any:\n    ...\n"
        result = _add_typing_imports(src, ["Any"])
        # Verify that "Any" still appears in the import but wasn't duplicated
        import_lines = [
            line for line in result.splitlines() if "from typing import" in line
        ]
        assert len(import_lines) == 1
        assert "Any" in import_lines[0]

    def test_inserts_after_future_import(self) -> None:
        src = "from __future__ import annotations\n\ndef f():\n    ...\n"
        result = _add_typing_imports(src, ["Any"])
        lines = result.splitlines()
        future_idx = next(
            i for i, line in enumerate(lines) if "__future__" in line
        )
        typing_idx = next(
            i for i, line in enumerate(lines) if "from typing import" in line
        )
        assert typing_idx > future_idx
