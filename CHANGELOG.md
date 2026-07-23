# Changelog

## Unreleased
- **Cookbook (`EXAMPLES.md`).** A gallery of 25+ verified copy-paste recipes
  across names, numbers/IDs, case & slugs, web & files, CSV/columns, dates, and
  templating — each showing the program exform inferred. Every command is run
  and diffed against its documented output before release. Linked from the README.
- **Slugify & whitespace reshaping (variable word count).** exform can now learn
  `-e 'Hello World => hello-world'` and infers `line.slug`: lowercase, runs of
  punctuation/whitespace collapse to a single `-`, trimmed. It generalises to
  lines with any number of words (something a fixed `field(...)` + glue program
  cannot do) from a single example. Also `.kebab` (whitespace -> `-`, case
  preserved) and `.snake` (whitespace -> `_`). As a bonus, common phone-style
  reformatting like `(555) 123-4567 => 555-123-4567` now generalises via
  `line.slug` instead of memorising a prefix.
- **Zero-padding to a fixed width.** exform can learn `-e '7 => 007'` and infers
  `line.zpad3`, padding integers to a fixed width and generalising (longer
  numbers pass through untouched). It composes with extraction, so
  `img_7.png => img_0007.png` renames a whole sequence to `img_0123.png`. A
  single example is enough and nothing is memorised.
- **Numeric thousands grouping.** exform can now learn spreadsheet-style number
  formatting: `-e '1234567 => 1,234,567'` infers `line.group,` and generalises
  to every line (a single example is enough — nothing is memorised). The output
  separator is taken from the example, so `1000000 => 1 000 000` groups with
  spaces (SI) and periods work too; grouping also composes with extraction, e.g.
  a number buried in text (`Total: 1234567 units => 1,234,567`).
- **`--fill` (Flash Fill mode).** Take a two-column file (`input<TAB>output`),
  fill in the output for the first row or two by hand, leave the rest blank, and
  exform completes the table — the spreadsheet Flash Fill workflow, on the
  command line. Filled rows become the examples; blank rows get completed; the
  finished table is printed in order. Column separator configurable via
  `--col-sep` (default TAB). Same generalisation guarantees and ambiguity
  warnings as `-e`.
- **Docs: animated terminal demo** (`assets/demo.svg`, self-contained, no deps,
  regenerable via `assets/make_demo.py`) added to the top of the README. Falls
  back to a fully-readable static frame on renderers that don't run SMIL.
- **Warn when the inferred program hardcodes data copied from the input.**
  A single, ambiguous example (e.g. `-e '(555) 123-4567 => 555-123-4567'`) can
  only be "solved" by memorising the `555` prefix, which then produces wrong
  output on the next line. exform now detects data-bearing literals that appear
  verbatim in an example's input and warns (on stderr) that the example is
  ambiguous and another varied example is needed. Pure glue (`, `, `-`, `/`) is
  never flagged. Silence with `-q`/`--quiet`.
- **Add `@` and `=` as field delimiters.** Extracting the username from an
  email (`jane.doe@corp.com => jane.doe`) or the value from a `key=value` pair
  now works directly via `field(@,0)` / `field(=,1)` instead of overfitting a
  fixed-length slice. These are among the most common first tasks a user tries.
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
