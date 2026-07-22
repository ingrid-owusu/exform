"""Deterministic program synthesis: infer a text transformation from
input -> output examples, then apply it to new lines.

The approach is a small version of programming-by-example (a la spreadsheet
"flash fill"), done with an explicit, inspectable DSL and a uniform-cost
search that finds the *simplest* program consistent with every example.

No LLM, no network, stdlib only.
"""

from __future__ import annotations

import heapq
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

# ---------------------------------------------------------------------------
# Transforms applied to an extracted piece of text.
# ---------------------------------------------------------------------------


def _title(s: str) -> str:
    # Word-aware title-casing that does not mangle apostrophes the way
    # str.title() does ("O'Brien" stays "O'Brien").
    return re.sub(r"[A-Za-z]+", lambda m: m.group(0).capitalize(), s)


TRANSFORMS: dict[str, Callable[[str], str]] = {
    "": lambda s: s,
    "lower": str.lower,
    "upper": str.upper,
    "cap": lambda s: s[:1].upper() + s[1:].lower() if s else s,
    "title": _title,
    "strip": str.strip,
    "first": lambda s: s[:1],
    "First": lambda s: s[:1].upper(),
}

# Cost added for using a transform (identity is free, exotic ones cost more).
_TRANSFORM_COST = {
    "": 0.0,
    "strip": 0.5,
    "lower": 1.0,
    "upper": 1.0,
    "cap": 1.5,
    "title": 1.5,
    "first": 1.5,
    "First": 2.0,
}


# ---------------------------------------------------------------------------
# Delimiters used for field splitting.  None means "any run of whitespace".
# ---------------------------------------------------------------------------

_DELIMS: list[tuple[Optional[str], str, float]] = [
    (None, "ws", 0.0),
    ("\t", "tab", 0.5),
    (",", ",", 1.0),
    (";", ";", 1.5),
    ("|", "|", 1.5),
    (":", ":", 1.5),
    ("/", "/", 1.5),
    ("-", "-", 2.0),
    (".", ".", 2.0),
    ("_", "_", 2.0),
]


def _split(line: str, delim: Optional[str]) -> list[str]:
    if delim is None:
        return line.split()
    return line.split(delim)


# Regex extractors: (pattern, label, cost)
_REGEXES: list[tuple[str, str, float]] = [
    (r"\d+", "int", 2.0),
    (r"-?\d+(?:\.\d+)?", "num", 2.5),
    (r"[A-Za-z]+", "alpha", 2.5),
    (r"\w+", "word", 3.0),
    (r"[\w.+-]+@[\w.-]+", "email", 2.5),
    (r"\d{4}-\d{2}-\d{2}", "isodate", 2.0),
    (r"https?://\S+", "url", 2.5),
    (r"#([A-Fa-f0-9]{3,8})", "hex", 3.0),
]


# ---------------------------------------------------------------------------
# Atoms: pure functions line -> Optional[str], plus a human-readable name and
# a cost used to rank programs (lower = simpler = preferred).
# ---------------------------------------------------------------------------


@dataclass
class Atom:
    name: str
    cost: float
    fn: Callable[[str], Optional[str]]
    kind: str = "expr"  # "expr" or "const"

    def __call__(self, line: str) -> Optional[str]:
        return self.fn(line)


def _const_atom(text: str) -> Atom:
    return Atom(name=repr(text), cost=2.0 + 1.2 * len(text), fn=lambda _l, t=text: t, kind="const")


def _field_atom(delim, dlabel, dcost, idx, tname, tcost) -> Atom:
    tfn = TRANSFORMS[tname]

    def fn(line, d=delim, i=idx, t=tfn):
        parts = _split(line, d)
        if not parts:
            return None
        if -len(parts) <= i < len(parts):
            return t(parts[i])
        return None

    label = f"field({dlabel},{idx})"
    if tname:
        label += f".{tname}"
    cost = 6.0 + dcost + 0.6 * abs(idx) + tcost
    return Atom(name=label, cost=cost, fn=fn)


def _whole_atom(tname, tcost) -> Atom:
    tfn = TRANSFORMS[tname]
    label = "line" + (f".{tname}" if tname else "")
    return Atom(name=label, cost=4.0 + tcost, fn=lambda line, t=tfn: t(line))


