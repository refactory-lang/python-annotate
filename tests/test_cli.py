"""Tests for the refactory-annotate CLI."""

from __future__ import annotations

from refactory_annotate.cli import parse_args


def test_parse_args_basic() -> None:
    """Test basic argument parsing."""
    args = parse_args(["src/"])
    assert args.paths == ["src/"]
    assert args.verify is True
    assert args.dry_run is False


def test_parse_args_no_verify() -> None:
    """Test --no-verify flag."""
    args = parse_args(["--no-verify", "src/"])
    assert args.verify is False


def test_parse_args_dry_run() -> None:
    """Test --dry-run flag."""
    args = parse_args(["--dry-run", "src/"])
    assert args.dry_run is True


def test_parse_args_multiple_paths() -> None:
    """Test multiple paths."""
    args = parse_args(["file1.py", "file2.py", "src/"])
    assert args.paths == ["file1.py", "file2.py", "src/"]
