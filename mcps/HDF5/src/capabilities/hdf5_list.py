
import glob
from pathlib import Path

def list_hdf5(directory: str = "data") -> list[str]:
    """
    Return a list of all .hdf5 file paths under the specified directory.
    Raises FileNotFoundError if the directory doesn't exist.
    """
    base = Path(directory)
    if not base.exists():
        raise FileNotFoundError(f"Directory '{directory}' not found")

    # Use glob to match *.hdf5
    return list(base.glob("*.h5")) + list(base.glob("*.hdf5"))