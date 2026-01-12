from typing import Dict, Any, List, Optional
import asyncio
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from .types import PipelineContext
from .events import PipelineEvents
from .manager import PipelineManager

# We need a way to pass the manager/config to the nodes.
# In LangGraph, nodes are usually pure functions of State.
# But we need access to the `manager` to emit events and `config` for LLM settings.
# A common pattern is to make the nodes methods of a class or use partials/closures.
# Here we will define a NodeFactory or similar helper.

class PipelineNodes:
    """
    Standard Nodes for the Pipeline Graph.
    """
    def __init__(self, manager: PipelineManager, llm_client: Any = None):
        self.manager = manager
        self.llm_client = llm_client
        self._logger = logger.bind(component="PipelineNodes")

    async def input_node(self, state: PipelineContext) -> Dict[str, Any]:
        """Node for Input Phase."""
        self._logger.debug("Executing Input Node")
        await self.manager.emit(PipelineEvents.START, state)
        await self.manager.emit(PipelineEvents.INPUT, state)
        # Return dict of changes for LangGraph (or the whole object if using PydanticState behavior)
        return state.model_dump()

    async def context_node(self, state: PipelineContext) -> Dict[str, Any]:
        """Node for Context Phase (RAG)."""
        if state.should_abort: return {}
        self._logger.debug("Executing Context Node")
        await self.manager.emit(PipelineEvents.CONTEXT, state)
        return {"metadata": state.metadata, "events_emitted": state.events_emitted}

    async def prompt_node(self, state: PipelineContext) -> Dict[str, Any]:
        """Node for Prompt Assembly."""
        if state.should_abort: return {}
        
        # Default Logic: Build System Prompt from Metadata
        rag = state.metadata.get("rag_context", [])
        system_prompt = state.metadata.get("system_prompt", "You are a helpful assistant.")
        if rag:
            context_str = "\n\n".join(rag[:5])
            system_prompt += f"\n\nContext:\n{context_str}"
        state.metadata["final_system_prompt"] = system_prompt
        
        await self.manager.emit(PipelineEvents.PROMPT, state)
        return state.model_dump()

    async def llm_node(self, state: PipelineContext) -> Dict[str, Any]:
        """Node for LLM Execution."""
        if state.should_abort: return {}
        self._logger.debug("Executing LLM Node")
        
        # 1. Emit LLM Event (Plugins could override response here)
        await self.manager.emit(PipelineEvents.LLM, state)
        
        if state.response:
            return state.model_dump()

        # 2. Default LLM Call
        if not self.llm_client:
             response = self._get_placeholder_response(state)
        else:
            try:
                system_prompt = state.metadata.get("final_system_prompt", "")
                messages = [SystemMessage(content=system_prompt)]
                for msg in state.history:
                    if msg.get("role") == "user":
                        messages.append(HumanMessage(content=msg.get("content", "")))
                    elif msg.get("role") == "assistant":
                        messages.append(AIMessage(content=msg.get("content", "")))
                messages.append(HumanMessage(content=state.message))
                
                result = await self.llm_client.ainvoke(messages)
                response = result.content
            except Exception as e:
                self._logger.error(f"LLM Error: {e}")
                response = self._get_placeholder_response(state)

        state.response = response
        return state.model_dump()

    async def post_process_node(self, state: PipelineContext) -> Dict[str, Any]:
        """Node for Post Processing."""
        if state.should_abort: return {}
        self._logger.debug("Executing Post Process Node")
        await self.manager.emit(PipelineEvents.POST_PROCESS, state)
        return state.model_dump()
        
    async def output_node(self, state: PipelineContext) -> Dict[str, Any]:
         """Node for Output Formatting."""
         self._logger.debug("Executing Output Node")
         await self.manager.emit(PipelineEvents.OUTPUT, state)
         await self.manager.emit(PipelineEvents.END, state)
         return state.model_dump()

    def _get_placeholder_response(self, state: PipelineContext) -> str:
        return f"[Demo Mode] Echo: {state.message}"
