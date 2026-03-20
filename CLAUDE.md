<!-- codemod-skill-discovery:begin -->
## Codemod Skill Discovery
This section is managed by `codemod` CLI.

- Core skill: `.agents/skills/codemod/SKILL.md`
- Package skills: `.agents/skills/<package-skill>/SKILL.md`
- List installed Codemod skills: `npx codemod agent list --harness antigravity --format json`

<!-- codemod-skill-discovery:end -->

## Project: python-annotate

Type inference CLI for the Refactory transformation pipeline. Part of the [refactory-lang](https://github.com/refactory-lang) organization. Implements Step 4 (Type Infer) of the pipeline — a **hybrid step**: JSSG transforms (via Codemod semantic analysis with ruff) handle symbol resolution, pyright handles type inference, python-annotate inserts explicit PEP 484 annotations using libcst, and mypy --strict verifies correctness.

### Architecture

- **CLI** (`src/refactory_annotate/cli.py`): Command-line entry point (`python-annotate` command)
- **Core** (`src/refactory_annotate/__init__.py`): Annotation insertion logic using `libcst`
- **Tests** (`tests/`): pytest test suite

### Pipeline Position (Hybrid Step)

```
                    Step 4: Type Infer (hybrid)
             ┌─────────────────────────────────────────┐
Step 3:      │  JSSG transforms   →  pyright oracle    │   Step 5:
Normalize ──►│  (symbol resolution)  (type inference)   │──► Validate
(refactory-  │           ↓                  ↓           │   (refactory-
 format)     │     site list    →   python-annotate     │    check)
             │                      (insert annotations)│
             └─────────────────────────────────────────┘
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


### Speckit Workflow

This repo uses [speckit](https://github.com/speckit) for specification-driven development.

- **Specs**: `specs/<NNN-feature-name>/spec.md` — feature specifications
- **Plans**: `specs/<NNN-feature-name>/plan.md` — implementation plans with tasks
- **Checklists**: `specs/<NNN-feature-name>/checklists/` — quality gates
- **Templates**: `.specify/templates/` — spec, plan, task, checklist templates
- **Extensions**: `.specify/extensions/` — verify, sync, review, workflow hooks

**Branch convention**: Feature branches are named `<NNN>-<short-name>` matching the spec directory (e.g., `001-milestone1-pipeline`).

**Issue → Spec flow**: Issues labeled `ready-to-spec` trigger the `ready-to-spec-notify` workflow, which assigns Copilot to run the speckit workflow and produce a spec + plan + tasks.
