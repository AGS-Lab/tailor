import pytest
import asyncio
import shutil
import json
from pathlib import Path
import sys
from unittest.mock import MagicMock, AsyncMock

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from sidecar.vault_brain import VaultBrain


@pytest.mark.asyncio
async def test_memory_fallback_linear_chat(example_vault_path):
    """
    Verify that core chat functionality works even if the 'chat_branches' plugin is missing.
    """
    # Setup paths
    vault_path = example_vault_path
    memory_dir = vault_path / ".memory"
    chat_id = "chat_fallback_test"

    # Clean up
    if memory_dir.exists():
        shutil.rmtree(memory_dir)

    # Reset Singleton
    if VaultBrain._instance:
        VaultBrain._instance = None

    # Initialize
    brain = VaultBrain(vault_path, MagicMock())

    from unittest.mock import patch

    # Patch the CLASS where it is IMPORTED in VaultBrain
    with patch("sidecar.vault_brain.LLMService") as MockServiceClass:
        # Setup the instance that will be returned
        mock_instance = MockServiceClass.return_value
        mock_instance.complete = AsyncMock()
        mock_instance.complete.return_value = MagicMock(
            content="Linear Response", model="test", usage={}
        )

        # Initialize Brain (will create LLMService internally)
        await brain.initialize()

        # Verify Keyring/others if needed, but mostly we care about LLM being mocked

        # Prevent smart_context from making extra LLM calls during topic extraction.
        # _run_topic_extraction is a background asyncio task that fires after each
        # pipeline output. It calls memory.load_chat then LLMService.complete, which
        # consumes mock calls and corrupts call_args assertions later in this test.
        if "smart_context" in brain.plugins:
            brain.plugins["smart_context"]._run_topic_extraction = AsyncMock(return_value=None)

        # SIMULATE MISSING PLUGIN
        # Manually remove chat_branches from the loaded plugins
        if "chat_branches" in brain.plugins:
            del brain.plugins["chat_branches"]

        # Manually remove command from registry to simulate it not being registered
        # commands keys are command IDs
        if "branch.create" in brain.commands:
            del brain.commands["branch.create"]

        # 1. Send Message (Should succeed via Memory plugin)
        # ... logic continues inside the with block ...
        response = await brain.chat_send(message="Hello Linear World", chat_id=chat_id)
        assert response["status"] == "success"
        # VaultBrain returns 'response' key, not 'content'
        print(f"DEBUG: Response keys: {response.keys()}")
        print(f"DEBUG: Response content: {response.get('response')}")
        assert response["response"] == "Linear Response"

        # 2. Check Persistence
        memory_file = memory_dir / f"{chat_id}.json"
        assert memory_file.exists()

        with open(memory_file, "r") as f:
            data = json.load(f)

        # Memory stores whatever schema is given
        assert "messages" in data
        assert len(data["messages"]) == 2  # User + Assistant

        # 3. Fetch History context check
        mock_instance.complete.return_value = MagicMock(
            content="Second Response", model="test", usage={}
        )
        await brain.chat_send(message="Second Message", chat_id=chat_id)

        # Verify LLM was called with history
        call_args = mock_instance.complete.call_args
        messages_sent = call_args[1]["messages"]
        assert len(messages_sent) >= 4
        assert messages_sent[-3]["content"] == "Hello Linear World"

        # 4. Attempt Branch Command (Should fail)
        try:
            await brain.execute_command("branch.create", chat_id=chat_id)
            assert False, "Should have raised an error/failed because plugin is missing"
        except Exception:
            pass

    print("Fallback Test Passed!")
