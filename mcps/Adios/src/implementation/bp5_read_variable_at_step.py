import numpy as np
import adios2


def read_variable_at_step(filename: str, variable_name: str, target_step: int):
    """
    Read a single variable from a specific step in a BP5 file.

    Args:
      filename: Path to the .bp directory (basename.bp)
      variable_name: Name of the variable to read
      target_step: The integer step index to fetch

    Returns:
      A Python scalar or list (flattened array) of that variable’s value
      at the specified step.

    Raises:
      ValueError: if the step or variable is not found.
    """
    with adios2.Stream(filename, "r") as s:
        for _ in s.steps():
            current = s.current_step()
            if current == target_step:
                # make sure the variable exists
                avail = s.available_variables()
                if variable_name not in avail:
                    raise ValueError(
                        f"Variable '{variable_name}' not in step {current}"
                    )
                arr = s.read(variable_name)
                # convert NumPy types → native Python
                if isinstance(arr, np.generic) or (
                    hasattr(arr, "shape") and arr.shape == ()
                ):
                    return np.array(arr).item()
                else:
                    return np.array(arr).flatten().tolist()
    raise ValueError(f"Step {target_step} not found in file '{filename}'")
