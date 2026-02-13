import json
import time
import uuid
from pathlib import Path
from typing import Dict, Any

from sidecar.api.plugin_base import PluginBase
from sidecar.pipeline.events import PipelineEvents
from sidecar.pipeline.types import PipelineContext

class Plugin(PluginBase):
    """
    Memory Plugin - Pure JSON Persistence Layer
    
    Schema-agnostic: just reads/writes JSON files.
    Does not interpret or validate structure.
    """
    
    def __init__(self, plugin_dir: Path, vault_path: Path, config: Dict[str, Any] = None):
        super().__init__(plugin_dir, vault_path, config)
        self.memory_dir = vault_path / ".memory"

    def register_commands(self) -> None:
        """Register memory commands."""
        self.brain.register_command("memory.load_chat", self.load_chat, self.name)
        self.brain.register_command("memory.save_chat", self.save_chat, self.name)
        self.brain.register_command("memory.search", self.search_chats, self.name)
        self.brain.register_command("chat.get_history", self.get_chat_history, self.name)
        
    async def on_load(self) -> None:
        """Load memory and subscribe to pipeline events."""
        await super().on_load()
        if not self.memory_dir.exists():
            self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        self.subscribe(PipelineEvents.OUTPUT, self.save_interaction, priority=10)
        
        self.logger.info("Memory Plugin loaded.")

    def _get_chat_path(self, chat_id: str) -> Path:
        """Get safe path for chat ID."""
        safe_id = "".join(x for x in chat_id if x.isalnum() or x in "-_")
        return self.memory_dir / f"{safe_id}.json"

    # =========================================================================
    # Pure Persistence API - No Schema Validation
    # =========================================================================

    async def load_chat(self, chat_id: str = "", **kwargs) -> Dict[str, Any]:
        """Load raw chat data (schema-agnostic)."""
        if not chat_id:
            p = kwargs.get("p") or kwargs.get("params", {})
            chat_id = p.get("chat_id")
            
        if not chat_id:
            return {"status": "error", "error": "chat_id required"}
            
        chat_file = self._get_chat_path(chat_id)
        if not chat_file.exists():
            return {"status": "success", "data": {"messages": []}}
            
        try:
            with open(chat_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {"status": "success", "data": data}
        except Exception as e:
            self.logger.error(f"Failed to load chat {chat_file}: {e}")
            return {"status": "error", "error": str(e)}

    async def save_chat(self, chat_id: str = "", data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """Save raw chat data (schema-agnostic)."""
        if not chat_id:
            p = kwargs.get("p") or kwargs.get("params", {})
            chat_id = p.get("chat_id")
            data = p.get("data", data)
            
        if not chat_id or data is None:
            return {"status": "error", "error": "chat_id and data required"}
            
        chat_file = self._get_chat_path(chat_id)
        try:
            if not self.memory_dir.exists():
                self.memory_dir.mkdir(parents=True, exist_ok=True)
                
            with open(chat_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            
            self.logger.debug(f"Saved chat to {chat_file.name}")
            return {"status": "success"}
        except Exception as e:
            self.logger.error(f"Failed to save chat {chat_file}: {e}")
            return {"status": "error", "error": str(e)}

    async def get_chat_history(self, chat_id: str = "", **kwargs) -> Dict[str, Any]:
        """Get messages from chat (convenience wrapper)."""
        result = await self.brain.execute_command("memory.load_chat", chat_id=chat_id)
        if result.get("status") != "success":
            return result
        
        messages = result.get("data", {}).get("messages", [])
        return {
            "status": "success",
            "chat_id": chat_id,
            "history": messages
        }

    async def search_chats(self, query: str = "", **kwargs) -> Dict[str, Any]:
        """Search or list chats."""
        if not query:
            p = kwargs.get("p") or kwargs.get("params", {})
            query = p.get("query", "")
        
        matches = []
        try:
            for chat_file in self.memory_dir.glob("*.json"):
                try:
                    with open(chat_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    messages = data.get("messages", [])
                    if not messages:
                        continue
                        
                    # Basic metadata
                    chat_id = chat_file.stem
                    last_msg = messages[-1]
                    # Handle legacy/missing time markers
                    try:
                        timestamp = float(last_msg.get("time_marker", 0))
                    except (ValueError, TypeError):
                        timestamp = chat_file.stat().st_mtime

                    preview = str(last_msg.get("content", ""))[:100]
                    
                    # Filter
                    if query:
                        # naive search: check if query in any message content
                        found = False
                        for msg in messages:
                            if query.lower() in str(msg.get("content", "")).lower():
                                found = True
                                break
                        if not found:
                            continue
                    
                    matches.append({
                        "id": chat_id,
                        "timestamp": timestamp,
                        "preview": preview,
                        "message_count": len(messages)
                    })
                except Exception:
                    continue
            
            # Sort by timestamp desc
            matches.sort(key=lambda x: x["timestamp"], reverse=True)
            
            return {"status": "success", "data": matches}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # =========================================================================
    # Event Handlers
    # =========================================================================

    async def save_interaction(self, ctx: PipelineContext) -> None:
        """Append messages to chat file."""
        if not ctx.response:
            return
            
        if ctx.metadata.get("save_to_memory") is False:
            return
            
        chat_id = ctx.metadata.get("chat_id")
        if not chat_id:
            chat_id = f"chat_{int(time.time())}"
            ctx.metadata["chat_id"] = chat_id
        
        # Load existing data
        result = await self.brain.execute_command("memory.load_chat", chat_id=chat_id)
        data = result.get("data", {"messages": []})
        
        # Ensure messages array exists
        if "messages" not in data:
            data["messages"] = []
        
        # Create message entries
        time_marker = str(time.time())
        
        user_msg = {
            "id": uuid.uuid4().hex[:8],
            "role": "user", 
            "content": ctx.message, 
            "time_marker": time_marker
        }
        
        assistant_msg = {
            "id": uuid.uuid4().hex[:8],
            "role": "assistant", 
            "content": ctx.response, 
            "time_marker": time_marker
        }
        
        # Append messages
        data["messages"].append(user_msg)
        data["messages"].append(assistant_msg)
        
        # Save back
        await self.brain.execute_command("memory.save_chat", chat_id=chat_id, data=data)
        self.logger.info(f"Saved interaction to {chat_id}.json")
        
        # Store generated IDs in metadata
        ctx.metadata["generated_ids"] = {
            "user_message_id": user_msg["id"],
            "assistant_message_id": assistant_msg["id"],
            "chat_id": chat_id
        }
