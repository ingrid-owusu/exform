"""In-line (sed-by-example) transforms.

The default exform engine rewrites a *whole* line: the output is built by
concatenating pieces taken from the input. That is perfect for reformatting
records ("John Smith" => "Smith, J.") but it cannot express "find the date
inside each line and reformat just that, leaving the rest of the line alone" --
the job people normally reach for ``sed`` to do.

This module adds exactly that, still by example. Given a before/after pair
where only a *substring* changed::

    "commit on 2021-03-05 by ana" => "commit on 2021/03/05 by ana"

exform:

1. strips the shared prefix (``"commit on "``) and suffix (``" by ana"``) to
   isolate the part that actually changed -- here ``"2021-03-05"`` becomes
   ``"2021/03/05"``;
2. synthesises an ordinary exform program for that inner change
   (``2021-03-05`` -> ``2021/03/05``) using the normal engine;
3. generalises the matched text into a *locator* pattern (``\\d+-\\d+-\\d+``)
   so it can find the same kind of token on lines it has never seen;
4. on every input line, finds the locator, transforms just that span with the
   inner program, and splices the result back in -- the rest of the line is
   untouched.

Everything stays deterministic, offline and dependency-free. It is a thin,
opt-in layer over the existing synthesiser, reachable via ``exform --in-line``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional

from .synth import Program, SynthesisError, synthesize


def _common_prefix_len(a: str, b: str) -> int:
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def _common_suffix_len(a: str, b: str, cap: int) -> int:
    n = min(len(a), len(b), cap)
    i = 0
    while i < n and a[-1 - i] == b[-1 - i]:
        i += 1
    return i


def _split_change(src: str, dst: str) -> Optional[tuple[str, str, str, str]]:
    """Return (prefix, mid_src, mid_dst, suffix) isolating the changed span.

    ``prefix + mid_src + suffix == src`` and ``prefix + mid_dst + suffix == dst``.
    The prefix/suffix are the maximal shared context; the mids are what
    differs. Returns None if the strings are identical (nothing changed).
    """
    if src == dst:
        return None
    p = _common_prefix_len(src, dst)
    # Cap the suffix so prefix and suffix cannot overlap on either string.
    cap = min(len(src) - p, len(dst) - p)
    s = _common_suffix_len(src, dst, cap)
    prefix = src[:p]
    suffix = src[len(src) - s:] if s else ""
    mid_src = src[p: len(src) - s]
    mid_dst = dst[p: len(dst) - s]
    return prefix, mid_src, mid_dst, suffix


def _char_class(ch: str) -> Optional[str]:
    if ch.isdigit():
        return r"\d"
    if "a" <= ch <= "z":
        return "[a-z]"
    if "A" <= ch <= "Z":
        return "[A-Z]"
    return None  # literal


def _generalise(mid: str) -> str:
    """Turn a concrete matched substring into a locator regex.

    Runs of the same character class collapse to a quantified class
    (``2021`` -> ``\\d+``); everything else is matched literally. This is what
    lets a rule inferred from one date find dates on other lines.
    """
    if mid == "":
        # Empty match (pure insertion). Anchor at a word boundary so we don't
        # match at every position; callers handle this conservatively.
        return r""
    parts: list[str] = []
    i = 0
    n = len(mid)
    while i < n:
        cls = _char_class(mid[i])
        if cls is None:
            parts.append(re.escape(mid[i]))
            i += 1
            continue
        j = i + 1
        while j < n and _char_class(mid[j]) == cls:
            j += 1
        parts.append(cls + "+")
        i = j
    return "".join(parts)


def _combine_locators(pats: list[str], mids: list[str]) -> str:
    seen: list[str] = []
    for p in pats:
        if p and p not in seen:
            seen.append(p)
    if not seen:
        raise SynthesisError(
            "the examples only insert text; in-line mode needs an example "
            "where an existing substring is changed"
        )
    if len(seen) == 1:
        return seen[0]
    # Prefer a single pattern that matches every example mid; otherwise union.
    for cand in seen:
        rx = re.compile(cand)
        if all(rx.fullmatch(m) for m in mids):
            return cand
    return "|".join(f"(?:{p})" for p in seen)


@dataclass
class InlineProgram:
    locator: "re.Pattern[str]"
    inner: Program
    replace_all: bool

    def explain(self) -> str:
        scope = "every match" if self.replace_all else "first match"
        return (
            f"find /{self.locator.pattern}/ ({scope}) and rewrite it as: "
            f"{self.inner.explain()}"
        )

    def apply(self, line: str) -> Optional[str]:
        """Transform matched span(s) in ``line``; return None if no change.

        Returning None lets the CLI apply its --on-error policy (default: keep
        the original line), consistent with whole-line mode.
        """
        matched_any = False

        def _sub(m: "re.Match[str]") -> str:
            nonlocal matched_any
            rewritten = self.inner.apply(m.group(0))
            if rewritten is None:
                return m.group(0)  # leave this span alone
            matched_any = True
            return rewritten

        count = 0 if self.replace_all else 1
        result = self.locator.sub(_sub, line, count=count)
        if not matched_any:
            return None
        return result


def infer_inline(
    examples: list[tuple[str, str]],
    *,
    use_slices: bool = True,
    replace_all: bool = False,
) -> InlineProgram:
    """Build an :class:`InlineProgram` from before/after examples.

    Raises :class:`SynthesisError` if the examples do not describe a consistent
    in-line change (e.g. nothing changed, or the inner transform is not
    learnable, or the result does not reproduce the examples).
    """
    if not examples:
        raise SynthesisError("no examples given")

    mids: list[tuple[str, str]] = []
    mid_srcs: list[str] = []
    locators: list[str] = []
    left_delims: list[Optional[str]] = []
    right_delims: list[Optional[str]] = []
    for src, dst in examples:
        split = _split_change(src, dst)
        if split is None:
            raise SynthesisError(
                f"example {src!r} => {dst!r} does not change anything"
            )
        prefix, mid_src, mid_dst, suffix = split
        mids.append((mid_src, mid_dst))
        mid_srcs.append(mid_src)
        locators.append(_generalise(mid_src))
        # A non-alphanumeric boundary char is a reliable anchor that keeps the
        # locator from latching onto an earlier/later run of the same class.
        left_delims.append(
            prefix[-1] if prefix and not prefix[-1].isalnum() else None
        )
        right_delims.append(
            suffix[0] if suffix and not suffix[0].isalnum() else None
        )

    inner = synthesize(mids, use_slices=use_slices)
    core = _combine_locators(locators, mid_srcs)
    lookbehind = ""
    lookahead = ""
    if left_delims and all(d is not None and d == left_delims[0] for d in left_delims):
        lookbehind = f"(?<={re.escape(left_delims[0])})"
    if right_delims and all(d is not None and d == right_delims[0] for d in right_delims):
        lookahead = f"(?={re.escape(right_delims[0])})"
    locator_src = lookbehind + core + lookahead
    locator = re.compile(locator_src)
    prog = InlineProgram(locator=locator, inner=inner, replace_all=replace_all)

    # Correctness gate: the assembled rule must reproduce every example exactly.
    for src, dst in examples:
        got = prog.apply(src)
        if got != dst:
            raise SynthesisError(
                "could not find a consistent in-line transformation "
                f"(example {src!r} => {dst!r} produced {got!r}); "
                "try a clearer example or drop --in-line for a whole-line rule"
            )
    return prog


def memorized_inner_literals(
    prog: InlineProgram, inputs: Iterable[str]
) -> list[str]:
    """Surface memorised literals in the inner program (same heuristic)."""
    mids = []
    for line in inputs:
        m = prog.locator.search(line)
        if m:
            mids.append(m.group(0))
    return prog.inner.memorized_literals(mids)
