<!-- codemod-skill-discovery:begin -->
## Codemod Skill Discovery
This section is managed by `codemod` CLI.

- Core skill: `.agents/skills/codemod/SKILL.md`
- Package skills: `.agents/skills/<package-skill>/SKILL.md`
- List installed Codemod skills: `npx codemod agent list --harness antigravity --format json`

<!-- codemod-skill-discovery:end -->

## Project: python-annotate

Type inference CLI for the Refactory transformation pipeline. Part of the [refactory-lang](https://github.com/refactory-lang) organization. Implements Step 2 (Type Infer) of the pipeline: pyright infers types, python-annotate inserts explicit PEP 484 annotations, mypy --strict verifies correctness. Not a codemod -- requires semantic analysis (whole-program data flow), not pattern matching.

### Architecture

- **CLI** (`src/refactory_annotate/cli.py`): Command-line entry point (`python-annotate` command)
- **Core** (`src/refactory_annotate/__init__.py`): Annotation insertion logic using `libcst`
- **Tests** (`tests/`): pytest test suite

### Pipeline Position

```
Step 1: Normalize  -->  Step 2: Type Infer      -->  Step 3: Validate  -->  ...
(refactory-format)     (python-annotate)          (refactory-check)
```

Skipped in strict mode (code already fully annotated).

### Running

```bash
# Install in development mode
pip install -e ".[dev]"

# Run the CLI
python-annotate <source-files-or-directory>

# Run tests
pytest

# Type check
mypy src/

# Lint
ruff check src/
```

### Key Files

| File | Purpose |
|------|---------|
| `src/refactory_annotate/cli.py` | CLI entry point (`python-annotate` command) |
| `src/refactory_annotate/__init__.py` | Core annotation insertion logic (libcst-based) |
| `pyproject.toml` | Package config (hatchling build, pyright + mypy + libcst deps) |
| `tests/` | pytest test suite |

### Conventions

- Uses `hatchling` as build backend
- Targets Python 3.11+
- Linting via `ruff` with strict annotation rules (`ANN` select)
- Type checking via `mypy --strict`
