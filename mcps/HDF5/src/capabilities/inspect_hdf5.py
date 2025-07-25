import h5py
from typing import List

def inspect_hdf5_file(fname: str) -> List[str]:
    """
    Walks the HDF5 file and returns a list of lines describing
    every group, dataset, and its attributes.
    """
    output: List[str] = []

    def print_attrs(obj, indent=0):
        for name, val in obj.attrs.items():
            output.append("  " * indent + f"- ATTR {name!r}: {val!r}")

    def walker(name, obj):
        indent = name.count("/")
        prefix = "  " * indent
        if isinstance(obj, h5py.Group):
            output.append(f"{prefix}GROUP   /{name or ''}/")
            print_attrs(obj, indent + 1)
        elif isinstance(obj, h5py.Dataset):
            output.append(f"{prefix}DATASET /{name}")
            output.append(f"{prefix}  shape={obj.shape}, dtype={obj.dtype}")
            print_attrs(obj, indent + 1)

    with h5py.File(fname, "r") as f:
        f.visititems(walker)

    return output
