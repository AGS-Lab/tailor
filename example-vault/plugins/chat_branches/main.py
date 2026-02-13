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
        self.brain.register_command("branch.delete", self.delete_branch, self.name)
        
    async def on_load(self) -> None:
        """Load plugin."""
        self.logger.info("Chat Branches Plugin loaded.")
        
        # Override chat.get_history to provide branched history
        self.brain.register_command("chat.get_history", self.get_history, self.name, override=True)
        
        # Subscribe to track new messages
        self.subscribe(PipelineEvents.OUTPUT, self._annotate_new_messages, priority=5)
        
    async def on_client_connected(self) -> None:
        """Register UI when client connects."""
        # Register Branch button action
        self._emit_ui_command("register_action", {
            "id": "branch",
            "icon": "git-branch",
            "label": "Branch",
            "position": 50,
            "type": "button",
            "location": "message-actionbar",
            "command": "event:chat:createBranch"
        })
        
        # Load frontend JavaScript module
        ui_path = self.plugin_dir / "ui.js"
        if ui_path.exists():
            try:
                with open(ui_path, 'r', encoding='utf-8') as f:
                    ui_code = f.read()
                
                # Inject script using inject_html action
                # DO NOT use f-strings for the whole payload as it corrupts JavaScript braces
                self._emit_ui_command("inject_html", {
                    "id": "plugin-script-" + self.name,
                    "target": "head",
                    "position": "beforeend",
                    "html": "<script>" + ui_code + "</script>"
                })
                self.logger.info("Loaded frontend UI module")
            except Exception as e:
                self.logger.error(f"Failed to load UI module: {e}")

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
        result = await self.brain.execute_command("memory.load_chat", chat_id=chat_id)
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
        result = await self.brain.execute_command("memory.save_chat", chat_id=chat_id, data=data)
        self.logger.debug(f"Annotated messages with branch '{active_branch}'")

    # =========================================================================
    # Commands
    # =========================================================================

    async def create_branch(self, chat_id: str = "", message_id: str = "", branch_id: str = None, **kwargs) -> Dict[str, Any]:
        """Create a new branch from a message."""
        self.logger.info("Chat Branches: Creating branch...")

        if not chat_id:
            p = kwargs.get("p") or kwargs.get("params", {})
            chat_id = p.get("chat_id")
            message_id = p.get("message_id") or p.get("parent_message_id", message_id)
            branch_id = p.get("branch_id", branch_id)
            
        if not chat_id:
            return {"status": "error", "error": "chat_id required"}
        
        try:
            branch_id = branch_id or uuid.uuid4().hex[:8]
            
            result = await self.brain.execute_command("memory.load_chat", chat_id=chat_id)
            data = result.get("data", {"messages": []})
            messages = data.get("messages", [])
            
            # 1. Locate Split Point & Identify Source Branch from Message
            # We must do this BEFORE assuming source_branch is active_branches[chat_id]
            # because the user might be branching off an ancestor message (Root).
            
            target_msg = None
            split_index = -1
            for i, msg in enumerate(messages):
                if msg.get("id") == message_id:
                    target_msg = msg
                    split_index = i
                    break
            
            if not target_msg:
                 return {"status": "error", "error": f"Message '{message_id}' not found"}

            # Determine which branch this message belongs to
            msg_branches = target_msg.get("branches", [])
            
            if not msg_branches:
                # If message has no branch, it belongs to the "Root" (or implicit main)
                # Check if we have an explicit root defined
                # Find the root branch (one with no parent)
                root_id = None
                for bid, bdata in data.get("branches", {}).items():
                    if bdata.get("parent_branch") is None:
                        root_id = bid
                        break
                source_branch = root_id or "main"
            else:
                # In strict tree, usually 1 branch per message.
                # Use the first one.
                source_branch = msg_branches[0]
            
            # Ensure "branches" dict exists
            if "branches" not in data:
                data["branches"] = {}

            # Lazy Root Generation again just in case
            if source_branch == "main" or source_branch not in data["branches"]:
                root_id = uuid.uuid4().hex[:8]
                data["branches"][root_id] = {
                    "display_name": None, # Explicitly null
                    "created_at": time.time(),
                    "parent_branch": None,
                    "parent_message_id": None
                }
                
                # Tag all currently untagged messages with root_id
                for msg in messages:
                    if "branches" not in msg or not msg["branches"]:
                        msg["branches"] = [root_id]
                    elif "main" in msg["branches"]:
                        msg["branches"] = [root_id if b == "main" else b for b in msg["branches"]]
                
                source_branch = root_id
                # If we just created root, and the message was previously untagged, 
                # make sure we use this new root as source
                pass
            
            # Re-fetch message branches in case they were just lazy-updated
            # (Loop updated the list objects, so target_msg (reference) should be updated? 
            #  Yes, dicts are mutable references).
            
            # Check if we are still "main" (shouldn't be)
            
            
            # Messages after the split point
            tail_messages = messages[split_index+1:]
            
            # Filter tail to only those actually belonging to source_branch hierarchy
            # (In a simple linear view, this is just the rest of the list, but be safe)
            actual_tail_messages = []
            for msg in tail_messages:
                branches = msg.get("branches", [])
                if source_branch in branches:
                    actual_tail_messages.append(msg)
            
            # 3. Execute Split
            existing_children_to_reparent = []
            
            # Check if Mid-Split (Tail exists)
            if actual_tail_messages:
                # Create Continuation Branch
                continuation_id = uuid.uuid4().hex[:8]
                data["branches"][continuation_id] = {
                    "display_name": None,
                    "created_at": time.time(),
                    "parent_branch": source_branch,
                    "parent_message_id": message_id
                }
                
                # Move Tail Messages
                moved_message_ids = set()
                for msg in actual_tail_messages:
                    msg_branches = msg.get("branches", [])
                    if source_branch in msg_branches:
                        msg_branches.remove(source_branch)
                        msg_branches.append(continuation_id)
                    msg["branches"] = msg_branches
                    moved_message_ids.add(msg.get("id"))
                    
                # Identify Orphans (Branches that were children of source attached to tail)
                for bid, b_data in data["branches"].items():
                    p_branch = b_data.get("parent_branch")
                    p_msg = b_data.get("parent_message_id")
                    if p_branch == source_branch and p_msg in moved_message_ids:
                        existing_children_to_reparent.append(bid)
                        
                # Reparent Orphans
                for child_bid in existing_children_to_reparent:
                    data["branches"][child_bid]["parent_branch"] = continuation_id
                    
                self.logger.info(f"Split branch '{source_branch}' at '{message_id}'. Created continuation '{continuation_id}' with {len(actual_tail_messages)} msgs.")

            # 4. Create New Branch
            data["branches"][branch_id] = {
                "display_name": kwargs.get("name"), # None if not provided
                "created_at": time.time(),
                "parent_branch": source_branch,
                "parent_message_id": message_id
            }
            
            # Save back
            result = await self.brain.execute_command("memory.save_chat", chat_id=chat_id, data=data)
            
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
            import traceback
            tb = traceback.format_exc()
            self.logger.error(f"Error creating branch: {e}\n{tb}")
            return {"status": "error", "error": f"{str(e)}\n{tb}"}

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
            result = await self.brain.execute_command("memory.load_chat", chat_id=chat_id)
            if result.get("status") != "success":
                return result
            
            data = result.get("data", {})
            messages = data.get("messages", [])
            
            # Extract all unique branch IDs
            branch_ids: Set[str] = set()
            for msg in messages:
                branches = msg.get("branches", [])
                branch_ids.update(branches)
            
            # Get branches from metadata
            branches_meta = data.get("branches", {})
            
            # If empty (linear chat), ensure we at least return a virtual main if requested?
            # actually, frontend expects what we have.
            if not branches_meta and not branch_ids:
                 branches_meta = {
                    "main": {
                        "id": "main",
                        "display_name": None,
                        "created_at": 0
                    }
                }
            
            # Ensure all used branches are in meta (handle legacy/implicit main)
            for bid in branch_ids:
                if bid == "main" and "main" not in branches_meta:
                     branches_meta["main"] = {
                        "id": "main", 
                        "display_name": None
                    }
                elif bid not in branches_meta:
                    # Should unlikely happen if we manage meta correctly
                    branches_meta[bid] = {
                        "id": bid,
                        "display_name": None
                    }
            
            return {
                "status": "success",
                "chat_id": chat_id,
                "active_branch": self.active_branches.get(chat_id, "main"),
                "branches": branches_meta
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def delete_branch(self, chat_id: str = "", branch_id: str = "", **kwargs) -> Dict[str, Any]:
        """Delete a branch."""
        if not chat_id:
            p = kwargs.get("p") or kwargs.get("params", {})
            chat_id = p.get("chat_id")
            branch_id = p.get("branch_id", branch_id)

        if not chat_id or not branch_id:
            return {"status": "error", "error": "chat_id and branch_id are required"}

        try:
            result = await self.brain.execute_command("memory.load_chat", chat_id=chat_id)
            if result.get("status") != "success":
                return result

            data = result.get("data", {})
            messages = data.get("messages", [])
            branches_meta = data.get("branches", {})

            # Validate branch exists
            if branch_id not in branches_meta:
                return {"status": "error", "error": f"Branch '{branch_id}' not found"}

            branch_info = branches_meta[branch_id]

            # Prevent deleting root branches (no parent)
            if branch_info.get("parent_branch") is None:
                return {"status": "error", "error": "Cannot delete the root branch"}

            # Prevent deleting branches that have children
            children = [bid for bid, bdata in branches_meta.items()
                        if bdata.get("parent_branch") == branch_id]
            if children:
                return {"status": "error", "error": f"Cannot delete branch with children: {', '.join(children)}. Delete children first."}

            # Remove messages that belong ONLY to this branch
            surviving_messages = []
            for msg in messages:
                msg_branches = msg.get("branches", [])
                if branch_id in msg_branches:
                    msg_branches = [b for b in msg_branches if b != branch_id]
                    if not msg_branches:
                        # Message was exclusive to this branch, remove it
                        continue
                    msg["branches"] = msg_branches
                surviving_messages.append(msg)

            data["messages"] = surviving_messages

            # Remove branch metadata
            del branches_meta[branch_id]

            # Save back
            await self.brain.execute_command("memory.save_chat", chat_id=chat_id, data=data)

            # If deleted branch was active, switch to parent
            parent_branch = branch_info.get("parent_branch", "main")
            if self.active_branches.get(chat_id) == branch_id:
                self.active_branches[chat_id] = parent_branch

            self.logger.info(f"Deleted branch '{branch_id}' from chat '{chat_id}'")

            # Rebuild history for the new active branch
            active = self.active_branches.get(chat_id, parent_branch)
            history = await self._get_filtered_history(chat_id, active)

            return {
                "status": "success",
                "deleted_branch": branch_id,
                "active_branch": active,
                "history": history
            }
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.logger.error(f"Error deleting branch: {e}\n{tb}")
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
            
            # Load branches metadata for frontend UI
            result = await self.brain.execute_command("memory.load_chat", chat_id=chat_id)
            branches_meta = {}
            if result.get("status") == "success":
                data = result.get("data", {})
                branches_meta = data.get("branches", {})
            
            return {
                "status": "success",
                "chat_id": chat_id,
                "history": history,
                "branches": branches_meta,
                "active_branch": branch or "main"
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _get_filtered_history(self, chat_id: str, branch_id: str = None) -> List[Dict[str, Any]]:
        """Get messages filtered by branch."""
        result = await self.brain.execute_command("memory.load_chat", chat_id=chat_id)
        
        if result.get("status") != "success":
            return []
        
        data = result.get("data", {})
        messages = data.get("messages", [])
        
        if not branch_id:
            # Legacy/Linear case
            return [msg for msg in messages if "branches" not in msg or not msg["branches"]]
        
        # 1. Build Ancestry Path (e.g., [Grandchild, Child, Root])
        ancestry = []
        current_bid = branch_id
        branches_meta = data.get("branches", {})
        
        while current_bid:
            ancestry.append(current_bid)
            parent = branches_meta.get(current_bid, {}).get("parent_branch")
            # Loop protection
            if parent in ancestry:
                break
            current_bid = parent
            
        # 2. Collect messages belonging to any branch in ancestry
        # Since messages are stored in chronological order in the list, 
        # we can just iterate once and pick what we need.
        filtered = []
        for msg in messages:
            msg_branches = msg.get("branches", [])
            
            # Check if this message belongs to any branch in our ancestry path
            # In Split-Parent logic, a message should restricted to ONE branch ID usually,
            # but we check intersection to be safe.
            matching_branch = next((b for b in msg_branches if b in ancestry), None)
            
            # Common messages (no branches tag) are implied root/base
            is_common = not msg_branches
            
            if matching_branch or is_common:
                # Create a copy to inject metadata without altering storage
                msg_copy = msg.copy()
                
                # Frontend needs 'source_branch' to render dividers
                # If common, maybe valid? But usually we want the ID.
                # If it matched an ancestor, use that ancestor ID.
                if matching_branch:
                    msg_copy["source_branch"] = matching_branch
                elif is_common:
                     # If common, it technically belongs to the "root-most" or implicit main.
                     # Let's leave it empty or set to root if we have one?
                     # For now, leave empty implies "Common/Main".
                     pass
                     
                filtered.append(msg_copy)
        
        return filtered
