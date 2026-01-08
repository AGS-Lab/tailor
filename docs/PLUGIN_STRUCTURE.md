# Plugin Directory Structure

Tailor uses a directory-based plugin system where each plugin is a self-contained folder with its own configuration and resources.

## Structure

```
example-vault/
├── .vault.json                # Vault metadata
├── plugins/                   # Plugin directory
│   ├── requirements.txt       # Shared dependencies
│   ├── my_plugin/            # Individual plugin
│   │   ├── main.py           # Entry point (required)
│   │   └── settings.json     # Plugin configuration
│   └── another_plugin/
│       ├── main.py
│       └── settings.json
├── lib/                       # Auto-managed dependencies
└── .memory/                   # Conversation history
```

## Plugin Entry Point

Each plugin must have a `main.py` file with a `Plugin` class:

```python
class Plugin:
    def __init__(self, emitter, brain, plugin_dir, vault_path):
        """
        Initialize plugin.
        
        Args:
            emitter: EventEmitter for UI interactions
 brain: VaultBrain for command registration
            plugin_dir: Path to plugin directory (for plugin-specific files)
            vault_path: Path to vault root (for accessing configs/)
        """
        self.emitter = emitter
        self.brain = brain
        self.plugin_dir = plugin_dir
        self.vault_path = vault_path
        self.name = "my_plugin"
        
        # Load plugin config from vault/configs/my_plugin/
        self.config = self._load_config()
        
        # Register commands
        brain.register_command("myPlugin.action", self.my_action, self.name)
        
        # Send init notification
        emitter.notify(f"Plugin '{self.name}' loaded!", severity="success")
    
    def _load_config(self):
        """Load plugin configuration from settings.json"""
        import json
        config_file = self.plugin_dir / "settings.json"
        
        if config_file.exists():
            with open(config_file, "r") as f:
                return json.load(f)
        
        return {}  # Default config
    
    async def on_tick(self, emitter):
        """Called every 5 seconds (optional)."""
        pass
    
    async def my_action(self, **kwargs):
        """Command handler."""
        return {"status": "ok"}
```

## Configuration Files

Each plugin can have a `settings.json` file in its directory:

### `plugins/my_plugin/settings.json`

```json
{
  "enabled": true,
  "heartbeat_interval": 3,
  "log_level": "info",  "api_key": "your-key-here"
}
```

Access config in your plugin:

```python
def __init__(self, emitter, brain, plugin_dir, vault_path):
    self.plugin_dir = plugin_dir
    self.config = self._load_config()
    
    # Use config values
    if self.config.get("enabled", True):
        self.setup()

def _load_config(self):
    import json
    config_file = self.plugin_dir / "settings.json"
    return json.load(open(config_file)) if config_file.exists() else {}
```

## Plugin Loading

VaultBrain automatically:
1. Scans `plugins/` directory for subdirectories
2. Looks for `main.py` in each directory
3. Loads the `Plugin` class
4. Passes `plugin_dir` path for config access
5. Calls `on_tick()` every 5 seconds if defined

## Requirements

Shared dependencies go in `plugins/requirements.txt`:

```txt
requests==2.31.0
beautifulsoup4==4.12.2
```

Plugin-specific dependencies can be added to the shared `requirements.txt` or documented separately.

## Example Plugin Structure

```
example_plugin/
├── main.py                 # Plugin entry point
├── configs/
│   ├── settings.json      # Plugin configuration
│   └── api_keys.json      # Sensitive configs (gitignored)
└── README.md              # Plugin documentation (optional)
```

## Best Practices

1. **Use `plugin_dir` for file access**: Always use `self.plugin_dir` to access plugin resources
2. **Default configs**: Provide sensible defaults if config files don't exist
3. **Config validation**: Validate config values in `_load_config()`
4. **Sensitive data**: Add sensitive config files to `.gitignore`
5. **Documentation**: Include README.md explaining plugin usage and configuration

## Creating a New Plugin

1. Create plugin directory:
   ```bash
   mkdir -p example-vault/plugins/my_plugin/configs
   ```

2. Create `main.py`:
   ```python
   class Plugin:
       def __init__(self, emitter, brain, plugin_dir):
           self.emitter = emitter
           self.brain = brain
           self.plugin_dir = plugin_dir
           # ... setup
   ```

3. Create `configs/settings.json`:
   ```json
   {
     "enabled": true
   }
   ```

4. Open vault in Tailor - plugin loads automatically!

## Advanced Features

### Multiple Config Files

```python
def _load_config(self):
    config_dir = self.plugin_dir / "configs"
    
    # Load multiple configs
    settings = self._load_json(config_dir / "settings.json")
    api_keys = self._load_json(config_dir / "api_keys.json")
    
    return {**settings, **api_keys}
```

### Plugin Resources

Store assets in plugin directory:

```
my_plugin/
├── main.py
├── configs/
│   └── settings.json
├── templates/
│   └── message.html
└── assets/
    └── icon.png
```

Access resources:

```python
template_path = self.plugin_dir / "templates" / "message.html"
icon_path = self.plugin_dir / "assets" / "icon.png"
```

## Future Features (Planned)

- **Plugin Manifest**: `plugin.json` with metadata (name, version, author)
- **UI Configuration**: Visual config editor in Tauri UI
- **Hot Reload**: Reload plugins without restarting sidecar
- **Plugin Marketplace**: Share and discover plugins
