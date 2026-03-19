"""Annotation pipeline: pyright → libcst insert → mypy verify."""

from __future__ import annotations

import sys
from pathlib import Path

from refactory_annotate.cst_annotator import apply_annotations
from refactory_annotate.location_finder import (
    AnnotationLocation,
    find_unannotated_locations,
)
from refactory_annotate.models import (
    AnnotationKind,
    AnnotationPlan,
    AnnotationReport,
    InferredType,
    UnannotatableLocation,
)
from refactory_annotate.mypy_verifier import verify_with_mypy
from refactory_annotate.pyright_lsp import (
    PyrightClient,
    parse_hover_param_type,
    parse_hover_return_type,
)


def annotate_paths(
    paths: list[Path],
    *,
    dry_run: bool = False,
    verify: bool = True,
    verbose: bool = False,
) -> AnnotationReport:
    """Annotate all Python files under *paths* and return a report.

    Pipeline for each file:

    1. Parse the CST to find unannotated parameters and return types.
    2. Query pyright (via LSP hover) for the inferred types at those
       locations.
    3. Insert annotations using libcst (preserving formatting).
    4. Optionally write the modified file back to disk.
    5. Optionally verify with ``mypy --strict``.

    Args:
        paths: Files or directories to annotate.
        dry_run: If ``True``, print what would be changed but do not
            write files.
        verify: If ``True``, run ``mypy --strict`` on the output and
            report errors.
        verbose: Enable verbose logging.

    Returns:
        An :class:`AnnotationReport` summarising the run.
    """
    report = AnnotationReport()

    # Collect all .py files
    py_files = _collect_py_files(paths)
    if not py_files:
        if verbose:
            _log("No Python files found.")
        return report

    if verbose:
        _log(f"Found {len(py_files)} Python file(s).")

    # ------------------------------------------------------------------
    # Phase 1 — find unannotated locations (libcst)
    # ------------------------------------------------------------------
    files_to_query: dict[Path, str] = {}
    for path in py_files:
        source = path.read_text(encoding="utf-8")
        locs = find_unannotated_locations(source, path)
        if locs:
            files_to_query[path] = source
        else:
            report.skipped_already_annotated += 1
            if verbose:
                _log(f"  {path}: fully annotated, skipping.")

    if not files_to_query:
        if verbose:
            _log("All files are already fully annotated.")
        if verify:
            _run_verification(py_files, report, verbose)
        return report

    # ------------------------------------------------------------------
    # Phase 2 — query pyright LSP for inferred types
    # ------------------------------------------------------------------
    plan = AnnotationPlan()

    root = _common_root(list(files_to_query.keys()))
    with PyrightClient(root=root) as client:
        # Open all files first so pyright can do cross-module analysis.
        for path in files_to_query:
            if verbose:
                _log(f"  Opening {path} for analysis …")
            client.open_file(path, wait_for_analysis=True)

        # Now query hover for each unannotated location.
        for path, source in files_to_query.items():
            locs = find_unannotated_locations(source, path)
            if verbose:
                _log(f"  Querying {len(locs)} location(s) in {path} …")
            _query_locations(client, path, locs, plan, report, verbose)

    report.files_processed = len(files_to_query)

    if plan.is_empty() and not report.unannotatable:
        if verbose:
            _log("No new annotations to insert.")
        if verify:
            _run_verification(py_files, report, verbose)
        return report

    # ------------------------------------------------------------------
    # Phase 3 — insert annotations (libcst)
    # ------------------------------------------------------------------
    for path, source in files_to_query.items():
        inferred_list = plan.by_file.get(path, [])
        if not inferred_list:
            continue

        ann_map: dict[tuple[int, int], tuple[AnnotationKind, str]] = {
            (it.line, it.column): (it.kind, it.type_string)
            for it in inferred_list
        }

        new_source = apply_annotations(source, ann_map)
        if new_source == source:
            if verbose:
                _log(f"  {path}: no changes (idempotent).")
            continue

        report.inserted += len(inferred_list)

        if dry_run:
            _print_diff(path, source, new_source)
        else:
            path.write_text(new_source, encoding="utf-8")
            if verbose:
                _log(f"  {path}: inserted {len(inferred_list)} annotation(s).")

    # ------------------------------------------------------------------
    # Phase 4 — verify with mypy --strict
    # ------------------------------------------------------------------
    if verify and not dry_run:
        _run_verification(py_files, report, verbose)

    return report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _query_locations(
    client: PyrightClient,
    path: Path,
    locs: list[AnnotationLocation],
    plan: AnnotationPlan,
    report: AnnotationReport,
    verbose: bool,
) -> None:
    """Hover each location in *locs* and populate *plan* or *report*."""
    for loc in locs:
        hover_text = client.hover(path, loc.line, loc.column)

        if hover_text is None:
            report.unannotatable.append(
                UnannotatableLocation(
                    file=loc.file,
                    line=loc.line,
                    column=loc.column,
                    name=loc.name,
                    kind=loc.kind,
                    reason="pyright returned no hover information",
                )
            )
            continue

        if loc.kind == AnnotationKind.RETURN:
            type_str = parse_hover_return_type(hover_text)
        else:
            type_str = parse_hover_param_type(hover_text)

        if type_str is None:
            report.unannotatable.append(
                UnannotatableLocation(
                    file=loc.file,
                    line=loc.line,
                    column=loc.column,
                    name=loc.name,
                    kind=loc.kind,
                    reason=f"type is not inferrable (hover: {hover_text!r})",
                )
            )
            if verbose:
                _log(
                    f"    ⚠ {loc.file.name}:{loc.line + 1} "
                    f"{loc.kind.value} '{loc.name}': not inferrable"
                )
            continue

        plan.add(
            InferredType(
                file=path,
                line=loc.line,
                column=loc.column,
                kind=loc.kind,
                name=loc.name,
                type_string=type_str,
            )
        )
        if verbose:
            _log(
                f"    ✓ {loc.file.name}:{loc.line + 1} "
                f"{loc.kind.value} '{loc.name}': {type_str}"
            )


def _run_verification(
    py_files: list[Path], report: AnnotationReport, verbose: bool
) -> None:
    """Run mypy --strict and populate *report.mypy_errors*."""
    if verbose:
        _log("Running mypy --strict …")
    success, errors = verify_with_mypy(py_files)
    report.mypy_errors = errors
    if verbose:
        if success:
            _log("  mypy --strict: passed ✓")
        else:
            _log(f"  mypy --strict: {len(errors)} error(s)")
            for err in errors[:10]:
                _log(f"    {err}")
            if len(errors) > 10:
                _log(f"    … and {len(errors) - 10} more")


def _collect_py_files(paths: list[Path]) -> list[Path]:
    """Expand directories to .py files; return all .py files."""
    result: list[Path] = []
    for p in paths:
        if p.is_dir():
            result.extend(sorted(p.rglob("*.py")))
        elif p.is_file() and p.suffix == ".py":
            result.append(p)
    return result


def _common_root(paths: list[Path]) -> Path:
    """Return the common parent directory of *paths*."""
    if not paths:
        return Path.cwd()
    resolved = [p.resolve() for p in paths]
    try:
        parts_list = [list(p.parts) for p in resolved]
        common: list[str] = []
        for parts in zip(*parts_list, strict=False):
            if len(set(parts)) == 1:
                common.append(parts[0])
            else:
                break
        if common:
            return Path(*common)
    except Exception:
        pass
    return resolved[0].parent


def _print_diff(path: Path, old: str, new: str) -> None:
    """Print a simple unified-style diff for dry-run mode."""
    import difflib

    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    )
    sys.stdout.writelines(diff)


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)
