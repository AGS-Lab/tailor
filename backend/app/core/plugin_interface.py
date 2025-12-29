from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BasePlugin(ABC):
    """
    Abstract base class for all Tailor plugins.
    Plugins can hook into various stages of the chat lifecycle.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name of the plugin."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Brief description of what the plugin does."""
        pass

    def on_startup(self) -> None:
        """Called when the application starts."""
        pass

    def transform_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Modify the list of messages before they are sent to the LLM.
        Useful for Memory plugins to inject history.
        """
        return messages

    def transform_system_prompt(self, system_prompt: str) -> str:
        """
        Modify the system prompt to change the bot's behavior or inject context.
        """
        return system_prompt

    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Return a list of tool definitions (JSON schema) that the LLM can using.
        """
        return []

    def execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Any:
        """
        Execute a tool if this plugin provides it.
        """
        return None

    def post_process_response(self, response: str) -> str:
        """
        Modify the final response before it is sent back to the user.
        """
        return response
