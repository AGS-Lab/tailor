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
from sidecar.services.llm_service import LLMService

@pytest.mark.asyncio
async def test_branching_edge_cases():
    # Setup paths
    vault_path = Path("/home/arc/Dev/tailor/example-vault")
    memory_dir = vault_path / ".memory"
    chat_id = "chat_edge_cases"
    memory_file = memory_dir / f"{chat_id}.json"
    
    # Clean up
    if memory_dir.exists():
        shutil.rmtree(memory_dir)
        
    # Reset Singleton
    if VaultBrain._instance:
        VaultBrain._instance = None
    
    # Initialize
    brain = VaultBrain(vault_path, MagicMock())
    
    from unittest.mock import patch
    
    with patch("sidecar.vault_brain.LLMService") as MockServiceClass:
        mock_instance = MockServiceClass.return_value
        mock_instance.complete = AsyncMock()
        # We need 2 responses for M1 and M2
        mock_instance.complete.side_effect = [
            MagicMock(content="Response 1", model="test", usage={}),
            MagicMock(content="Response 2", model="test", usage={})
        ]
        
        await brain.initialize()
        
        print(f"Loaded plugins: {list(brain.plugins.keys())}")
        
        # =========================================================================
        # Scenario 1: Setup - Linear Chat [M1, R1, M2, R2]
        # =========================================================================
        await brain.chat_send(message="M1", chat_id=chat_id)
        await brain.chat_send(message="M2", chat_id=chat_id)
        
        with open(memory_file, "r") as f:
            data = json.load(f)
        root_id = data["active_branch"]
        msgs = data["branches"][root_id]["messages"]
        # IDs: M1=0, R1=1, M2=2, R2=3
        m1_id = msgs[0]["id"]
        m2_id = msgs[2]["id"]
        
        # =========================================================================
        # Scenario 2: Branch from LAST message (M2)
        # =========================================================================
        res = await brain.execute_command("branch.create", chat_id=chat_id, message_id=m2_id, name="Branch_From_End")
        assert res["status"] == "success"
        branch_end_id = res["branch"]
        
        with open(memory_file, "r") as f:
            data = json.load(f)
            
        root_msgs = data["branches"][root_id]["messages"]
        # If we branch from END, the root might keep all if we just add a new pointer?
        # But logic usually splits if message is not last.
        # Here message M2 (index 2) is NOT last (R2 index 3 is last).
        # So it SHOULD split.
        
        assert len(root_msgs) == 3 # M1, R1, M2
        assert root_msgs[-1]["id"] == m2_id
        
        # Find Continuation
        continuation_id = None
        print(f"DEBUG: Branches: {json.dumps(data['branches'], indent=2)}")
        for bid, b in data["branches"].items():
            if b.get("parent_branch") == root_id and bid != branch_end_id:
                continuation_id = bid
                break
        assert continuation_id is not None
        assert len(data["branches"][continuation_id]["messages"]) == 1 # R2
        
        # =========================================================================
        # Scenario 3: Branch from MIDDLE (M1)
        # =========================================================================
        res = await brain.execute_command("branch.create", chat_id=chat_id, message_id=m1_id, name="Branch_From_Mid")
        assert res["status"] == "success"
        branch_mid_id = res["branch"]
        
        with open(memory_file, "r") as f:
            data = json.load(f)
            
        root_msgs = data["branches"][root_id]["messages"]
        # If splitting at M1 (index 0), root becomes length 1.
        assert len(root_msgs) == 1 # Just M1
        
        # =========================================================================
        # Scenario 4: Switch to Non-Existent Branch
        # =========================================================================
        res = await brain.execute_command("branch.switch", chat_id=chat_id, branch="fake_branch")
        assert res["status"] == "error"
        
        # =========================================================================
        # Scenario 5: Ensure correct active branch
        # =========================================================================
        # We last created "Branch_From_Mid", so that should be active
        assert data["active_branch"] == branch_mid_id

    print("Edge Cases Test Passed!")

if __name__ == "__main__":
    asyncio.run(test_branching_edge_cases())
