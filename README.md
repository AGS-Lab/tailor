# Tailor - Multi-Window AI Workspace

A modular AI framework that lets you stitch together models and tools into an assistant that fits you perfectly.

## Features

- **Multi-Window Vaults**: Open multiple independent vaults simultaneously
- **Isolated Sidecars**: Each vault runs its own Python process for complete isolation
- **Plugin System**: Create and share custom plugins with the community
- **Bi-Directional Events**: Plugins can emit events back to the UI
- **Portable Vaults**: Vault folders are self-contained and can be shared easily

## Architecture

- **Rust/Tauri**: Window management, process orchestration, event routing
- **Python Sidecar**: Plugin system, command registry, event emission
  - **Type-safe**: Full type hints with mypy validation
  - **Professional logging**: Rotating file handlers and console output
  - **Plugin system**: Extensible PluginBase class with lifecycle hooks
- **WebSocket**: Bi-directional JSON-RPC 2.0 communication
- **Plugins**: Vault-specific extensions with command registration

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed design

## Prerequisites

- **Pixi**: Install from [prefix.dev](https://prefix.dev/)
- **Rust**: Install from [rustup.rs](https://rustup.rs/) (Required for Tauri)

## Installation

### 1. Install Dependencies

```bash
pixi install
```

This will automatically set up the isolated Python and Node.js environments with all dependencies.

## Development

### Run in Development Mode

```bash
# Start Tauri development server
pixi run dev
```

This will:
1. Start Vite dev server for frontend
2. Compile Rust backend
3. Launch the Tauri application

### Testing the Example Vault

1. Click "Open Vault" in the app
2. Select the `example-vault` directory
3. Watch the console for sidecar initialization
4. Observe the example plugin emit events every 15 seconds

## Project Structure

```
tailor/
├── src/                          # Frontend code
│   └── index.html
├── src-tauri/                    # Rust backend
│   ├── src/
│   │   ├── main.rs               # Entry point
│   │   ├── window_manager.rs    # Window lifecycle
│   │   ├── sidecar_manager.rs   # Process orchestration
│   │   ├── dependency_checker.rs # Auto install dependencies
│   │   ├── ipc_router.rs        # Command routing
│   │   └── event_bus.rs         # Event routing
│   ├── Cargo.toml
│   └── tauri.conf.json
├── sidecar/                      # Python sidecar (✨ refactored)
│   ├── __main__.py               # Module entry point
│   ├── main.py                   # CLI logic
│   ├── websocket_server.py       # JSON-RPC 2.0 WebSocket server
│   ├── vault_brain.py            # Plugin orchestrator
│   ├── event_emitter.py          # Event emission API
│   ├── constants.py              # Centralized constants & enums
│   ├── exceptions.py             # Custom exception hierarchy
│   ├── api/                      # Plugin API
│   │   ├── plugin_base.py        # Abstract base class with lifecycle
│   │   └── __init__.py
│   ├── utils/                    # Utility modules
│   │   ├── logging_config.py     # Professional logging system
│   │   ├── json_rpc.py           # JSON-RPC utilities
│   │   ├── path_utils.py         # Safe path operations
│   │   └── __init__.py
│   └── requirements.txt
└── example-vault/                # Example vault
    ├── .vault.json               # Vault configuration
    └── plugins/                  # Vault-specific plugins
        ├── llm/                  # LLM chat plugin
        │   └── main.py           # (inherits from PluginBase)
        └── demo_plugin/          # Demo plugin
            └── main.py           # (inherits from PluginBase)
```

See [PLUGIN_GUIDE.md](PLUGIN_GUIDE.md) for plugin development.

## Creating a Vault

A vault is a self-contained directory with the following structure:

```
my-vault/
├── .vault.json              # Vault metadata
├── plugins/                 # Plugin directory
│   ├── requirements.txt     # Shared dependencies
│   ├── my_plugin/          # Individual plugin
│   │   ├── main.py         # Entry point (required)
│   │   └── settings.json   # Plugin configuration
│   └── another_plugin/
│       ├── main.py
│       └── settings.json
├── lib/                     # Auto-managed dependencies
├── .memory/                 # Conversation history
└── config/                  # User preferences
```

### Example Plugin

Each plugin is a directory with `main.py` that inherits from `PluginBase`:

```python
# plugins/my_plugin/main.py
import sys
from pathlib import Path

# Add sidecar to path
sidecar_path = Path(__file__).parent.parent.parent.parent / "sidecar"
sys.path.insert(0, str(sidecar_path))

from api.plugin_base import PluginBase

class Plugin(PluginBase):
    """My custom plugin."""
    
    def __init__(self, emitter, brain, plugin_dir, vault_path):
        """Initialize plugin - automatically sets up logging."""
        super().__init__(emitter, brain, plugin_dir, vault_path)
        
        # Load settings (helper method from PluginBase)
        settings = self.load_settings()
        self.my_setting = settings.get("key", "default")
        
        # Register commands
        self.register_commands()
        
        self.logger.info("My plugin initialized")
    
    def register_commands(self) -> None:
        """Register plugin commands."""
        self.brain.register_command(
            "myPlugin.action",
            self.custom_action,
            self.name
        )
    
    async def custom_action(self, **kwargs):
        """Custom action callable via execute_command."""
        self.emitter.notify("Action executed!", severity="success")
        return {"status": "ok"}
    
    async def on_tick(self, emitter):
        """Called every 5 seconds - optional lifecycle hook."""
        self.logger.debug("Tick from my plugin")
```

See [PLUGIN_GUIDE.md](PLUGIN_GUIDE.md) for complete plugin development guide.

## Event Emission

Plugins can emit events using the EventEmitter API or command registry:

```python
# Via EventEmitter (convenient)
emitter.notify("Task complete!")
emitter.progress(75, "Processing...")
emitter.update_state("task_count", 42)

# Via Command Registry (discoverable)
await brain.execute_command("ui.notify", message="Task complete!", severity="success")
await brain.execute_command("ui.progress", percent=75, status="Processing...")

# Scoped events
emitter.global_event("SYSTEM_ALERT", {"msg": "Important!"})  # All windows
emitter.vault_event("STATE_CHANGED", {"key": "value"})        # Same vault
```

## Building for Production

```bash
# Build application bundle
pixi run build
```

The compiled app will be in `src-tauri/target/release/bundle/`.

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT

## Documentation

For detailed architecture documentation, see:
- Architecture Overview: `.gemini/antigravity/brain/.../architecture_overview.md`
- Implementation Plan: `.gemini/antigravity/brain/.../implementation_plan.md`
- Event Bus Design: `.gemini/antigravity/brain/.../event_bus_design.md`