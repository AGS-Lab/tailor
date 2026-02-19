from typing import Dict, Any
from loguru import logger

from .types import PipelineContext
from .events import PipelineEvents


class PipelineNodes:
    """
    Standard Nodes for the Pipeline Graph.
    """

    def __init__(self, llm_client: Any = None):
        self.llm_client = llm_client
        self._logger = logger.bind(component="PipelineNodes")

    @property
    def brain(self):
        from ..vault_brain import VaultBrain

        return VaultBrain.get()

    async def input_node(self, state: PipelineContext) -> Dict[str, Any]:
        """Node for Input Phase."""
        self._logger.debug("Executing Input Node")
        await self.brain.publish(PipelineEvents.START, sequential=True, ctx=state)
        await self.brain.publish(PipelineEvents.INPUT, sequential=True, ctx=state)
        # Return dict of changes for LangGraph (or the whole object if using PydanticState behavior)
        return state.model_dump()

    async def context_node(self, state: PipelineContext) -> Dict[str, Any]:
        """Node for Context Phase (RAG)."""
        if state.should_abort:
            return {}
        self._logger.debug("Executing Context Node")
        await self.brain.publish(PipelineEvents.CONTEXT, sequential=True, ctx=state)
        return {"metadata": state.metadata, "events_emitted": state.events_emitted}

    async def prompt_node(self, state: PipelineContext) -> Dict[str, Any]:
        """Node for Prompt Assembly."""
        if state.should_abort:
            return {}

        # Default Logic: Build System Prompt from Metadata
        rag = state.metadata.get("rag_context", [])
        system_prompt = state.metadata.get(
            "system_prompt", "You are a helpful assistant."
        )
        if rag:
            context_str = "\n\n".join(rag[:5])
            system_prompt += f"\n\nContext:\n{context_str}"
        state.metadata["final_system_prompt"] = system_prompt

        await self.brain.publish(PipelineEvents.PROMPT, sequential=True, ctx=state)
        return state.model_dump()

    async def llm_node(self, state: PipelineContext) -> Dict[str, Any]:
        """Node for LLM Execution."""
        if state.should_abort:
            return {}
        self._logger.debug("Executing LLM Node")

        # 1. Emit LLM Event (Plugins could override response here)
        await self.brain.publish(PipelineEvents.LLM, sequential=True, ctx=state)

        if state.response:
            return state.model_dump()

        # 2. Default LLM Call using LLMService
        if not self.llm_client or not hasattr(self.llm_client, "llm_service"):
            response = self._get_placeholder_response(state)
        else:
            try:
                # Build messages for LLMService
                system_prompt = state.metadata.get(
                    "final_system_prompt", "You are a helpful assistant."
                )
                messages = [{"role": "system", "content": system_prompt}]

                for msg in state.history:
                    messages.append(
                        {
                            "role": msg.get("role", "user"),
                            "content": msg.get("content", ""),
                        }
                    )

                messages.append({"role": "user", "content": state.message})

                # Get category from metadata or default to "fast"
                category = state.metadata.get("category", "fast")

                # Use LLMService via pipeline
                llm_response = await self.llm_client.complete(
                    messages=messages,
                    category=category,
                    stream=False,  # Non-streaming for graph mode
                )
                response = llm_response.content
            except Exception as e:
                self._logger.error(f"LLM Error: {e}")
                response = f"[Error] {str(e)}"

        state.response = response
        return state.model_dump()

    async def post_process_node(self, state: PipelineContext) -> Dict[str, Any]:
        """Node for Post Processing."""
        if state.should_abort:
            return {}
        self._logger.debug("Executing Post Process Node")
        await self.brain.publish(
            PipelineEvents.POST_PROCESS, sequential=True, ctx=state
        )
        return state.model_dump()

    async def output_node(self, state: PipelineContext) -> Dict[str, Any]:
        """Node for Output Formatting."""
        self._logger.debug("Executing Output Node")
        await self.brain.publish(PipelineEvents.OUTPUT, sequential=True, ctx=state)
        await self.brain.publish(PipelineEvents.END, sequential=True, ctx=state)
        return state.model_dump()

    def _get_placeholder_response(self, state: PipelineContext) -> str:
        return f"[Demo Mode] Echo: {state.message}"
