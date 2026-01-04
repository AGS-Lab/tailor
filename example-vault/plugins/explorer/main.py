"""
Explorer Plugin

Provides a file explorer sidebar view for navigating vault contents.
Uses PluginBase for standardized plugin structure.
"""
import sys
from pathlib import Path
from typing import Dict, Any

# Add tailor root to path
tailor_path = Path(__file__).resolve().parent.parent.parent.parent
if str(tailor_path) not in sys.path:
    sys.path.insert(0, str(tailor_path))

from sidecar.api.plugin_base import PluginBase


class Plugin(PluginBase):
    """
    Explorer Plugin
    
    Demonstrates the use of the Side Panel API to render a file explorer.
    Inherits from PluginBase for standardized lifecycle management.
    """
    
    def __init__(self, plugin_dir: Path, vault_path: Path):
        # Store UI path before super().__init__ calls register_commands
        self._plugin_dir = Path(plugin_dir)
        self.ui_path = self._plugin_dir / "ui" / "panel.html"
        self.icon = "folder-open"
        
        super().__init__(plugin_dir, vault_path)
        
    def register_commands(self) -> None:
        """Register plugin commands."""
        self.brain.register_command(
            "explorer.get_ui",
            self.get_ui,
            self.name
        )
        
    async def get_ui(self, **kwargs) -> Dict[str, Any]:
        """Return the Explorer panel HTML."""
        html = self._load_html()
        return {"html": html}
    
    def _load_html(self) -> str:
        """Load the panel HTML from file."""
        if self.ui_path.exists():
            return self.ui_path.read_text(encoding="utf-8")
        else:
            self.logger.warning(f"UI file not found: {self.ui_path}")
            return "<p style='color:var(--text-secondary);'>Explorer UI not found.</p>"
    
    async def on_load(self) -> None:
        """Called after plugin is loaded."""
        await super().on_load()
        self.logger.info("Explorer plugin fully loaded")

    async def on_client_connected(self) -> None:
        """Register UI when client connects."""
        self.logger.info("Client connected, registering Explorer UI...")
        
        # Register the Sidebar View
        await self.register_sidebar_view(
            identifier="explorer.view",
            icon_svg=self.icon,
            title="EXPLORER"
        )
        
        # Set Initial Content
        html = self._load_html()
        await self.set_sidebar_content("explorer.view", html)
        
        self.notify("Explorer plugin loaded!", severity="success")
