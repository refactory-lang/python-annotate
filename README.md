<p align="center">
  <a href="https://github.com/refactory-lang"><img src="https://raw.githubusercontent.com/refactory-lang/.github/main/assets/refactory-logo.svg" alt="Refactory" width="300"></a>
</p>

# refactory-annotate

Type inference CLI for the Refactory transformation pipeline.

## Purpose

**Step 2 (Type Infer)** of the Refactory pipeline. In relaxed mode, developers write idiomatic Python without full type annotations. `refactory-annotate` ensures all code has PEP 484 annotations before validation:

1. **pyright** infers types from the source code (whole-program data flow analysis)
2. **refactory-annotate** inserts explicit PEP 484 annotations based on pyright's inference
3. **mypy --strict** verifies the annotations are correct and complete

## Key Design Decisions

- **Not a codemod** — type inference requires semantic analysis (whole-program data flow), not pattern matching
- **Skipped in strict mode** — code is already fully annotated
- **pyright for inference** — better inference coverage than mypy
- **mypy for verification** — `mypy --strict` is the profile contract

## Pipeline Position

```
Step 1: Normalize  -->  Step 2: Type Infer  -->  Step 3: Validate  -->  ...
(refactory-format)     (refactory-annotate)     (refactory-check)
```

## Installation

```bash
pip install refactory-annotate
```

## Usage

```bash
refactory-annotate <source-files-or-directory>
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

- Master spec v0.3 section 2.2 Pipeline Model, Step 2
- Master spec v0.3 section 2.7 Token Economics
