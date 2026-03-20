<p align="center">
  <a href="https://github.com/refactory-lang"><img src="https://raw.githubusercontent.com/refactory-lang/.github/main/assets/refactory-logo.svg" alt="Refactory" width="300"></a>
</p>

# python-annotate

Type inference CLI for the Refactory transformation pipeline.

## Purpose

**Step 4 (Type Infer)** of the Refactory pipeline — a **hybrid step**. In relaxed mode, developers write idiomatic Python without full type annotations. Type Infer ensures all code has PEP 484 annotations before validation:

1. **JSSG transforms** (via Codemod semantic analysis with ruff) handle **symbol resolution**: identifying unannotated sites, tracing imports, finding usages
2. **pyright** (external oracle) handles **type inference**: "what type should this annotation be?"
3. **python-annotate** (this tool) handles **annotation insertion** using libcst
4. **mypy --strict** handles **verification**

## Key Design Decisions

- **Hybrid step** — JSSG handles symbol resolution (identifying unannotated sites via Codemod semantic analysis with ruff), pyright handles type inference, this tool handles annotation insertion
- **Skipped in strict mode** — code is already fully annotated
- **pyright for inference** — better inference coverage than mypy
- **mypy for verification** — `mypy --strict` is the profile contract

## Pipeline Position

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

## Installation

```bash
pip install python-annotate
```

## Usage

```bash
python-annotate <source-files-or-directory>
```

## Development

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Type check
mypy src/
```

## References

- Master spec v0.3.1 section 2.2 Pipeline Model, Step 4 (Type Infer — hybrid step)
- Master spec v0.3.1 section 2.6 Token Economics
