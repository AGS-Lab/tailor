"""
Tests for LLM Service.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from sidecar.services.llm_service import LLMService


@pytest.fixture
def mock_keyring():
    with patch("sidecar.services.llm_service.get_keyring_service") as mock:
        service = MagicMock()
        service.list_configured_providers.return_value = ["openai", "anthropic"]
        service.get_api_key.return_value = "sk-test"
        mock.return_value = service
        yield service


@pytest.fixture
def llm_service(tmp_path, mock_keyring):
    config = {
        "categories": {"fast": "openai/gpt-4o-mini"},
        "defaults": {"temperature": 0.7},
    }
    # Mock registry load
    with patch.object(
        LLMService, "_load_registry", return_value={"categories": {}, "recommended": {}}
    ):
        service = LLMService(tmp_path, config)
        return service


@pytest.mark.asyncio
async def test_initialization(llm_service):
    assert llm_service.config["defaults"]["temperature"] == 0.7
    assert llm_service._keyring.set_env_vars.called


@pytest.mark.asyncio
async def test_get_available_models(llm_service):
    # Mock LiteLLM cost data
    mock_cost = {
        "gpt-4o-mini": {"max_tokens": 128000},
        "claude-3-5-sonnet-20241022": {"max_tokens": 200000},
    }

    with patch("sidecar.services.llm_service.litellm.model_cost", mock_cost):
        # We also need to mock _registry to have some recommended models
        llm_service._registry = {
            "categories": {
                "fast": {"recommended": ["openai/gpt-4o-mini"]},
                "thinking": {"recommended": ["anthropic/claude-3-5-sonnet-20241022"]},
            }
        }

        models = await llm_service.get_available_models()

        assert "openai" in models
        assert "anthropic" in models

        gpt4 = next(m for m in models["openai"] if m.id == "gpt-4o-mini")
        assert gpt4.provider == "openai"
        assert "fast" in gpt4.categories


@pytest.mark.asyncio
async def test_complete_sync(llm_service):
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="Hello"), finish_reason="stop")
    ]
    mock_response.usage = MagicMock(
        prompt_tokens=10, completion_tokens=5, total_tokens=15
    )

    with patch(
        "sidecar.services.llm_service.acompletion", return_value=mock_response
    ) as mock_complete:
        response = await llm_service.complete(
            messages=[{"role": "user", "content": "Hi"}], category="fast"
        )

        assert response.content == "Hello"
        assert response.model == "openai/gpt-4o-mini"

        # Verify call args
        args = mock_complete.call_args
        assert args.kwargs["model"] == "openai/gpt-4o-mini"
        assert args.kwargs["temperature"] == 0.7


@pytest.mark.asyncio
async def test_complete_stream(llm_service):
    # Mock async generator for streaming
    async def mock_stream(*args, **kwargs):
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock(delta=MagicMock(content="Hello"))]
        yield chunk1

        chunk2 = MagicMock()
        chunk2.choices = [MagicMock(delta=MagicMock(content=" World"))]
        yield chunk2

    with patch("sidecar.services.llm_service.acompletion", side_effect=mock_stream):
        gen = await llm_service.complete(
            messages=[{"role": "user", "content": "Hi"}], category="fast", stream=True
        )

        chunks = []
        async for chunk in gen:
            chunks.append(chunk)

        assert "".join(chunks) == "Hello World"


@pytest.mark.asyncio
async def test_guardrails_o1(llm_service):
    # Check if o1 models enforce temperature=1
    llm_service.set_category_model("reasoning", "openai/o1-preview")

    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="Thinking..."), finish_reason="stop")
    ]

    with patch(
        "sidecar.services.llm_service.acompletion", return_value=mock_response
    ) as mock_complete:
        await llm_service.complete(
            messages=[{"role": "user", "content": "Solve"}],
            category="reasoning",
            temperature=0.5,  # Should be overridden
        )

        args = mock_complete.call_args
        assert args.kwargs["temperature"] == 1.0
        assert "top_p" not in args.kwargs


@pytest.mark.asyncio
async def test_embed_returns_list_of_vectors():
    with patch("sidecar.services.llm_service.aembedding") as mock_embed:
        mock_embed.return_value = MagicMock(
            data=[
                {"embedding": [0.1, 0.2, 0.3]},
                {"embedding": [0.4, 0.5, 0.6]},
            ]
        )
        service = LLMService(
            Path("/tmp"),
            {"categories": {"embedding": "openai/text-embedding-3-large"}}
        )
        result = await service.embed(["hello", "world"])

    assert len(result) == 2
    assert result[0] == [0.1, 0.2, 0.3]
    assert result[1] == [0.4, 0.5, 0.6]


@pytest.mark.asyncio
async def test_embed_raises_when_no_embedding_model(llm_service):
    with pytest.raises(ValueError, match="No model configured for category: embedding"):
        await llm_service.embed(["hello"])


@pytest.mark.asyncio
async def test_detect_ollama(llm_service):
    # Mock httpx
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "models": [
            {
                "name": "llama3:latest",
                "size": 1000000,
                "modified_at": "2024-01-01",
                "digest": "sha256:123",
            }
        ]
    }

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client_cls.return_value = mock_client

        models = await llm_service.detect_ollama(force_refresh=True)

        assert len(models) == 1
        assert models[0].name == "llama3:latest"
