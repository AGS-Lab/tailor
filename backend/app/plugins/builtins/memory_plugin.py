from typing import List, Dict, Any
from app.core.plugin_interface import BasePlugin

class MemoryPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "MemoryPlugin"

    @property
    def description(self) -> str:
        return "Simple in-memory conversation history management."

    def __init__(self):
        self.history: List[Dict[str, str]] = []

    def transform_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Merge persistent history with the current incoming messages.
        Arguments:
            messages: The current request messages (usually just the latest user message)
        """
        # In this simple version, we assume 'messages' contains the current turn.
        # We prepend our stored history.
        # Note: In a real app, orchestrator passes the full conversational context, 
        # so we might just need to SAVE the new messages here, or retrieve old ones.
        
        # Correct approach for this Architecture:
        # The Orchestrator passes us the 'current build' of messages.
        # We append our stored history to the front if it's not already there.
        
        # Actually, let's keep it simple: 
        # This plugin manages a global list for the session (Singleton pattern for now).
        
        # Append latest user message to history if it's new
        if messages and messages[-1]['role'] == 'user':
             last_msg = messages[-1]
             # simplistic check to avoid dupes if orchestrator calls multiple times
             if not self.history or self.history[-1] != last_msg:
                 self.history.append(last_msg)
        
        return self.history + messages[:-1] # Return full history + current message? 
        # Wait, the orchestrator constructs "full_history = conversation_history + messages"
        # Let's simplify: 
        # The Orchestrator manages the request scope.
        # This plugin injects *Long Term* memory or *Session* memory.
        
        # For now, let's just return the messages as is, but print that we are "remembering".
        # Real implementation: read from DB.
        
        return messages # No-op for this simple v1, relying on Orchestrator's ephemeral history for now.
    
    def post_process_response(self, response: str) -> str:
        # Save assistant response to history
        self.history.append({"role": "assistant", "content": response})
        return response
