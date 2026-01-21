"""
Default Pipeline - LiteLLM Integration

The linear, out-of-the-box pipeline flow using LiteLLM for model agnostic LLM access.
"""
import os
from typing import Optional, List, Dict, Any, AsyncGenerator

from loguru import logger
from langgraph.graph import StateGraph, END

from .types import PipelineConfig, PipelineContext
from .nodes import PipelineNodes

from ..services.llm_service import LLMService, get_llm_service, LLMResponse


class DefaultPipeline:
    """
    The linear, out-of-the-box pipeline flow.
    Implemented as a pre-configured LangGraph StateGraph.
    Steps: Input -> Context -> Prompt -> LLM -> PostProcess -> Output
    
    Now uses LLMService with LiteLLM for provider-agnostic model access.
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self._logger = logger.bind(component="DefaultPipeline")
        
        # LLM Service reference (lazy loaded from singleton)
        self._llm_service: Optional[LLMService] = None
        
        # Initialize Graph
        self.nodes = PipelineNodes(self)  # Pass pipeline as LLM interface
        self.graph = self._build_graph()

    @property
    def llm_service(self) -> Optional[LLMService]:
        """Lazy-load LLMService singleton."""
        if self._llm_service is None:
            try:
                self._llm_service = get_llm_service()
            except RuntimeError:
                self._logger.debug("LLMService not yet initialized")
        return self._llm_service

    def _build_graph(self):
        """Construct the linear StateGraph."""
        workflow = StateGraph(PipelineContext)

        # Add Nodes
        workflow.add_node("input", self.nodes.input_node)
        workflow.add_node("context", self.nodes.context_node)
        workflow.add_node("prompt", self.nodes.prompt_node)
        workflow.add_node("llm", self.nodes.llm_node)
        workflow.add_node("post_process", self.nodes.post_process_node)
        workflow.add_node("output", self.nodes.output_node)

        # Add Linear Edges
        workflow.set_entry_point("input")
        workflow.add_edge("input", "context")
        workflow.add_edge("context", "prompt")
        workflow.add_edge("prompt", "llm")
        workflow.add_edge("llm", "post_process")
        workflow.add_edge("post_process", "output")
        workflow.set_finish_point("output")

        # Compile
        return workflow.compile()

    async def complete(
        self, 
        messages: List[Dict[str, str]], 
        category: str = "fast",
        stream: bool = False,
        **kwargs
    ) -> Any:
        """
        Generate a completion using LLMService.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            category: Model category to use
            stream: If True, return async generator
            **kwargs: Additional parameters
            
        Returns:
            LLMResponse or AsyncGenerator if streaming
        """
        if not self.llm_service:
            self._logger.warning("LLMService not available")
            return LLMResponse(content="[Error] LLM service not initialized", model="none")
        
        return await self.llm_service.complete(
            messages=messages,
            category=category,
            stream=stream,
            **kwargs
        )

    async def run(
        self, 
        message: str, 
        history: List[Dict[str, str]] = None,
        stream: bool = False,
        metadata: Dict[str, Any] = None
    ) -> PipelineContext:
        """
        Execute the pipeline flow via LangGraph.
        
        Args:
            message: User message
            history: Conversation history
            stream: If True, enable streaming mode (stored in metadata)
            metadata: Additional metadata (e.g. chat_id)
            
        Returns:
            PipelineContext with response
        """
        # Initialize State
        initial_state = PipelineContext(
            message=message,
            original_message=message,
            history=history or []
        )
        
        # Store metadata
        if metadata:
            initial_state.metadata.update(metadata)
        
        # Store streaming preference in metadata
        initial_state.metadata["stream"] = stream
        initial_state.metadata["category"] = self.config.category
        
        try:
            self._logger.debug("Invoking LangGraph...")
            # LangGraph invoke returns the final state
            final_state = await self.graph.ainvoke(initial_state)
            
            # If final_state is a dict, convert back to PipelineContext
            if isinstance(final_state, dict):
                return PipelineContext(**final_state)
            
            return final_state
            
        except Exception as e:
            self._logger.error(f"Graph Execution Error: {e}", exc_info=True)
            # Return state with error
            initial_state.response = f"Error: {str(e)}"
            return initial_state
    
    async def stream_run(
        self,
        message: str,
        history: List[Dict[str, str]] = None,
        metadata: Dict[str, Any] = None
    ) -> AsyncGenerator[str, None]:
        """
        Execute the pipeline with streaming response.
        
        Yields tokens as they arrive from the LLM.
        """
        if not self.llm_service:
            yield "[Error] LLM service not initialized"
            return
        
        # Build messages list
        messages = []
        
        # Resolve System Prompt
        meta = metadata or {}
        system_prompt = meta.get("system_prompt", "You are a helpful assistant.")
        
        # Add RAG context if present
        rag = meta.get("rag_context", [])
        if rag:
            context_str = "\n\n".join(rag[:5])
            system_prompt += f"\n\nContext:\n{context_str}"
            
        messages.append({"role": "system", "content": system_prompt})
        
        for msg in (history or []):
            messages.append(msg)
        
        messages.append({"role": "user", "content": message})
        
        try:
            async for token in await self.llm_service.complete(
                messages=messages,
                category=self.config.category,
                stream=True
            ):
                yield token
        except Exception as e:
            self._logger.error(f"Stream error: {e}")
            yield f"[Error] {str(e)}"
