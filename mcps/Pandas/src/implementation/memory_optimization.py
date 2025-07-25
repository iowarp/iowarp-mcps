"""
Memory optimization capabilities for efficient data processing.
"""
import pandas as pd
import numpy as np
import os
import psutil
from typing import Optional, List, Any, Dict
import traceback


def optimize_memory_usage(file_path: str, optimize_dtypes: bool = True,
                         chunk_size: Optional[int] = None) -> dict:
    """
    Optimize memory usage through efficient dtypes and chunking.
    
    Args:
        file_path: Path to the data file
        optimize_dtypes: Whether to optimize data types
        chunk_size: Size for chunked processing
    
    Returns:
        Dictionary with optimization results
    """
    try:
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "error_type": "FileNotFoundError"
            }
        
        # Get system memory info
        memory_info = psutil.virtual_memory()
        system_memory = {
            "total_gb": round(memory_info.total / (1024**3), 2),
            "available_gb": round(memory_info.available / (1024**3), 2),
            "percent_used": memory_info.percent
        }
        
        # Load data
        df = pd.read_csv(file_path)
        
        # Get initial memory usage
        initial_memory = df.memory_usage(deep=True).sum()
        initial_memory_mb = initial_memory / (1024 * 1024)
        
        optimization_log = {
            "initial_memory_mb": round(initial_memory_mb, 2),
            "initial_shape": df.shape,
            "optimizations_applied": []
        }
        
        optimized_df = df.copy()
        
        if optimize_dtypes:
            # Optimize data types
            dtype_changes = {}
            
            for col in optimized_df.columns:
                original_dtype = optimized_df[col].dtype
                
                if optimized_df[col].dtype == 'object':
                    # Try to convert to numeric
                    try:
                        numeric_series = pd.to_numeric(optimized_df[col], errors='coerce')
                        if not numeric_series.isnull().all():
                            optimized_df[col] = numeric_series
                            dtype_changes[col] = f"object -> {numeric_series.dtype}"
                            continue
                    except:
                        pass
                    
                    # Try to convert to category if it has repeated values
                    unique_ratio = optimized_df[col].nunique() / len(optimized_df[col])
                    if unique_ratio < 0.5:  # Less than 50% unique values
                        optimized_df[col] = optimized_df[col].astype('category')
                        dtype_changes[col] = "object -> category"
                        continue
                
                elif optimized_df[col].dtype in ['int64', 'float64']:
                    # Optimize numeric types
                    if optimized_df[col].dtype == 'int64':
                        # Check if we can use smaller int types
                        col_min = optimized_df[col].min()
                        col_max = optimized_df[col].max()
                        
                        if col_min >= 0:  # Unsigned integers
                            if col_max <= 255:
                                optimized_df[col] = optimized_df[col].astype('uint8')
                                dtype_changes[col] = "int64 -> uint8"
                            elif col_max <= 65535:
                                optimized_df[col] = optimized_df[col].astype('uint16')
                                dtype_changes[col] = "int64 -> uint16"
                            elif col_max <= 4294967295:
                                optimized_df[col] = optimized_df[col].astype('uint32')
                                dtype_changes[col] = "int64 -> uint32"
                        else:  # Signed integers
                            if col_min >= -128 and col_max <= 127:
                                optimized_df[col] = optimized_df[col].astype('int8')
                                dtype_changes[col] = "int64 -> int8"
                            elif col_min >= -32768 and col_max <= 32767:
                                optimized_df[col] = optimized_df[col].astype('int16')
                                dtype_changes[col] = "int64 -> int16"
                            elif col_min >= -2147483648 and col_max <= 2147483647:
                                optimized_df[col] = optimized_df[col].astype('int32')
                                dtype_changes[col] = "int64 -> int32"
                    
                    elif optimized_df[col].dtype == 'float64':
                        # Check if we can use float32
                        if not optimized_df[col].isnull().all():
                            # Check if values fit in float32 range
                            col_min = optimized_df[col].min()
                            col_max = optimized_df[col].max()
                            
                            if (col_min >= np.finfo(np.float32).min and 
                                col_max <= np.finfo(np.float32).max):
                                # Check if precision is preserved
                                float32_series = optimized_df[col].astype('float32')
                                if np.allclose(optimized_df[col], float32_series, equal_nan=True):
                                    optimized_df[col] = float32_series
                                    dtype_changes[col] = "float64 -> float32"
            
            optimization_log["optimizations_applied"].append({
                "optimization": "dtype_optimization",
                "changes": dtype_changes
            })
        
        # Get final memory usage
        final_memory = optimized_df.memory_usage(deep=True).sum()
        final_memory_mb = final_memory / (1024 * 1024)
        
        memory_reduction = ((initial_memory - final_memory) / initial_memory) * 100
        
        # Save optimized data
        output_path = file_path.replace('.csv', '_optimized.csv')
        optimized_df.to_csv(output_path, index=False)
        
        # Chunked processing analysis
        chunked_info = None
        if chunk_size:
            chunked_info = analyze_chunked_processing(file_path, chunk_size)
        
        # Memory usage by column
        column_memory = {}
        for col in optimized_df.columns:
            col_memory = optimized_df[col].memory_usage(deep=True)
            column_memory[col] = {
                "memory_mb": round(col_memory / (1024 * 1024), 4),
                "dtype": str(optimized_df[col].dtype),
                "percentage_of_total": round((col_memory / final_memory) * 100, 2)
            }
        
        # Recommendations
        recommendations = []
        
        if memory_reduction < 10:
            recommendations.append("Consider using categorical data types for string columns with repeated values")
        
        if final_memory_mb > 1000:  # > 1GB
            recommendations.append("Consider using chunked processing for large datasets")
        
        if any(col.endswith('_id') for col in optimized_df.columns):
            recommendations.append("ID columns might be better stored as categorical or string types")
        
        # Check for sparse data
        for col in optimized_df.select_dtypes(include=[np.number]).columns:
            zeros_percentage = (optimized_df[col] == 0).sum() / len(optimized_df) * 100
            if zeros_percentage > 90:
                recommendations.append(f"Column '{col}' has {zeros_percentage:.1f}% zeros - consider sparse arrays")
        
        return {
            "success": True,
            "file_path": file_path,
            "output_file": output_path,
            "system_memory": system_memory,
            "optimization_results": {
                "initial_memory_mb": round(initial_memory_mb, 2),
                "final_memory_mb": round(final_memory_mb, 2),
                "memory_reduction_mb": round(initial_memory_mb - final_memory_mb, 2),
                "memory_reduction_percentage": round(memory_reduction, 2),
                "shape": optimized_df.shape
            },
            "column_memory_usage": column_memory,
            "optimization_log": optimization_log,
            "chunked_processing": chunked_info,
            "recommendations": recommendations,
            "message": f"Memory optimized from {initial_memory_mb:.2f}MB to {final_memory_mb:.2f}MB ({memory_reduction:.1f}% reduction)"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc()
        }


