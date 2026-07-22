import pytest

from exform import Program, SynthesisError, synthesize


def infer_apply(examples, tests):
    prog = synthesize(examples)
    return prog, [prog.apply(t) for t in tests]


def test_name_reformat():
    prog, out = infer_apply(
        [("John Smith", "Smith, J."), ("Grace Hopper", "Hopper, G.")],
        ["Alan Turing"],
    )
    assert out == ["Turing, A."]


def test_csv_reorder():
    prog, out = infer_apply(
        [("2021,apple,5", "apple: 5"), ("2022,pear,9", "pear: 9")],
        ["2023,plum,2"],
    )
    assert out == ["plum: 2"]


def test_extract_number():
    prog, out = infer_apply(
        [("Order #12345 shipped", "12345"), ("Order #7 shipped", "7")],
        ["Order #42 shipped"],
    )
    assert out == ["42"]


def test_email_upper():
    prog, out = infer_apply(
        [("alice@example.com", "ALICE at EXAMPLE.COM"),
         ("bob@test.org", "BOB at TEST.ORG")],
        ["carol@mail.net"],
    )
    assert out == ["CAROL at MAIL.NET"]


def test_iso_date_to_slashes():
    prog, out = infer_apply(
        [("2021-05-01 ERROR boom", "01/05/2021 boom"),
         ("2022-12-31 WARN cold", "31/12/2022 cold")],
        ["2020-01-15 INFO ok"],
    )
    assert out == ["15/01/2020 ok"]


def test_phone_digits():
    prog, out = infer_apply(
        [("(415) 555-1234", "4155551234"), ("(212) 999-0000", "2129990000")],
        ["(650) 111-2222"],
    )
    assert out == ["6501112222"]


def test_upper_whole_line():
    prog, out = infer_apply(
        [("hello", "HELLO"), ("world foo", "WORLD FOO")],
        ["mixed Case"],
    )
    assert out == ["MIXED CASE"]


def test_all_examples_are_satisfied():
    examples = [("John Smith", "Smith, J."), ("Grace Hopper", "Hopper, G.")]
    prog = synthesize(examples)
    for i, o in examples:
        assert prog.apply(i) == o


def test_program_is_inspectable():
    prog = synthesize([("a,b", "b"), ("c,d", "d")])
    assert isinstance(prog, Program)
    assert isinstance(prog.explain(), str)
    assert prog.explain()


def test_no_examples_raises():
    with pytest.raises(SynthesisError):
        synthesize([])


def test_impossible_is_reported():
    # Output cannot be produced from input by any DSL program.
    with pytest.raises(SynthesisError):
        synthesize(
            [("abc", "totally unrelated \u2603 zzz"),
             ("def", "another \u2603 unrelated one")],
            use_slices=False,
        )


def test_single_example_is_consistent_even_if_ambiguous():
    # With one example the whole output is a valid (if trivial) program.
    prog = synthesize([("x", "y")])
    assert prog.apply("x") == "y"


def test_unicode_roundtrip():
    prog, out = infer_apply(
        [("café latte", "LATTE"), ("thé vert", "VERT")],
        ["número dos"],
    )
    assert out == ["DOS"]


def test_empty_line_handled():
    prog = synthesize([("a b", "b"), ("c d", "d")])
    # a line with too few fields cannot be transformed -> None (CLI decides)
    assert prog.apply("") is None


def test_path_basename():
    prog, out = infer_apply(
        [("/usr/local/bin/exform", "exform"), ("/home/x/a.txt", "a.txt")],
        ["/etc/hosts"],
    )
    assert out == ["hosts"]


def test_constant_program_flagged():
    # When no part of the output can be derived from the input, the only
    # consistent program is a pure constant -- which is_constant() flags.
    prog = synthesize([("x", "hello")])
    assert prog.is_constant()
    assert prog.apply("anything") == "hello"


def test_single_example_prefers_input_reference():
    # A single example is ambiguous, but we should still prefer a program that
    # references the input over one that memorises the whole output.
    prog = synthesize([("Order #12345 shipped", "12345")])
    assert not prog.is_constant()
    assert prog.apply("Order #42 shipped") == "42"


def test_real_transformation_not_constant():
    prog = synthesize([("John Smith", "Smith, J."), ("Grace Hopper", "Hopper, G.")])
    assert not prog.is_constant()


def test_email_username_at_delimiter():
    # Splitting on '@' is a very common first task; a single example should
    # generalise via field(@,0) rather than overfitting a fixed slice.
    prog, out = infer_apply(
        [("jane.doe@corp.com", "jane.doe")],
        ["bob.lee@corp.com", "x@y.io"],
    )
    assert out == ["bob.lee", "x"]


def test_key_value_equals_delimiter():
    prog, out = infer_apply(
        [("name=jane", "jane"), ("city=paris", "paris")],
        ["role=admin"],
    )
    assert out == ["admin"]
