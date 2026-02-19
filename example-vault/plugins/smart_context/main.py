"""
Smart Context Plugin
"""

import sys
from pathlib import Path
from typing import Dict, Any

# Add tailor root to path for imports if needed, though usually available in plugin context
tailor_path = Path(__file__).resolve().parent.parent.parent.parent
if str(tailor_path) not in sys.path:
    sys.path.insert(0, str(tailor_path))

from sidecar.api.plugin_base import PluginBase
from sidecar.constants import EventType

class Plugin(PluginBase):
    """
    Smart Context Plugin.
    Renders a panel in the UI.
    """
    
    def __init__(
        self,
        plugin_dir: Path,
        vault_path: Path,
        config: Dict[str, Any] = None
    ):
        super().__init__(plugin_dir, vault_path, config)
        self.logger.info("Smart Context plugin initialized")
        self.panel_id = "smart-context-panel"
    
    def register_commands(self) -> None:
        """Register plugin commands."""
        # No commands to register yet
        pass
    
    async def on_client_connected(self) -> None:
        """Called when frontend connects - register UI elements."""
        self.logger.info("Client connected - registering Smart Context panel")
        
        # Register the panel
        await self.register_panel(
            panel_id=self.panel_id,
            title="Smart Context",
            icon="brain", 
            position="right"
        )
        
        # Set initial content
        await self.set_panel_content(
            panel_id=self.panel_id,
            html_content="<div style='padding: 10px;'><h3>Smart Context</h3><p>Waiting for context...</p></div>"
        )
        
        self.logger.info("Registered Smart Context panel")

    async def on_load(self) -> None:
        """Called after plugin is loaded."""
        await super().on_load()
        self.logger.info("Smart Context plugin loaded")

    async def on_unload(self) -> None:
        """Called when plugin is unloaded."""
        self.logger.info("Smart Context plugin unloading")
        await self.remove_panel(self.panel_id)
        await super().on_unload()
