import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from sidecar.pipeline.default import DefaultPipeline
from sidecar.pipeline.types import PipelineConfig, PipelineContext
from sidecar.services.llm_service import LLMResponse

@pytest.fixture
def mock_llm_service():
    service = AsyncMock()
    service.complete = AsyncMock(return_value=LLMResponse(content="mocked response", model="test-model"))
    return service

@pytest.fixture
def config():
    return PipelineConfig(category="test")

@pytest.fixture
def pipeline(config, mock_llm_service):
    p = DefaultPipeline(config)
    p._llm_service = mock_llm_service
    return p

@pytest.mark.asyncio
async def test_pipeline_run(pipeline, mock_llm_service):
    mock_brain_instance = AsyncMock()
    with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain_instance):
        result = await pipeline.run(message="Hello")
        
        assert isinstance(result, PipelineContext)
        assert result.response == "mocked response"
        mock_llm_service.complete.assert_called_once()
        
@pytest.mark.asyncio
async def test_pipeline_stream_run(pipeline, mock_llm_service):
    # Setup mock stream
    async def mock_stream(*args, **kwargs):
        yield "token1"
        yield "token2"
        
    mock_llm_service.complete = AsyncMock(return_value=mock_stream())
    
    tokens = []
    async for token in pipeline.stream_run(message="Hello"):
        tokens.append(token)
        
    assert tokens == ["token1", "token2"]

@pytest.mark.asyncio
async def test_nodes_abort_handling(pipeline):
    mock_brain_instance = AsyncMock()
    with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain_instance):
        context = PipelineContext(message="test", original_message="test")
        context.should_abort = True
        
        # When aborted, these nodes should return an empty dict to skip updating state
        assert await pipeline.nodes.context_node(context) == {}
        assert await pipeline.nodes.prompt_node(context) == {}
        assert await pipeline.nodes.llm_node(context) == {}
        assert await pipeline.nodes.post_process_node(context) == {}
