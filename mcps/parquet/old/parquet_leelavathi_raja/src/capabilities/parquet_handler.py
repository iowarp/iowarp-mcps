import pyarrow.parquet as pq
from fastapi.responses import JSONResponse
import pathlib

def read_parquet_column(action, file_path, column_name):
    try:
        if not file_path or not pathlib.Path(file_path).exists():
            return JSONResponse(content={"error": "File path is missing or does not exist"}, status_code=400)

        table = pq.read_table(file_path)
        if action == "read_column":
            if column_name not in table.schema.names:
                return JSONResponse(content={"error": "Column not found"}, status_code=400)
            column_data = table[column_name].to_pylist()
            return {column_name: column_data}
        else:
            return JSONResponse(content={"error": "Invalid action"}, status_code=400)
    
    except Exception as e:
        print(str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)