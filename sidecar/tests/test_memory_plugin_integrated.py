import pytest
import asyncio
import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from sidecar.vault_brain import VaultBrain
from sidecar.services.llm_service import LLMService

@pytest.mark.asyncio
async def test_memory_plugin_integrated():
    # Setup paths
    vault_path = Path("/home/arc/Dev/tailor/example-vault")
    memory_dir = vault_path / ".memory"
    memory_file = memory_dir / "chat_default.json"
    
    # Clean up previous memory
    if memory_dir.exists():
        shutil.rmtree(memory_dir)
        
    # Initialize Brain
    # Force singleton reset if needed (though pytest runs usually isolate or we can patch)
    if VaultBrain._instance:
        VaultBrain._instance = None
    
    # Mock WebSocket
    ws_mock = MagicMock()
    brain = VaultBrain(vault_path, ws_mock)
    
    # Mock LLM Service to capture prompts and return specific responses
    mock_llm = MagicMock(spec=LLMService)
    mock_llm.complete = AsyncMock()
    
    # First response (simple ack)
    # Second response (answer)
    mock_llm.complete.side_effect = [
        MagicMock(content="Hello AutoTest", model="test-model", usage={}),
        MagicMock(content="Your name is AutoTest", model="test-model", usage={})
    ]
    
    # Start Brain (loads plugins)
    await brain.initialize()
    
    # Inject mock LLM AFTER initialization (overwriting real service)
    brain._llm_service = mock_llm
    
    # Update global singleton so Pipeline picks it up
    import sidecar.services.llm_service as llm_module
    llm_module._llm_service = mock_llm
    
    # Verify plugin loaded
    assert "memory" in brain.plugins
    assert brain.plugins["memory"].is_loaded
    
    # 1. Send first message (Memory should store this)
    # Provide chat_id to ensure we use chat_default.json
    response1 = await brain.chat_send(message="My name is AutoTest", chat_id="chat_default")
    assert response1["status"] == "success"
    assert response1["response"] == "Hello AutoTest"
    
    # Verify memory file created
    assert memory_file.exists()
    with open(memory_file, "r") as f:
        memories = json.load(f)
    # Expect 2 messages: User + Assistant
    assert len(memories) == 2
    assert memories[0]["role"] == "user"
    assert memories[0]["content"] == "My name is AutoTest"
    assert "time_marker" in memories[0]
    assert memories[1]["role"] == "assistant"
    assert memories[1]["content"] == "Hello AutoTest"
    assert "time_marker" in memories[1]
    
    # 2. Send second message (Memory should inject context)
    response2 = await brain.chat_send(message="What is my name?", chat_id="chat_default")
    assert response2["response"] == "Your name is AutoTest"
    
    # Verify LLM call arguments to check for injected context
    # Get the LAST call arguments
    call_args = mock_llm.complete.call_args
    # messages is the first arg (or keyword 'messages')
    messages = call_args.kwargs.get("messages")
    system_prompt = messages[0]["content"]
    
    # Check if memory context is present in system prompt
    # User Request: "Just store", so we expect NO injection
    assert "Long-term Memory:" not in system_prompt
    assert "- User: My name is AutoTest" not in system_prompt
    
    # Cleanup
    await brain.shutdown()
    if memory_dir.exists():
        shutil.rmtree(memory_dir)
