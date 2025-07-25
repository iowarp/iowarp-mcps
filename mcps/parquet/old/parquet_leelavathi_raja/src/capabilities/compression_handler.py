import gzip
import shutil
import pathlib

def file_compression(file_path):
    try:
        input_path = pathlib.Path(file_path)
        if not input_path.exists():
            return {"status_code": 400,"body": "File path does not exist"}
        
        output_path = input_path.with_suffix(input_path.suffix + ".gz")
        with open(input_path, 'rb') as f_in:
            with gzip.open(output_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        return {"status_code": 200, "body": f"Compressed to {output_path}"}
    except Exception as e:
        return {"status_code": 500, "body": f"Compression failed: {str(e)}"}