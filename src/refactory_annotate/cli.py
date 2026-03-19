"""CLI entry point for refactory-annotate."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="refactory-annotate",
        description=(
            "Infer types via pyright and insert PEP 484 annotations "
            "into Python source files."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="Python source files or directories to annotate",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        default=True,
        help="Verify annotations with mypy --strict (default: True)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_false",
        dest="verify",
        help="Skip mypy --strict verification",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print annotations without modifying files",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_get_version()}",
    )
    return parser.parse_args(argv)


def _get_version() -> str:
    """Get the package version."""
    from refactory_annotate import __version__

    return __version__


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the python-annotate CLI.

    Returns:
        0 on success (annotations inserted and mypy passes, or no changes
        needed), 1 on any error (mypy failures, I/O errors, etc.).
    """
    args = parse_args(argv)

    if args.verbose:
        print(
            f"python-annotate v{_get_version()}",
            file=sys.stderr,
        )

    from refactory_annotate.pipeline import annotate_paths

    paths = [Path(p) for p in args.paths]

    # Validate paths exist
    bad = [p for p in paths if not p.exists()]
    if bad:
        for p in bad:
            print(f"error: path not found: {p}", file=sys.stderr)
        return 1

    report = annotate_paths(
        paths,
        dry_run=args.dry_run,
        verify=args.verify,
        verbose=args.verbose,
    )

    # Summary output
    if not args.dry_run:
        inserted = report.inserted
        unannotatable = len(report.unannotatable)
        if inserted or unannotatable:
            print(
                f"Inserted {inserted} annotation(s); "
                f"{unannotatable} location(s) not inferrable."
            )
        else:
            print("No annotations needed — files already fully annotated.")

    if report.unannotatable:
        print(
            f"\nUnannotatable locations ({len(report.unannotatable)}):",
            file=sys.stderr,
        )
        for loc in report.unannotatable:
            print(
                f"  {loc.file}:{loc.line + 1}: "
                f"{loc.kind.value} '{loc.name}' — {loc.reason}",
                file=sys.stderr,
            )

    if report.mypy_errors:
        print(
            f"\nmypy --strict reported {len(report.mypy_errors)} error(s):",
            file=sys.stderr,
        )
        for err in report.mypy_errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
