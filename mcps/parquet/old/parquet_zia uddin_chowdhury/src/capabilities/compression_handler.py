import gzip
import os
import shutil

def compress_file(file_path: str):
    try:
        output_path = file_path + '.gz'
        
        # get original file size
        original_size = os.path.getsize(file_path)
        
        # compress the file
        with open(file_path, 'rb') as f_in:
            with gzip.open(output_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # get compressed file size
        compressed_size = os.path.getsize(output_path)
        
        # calculate compression ratio
        compression_ratio = (1 - (compressed_size / original_size)) * 100
        
        return {
            "status": "success",
            "original_file": file_path,
            "compressed_file": output_path,
            "original_size": original_size,
            "compressed_size": compressed_size,
            "compression_ratio": f"{compression_ratio:.2f}%"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"compression failed: {str(e)}"
        } 