"""Unit tests for :mod:`parser.lean_parser`.

All cases use :func:`parse_text` so there is zero filesystem coupling
and no need for ``pytest-asyncio`` / temp-dirs.
"""

from __future__ import annotations

import textwrap

import pytest

from parser.lean_parser import parse_text


def _names(content: str) -> list[str]:
    return [s.name for s in parse_text(content).symbols]


def _kinds(content: str) -> list[tuple[str, str]]:
    return [(s.name, s.kind) for s in parse_text(content).symbols]


# ──────────────────────────────────────────────────────────────────────────────


def test_simple_def() -> None:
    src = "def foo : Nat := 42\n"
    parsed = parse_text(src)
    assert len(parsed.symbols) == 1
    assert parsed.symbols[0].name == "foo"
    assert parsed.symbols[0].kind == "def"
    assert parsed.symbols[0].line_start == 1
    assert parsed.symbols[0].is_private is False
    assert "def foo" in parsed.symbols[0].signature_text


def test_theorem_extraction() -> None:
    src = "theorem foo (h : p) : q := by tauto\n"
    parsed = parse_text(src)
    assert _kinds(src) == [("foo", "theorem")]
    assert parsed.symbols[0].signature_text.startswith("theorem foo")


def test_modifier_protected_private_noncomputable() -> None:
    src = textwrap.dedent(
        """\
        protected def a : Nat := 1
        private def b : Nat := 2
        noncomputable def c : Nat := 3
        partial def d : Nat → Nat | n => d n
        unsafe def e : Nat := 5
        """
    )
    parsed = parse_text(src)
    assert _kinds(src) == [
        ("a", "def"),
        ("b", "def"),
        ("c", "def"),
        ("d", "def"),
        ("e", "def"),
    ]
    by_name = {s.name: s for s in parsed.symbols}
    assert by_name["b"].is_private is True
    assert by_name["a"].is_private is False
    assert by_name["c"].is_private is False


def test_namespace_tracking() -> None:
    src = textwrap.dedent(
        """\
        namespace Foo
        def bar : Nat := 1
        end Foo
        def baz : Nat := 2
        """
    )
    parsed = parse_text(src)
    by_name = {s.name: s for s in parsed.symbols}
    assert by_name["bar"].namespace_path == "Foo"
    assert by_name["bar"].full_name == "Foo.bar"
    assert by_name["baz"].namespace_path == ""
    assert by_name["baz"].full_name == "baz"


def test_nested_namespaces() -> None:
    src = textwrap.dedent(
        """\
        namespace Foo
        namespace Bar
        def deep : Nat := 1
        end Bar
        def shallow : Nat := 2
        end Foo
        """
    )
    by_name = {s.name: s for s in parse_text(src).symbols}
    assert by_name["deep"].namespace_path == "Foo.Bar"
    assert by_name["deep"].full_name == "Foo.Bar.deep"
    assert by_name["shallow"].namespace_path == "Foo"
    assert by_name["shallow"].full_name == "Foo.shallow"


def test_imports_parsing() -> None:
    src = textwrap.dedent(
        """\
        import Mathlib.Algebra.Group.Basic
        import Mathlib.Data.Nat.Defs
        import Std

        def x : Nat := 0
        """
    )
    parsed = parse_text(src)
    assert parsed.imports == [
        "Mathlib.Algebra.Group.Basic",
        "Mathlib.Data.Nat.Defs",
        "Std",
    ]
    assert _names(src) == ["x"]


def test_line_comments_stripped() -> None:
    src = textwrap.dedent(
        """\
        -- def fake : Nat := 0
        def real : Nat := 1
        -- theorem also_fake : True := trivial
        """
    )
    assert _names(src) == ["real"]


def test_block_comments_stripped() -> None:
    src = textwrap.dedent(
        """\
        /- def fake : Nat := 0
           theorem hidden : True := trivial -/
        def real : Nat := 1
        """
    )
    assert _names(src) == ["real"]


def test_string_literals_no_false_positives() -> None:
    src = textwrap.dedent(
        '''\
        def banner : String := "def fake_in_string : Nat := 99"
        def other : String := "theorem hidden : True := trivial"
        '''
    )
    names = _names(src)
    assert names == ["banner", "other"]


def test_class_structure_inductive() -> None:
    src = textwrap.dedent(
        """\
        class MyClass where field : Nat
        structure MyStruct where x : Nat
        inductive MyInd | a | b | c
        """
    )
    assert _kinds(src) == [
        ("MyClass", "class"),
        ("MyStruct", "structure"),
        ("MyInd", "inductive"),
    ]


def test_empty_file() -> None:
    parsed = parse_text("")
    assert parsed.imports == []
    assert parsed.symbols == []
    assert parsed.line_count == 0


def test_file_with_only_imports() -> None:
    src = "import Foo\nimport Bar.Baz\n"
    parsed = parse_text(src)
    assert parsed.imports == ["Foo", "Bar.Baz"]
    assert parsed.symbols == []


def test_abbrev_axiom_opaque_instance_lemma() -> None:
    src = textwrap.dedent(
        """\
        abbrev Nat' := Nat
        axiom choice : ∀ {α : Type}, Nonempty α → α
        opaque secret : Nat
        instance : Inhabited Nat where default := 0
        lemma trivial_lemma : True := trivial
        """
    )
    kinds = _kinds(src)
    # The anonymous instance gets a synthesised name (starts with "_anon_").
    kind_only = [k for _, k in kinds]
    assert "abbrev" in kind_only
    assert "axiom" in kind_only
    assert "opaque" in kind_only
    assert "instance" in kind_only
    assert "lemma" in kind_only


def test_signature_text_truncates_at_walrus() -> None:
    src = "def add (a b : Nat) : Nat := a + b\n"
    parsed = parse_text(src)
    sig = parsed.symbols[0].signature_text
    assert ":=" not in sig
    assert "a + b" not in sig
    assert "def add" in sig


def test_multiple_namespace_blocks_pop_correctly() -> None:
    """``end`` must really restore the outer scope."""
    src = textwrap.dedent(
        """\
        namespace A
        def in_a : Nat := 0
        end A
        namespace B
        def in_b : Nat := 0
        end B
        def top_level : Nat := 0
        """
    )
    by_name = {s.name: s for s in parse_text(src).symbols}
    assert by_name["in_a"].namespace_path == "A"
    assert by_name["in_b"].namespace_path == "B"
    assert by_name["top_level"].namespace_path == ""


def test_attributes_before_decl() -> None:
    src = "@[simp] theorem t : True := trivial\n"
    parsed = parse_text(src)
    assert _kinds(src) == [("t", "theorem")]


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
