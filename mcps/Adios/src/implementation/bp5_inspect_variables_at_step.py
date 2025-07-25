"""
Inspect variables in a BP5 file at a specific step.
"""

from adios2 import Stream


def inspect_variables_at_step(filename: str, variable_name: str, step: int):
    """
    Inspect a specific variable at a given step in a BP5 file.

    Args:
        filename: Path to the BP5 file
        variable_name: Name of the variable to inspect
        step: Step number to inspect

    Returns:
        Dict containing variable information at the specified step
    """
    try:
        with Stream(filename, "r") as s:
            # Iterate to the desired step
            for i, _ in enumerate(s.steps(timeout=3)):
                if i == step:
                    print(f"Current step is {s.current_step()}")
                    # Get variable info at this step
                    variables = s.available_variables()
                    if variable_name in variables:
                        info = variables[variable_name]
                        output = {"variable_name": variable_name}
                        # Add all variable info in same format as test.py
                        for key, value in info.items():
                            output[key] = value
                        return output
                    else:
                        raise ValueError(
                            f"Variable {variable_name} not found at step {step}"
                        )
            return {
                "error": f"Step {step} exceeds available steps in the variable or incorrect step."
            }

    except Exception as e:
        raise RuntimeError(
            f"Error inspecting variable {variable_name} at step {step}: {str(e)}"
        )
