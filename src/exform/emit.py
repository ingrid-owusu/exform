"""Emit a standalone, dependency-free Python script that reproduces a
synthesized transform.

`exform --emit python` turns exform from a *runtime* dependency into a code
generator: infer the transformation from your examples once, then get a plain
`python3` script you can commit to your repo and run anywhere — no exform, no
pip install, stdlib only. The emitted script reads lines on stdin and writes
the transformed lines on stdout, exactly like `exform` itself.

The generated code is deliberately human-readable (it uses `.lower()`,
`_field(...)`, etc. rather than an opaque interpreter) so a reviewer can see
what it does. Before returning, we *execute* the generated script against the
original examples and refuse to emit anything that does not reproduce them —
the same correctness gate the synthesizer applies, so a script is never shipped
that silently disagrees with the examples it was derived from.
"""

from __future__ import annotations

import inspect
from typing import Iterable

from . import synth
from .synth import Program


class EmitError(Exception):
    """Raised when a faithful standalone script cannot be produced."""


# Transform name -> (python expression template, set of helper names it needs).
# `{x}` is substituted with the inner expression. Helpers are pulled verbatim
# from synth.py so the emitted code cannot drift from the engine.
def _t_expr(t: str, x: str) -> tuple[str, set[str]]:
    if t == "" or t is None:
        return x, set()
    simple = {
        "lower": (f"({x}).lower()", set()),
        "upper": (f"({x}).upper()", set()),
        "strip": (f"({x}).strip()", set()),
        "first": (f"({x})[:1]", set()),
        "First": (f"({x})[:1].upper()", set()),
        "first_": (f"({x})[:1].lower()", set()),
        "cap": (f"_cap({x})", {"_cap"}),
        "title": (f"_title({x})", {"_title"}),
        "slug": (f"_slug({x})", {"_slug"}),
        "kebab": (f'_ws_to({x}, "-")', {"_ws_to"}),
        "snake": (f'_ws_to({x}, "_")', {"_ws_to"}),
        "acronym": (f'_acronym({x}, "")', {"_acronym"}),
        "acronym.": (f'_acronym({x}, ".")', {"_acronym"}),
        "camel": (f"_camel({x}, False)", {"_camel", "_words"}),
        "pascal": (f"_camel({x}, True)", {"_camel", "_words"}),
        "group,": (f'_group({x}, ",")', {"_group"}),
        "group_": (f'_group({x}, " ")', {"_group"}),
        "group.": (f'_group({x}, ".")', {"_group"}),
    }
    if t in simple:
        return simple[t]
    if t.startswith("zpad"):
        width = int(t[4:])
        return f"_zpad({x}, {width})", {"_zpad"}
    raise EmitError(f"cannot emit transform {t!r}")


# Names of module-level regex constants each helper depends on.
_HELPER_DEPS = {
    "_title": [],
    "_group": ["_NUMRE"],
    "_slug": ["_SLUG_RE"],
    "_ws_to": [],
    "_acronym": [],
    "_words": ["_WORD_SEP_RE", "_CAMEL_RE"],
    "_camel": [],
    "_zpad": ["_INTRE"],
}


def _atom_parts(meta: dict) -> tuple[str, str, set[str]]:
    """Return (inner_expr, transform_name, extra_helper_names).

    The inner expression may evaluate to None (e.g. an out-of-range field);
    the caller guards against that *before* applying the transform, mirroring
    the runtime atoms which bail out early on a missing piece.
    """
    op = meta.get("op")
    if op == "const":
        return repr(meta["text"]), "", set()
    if op == "whole":
        return "L", meta["t"], set()
    if op == "field":
        return f"_field(L, {meta['delim']!r}, {meta['idx']})", meta["t"], {"_field"}
    if op == "regex":
        return f"_nth(L, {meta['pattern']!r}, {meta['nth']})", meta["t"], {"_nth"}
    if op == "slice":
        b = meta["b"]
        return f"L[{meta['a']}:{'' if b is None else b}]", meta["t"], set()
    raise EmitError(f"cannot emit atom {op!r}")


# Small extra helpers not present verbatim in synth (thin wrappers).
_EXTRA_HELPERS = {
    "_cap": (
        "def _cap(s):\n"
        "    return s[:1].upper() + s[1:].lower() if s else s\n"
    ),
    "_field": (
        "def _field(line, delim, idx):\n"
        "    parts = line.split() if delim is None else line.split(delim)\n"
        "    if parts and -len(parts) <= idx < len(parts):\n"
        "        return parts[idx]\n"
        "    return None\n"
    ),
    "_nth": (
        "def _nth(line, pattern, n):\n"
        "    ms = re.findall(pattern, line)\n"
        "    if not ms or n >= len(ms) or n < -len(ms):\n"
        "        return None\n"
        "    m = ms[n]\n"
        "    return m[0] if isinstance(m, tuple) else m\n"
    ),
}


