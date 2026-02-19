"""
Tests for Prompt Refiner Plugin.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
import importlib.util


def load_plugin_module(path):
    spec = importlib.util.spec_from_file_location("prompt_refiner_plugin", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plugin_path = Path("/home/arc/Dev/tailor/example-vault/plugins/prompt_refiner/main.py")
refiner = load_plugin_module(plugin_path)


@pytest.fixture
def mock_brain():
    brain = MagicMock()
    brain.emit_to_frontend = MagicMock()
    brain.register_command = MagicMock()
    brain.pipeline = MagicMock()  # Ensure pipeline exists check passes
    return brain


@pytest.fixture
def plugin(mock_brain, tmp_path):
    with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
        p = refiner.Plugin(tmp_path, tmp_path)
        yield p


@pytest.mark.asyncio
async def test_register_commands(plugin):
    plugin.register_commands()
    args = [call.args[0] for call in plugin.brain.register_command.call_args_list]
    assert "refiner.refine" in args
    assert "refiner.refine_from_ui" in args


@pytest.mark.asyncio
async def test_on_client_connected(plugin):
    await plugin.on_client_connected()
    calls = plugin.brain.emit_to_frontend.call_args_list
    # Should register action in composer
    assert any(
        c.kwargs["data"]["action"] == "register_action"
        and c.kwargs["data"]["id"] == "prompt-refiner"
        for c in calls
    )


@pytest.mark.asyncio
async def test_handle_refine_empty(plugin):
    res = await plugin._handle_refine("")
    assert res["status"] == "error"
    assert res["error"] == "empty_input"


@pytest.mark.asyncio
async def test_handle_refine_success(plugin):
    # Mock LLM service
    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(return_value=MagicMock(content="Refined Prompt"))

    with patch("sidecar.services.llm_service.get_llm_service", return_value=mock_llm):
        res = await plugin._handle_refine("Original Prompt")

        assert res["status"] == "success"
        assert res["original"] == "Original Prompt"
        assert res["refined"] == "Refined Prompt"

        # Should emit set_input
        calls = plugin.brain.emit_to_frontend.call_args_list
        assert any(
            c.kwargs["data"]["action"] == "set_input"
            and c.kwargs["data"]["text"] == "Refined Prompt"
            for c in calls
        )


@pytest.mark.asyncio
async def test_handle_refine_llm_unavailable(plugin):
    plugin.brain.pipeline = None
    res = await plugin._handle_refine("input")
    assert res["status"] == "error"
    assert res["error"] == "llm_unavailable"


@pytest.mark.asyncio
async def test_handle_refine_from_ui(plugin):
    await plugin._handle_refine_from_ui()
    # Should request input
    calls = plugin.brain.emit_to_frontend.call_args_list
    assert any(c.kwargs["data"]["action"] == "request_input" for c in calls)
