"""Tests for --field (column-aware) mode."""

import io
import subprocess
import sys

import pytest

from exform.cli import _parse_fields, run


def _run(argv, stdin=""):
    """Invoke the CLI in-process, capturing stdout/stderr and exit code."""
    old_in, old_out, old_err = sys.stdin, sys.stdout, sys.stderr
    sys.stdin = io.StringIO(stdin)
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    try:
        code = run(argv)
        return code, sys.stdout.getvalue(), sys.stderr.getvalue()
    finally:
        sys.stdin, sys.stdout, sys.stderr = old_in, old_out, old_err


def test_parse_fields_single():
    assert _parse_fields("3") == [3]


def test_parse_fields_list():
    assert _parse_fields("2,4") == [2, 4]
    assert _parse_fields("1, 3 , 5") == [1, 3, 5]


def test_parse_fields_rejects_zero():
    with pytest.raises(SystemExit):
        _parse_fields("0")


def test_parse_fields_rejects_nonint():
    with pytest.raises(SystemExit):
        _parse_fields("a")


def test_field_transforms_only_target_column():
    code, out, _ = _run(
        ["--field", "2", "-e", "John Smith => Smith, J."],
        stdin="1,John Smith,NYC\n2,Jane Doe,LA\n",
    )
    assert code == 0
    # column 1 (id) and column 3 (city) are untouched
    assert out == "1,Smith, J.,NYC\n2,Doe, J.,LA\n"


def test_field_leaves_other_columns_byte_identical():
    # leading/trailing spaces and delimiters in untouched cells are preserved
    code, out, _ = _run(
        ["--field", "3", "-e", "NYC => New York", "-q"],
        stdin="1, John Smith ,NYC\n",
    )
    assert code == 0
    assert out == "1, John Smith ,New York\n"


def test_field_tab_separator():
    code, out, _ = _run(
        [
            "--field", "2",
            "--field-sep", "\t",
            "-e", "2021-05-01 => 05/01/2021",
            "-e", "2022-12-31 => 12/31/2022",
        ],
        stdin="a\t2021-05-01\tx\nb\t2022-12-31\ty\n",
    )
    assert code == 0
    assert out == "a\t05/01/2021\tx\nb\t12/31/2022\ty\n"


def test_field_multiple_columns():
    code, out, _ = _run(
        ["--field", "1,3", "-e", "john => John", "-e", "jane => Jane"],
        stdin="john,x,doe\njane,y,roe\n",
    )
    # note: the transform is title-case-first-word, applies to cols 1 and 3
    assert code == 0
    lines = out.strip().split("\n")
    assert lines[0].split(",")[0] == "John"
    assert lines[0].split(",")[2] == "Doe"
    assert lines[1].split(",")[0] == "Jane"
    assert lines[1].split(",")[2] == "Roe"


def test_field_out_of_range_column_is_noop():
    # a row shorter than the target column is passed through unchanged
    code, out, _ = _run(
        ["--field", "5", "-e", "a => A", "-q"],
        stdin="a,b,c\n",
    )
    assert code == 0
    assert out == "a,b,c\n"


def test_field_on_error_keep_default():
    # a cell the program can't transform is kept as-is (default policy)
    code, out, _ = _run(
        ["--field", "1", "-e", "John Smith => Smith, J.", "-q"],
        stdin="John Smith\nsingle\n",
    )
    assert code == 0
    # 'single' can't match the two-word rule -> kept unchanged
    assert out == "Smith, J.\nsingle\n"


def test_field_on_error_skip_drops_row():
    code, out, _ = _run(
        ["--field", "1", "--on-error", "skip", "-e", "John Smith => Smith, J.", "-q"],
        stdin="John Smith\nsingle\n",
    )
    assert code == 0
    assert out == "Smith, J.\n"


def test_field_rejects_emit():
    code, _out, err = _run(
        ["--field", "2", "--emit", "python", "-e", "a => A"],
        stdin="",
    )
    assert code == 2
    assert "emit" in err.lower()


def test_field_rejects_inline_combo():
    code, _out, err = _run(
        ["--field", "2", "--in-line", "-e", "a => A"],
        stdin="",
    )
    assert code == 2
    assert "field" in err.lower()
