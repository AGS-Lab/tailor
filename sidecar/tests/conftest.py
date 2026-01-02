"""
Pytest configuration for Tailor sidecar tests.

This module configures pytest for testing the refactored codebase.
"""

import sys
from pathlib import Path

# Add tailor root to path for imports (allow 'sidecar' package import)
tailor_path = Path(__file__).resolve().parent.parent.parent
if str(tailor_path) not in sys.path:
    sys.path.insert(0, str(tailor_path))


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
