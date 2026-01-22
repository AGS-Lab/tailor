from pathlib import Path
from typing import List, Dict, Any, Set
import uuid
import time

from sidecar.api.plugin_base import PluginBase
from sidecar.pipeline.events import PipelineEvents
from sidecar.pipeline.types import PipelineContext

class Plugin(PluginBase):
    """
    Chat Branches Plugin
    
    Manages branching by annotating messages with 'branches' field.
    Messages without 'branches' are common to all branches.
    """
    
    def __init__(self, plugin_dir: Path, vault_path: Path, config: Dict[str, Any] = None):
        super().__init__(plugin_dir, vault_path, config)
        self.active_branches = {}  # {chat_id: active_branch_id}

    def register_commands(self) -> None:
        """Register branching commands."""
        self.brain.register_command("branch.create", self.create_branch, self.name)
        self.brain.register_command("branch.switch", self.switch_branch, self.name)
        self.brain.register_command("branch.list", self.list_branches, self.name)
        
    async def on_load(self) -> None:
        """Load plugin."""
        self.logger.info("Chat Branches Plugin loaded.")
        
        # Override chat.get_history to provide branched history
        self.brain.register_command("chat.get_history", self.get_history, self.name, override=True)
        
        # Subscribe to track new messages
        self.subscribe(PipelineEvents.OUTPUT, self._annotate_new_messages, priority=5)
        
    async def on_client_connected(self) -> None:
        """Register UI when client connects."""
        self._emit_ui_command("register_action", {
            "id": "branch",
            "icon": "git-branch",
            "label": "Branch",
            "position": 50,
            "type": "button",
            "location": "message-actionbar",
            "command": "event:chat:createBranch"
        })

    async def _get_memory_plugin(self):
        """Helper to get memory plugin instance."""
        memory = self.brain.plugins.get("memory")
        if not memory:
            raise Exception("Memory plugin not available")
        return memory

    # =========================================================================
    # Event Handlers
    # =========================================================================

    async def _annotate_new_messages(self, ctx: PipelineContext) -> None:
        """Annotate new messages with current branch."""
        if not ctx.response:
            return
        
        chat_id = ctx.metadata.get("chat_id")
        if not chat_id:
            return
        
        # Get active branch for this chat
        active_branch = self.active_branches.get(chat_id)
        if not active_branch:
            return  # No active branch, leave messages common
        
        # Get generated message IDs
        generated_ids = ctx.metadata.get("generated_ids", {})
        user_msg_id = generated_ids.get("user_message_id")
        assistant_msg_id = generated_ids.get("assistant_message_id")
        
        if not (user_msg_id and assistant_msg_id):
            return
        
        # Load chat data
        memory = await self._get_memory_plugin()
        result = await memory.load_chat(chat_id=chat_id)
        if result.get("status") != "success":
            return
        
        data = result.get("data", {})
        messages = data.get("messages", [])
        
        # Find and annotate the new messages
        for msg in messages:
            if msg.get("id") in [user_msg_id, assistant_msg_id]:
                if "branches" not in msg:
                    msg["branches"] = []
                if active_branch not in msg["branches"]:
                    msg["branches"].append(active_branch)
        
        # Save back
        await memory.save_chat(chat_id=chat_id, data=data)
        self.logger.debug(f"Annotated messages with branch '{active_branch}'")

    # =========================================================================
    # Commands
    # =========================================================================

    async def create_branch(self, chat_id: str = "", message_id: str = "", name: str = None, **kwargs) -> Dict[str, Any]:
        """Create a new branch from a message."""
        if not chat_id:
            p = kwargs.get("p") or kwargs.get("params", {})
            chat_id = p.get("chat_id")
            message_id = p.get("message_id") or p.get("parent_message_id", message_id)
            name = p.get("name", name)
            
        if not chat_id:
            return {"status": "error", "error": "chat_id required"}
        
        try:
            # Generate branch ID
            branch_id = name or uuid.uuid4().hex[:8]
            
            # Load chat data
            memory = await self._get_memory_plugin()
            result = await memory.load_chat(chat_id=chat_id)
            data = result.get("data", {"messages": []})
            messages = data.get("messages", [])
            
            # Determine source branch (default to "main" if not set)
            source_branch = self.active_branches.get(chat_id, "main")
            
            # Store branch metadata
            if "branches" not in data:
                data["branches"] = {}
            data["branches"][branch_id] = {
                "parent_message_id": message_id,
                "source_branch": source_branch,
                "created_at": time.time()
            }
            
            # Approach 2: Explicit Branching
            # 1. Identify common ancestor (messages up to message_id) - Leave them untouched (Common)
            # 2. Identify divergent path (messages AFTER message_id) - Tag them with source_branch
            
            found_split = False
            for msg in messages:
                if not found_split:
                    if msg.get("id") == message_id:
                        found_split = True
                else:
                    # Message is AFTER split point
                    # It belongs to the source branch path, not the new branch
                    # Explicitly tag it with source branch if not already tagged
                    if "branches" not in msg or not msg["branches"]:
                        msg["branches"] = [source_branch]
                    elif source_branch not in msg["branches"]:
                        # If we are forking from an existing branch, keep the existing tag
                        pass
            
            if not found and message_id:
                return {"status": "error", "error": f"Message '{message_id}' not found"}
            
            # Save back
            await memory.save_chat(chat_id=chat_id, data=data)
            
            # Set as active
            self.active_branches[chat_id] = branch_id
            
            # Get filtered history for this new branch
            history = await self._get_filtered_history(chat_id, branch_id)
            
            self.logger.info(f"Created branch '{branch_id}' from message '{message_id}' for chat '{chat_id}'")
            
            return {
                "status": "success",
                "branch": branch_id,
                "history": history
            }
            
        except Exception as e:
            self.logger.error(f"Error creating branch: {e}")
            return {"status": "error", "error": str(e)}

    async def switch_branch(self, chat_id: str = "", branch: str = "", **kwargs) -> Dict[str, Any]:
        """Switch to a different branch."""
        if not chat_id:
            p = kwargs.get("p") or kwargs.get("params", {})
            chat_id = p.get("chat_id")
            branch = p.get("branch", branch)
        
        try:
            # Set as active (default to "main" if empty)
            target_branch = branch or "main"
            self.active_branches[chat_id] = target_branch
            
            # Get history
            history = await self._get_filtered_history(chat_id, target_branch)
            
            return {
                "status": "success",
                "branch": branch or "main",
                "history": history
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def list_branches(self, chat_id: str = "", **kwargs) -> Dict[str, Any]:
        """List all branches in a chat."""
        if not chat_id:
            p = kwargs.get("p") or kwargs.get("params", {})
            chat_id = p.get("chat_id")
        
        try:
            result = await self.brain.execute_command("chat.load", chat_id=chat_id)
            if result.get("status") != "success":
                return result
            
            data = result.get("data", {})
            messages = data.get("messages", [])
            
            # Extract all unique branch IDs
            branch_ids: Set[str] = set()
            for msg in messages:
                branches = msg.get("branches", [])
                branch_ids.update(branches)
            
            branches_meta = {
                "main": {
                    "id": "main",
                    "display_name": "Main"
                }
            }
            
            for bid in branch_ids:
                branches_meta[bid] = {
                    "id": bid,
                    "display_name": bid
                }
            
            return {
                "status": "success",
                "chat_id": chat_id,
                "active_branch": self.active_branches.get(chat_id, "main"),
                "branches": branches_meta
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def get_history(self, chat_id: str = "", branch: str = None, **kwargs) -> Dict[str, Any]:
        """Get history filtered by branch."""
        if not chat_id:
            p = kwargs.get("p") or kwargs.get("params", {})
            chat_id = p.get("chat_id")
            branch = p.get("branch", branch)
        
        try:
            # Use active branch if not specified
            if branch is None:
                branch = self.active_branches.get(chat_id)
            
            history = await self._get_filtered_history(chat_id, branch)
            
            return {
                "status": "success",
                "chat_id": chat_id,
                "history": history,
                "active_branch": branch or "main"
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _get_filtered_history(self, chat_id: str, branch_id: str = None) -> List[Dict[str, Any]]:
        """Get messages filtered by branch."""
        result = await self.brain.execute_command("chat.load", chat_id=chat_id)
        
        if result.get("status") != "success":
            return []
        
        data = result.get("data", {})
        messages = data.get("messages", [])
        
        if not branch_id:
            return [msg for msg in messages if "branches" not in msg or not msg["branches"]]
        
        filtered = []
        for msg in messages:
            branches = msg.get("branches", [])
            if not branches or branch_id in branches:
                filtered.append(msg)
        
        return filtered
