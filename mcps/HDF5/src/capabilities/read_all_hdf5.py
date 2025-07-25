import h5py
from typing import Dict, Any

def read_all_hdf5_datasets(fname: str) -> Dict[str, Any]:
    """
    Reads each dataset in the file in full and returns it
    as nested Python lists (or raw objects) under its path key.
    """
    result: Dict[str, Any] = {}

    with h5py.File(fname, "r") as f:
        def reader(name, obj):
            if isinstance(obj, h5py.Dataset):
                data = obj[()]
                try:
                    # for numeric arrays, convert to nested lists
                    result[name] = data.tolist()
                except AttributeError:
                    # e.g. VLEN or object arrays
                    result[name] = data

        f.visititems(reader)

    return result
