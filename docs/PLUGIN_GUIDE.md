# Plugin Development Guide

## Creating a New Plugin

### Quick Start

1. Create a new directory in `example-vault/plugins/`
2. Add a `main.py` file with a `Plugin` class
3. Inherit from `PluginBase`
4. Implement `register_commands()`

## Plugin Directory Structure

Tailor uses a directory-based plugin system. Each plugin is a self-contained folder in `vault/plugins/` with its own configuration and resources.

```
example-vault/
├── .vault.json                # Vault metadata
├── plugins/   
│   ├── my_plugin/            # Plugin Directory
│   │   ├── main.py           # ENTRY POINT (Required)
│   │   ├── settings.json     # Configuration (Optional)
│   │   └── README.md         # Documentation
│   └── another_plugin/
│       ├── main.py
│       └── ...
└── ...
```

## Plugin Entry Point (`main.py`)

Every plugin **must** have a `main.py` file containing a `Plugin` class that inherits from `PluginBase`.

```python
"""
My Plugin - Description of what it does
"""
import sys
from pathlib import Path
from typing import Dict, Any

# Boilerplate: Add sidecar to path so we can import api.plugin_base
sidecar_path = Path(__file__).parent.parent.parent.parent / "sidecar"
if str(sidecar_path) not in sys.path:
    sys.path.insert(0, str(sidecar_path))

from api.plugin_base import PluginBase

class Plugin(PluginBase):
    """My custom plugin."""
    
    def __init__(self, emitter, brain, plugin_dir, vault_path):
        """
        Initialize plugin.
        
        Args:
            emitter: EventEmitter for UI interactions
            brain: VaultBrain for command registration
            plugin_dir: Path to this plugin's directory
            vault_path: Path to the vault root
        """
        super().__init__(emitter, brain, plugin_dir, vault_path)
        
        # Load configuration
        self.config = self.load_settings()
        
        # Register commands
        self.register_commands()
        
        self.logger.info(f"Plugin '{self.name}' initialized")
    
    def register_commands(self) -> None:
        """Register plugin commands (Required)."""
        self.brain.register_command(
            "my_plugin.hello",
            self.handle_hello,
            self.name
        )
    
    async def handle_hello(self, name: str = "World", **kwargs) -> Dict[str, Any]:
        """Example command handler."""
        message = f"Hello, {name}!"
        self.emitter.notify(message, severity="info")
        return {"status": "success", "message": message}
```

## Configuration (`settings.json`)

Plugins can have a `settings.json` file in their directory. This file is automatically loaded if you use `self.load_settings()`.

**`plugins/my_plugin/settings.json`:**
```json
{
  "enabled": true,
  "api_key": "secret-key",
  "theme": "dark"
}
```

**Accessing Settings:**
```python
def __init__(self, ...):
    super().__init__(...)
    
    # helper method to load settings.json
    settings = self.load_settings() 
    
    if settings.get("enabled"):
        self.setup_feature()
```

### Advanced Configuration

You can also override plugin settings globally in the `.vault.json` file of the vault:

```json
{
  "plugins": {
    "my_plugin": {
      "enabled": false
    }
  }
}
```
Global overrides take precedence over the plugin's `settings.json`.


## PluginBase API

### Properties

- `self.emitter` - EventEmitter for sending UI events
- `self.brain` - VaultBrain for registering commands
- `self.plugin_dir` - Path to plugin directory
- `self.vault_path` - Path to vault root
- `self.name` - Plugin name (directory name)
- `self.logger` - Plugin-specific logger
- `self.is_loaded` - Whether plugin has been loaded

### Methods to Override

#### Required
- `register_commands()` - Register plugin commands

#### Optional Lifecycle Hooks
- `async on_load()` - Called after all plugins loaded
- `async on_tick(emitter)` - Called every 5 seconds
- `async on_unload()` - Called when plugin unloaded

### Helper Methods

#### Settings Management
```python
# Load settings
settings = self.load_settings()  # Returns dict
value = settings.get("key", default)

# Save settings
self.save_settings({"key": "value"})
```

