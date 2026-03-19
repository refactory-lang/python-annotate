"""CLI entry point for refactory-annotate."""

from __future__ import annotations

import argparse
import sys


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
    """Main entry point."""
    args = parse_args(argv)

    if args.verbose:
        print(f"refactory-annotate v{_get_version()}")
        print(f"Paths: {args.paths}")
        print(f"Verify: {args.verify}")
        print(f"Dry run: {args.dry_run}")

    # TODO: Implement the annotation pipeline:
    # 1. Run pyright to infer types
    # 2. Parse pyright output to extract type information
    # 3. Use libcst to insert PEP 484 annotations
    # 4. Verify with mypy --strict (unless --no-verify)

    print("refactory-annotate: not yet implemented")
    return 1


if __name__ == "__main__":
    sys.exit(main())
