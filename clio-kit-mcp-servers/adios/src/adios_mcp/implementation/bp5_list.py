from pathlib import Path


def list_bp5(directory: str = "data") -> list[Path]:
    """
    Return a list of all .bp and .bp5 file paths under the specified directory.
    Raises FileNotFoundError if the directory doesn't exist.
    """
    base = Path(directory)
    if not base.exists():
        raise FileNotFoundError(f"Directory '{directory}' not found")

    # Use glob to match both *.bp and *.bp5
    bp_files = list(base.glob("*.bp"))
    bp5_files = list(base.glob("*.bp5"))
    return bp_files + bp5_files
