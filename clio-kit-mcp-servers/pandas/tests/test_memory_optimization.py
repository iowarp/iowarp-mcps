"""
Test cases for memory optimization capabilities.
"""

import pytest
import pandas as pd
import numpy as np
import tempfile
import os

from pandas_mcp.implementation.memory_optimization import (
    optimize_memory_usage,
    analyze_chunked_processing,
    get_memory_recommendations,
)


class TestMemoryOptimization:
    """Test suite for memory optimization"""

    @pytest.fixture
    def sample_data_mixed_types(self):
        """Create sample data with various types"""
        return pd.DataFrame(
            {
                # Integer columns with different ranges
                "small_int": np.random.randint(0, 100, 1000),  # Can be uint8
                "medium_int": np.random.randint(0, 50000, 1000),  # Can be uint16
                "large_int": np.random.randint(-1000, 1000, 1000),  # Can be int16
                "big_int": np.arange(1000),  # Currently int64
                # Float columns
                "float_col": np.random.rand(1000) * 100,  # Can be float32
                "precise_float": np.random.rand(1000) * 1e10,  # Needs float64
                # Categorical candidates
                "category_col": np.random.choice(["A", "B", "C", "D"], 1000),
                "low_cardinality": np.random.choice(["Type1", "Type2"], 1000),
                # Regular object column
                "unique_strings": [f"unique_{i}" for i in range(1000)],
            }
        )

    @pytest.fixture
    def temp_csv_file(self, sample_data_mixed_types):
        """Create a temporary CSV file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            sample_data_mixed_types.to_csv(f.name, index=False)
            yield f.name
        if os.path.exists(f.name):
            os.unlink(f.name)
            output_file = f.name.replace(".csv", "_optimized.csv")
            if os.path.exists(output_file):
                os.unlink(output_file)

    def test_optimize_memory_usage_success(self, temp_csv_file):
        """Test successful memory optimization"""
        result = optimize_memory_usage(temp_csv_file, optimize_dtypes=True)

        assert result["success"]
        assert "optimization_results" in result
        assert "column_memory_usage" in result
        assert "recommendations" in result
        assert result["optimization_results"]["memory_reduction_percentage"] >= 0
        assert os.path.exists(result["output_file"])

    def test_optimize_memory_usage_file_not_found(self):
        """Test with non-existent file"""
        result = optimize_memory_usage("nonexistent.csv")

        assert not result["success"]
        assert result["error_type"] == "FileNotFoundError"

    def test_optimize_memory_usage_no_optimization(self):
        """Test when optimization is disabled"""
        # Create simple data
        df = pd.DataFrame({"col1": [1, 2, 3], "col2": [4, 5, 6]})
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = optimize_memory_usage(temp_file, optimize_dtypes=False)

            assert result["success"]
            assert result["optimization_results"]["memory_reduction_percentage"] == 0.0
        finally:
            os.unlink(temp_file)
            output_file = temp_file.replace(".csv", "_optimized.csv")
            if os.path.exists(output_file):
                os.unlink(output_file)

    def test_optimize_dtypes_integers(self):
        """Test integer dtype optimization"""
        df = pd.DataFrame(
            {
                "uint8_candidate": np.random.randint(0, 200, 100),
                "uint16_candidate": np.random.randint(0, 60000, 100),
                "int8_candidate": np.random.randint(-100, 100, 100),
                "int16_candidate": np.random.randint(-30000, 30000, 100),
            }
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = optimize_memory_usage(temp_file, optimize_dtypes=True)

            assert result["success"]
            # Should have memory reduction due to dtype optimization
            assert result["optimization_results"]["memory_reduction_percentage"] > 0
        finally:
            os.unlink(temp_file)
            output_file = temp_file.replace(".csv", "_optimized.csv")
            if os.path.exists(output_file):
                os.unlink(output_file)

    def test_optimize_dtypes_floats(self):
        """Test float dtype optimization"""
        df = pd.DataFrame(
            {
                "float32_candidate": np.random.rand(100) * 100,
                "float64_needed": np.random.rand(100) * 1e10,
            }
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = optimize_memory_usage(temp_file, optimize_dtypes=True)

            assert result["success"]
            assert "column_memory_usage" in result
        finally:
            os.unlink(temp_file)
            output_file = temp_file.replace(".csv", "_optimized.csv")
            if os.path.exists(output_file):
                os.unlink(output_file)

    def test_optimize_dtypes_categorical(self):
        """Test categorical dtype optimization"""
        df = pd.DataFrame(
            {
                "low_cardinality": np.random.choice(["A", "B", "C"], 1000),
                "high_cardinality": [f"unique_{i}" for i in range(1000)],
            }
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = optimize_memory_usage(temp_file, optimize_dtypes=True)

            assert result["success"]
            # Low cardinality column should be converted to category
            assert result["optimization_results"]["memory_reduction_percentage"] > 0
        finally:
            os.unlink(temp_file)
            output_file = temp_file.replace(".csv", "_optimized.csv")
            if os.path.exists(output_file):
                os.unlink(output_file)

    def test_optimize_with_chunking(self, temp_csv_file):
        """Test optimization with chunk size specified"""
        result = optimize_memory_usage(
            temp_csv_file, optimize_dtypes=True, chunk_size=100
        )

        assert result["success"]
        assert result["chunked_processing"] is not None
        assert "estimated_chunks" in result["chunked_processing"]
        assert result["chunked_processing"]["chunk_size"] == 100

    def test_analyze_chunked_processing_success(self, temp_csv_file):
        """Test chunked processing analysis"""
        result = analyze_chunked_processing(temp_csv_file, chunk_size=100)

        assert "file_size_mb" in result
        assert "total_rows" in result
        assert "chunk_size" in result
        assert "estimated_chunks" in result
        assert result["chunk_size"] == 100

    def test_analyze_chunked_processing_large_chunks(self, temp_csv_file):
        """Test with large chunk size"""
        result = analyze_chunked_processing(temp_csv_file, chunk_size=5000)

        assert "estimated_chunks" in result
        # Should have fewer chunks with larger size
        assert result["estimated_chunks"] == 1

    def test_get_memory_recommendations_success(self, temp_csv_file):
        """Test getting memory recommendations"""
        result = get_memory_recommendations(temp_csv_file)

        assert result["success"]
        assert "recommendations" in result
        assert "current_memory_bytes" in result
        assert "potential_savings_bytes" in result
        assert isinstance(result["recommendations"], list)

    def test_get_memory_recommendations_file_not_found(self):
        """Test recommendations with non-existent file"""
        result = get_memory_recommendations("nonexistent.csv")

        assert not result["success"]
        assert result["error_type"] == "FileNotFoundError"

    def test_memory_recommendations_categorical(self):
        """Test recommendations for categorical conversion"""
        df = pd.DataFrame(
            {
                "category_candidate": np.random.choice(["A", "B", "C", "D"], 1000),
                "unique_values": [f"unique_{i}" for i in range(1000)],
            }
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = get_memory_recommendations(temp_file)

            assert result["success"]
            # Should recommend categorical for low cardinality column
            assert len(result["recommendations"]) > 0
            categorical_recs = [
                r
                for r in result["recommendations"]
                if r["recommended_type"] == "category"
            ]
            assert len(categorical_recs) > 0
        finally:
            os.unlink(temp_file)

    def test_memory_recommendations_numeric(self):
        """Test recommendations for numeric optimization"""
        df = pd.DataFrame(
            {
                "small_int": np.random.randint(0, 100, 1000),
                "large_float": np.random.rand(1000) * 100,
            }
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = get_memory_recommendations(temp_file)

            assert result["success"]
            assert "recommendations" in result
            # Should have recommendations for smaller numeric types
            numeric_recs = [
                r
                for r in result["recommendations"]
                if r["recommended_type"] in ["uint8", "float32"]
            ]
            assert len(numeric_recs) > 0
        finally:
            os.unlink(temp_file)

    def test_recommendations_for_sparse_data(self):
        """Test recommendations identify sparse data"""
        df = pd.DataFrame(
            {
                "sparse_col": np.concatenate([np.zeros(950), np.random.rand(50)]),
                "dense_col": np.random.rand(1000),
            }
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = optimize_memory_usage(temp_file, optimize_dtypes=True)

            assert result["success"]
            # Should recommend sparse arrays for sparse_col
            sparse_recommendations = [
                r for r in result["recommendations"] if "sparse" in r.lower()
            ]
            assert len(sparse_recommendations) > 0
        finally:
            os.unlink(temp_file)
            output_file = temp_file.replace(".csv", "_optimized.csv")
            if os.path.exists(output_file):
                os.unlink(output_file)

    def test_system_memory_info_included(self, temp_csv_file):
        """Test that system memory info is included"""
        result = optimize_memory_usage(temp_csv_file)

        assert result["success"]
        assert "system_memory" in result
        assert "total_gb" in result["system_memory"]
        assert "available_gb" in result["system_memory"]
        assert "percent_used" in result["system_memory"]

    def test_column_memory_breakdown(self, temp_csv_file):
        """Test column-level memory breakdown"""
        result = optimize_memory_usage(temp_csv_file, optimize_dtypes=True)

        assert result["success"]
        assert "column_memory_usage" in result

        for col_name, col_info in result["column_memory_usage"].items():
            assert "memory_mb" in col_info
            assert "dtype" in col_info
            assert "percentage_of_total" in col_info

    def test_optimization_log_tracking(self, temp_csv_file):
        """Test that optimization changes are logged"""
        result = optimize_memory_usage(temp_csv_file, optimize_dtypes=True)

        assert result["success"]
        assert "optimization_log" in result
        assert "initial_memory_mb" in result["optimization_log"]
        assert "optimizations_applied" in result["optimization_log"]

    def test_large_file_recommendations(self):
        """Test recommendations for large files"""
        # Create a large-ish dataset
        df = pd.DataFrame(
            {
                "col1": np.random.rand(10000),
                "col2": np.random.rand(10000),
                "col3": np.random.rand(10000),
            }
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = optimize_memory_usage(temp_file, optimize_dtypes=True)

            assert result["success"]
            # Should have recommendations
            assert "recommendations" in result
        finally:
            os.unlink(temp_file)
            output_file = temp_file.replace(".csv", "_optimized.csv")
            if os.path.exists(output_file):
                os.unlink(output_file)

    def test_empty_dataframe_handling(self):
        """Test handling of empty dataframes"""
        df = pd.DataFrame()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = optimize_memory_usage(temp_file)

            # Empty dataframes return error since there are no columns to parse
            assert not result["success"]
            assert result["error_type"] == "EmptyDataError"
        finally:
            os.unlink(temp_file)
            output_file = temp_file.replace(".csv", "_optimized.csv")
            if os.path.exists(output_file):
                os.unlink(output_file)

    def test_numeric_string_conversion(self):
        """Test conversion of numeric strings to actual numerics"""
        df = pd.DataFrame(
            {"numeric_strings": ["123", "456", "789"], "real_strings": ["A", "B", "C"]}
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = optimize_memory_usage(temp_file, optimize_dtypes=True)

            assert result["success"]
            # numeric_strings should be converted
            assert result["optimization_results"]["memory_reduction_percentage"] > 0
        finally:
            os.unlink(temp_file)
            output_file = temp_file.replace(".csv", "_optimized.csv")
            if os.path.exists(output_file):
                os.unlink(output_file)


class TestMemoryOptimizationEdgeCases:
    """Test edge cases for memory optimization to improve coverage"""

    def test_optimize_numeric_string_conversion_failure(self):
        """Test object columns that fail numeric conversion"""
        df = pd.DataFrame({"mixed_col": ["text", "more_text", "not_numeric"]})
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = optimize_memory_usage(temp_file, optimize_dtypes=True)
            assert result["success"]
            # Should convert to category since it's not numeric
        finally:
            os.unlink(temp_file)
            output_file = temp_file.replace(".csv", "_optimized.csv")
            if os.path.exists(output_file):
                os.unlink(output_file)

    def test_optimize_int32_conversion(self):
        """Test optimization to int32 dtype"""
        df = pd.DataFrame({"large_ints": [1000000, 2000000, 3000000]})
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = optimize_memory_usage(temp_file, optimize_dtypes=True)
            assert result["success"]
        finally:
            os.unlink(temp_file)
            output_file = temp_file.replace(".csv", "_optimized.csv")
            if os.path.exists(output_file):
                os.unlink(output_file)

    def test_optimize_large_memory_recommendations(self):
        """Test recommendations for large memory datasets"""
        # Create a large dataset > 1GB indicator
        df = pd.DataFrame({"col1": range(200000), "col2": ["x" * 100] * 200000})
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = optimize_memory_usage(temp_file, optimize_dtypes=True)
            assert result["success"]
        finally:
            os.unlink(temp_file)
            output_file = temp_file.replace(".csv", "_optimized.csv")
            if os.path.exists(output_file):
                os.unlink(output_file)

    def test_optimize_with_id_columns(self):
        """Test recommendations for ID columns"""
        df = pd.DataFrame(
            {"user_id": range(100), "product_id": range(100, 200), "value": range(100)}
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = optimize_memory_usage(temp_file, optimize_dtypes=True)
            assert result["success"]
        finally:
            os.unlink(temp_file)
            output_file = temp_file.replace(".csv", "_optimized.csv")
            if os.path.exists(output_file):
                os.unlink(output_file)

    def test_analyze_chunked_processing_exception(self):
        """Test analyze_chunked_processing exception handling"""
        result = analyze_chunked_processing("nonexistent_file.csv", chunk_size=1000)
        # Should return error in result
        assert "error" in result or "error_type" in result

    def test_get_memory_recommendations_numeric_conversion(self):
        """Test memory recommendations with numeric conversion opportunity"""
        df = pd.DataFrame({"numeric_strings": ["123", "456", "789"]})
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            result = get_memory_recommendations(temp_file)
            assert result["success"]
        finally:
            os.unlink(temp_file)

    def test_get_memory_recommendations_exception(self):
        """Test get_memory_recommendations exception handling"""
        result = get_memory_recommendations("nonexistent_file.csv")
        assert not result["success"]
        assert "error" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
