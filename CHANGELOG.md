# Changelog

## Unreleased
- **Prefer programs that reference the input.** Synthesis now runs in two
  phases: it first searches for the simplest program that actually uses the
  input, and only falls back to a pure constant if none exists. This fixes the
  common single-example footgun where `-e 'Order #12345 shipped => 12345'`
  used to memorise `12345` for every line; it now correctly infers
  `match(int,0)` and generalises (`Order #42 shipped => 42`).
- Warn (on stderr) when the inferred program is a constant that ignores the
  input — now only when nothing in the output is derivable from the input. Add
  `-q`/`--quiet` to silence non-fatal warnings.

## 0.1.0
- First public release.
- Deterministic programming-by-example engine (uniform-cost search over an
  inspectable transformation DSL).
- CLI: `-e/--example`, `-E/--examples-file`, `--explain`, `--dry-run`,
  `--sep`, `--on-error`, `--no-slices`.
- Field, regex, whole-line, and slice extractors with case transforms and
  literal glue. Zero runtime dependencies.
