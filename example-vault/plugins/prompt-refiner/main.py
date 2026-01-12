"""
Prompt Refiner Plugin

Adds a "Refine" button to the vault UI that uses an LLM to improve
the user's prompt before sending it to the main chat.

Features:
- Toolbar button to trigger refinement
- Validates that input is not empty
- Uses LLM to refine/improve prompts
- Automatically updates the chat input field
"""

import sys
from pathlib import Path
from typing import Dict, Any

# Add tailor root to path for imports
tailor_path = Path(__file__).resolve().parent.parent.parent
if str(tailor_path) not in sys.path:
    sys.path.insert(0, str(tailor_path))

from sidecar.api.plugin_base import PluginBase
from sidecar.constants import EventType, Severity


# System prompt for the refiner LLM
REFINER_SYSTEM_PROMPT = """You are a prompt engineering expert. Your job is to take a user's rough prompt and refine it to be:

1. **Clear**: Remove ambiguity and be specific about what is being asked
2. **Concise**: Remove unnecessary words while keeping meaning
3. **Structured**: Add structure if the prompt is complex
4. **Complete**: Add missing context that would help get a better response

Rules:
- Return ONLY the refined prompt, no explanations
- Preserve the original intent completely
- Keep the same language/tone as the original
- If the prompt is already good, make minimal changes
- Do not add greetings or pleasantries

Example:
Input: "explain python decorators"
Output: "Explain Python decorators with the following: 1) What they are and their purpose, 2) How the @ syntax works, 3) A simple example with code, 4) Common use cases like @property and @staticmethod."
"""


class Plugin(PluginBase):
    """
    Prompt Refiner Plugin.
    
    Adds a toolbar button that refines the user's prompt using an LLM
    before sending it to the main chat.
    """
    
    def __init__(
        self,
        plugin_dir: Path,
        vault_path: Path,
        config: Dict[str, Any] = None
    ):
        super().__init__(plugin_dir, vault_path, config)
        self.logger.info("Prompt Refiner plugin initialized")
    
    def register_commands(self) -> None:
        """Register plugin commands."""
        self.brain.register_command(
            "refiner.refine",
            self._handle_refine,
            self.name
        )
        self.logger.debug("Registered refiner.refine command")
    
    async def on_client_connected(self) -> None:
        """Called when frontend connects - register UI elements."""
        self.logger.info("Client connected - registering refiner UI")
        
        # Register the refine button in the toolbar
        await self.register_toolbar_button(
            button_id="refiner_btn",
            icon="sparkles",  # Lucide icon
            title="Refine Prompt",
            command="refiner.refine_from_ui"
        )
        
        # Register a WebSocket handler for the UI button
        self.brain.ws_server.register_handler(
            "refiner.refine_from_ui",
            self._handle_refine_from_ui
        )
        
        self.notify("Prompt Refiner ready! Click ✨ to refine your prompts.", severity="success")
    
    async def _handle_refine_from_ui(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle refine request from UI - gets text from frontend."""
        # This handler is called when the toolbar button is clicked
        # We need to tell the frontend to send us the current input text
        
        # Emit an event asking frontend for the current input
        self.brain.emit_to_frontend(
            event_type=EventType.UI_COMMAND,
            data={
                "action": "request_input",
                "callback_command": "refiner.refine"
            }
        )
        
        return {"status": "pending", "message": "Requesting input from UI"}
    
    async def _handle_refine(self, text: str = "", **kwargs) -> Dict[str, Any]:
        """
        Refine the given text using the LLM.
        
        Args:
            text: The prompt text to refine
            
        Returns:
            Dict with refined prompt or error
        """
        # Guardrail: Check for empty input
        if not text or not text.strip():
            self.notify(
                "Please enter some text before refining!",
                severity=Severity.WARNING
            )
            return {
                "status": "error",
                "error": "empty_input",
                "message": "Please enter text in the chat box before clicking Refine."
            }
        
        original_text = text.strip()
        self.logger.info(f"Refining prompt: {original_text[:50]}...")
        
        # Check if LLM pipeline is available
        if not self.brain or not self.brain.pipeline:
            self.notify(
                "LLM not available. Please check your API key configuration.",
                severity=Severity.ERROR
            )
            return {
                "status": "error",
                "error": "llm_unavailable",
                "message": "LLM pipeline not initialized"
            }
        
        try:
            # Call LLM with refiner system prompt
            # Prepend system context to the message for refinement
            refine_prompt = f"{REFINER_SYSTEM_PROMPT}\n\nUser prompt to refine:\n{original_text}"
            
            ctx = await self.brain.pipeline.run(
                message=refine_prompt,
                history=[]
            )
            
            if ctx.response:
                refined_text = ctx.response.strip()
                
                # Send refined text back to frontend to update input
                self.brain.emit_to_frontend(
                    event_type=EventType.UI_COMMAND,
                    data={
                        "action": "set_input",
                        "text": refined_text
                    }
                )
                
                self.notify("Prompt refined! Review and send when ready.", severity="success")
                
                self.logger.info(f"Prompt refined successfully")
                
                return {
                    "status": "success",
                    "original": original_text,
                    "refined": refined_text
                }
            else:
                error_msg = "Empty response from LLM"
                self.notify(f"Refinement failed: {error_msg}", severity=Severity.ERROR)
                return {
                    "status": "error",
                    "error": "refinement_failed",
                    "message": error_msg
                }
                
        except Exception as e:
            self.logger.exception(f"Error refining prompt: {e}")
            self.notify(f"Error: {str(e)}", severity=Severity.ERROR)
            return {
                "status": "error",
                "error": "exception",
                "message": str(e)
            }
    
    async def on_load(self) -> None:
        """Called after plugin is loaded."""
        await super().on_load()
        self.logger.info("Prompt Refiner plugin loaded")
    
    async def on_unload(self) -> None:
        """Called when plugin is unloaded."""
        self.logger.info("Prompt Refiner plugin unloading")
        await super().on_unload()