def analyze_chunked_processing(file_path: str, chunk_size: int) -> dict:
    """
    Analyze how the data would be processed in chunks.
    
    Args:
        file_path: Path to the data file
        chunk_size: Size of each chunk
    
    Returns:
        Dictionary with chunked processing analysis
    """
    try:
        # Get file size
        file_size = os.path.getsize(file_path)
        file_size_mb = file_size / (1024 * 1024)
        
        # Estimate number of chunks
        with open(file_path, 'r') as f:
            # Count lines (approximately)
            line_count = sum(1 for _ in f)
        
        num_chunks = (line_count - 1) // chunk_size + 1  # -1 for header
        
        # Estimate memory usage per chunk
        df_sample = pd.read_csv(file_path, nrows=min(1000, chunk_size))
        sample_memory = df_sample.memory_usage(deep=True).sum()
        estimated_chunk_memory = (sample_memory / len(df_sample)) * chunk_size
        estimated_chunk_memory_mb = estimated_chunk_memory / (1024 * 1024)
        
        return {
            "file_size_mb": round(file_size_mb, 2),
            "total_rows": line_count - 1,  # Exclude header
            "chunk_size": chunk_size,
            "estimated_chunks": num_chunks,
            "estimated_memory_per_chunk_mb": round(estimated_chunk_memory_mb, 2),
            "processing_strategy": "sequential" if estimated_chunk_memory_mb < 100 else "careful_sequential"
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "error_type": type(e).__name__
        }


