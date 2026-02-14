"""
Explorer Plugin → Chat History Sidebar

Provides a ChatGPT-style chat history sidebar for browsing, searching,
switching, renaming, and deleting chat sessions. Integrates with the
Memory plugin for persistence.
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
    Chat History Sidebar Plugin
    
    Renders a ChatGPT-style chat history in the sidebar, powered by
    the Memory plugin's persistence layer.
    """
    
    def __init__(
        self,
        plugin_dir: Path,
        vault_path: Path,
        config: Dict[str, Any] = None
    ):
        self._plugin_dir = Path(plugin_dir)
        self.ui_path = self._plugin_dir / "ui" / "panel.html"
        self.css_path = self._plugin_dir / "ui" / "styles.css"
        self.icon = "message-square"
        
        super().__init__(plugin_dir, vault_path, config)
        
    def register_commands(self) -> None:
        """Register chat history commands."""
        self.brain.register_command(
            "explorer.list_chats",
            self.list_chats,
            self.name
        )
        self.brain.register_command(
            "explorer.delete_chat",
            self.delete_chat,
            self.name
        )
        self.brain.register_command(
            "explorer.rename_chat",
            self.rename_chat,
            self.name
        )
        self.brain.register_command(
            "explorer.get_ui",
            self.get_ui,
            self.name
        )
        
    async def list_chats(self, query: str = "", **kwargs) -> Dict[str, Any]:
        """List all chats, optionally filtered by search query."""
        if not query:
            p = kwargs.get("p") or kwargs.get("params", {})
            query = p.get("query", "")
        
        try:
            result = await self.brain.execute_command(
                "memory.search", query=query
            )
            return result
        except Exception as e:
            self.logger.error(f"Failed to list chats: {e}")
            return {"status": "error", "error": str(e)}
    
    async def delete_chat(self, chat_id: str = "", **kwargs) -> Dict[str, Any]:
        """Delete a chat session."""
        if not chat_id:
            p = kwargs.get("p") or kwargs.get("params", {})
            chat_id = p.get("chat_id", "")
        
        try:
            result = await self.brain.execute_command(
                "memory.delete_chat", chat_id=chat_id
            )
            return result
        except Exception as e:
            self.logger.error(f"Failed to delete chat: {e}")
            return {"status": "error", "error": str(e)}
    
    async def rename_chat(self, chat_id: str = "", title: str = "", **kwargs) -> Dict[str, Any]:
        """Rename a chat session."""
        if not chat_id or not title:
            p = kwargs.get("p") or kwargs.get("params", {})
            chat_id = chat_id or p.get("chat_id", "")
            title = title or p.get("title", "")
        
        try:
            result = await self.brain.execute_command(
                "memory.rename_chat", chat_id=chat_id, title=title
            )
            return result
        except Exception as e:
            self.logger.error(f"Failed to rename chat: {e}")
            return {"status": "error", "error": str(e)}
    
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
            return "<p style='color:var(--text-secondary);'>Chat History UI not found.</p>"
    
    def _load_css(self) -> str:
        """Load the CSS from file."""
        if self.css_path.exists():
            return self.css_path.read_text(encoding="utf-8")
        return ""
    
    async def on_load(self) -> None:
        """Called after plugin is loaded."""
        await super().on_load()
        self.logger.info("Chat History sidebar plugin loaded")

    async def on_client_connected(self) -> None:
        """Register UI when client connects."""
        self.logger.info("Client connected, registering Chat History sidebar...")
        
        # Inject CSS into document head (separate from HTML for cleanliness)
        css = self._load_css()
        if css:
            self._emit_ui_command("inject_css", {
                "plugin_id": "explorer",
                "css": css
            })
        
        # Register the Sidebar View
        await self.register_sidebar_view(
            identifier="explorer.view",
            icon_svg=self.icon,
            title="CHATS"
        )
        
        # Set Initial Content
        html = self._load_html()
        await self.set_sidebar_content("explorer.view", html)
        
        self.logger.info("Chat History sidebar registered")
