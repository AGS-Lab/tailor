"""
Tests for Sidecar Pipeline (New Architecture).
Covers:
- Types (Pydantic)
- Nodes (Graph Steps)
- DefaultPipeline (LangGraph Integration)
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from sidecar.pipeline import (
    DefaultPipeline,
    PipelineConfig,
    PipelineContext,
    PipelineEvents,
)
from sidecar.pipeline.nodes import PipelineNodes

# =============================================================================
# Test Types (Pydantic)
# =============================================================================


@pytest.mark.unit
def test_pipeline_context_validation():
    """Test Pydantic validation for PipelineContext."""
    # 1. Valid Creation
    ctx = PipelineContext(message="hello", original_message="hello")
    assert ctx.message == "hello"
    assert ctx.metadata == {}
    assert ctx.events_emitted == []

    # 2. Metadata Updates
    ctx.add_metadata("key", "value")
    assert ctx.metadata["key"] == "value"

    # 3. Abort Logic
    ctx.abort("stop")
    assert ctx.should_abort is True
    assert ctx.abort_reason == "stop"


@pytest.mark.unit
def test_pipeline_config_defaults():
    """Test PipelineConfig defaults."""
    cfg = PipelineConfig()
    assert cfg.category == "fast"
    assert cfg.temperature == 0.7
    assert cfg.is_graph_mode is False


# =============================================================================
# Test Pipeline Nodes (Isolating Step Logic)
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestPipelineNodes:
    @pytest.fixture
    def mock_brain(self):
        with patch("sidecar.vault_brain.VaultBrain.get") as mock_get:
            mock_brain = MagicMock()
            mock_brain.publish = AsyncMock()
            mock_get.return_value = mock_brain
            yield mock_brain

    @pytest.fixture
    def nodes(self, mock_brain):
        return PipelineNodes(llm_client=None)

    async def test_input_node_emits_events(self, nodes, mock_brain):
        ctx = PipelineContext(message="hi", original_message="hi")
        result = await nodes.input_node(ctx)

        # Should emit START and INPUT
        assert mock_brain.publish.call_count == 2

        # Verify call args
        calls = mock_brain.publish.call_args_list
        assert calls[0].args[0] == PipelineEvents.START
        assert calls[1].args[0] == PipelineEvents.INPUT

        # Should return events_emitted for LangGraph persistence (or at least valid dict)
        assert isinstance(result, dict)

    async def test_llm_node_offline(self, nodes, mock_brain):
        """Test LLM node fallback when no client."""
        ctx = PipelineContext(message="hi", original_message="hi")

        result = await nodes.llm_node(ctx)

        assert "[Demo Mode]" in result["response"]
        assert ctx.response is not None


# =============================================================================
# Test DefaultPipeline (Integration)
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestDefaultPipeline:
    @pytest.fixture
    def mock_brain(self):
        with patch("sidecar.vault_brain.VaultBrain.get") as mock_get:
            mock_brain = MagicMock()
            mock_brain.publish = AsyncMock()
            mock_get.return_value = mock_brain
            yield mock_brain

    async def test_full_run_success(self, mock_brain):
        config = PipelineConfig()
        pipeline = DefaultPipeline(config)

        # We can't easily hook into "INPUT" event via manager anymore since manager is gone.
        # But we can verify that events were published via mock_brain.

        result_ctx = await pipeline.run("Test Message")

        assert result_ctx.response is not None
        # Verify END event was published
        assert mock_brain.publish.called
        # Check for END event
        event_names = [call.args[0] for call in mock_brain.publish.call_args_list]
        assert PipelineEvents.END in event_names

    async def test_pipeline_abort_stops_execution(self, mock_brain):
        config = PipelineConfig()
        pipeline = DefaultPipeline(config)

        # Simulate an aborter hook
        async def mock_publish(event, sequential=False, ctx=None, **kwargs):
            if event == PipelineEvents.INPUT and ctx:
                ctx.abort("Security Violation")

        mock_brain.publish.side_effect = mock_publish

        result_ctx = await pipeline.run("Bad Message")

        assert result_ctx.should_abort is True
        assert result_ctx.abort_reason == "Security Violation"
        # Since logic aborts, LLM node calls mock_publish(LLM) ?
        # Actually PipelineNodes checks `if state.should_abort: return {}` at start of nodes.
        # So subsequent nodes should NOT publish events like PROMPT or LLM.

        event_names = [call.args[0] for call in mock_brain.publish.call_args_list]
        assert PipelineEvents.INPUT in event_names
        # LLM event should NOT be present
        assert PipelineEvents.LLM not in event_names
