"""Tests for --fill (FlashFill) mode of the exform CLI."""

import io

import pytest

from exform.cli import run


def _run(argv, stdin_text, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_text))
    code = run(argv)
    out, err = capsys.readouterr()
    return code, out, err


def test_fill_completes_blank_rows(monkeypatch, capsys):
    stdin = (
        "John Smith\tSmith, J.\n"
        "Grace Hopper\tHopper, G.\n"
        "Alan Turing\n"
        "Ada Lovelace\n"
    )
    code, out, _ = _run(["--fill"], stdin, monkeypatch, capsys)
    assert code == 0
    lines = out.rstrip("\n").split("\n")
    assert lines[2] == "Alan Turing\tTuring, A."
    assert lines[3] == "Ada Lovelace\tLovelace, A."


def test_fill_preserves_given_rows_verbatim(monkeypatch, capsys):
    stdin = "a@x.com\ta\nb@x.com\tb\nc@x.com\n"
    code, out, _ = _run(["--fill"], stdin, monkeypatch, capsys)
    assert code == 0
    lines = out.rstrip("\n").split("\n")
    assert lines[0] == "a@x.com\ta"
    assert lines[1] == "b@x.com\tb"
    assert lines[2] == "c@x.com\tc"


def test_fill_requires_a_completed_row(monkeypatch, capsys):
    code, out, err = _run(["--fill"], "alpha\nbeta\n", monkeypatch, capsys)
    assert code == 2
    assert out == ""
    assert "at least one completed row" in err


def test_fill_custom_col_sep(monkeypatch, capsys):
    stdin = "John Smith,Smith\nGrace Hopper,Hopper\nAlan Turing\n"
    code, out, _ = _run(["--fill", "--col-sep", ","], stdin, monkeypatch, capsys)
    assert code == 0
    assert out.rstrip("\n").split("\n")[2] == "Alan Turing,Turing"


def test_fill_explain_prints_program(monkeypatch, capsys):
    stdin = "John Smith\tSmith\nGrace Hopper\tHopper\nAlan Turing\n"
    code, _, err = _run(["--fill", "--explain"], stdin, monkeypatch, capsys)
    assert code == 0
    assert "program:" in err


def test_fill_nothing_to_do_echoes(monkeypatch, capsys):
    stdin = "John Smith\tSmith\nGrace Hopper\tHopper\n"
    code, out, _ = _run(["--fill"], stdin, monkeypatch, capsys)
    assert code == 0
    assert out == "John Smith\tSmith\nGrace Hopper\tHopper\n"
