# Tailor Sidecar

The Python backend for the Tailor Desktop Application. It operates as a sidecar process, handling vault-specific logic, AI orchestration (LangGraph), and plugin management.

## Architecture

The Sidecar communicates with the main Tauri process via **WebSockets** (JSON-RPC 2.0).

- **`__main__.py`**: Module entry point (supports `python -m sidecar`).
- **`main.py`**: CLI argument parsing and initialization.
- **`websocket_server.py`**: Handles bi-directional communication with Tauri.
- **`vault_brain.py`**: Core orchestrator. Loads plugins, manages lifecycle, and executes commands.
- **`api/plugin_base.py`**: Base class for all plugins.
- **`event_emitter.py`**: Utility for plugins to send events to the UI.

## Requirements

- Python 3.10+
- Dependencies listed in `requirements.txt`

## Development

### Setup
```bash
pixi install
```

### Running Tests
We use `pytest` for unit and integration testing.
```bash
# Run all tests
pixi run test

# Run with coverage (configured in pixi.toml or via arguments)
pixi run pytest tests/ --cov=.
```

### Type Checking
We use `mypy` for strict type enforcement.
```bash
mypy --explicit-package-bases .
```

### Project Structure
```text
sidecar/
├── api/             # Public APIs for plugins
├── utils/           # Shared utilities (logging, paths, json-rpc)
├── tests/           # Unit and Integration tests
├── __main__.py      # Module entry point
├── main.py          # Entry point logic
├── vault_brain.py   # Core logic
└── ...
```

## Plugin Development

Plugins reside in the Vault's `plugins/` directory. Each plugin must have a `main.py` defining a `Plugin` class that inherits from `api.plugin_base.PluginBase`.

Example:
```python
from api.plugin_base import PluginBase

class Plugin(PluginBase):
    def register_commands(self):
        self.brain.register_command("my.command", self.handle_command, self.name)

    async def handle_command(self, **kwargs):
        self.emitter.notify("Command executed!")
        return {"status": "ok"}
```
