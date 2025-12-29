import os
from typing import List, Dict, Any
from app.core.plugin_interface import BasePlugin

class FileContextPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "FileContextPlugin"

    @property
    def description(self) -> str:
        return "Provides tools to read and list files in the current directory."

    def transform_system_prompt(self, system_prompt: str) -> str:
        cwd = os.getcwd()
        return f"{system_prompt}\nYou have access to the file system. Current working directory: {cwd}"

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files in a directory",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "The path to list. Defaults to current directory."}
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read the contents of a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "The path to the file to read."}
                        },
                        "required": ["path"]
                    }
                }
            }
        ]

    def execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Any:
        if tool_name == "list_files":
            path = tool_args.get("path", ".")
            try:
                return str(os.listdir(path))
            except Exception as e:
                return str(e)
        elif tool_name == "read_file":
            path = tool_args.get("path")
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                return str(e)
        return None
