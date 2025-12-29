from typing import List, Dict, Any
from app.core.plugin_interface import BasePlugin

class SystemIdentityPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "SystemIdentityPlugin"

    @property
    def description(self) -> str:
        return "Defines the core personality of the Tailor assistant."

    def transform_system_prompt(self, system_prompt: str) -> str:
        identity = """
You are Tailor, a personalized AI assistant designed to adapt to the user's workflow.
You are extensible, modular, and precise.
Always verify your tools before claiming to do something.
If a user asks to create a plugin, guide them through the Python code required.
"""
        return f"{identity}\n{system_prompt}"
