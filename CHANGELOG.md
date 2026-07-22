# Changelog

## Unreleased
- Warn (on stderr) when the inferred program is a constant that ignores the
  input — the classic symptom of too few / non-varied examples. Add `-q`/
  `--quiet` to silence non-fatal warnings.

## 0.1.0
- First public release.
- Deterministic programming-by-example engine (uniform-cost search over an
  inspectable transformation DSL).
- CLI: `-e/--example`, `-E/--examples-file`, `--explain`, `--dry-run`,
  `--sep`, `--on-error`, `--no-slices`.
- Field, regex, whole-line, and slice extractors with case transforms and
  literal glue. Zero runtime dependencies.
