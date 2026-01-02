"""
Demo Plugin - Example plugin showing all PluginBase features

This plugin demonstrates:
- Inheriting from PluginBase
- Registering commands
- Using lifecycle hooks
- Loading/saving settings
- Emitting events
"""

import sys
from pathlib import Path
from typing import Dict, Any, TYPE_CHECKING, cast

# Add sidecar to path
# Add tailor root to path (parent of sidecar)
tailor_path = Path(__file__).resolve().parent.parent.parent.parent
if str(tailor_path) not in sys.path:
    sys.path.insert(0, str(tailor_path))

from sidecar.api.plugin_base import PluginBase

if TYPE_CHECKING:
    from event_emitter import EventEmitter
    from vault_brain import VaultBrain


class Plugin(PluginBase):
    """
    Demo plugin showing PluginBase usage.
    
    This is a reference implementation for plugin developers.
    """
    
    def __init__(
        self,
        emitter: 'EventEmitter',
        brain: 'VaultBrain',
        plugin_dir: Path,
        vault_path: Path
    ):
        """Initialize demo plugin."""
        super().__init__(emitter, brain, plugin_dir, vault_path)
        
        # Plugin-specific state
        self.counter = 0
        
        # Load settings
        settings = self.load_settings()
        self.counter = cast(int, settings.get("counter", 0))
        
        self.logger.info("Demo plugin initialized")
    
    def register_commands(self) -> None:
        """Register demo commands."""
        # Simple command
        self.brain.register_command(
            "demo.hello",
            self.handle_hello,
            self.name
        )
        
        # Command with parameters
        self.brain.register_command(
            "demo.increment",
            self.handle_increment,
            self.name
        )
        
        # Command that uses settings
        self.brain.register_command(
            "demo.get_count",
            self.handle_get_count,
            self.name
        )
        
        self.logger.debug("Registered 3 demo commands")
    
    async def handle_hello(self, name: str = "World", **kwargs: Any) -> Dict[str, Any]:
        """
        Simple hello command.
        
        Args:
            name: Name to greet
        
        Returns:
            Greeting message
        """
        message = f"Hello, {name}!"
        
        # Emit notification to UI
        self.emitter.notify(message, severity="info")
        
        return {
            "status": "success",
            "message": message
        }
    
    async def handle_increment(self, amount: int = 1, **kwargs: Any) -> Dict[str, Any]:
        """
        Increment the counter.
        
        Args:
            amount: Amount to increment by
        
        Returns:
            New counter value
        """
        self.counter += amount
        
        # Save to settings
        settings = self.load_settings()
        settings["counter"] = self.counter
        self.save_settings(settings)
        
        self.logger.info(f"Counter incremented to {self.counter}")
        
        # Emit progress update
        self.emitter.progress(
            min(100, self.counter),
            f"Counter: {self.counter}"
        )
        
        return {
            "status": "success",
            "counter": self.counter,
            "incremented_by": amount
        }
    
    async def handle_get_count(self, **kwargs: Any) -> Dict[str, Any]:
        """Get current counter value."""
        return {
            "status": "success",
            "counter": self.counter
        }
    
    async def on_load(self) -> None:
        """Called after plugin is loaded."""
        await super().on_load()
        
        self.emitter.notify(
            f"Demo plugin loaded (counter: {self.counter})",
            severity="success"
        )
    
    async def on_tick(self, emitter: 'EventEmitter') -> None:
        """
        Periodic tick - demonstrates background processing.
        
        Every 5 seconds, emit an event showing the plugin is running.
        """
        # Only emit every 10 ticks (every ~50 seconds) to avoid spam
        if self.counter % 10 == 0:
            self.logger.debug(f"Demo plugin tick (counter: {self.counter})")
    
    async def on_unload(self) -> None:
        """Called when plugin is unloaded."""
        # Save final state
        settings = {"counter": self.counter}
        self.save_settings(settings)
        
        await super().on_unload()
        
        self.logger.info(f"Demo plugin unloaded (final counter: {self.counter})")
