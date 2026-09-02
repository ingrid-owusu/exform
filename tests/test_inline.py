"""Tests for in-line (sed-by-example) transforms."""

import subprocess
import sys

import pytest

from exform.inline import infer_inline
from exform.synth import SynthesisError


def test_reformat_date_inside_line():
    p = infer_inline(
        [("commit on 2021-03-05 by ana", "commit on 2021/03/05 by ana")]
    )
    assert p.apply("pushed 1999-12-31 tag") == "pushed 1999/12/31 tag"
    # Lines with no match are reported as unchanged (None).
    assert p.apply("no date here") is None


def test_uppercase_token_with_delimiter_anchor():
    # The changed token ("info") shares its character class with earlier text
    # ("level"); the delimiter anchor must keep the locator on the right span.
    p = infer_inline(
        [
            ("level=info msg=x", "level=INFO msg=x"),
            ("level=warn go", "level=WARN go"),
        ]
    )
    assert p.apply("level=error boom") == "level=ERROR boom"
    assert p.apply("level=debug q") == "level=DEBUG q"
    assert p.apply("no keyword") is None


def test_wrap_word_in_brackets():
    p = infer_inline(
        [("see foo here", "see <foo> here"), ("see bar ok", "see <bar> ok")]
    )
    assert p.apply("see baz now") == "see <baz> now"


def test_examples_reproduced_exactly():
    exs = [("a-1-b", "a/1/b"), ("c-9-d", "c/9/d")]
    p = infer_inline(exs)
    for src, dst in exs:
        assert p.apply(src) == dst


def test_replace_all_vs_first():
    src = "a 1 2 3 b"
    first = infer_inline([("a 1 b", "a [1] b")])
    assert first.apply(src) == "a [1] 2 3 b"
    every = infer_inline([("a 1 b", "a [1] b")], replace_all=True)
    assert every.apply(src) == "a [1] [2] [3] b"


def test_no_change_example_rejected():
    with pytest.raises(SynthesisError):
        infer_inline([("same", "same")])


def test_inconsistent_transform_rejected():
    # A whole-token restructure (phone) is not a clean substring change.
    with pytest.raises(SynthesisError):
        infer_inline(
            [("call 1234567890 now", "call (123) 456-7890 now")]
        )


def test_apply_returns_none_when_no_match():
    p = infer_inline([("a-1-b", "a/1/b")])
    assert p.apply("nothing to match") is None


def test_pure_insertion_rejected():
    # Zero-padding ("7" -> "007") reads as inserting "00" before a shared "7",
    # which is not a substring *change*; in-line mode declines it.
    with pytest.raises(SynthesisError):
        infer_inline([("id=7 x", "id=007 x")])


def _cli(args, stdin):
    return subprocess.run(
        [sys.executable, "-m", "exform", *args],
        input=stdin,
        capture_output=True,
        text=True,
    )


def test_cli_inline_basic():
    r = _cli(
        ["--in-line", "-e", "d 2020-01-02 e => d 2020/01/02 e"],
        "row 2024-11-30 tail\n",
    )
    assert r.returncode == 0
    assert r.stdout == "row 2024/11/30 tail\n"


def test_cli_inline_explain_and_keep():
    r = _cli(
        ["--in-line", "--explain", "-e", "a-1-b => a/1/b"],
        "keep this\nx-5-y\n",
    )
    assert r.returncode == 0
    # unmatched line kept verbatim; matched line transformed
    assert r.stdout == "keep this\nx/5/y\n"
    assert "program:" in r.stderr


def test_cli_inline_alias():
    r = _cli(["--inline", "-e", "a-1-b => a/1/b"], "p-2-q\n")
    assert r.returncode == 0
    assert r.stdout == "p/2/q\n"
