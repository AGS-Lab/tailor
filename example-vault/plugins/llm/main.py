"""
LLM Plugin - Chat interface with conversation history

Example plugin showing how to:
- Inherit from PluginBase
- Register commands
- Maintain plugin state
- Emit events to UI
- Use plugin settings
"""

import sys
from pathlib import Path
from typing import Dict, Any, List, TYPE_CHECKING, cast

# Add sidecar to path
# Add tailor root to path (parent of sidecar)
tailor_path = Path(__file__).resolve().parent.parent.parent.parent
if str(tailor_path) not in sys.path:
    sys.path.insert(0, str(tailor_path))

from sidecar.api.plugin_base import PluginBase
from sidecar.constants import EventType, EventScope

if TYPE_CHECKING:
    pass


class Plugin(PluginBase):
    """
    LLM Chat Plugin.
    
    Provides a conversational interface for the vault.
    """
    
    def __init__(
        self,
        plugin_dir: Path,
        vault_path: Path
    ):
        """Initialize LLM plugin."""
        super().__init__(plugin_dir, vault_path)
        
        # Plugin state
        self.conversation_history: List[Dict[str, str]] = []
        self.model_name = "gpt-4"  # Placeholder
        
        # Load settings
        settings = self.load_settings()
        if settings:
            self.model_name = cast(str, settings.get("model", self.model_name))
            self.logger.info(f"Using model: {self.model_name}")
        
        self.logger.info("LLM plugin initialized")
    
    def register_commands(self) -> None:
        """Register LLM commands."""
        self.brain.register_command(
            "llm.send",
            self._handle_send,
            self.name
        )
        self.brain.register_command(
            "llm.clear",
            self._handle_clear,
            self.name
        )
        self.brain.register_command(
            "llm.get_ui",
            self._handle_get_ui,
            self.name
        )
        
        self.logger.debug("Registered 3 LLM commands")
    
    async def _handle_send(self, message: str = "", **kwargs: Any) -> Dict[str, Any]:
        """Handle sending a message to the LLM."""
        if not message:
            return {"status": "error", "error": "Message cannot be empty"}
        
        self.logger.info(f"Received message: {message[:50]}...")
        
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": message
        })
        
        # Generate response (placeholder - integrate actual LLM here)
        response = await self._generate_response(message)
        
        # Add assistant response to history
        self.conversation_history.append({
            "role": "assistant",
            "content": response
        })
        
        # Emit event to update UI
        self.brain.emit_to_frontend(
            EventType.LLM_RESPONSE,
            {
                "user_message": message,
                "assistant_message": response,
                "history": self.conversation_history
            },
            scope=EventScope.WINDOW
        )
        
        self.logger.debug("Response generated and emitted")
        
        return {
            "status": "success",
            "response": response,
            "history_length": len(self.conversation_history)
        }
    
    async def _handle_clear(self, **kwargs: Any) -> Dict[str, Any]:
        """Clear conversation history."""
        previous_count = len(self.conversation_history)
        self.conversation_history = []
        
        self.logger.info(f"Cleared {previous_count} messages from history")
        
        # Notify UI
        self.brain.emit_to_frontend(EventType.LLM_CLEARED, {}, scope=EventScope.WINDOW)
        
        return {
            "status": "success",
            "message": "Conversation cleared",
            "cleared": previous_count
        }
    
    async def _handle_get_ui(self, **kwargs: Any) -> Dict[str, Any]:
        """Return HTML for the LLM chat UI."""
        ui_file = self.plugin_dir / "ui" / "panel.html"
        
        if ui_file.exists():
            with open(ui_file, "r", encoding="utf-8") as f:
                ui_html = f.read()
            return {
                "status": "success",
                "html": ui_html,
                "plugin_name": self.name
            }
        else:
            # Fallback HTML
            html = """
            <div class="llm-chat">
                <h2>LLM Chat</h2>
                <div id="chat-history"></div>
                <input type="text" id="chat-input" placeholder="Type a message..." />
                <button onclick="sendMessage()">Send</button>
            </div>
            """
            return {
                "status": "success",
                "html": html,
                "plugin_name": self.name
            }
    
    async def _generate_response(self, message: str) -> str:
        """Generate LLM response."""
        # Placeholder implementation
        if not message:
            return "Please send a message."
        
        if "hello" in message.lower() or "hi" in message.lower():
            return "Hello! I'm your vault AI assistant. How can I help you today?"
        
        if "?" in message:
            return f"That's an interesting question. I'm a demo LLM plugin, so I can't provide real answers yet. But you asked: '{message}'"
        
        # Echo back with word count
        word_count = len(message.split())
        return f"I received your message ({word_count} words). In a real implementation, I would process this with an LLM API and provide a meaningful response."
    
    async def on_load(self) -> None:
        """Called after plugin is loaded."""
        await super().on_load()
        
        self.notify(
            f"LLM plugin loaded (model: {self.model_name})",
            severity="success"
        )
    
    async def on_tick(self, brain) -> None:
        """Periodic tick."""
        # Log message count periodically (only if non-zero)
        if len(self.conversation_history) > 0:
            self.logger.debug(f"Conversation has {len(self.conversation_history)} messages")
    
    async def on_unload(self) -> None:
        """Called when plugin is unloaded."""
        # Save conversation history if needed
        if self.conversation_history:
            self.logger.info(f"Unloading with {len(self.conversation_history)} messages in history")
        
        await super().on_unload()
