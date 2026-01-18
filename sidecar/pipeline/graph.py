from typing import List, Dict, Any, Optional
from loguru import logger

from .types import PipelineConfig, PipelineContext
from .default import DefaultPipeline

class GraphPipeline:
    """
    Power User Pipeline based on LangGraph.
    Executes a configurable graph of Commands.
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self._logger = logger.bind(component="GraphPipeline")
        
        # In the future, this would load the graph definition
        # self.graph = load_graph(config.graph_config)

    async def run(self, message: str, history: List[Dict[str, str]] = None) -> PipelineContext:
        """
        Execute the graph pipeline.
        """
        self._logger.info("Executing Graph Pipeline")
        
        # TODO: Implement actual Graph traversal / LangGraph execution.
        # For MVP, we might fallback to DefaultPipeline logic or a hardcoded simple graph.
        
        # For now, let's just warn and run the default flow as a fallback
        # so things don't break if someone accidentally toggles this mode.
        self._logger.warning("Graph execution not fully implemented. Falling back to linear flow.")
        
        fallback = DefaultPipeline(self.config)
        return await fallback.run(message, history)
