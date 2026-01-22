import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from sidecar.vault_brain import VaultBrain

async def test_plugin_chat_branches():
    """Test Chat Branches plugin with inline branch annotations."""
    
    # Setup test brain
    example_vault = Path(__file__).parent.parent.parent / "example-vault"
    brain = VaultBrain(example_vault, MagicMock())
    
    # Mock LLM
    with patch("sidecar.services.llm_service.LLMService") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.complete.return_value = MagicMock(content="Response", model="test", usage={})
        
        brain.llm = mock_instance
        
        # Initialize
        await brain.initialize()
        
        # Test chat ID
        chat_id = "chat_branch_plugin_test"
        memory_dir = example_vault / ".memory"
        memory_file = memory_dir / f"{chat_id}.json"
        
        # Clean up if exists
        if memory_file.exists():
            memory_file.unlink()
        
        # 1. Send initial message
        await brain.chat_send(message="Hello", chat_id=chat_id)
        
        # Verify messages stored
        assert memory_file.exists()
        with open(memory_file, "r") as f:
            data = json.load(f)
        assert "messages" in data
        assert len(data["messages"]) == 2
        msg_id = data["messages"][0]["id"]
        
        # 2. Create branch
        result = await brain.execute_command("branch.create", 
            chat_id=chat_id, 
            message_id=msg_id,
            name="test_branch"
        )
        assert result["status"] == "success"
        assert result["branch"] == "test_branch"
        
        # 3. Send message on branch
        mock_instance.complete.return_value = MagicMock(content="Branch Response", model="test", usage={})
        await brain.chat_send(message="Branch Message", chat_id=chat_id)
        
        # Verify branch annotation
        with open(memory_file, "r") as f:
            data = json.load(f)
        
        # Last 2 messages should have branches field
        assert "branches" in data["messages"][-1]
        assert "test_branch" in data["messages"][-1]["branches"]
        
        # 4. Switch to main (no branch)
        result = await brain.execute_command("branch.switch",
            chat_id=chat_id,
            branch=""
        )
        assert result["status"] == "success"
        
        # Should only see original 2 messages (not branched ones)
        history = result["history"]
        assert len(history) == 2
        
        # 5. List branches
        result = await brain.execute_command("branch.list", chat_id=chat_id)
        assert result["status"] == "success"
        assert "test_branch" in result["branches"]
        
        print("Chat Branches Plugin Test Passed!")

if __name__ == "__main__":
    asyncio.run(test_plugin_chat_branches())
