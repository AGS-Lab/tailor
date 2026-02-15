"""
Message Summarizer Plugin

Adds a "Summarize" button to the message action toolbar that uses an LLM
to create concise summaries of long assistant responses.

Features:
- TL;DR preview (1-2 lines) + expandable full summary
- Persistent storage in .memory/{chat_id}.json
- Minimum length guardrail (200 characters)
- Three-dots menu: Save, Replace, Delete
- Assets loaded from external files (styles.css, scripts.js)
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any

# Add tailor root to path for imports
tailor_path = Path(__file__).resolve().parent.parent.parent
if str(tailor_path) not in sys.path:
    sys.path.insert(0, str(tailor_path))

from sidecar.api.plugin_base import PluginBase
from sidecar.constants import EventType, Severity


# Minimum characters required to summarize
MIN_CHARS_TO_SUMMARIZE = 200

# System prompt for summarization
SUMMARIZER_SYSTEM_PROMPT = """You are an expert at creating concise, high-signal summaries.

Return a JSON object with exactly this structure:
{
  "tldr": "A brief 1-2 sentence summary (max 150 characters)",
  "full": "• Key point 1\\n• Key point 2\\n• Key point 3\\n..."
}

Rules:
1. "tldr" must be under 150 characters
2. "full" should have 3-7 bullet points using • character
3. Extract only important, actionable information
4. Return ONLY valid JSON, no markdown
"""


class Plugin(PluginBase):
    """Message Summarizer Plugin - uses external asset files."""
    
    def __init__(self, plugin_dir: Path, vault_path: Path, config: Dict[str, Any] = None):
        super().__init__(plugin_dir, vault_path, config)
        self.memory_dir = vault_path / ".memory"
        
        # Load assets from files
        self.css = self._load_asset("styles.css")
        self.js = self._load_asset("scripts.js")
        
        self.logger.info("Summarizer plugin initialized")
    
    def _load_asset(self, filename: str) -> str:
        """Load an asset file from the plugin directory."""
        asset_path = self.plugin_dir / filename
        if asset_path.exists():
            return asset_path.read_text(encoding="utf-8")
        self.logger.warning(f"Asset not found: {filename}")
        return ""
    
    def register_commands(self) -> None:
        """Register plugin commands."""
        commands = [
            ("summarizer.summarize", self._handle_summarize),
            ("summarizer.delete_summary", self._handle_delete_summary),
            ("summarizer.replace_message", self._handle_replace_message),
            ("summarizer.save_bookmark", self._handle_save_bookmark),
        ]
        for cmd_id, handler in commands:
            self.brain.register_command(cmd_id, handler, self.name)
    
    async def on_client_connected(self) -> None:
        """Register UI elements when frontend connects."""
        self.logger.info("Client connected - registering summarizer UI")
        
        # 1. Inject CSS
        if self.css:
            self.brain.emit_to_frontend(
                event_type=EventType.UI_COMMAND,
                data={"action": "inject_css", "plugin_id": "summarizer", "css": self.css}
            )
        
        # 2. Inject JavaScript
        if self.js:
            self.brain.emit_to_frontend(
                event_type=EventType.UI_COMMAND,
                data={
                    "action": "inject_html",
                    "id": "summarizer-js",
                    "target": "head",
                    "position": "beforeend",
                    "html": f"<script id='summarizer-js'>{self.js}</script>"
                }
            )
        
        # 3. Register toolbar button
        self.brain.emit_to_frontend(
            event_type=EventType.UI_COMMAND,
            data={
                "action": "register_action",
                "id": "summarizer",
                "icon": "file-text",
                "label": "Summarize",
                "position": 15,
                "type": "button",
                "command": "summarizer.summarize",
                "location": "message-actionbar"
            }
        )
        
        self.logger.info("Registered summarizer UI elements")
    
    def _get_memory_file(self, chat_id: str) -> Path:
        safe_id = "".join(x for x in chat_id if x.isalnum() or x in "-_")
        return self.memory_dir / f"{safe_id}.json"
    
    def _load_memory(self, chat_id: str) -> tuple[Any, list]:
        """Load memory, handling both legacy (list) and v2 (dict) formats."""
        f = self._get_memory_file(chat_id)
        if f.exists():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                
                # Check for V2 format
                if isinstance(data, dict) and "branches" in data and "active_branch" in data:
                    active_branch = data.get("active_branch", "main")
                    branches = data.get("branches", {})
                    return data, branches.get(active_branch, [])
                
                # Legacy format
                if isinstance(data, list):
                    return data, data
                
                return data, []
            except Exception as e:
                self.logger.error(f"Failed to load memory: {e}")
        return [], []
    
    def _save_memory(self, chat_id: str, data: Any) -> bool:
        try:
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            self._get_memory_file(chat_id).write_text(
                json.dumps(data, indent=2), encoding="utf-8"
            )
            return True
        except Exception as e:
            self.logger.error(f"Failed to save memory: {e}")
            return False
    
    def _create_summary_html(self, msg_id: str, msg_idx: int, chat_id: str, tldr: str, full: str) -> str:
        """Generate HTML for the summary container."""
        safe_tldr = tldr.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        safe_full = full.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        safe_full = safe_full.replace("\\n", "<br>").replace("\n", "<br>")
        
        return f'''<div id="summary-{msg_id}" class="summary-container" data-message-id="{msg_id}" data-message-index="{msg_idx}" data-chat-id="{chat_id}">
    <div class="summary-header">
        <span class="summary-label"><i data-lucide="file-text"></i>Summary</span>
        <div class="summary-menu-wrapper">
            <button class="summary-menu-btn" onclick="window.toggleSummaryMenu(this)" title="More options">
                <i data-lucide="more-vertical"></i>
            </button>
        </div>
    </div>
    <div class="summary-tldr">{safe_tldr}</div>
    <button class="summary-expand-btn" onclick="window.toggleSummaryExpand(this)">
        <i data-lucide="chevron-down"></i><span>Show more</span>
    </button>
    <div class="summary-full collapsed">{safe_full}</div>
</div>'''
    
    async def _handle_summarize(self, message_id: str = "", message_index: int = -1, 
                                 content: str = "", chat_id: str = "", **kwargs) -> Dict[str, Any]:
        """Summarize a message."""
        self.logger.info(f"Summarize: message_id={message_id}, index={message_index}")
        
        # Guardrail
        stripped_len = len(content.strip()) if content else 0
        if stripped_len < MIN_CHARS_TO_SUMMARIZE:
            self.notify(f"Message too short ({stripped_len} chars). Min {MIN_CHARS_TO_SUMMARIZE} required.", severity=Severity.WARNING)
            return {"status": "error", "error": "too_short"}
        
        # Check for cached summary
        if chat_id and message_index >= 0:
            full_data, memory_list = self._load_memory(chat_id)
            if message_index < len(memory_list):
                existing = memory_list[message_index].get("summary")
                if existing:
                    self._inject_summary_html(message_id, message_index, chat_id, 
                                               existing["tldr"], existing["full"])
                    return {"status": "success", "cached": True}
        
        # Check LLM
        if not self.brain or not self.brain.pipeline:
            self.notify("LLM not available.", severity=Severity.ERROR)
            return {"status": "error", "error": "llm_unavailable"}
        
        try:
            # Call LLM
            from sidecar.services.llm_service import get_llm_service
            llm = get_llm_service()
            if not llm:
                 self.notify("LLM service execution failed", severity=Severity.ERROR)
                 return {"status": "error", "error": "llm_unavailable"}

            category = self.config.get("summary_category", "fast")
            prompt = f"{SUMMARIZER_SYSTEM_PROMPT}\n\nText to summarize:\n{content}"
            
            # Using complete instead of pipeline.run to support category/model selection
            response = await llm.complete(
                messages=[{"role": "user", "content": prompt}],
                category=category,
                temperature=0.3
            )
            
            if response and response.content:
                # Mock ctx object for compatibility with existing parsing logic
                class MockCtx:
                     pass
                ctx = MockCtx()
                ctx.response = response.content
            
            if ctx.response:
                # Parse response
                try:
                    text = ctx.response.strip()
                    if text.startswith("```"):
                        lines = text.split("\n")
                        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
                    
                    data = json.loads(text)
                    tldr, full = data.get("tldr", ""), data.get("full", "")
                    if not tldr or not full:
                        raise ValueError("Missing fields")
                except (json.JSONDecodeError, ValueError):
                    full = ctx.response.strip()
                    tldr = full[:147] + "..." if len(full) > 150 else full
                
                # Save to memory
                if chat_id and message_index >= 0:
                    full_data, memory_list = self._load_memory(chat_id)
                    if message_index < len(memory_list):
                        memory_list[message_index]["summary"] = {"tldr": tldr, "full": full}
                        self._save_memory(chat_id, full_data)
                
                # Inject UI
                self._inject_summary_html(message_id, message_index, chat_id, tldr, full)
                self.notify("Summary generated!", severity="success")
                return {"status": "success", "summary": {"tldr": tldr, "full": full}}
            
            self.notify("Empty LLM response", severity=Severity.ERROR)
            return {"status": "error", "error": "empty_response"}
            
        except Exception as e:
            self.logger.exception(f"Error: {e}")
            self.notify(f"Error: {e}", severity=Severity.ERROR)
            return {"status": "error", "error": str(e)}
    
    def _inject_summary_html(self, msg_id: str, msg_idx: int, chat_id: str, tldr: str, full: str):
        """Inject summary HTML into the frontend."""
        html = self._create_summary_html(msg_id, msg_idx, chat_id, tldr, full)
        self.brain.emit_to_frontend(
            event_type=EventType.UI_COMMAND,
            data={
                "action": "inject_html",
                "id": f"summary-{msg_id}",
                "target": f"[data-message-id='{msg_id}'] .message-toolbar-container",
                "position": "beforebegin",
                "html": html
            }
        )
    
    async def _handle_delete_summary(self, message_id: str = "", message_index: int = -1,
                                      chat_id: str = "", **kwargs) -> Dict[str, Any]:
        """Delete a summary."""
        if chat_id and message_index >= 0:
            full_data, memory_list = self._load_memory(chat_id)
            if message_index < len(memory_list) and "summary" in memory_list[message_index]:
                del memory_list[message_index]["summary"]
                self._save_memory(chat_id, full_data)
        
        self.brain.emit_to_frontend(
            event_type=EventType.UI_COMMAND,
            data={"action": "remove_html", "id": f"summary-{message_id}"}
        )
        self.notify("Summary deleted", severity="success")
        return {"status": "success"}
    
    async def _handle_replace_message(self, message_id: str = "", message_index: int = -1,
                                        chat_id: str = "", **kwargs) -> Dict[str, Any]:
        """Replace message with summary."""
        if not chat_id or message_index < 0:
            return {"status": "error", "message": "Invalid parameters"}
        
        full_data, memory_list = self._load_memory(chat_id)
        if message_index >= len(memory_list):
            return {"status": "error", "message": "Not found"}
        
        summary = memory_list[message_index].get("summary")
        if not summary:
            return {"status": "error", "message": "No summary"}
        
        text = f"TL;DR: {summary['tldr']}\n\n{summary['full']}"
        memory_list[message_index]["original_content"] = memory_list[message_index].get("content", "")
        memory_list[message_index]["content"] = text
        del memory_list[message_index]["summary"]
        self._save_memory(chat_id, full_data)
        
        safe_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        self.brain.emit_to_frontend(
            event_type=EventType.UI_COMMAND,
            data={"action": "update_html", "selector": f"[data-message-id='{message_id}'] .message-content", "html": safe_text}
        )
        self.brain.emit_to_frontend(
            event_type=EventType.UI_COMMAND,
            data={"action": "remove_html", "id": f"summary-{message_id}"}
        )
        
        self.notify("Message replaced", severity="success")
        return {"status": "success"}
    
    async def _handle_save_bookmark(self, **kwargs) -> Dict[str, Any]:
        self.notify("Summary saved to bookmarks!", severity="success")
        return {"status": "success"}
    
    async def on_load(self) -> None:
        await super().on_load()
        self.logger.info("Summarizer plugin loaded")
