"""
Configuration file for pytest.
This file suppresses warnings during test execution.
"""

import warnings
import pytest


@pytest.fixture(autouse=True)
def suppress_warnings():
    """Automatically suppress warnings for all tests."""
    # Suppress all DeprecationWarnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    # Suppress all UserWarnings
    warnings.filterwarnings("ignore", category=UserWarning)

    # Suppress all FutureWarnings
    warnings.filterwarnings("ignore", category=FutureWarning)

    # Suppress all PendingDeprecationWarnings
    warnings.filterwarnings("ignore", category=PendingDeprecationWarning)

    # Specifically suppress matplotlib/Pillow warnings
    warnings.filterwarnings("ignore", message=".*mode.*parameter.*deprecated.*")
    warnings.filterwarnings("ignore", message=".*Matplotlib.*")

    # Suppress any other common warnings
    warnings.filterwarnings("ignore", category=ResourceWarning)
    warnings.filterwarnings("ignore", category=RuntimeWarning)


def pytest_configure(config):
    """Configure pytest to suppress warnings globally."""
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    warnings.filterwarnings("ignore", category=UserWarning)
    warnings.filterwarnings("ignore", category=FutureWarning)
    warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
    warnings.filterwarnings("ignore", message=".*mode.*parameter.*deprecated.*")
    warnings.filterwarnings("ignore", message=".*Matplotlib.*")
