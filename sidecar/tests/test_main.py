import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
import pytest
from pathlib import Path
from sidecar import main

def test_parse_arguments():
    with patch("sys.argv", ["main.py", "--vault", "/tmp/vault", "--ws-port", "8080", "--verbose"]):
        args = main.parse_arguments()
        assert str(args.vault) == "/tmp/vault"
        assert args.ws_port == 8080
        assert args.verbose is True

@pytest.mark.asyncio
async def test_run_servers():
    mock_ws = AsyncMock()
    mock_brain = AsyncMock()

    await main.run_servers(mock_ws, mock_brain)
    
    mock_brain.initialize.assert_called_once()
    mock_ws.start.assert_called_once()
    mock_brain.tick_loop.assert_called_once()

def test_main_exit_on_missing_vault(tmp_path):
    vault_dir = tmp_path / "non_existent_vault"
    
    with patch("sys.argv", ["main.py", "--vault", str(vault_dir), "--ws-port", "8080"]):
        with patch("sys.exit") as mock_exit:
            main.main()
            mock_exit.assert_called_once_with(1)