#### Logging
```python
self.logger.debug("Debug message")
self.logger.info("Info message")
self.logger.warning("Warning message")
self.logger.error("Error message")
```

#### Event Emission
```python
# Simple notification
self.emitter.notify("Hello!", severity="info")

# Progress update
self.emitter.progress(50, "Half done")

# Custom event
self.emitter.emit("MY_EVENT", {"data": "value"}, scope="window")
```

## Command Registration

```python
def register_commands(self) -> None:
    """Register commands."""
    # Basic command
    self.brain.register_command(
        "my_plugin.command_name",
        self.handler_method,
        self.name  # Plugin name
    )
```

### Command Handler Pattern

```python
async def handler_method(self, param1: str = "", **kwargs) -> Dict[str, Any]:
    """
    Handle command.
    
    Args:
        param1: Description
        **kwargs: Additional parameters from UI
    
    Returns:
        Result dictionary with status
    """
    # Validate input
    if not param1:
        return {"status": "error", "error": "param1 required"}
    
    # Do work
    result = do_something(param1)
    
    # Emit event to UI
    self.emitter.notify(f"Processed {param1}", severity="success")
    
    # Return result
    return {
        "status": "success",
        "result": result
    }
```

## Best Practices

### 1. Always Use Type Hints
```python
async def my_command(self, value: int, **kwargs) -> Dict[str, Any]:
    return {"status": "success", "value": value}
```

### 2. Use Logging Instead of Print
```python
# Bad
print("Plugin loaded")

# Good
self.logger.info("Plugin loaded")
```

### 3. Validate Input
```python
async def handle_command(self, value: str = "", **kwargs) -> Dict[str, Any]:
    if not value:
        self.logger.warning("Empty value provided")
        return {"status": "error", "error": "value required"}
    
    # Process...
```

### 4. Handle Errors Gracefully
```python
async def handle_command(self, **kwargs) -> Dict[str, Any]:
    try:
        result = risky_operation()
        return {"status": "success", "result": result}
    except Exception as e:
        self.logger.error(f"Operation failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
```

### 5. Use Settings for Configuration
```python
def __init__(self, emitter, brain, plugin_dir, vault_path):
    super().__init__(emitter, brain, plugin_dir, vault_path)
    
    # Load settings
    settings = self.load_settings()
    self.api_key = settings.get("api_key", "")
    self.model = settings.get("model", "default")
```

## Example Plugins

- **demo_plugin** - Shows all PluginBase features
- **llm** - Chat interface with conversation history

## Testing Your Plugin

```bash
# Run sidecar with your vault
pixi run sidecar --vault example-vault --ws-port 9001 --verbose

# Check logs
# Look for: "Plugin 'your_plugin' loaded"
```

## Debugging

Enable verbose logging:
```bash
pixi run sidecar --vault example-vault --ws-port 9001 --verbose
```

Check plugin-specific logs:
```python
self.logger.debug("Detailed debug info")
self.logger.info("Normal info")
self.logger.error("Error info", exc_info=True)  # Includes stack trace
```

## Common Patterns

### Maintaining State
```python
def __init__(self, emitter, brain, plugin_dir, vault_path):
    super().__init__(emitter, brain, plugin_dir, vault_path)
    self.my_state = []  # Plugin-specific state
    
    # Load from settings
    settings = self.load_settings()
    self.my_state = settings.get("state", [])

async def on_unload(self) -> None:
    """Save state on unload."""
    self.save_settings({"state": self.my_state})
    await super().on_unload()
```

### Background Tasks
```python
async def on_tick(self, emitter) -> None:
    """Run periodic task."""
    # Do something every 5 seconds
    await self.check_for_updates()
```

### UI Integration
```python
async def get_ui(self, **kwargs) -> Dict[str, Any]:
    """Return custom UI HTML."""
    ui_file = self.plugin_dir / "ui" / "panel.html"
    
    if ui_file.exists():
        with open(ui_file, 'r', encoding='utf-8') as f:
            return {"status": "success", "html": f.read()}
    
    return {"status": "error", "error": "UI not found"}
```