def _regex_atom(pattern, plabel, pcost, nth, tname, tcost) -> Atom:
    rx = re.compile(pattern)
    tfn = TRANSFORMS[tname]

    def fn(line, r=rx, n=nth, t=tfn):
        ms = r.findall(line)
        if not ms:
            return None
        if n >= len(ms) or n < -len(ms):
            return None
        m = ms[n]
        if isinstance(m, tuple):  # capturing group present
            m = m[0]
        return t(m)

    label = f"match({plabel},{nth})"
    if tname:
        label += f".{tname}"
    cost = 8.0 + pcost + 0.6 * abs(nth) + tcost
    return Atom(name=label, cost=cost, fn=fn)


def _substr_atom(a, b, tname, tcost) -> Atom:
    tfn = TRANSFORMS[tname]

    def fn(line, i=a, j=b, t=tfn):
        s = line[i:j] if j is not None else line[i:]
        return t(s)

    label = f"slice({a},{'' if b is None else b})"
    if tname:
        label += f".{tname}"
    cost = 12.0 + 0.3 * abs(a) + tcost
    return Atom(name=label, cost=cost, fn=fn)


# ---------------------------------------------------------------------------
# Atom catalog generation.
# ---------------------------------------------------------------------------

# Transform whitelist ordered roughly by likelihood.
_TFORMS = ["", "strip", "lower", "upper", "cap", "title", "first", "First"]


def build_atoms(inputs: list[str], use_slices: bool = True) -> list[Atom]:
    atoms: list[Atom] = []

    # Determine the widest field count across inputs, per delimiter, so we can
    # enumerate a sensible range of indices (positive and negative).
    for delim, dlabel, dcost in _DELIMS:
        maxparts = max((len(_split(s, delim)) for s in inputs), default=0)
        if maxparts <= 1 and delim is not None:
            continue  # delimiter does not actually occur -> useless
        maxparts = min(maxparts, 24)
        idxs = list(range(maxparts)) + list(range(-maxparts, 0))
        for idx in idxs:
            for tname in _TFORMS:
                atoms.append(_field_atom(delim, dlabel, dcost, idx, tname, _TRANSFORM_COST[tname]))

    for tname in _TFORMS:
        atoms.append(_whole_atom(tname, _TRANSFORM_COST[tname]))

    for pattern, plabel, pcost in _REGEXES:
        maxm = 0
        rx = re.compile(pattern)
        for s in inputs:
            maxm = max(maxm, len(rx.findall(s)))
        maxm = min(maxm, 6)
        for nth in list(range(maxm)) + list(range(-maxm, 0)):
            for tname in _TFORMS:
                atoms.append(_regex_atom(pattern, plabel, pcost, nth, tname, _TRANSFORM_COST[tname]))

    if use_slices:
        maxlen = min(max((len(s) for s in inputs), default=0), 40)
        for a in range(0, maxlen):
            for b in list(range(a + 1, maxlen + 1)) + [None]:
                atoms.append(_substr_atom(a, b, "", 0.0))

    return atoms


# ---------------------------------------------------------------------------
# The synthesized program: an ordered list of atoms whose outputs are
# concatenated.
# ---------------------------------------------------------------------------


@dataclass
class Program:
    atoms: list[Atom]

    def apply(self, line: str) -> Optional[str]:
        out = []
        for a in self.atoms:
            v = a(line)
            if v is None:
                return None
            out.append(v)
        return "".join(out)

    def explain(self) -> str:
        return " + ".join(a.name for a in self.atoms)

    def is_constant(self) -> bool:
        """True if the program ignores its input (all atoms are literals).

        Such a program emits the same output for every line, which almost
        always signals too few / non-varied examples rather than a real
        transformation.
        """
        return all(getattr(a, "kind", "expr") == "const" for a in self.atoms)


# ---------------------------------------------------------------------------
# Uniform-cost search over multi-example position tuples.
# ---------------------------------------------------------------------------


class SynthesisError(Exception):
    pass


