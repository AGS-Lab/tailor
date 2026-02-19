from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict
import datetime


class PipelineConfig(BaseModel):
    """Configuration for the LLM pipeline."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Category-based model selection (replaces direct model specification)
    category: str = Field(default="fast", description="Model category to use")

    # Generation parameters
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: float = 30.0

    # Streaming is now default
    stream: bool = True

    # Graph specific settings
    is_graph_mode: bool = False
    graph_config: Optional[Dict[str, Any]] = None


class PipelineContext(BaseModel):
    """
    Context passed through the pipeline.
    Represents the State of the LangGraph.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Input
    message: str
    original_message: str

    # State (Mutable by plugins)
    history: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Output
    response: Optional[str] = None

    # Flow Control
    should_abort: bool = False
    abort_reason: Optional[str] = None

    # Telemetry
    events_emitted: List[str] = Field(default_factory=list)
    start_time: float = Field(
        default_factory=lambda: datetime.datetime.now().timestamp()
    )

    def add_metadata(self, key: str, value: Any) -> None:
        self.metadata[key] = value

    def abort(self, reason: str) -> None:
        self.should_abort = True
        self.abort_reason = reason
