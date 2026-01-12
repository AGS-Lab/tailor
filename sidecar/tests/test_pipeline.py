"""
Tests for Sidecar Pipeline (New Architecture).
Covers:
- Types (Pydantic)
- Manager (Events)
- Nodes (Graph Steps)
- DefaultPipeline (LangGraph Integration)
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from sidecar.pipeline import (
    PipelineManager, 
    DefaultPipeline, 
    PipelineConfig, 
    PipelineContext, 
    PipelineEvents
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
    assert cfg.model == "gpt-4"
    assert cfg.temperature == 0.7
    assert cfg.is_graph_mode is False

# =============================================================================
# Test PipelineManager (Event System)
# =============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
class TestPipelineManager:
    
    async def test_subscribe_and_emit(self):
        manager = PipelineManager()
        mock_handler = AsyncMock()
        
        manager.subscribe(PipelineEvents.INPUT, mock_handler)
        
        ctx = PipelineContext(message="test", original_message="test")
        await manager.emit(PipelineEvents.INPUT, ctx)
        
        mock_handler.assert_called_once_with(ctx)
        assert PipelineEvents.INPUT in ctx.events_emitted

    async def test_emit_aborts_if_flag_set(self):
        manager = PipelineManager()
        mock_handler = AsyncMock()
        
        manager.subscribe(PipelineEvents.INPUT, mock_handler)
        
        ctx = PipelineContext(message="test", original_message="test")
        ctx.should_abort = True
        
        await manager.emit(PipelineEvents.INPUT, ctx)
        
        # Should NOT call handler if already aborted
        mock_handler.assert_not_called()

    async def test_handler_aborts_flow(self):
        """Test that a handler can abort the pipeline."""
        manager = PipelineManager()
        
        async def aborting_handler(ctx):
            ctx.abort("Stop here")
            
        mock_Handler2 = AsyncMock()
        
        manager.subscribe(PipelineEvents.INPUT, aborting_handler)
        manager.subscribe(PipelineEvents.INPUT, mock_Handler2)
        
        ctx = PipelineContext(message="test", original_message="test")
        await manager.emit(PipelineEvents.INPUT, ctx)
        
        assert ctx.should_abort is True
        assert ctx.abort_reason == "Stop here"
        # Since logic is sequential per event, handler2 should NOT be called if handler1 aborted?
        # Let's check logic. PipelineManager.emit loops sequentially.
        # "if ctx.should_abort: return" is inside the loop? 
        # Actually in manager.py: 
        #    await handler(ctx)
        #    if ctx.should_abort: ... return
        # So yes, subsequent handlers for SAME event are skipped.
        mock_Handler2.assert_not_called()

# =============================================================================
# Test Pipeline Nodes (Isolating Step Logic)
# =============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
class TestPipelineNodes:
    
    @pytest.fixture
    def manager(self):
        return PipelineManager()
        
    @pytest.fixture
    def nodes(self, manager):
        return PipelineNodes(manager)

    async def test_input_node_emits_events(self, nodes, manager):
        mock_emit = AsyncMock()
        manager.emit = mock_emit
        
        ctx = PipelineContext(message="hi", original_message="hi")
        result = await nodes.input_node(ctx)
        
        # Should emit START and INPUT
        assert mock_emit.call_count == 2
        
        # Should return events_emitted for LangGraph persistence
        assert "events_emitted" in result

    async def test_llm_node_offline(self, nodes):
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
    
    async def test_full_run_success(self):
        manager = PipelineManager()
        config = PipelineConfig()
        pipeline = DefaultPipeline(manager, config)
        
        # Hook into input
        async def modify_input(ctx):
            ctx.metadata["visited_input"] = True
            
        manager.subscribe(PipelineEvents.INPUT, modify_input)
        
        result_ctx = await pipeline.run("Test Message")
        
        assert result_ctx.response is not None
        assert result_ctx.metadata.get("visited_input") is True
        assert PipelineEvents.END in result_ctx.events_emitted

    async def test_pipeline_abort_stops_execution(self):
        manager = PipelineManager()
        config = PipelineConfig()
        pipeline = DefaultPipeline(manager, config)
        
        # Abort at INPUT
        async def abort_hook(ctx):
            ctx.abort("Security Violation")
            
        manager.subscribe(PipelineEvents.INPUT, abort_hook)
        
        # We need to verify that subsequent nodes (like LLM) didn't run.
        # But Nodes check `if state.should_abort: return {}`.
        # So the graph finishes but with no response.
        
        result_ctx = await pipeline.run("Bad Message")
        
        assert result_ctx.should_abort is True
        assert result_ctx.abort_reason == "Security Violation"
        # Response should be None (or potentially error string if graph handled it)
        # But since LLM node returns early, ctx.response stays None.
        assert result_ctx.response is None
