#!/usr/bin/env python3
"""
Create comprehensive sample data in all acceptable formats for testing.
"""
import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

def create_sample_datasets():
    """Create comprehensive sample datasets."""
    print("Creating comprehensive sample datasets...")
    
    # Set random seed for reproducibility
    np.random.seed(42)
    
    # Create data directory
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)
    
    # 1. Employee Dataset
    print("Creating employee dataset...")
    n_employees = 1000
    departments = ['Engineering', 'Sales', 'Marketing', 'HR', 'Finance', 'Operations']
    positions = ['Junior', 'Senior', 'Manager', 'Director', 'VP']
    
    employee_data = {
        'employee_id': range(1, n_employees + 1),
        'name': [f'Employee_{i}' for i in range(1, n_employees + 1)],
        'department': np.random.choice(departments, n_employees),
        'position': np.random.choice(positions, n_employees),
        'age': np.random.randint(22, 65, n_employees),
        'salary': np.random.normal(75000, 20000, n_employees).round(2),
        'years_experience': np.random.randint(0, 40, n_employees),
        'performance_score': np.random.uniform(1.0, 5.0, n_employees).round(2),
        'bonus': np.random.uniform(0, 10000, n_employees).round(2),
        'hire_date': pd.date_range('2015-01-01', periods=n_employees, freq='D')[:n_employees]
    }
    
    employee_df = pd.DataFrame(employee_data)
    
    # Add some missing values realistically
    missing_indices = np.random.choice(n_employees, 50, replace=False)
    employee_df.loc[missing_indices, 'salary'] = np.nan
    
    missing_indices = np.random.choice(n_employees, 30, replace=False)
    employee_df.loc[missing_indices, 'performance_score'] = np.nan
    
    # 2. Sales Dataset
    print("Creating sales dataset...")
    n_sales = 2000
    products = ['Laptop', 'Mouse', 'Keyboard', 'Monitor', 'Headphones', 'Tablet', 'Phone']
    regions = ['North', 'South', 'East', 'West', 'Central']
    
    sales_data = {
        'sale_id': range(1, n_sales + 1),
        'employee_id': np.random.randint(1, n_employees + 1, n_sales),
        'product': np.random.choice(products, n_sales),
        'region': np.random.choice(regions, n_sales),
        'quantity': np.random.randint(1, 10, n_sales),
        'unit_price': np.random.uniform(50, 2000, n_sales).round(2),
        'total_amount': np.nan,  # Will calculate
        'sale_date': pd.date_range('2023-01-01', periods=n_sales, freq='H')[:n_sales],
        'customer_rating': np.random.randint(1, 6, n_sales),
        'discount_percent': np.random.uniform(0, 25, n_sales).round(2)
    }
    
    sales_df = pd.DataFrame(sales_data)
    # Calculate total amount
    sales_df['total_amount'] = (sales_df['quantity'] * sales_df['unit_price'] * 
                               (1 - sales_df['discount_percent'] / 100)).round(2)
    
    # 3. Time Series Dataset (Weather Data)
    print("Creating weather time series dataset...")
    n_days = 365
    dates = pd.date_range('2023-01-01', periods=n_days, freq='D')
    
    # Generate realistic weather data with seasonal patterns
    day_of_year = np.arange(1, n_days + 1)
    
    weather_data = {
        'date': dates,
        'temperature': (20 + 15 * np.sin(2 * np.pi * day_of_year / 365) + 
                       np.random.normal(0, 3, n_days)).round(1),
        'humidity': np.clip(50 + 20 * np.sin(2 * np.pi * day_of_year / 365 + np.pi/4) + 
                           np.random.normal(0, 5, n_days), 0, 100).round(1),
        'pressure': (1013 + 10 * np.sin(2 * np.pi * day_of_year / 365 + np.pi/2) + 
                    np.random.normal(0, 5, n_days)).round(1),
        'wind_speed': np.abs(np.random.normal(10, 3, n_days)).round(1),
        'precipitation': np.random.exponential(1, n_days).round(1),
        'cloud_cover': np.random.uniform(0, 100, n_days).round(1)
    }
    
    weather_df = pd.DataFrame(weather_data)
    
    # 4. Product Inventory Dataset
    print("Creating product inventory dataset...")
    n_products = 500
    categories = ['Electronics', 'Clothing', 'Books', 'Sports', 'Home', 'Beauty', 'Toys']
    
    inventory_data = {
        'product_id': range(1, n_products + 1),
        'product_name': [f'Product_{i}' for i in range(1, n_products + 1)],
        'category': np.random.choice(categories, n_products),
        'supplier': [f'Supplier_{i}' for i in np.random.randint(1, 21, n_products)],
        'cost_price': np.random.uniform(10, 1000, n_products).round(2),
        'selling_price': np.nan,  # Will calculate
        'stock_quantity': np.random.randint(0, 1000, n_products),
        'reorder_level': np.random.randint(10, 100, n_products),
        'weight_kg': np.random.uniform(0.1, 50, n_products).round(2),
        'last_updated': pd.date_range('2023-12-01', periods=n_products, freq='H')[:n_products]
    }
    
    inventory_df = pd.DataFrame(inventory_data)
    # Calculate selling price with margin
    inventory_df['selling_price'] = (inventory_df['cost_price'] * 
                                   np.random.uniform(1.2, 2.5, n_products)).round(2)
    
    # Store datasets
    datasets = {
        'employees': employee_df,
        'sales': sales_df,
        'weather': weather_df,
        'inventory': inventory_df
    }
    
    return datasets

