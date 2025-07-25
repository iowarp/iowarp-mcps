import pathlib
from fastapi import HTTPException

def list_hdf5_files(path_pattern):
    path = pathlib.Path(path_pattern)
    if not path.exists() or not path.is_dir():
        raise HTTPException(status_code=400, detail="Directory does not exist or is not a valid directory.")
    
    try:
        # Return the list of .hdf5 files in the directory
        return [str(file) for file in path.glob("*.hdf5")]
    except Exception as e:
        # Catch any unexpected exceptions and raise an HTTPException
        raise HTTPException(status_code=500, detail=f"error while processing the directory: {str(e)}")
