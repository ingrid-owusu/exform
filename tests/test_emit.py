"""Tests for `exform --emit python` (standalone script generation)."""

import subprocess
import sys

from exform.synth import synthesize
from exform.emit import to_python, EmitError


def _run_script(script: str, lines):
    """Execute an emitted script in a fresh interpreter, feeding `lines` on
    stdin; return the list of output lines."""
    proc = subprocess.run(
        [sys.executable, "-c", script],
        input="\n".join(lines) + "\n",
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.splitlines()


def _emit(pairs):
    prog = synthesize(pairs)
    return to_python(prog, pairs)


def test_emit_reproduces_examples_camel():
    pairs = [("my_var_name", "myVarName"), ("home_address", "homeAddress")]
    script = _emit(pairs)
    assert _run_script(script, ["foo_bar_baz"]) == ["fooBarBaz"]


def test_emit_date_reorder():
    pairs = [("2021-03-05", "05/03/2021"), ("1999-12-31", "31/12/1999")]
    script = _emit(pairs)
    assert _run_script(script, ["2020-01-02"]) == ["02/01/2020"]


def test_emit_zpad():
    pairs = [("7", "007"), ("42", "042")]
    script = _emit(pairs)
    assert _run_script(script, ["5", "123"]) == ["005", "123"]


def test_emit_group_thousands():
    pairs = [("1234567", "1,234,567"), ("42", "42")]
    script = _emit(pairs)
    assert _run_script(script, ["9999999"]) == ["9,999,999"]


def test_emit_slug():
    pairs = [("Hello, World!", "hello-world")]
    script = _emit(pairs)
    assert _run_script(script, ["Foo Bar Baz!"]) == ["foo-bar-baz"]


def test_emit_field_upper():
    pairs = [("level=info", "INFO")]
    script = _emit(pairs)
    assert _run_script(script, ["level=warn"]) == ["WARN"]


def test_emit_title():
    pairs = [("the lord of the rings", "The Lord Of The Rings")]
    script = _emit(pairs)
    assert _run_script(script, ["a tale of two cities"]) == [
        "A Tale Of Two Cities"
    ]


def test_emit_is_dependency_free():
    """Generated script must not import exform."""
    pairs = [("my_var_name", "myVarName"), ("home_address", "homeAddress")]
    script = _emit(pairs)
    assert "import exform" not in script
    assert "from exform" not in script


def test_emit_passthrough_on_no_match():
    """A line the transform can't handle is echoed unchanged."""
    pairs = [("level=info", "INFO")]
    script = _emit(pairs)
    # a line without the '=' delimiter -> field() returns None -> passthrough
    assert _run_script(script, ["noequalshere"]) == ["noequalshere"]


def test_emit_verify_gate_catches_mismatch():
    """to_python must reject a program that doesn't reproduce its examples."""
    prog = synthesize([("a", "A")])
    # Corrupt the example set so the verify step disagrees.
    try:
        to_python(prog, [("a", "Z")])
    except EmitError:
        pass
    else:
        raise AssertionError("expected EmitError on mismatched examples")


def test_cli_emit_runs_end_to_end():
    """`exform ... --emit python | python3 -` round-trips through the CLI."""
    gen = subprocess.run(
        [sys.executable, "-m", "exform",
         "-e", "my_var_name => myVarName",
         "-e", "home_address => homeAddress",
         "--emit", "python"],
        capture_output=True, text=True,
    )
    assert gen.returncode == 0, gen.stderr
    assert _run_script(gen.stdout, ["deep_nested_key"]) == ["deepNestedKey"]


def test_emit_camel_to_snake_case():
    prog = synthesize([("myVariableName", "my_variable_name"),
                       ("firstName", "first_name")])
    script = to_python(prog, [("myVariableName", "my_variable_name"),
                              ("firstName", "first_name")])
    assert _run_script(script, ["getHTTPResponse", "userId"]) == [
        "get_http_response", "user_id"]


def test_emit_title_case():
    prog = synthesize([("myVariableName", "My Variable Name"),
                       ("first_name", "First Name")])
    script = to_python(prog, [("myVariableName", "My Variable Name"),
                              ("first_name", "First Name")])
    assert _run_script(script, ["http_status_code"]) == ["Http Status Code"]
