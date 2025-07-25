"""
Data validation and hypothesis testing capabilities.
"""

import pandas as pd
import os
from scipy import stats
from typing import Optional, Any, Dict
import traceback


def validate_data(
    file_path: str, validation_rules: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Validate data against specified rules.

    Args:
        file_path: Path to the data file
        validation_rules: Dictionary of column: rules pairs

    Returns:
        Dictionary with validation results
    """
    try:
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "error_type": "FileNotFoundError",
            }

        # Load data
        df = pd.read_csv(file_path)

        validation_results: Dict[str, Any] = {}
        overall_valid = True

        for column, rules in validation_rules.items():
            if column not in df.columns:
                validation_results[column] = {
                    "valid": False,
                    "error": f"Column '{column}' not found in dataset",
                }
                overall_valid = False
                continue

            column_results: Dict[str, Any] = {
                "valid": True,
                "violations": [],
                "statistics": {},
            }

            col_data = df[column]

            # Range validation
            if "min_value" in rules:
                min_violations = col_data < rules["min_value"]
                if min_violations.any():
                    violation_count = min_violations.sum()
                    column_results["violations"].append(
                        {
                            "rule": "min_value",
                            "expected": rules["min_value"],
                            "violation_count": int(violation_count),
                            "violation_percentage": round(
                                violation_count / len(col_data) * 100, 2
                            ),
                        }
                    )
                    column_results["valid"] = False

            if "max_value" in rules:
                max_violations = col_data > rules["max_value"]
                if max_violations.any():
                    violation_count = max_violations.sum()
                    column_results["violations"].append(
                        {
                            "rule": "max_value",
                            "expected": rules["max_value"],
                            "violation_count": int(violation_count),
                            "violation_percentage": round(
                                violation_count / len(col_data) * 100, 2
                            ),
                        }
                    )
                    column_results["valid"] = False

            # Data type validation
            if "dtype" in rules:
                expected_dtype = rules["dtype"]
                if str(col_data.dtype) != expected_dtype:
                    column_results["violations"].append(
                        {
                            "rule": "dtype",
                            "expected": expected_dtype,
                            "actual": str(col_data.dtype),
                        }
                    )
                    column_results["valid"] = False

            # Null value validation
            if "allow_null" in rules:
                allow_null = rules["allow_null"]
                has_null = col_data.isnull().any()
                if not allow_null and has_null:
                    null_count = col_data.isnull().sum()
                    column_results["violations"].append(
                        {
                            "rule": "allow_null",
                            "expected": allow_null,
                            "null_count": int(null_count),
                            "null_percentage": round(
                                null_count / len(col_data) * 100, 2
                            ),
                        }
                    )
                    column_results["valid"] = False

            # Unique values validation
            if "unique" in rules:
                should_be_unique = rules["unique"]
                has_duplicates = col_data.duplicated().any()
                if should_be_unique and has_duplicates:
                    duplicate_count = col_data.duplicated().sum()
                    column_results["violations"].append(
                        {
                            "rule": "unique",
                            "expected": should_be_unique,
                            "duplicate_count": int(duplicate_count),
                            "duplicate_percentage": round(
                                duplicate_count / len(col_data) * 100, 2
                            ),
                        }
                    )
                    column_results["valid"] = False

            # Pattern validation (for string columns)
            if "pattern" in rules and col_data.dtype == "object":
                pattern = rules["pattern"]
                try:
                    pattern_matches = col_data.str.match(pattern, na=False)
                    pattern_violations = ~pattern_matches
                    if pattern_violations.any():
                        violation_count = pattern_violations.sum()
                        column_results["violations"].append(
                            {
                                "rule": "pattern",
                                "expected": pattern,
                                "violation_count": int(violation_count),
                                "violation_percentage": round(
                                    violation_count / len(col_data) * 100, 2
                                ),
                            }
                        )
                        column_results["valid"] = False
                except Exception as e:
                    column_results["violations"].append(
                        {
                            "rule": "pattern",
                            "error": f"Pattern validation failed: {str(e)}",
                        }
                    )
                    column_results["valid"] = False

            # Add column statistics
            if col_data.dtype in ["int64", "float64"]:
                column_results["statistics"] = {
                    "count": int(col_data.count()),
                    "mean": float(col_data.mean()),
                    "std": float(col_data.std()),
                    "min": float(col_data.min()),
                    "max": float(col_data.max()),
                    "null_count": int(col_data.isnull().sum()),
                }
            else:
                column_results["statistics"] = {
                    "count": int(col_data.count()),
                    "unique_count": int(col_data.nunique()),
                    "null_count": int(col_data.isnull().sum()),
                    "most_frequent": str(col_data.mode().iloc[0])
                    if not col_data.mode().empty
                    else None,
                }

            validation_results[column] = column_results

            if not column_results["valid"]:
                overall_valid = False

        # Generate summary
        total_columns = len(validation_rules)
        valid_columns = sum(
            1 for result in validation_results.values() if result["valid"]
        )
        total_violations = sum(
            len(result["violations"]) for result in validation_results.values()
        )

        summary = {
            "overall_valid": overall_valid,
            "total_columns_validated": total_columns,
            "valid_columns": valid_columns,
            "invalid_columns": total_columns - valid_columns,
            "total_violations": total_violations,
        }

        return {
            "success": True,
            "file_path": file_path,
            "validation_summary": summary,
            "validation_results": validation_results,
            "message": f"Validation completed: {valid_columns}/{total_columns} columns valid",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc(),
        }


def hypothesis_testing(
    file_path: str,
    test_type: str,
    column1: str,
    column2: Optional[str] = None,
    alpha: float = 0.05,
) -> dict:
    """
    Perform hypothesis testing on data.

    Args:
        file_path: Path to the data file
        test_type: Type of test (t_test, chi_square, anova, correlation)
        column1: First column for testing
        column2: Second column for testing (if needed)
        alpha: Significance level

    Returns:
        Dictionary with hypothesis test results
    """
    try:
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "error_type": "FileNotFoundError",
            }

        # Load data
        df = pd.read_csv(file_path)

        # Check if columns exist
        if column1 not in df.columns:
            return {
                "success": False,
                "error": f"Column '{column1}' not found",
                "error_type": "ValueError",
            }

        if column2 and column2 not in df.columns:
            return {
                "success": False,
                "error": f"Column '{column2}' not found",
                "error_type": "ValueError",
            }

        # Perform hypothesis tests
        if test_type in ["t_test", "ttest_ind", "ttest"]:
            if column2 is None:
                # One-sample t-test
                data = df[column1].dropna()
                statistic, p_value = stats.ttest_1samp(data, 0)
                test_info = {
                    "test_type": "one_sample_t_test",
                    "null_hypothesis": "Mean equals 0",
                    "sample_size": len(data),
                    "sample_mean": float(data.mean()),
                    "sample_std": float(data.std()),
                }
            else:
                # Two-sample t-test
                data1 = df[column1].dropna()
                data2 = df[column2].dropna()
                statistic, p_value = stats.ttest_ind(data1, data2)
                test_info = {
                    "test_type": "two_sample_t_test",
                    "null_hypothesis": "Means are equal",
                    "sample1_size": len(data1),
                    "sample1_mean": float(data1.mean()),
                    "sample1_std": float(data1.std()),
                    "sample2_size": len(data2),
                    "sample2_mean": float(data2.mean()),
                    "sample2_std": float(data2.std()),
                }

        elif test_type == "chi_square":
            if column2 is None:
                # Goodness of fit test
                observed = df[column1].value_counts()
                expected = [len(df) / len(observed)] * len(observed)
                statistic, p_value = stats.chisquare(observed, expected)
                test_info = {
                    "test_type": "chi_square_goodness_of_fit",
                    "null_hypothesis": "Data follows uniform distribution",
                    "categories": len(observed),
                    "total_observations": len(df),
                }
            else:
                # Test of independence
                contingency_table = pd.crosstab(df[column1], df[column2])
                statistic, p_value, dof, expected = stats.chi2_contingency(
                    contingency_table
                )
                test_info = {
                    "test_type": "chi_square_independence",
                    "null_hypothesis": "Variables are independent",
                    "degrees_of_freedom": dof,
                    "contingency_table": contingency_table.to_dict(),
                }

        elif test_type == "correlation":
            if column2 is None:
                return {
                    "success": False,
                    "error": "Correlation test requires two columns",
                    "error_type": "ValueError",
                }

            # Pearson correlation test
            data1 = df[column1].dropna()
            data2 = df[column2].dropna()

            # Align data (keep only rows where both columns have values)
            aligned_data = df[[column1, column2]].dropna()

            correlation, p_value = stats.pearsonr(
                aligned_data[column1], aligned_data[column2]
            )
            statistic = correlation

            test_info = {
                "test_type": "pearson_correlation",
                "null_hypothesis": "No correlation (r = 0)",
                "sample_size": len(aligned_data),
                "correlation_coefficient": float(correlation),
            }

        elif test_type == "anova":
            if column2 is None:
                return {
                    "success": False,
                    "error": "ANOVA test requires grouping variable",
                    "error_type": "ValueError",
                }

            # One-way ANOVA
            groups = df.groupby(column2)[column1].apply(list)
            statistic, p_value = stats.f_oneway(*groups)

            test_info = {
                "test_type": "one_way_anova",
                "null_hypothesis": "All group means are equal",
                "number_of_groups": len(groups),
                "group_sizes": {
                    str(group): len(data) for group, data in groups.items()
                },
            }

        else:
            return {
                "success": False,
                "error": f"Unknown test type: {test_type}",
                "error_type": "ValueError",
            }

        # Interpret results
        is_significant = p_value < alpha
        interpretation = {
            "statistic": float(statistic),
            "p_value": float(p_value),
            "alpha": alpha,
            "is_significant": is_significant,
            "conclusion": "Reject null hypothesis"
            if is_significant
            else "Fail to reject null hypothesis",
            "effect_size": "large"
            if p_value < 0.01
            else "medium"
            if p_value < 0.05
            else "small",
        }

        return {
            "success": True,
            "file_path": file_path,
            "test_info": test_info,
            "results": interpretation,
            "message": f"{test_type} test completed: {'significant' if is_significant else 'not significant'} (p={p_value:.4f})",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc(),
        }