def get_memory_recommendations(file_path: str) -> dict:
    """
    Get memory optimization recommendations for a dataset.
    
    Args:
        file_path: Path to the data file
    
    Returns:
        Dictionary with memory recommendations
    """
    try:
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "error_type": "FileNotFoundError"
            }
        
        # Load a sample to analyze
        df_sample = pd.read_csv(file_path, nrows=1000)
        
        recommendations = []
        potential_savings = 0
        
        # Analyze each column
        for col in df_sample.columns:
            col_type = df_sample[col].dtype
            col_memory = df_sample[col].memory_usage(deep=True)
            
            if col_type == 'object':
                # Check if it can be converted to category
                unique_ratio = df_sample[col].nunique() / len(df_sample[col])
                if unique_ratio < 0.5:
                    category_memory = df_sample[col].astype('category').memory_usage(deep=True)
                    savings = col_memory - category_memory
                    if savings > 0:
                        recommendations.append({
                            "column": col,
                            "current_type": str(col_type),
                            "recommended_type": "category",
                            "reason": f"Only {unique_ratio:.1%} unique values",
                            "estimated_savings_bytes": int(savings)
                        })
                        potential_savings += savings
                
                # Check if it can be converted to numeric
                try:
                    numeric_series = pd.to_numeric(df_sample[col], errors='coerce')
                    if not numeric_series.isnull().all():
                        recommendations.append({
                            "column": col,
                            "current_type": str(col_type),
                            "recommended_type": "numeric",
                            "reason": "Can be converted to numeric",
                            "estimated_savings_bytes": 0  # Would need full analysis
                        })
                except:
                    pass
            
            elif col_type in ['int64', 'float64']:
                # Check if we can use smaller types
                if col_type == 'int64':
                    col_min = df_sample[col].min()
                    col_max = df_sample[col].max()
                    
                    if col_min >= 0 and col_max <= 255:
                        uint8_memory = df_sample[col].astype('uint8').memory_usage(deep=True)
                        savings = col_memory - uint8_memory
                        recommendations.append({
                            "column": col,
                            "current_type": str(col_type),
                            "recommended_type": "uint8",
                            "reason": f"Values range from {col_min} to {col_max}",
                            "estimated_savings_bytes": int(savings)
                        })
                        potential_savings += savings
                
                elif col_type == 'float64':
                    # Check if float32 is sufficient
                    if not df_sample[col].isnull().all():
                        float32_series = df_sample[col].astype('float32')
                        if np.allclose(df_sample[col], float32_series, equal_nan=True):
                            float32_memory = float32_series.memory_usage(deep=True)
                            savings = col_memory - float32_memory
                            recommendations.append({
                                "column": col,
                                "current_type": str(col_type),
                                "recommended_type": "float32",
                                "reason": "Precision preserved with float32",
                                "estimated_savings_bytes": int(savings)
                            })
                            potential_savings += savings
        
        # Overall recommendations
        total_memory = df_sample.memory_usage(deep=True).sum()
        estimated_reduction = (potential_savings / total_memory) * 100
        
        return {
            "success": True,
            "file_path": file_path,
            "current_memory_bytes": int(total_memory),
            "potential_savings_bytes": int(potential_savings),
            "estimated_reduction_percentage": round(estimated_reduction, 2),
            "recommendations": recommendations,
            "message": f"Found {len(recommendations)} optimization opportunities"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc()
        }
