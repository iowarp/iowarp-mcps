"""Tests for Chronolog utility helper functions."""

import pytest

from chronomcp.utils.helpers import parse_time_arg
from .test_utils import are_chronolog_processes_running


class TestHelpers:
    """Test utility helper functions"""

    def test_parse_time_arg_with_digits(self):
        """Test parsing numeric time arguments"""
        if not are_chronolog_processes_running():
            pytest.skip("ChronoLog processes are not running")

        result = parse_time_arg("1672574400000000000", False)
        assert result == "1672574400000000000"

    def test_parse_time_arg_today(self):
        """Test parsing 'today' keyword"""
        if not are_chronolog_processes_running():
            pytest.skip("ChronoLog processes are not running")

        result = parse_time_arg("today", False)
        assert isinstance(result, str)
        assert result.isdigit()

    def test_parse_time_arg_iso_format(self):
        """Test parsing ISO format dates"""
        if not are_chronolog_processes_running():
            pytest.skip("ChronoLog processes are not running")

        result = parse_time_arg("2023-01-15", False)
        assert isinstance(result, str)
        assert result.isdigit()