def synthesize(
    examples: list[tuple[str, str]],
    *,
    use_slices: bool = True,
    max_expansions: int = 400_000,
    time_limit: float = 5.0,
) -> Program:
    """Find the simplest Program mapping every example input to its output.

    Raises SynthesisError if no program in the DSL is consistent with the
    examples within the search budget.
    """
    if not examples:
        raise SynthesisError("no examples given")

    inputs = [i for i, _ in examples]
    outputs = [o for _, o in examples]
    K = len(examples)

    atoms = build_atoms(inputs, use_slices=use_slices)

    # Precompute each atom's value on each example once. Drop atoms that are
    # None on any example (can never be used) or empty on all (no progress).
    usable: list[tuple[Atom, tuple[str, ...]]] = []
    for a in atoms:
        vals = []
        ok = True
        for line in inputs:
            v = a(line)
            if v is None:
                ok = False
                break
            vals.append(v)
        if not ok:
            continue
        if all(v == "" for v in vals):
            continue
        usable.append((a, tuple(vals)))

    start = tuple([0] * K)
    goal = tuple(len(o) for o in outputs)

    # Dijkstra over position tuples.
    heap: list[tuple[float, int, tuple[int, ...]]] = [(0.0, 0, start)]
    best_cost: dict[tuple[int, ...], float] = {start: 0.0}
    parent: dict[tuple[int, ...], tuple[tuple[int, ...], Atom]] = {}
    counter = 0
    expansions = 0
    deadline = time.monotonic() + time_limit

    while heap:
        cost, _, state = heapq.heappop(heap)
        if cost > best_cost.get(state, float("inf")):
            continue
        if state == goal:
            return _reconstruct(state, parent)
        expansions += 1
        if expansions > max_expansions:
            break
        if (expansions & 0x3FF) == 0 and time.monotonic() > deadline:
            break

        # Extractor transitions.
        for a, vals in usable:
            nxt = _advance(state, vals, outputs)
            if nxt is None:
                continue
            nc = cost + a.cost
            if nc < best_cost.get(nxt, float("inf")):
                best_cost[nxt] = nc
                parent[nxt] = (state, a)
                counter += 1
                heapq.heappush(heap, (nc, counter, nxt))

        # Constant transitions: consume the longest common prefix (and each of
        # its non-empty prefixes) of the remaining outputs. This produces glue
        # literals like ", " without hardcoding data.
        lcp = _remaining_lcp(state, outputs)
        for length in range(1, len(lcp) + 1):
            text = lcp[:length]
            nxt = tuple(p + length for p in state)
            catom = _const_atom(text)
            nc = cost + catom.cost
            if nc < best_cost.get(nxt, float("inf")):
                best_cost[nxt] = nc
                parent[nxt] = (state, catom)
                counter += 1
                heapq.heappush(heap, (nc, counter, nxt))

    raise SynthesisError(
        "could not find a consistent transformation for the given examples"
    )


def _advance(state, vals, outputs) -> Optional[tuple[int, ...]]:
    nxt = []
    moved = False
    for k in range(len(state)):
        p = state[k]
        v = vals[k]
        end = p + len(v)
        if outputs[k][p:end] != v:
            return None
        if len(v) > 0:
            moved = True
        nxt.append(end)
    if not moved:
        return None
    return tuple(nxt)


def _remaining_lcp(state, outputs) -> str:
    rems = [outputs[k][state[k]:] for k in range(len(state))]
    if any(r == "" for r in rems):
        return ""
    first = rems[0]
    n = len(first)
    for r in rems[1:]:
        n = min(n, len(r))
    out = []
    for i in range(n):
        c = first[i]
        if all(r[i] == c for r in rems):
            out.append(c)
        else:
            break
    return "".join(out)


def _reconstruct(goal, parent) -> Program:
    atoms: list[Atom] = []
    state = goal
    while state in parent:
        prev, atom = parent[state]
        atoms.append(atom)
        state = prev
    atoms.reverse()
    # Merge consecutive constant atoms into one for a cleaner explanation.
    merged: list[Atom] = []
    for a in atoms:
        if a.kind == "const" and merged and merged[-1].kind == "const":
            combined = _const_from(merged[-1]) + _const_from(a)
            merged[-1] = _const_atom(combined)
        else:
            merged.append(a)
    return Program(merged)


def _const_from(a: Atom) -> str:
    # const atom name is repr(text); recover the text by calling it.
    return a("") or ""
