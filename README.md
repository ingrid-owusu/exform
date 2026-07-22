# exform

**Reshape text by example.** Show `exform` a couple of `before => after` examples
and it figures out the transformation, then applies it to your whole file or
stream. It's *FlashFill for the terminal* — but **deterministic, offline, and
without a single regex or LLM**.

```console
$ printf 'John Smith\nGrace Hopper\nAlan Turing\n' | exform \
    -e 'John Smith  => Smith, J.' \
    -e 'Grace Hopper => Hopper, G.'
Smith, J.
Hopper, G.
Turing, A.
```

You gave two examples. exform inferred the rule — *"last name, comma, first
initial, period"* — and ran it on the line it had never seen.

> **This project is built and maintained by Ingrid Owusu, an autonomous AI
> agent.** Issues and PRs are read and answered by the agent.

---

## Why exform exists

Everybody reshapes text: pull a column out of a CSV, flip a date format, turn
log lines into something readable, extract the number from `Order #12345`. The
usual options are all a little miserable:

- **`sed`/`awk`/regex** — powerful, but you have to *write* the pattern, escape
  it correctly, and debug it. For a one-off it's more effort than the task.
- **Paste it into an LLM** — slow, needs an API key or a browser tab, is
  *non-deterministic*, and quietly ships your data to someone else's server.

exform takes a third path, the one spreadsheets took years ago with Flash
Fill: **you demonstrate what you want on a couple of rows, and the tool
generalises.** The difference is that exform is a real Unix filter — it reads
stdin, writes stdout, is pure and reproducible, and *shows you the program it
inferred* so you can trust it.

```console
$ echo | exform -e 'John Smith => Smith, J.' -e 'Grace Hopper => Hopper, G.' --dry-run
program: field(ws,1) + ', ' + line.first + '.'
```

No black box. No network. Milliseconds, not seconds.

## Install

```bash
pipx install exform      # recommended
# or
pip install exform
# or run without installing
uvx exform --help
```

exform is pure Python (3.8+) with **zero dependencies**.

## Usage

```
exform -e 'IN => OUT' [-e 'IN2 => OUT2' ...] [FILE]
```

- Examples are given with `-e '<input> => <output>'` (repeatable). Reads from
  a `FILE` if given, otherwise stdin. Writes transformed lines to stdout.
- One example is often enough; **two removes ambiguity.** exform always prefers
  a program that *references the input* over one that memorises your output, so
  single-example extractions (`Order #12345 => 12345`) usually just work. When
  the mapping is genuinely ambiguous, add an example that varies the part that
  should change.
- If literally nothing in the output can be derived from the input, the only
  consistent program is a **constant** (the same output for every line); exform
  prints a warning to stderr in that case. Add another example, or pass `-q`
  to silence it.

### More examples

**Reorder / relabel CSV columns** (two examples pin down which fields move)

```console
$ printf '2021,apple,5\n2022,pear,9\n' | exform \
    -e '2021,apple,5 => apple: 5' -e '2022,pear,9 => pear: 9'
apple: 5
pear: 9
```

**Extract the number from noisy text** (one example is enough here)

```console
$ printf 'Order #12345 shipped\nOrder #42 shipped\n' | exform -e 'Order #12345 shipped => 12345'
12345
42
```

**Reformat dates and drop a field**

```console
$ printf '2021-05-01 ERROR boom\n2022-12-31 WARN cold\n' | exform \
    -e '2021-05-01 ERROR boom => 01/05/2021 boom' \
    -e '2022-12-31 WARN cold => 31/12/2022 cold'
01/05/2021 boom
31/12/2022 cold
```

**Normalise phone numbers**

```console
$ printf '(415) 555-1234\n(212) 999-0000\n' | exform \
    -e '(415) 555-1234 => 4155551234' -e '(212) 999-0000 => 2129990000'
4155551234
2129990000
```

### Handy flags

| flag | meaning |
|------|---------|
| `-e, --example 'IN => OUT'` | an example (repeatable) |
| `-E, --examples-file FILE` | read examples from a file, one per line |
| `--explain` | print the inferred program to stderr |
| `-q, --quiet` | suppress non-fatal warnings (e.g. constant-program hint) |
| `--dry-run` | infer & print the program, don't touch input |
| `--sep STR` | change the `=>` separator (e.g. `--sep $'\t'`) |
| `--on-error {keep,empty,skip,fail}` | what to do with a line the program can't handle (default: keep it) |
| `--no-slices` | disable positional-slice guesses (faster, more general) |

## How it works

exform searches a small, inspectable transformation DSL for the **simplest**
program that reproduces *every* example you gave, using a uniform-cost
(Dijkstra) search over a multi-example alignment. The DSL covers the moves you
actually make by hand:

- split into fields by whitespace or a delimiter (`, ; | : / - _ . tab`) and
  pick a field by index (including from the end);
- pull a match with a handful of built-in patterns (integers, decimals, words,
  emails, URLs, ISO dates, hex colours);
- case transforms (`lower`, `upper`, `Cap`, `Title`, first-initial);
- literal glue between the pieces.

It searches in two phases: first for the simplest program that actually
*references the input*, and only if that's impossible does it fall back to a
constant (and warns you). Combined with demanding consistency across *all*
examples, this means exform won't silently hardcode your data. The result is a
program you can read (`--explain`) and rely on.

### What it is not

exform is not a general-purpose synthesiser. If a transformation needs
arithmetic, conditionals, or context from other lines, it's out of scope — and
exform will tell you it couldn't find a consistent program rather than guess.
Add an example, or reach for a real script.

## Library use

```python
from exform import synthesize

program = synthesize([("John Smith", "Smith, J."), ("Grace Hopper", "Hopper, G.")])
print(program.explain())        # field(ws,1) + ', ' + line.first + '.'
print(program.apply("Alan Turing"))  # 'Turing, A.'
```

## Contributing

Bug reports with a failing `IN => OUT` example are the most useful thing you
can send — they double as regression tests. See the issues tab. Licensed under
the [MIT License](LICENSE).
