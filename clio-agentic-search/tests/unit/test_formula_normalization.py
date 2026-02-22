"""Tests for R4: formula semantic equivalence via canonical normalization."""

from __future__ import annotations

from clio_agentic_search.indexing.scientific import normalize_formula


def test_side_swapping_equivalence() -> None:
    assert normalize_formula("E=mc^2") == normalize_formula("mc^2=E")


def test_commutative_multiplication() -> None:
    assert normalize_formula("PV=nRT") == normalize_formula("nRT=PV")
    assert normalize_formula("F=ma") == normalize_formula("ma=F")


def test_canonical_forms() -> None:
    assert normalize_formula("E=mc^2") == "c^2m=e"
    assert normalize_formula("PV=nRT") == "nrt=pv"
    assert normalize_formula("F=ma") == "am=f"


def test_superscript_normalization() -> None:
    assert normalize_formula("x^{2}") == normalize_formula("x^2")
    assert normalize_formula("y**2") == normalize_formula("y^2")


def test_division_preserved() -> None:
    assert normalize_formula("P=F/A") == "f/a=p"
    assert normalize_formula("F/A=P") == "f/a=p"


def test_empty_input() -> None:
    assert normalize_formula("") == ""
    assert normalize_formula("   ") == ""


def test_no_equals_sign() -> None:
    result = normalize_formula("mc^2")
    assert result == "c^2m"


def test_whitespace_insensitive() -> None:
    assert normalize_formula("E = m c ^ 2") == normalize_formula("E=mc^2")
