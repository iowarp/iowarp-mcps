"""
Test cases for output formatting capabilities.
"""

import pytest
import pandas as pd
import numpy as np
import json
from datetime import datetime

from pandas_mcp.implementation.output_formatter import (
    BeautifulFormatter,
    create_beautiful_response,
)


class TestBeautifulFormatter:
    """Test suite for BeautifulFormatter"""

    @pytest.fixture
    def sample_dataframe(self):
        """Create sample DataFrame"""
        return pd.DataFrame(
            {
                "id": [1, 2, 3, 4, 5],
                "name": ["Alice", "Bob", "Charlie", "David", "Eve"],
                "score": [85.5, 92.3, 78.9, 95.0, 88.7],
            }
        )

    @pytest.fixture
    def sample_dict(self):
        """Create sample dictionary"""
        return {
            "count": 100,
            "mean": 85.5,
            "std": 10.2,
            "categories": ["A", "B", "C"],
        }

    @pytest.fixture
    def sample_list(self):
        """Create sample list"""
        return [{"id": 1, "value": 10}, {"id": 2, "value": 20}]

    def test_format_success_response_basic(self):
        """Test basic success response formatting"""
        result = BeautifulFormatter.format_success_response(
            operation="load_data", data={"rows": 100, "columns": 5}
        )

        assert "🎯 Operation" in result
        assert result["🎯 Operation"] == "Load Data"
        assert "✅ Status" in result
        assert result["✅ Status"] == "Success"
        assert "⏰ Timestamp" in result
        assert "📊 Results" in result

    def test_format_success_response_with_summary(self):
        """Test success response with summary"""
        result = BeautifulFormatter.format_success_response(
            operation="analyze_data",
            data={"key": "value"},
            summary={"count": 1000, "time_elapsed": 2.5, "memory_usage": 100},
        )

        assert "📈 Summary" in result
        assert any("Count" in key for key in result["📈 Summary"].keys())

    def test_format_success_response_with_metadata(self):
        """Test success response with metadata"""
        result = BeautifulFormatter.format_success_response(
            operation="process_data",
            data={"key": "value"},
            metadata={"file_path": "/path/to/file", "version": "1.0"},
        )

        assert "🔍 Metadata" in result
        assert len(result["🔍 Metadata"]) == 2

    def test_format_success_response_with_insights(self):
        """Test success response with insights"""
        insights = ["Data quality is excellent", "No missing values found"]

        result = BeautifulFormatter.format_success_response(
            operation="validate_data", data={"valid": True}, insights=insights
        )

        assert "💡 Insights" in result
        assert len(result["💡 Insights"]) == 2
        assert all("💡" in insight for insight in result["💡 Insights"])

    def test_format_error_response_basic(self):
        """Test basic error response formatting"""
        result = BeautifulFormatter.format_error_response(
            operation="load_data",
            error_message="File not found",
            error_type="FileNotFoundError",
        )

        assert "🎯 Operation" in result
        assert "❌ Status" in result
        assert result["❌ Status"] == "Error"
        assert "🚨 Error Type" in result
        assert result["🚨 Error Type"] == "FileNotFoundError"
        assert "📝 Error Message" in result
        assert result["📝 Error Message"] == "File not found"

    def test_format_error_response_with_suggestions(self):
        """Test error response with suggestions"""
        suggestions = ["Check file path", "Verify file exists"]

        result = BeautifulFormatter.format_error_response(
            operation="load_data",
            error_message="File not found",
            error_type="FileNotFoundError",
            suggestions=suggestions,
        )

        assert "💭 Suggestions" in result
        assert len(result["💭 Suggestions"]) == 2
        assert all("💭" in sugg for sugg in result["💭 Suggestions"])

    def test_format_dataframe(self, sample_dataframe):
        """Test DataFrame formatting"""
        result = BeautifulFormatter._format_dataframe(sample_dataframe)

        assert "📏 Shape" in result
        assert "5 rows × 3 columns" in result["📏 Shape"]
        assert "📋 Columns" in result
        assert result["📋 Columns"] == ["id", "name", "score"]
        assert "🔍 Preview" in result
        assert len(result["🔍 Preview"]) == 5
        assert "📊 Data Types" in result
        assert "💾 Memory Usage" in result

    def test_format_dict(self, sample_dict):
        """Test dictionary formatting"""
        result = BeautifulFormatter._format_dict(sample_dict)

        assert "count" in result
        assert result["count"] == 100
        assert "mean" in result
        assert "categories" in result
        assert isinstance(result["categories"], list)

    def test_format_list(self, sample_list):
        """Test list formatting"""
        result = BeautifulFormatter._format_list(sample_list)

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(item, dict) for item in result)

    def test_convert_numpy_types(self):
        """Test numpy type conversion"""
        # Test integer conversion
        assert isinstance(BeautifulFormatter._convert_numpy_types(np.int64(10)), int)
        assert BeautifulFormatter._convert_numpy_types(np.int64(10)) == 10

        # Test float conversion
        assert isinstance(
            BeautifulFormatter._convert_numpy_types(np.float64(10.5)), float
        )
        assert BeautifulFormatter._convert_numpy_types(np.float64(10.5)) == 10.5

        # Test bool conversion
        assert isinstance(BeautifulFormatter._convert_numpy_types(np.bool_(True)), bool)
        assert BeautifulFormatter._convert_numpy_types(np.bool_(True)) is True

        # Test array conversion
        arr = np.array([1, 2, 3])
        result = BeautifulFormatter._convert_numpy_types(arr)
        assert isinstance(result, list)
        assert result == [1, 2, 3]

        # Test NaN conversion
        assert BeautifulFormatter._convert_numpy_types(np.nan) is None
        assert BeautifulFormatter._convert_numpy_types(pd.NA) is None

    def test_format_summary_with_various_keys(self):
        """Test summary formatting with different key types"""
        summary = {
            "total_count": 100,
            "processing_time": 2.5,
            "memory_size": 1024,
            "error_count": 0,
            "success_rate": 95.5,
            "custom_metric": 42,
        }

        result = BeautifulFormatter._format_summary(summary)

        # Check that emojis are added appropriately
        assert any("📊" in key for key in result.keys())
        assert any("⏱️" in key for key in result.keys())
        assert any("💾" in key for key in result.keys())

    def test_format_statistical_summary(self):
        """Test statistical summary formatting"""
        stats = {
            "descriptive_stats": {
                "score": {
                    "count": 100,
                    "mean": 85.5,
                    "std": 10.2,
                    "min": 50.0,
                    "25%": 75.0,
                    "50%": 85.0,
                    "75%": 95.0,
                    "max": 100.0,
                }
            },
            "missing_values": {"score": 5, "name": 0},
            "total_rows": 105,
            "data_types": {"score": "float64", "name": "object"},
        }

        result = BeautifulFormatter.format_statistical_summary(stats)

        assert "📊 Descriptive Statistics" in result
        assert "score" in result["📊 Descriptive Statistics"]
        assert "📈 Count" in result["📊 Descriptive Statistics"]["score"]
        assert "🔍 Missing Values" in result
        assert "🏷️ Data Types" in result

    def test_format_correlation_matrix(self):
        """Test correlation matrix formatting"""
        corr_matrix = {
            "var1": {"var1": 1.0, "var2": 0.85, "var3": 0.3},
            "var2": {"var1": 0.85, "var2": 1.0, "var3": 0.25},
            "var3": {"var1": 0.3, "var2": 0.25, "var3": 1.0},
        }

        result = BeautifulFormatter.format_correlation_matrix(corr_matrix)

        assert "🔗 Correlation Matrix" in result
        assert "🔍 Strong Correlations" in result
        # Should identify var1-var2 as strong correlation
        assert len(result["🔍 Strong Correlations"]) > 0

    def test_format_data_quality_report_excellent(self):
        """Test data quality report with excellent score"""
        quality_report = {
            "overall_score": 0.95,
            "quality_metrics": {
                "completeness": 0.98,
                "accuracy": 0.95,
                "consistency": 0.93,
            },
            "issues": ["Minor formatting issues in column A"],
            "recommendations": ["Consider standardizing date formats"],
        }

        result = BeautifulFormatter.format_data_quality_report(quality_report)

        assert "📊 Overall Quality Score" in result
        assert "🟢 Excellent" in result["📊 Overall Quality Score"]
        assert "📋 Quality Metrics" in result
        assert "🚨 Issues Found" in result
        assert "💡 Recommendations" in result

    def test_format_data_quality_report_poor(self):
        """Test data quality report with poor score"""
        quality_report = {
            "overall_score": 0.45,
            "quality_metrics": {"completeness": 0.50, "accuracy": 0.40},
            "issues": ["Many missing values", "Inconsistent data types"],
            "recommendations": ["Clean missing data", "Standardize formats"],
        }

        result = BeautifulFormatter.format_data_quality_report(quality_report)

        assert "📊 Overall Quality Score" in result
        assert "🔴 Poor" in result["📊 Overall Quality Score"]

    def test_create_beautiful_response_success(self):
        """Test create_beautiful_response for success case"""
        result = create_beautiful_response(
            operation="test_operation",
            success=True,
            data={"key": "value"},
            summary={"count": 10},
        )

        assert "content" in result
        assert "_meta" in result
        assert result["_meta"]["success"] is True
        assert result["isError"] is False

        # Check that content is valid JSON
        content_text = result["content"][0]["text"]
        parsed = json.loads(content_text)
        assert "✅ Status" in parsed

    def test_create_beautiful_response_error(self):
        """Test create_beautiful_response for error case"""
        result = create_beautiful_response(
            operation="test_operation",
            success=False,
            error_message="Something went wrong",
            error_type="RuntimeError",
            suggestions=["Try again", "Check inputs"],
        )

        assert "content" in result
        assert "_meta" in result
        assert result["_meta"]["success"] is False
        assert result["isError"] is True

        # Check that content is valid JSON
        content_text = result["content"][0]["text"]
        parsed = json.loads(content_text)
        assert "❌ Status" in parsed
        assert "💭 Suggestions" in parsed

    def test_format_large_dataframe_preview(self):
        """Test that large DataFrames are limited in preview"""
        large_df = pd.DataFrame({"col1": range(1000), "col2": range(1000, 2000)})

        result = BeautifulFormatter._format_dataframe(large_df)

        assert "🔍 Preview" in result
        # Preview should be limited to 10 rows
        assert len(result["🔍 Preview"]) == 10

    def test_format_nested_dict(self):
        """Test formatting of nested dictionaries"""
        nested_dict = {
            "level1": {
                "level2": {"level3": "value"},
                "list_item": [1, 2, 3],
            },
            "simple": "text",
        }

        result = BeautifulFormatter._format_dict(nested_dict)

        assert "level1" in result
        assert isinstance(result["level1"], dict)
        assert "level2" in result["level1"]

    def test_numpy_types_in_nested_structures(self):
        """Test numpy type conversion in nested structures"""
        nested = {
            "array": np.array([1, 2, 3]),
            "int": np.int64(42),
            "float": np.float64(3.14),
            "list": [np.int32(1), np.int32(2)],
        }

        result = BeautifulFormatter._convert_numpy_types(nested)

        assert isinstance(result["array"], list)
        assert isinstance(result["int"], int)
        assert isinstance(result["float"], float)
        assert all(isinstance(x, int) for x in result["list"])

    def test_operation_name_formatting(self):
        """Test that operation names are formatted correctly"""
        operations = ["load_data", "process_file", "analyze_results"]

        for op in operations:
            result = BeautifulFormatter.format_success_response(operation=op, data={})
            # Check that underscores are replaced with spaces and title case
            assert "_" not in result["🎯 Operation"]
            assert result["🎯 Operation"].istitle()

    def test_timestamp_format(self):
        """Test that timestamp is in correct format"""
        result = BeautifulFormatter.format_success_response(operation="test", data={})

        timestamp = result["⏰ Timestamp"]
        # Try to parse it back
        parsed = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        assert isinstance(parsed, datetime)

    def test_empty_data_handling(self):
        """Test handling of empty data structures"""
        # Empty DataFrame
        empty_df = pd.DataFrame()
        result = BeautifulFormatter._format_dataframe(empty_df)
        assert "📏 Shape" in result

        # Empty dict
        empty_dict = {}
        result = BeautifulFormatter._format_dict(empty_dict)
        assert isinstance(result, dict)

        # Empty list
        empty_list = []
        result = BeautifulFormatter._format_list(empty_list)
        assert isinstance(result, list)
        assert len(result) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
