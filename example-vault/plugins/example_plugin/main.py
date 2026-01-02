"""
Example Plugin - Demonstrates plugin capabilities

This plugin shows how to:
- Receive EventEmitter in __init__
- Use on_tick hook for periodic tasks
- Emit notifications and events
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add tailor root to path (parent of sidecar)
tailor_path = Path(__file__).resolve().parent.parent.parent.parent
if str(tailor_path) not in sys.path:
    sys.path.insert(0, str(tailor_path))

from sidecar.api.plugin_base import PluginBase


class Plugin(PluginBase):
    """Example plugin that demonstrates command registration and execution."""
    
    def __init__(self, emitter, brain, plugin_dir, vault_path):
        """
        Initialize plugin with EventEmitter and VaultBrain.
        
        Args:
            emitter: EventEmitter instance for sending events
            brain: VaultBrain instance for command registration
            plugin_dir: Path to plugin directory (contains main.py)
            vault_path: Path to vault root (for accessing configs/)
        """
        self.emitter = emitter
        self.brain = brain
        self.plugin_dir = plugin_dir
        self.vault_path = vault_path
        self.name = "example_plugin"
        self.tick_count = 0
        
        # Load plugin config from vault/configs/example_plugin/
        self.config = self._load_config()
        
        print(f"[{self.name}] Plugin initialized from {plugin_dir}")
        
        # Register commands (like VSCode/Obsidian)
        brain.register_command("example.customAction", self.custom_action, self.name)
        brain.register_command("example.getStatus", self.get_status, self.name)
        brain.register_command("example.callOtherPlugin", self.call_other_plugin_example, self.name)
        
        # Send initialization notification
        self.emitter.notify(
            f"Plugin '{self.name}' loaded successfully!",
            severity="success"
        )
    
    def _load_config(self):
        """Load plugin configuration from settings.json in plugin directory."""
        import json
        config_file = self.plugin_dir / "settings.json"
        
        if config_file.exists():
            with open(config_file, "r") as f:
                return json.load(f)
        
        # Default configuration
        return {
            "heartbeat_interval": 3,  # Every 3 ticks
            "enabled": True
        }
    
    async def on_tick(self, emitter):
        """
        Called every 5 seconds by VaultBrain.
        
        Args:
            emitter: EventEmitter instance
        """
        self.tick_count += 1
        current_time = datetime.now().strftime("%H:%M:%S")
        
        print(f"[{self.name}] Tick #{self.tick_count} at {current_time}")
        
        # Every N ticks (configurable), send a notification
        heartbeat_interval = self.config.get("heartbeat_interval", 3)
        if self.tick_count % heartbeat_interval == 0:
            emitter.notify(
                f"Heartbeat #{self.tick_count // heartbeat_interval} from {self.name}",
                severity="info"
            )
        
        # Update state
        emitter.update_state("tick_count", self.tick_count)
        emitter.update_state("last_tick", current_time)
    
    async def custom_action(self, **kwargs):
        """
        Custom action registered as 'example.customAction'.
        Can be called by UI or other plugins via execute_command.
        
        Args:
            **kwargs: Action parameters
        """
        print(f"[{self.name}] Custom action called with: {kwargs}")
        
        self.emitter.notify(
            "Custom action executed!",
            severity="success"
        )
        
        return {"status": "completed", "kwargs": kwargs}
    
    async def get_status(self, **kwargs):
        """
        Get plugin status - registered as 'example.getStatus'.
        
        Returns:
            Plugin status information
        """
        return {
            "name": self.name,
            "tick_count": self.tick_count,
            "status": "active"
        }
    
    async def call_other_plugin_example(self, plugin_command: str, **kwargs):
        """
        Example of calling another plugin's command.
        Registered as 'example.callOtherPlugin'.
        
        This demonstrates plugin-to-plugin communication via command registry.
        
        Args:
            plugin_command: Command ID to call (e.g., "database.query")
            **kwargs: Arguments to pass to the other command
        
        Example:
            await brain.execute_command("example.callOtherPlugin", 
                                       plugin_command="database.query",
                                       table="users")
        """
        try:
            result = await self.brain.execute_command(plugin_command, **kwargs)
            self.emitter.notify(
                f"Successfully called {plugin_command}",
                severity="success"
            )
            return {"called": plugin_command, "result": result}
        except ValueError as e:
            self.emitter.notify(
                f"Command not found: {plugin_command}",
                severity="error"
            )
            return {"error": str(e)}
