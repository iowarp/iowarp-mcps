import h5py
from typing import Dict, List, Any

def preview_hdf5_datasets(fname: str, count: int = 10) -> Dict[str, List[Any]]:
    """
    Reads each dataset in the file and returns the first count
    elements as a Python list under its path key.
    """
    result: Dict[str, List[Any]] = {}

    with h5py.File(fname, "r") as f:
        def previewer(name, obj):
            if isinstance(obj, h5py.Dataset):
                data = obj[()]
                flat = data.ravel()
                sample = flat[:count] if flat.size > count else flat
                # convert numpy types to Python native
                result[name] = sample.tolist()

        f.visititems(previewer)

    return result