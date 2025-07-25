from adios2 import FileReader
import numpy as np
from typing import Optional, Dict, Any, Union


def inspect_attributes(
    filename: str, variable_name: Optional[str] = None
) -> Union[Dict[str, Dict[str, Any]], Dict[str, str]]:
    """
    List and read attributes from a BP5 file.
    If variable_name is None, returns global attributes;
    otherwise returns only attributes for that variable.

    Returns a mapping:
      attribute_name -> {
        "value": Python scalar or list,
        "Type": ADIOS data type as string,
        "SingleValue": "true" or "false",
        ...any other Params returned by ADIOS
      }
    """
    with FileReader(filename) as stream:
        # Fetch metadata for the requested scope
        if variable_name:
            attrs_meta = stream.available_attributes(variable_name)
        else:
            attrs_meta = stream.available_attributes()

        result: Dict[str, Dict[str, Any]] = {}
        if attrs_meta is None or not attrs_meta:
            return {"error": "Invalid Variable name or no attributes found"}
        for attr_name, meta in attrs_meta.items():
            # Build full attribute path for reading
            full_name = f"{variable_name}/{attr_name}" if variable_name else attr_name
            raw = stream.read_attribute(full_name)
            # Convert NumPy types/arrays to native Python types
            if isinstance(raw, np.generic) or (
                hasattr(raw, "shape") and raw.shape == ()
            ):  # scalar
                val = np.array(raw).item()
            else:
                val = np.array(raw).flatten().tolist()

            # Combine value with metadata Params
            entry: Dict[str, Any] = {"value": val}
            if "Type" in meta:
                entry["Type"] = meta["Type"]
            if "Elements" in meta:
                entry["Elements"] = meta["Elements"]
            result[attr_name] = entry

        return result
