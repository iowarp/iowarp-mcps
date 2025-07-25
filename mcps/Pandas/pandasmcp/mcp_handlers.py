"""
MCP Handlers for Pandas MCP Server

This module provides handler functions that wrap the implementation modules
for testing and external integration purposes.
"""

import os
import sys
import logging
from typing import Any, Dict

# Add src directory to path for relative imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Import implementation modules
from implementation.data_io import load_data_file, save_data_file
from implementation.pandas_statistics import (
    get_statistical_summary,
    get_correlation_analysis,
)
from implementation.data_cleaning import handle_missing_data, clean_data
from implementation.data_profiling import profile_data
from implementation.filtering import filter_data
from implementation.memory_optimization import optimize_memory_usage

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_data_handler(file_path: str, **kwargs) -> dict:
    """Handler for loading data from files"""
    try:
        result = load_data_file(file_path, **kwargs)

        # Check if the operation was successful
        if isinstance(result, dict) and not result.get("success", True):
            # Operation failed, raise an exception with the error message
            error_msg = result.get("error", "Unknown error occurred")
            raise Exception(error_msg)

        return {"content": result, "_meta": {"tool": "load_data", "success": True}}
    except Exception as e:
        logger.error(f"Error loading data from {file_path}: {str(e)}")
        return {
            "content": f"Error loading data: {str(e)}",
            "_meta": {"tool": "load_data", "success": False, "error": str(e)},
            "isError": True,
        }


def save_data_handler(data: dict, file_path: str, **kwargs) -> dict:
    """Handler for saving data to files"""
    try:
        result = save_data_file(data, file_path, **kwargs)
        return {"content": result, "_meta": {"tool": "save_data", "success": True}}
    except Exception as e:
        logger.error(f"Error saving data to {file_path}: {str(e)}")
        return {
            "content": f"Error saving data: {str(e)}",
            "_meta": {"tool": "save_data", "success": False, "error": str(e)},
            "isError": True,
        }


def statistical_summary_handler(file_path: str, **kwargs) -> dict:
    """Handler for statistical summary analysis"""
    try:
        result = get_statistical_summary(file_path, **kwargs)
        return {
            "content": result,
            "_meta": {"tool": "statistical_summary", "success": True},
        }
    except Exception as e:
        logger.error(f"Error generating statistical summary for {file_path}: {str(e)}")
        return {
            "content": f"Error generating statistical summary: {str(e)}",
            "_meta": {"tool": "statistical_summary", "success": False, "error": str(e)},
            "isError": True,
        }


def correlation_analysis_handler(file_path: str, **kwargs) -> dict:
    """Handler for correlation analysis"""
    try:
        result = get_correlation_analysis(file_path, **kwargs)
        return {
            "content": result,
            "_meta": {"tool": "correlation_analysis", "success": True},
        }
    except Exception as e:
        logger.error(f"Error performing correlation analysis for {file_path}: {str(e)}")
        return {
            "content": f"Error performing correlation analysis: {str(e)}",
            "_meta": {
                "tool": "correlation_analysis",
                "success": False,
                "error": str(e),
            },
            "isError": True,
        }


def handle_missing_data_handler(
    file_path: str, strategy: str = "detect", **kwargs
) -> dict:
    """Handler for missing data operations"""
    try:
        result = handle_missing_data(file_path, strategy=strategy, **kwargs)
        return {
            "content": result,
            "_meta": {"tool": "handle_missing_data", "success": True},
        }
    except Exception as e:
        logger.error(f"Error handling missing data for {file_path}: {str(e)}")
        return {
            "content": f"Error handling missing data: {str(e)}",
            "_meta": {"tool": "handle_missing_data", "success": False, "error": str(e)},
            "isError": True,
        }


def clean_data_handler(file_path: str, **kwargs) -> dict:
    """Handler for data cleaning operations"""
    try:
        result = clean_data(file_path, **kwargs)
        return {"content": result, "_meta": {"tool": "clean_data", "success": True}}
    except Exception as e:
        logger.error(f"Error cleaning data for {file_path}: {str(e)}")
        return {
            "content": f"Error cleaning data: {str(e)}",
            "_meta": {"tool": "clean_data", "success": False, "error": str(e)},
            "isError": True,
        }


def profile_data_handler(file_path: str, **kwargs) -> dict:
    """Handler for data profiling operations"""
    try:
        result = profile_data(file_path, **kwargs)
        return {"content": result, "_meta": {"tool": "profile_data", "success": True}}
    except Exception as e:
        logger.error(f"Error profiling data for {file_path}: {str(e)}")
        return {
            "content": f"Error profiling data: {str(e)}",
            "_meta": {"tool": "profile_data", "success": False, "error": str(e)},
            "isError": True,
        }


def filter_data_handler(
    file_path: str, filter_conditions: Dict[str, Any], **kwargs
) -> dict:
    """Handler for data filtering operations"""
    try:
        result = filter_data(file_path, filter_conditions, **kwargs)
        return {"content": result, "_meta": {"tool": "filter_data", "success": True}}
    except Exception as e:
        logger.error(f"Error filtering data for {file_path}: {str(e)}")
        return {
            "content": f"Error filtering data: {str(e)}",
            "_meta": {"tool": "filter_data", "success": False, "error": str(e)},
            "isError": True,
        }


def optimize_memory_handler(file_path: str, **kwargs) -> dict:
    """Handler for memory optimization operations"""
    try:
        result = optimize_memory_usage(file_path, **kwargs)
        return {
            "content": result,
            "_meta": {"tool": "optimize_memory", "success": True},
        }
    except Exception as e:
        logger.error(f"Error optimizing memory for {file_path}: {str(e)}")
        return {
            "content": f"Error optimizing memory: {str(e)}",
            "_meta": {"tool": "optimize_memory", "success": False, "error": str(e)},
            "isError": True,
        }
