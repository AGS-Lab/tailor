import pytest
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from sidecar.vault_brain import VaultBrain


@pytest.fixture(autouse=True)
def reset_singleton():
    VaultBrain._instance = None
    yield
    VaultBrain._instance = None


@pytest.mark.asyncio
async def test_plugin_chat_branches():
    """Test Chat Branches plugin with inline branch annotations."""

    # Setup test brain
    example_vault = Path(__file__).parent.parent.parent / "example-vault"
    brain = VaultBrain(example_vault, MagicMock())

    # Mock LLM
    with patch("sidecar.vault_brain.LLMService") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.complete = AsyncMock(
            return_value=MagicMock(content="Response", model="test", usage={})
        )

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
        result = await brain.execute_command(
            "branch.create", chat_id=chat_id, message_id=msg_id, branch_id="test_branch"
        )
        print(f"Branch Create Result 1: {result}")
        assert result["status"] == "success", f"Branch creation failed: {result}"
        assert result["branch"] == "test_branch"

        # 3. Send message on branch
        mock_instance.complete.return_value = MagicMock(
            content="Branch Response", model="test", usage={}
        )
        await brain.chat_send(message="Branch Message", chat_id=chat_id)

        # Verify branch annotation
        with open(memory_file, "r") as f:
            data = json.load(f)

        # Last 2 messages should have branches field
        assert "branches" in data["messages"][-1]
        assert "test_branch" in data["messages"][-1]["branches"]

        # 4. List branches to find Root
        result = await brain.execute_command("branch.list", chat_id=chat_id)
        assert result["status"] == "success"

        # Find the branch that is effectively main/root (display_name="Main")
        root_branch_id = None
        for bid, bdata in result["branches"].items():
            if bdata.get("display_name") == "Main":
                root_branch_id = bid
                break

        assert root_branch_id is not None

        # 5. Switch to Root
        result = await brain.execute_command(
            "branch.switch", chat_id=chat_id, branch=root_branch_id
        )
        assert result["status"] == "success"

        # Should see original 2 message (User + Assistant on Main/Root path)
        history = result["history"]
        assert len(history) == 2
        assert history[1]["content"] == "Response"

        # 5. List branches
        result = await brain.execute_command("branch.list", chat_id=chat_id)
        assert result["status"] == "success"
        assert "test_branch" in result["branches"]

        # 6. Create Grandchild Branch (Recursive)
        # We are currently on "test_branch" (which has 2 messages: "Main Msg 1", "Branch Message")
        # Let's branch off "Branch Message" (the last one)

        # Get history to find the ID of "Branch Message"
        current_history = await brain.execute_command(
            "chat.get_history", chat_id=chat_id
        )
        last_msg_id = current_history["history"][-1]["id"]

        result = await brain.execute_command(
            "branch.create",
            chat_id=chat_id,
            message_id=last_msg_id,
            branch_id="grandchild_branch",
        )
        assert result["status"] == "success"

        # 7. Verify Grandchild History
        # Should contain:
        # - Root Msg (1)
        # - Child Msg (1) (Truncated from test_branch if split? OR if we branch from END, it's just append)
        # Wait, if we branch from END, it's NOT a split. It's just a new head.
        # But our create_branch logic treats everything as "Split" or "End Split".
        # If "End Split" (tail is empty), we create a new branch parented to source.
        # So: Root -> test_branch -> grandchild.
        # History should specify messages from all 3?
        # Actually:
        # Root has Msg1.
        # test_branch has Msg2.
        # grandchild_branch starts empty?
        # Let's send a message on grandchild.

        mock_instance.complete.return_value = MagicMock(
            content="Grandchild Resp", model="test", usage={}
        )
        await brain.chat_send(message="Grandchild Msg", chat_id=chat_id)

        # Now fetch history for grandchild
        result = await brain.execute_command("chat.get_history", chat_id=chat_id)
        history = result["history"]

        # Expectation:
        # 1. Root Msg ("Hello") [Source: Root]
        # 2. Test Branch Msg ("Branch Message") [Source: test_branch] (Assistant response)
        #    Wait, in previous steps we sent "Branch Message" (User) + "Branch Response" (Assistant)?
        #    Let's check previous steps...
        #    Step 3 sent "Branch Message".
        #    So test_branch has: "Branch Message", "Branch Response".
        #    We branched off "Branch Response" (last_msg_id).
        #    So "test_branch" keeps those messages.
        #    "grandchild_branch" is new.
        #    Plus "Grandchild Msg" + "Grandchild Resp".
        # Total: 1 (Root) + 2 (Test) + 2 (Grandchild) = 5?

        assert len(history) >= 3  # At least one from each layer

        # Verify source_branch injection
        # Last message should have source_branch = grandchild_branch
        assert history[-1]["source_branch"] == "grandchild_branch"

        # First message should have source_branch = PARENT of root_branch_id (Main)
        # Because User "Hello" is in the absolute root (which has no name), and "Main" is the continuation.
        branches_meta = result["branches"]  # From last branch.list call
        main_branch_info = branches_meta.get(root_branch_id)
        assert main_branch_info is not None
        absolute_root_id = main_branch_info.get("parent_branch")
        assert absolute_root_id is not None

        assert history[0]["source_branch"] == absolute_root_id

        print("Chat Branches Plugin Recursive Test Passed!")


if __name__ == "__main__":
    asyncio.run(test_plugin_chat_branches())
