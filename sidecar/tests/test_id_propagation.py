import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

from sidecar.vault_brain import VaultBrain
from sidecar.services.llm_service import LLMService
from sidecar import constants
from sidecar.pipeline.events import PipelineEvents
from sidecar.pipeline.default import DefaultPipeline


@pytest.fixture(autouse=True)
def reset_singleton():
    VaultBrain._instance = None
    yield
    VaultBrain._instance = None


@pytest.mark.asyncio
async def test_id_propagation():
    # Setup
    if VaultBrain._instance is None:
        brain = VaultBrain(MagicMock(), MagicMock())
        # Prevent partial init issues
        brain._initialized = True
        brain.events.clear_subscribers(PipelineEvents.OUTPUT)
    else:
        brain = VaultBrain.get()

    # We need to ensure brain has the memory plugin loaded
    # Ideally we'd mock the whole plugin loading, but we can just mock the self.plugins dict

    mock_memory = MagicMock()
    mock_memory.get_chat_history = AsyncMock(
        return_value={"status": "success", "history": []}
    )

    brain.plugins["memory"] = mock_memory

    # Mock LLMService to return a predictable response
    mock_llm = MagicMock(spec=LLMService)
    mock_llm.complete = AsyncMock(
        return_value=MagicMock(content="Test Response", model="test", usage={})
    )

    brain._llm_service = mock_llm

    # Instantiate real pipeline to ensure events are emitted
    brain.pipeline = DefaultPipeline(brain)
    # Inject mock LLM into pipeline
    brain.pipeline._llm_service = mock_llm

    # WORKAROUND: DefaultPipeline expects llm_client to have 'complete', but VaultBrain doesn't.
    # In integration it might work via __getattr__ or similar, but here we must mock it.
    brain.complete = mock_llm.complete
    # Also add category and llm_service to satisfy potential accesses
    brain.category = "fast"
    brain.llm_service = mock_llm

    # Also need to patch Pipeline execution to ensure OUTPUT event is published triggers our Logic?
    # Actually, we need integration test behavior here.
    # The DefaultPipeline emits OUTPUT. The Memory plugin listens to OUTPUT.
    # We need real event bus behavior.

    # Let's mock the 'save_interaction' method of memory plugin to simulate what the real one does
    # (setting metadata), since loading the real plugin involves filesystem I/O we might want to avoid or assume works.
    # BUT, the real test is seeing if VaultBrain passes it back.

    async def mock_save_interaction(ctx):
        ctx.metadata["generated_ids"] = {
            "user_message_id": "uuid-user-123",
            "assistant_message_id": "uuid-assist-123",
        }

    brain.subscribe(PipelineEvents.OUTPUT, mock_save_interaction)

    # TEST 1: Non-Streaming
    res = await brain.chat_send(message="Hello", chat_id="test_chat", stream=False)

    assert res["status"] == "success"
    assert "message_ids" in res
    assert res["message_ids"]["user_message_id"] == "uuid-user-123"
    assert res["message_ids"]["assistant_message_id"] == "uuid-assist-123"

    # TEST 2: Streaming
    # We need to mock emit_to_frontend
    brain.emit_to_frontend = MagicMock()
    brain.pipeline.stream_run = (
        AsyncMock()
    )  # Mock stream_run to yield nothing but allow flow

    async def mock_stream_run(**kwargs):
        yield "Test Token"

    brain.pipeline.stream_run = mock_stream_run

    res = await brain.chat_send(
        message="Hello Stream", chat_id="test_chat", stream=True
    )

    # Check if CHAT_STREAM_END event was emitted with message_ids
    calls = brain.emit_to_frontend.call_args_list
    stream_end_call = None
    for call in calls:
        if call[0][0] == constants.EventType.CHAT_STREAM_END:
            stream_end_call = call
            break

    assert stream_end_call is not None
    data = stream_end_call[0][1]
    assert "message_ids" in data
    assert data["message_ids"]["user_message_id"] == "uuid-user-123"
    assert data["message_ids"]["assistant_message_id"] == "uuid-assist-123"

    # TEST 3: Metadata generation (chat_id)
    # Call without chat_id, expect one returned
    res = await brain.chat_send(message="New Chat", stream=False)
    assert res["status"] == "success"
    assert "chat_id" in res
    assert res["chat_id"].startswith("chat_")


if __name__ == "__main__":
    asyncio.run(test_id_propagation())
    print("Test passed!")
