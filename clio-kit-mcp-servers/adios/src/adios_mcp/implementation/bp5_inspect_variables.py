from adios2 import FileReader
from typing import Optional, Dict, Any


def inspect_variables(
    filename: str, variable_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Discover variables in a BP5 file.

    Args:
        filename: Path to the BP5 file
        variable_name: Optional name of specific variable to inspect

    Returns:
        If variable_name is None:
            Dict mapping each variable name to its metadata:
              - "Shape": global dimensions as a string
              - "Type": ADIOS data type as a string
              - "AvailableStepsCount": number of timesteps written
              - any additional ADIOS Params
        If variable_name is provided:
            Dict containing only the metadata for the specified variable
    """
    # Open in read mode
    with FileReader(filename) as stream:
        vars_info = stream.available_variables()
        # Convert ADIOS Params to plain dicts for JSON serialization
        all_vars = {name: dict(info) for name, info in vars_info.items()}

        if variable_name is None:
            return all_vars
        if variable_name in all_vars:
            return {variable_name: all_vars[variable_name]}
        else:
            return {"error": f"Variable '{variable_name}' not found in file."}