def save_in_multiple_formats(datasets, data_dir):
    """Save datasets in multiple formats."""
    print("Saving datasets in multiple formats...")
    
    formats = ['csv', 'json', 'parquet']
    
    # Try to add Excel format
    try:
        import openpyxl
        formats.append('excel')
    except ImportError:
        print("Warning: openpyxl not available, skipping Excel format")
    
    # Try to add HDF5 format
    try:
        import tables
        formats.append('hdf5')
    except ImportError:
        print("Warning: tables not available, skipping HDF5 format")
    
    saved_files = {}
    
    for dataset_name, df in datasets.items():
        print(f"\nSaving {dataset_name} dataset...")
        saved_files[dataset_name] = {}
        
        for fmt in formats:
            try:
                if fmt == 'csv':
                    file_path = os.path.join(data_dir, f'{dataset_name}.csv')
                    df.to_csv(file_path, index=False)
                    saved_files[dataset_name]['csv'] = file_path
                    print(f"  ✓ Saved {dataset_name}.csv")
                    
                elif fmt == 'json':
                    file_path = os.path.join(data_dir, f'{dataset_name}.json')
                    # Convert datetime columns to strings for JSON compatibility
                    df_json = df.copy()
                    for col in df_json.select_dtypes(include=['datetime64']).columns:
                        df_json[col] = df_json[col].dt.strftime('%Y-%m-%d %H:%M:%S')
                    df_json.to_json(file_path, orient='records', date_format='iso')
                    saved_files[dataset_name]['json'] = file_path
                    print(f"  ✓ Saved {dataset_name}.json")
                    
                elif fmt == 'parquet':
                    file_path = os.path.join(data_dir, f'{dataset_name}.parquet')
                    df.to_parquet(file_path, index=False)
                    saved_files[dataset_name]['parquet'] = file_path
                    print(f"  ✓ Saved {dataset_name}.parquet")
                    
                elif fmt == 'excel':
                    file_path = os.path.join(data_dir, f'{dataset_name}.xlsx')
                    df.to_excel(file_path, index=False)
                    saved_files[dataset_name]['excel'] = file_path
                    print(f"  ✓ Saved {dataset_name}.xlsx")
                    
                elif fmt == 'hdf5':
                    file_path = os.path.join(data_dir, f'{dataset_name}.h5')
                    df.to_hdf(file_path, key='data', mode='w')
                    saved_files[dataset_name]['hdf5'] = file_path
                    print(f"  ✓ Saved {dataset_name}.h5")
                    
            except Exception as e:
                print(f"  ✗ Failed to save {dataset_name}.{fmt}: {e}")
    
    return saved_files

def main():
    """Main function to create sample data."""
    print("Creating Sample Data for Pandas MCP Server")
    print("=" * 50)
    
    # Create datasets
    datasets = create_sample_datasets()
    
    # Save in multiple formats
    saved_files = save_in_multiple_formats(datasets, "data")
    
    # Print summary
    print("\n" + "=" * 50)
    print("SAMPLE DATA CREATION SUMMARY")
    print("=" * 50)
    
    for dataset_name, formats in saved_files.items():
        print(f"\n{dataset_name.upper()} Dataset:")
        print(f"  Rows: {len(datasets[dataset_name])}")
        print(f"  Columns: {len(datasets[dataset_name].columns)}")
        print("  Formats:")
        for fmt, path in formats.items():
            file_size = os.path.getsize(path) / 1024  # Size in KB
            print(f"    ✓ {fmt.upper()}: {path} ({file_size:.1f} KB)")
    
    print(f"\n🎉 Sample data created successfully in 'data' directory!")
    print(f"Total files created: {sum(len(formats) for formats in saved_files.values())}")
    
    return saved_files

if __name__ == "__main__":
    main()
