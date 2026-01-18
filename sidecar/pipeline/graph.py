import os
from typing import List, Dict, Any, Optional

from loguru import logger
from langgraph.graph import StateGraph, END

try:
    from langchain_openai import ChatOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from .types import PipelineConfig, PipelineContext
from .nodes import PipelineNodes

class Pipeline:
    """
    Unified Pipeline Executor.
    
    If `config.graph_config` is present, it constructs a custom graph.
    Otherwise, it defaults to the robust linear flow (DefaultPipeline behavior).
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self._logger = logger.bind(component="Pipeline")
        
        self._llm: Optional[Any] = None
        self._init_llm()
        
        # Initialize Nodes
        self.nodes = PipelineNodes(self._llm)
        
        # Build Graph (Default or Custom)
        self.graph = self._build_graph()

    def _init_llm(self):
        """Initialize LLM client."""
        # TODO: Move to a unified LLM factory with LiteLLM later
        if not OPENAI_AVAILABLE:
            self._logger.warning("OpenAI not available.")
            return

        api_key = self.config.api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            return

        try:
            self._llm = ChatOpenAI(
                model=self.config.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                api_key=api_key,
                request_timeout=self.config.timeout
            )
        except Exception as e:
            self._logger.error(f"Failed to init OpenAI: {e}")

    def _build_graph(self):
        """Construct the execution graph."""
        if self.config.graph_config:
            return self._build_custom_graph(self.config.graph_config)
        else:
            return self._build_default_graph()

    def _build_default_graph(self):
        """Construct the default linear StateGraph."""
        self._logger.info("Building default linear pipeline")
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
        workflow.add_edge("output", END)

        return workflow.compile()

    def _build_custom_graph(self, graph_config: Dict[str, Any]):
        """
        Construct a custom graph from configuration.
        TODO: Implement full JSON-to-Graph loader.
        """
        self._logger.warning("Custom graph loading not full implemented. Falling back to default.")
        return self._build_default_graph()

    async def run(self, message: str, history: List[Dict[str, str]] = None) -> PipelineContext:
        """
        Execute the pipeline flow via LangGraph.
        """
        # Initialize State
        initial_state = PipelineContext(
            message=message,
            original_message=message,
            history=history or []
        )
        
        try:
            self._logger.debug("Invoking Pipeline Graph...")
            
            # LangGraph invoke returns the final state
            final_state = await self.graph.ainvoke(initial_state)
            
            # If final_state is a dict (sometimes happens depending on LangGraph version/config), convert back
            if isinstance(final_state, dict):
                return PipelineContext(**final_state)
            
            return final_state
            
        except Exception as e:
            self._logger.error(f"Pipeline Execution Error: {e}", exc_info=True)
            # Return state with error
            initial_state.response = f"Error: {str(e)}"
            return initial_state
