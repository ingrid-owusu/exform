"""exform command-line interface.

Reshape text by example:

    $ printf 'John Smith\\nJane Doe\\n' | exform -e 'John Smith => Smith, J.'

exform infers the transformation from the example(s) and applies it to every
input line.
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from . import __version__
from .synth import Program, SynthesisError, synthesize

_ARROW = "=>"


def _parse_example(raw: str, sep: str) -> tuple[str, str]:
    if sep not in raw:
        raise SystemExit(
            f"exform: example {raw!r} does not contain the separator {sep!r}.\n"
            f"        write it as  INPUT {sep} OUTPUT"
        )
    left, right = raw.split(sep, 1)
    return left.strip(), right.strip()


def _read_examples_file(path: str, sep: str) -> list[tuple[str, str]]:
    exs = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            exs.append(_parse_example(line, sep))
    return exs


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="exform",
        description="Reshape text by example. Give a couple of before=>after "
        "examples; exform infers the transformation and applies it to every "
        "line. Deterministic, offline, no regex, no LLM.",
        epilog="examples:\n"
        "  exform -e 'John Smith => Smith, J.' names.txt\n"
        "  cat log.txt | exform -e '2021-05-01 ERROR boom => [ERROR] boom'\n"
        "  exform -E pairs.tsv --sep $'\\t' data.txt --explain\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "-e",
        "--example",
        action="append",
        default=[],
        metavar="'IN => OUT'",
        help="an input=>output example (repeatable)",
    )
    p.add_argument(
        "-E",
        "--examples-file",
        metavar="FILE",
        help="read examples from FILE (one 'IN => OUT' per line)",
    )
    p.add_argument(
        "file",
        nargs="?",
        help="input file to transform (default: stdin)",
    )
    p.add_argument(
        "--sep",
        default=_ARROW,
        help=f"separator between input and output in examples (default: {_ARROW!r})",
    )
    p.add_argument(
        "--fill",
        action="store_true",
        help="FlashFill mode: read a 2-column file (input<TAB>output). Rows "
        "where you filled in the output become examples; rows with a blank "
        "output are completed. Prints the finished table.",
    )
    p.add_argument(
        "--col-sep",
        default="\t",
        metavar="SEP",
        help="column separator for --fill mode (default: TAB)",
    )
    p.add_argument(
        "--explain",
        action="store_true",
        help="print the inferred program to stderr",
    )
    p.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="suppress non-fatal warnings (e.g. constant-program hint)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="only infer and print the program; do not read/transform input",
    )
    p.add_argument(
        "--in-line",
        "--inline",
        dest="in_line",
        action="store_true",
        help="sed-by-example: change only the substring that differs between "
        "your example's input and output, leaving the rest of each line intact "
        "(e.g. reformat the date inside a log line and nothing else)",
    )
    p.add_argument(
        "--all",
        action="store_true",
        help="in --in-line mode, rewrite every match on a line (default: only "
        "the first)",
    )
    p.add_argument(
        "--no-slices",
        action="store_true",
        help="disable positional slice atoms (faster, more general)",
    )
    p.add_argument(
        "--on-error",
        choices=["keep", "empty", "skip", "fail"],
        default="keep",
        help="what to do with a line the program cannot transform "
        "(default: keep the original line)",
    )
    p.add_argument("--version", action="version", version=f"exform {__version__}")
    return p


def _iter_input(path: Optional[str]):
    if path is None or path == "-":
        for line in sys.stdin:
            yield line.rstrip("\n")
    else:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                yield line.rstrip("\n")


def _run_fill(args) -> int:
    """FlashFill mode.

    Read a 2-column table (input<COLSEP>output). Rows whose output cell is
    non-empty are treated as examples; rows with a blank/absent output cell are
    completed by the inferred program. The full finished table is written to
    stdout in the same order.
    """
    colsep = args.col_sep
    rows: list[tuple[str, Optional[str]]] = []
    examples: list[tuple[str, str]] = []
    for line in _iter_input(args.file):
        if colsep in line:
            inp, out = line.split(colsep, 1)
        else:
            inp, out = line, ""
        out_stripped = out.strip()
        if out_stripped:
            examples.append((inp, out_stripped))
            rows.append((inp, out_stripped))
        else:
            rows.append((inp, None))

    if not examples:
        sys.stderr.write(
            "exform: --fill needs at least one completed row "
            f"(input{colsep!r}output). Fill in the output for the first row "
            "or two, then re-run.\n"
        )
        return 2

    n_blank = sum(1 for _, o in rows if o is None)
    if n_blank == 0:
        # Nothing to do; just echo back. Still infer so --explain works.
        pass

    try:
        program: Program = synthesize(examples, use_slices=not args.no_slices)
    except SynthesisError as exc:
        sys.stderr.write(f"exform: {exc}\n")
        sys.stderr.write(
            "        try filling in another representative row.\n"
        )
        return 1

    if args.explain:
        sys.stderr.write(f"program: {program.explain()}\n")

    if not args.quiet:
        memo = program.memorized_literals(i for i, _ in examples)
        if program.is_constant():
            sys.stderr.write(
                "exform: warning: the inferred rule is constant (every row "
                "would get the same output). Fill in another, more varied "
                "row.\n"
            )
        elif memo:
            shown = ", ".join(repr(m) for m in memo[:3])
            sys.stderr.write(
                "exform: warning: the inferred rule hardcodes " + shown + " "
                "copied from a completed row, so other rows will likely be "
                "wrong. Fill in another varied row so exform can generalise.\n"
            )

    out = sys.stdout
    for inp, given in rows:
        if given is not None:
            out.write(inp + colsep + given + "\n")
            continue
        result = program.apply(inp)
        if result is None:
            if args.on_error == "keep":
                result = ""
            elif args.on_error == "empty":
                result = ""
            elif args.on_error == "skip":
                out.write(inp + "\n")
                continue
            else:  # fail
                sys.stderr.write(
                    f"exform: could not fill row: {inp!r}\n"
                )
                return 1
        out.write(inp + colsep + result + "\n")
    return 0


def _run_inline(args, examples) -> int:
    from .inline import InlineProgram, infer_inline, memorized_inner_literals

    try:
        program: InlineProgram = infer_inline(
            examples, use_slices=not args.no_slices, replace_all=args.all
        )
    except SynthesisError as exc:
        sys.stderr.write(f"exform: {exc}\n")
        return 1

    if args.explain or args.dry_run:
        sys.stderr.write(f"program: {program.explain()}\n")

    if not args.quiet:
        memo = memorized_inner_literals(program, (i for i, _ in examples))
        if memo:
            shown = ", ".join(repr(m) for m in memo[:3])
            sys.stderr.write(
                "exform: warning: the inferred in-line rule hardcodes "
                + shown + " copied from your example, so it will likely be "
                "wrong on other lines. Add another varied example so exform "
                "can generalise (pass --quiet to silence).\n"
            )

    if args.dry_run:
        return 0

    out = sys.stdout
    for line in _iter_input(args.file):
        result = program.apply(line)
        if result is None:
            # No match on this line -> apply the --on-error policy. For in-line
            # mode "no match" is the common, benign case, so 'keep' is sensible.
            if args.on_error in ("keep",):
                result = line
            elif args.on_error == "empty":
                result = ""
            elif args.on_error == "skip":
                continue
            else:  # fail
                sys.stderr.write(
                    f"exform: no match to transform on line: {line!r}\n"
                )
                return 1
        out.write(result + "\n")
    return 0


def run(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.fill:
        return _run_fill(args)

    examples: list[tuple[str, str]] = []
    if args.examples_file:
        examples.extend(_read_examples_file(args.examples_file, args.sep))
    for raw in args.example:
        examples.append(_parse_example(raw, args.sep))

    if not examples:
        sys.stderr.write("exform: no examples given (use -e 'IN => OUT')\n")
        return 2

    if args.in_line:
        return _run_inline(args, examples)

    try:
        program: Program = synthesize(examples, use_slices=not args.no_slices)
    except SynthesisError as exc:
        sys.stderr.write(f"exform: {exc}\n")
        sys.stderr.write(
            "        try adding another example, or a more representative one.\n"
        )
        return 1

    if args.explain or args.dry_run:
        sys.stderr.write(f"program: {program.explain()}\n")

    if program.is_constant() and not args.quiet:
        sys.stderr.write(
            "exform: warning: the inferred program is a constant and ignores "
            "the input\n"
            "        (every line would become the same text). This usually "
            "means too few\n"
            "        or non-varied examples. Add another example, e.g. "
            "-e 'OTHER_IN => OTHER_OUT',\n"
            "        or pass --quiet to silence this warning.\n"
        )
    else:
        memo = program.memorized_literals(i for i, _ in examples)
        if memo and not args.quiet:
            shown = ", ".join(repr(m) for m in memo[:3])
            sys.stderr.write(
                "exform: warning: the inferred program hardcodes " + shown + " "
                "copied from your\n"
                "        example's input, so it will likely be wrong on other "
                "lines. This means the\n"
                "        example is ambiguous. Add another varied example, e.g. "
                "-e 'OTHER_IN => OTHER_OUT',\n"
                "        so exform can generalise (pass --quiet to silence).\n"
            )

    if args.dry_run:
        return 0

    out = sys.stdout
    exit_code = 0
    for line in _iter_input(args.file):
        result = program.apply(line)
        if result is None:
            if args.on_error == "keep":
                result = line
            elif args.on_error == "empty":
                result = ""
            elif args.on_error == "skip":
                continue
            else:  # fail
                sys.stderr.write(
                    f"exform: could not transform line: {line!r}\n"
                )
                return 1
        out.write(result + "\n")
    return exit_code


def main() -> None:  # console_scripts entry point
    try:
        raise SystemExit(run())
    except BrokenPipeError:
        pass


if __name__ == "__main__":
    main()
