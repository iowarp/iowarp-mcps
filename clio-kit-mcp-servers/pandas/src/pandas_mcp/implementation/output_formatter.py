"""
Beautiful output formatting utilities for pandas MCP server.
Provides structured, readable, and visually appealing output formatting.
"""

import json
from typing import Any, Dict, List, Optional
from datetime import datetime
import pandas as pd
import numpy as np


class BeautifulFormatter:
    """
    A comprehensive formatter for creating beautiful, structured output
    that enhances readability and provides consistent formatting across
    all pandas MCP operations.
    """

    @staticmethod
    def format_success_response(
        operation: str,
        data: Any,
        summary: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
        insights: Optional[List[str]] = None,
    ) -> Dict:
        """
        Format a successful operation response with beautiful structure.

        Args:
            operation: Name of the operation performed
            data: Main data result
            summary: Summary statistics or information
            metadata: Additional metadata about the operation
            insights: Key insights or recommendations

        Returns:
            Beautifully formatted response dictionary
        """
        response = {
            "🎯 Operation": operation.replace("_", " ").title(),
            "✅ Status": "Success",
            "⏰ Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "📊 Results": BeautifulFormatter._format_data(data),
        }

        if summary:
            response["📈 Summary"] = BeautifulFormatter._format_summary(summary)

        if metadata:
            response["🔍 Metadata"] = BeautifulFormatter._format_metadata(metadata)

        if insights:
            response["💡 Insights"] = BeautifulFormatter._format_insights(insights)

        return response

    @staticmethod
    def format_error_response(
        operation: str,
        error_message: str,
        error_type: str,
        suggestions: Optional[List[str]] = None,
    ) -> Dict:
        """
        Format an error response with helpful information.

        Args:
            operation: Name of the operation that failed
            error_message: Detailed error message
            error_type: Type of error that occurred
            suggestions: Suggested solutions or next steps

        Returns:
            Beautifully formatted error response
        """
        response: Dict[str, Any] = {
            "🎯 Operation": operation.replace("_", " ").title(),
            "❌ Status": "Error",
            "⏰ Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "🚨 Error Type": error_type,
            "📝 Error Message": error_message,
        }

        if suggestions:
            response["💭 Suggestions"] = BeautifulFormatter._format_suggestions(
                suggestions
            )

        return response

    @staticmethod
    def _format_data(data: Any) -> Any:
        """Format main data with appropriate structure."""
        if isinstance(data, pd.DataFrame):
            return BeautifulFormatter._format_dataframe(data)
        elif isinstance(data, dict):
            return BeautifulFormatter._format_dict(data)
        elif isinstance(data, list):
            return BeautifulFormatter._format_list(data)
        else:
            return BeautifulFormatter._convert_numpy_types(data)

    @staticmethod
    def _format_dataframe(df: pd.DataFrame) -> Dict:
        """Format DataFrame with structure and preview."""
        preview_rows = min(10, len(df))

        return {
            "📏 Shape": f"{df.shape[0]:,} rows × {df.shape[1]:,} columns",
            "📋 Columns": df.columns.tolist(),
            "🔍 Preview": BeautifulFormatter._convert_numpy_types(
                df.head(preview_rows).to_dict("records")
            ),
            "📊 Data Types": df.dtypes.astype(str).to_dict(),
            "💾 Memory Usage": f"{df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB",
        }

    @staticmethod
    def _format_dict(data: Dict) -> Dict:
        """Format dictionary with nested structure handling."""
        formatted = {}
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                formatted[key] = BeautifulFormatter._format_data(value)
            else:
                formatted[key] = BeautifulFormatter._convert_numpy_types(value)
        return formatted

    @staticmethod
    def _format_list(data: List) -> List:
        """Format list with appropriate item formatting."""
        return [BeautifulFormatter._convert_numpy_types(item) for item in data]

    @staticmethod
    def _format_summary(summary: Dict) -> Dict:
        """Format summary information with visual enhancements."""
        formatted_summary = {}

        for key, value in summary.items():
            # Add appropriate emoji prefixes for common summary items
            if "count" in key.lower():
                formatted_key = f"📊 {key.replace('_', ' ').title()}"
            elif "time" in key.lower():
                formatted_key = f"⏱️ {key.replace('_', ' ').title()}"
            elif "size" in key.lower() or "memory" in key.lower():
                formatted_key = f"💾 {key.replace('_', ' ').title()}"
            elif "error" in key.lower():
                formatted_key = f"🚨 {key.replace('_', ' ').title()}"
            elif "success" in key.lower():
                formatted_key = f"✅ {key.replace('_', ' ').title()}"
            else:
                formatted_key = f"📈 {key.replace('_', ' ').title()}"

            formatted_summary[formatted_key] = BeautifulFormatter._convert_numpy_types(
                value
            )

        return formatted_summary

    @staticmethod
    def _format_metadata(metadata: Dict) -> Dict:
        """Format metadata with organized structure."""
        formatted_metadata = {}

        for key, value in metadata.items():
            formatted_key = f"🔍 {key.replace('_', ' ').title()}"
            formatted_metadata[formatted_key] = BeautifulFormatter._convert_numpy_types(
                value
            )

        return formatted_metadata

    @staticmethod
    def _format_insights(insights: List[str]) -> List[str]:
        """Format insights with visual indicators."""
        return [f"💡 {insight}" for insight in insights]

    @staticmethod
    def _format_suggestions(suggestions: List[str]) -> List[str]:
        """Format suggestions with helpful indicators."""
        return [f"💭 {suggestion}" for suggestion in suggestions]

    @staticmethod
    def _convert_numpy_types(obj: Any) -> Any:
        """Convert numpy types to Python native types for JSON serialization."""
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.Series):
            return [BeautifulFormatter._convert_numpy_types(item) for item in obj]
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, np.str_):
            return str(obj)
        elif isinstance(obj, dict):
            return {
                k: BeautifulFormatter._convert_numpy_types(v) for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [BeautifulFormatter._convert_numpy_types(item) for item in obj]
        elif pd.isna(obj):
            return None
        else:
            return obj

    @staticmethod
    def format_statistical_summary(stats: Dict) -> Dict:
        """Format statistical summary with enhanced readability."""
        formatted_stats: Dict[str, Any] = {}

        # Format descriptive statistics
        if "descriptive_stats" in stats:
            formatted_stats["📊 Descriptive Statistics"] = {}
            for column, column_stats in stats["descriptive_stats"].items():
                formatted_stats["📊 Descriptive Statistics"][column] = {
                    "📈 Count": f"{column_stats.get('count', 0):,}",
                    "📊 Mean": f"{column_stats.get('mean', 0):.4f}",
                    "📊 Std Dev": f"{column_stats.get('std', 0):.4f}",
                    "📊 Min": f"{column_stats.get('min', 0):.4f}",
                    "📊 25%": f"{column_stats.get('25%', 0):.4f}",
                    "📊 50%": f"{column_stats.get('50%', 0):.4f}",
                    "📊 75%": f"{column_stats.get('75%', 0):.4f}",
                    "📊 Max": f"{column_stats.get('max', 0):.4f}",
                }

        # Format missing values
        if "missing_values" in stats:
            formatted_stats["🔍 Missing Values"] = {}
            for column, missing_count in stats["missing_values"].items():
                percentage = (missing_count / stats.get("total_rows", 1)) * 100
                formatted_stats["🔍 Missing Values"][column] = (
                    f"{missing_count:,} ({percentage:.1f}%)"
                )

        # Format data types
        if "data_types" in stats:
            formatted_stats["🏷️ Data Types"] = stats["data_types"]

        return formatted_stats

    @staticmethod
    def format_correlation_matrix(corr_matrix: Dict) -> Dict:
        """Format correlation matrix with visual enhancements."""
        formatted_corr: Dict[str, Any] = {
            "🔗 Correlation Matrix": {},
            "🔍 Strong Correlations": [],
        }

        # Format correlation matrix
        for col1, correlations in corr_matrix.items():
            formatted_corr["🔗 Correlation Matrix"][col1] = {
                col2: f"{corr:.4f}" for col2, corr in correlations.items()
            }

        # Identify strong correlations
        strong_correlations = []
        for col1, correlations in corr_matrix.items():
            for col2, corr in correlations.items():
                if col1 != col2 and abs(corr) > 0.7:
                    strength = "Strong" if abs(corr) > 0.8 else "Moderate"
                    direction = "Positive" if corr > 0 else "Negative"
                    strong_correlations.append(
                        f"{strength} {direction} correlation between {col1} and {col2}: {corr:.4f}"
                    )

        formatted_corr["🔍 Strong Correlations"] = strong_correlations[:10]  # Top 10

        return formatted_corr

    @staticmethod
    def format_data_quality_report(quality_report: Dict) -> Dict:
        """Format data quality report with clear indicators."""
        formatted_report: Dict[str, Any] = {}

        # Overall quality score
        if "overall_score" in quality_report:
            score = quality_report["overall_score"]
            if score >= 0.9:
                indicator = "🟢 Excellent"
            elif score >= 0.7:
                indicator = "🟡 Good"
            elif score >= 0.5:
                indicator = "🟠 Fair"
            else:
                indicator = "🔴 Poor"

            formatted_report["📊 Overall Quality Score"] = f"{indicator} ({score:.1%})"

        # Quality metrics
        if "quality_metrics" in quality_report:
            formatted_report["📋 Quality Metrics"] = {}
            for metric, value in quality_report["quality_metrics"].items():
                formatted_report["📋 Quality Metrics"][
                    f"📊 {metric.replace('_', ' ').title()}"
                ] = (
                    f"{value:.1%}"
                    if isinstance(value, float) and value <= 1
                    else str(value)
                )

        # Issues found
        if "issues" in quality_report:
            formatted_report["🚨 Issues Found"] = [
                f"⚠️ {issue}" for issue in quality_report["issues"]
            ]

        # Recommendations
        if "recommendations" in quality_report:
            formatted_report["💡 Recommendations"] = [
                f"💭 {rec}" for rec in quality_report["recommendations"]
            ]

        return formatted_report


def create_beautiful_response(
    operation: str,
    success: bool,
    data: Any = None,
    summary: Optional[Dict] = None,
    metadata: Optional[Dict] = None,
    insights: Optional[List[str]] = None,
    error_message: Optional[str] = None,
    error_type: Optional[str] = None,
    suggestions: Optional[List[str]] = None,
) -> Dict:
    """
    Create a beautifully formatted response for any pandas MCP operation.

    Args:
        operation: Name of the operation
        success: Whether the operation was successful
        data: Main result data
        summary: Summary information
        metadata: Additional metadata
        insights: Key insights or findings
        error_message: Error message if operation failed
        error_type: Type of error if operation failed
        suggestions: Suggested solutions if operation failed

    Returns:
        Beautifully formatted response dictionary
    """
    if success:
        response = BeautifulFormatter.format_success_response(
            operation=operation,
            data=data,
            summary=summary,
            metadata=metadata,
            insights=insights,
        )
    else:
        response = BeautifulFormatter.format_error_response(
            operation=operation,
            error_message=error_message or "Unknown error occurred",
            error_type=error_type or "UnknownError",
            suggestions=suggestions,
        )

    return {
        "content": [{"text": json.dumps(response, indent=2, ensure_ascii=False)}],
        "_meta": {
            "tool": operation,
            "success": success,
            "timestamp": datetime.now().isoformat(),
        },
        "isError": not success,
    }
