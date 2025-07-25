import pyarrow.parquet as pq

# function to read any specified column
def read_column(parquet_file: str, column_name: str):
    table = pq.read_table(parquet_file, columns=[column_name])
    return table.column(column_name).to_pylist()
