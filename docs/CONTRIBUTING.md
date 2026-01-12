# Contributing to Tailor

Thank you for your interest in contributing to Tailor! This document provides guidelines for developing the Python sidecar and plugins.

## Development Setup

1.  **Environment**: Ensure you have Python 3.12+ installed.
2.  **Dependencies**: Install development dependencies:
    ```bash
    pixi install
    ```

## Code Structure

The project follows a strict package structure:
- **`sidecar/`**: Main Python package.
- **`sidecar/api/`**: Public API for plugins (`PluginBase`).
- **`sidecar/utils/`**: Internal utilities.
- **`sidecar/tests/`**: Test suite.

### Import Guidelines
- **Internal Imports**: Use relative imports within the `sidecar` package (e.g., `from .utils import ...`).
- **External Imports**: Use fully qualified imports or `sidecar.` prefix where appropriate in tests.
- **Top-Level**: Do NOT import `sidecar` submodules as top-level modules (e.g., avoid `import utils`). Always use `from sidecar import ...` or `import sidecar.utils`.

## Running Tests

We use `pytest` for testing. You must run tests from the project root (`tailor` directory) to ensure correct package resolution.

```bash
# Correct way to run tests
pixi run test

# Run specific test file
pixi run pytest sidecar/tests/test_integration.py
```

## Developing Plugins

Plugins reside in the vault's `plugins/` directory.

### Requirements
1.  **Inheritance**: Your plugin class MUST inherit from `sidecar.api.plugin_base.PluginBase`.
2.  **Imports**: Use the `sidecar` package for API imports.
    ```python
    from sidecar.api.plugin_base import PluginBase
    ```
3.  **Path Configuration**: The `tailor` root directory must be in `sys.path`. This is handled automatically by the app, but crucial for standalone testing when importing `sidecar`.

### Example Plugin Structure
```python
# main.py
from sidecar.api.plugin_base import PluginBase

class Plugin(PluginBase):
    def register_commands(self):
        self.brain.register_command("my.command", self.handle_command, self.name)
        
    async def handle_command(self, **kwargs):
        return {"status": "ok"}
```
