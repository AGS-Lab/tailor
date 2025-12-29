from typing import List, Dict, Any
import json
from app.services.llm import LLMClient
from app.core.plugin_interface import BasePlugin
from app.core.plugin_loader import PluginLoader

class Orchestrator:
    def __init__(self, llm_client: LLMClient, plugin_loader: PluginLoader):
        self.llm = llm_client
        self.plugin_loader = plugin_loader
        self.plugins = self.plugin_loader.load_plugins()
        
        # Initialize plugins
        for plugin in self.plugins:
            plugin.on_startup()

    async def process_message(self, user_message: str, conversation_history: List[Dict[str, str]]) -> str:
        """
        Main pipeline:
        1. User Input
        2. Plugin.transform_messages() (e.g. Memory)
        3. Plugin.transform_system_prompt()
        4. Plugin.get_tools()
        5. LLM Call
        6. Tool Execution (if needed)
        7. Plugin.post_process_response()
        """
        
        # 1. Prepare Base Context
        messages = [{"role": "user", "content": user_message}]
        full_history = conversation_history + messages

        # 2. Apply Plugin Transforms on Messages (Memory injection, etc.)
        for plugin in self.plugins:
            full_history = plugin.transform_messages(full_history)

        # 3. Apply Plugin Transforms on System Prompt
        system_prompt = "You are Tailor, a helpful AI assistant."
        for plugin in self.plugins:
            system_prompt = plugin.transform_system_prompt(system_prompt)

        # 4. Gather Tools
        tools = []
        for plugin in self.plugins:
            plugin_tools = plugin.get_tools()
            if plugin_tools:
                tools.extend(plugin_tools)

        # 5. LLM Call
        # If no tools, pass None to avoid API errors if provider doesn't support empty tools
        final_tools = tools if tools else None
        
        response_msg = self.llm.generate_response(
            messages=full_history,
            tools=final_tools,
            system_prompt=system_prompt
        )

        final_content = response_msg.content or ""

        # 6. Tool Execution Loop (Simple single-turn for now)
        if response_msg.tool_calls:
            # Append initial helper message
            full_history.append(response_msg)
            
            for tool_call in response_msg.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)
                
                # Find plugin that owns this tool
                tool_result = None
                for plugin in self.plugins:
                    # In a real app, we'd have a map of tool_name -> plugin
                    # Here we just try to execute on all, or query plugin if it has it
                    if any(t['function']['name'] == fn_name for t in plugin.get_tools()):
                        tool_result = plugin.execute_tool(fn_name, fn_args)
                        break
                
                # Append result
                full_history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": fn_name,
                    "content": str(tool_result)
                })

            # Follow-up LLM Call
            response_msg_2 = self.llm.generate_response(
                messages=full_history,
                tools=final_tools, 
                system_prompt=system_prompt
            )
            final_content = response_msg_2.content

        # 7. Post-process Response
        for plugin in self.plugins:
            final_content = plugin.post_process_response(final_content)

        return final_content
