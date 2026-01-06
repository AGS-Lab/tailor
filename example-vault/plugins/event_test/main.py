import sys
from pathlib import Path
from typing import Dict, Any

# Add tailor root to path (parent of sidecar)
tailor_path = Path(__file__).resolve().parent.parent.parent.parent
if str(tailor_path) not in sys.path:
    sys.path.insert(0, str(tailor_path))

from sidecar.api.plugin_base import PluginBase
from sidecar.constants import CoreEvents

class Plugin(PluginBase):
    """
    Event Bus Test Plugin.
    
    Demonstrates:
    1. Subscribing to events (Core & Custom)
    2. Publishing events
    3. Receiving and handling data via **kwargs
    """
    
    
    def __init__(
        self,
        plugin_dir: Path,
        vault_path: Path,
        config: Dict[str, Any] = None
    ):
        super().__init__(plugin_dir, vault_path, config)
        
        # 1. Subscribe to a Core Event
        self.subscribe(CoreEvents.PLUGIN_LOADED, self.on_plugin_loaded)
        
        # 2. Subscribe to a Custom Event (namespaced)
        self.subscribe("event_test:ping", self.on_ping)
        
    def register_commands(self) -> None:
        self.brain.register_command(
            "event_test.trigger",
            self.handle_trigger,
            self.name
        )
        
    async def on_load(self) -> None:
        await super().on_load()
        # Publish an event on load
        await self.publish(CoreEvents.PLUGIN_LOADED, plugin_name=self.name)
        
    async def on_tick(self) -> None:
        # Periodically publish a ping event
        import time
        if int(time.time()) % 10 == 0:
            await self.publish("event_test:ping", timestamp=time.time(), source="tick")

    # --- Event Handlers ---
    
    async def on_plugin_loaded(self, plugin_name: str, **kwargs):
        """React to any plugin loading."""
        self.logger.info(f"EVENT RECEIVED: Plugin '{plugin_name}' was loaded!")
        
    async def on_ping(self, timestamp: float, source: str, **kwargs):
        """React to our own ping."""
        self.logger.info(f"EVENT RECEIVED: Ping from {source} at {timestamp}")

    # --- Command Handlers ---

    async def handle_trigger(self, **kwargs):
        """Manually fire an event via command."""
        self.logger.info("Command received. Firing 'event_test:ping'...")
        await self.publish("event_test:ping", timestamp=0, source="command")
        return {"status": "fired"}
