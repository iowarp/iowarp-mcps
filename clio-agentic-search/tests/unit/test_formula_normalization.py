"""Tests for R4: formula semantic equivalence via canonical normalization."""

from __future__ import annotations

from clio_agentic_search.indexing.scientific import (
    extract_formula_signatures,
    normalize_formula,
)


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


# ---- Plain-text extraction (no $ delimiters) ----


def test_extract_plain_text_arrhenius() -> None:
    text = "The Arrhenius equation k = A e^{-E_a/RT}, where A is the pre-exponential factor."
    sigs = extract_formula_signatures(text)
    assert sigs, "Expected formula extraction from plain text"
    expected = normalize_formula("k = A e^{-E_a/RT}")
    assert expected in sigs


def test_extract_plain_text_emc2() -> None:
    text = "Einstein showed that E = mc^2 in 1905."
    sigs = extract_formula_signatures(text)
    assert sigs
    assert normalize_formula("E = mc^2") in sigs


def test_extract_plain_text_skips_dollar_delimited() -> None:
    """Dollar-delimited equations should be extracted by the $ pass, not duplicated."""
    text = "The relation $k = A e^{-E_a/RT}$ holds."
    sigs = extract_formula_signatures(text)
    assert len(sigs) == 1
    assert normalize_formula("k = A e^{-E_a/RT}") in sigs


def test_extract_plain_text_skips_table_lines() -> None:
    text = "| k = A e^{-E_a/RT} | some col |\n"
    sigs = extract_formula_signatures(text)
    assert sigs == []


def test_extract_plain_text_no_math_indicator() -> None:
    """Expressions without ^, {, or \\ are not extracted as formulas."""
    text = "The result is F = ma in all inertial frames."
    sigs = extract_formula_signatures(text)
    assert sigs == []


def test_extract_plain_text_coexists_with_dollar() -> None:
    """A document may have both $-delimited and plain-text equations."""
    text = "First: $P V = n R T$.\nAlso: E = mc^2 is well known.\n"
    sigs = extract_formula_signatures(text)
    assert normalize_formula("PV=nRT") in sigs
    assert normalize_formula("E=mc^2") in sigs
