"""
Demo UI Plugin - Demonstrates all UI registration capabilities

This plugin shows how to use:
- register_sidebar_view() - Add sidebar items
- register_panel() - Add GoldenLayout tabs
- register_toolbar_button() - Add toolbar buttons
- set_stage_content() - Set main stage area
- show_modal() / close_modal() - Show modal dialogs
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
    """Demo plugin showcasing UI capabilities."""
    
    def __init__(
        self,
        plugin_dir: Path,
        vault_path: Path,
        config: Dict[str, Any] = None
    ):
        super().__init__(plugin_dir, vault_path, config)
        self.logger.info("Demo UI plugin initialized")
    
    def register_commands(self) -> None:
        """Register demo commands."""
        self.brain.register_command(
            "demo_ui.show_modal",
            self._handle_show_modal,
            self.name
        )
        self.brain.register_command(
            "demo_ui.update_stage",
            self._handle_update_stage,
            self.name
        )
        self.brain.register_command(
            "demo_ui.toolbar_action",
            self._handle_toolbar_action,
            self.name
        )
        self.logger.debug("Registered demo UI commands")
    
    async def on_client_connected(self) -> None:
        """Called when frontend connects - register UI elements."""
        self.logger.info("Client connected - registering UI elements")
        
        # Register a sidebar view
        await self.register_sidebar_view(
            identifier="demo_explorer",
            icon_svg="box",  # Lucide icon name
            title="Demo Explorer"
        )
        
        # Set initial sidebar content
        await self.set_sidebar_content(
            identifier="demo_explorer",
            html_content="""
                <div style="padding: 12px;">
                    <h4 style="margin: 0 0 12px 0; color: var(--text-secondary);">Demo Plugin</h4>
                    <p style="color: var(--text-muted); font-size: 0.9rem;">
                        This sidebar was created by the demo_ui plugin!
                    </p>
                    <button onclick="window.request('execute_command', {command: 'demo_ui.show_modal', args: {}})"
                            class="btn btn-primary" style="width: 100%; margin-top: 12px;">
                        Show Modal
                    </button>
                </div>
            """
        )
        
        # Register a toolbar button
        await self.register_toolbar_button(
            button_id="demo_run",
            icon="play",
            title="Run Demo Action",
            command="demo_ui.toolbar_action"
        )
        
        # Register a new panel/tab
        await self.register_panel(
            panel_id="demo_output",
            title="Demo Output",
            icon="terminal",
            position="right"
        )
        
        # Set panel content
        await self.set_panel_content(
            panel_id="demo_output",
            html_content="""
                <div style="font-family: monospace; color: var(--text-secondary);">
                    <div style="color: var(--accent-green);">[demo_ui]</div>
                    <div>Plugin loaded successfully!</div>
                    <div>Use the toolbar button or sidebar to interact.</div>
                </div>
            """
        )
        
        self.notify("Demo UI plugin ready!", severity="success")
    
    async def _handle_show_modal(self, **kwargs) -> Dict[str, Any]:
        """Show a demo modal dialog."""
        await self.show_modal(
            title="Demo Modal",
            html_content="""
                <div>
                    <p>This is a modal dialog created by a plugin!</p>
                    <p>Plugins can use modals for:</p>
                    <ul>
                        <li>Configuration dialogs</li>
                        <li>Confirmation prompts</li>
                        <li>Information display</li>
                    </ul>
                    <button onclick="window.request('execute_command', {command: 'demo_ui.update_stage', args: {}})"
                            class="btn btn-primary">
                        Update Stage Content
                    </button>
                </div>
            """,
            width="400px"
        )
        return {"status": "success", "message": "Modal shown"}
    
    async def _handle_update_stage(self, **kwargs) -> Dict[str, Any]:
        """Update the main stage area."""
        await self.close_modal()
        
        await self.set_stage_content("""
            <div style="padding: 40px; text-align: center;">
                <div style="font-size: 3rem; margin-bottom: 20px;">🎉</div>
                <h2 style="margin: 0 0 12px 0;">Stage Content Updated!</h2>
                <p style="color: var(--text-muted);">
                    This content was set by the demo_ui plugin using set_stage_content()
                </p>
            </div>
        """)
        
        return {"status": "success", "message": "Stage updated"}
    
    async def _handle_toolbar_action(self, **kwargs) -> Dict[str, Any]:
        """Handle toolbar button click."""
        self.notify("Toolbar button clicked!", severity="info")
        
        # Update panel with timestamp
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        await self.set_panel_content(
            panel_id="demo_output",
            html_content=f"""
                <div style="font-family: monospace; color: var(--text-secondary);">
                    <div style="color: var(--accent-green);">[{timestamp}]</div>
                    <div>Toolbar action executed!</div>
                </div>
            """
        )
        
        return {"status": "success", "message": "Toolbar action executed"}
    
    async def on_load(self) -> None:
        """Called after plugin is loaded."""
        await super().on_load()
        self.logger.info("Demo UI plugin loaded")
    
    async def on_unload(self) -> None:
        """Called when plugin is unloaded."""
        await super().on_unload()
        self.logger.info("Demo UI plugin unloaded")