def _regex_const_src(name: str) -> str:
    rx = getattr(synth, name)
    return f"{name} = re.compile({rx.pattern!r})\n"


def _collect(needs: set[str]) -> str:
    """Emit source for every helper (and its regex/helper deps) in `needs`."""
    seen: set[str] = set()
    regex_consts: list[str] = []
    func_src: list[str] = []

    def add(name: str) -> None:
        if name in seen:
            return
        seen.add(name)
        if name in _EXTRA_HELPERS:
            func_src.append(_EXTRA_HELPERS[name])
            return
        # a synth helper function
        for dep in _HELPER_DEPS.get(name, []):
            if dep not in seen:
                seen.add(dep)
                regex_consts.append(_regex_const_src(dep))
        if name == "_camel":
            add("_words")
        func_src.append(inspect.getsource(getattr(synth, name)))

    for n in sorted(needs):
        add(n)

    out = []
    if regex_consts:
        out.append("".join(sorted(set(regex_consts))))
    out.append("\n\n".join(s.rstrip() + "\n" for s in func_src))
    return "\n".join(p for p in out if p.strip())


_HEADER = '''#!/usr/bin/env python3
"""Standalone text transform generated by exform (https://github.com/ingrid-owusu/exform).

Reads lines on stdin, writes the transformed lines on stdout. No dependencies
beyond the Python standard library. Lines the transform cannot handle are
passed through unchanged.

Inferred program: {program}
Generated from {n} example(s); do not edit by hand — re-run exform to regenerate.
"""
{imports}'''

_FOOTER = '''

def main():
    for line in sys.stdin:
        line = line.rstrip("\\n")
        out = transform(line)
        sys.stdout.write((line if out is None else out) + "\\n")


if __name__ == "__main__":
    main()
'''


def to_python(program: Program, examples: Iterable[tuple[str, str]]) -> str:
    """Render `program` as a standalone Python script and verify it against
    `examples` (a list of (input, output) pairs). Raises EmitError if a
    faithful script cannot be produced or it disagrees with an example."""
    needs: set[str] = set()
    body_lines = ["def transform(L):", "    parts = []"]
    for i, a in enumerate(program.atoms):
        if not a.meta:
            raise EmitError("program contains an atom with no emit metadata")
        inner, tname, extra = _atom_parts(a.meta)
        needs |= extra
        body_lines.append(f"    p{i} = {inner}")
        body_lines.append(f"    if p{i} is None:")
        body_lines.append("        return None")
        t_expr, t_needs = _t_expr(tname, f"p{i}")
        needs |= t_needs
        if t_expr != f"p{i}":
            body_lines.append(f"    p{i} = {t_expr}")
        body_lines.append(f"    parts.append(p{i})")
    body_lines.append('    return "".join(parts)')
    body = "\n".join(body_lines) + "\n"

    helpers = _collect(needs)

    examples = list(examples)
    # `from __future__ import annotations` keeps PEP 585 generics (list[str],
    # etc.) that appear in helpers lifted from the engine as strings, so the
    # emitted script runs on Python 3.8/3.9 where those annotations would
    # otherwise be evaluated at runtime and raise TypeError.
    imports = "from __future__ import annotations\n\nimport sys\n"
    if "re." in helpers:
        imports = "from __future__ import annotations\n\nimport re\nimport sys\n"
    header = _HEADER.format(
        program=program.explain(), n=len(examples), imports=imports
    )
    sections = [header.rstrip("\n")]
    if helpers.strip():
        sections.append(helpers.rstrip("\n"))
    sections.append(body.rstrip("\n"))
    sections.append(_FOOTER.strip("\n"))
    # Two blank lines between top-level sections (PEP 8 friendly, readable).
    script = "\n\n\n".join(sections) + "\n"

    _verify(script, examples)
    return script


def _verify(script: str, examples: Iterable[tuple[str, str]]) -> None:
    ns: dict = {}
    try:
        exec(compile(script, "<emitted>", "exec"), ns)
    except Exception as e:  # pragma: no cover - defensive
        raise EmitError(f"generated script failed to compile: {e}") from e
    fn = ns.get("transform")
    if fn is None:
        raise EmitError("generated script has no transform()")
    for inp, want in examples:
        try:
            got = fn(inp)
        except Exception as e:
            raise EmitError(f"generated script raised on {inp!r}: {e}") from e
        if got != want:
            raise EmitError(
                "generated script does not reproduce the examples "
                f"({inp!r} -> {got!r}, expected {want!r})"
            )
