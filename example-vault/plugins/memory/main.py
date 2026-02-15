import asyncio
import json
import os
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
        self.brain.register_command("memory.delete_chat", self.delete_chat, self.name)
        self.brain.register_command("memory.rename_chat", self.rename_chat, self.name)
        self.brain.register_command("memory.rename_chat", self.rename_chat, self.name)
        self.brain.register_command("chat.get_history", self.get_chat_history, self.name)
        self.brain.register_command("chat.auto_title", self.manual_auto_title, self.name)
        
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
                    
                    # Title: stored title, or first user message as fallback
                    title = data.get("title", "")
                    if not title:
                        for msg in messages:
                            if msg.get("role") == "user":
                                title = str(msg.get("content", ""))[:60]
                                break
                    if not title:
                        title = "Untitled Chat"
                    
                    # Filter
                    if query:
                        query_lower = query.lower()
                        found = query_lower in title.lower()
                        if not found:
                            for msg in messages:
                                if query_lower in str(msg.get("content", "")).lower():
                                    found = True
                                    break
                        if not found:
                            continue
                    
                    matches.append({
                        "id": chat_id,
                        "title": title,
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

    async def delete_chat(self, chat_id: str = "", **kwargs) -> Dict[str, Any]:
        """Delete a chat file."""
        if not chat_id:
            p = kwargs.get("p") or kwargs.get("params", {})
            chat_id = p.get("chat_id")
            
        if not chat_id:
            return {"status": "error", "error": "chat_id required"}
            
        chat_file = self._get_chat_path(chat_id)
        if not chat_file.exists():
            return {"status": "error", "error": "Chat not found"}
            
        try:
            os.remove(chat_file)
            self.logger.info(f"Deleted chat: {chat_id}")
            return {"status": "success"}
        except Exception as e:
            self.logger.error(f"Failed to delete chat {chat_id}: {e}")
            return {"status": "error", "error": str(e)}

    async def rename_chat(self, chat_id: str = "", title: str = "", **kwargs) -> Dict[str, Any]:
        """Rename a chat by setting its title metadata."""
        if not chat_id or not title:
            p = kwargs.get("p") or kwargs.get("params", {})
            chat_id = chat_id or p.get("chat_id", "")
            title = title or p.get("title", "")
            
        if not chat_id or not title:
            return {"status": "error", "error": "chat_id and title required"}
            
        chat_file = self._get_chat_path(chat_id)
        if not chat_file.exists():
            return {"status": "error", "error": "Chat not found"}
            
        try:
            with open(chat_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            data["title"] = title
            
            with open(chat_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            
            self.logger.info(f"Renamed chat {chat_id} to: {title}")
            return {"status": "success"}
        except Exception as e:
            self.logger.error(f"Failed to rename chat {chat_id}: {e}")
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
        
        # Truncate if max_messages is set
        max_msgs = self.config.get("max_messages", 0)
        if max_msgs > 0 and len(data["messages"]) > max_msgs:
            # Keep the last N messages
            data["messages"] = data["messages"][-max_msgs:]
            self.logger.debug(f"Truncated chat {chat_id} to last {max_msgs} messages")
        
        # Save back
        await self.brain.execute_command("memory.save_chat", chat_id=chat_id, data=data)
        self.logger.info(f"Saved interaction to {chat_id}.json")
        
        # Store generated IDs in metadata
        ctx.metadata["generated_ids"] = {
            "user_message_id": user_msg["id"],
            "assistant_message_id": assistant_msg["id"],
            "chat_id": chat_id
        }
        
        # Auto-title: generate once after first exchange
        if self.config.get("auto_title", True) and not data.get("title"):
            asyncio.create_task(self._auto_generate_title(chat_id, data))

    # =========================================================================
    # Auto Title Generation
    # =========================================================================

    async def _auto_generate_title(self, chat_id: str, data: dict) -> None:
        """Generate a chat title from the first user+assistant exchange."""
        try:
            messages = data.get("messages", [])
            if len(messages) < 2:
                return

            # Use just the first user message and assistant response
            user_msg = messages[0].get("content", "")[:300]
            assistant_msg = messages[1].get("content", "")[:300]

            llm_messages = [
                {
                    "role": "system",
                    "content": (
                        "You generate concise chat titles.\n"
                        "Task: Create a clear, specific 3–6 word title summarizing the main topic.\n\n"
                        "Rules:\n"
                        "- Capture the core subject, not conversational filler.\n"
                        "- Be specific, not generic (avoid 'Discussion' or 'Question').\n"
                        "- Use Title Case.\n"
                        "- No punctuation.\n"
                        "- No quotation marks.\n"
                        "- No emojis.\n"
                        "- Do not invent information.\n"
                        "- Output ONLY the title text."
                    )
                },
                {
                    "role": "user",
                    "content": f"User: {user_msg}\nAssistant: {assistant_msg}"
                }
            ]

            from sidecar.services.llm_service import get_llm_service
            llm = get_llm_service()
            if not llm:
                return

            category = self.config.get("title_category", "fast")
            
            response = await llm.complete(
                messages=llm_messages,
                category=category,
                max_tokens=20,
                temperature=0.3
            )

            title = response.content.strip().strip('"\'.-').strip()
            if not title or len(title) < 2:
                return
                
            max_len = self.config.get("title_max_length", 50)
            if len(title) > max_len:
                title = title[:max_len-3] + "..."

            chat_file = self._get_chat_path(chat_id)
            if chat_file.exists():
                with open(chat_file, "r", encoding="utf-8") as f:
                    current_data = json.load(f)
                current_data["title"] = title
                with open(chat_file, "w", encoding="utf-8") as f:
                    json.dump(current_data, f, indent=2)
                self.logger.info(f"Auto-title: {chat_id} -> '{title}'")

        except Exception as e:
            self.logger.warning(f"Auto-title failed for {chat_id}: {e}")

    async def manual_auto_title(self, chat_id: str = "", **kwargs) -> Dict[str, Any]:
        """Manually trigger auto-titling for a chat."""
        if not chat_id:
            p = kwargs.get("p") or kwargs.get("params", {})
            chat_id = p.get("chat_id")
            
        if not chat_id:
             return {"status": "error", "error": "chat_id required"}

        # Load data
        result = await self.brain.execute_command("memory.load_chat", chat_id=chat_id)
        if result.get("status") != "success":
            return result
            
        data = result.get("data", {})
        
        # Trigger background generation
        asyncio.create_task(self._auto_generate_title(chat_id, data))
        
        return {"status": "success", "message": "Auto-titling started"}
