"""
Tests for Smart Context Plugin.
"""

import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from sidecar import constants
from sidecar.pipeline.types import PipelineContext

# Import the plugin module dynamically since it's not in the main package
import importlib.util


def load_plugin_module(plugin_path):
    spec = importlib.util.spec_from_file_location(
        "smart_context_main", plugin_path / "main.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def smart_context_plugin_cls(tmp_path):
    """Load the Smart Context plugin class."""
    # We need to point to the actual plugin location
    # Assuming test is run from project root, locate the plugin
    base_dir = Path(__file__).resolve().parent.parent.parent
    plugin_path = base_dir / "example-vault" / "plugins" / "smart_context"

    module = load_plugin_module(plugin_path)
    return module.Plugin


@pytest.fixture
def mock_brain():
    """Create a mock VaultBrain."""
    brain = MagicMock()
    brain.emit_to_frontend = MagicMock()
    brain.notify_frontend = MagicMock()
    return brain


@pytest.fixture
def plugin_instance(smart_context_plugin_cls, tmp_path, mock_brain):
    """Create an instance of the Smart Context plugin."""
    plugin_dir = tmp_path / "plugins" / "smart_context"
    plugin_dir.mkdir(parents=True)
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
        plugin = smart_context_plugin_cls(plugin_dir, vault_path)
    return plugin


@pytest.mark.asyncio
class TestSmartContextPlugin:
    async def test_init(self, plugin_instance):
        """Test plugin initialization."""
        assert plugin_instance.name == "smart_context"
        assert plugin_instance.panel_id == "smart-context-panel"

    async def test_on_client_connected_registers_panel(
        self, plugin_instance, mock_brain
    ):
        """Test that panel is registered when client connects."""

        with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
            await plugin_instance.on_client_connected()

            # Check register_panel call (which emits UI_COMMAND)
            # We check the calls to brain.emit_to_frontend

            # Should have registered panel
            register_call = None
            set_content_call = None

            for call in mock_brain.emit_to_frontend.call_args_list:
                args, kwargs = call
                data = kwargs.get("data", {})
                if data.get("action") == constants.UIAction.REGISTER_PANEL.value:
                    register_call = data
                elif data.get("action") == constants.UIAction.SET_PANEL.value:
                    set_content_call = data

            assert register_call is not None
            assert register_call["id"] == "smart-context-panel"
            assert register_call["title"] == "Smart Context"

            # Should have set initial content
            assert set_content_call is not None
            assert set_content_call["id"] == "smart-context-panel"
            assert "Waiting for context" in set_content_call["html"]

    async def test_on_unload_removes_panel(self, plugin_instance, mock_brain):
        """Test that panel is removed when plugin unloads."""

        with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
            await plugin_instance.on_unload()

            # Check remove_panel call
            remove_call = None
            for call in mock_brain.emit_to_frontend.call_args_list:
                args, kwargs = call
                data = kwargs.get("data", {})
                if data.get("action") == constants.UIAction.REMOVE_PANEL.value:
                    remove_call = data

            assert remove_call is not None
            assert remove_call["id"] == "smart-context-panel"

    @pytest.mark.asyncio
    async def test_plugin_loads_config_defaults(self, plugin_instance):
        assert plugin_instance.similarity_threshold == 0.4
        assert plugin_instance.embedding_search is True
        assert plugin_instance.active_topics == set()

    @pytest.mark.asyncio
    async def test_on_load_subscribes_to_pipeline_events(self, plugin_instance, mock_brain):
        with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
            await plugin_instance.on_load()
        subscribed = [c[0][0] for c in mock_brain.subscribe.call_args_list]
        assert "pipeline.output" in subscribed
        assert "pipeline.context" in subscribed

    @pytest.mark.asyncio
    async def test_extract_topics_parses_llm_response(self, plugin_instance, mock_brain):
        messages = [
            {"id": "a1b2", "role": "user", "content": "be concise"},
            {"id": "c3d4", "role": "user", "content": "How does async work in Python?"},
            {"id": "e5f6", "role": "assistant", "content": "Async uses coroutines..."},
        ]

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "topics": [{"label": "Python Async", "count": 2}],
            "sticky_message_ids": ["a1b2"]
        })

        with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
            with patch("sidecar.services.llm_service.get_llm_service") as mock_get_llm:
                mock_llm = MagicMock()
                mock_llm.complete = AsyncMock(return_value=mock_response)
                mock_get_llm.return_value = mock_llm
                result = await plugin_instance._extract_topics(messages)

        labels = [t["label"] for t in result]
        assert "Python Async" in labels
        assert "Instructions & Preferences" in labels
        sticky = next(t for t in result if t.get("sticky"))
        assert sticky["message_ids"] == ["a1b2"]
        assert sticky["count"] == 1

    @pytest.mark.asyncio
    async def test_on_pipeline_output_creates_extraction_task(self, plugin_instance, mock_brain):
        """_on_pipeline_output should fire _run_topic_extraction as background task."""
        ctx = PipelineContext(
            message="hi", original_message="hi",
            metadata={"chat_id": "chat_abc"},
            response="Some LLM response",
        )
        extraction_calls = []

        async def fake_extraction(chat_id):
            extraction_calls.append(chat_id)

        plugin_instance._run_topic_extraction = fake_extraction
        await plugin_instance._on_pipeline_output(ctx)
        # Let the event loop run the created task
        await asyncio.sleep(0)
        assert extraction_calls == ["chat_abc"]

    @pytest.mark.asyncio
    async def test_on_pipeline_output_skips_when_no_response(self, plugin_instance):
        """_on_pipeline_output should do nothing when ctx.response is falsy."""
        ctx = PipelineContext(
            message="hi", original_message="hi",
            metadata={"chat_id": "chat_abc"},
        )
        called = []

        async def fake_extraction(chat_id):
            called.append(chat_id)

        plugin_instance._run_topic_extraction = fake_extraction
        await plugin_instance._on_pipeline_output(ctx)
        await asyncio.sleep(0)
        assert called == []

    @pytest.mark.asyncio
    async def test_run_topic_extraction_saves_and_emits(self, plugin_instance, mock_brain):
        """_run_topic_extraction should load chat, extract topics, save, and emit."""
        messages = [{"id": "m1", "role": "user", "content": "How does async work?"}]
        extracted_topics = [{"label": "Python Async", "count": 1}]

        mock_brain.execute_command = AsyncMock(return_value={
            "status": "success",
            "data": {"messages": messages, "topics": []},
        })
        plugin_instance._extract_topics = AsyncMock(return_value=extracted_topics)

        emitted = []
        plugin_instance.emit = lambda event, data: emitted.append((event, data))

        with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
            await plugin_instance._run_topic_extraction("chat_xyz")

        assert plugin_instance.current_chat_id == "chat_xyz"

        # execute_command called at least twice: load_chat and save_chat
        assert mock_brain.execute_command.call_count >= 2
        save_calls = [
            c for c in mock_brain.execute_command.call_args_list
            if c.args and c.args[0] == "memory.save_chat"
        ]
        assert len(save_calls) == 1

        # smart_context.topics_updated event emitted with correct payload
        assert any(event == "smart_context.topics_updated" for event, _ in emitted)
        topics_event = next(d for ev, d in emitted if ev == "smart_context.topics_updated")
        assert topics_event["chat_id"] == "chat_xyz"
        assert topics_event["total_messages"] == 1
        assert topics_event["topics"] == extracted_topics

    @pytest.mark.asyncio
    async def test_context_injection_passthrough_when_no_active_topics(self, plugin_instance, mock_brain):
        plugin_instance.active_topics = set()
        ctx = PipelineContext(message="hi", original_message="hi", metadata={})
        ctx.history = [{"id": "1", "role": "user", "content": "hello"}]
        await plugin_instance._on_pipeline_context(ctx)
        assert len(ctx.history) == 1  # unchanged

    @pytest.mark.asyncio
    async def test_context_injection_filters_by_similarity(self, plugin_instance, mock_brain):
        plugin_instance.active_topics = {"Python Async"}
        plugin_instance.embedding_search = True
        plugin_instance.similarity_threshold = 0.7

        ctx = PipelineContext(
            message="more?", original_message="more?",
            metadata={"chat_id": "chat_test"},
        )
        ctx.history = [
            {"id": "m1", "role": "user", "content": "How does async work in Python?"},
            {"id": "m2", "role": "user", "content": "What is the capital of France?"},
        ]

        with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
            mock_brain.execute_command = AsyncMock(return_value={
                "status": "success",
                "data": {"messages": ctx.history, "topics": [{"label": "Python Async", "count": 1}]}
            })
            with patch("sidecar.services.llm_service.get_llm_service") as mock_get_llm:
                mock_llm = MagicMock()
                mock_llm.embed = AsyncMock(side_effect=[
                    [[0.9, 0.1]],               # topic embedding
                    [[0.85, 0.15], [0.1, 0.95]] # m1=similar, m2=dissimilar
                ])
                mock_get_llm.return_value = mock_llm
                await plugin_instance._on_pipeline_context(ctx)

        assert len(ctx.history) == 1
        assert ctx.history[0]["id"] == "m1"

    @pytest.mark.asyncio
    async def test_context_injection_always_includes_sticky(self, plugin_instance, mock_brain):
        """Sticky messages are kept even when their own cosine similarity is below threshold."""
        plugin_instance.active_topics = {"Python Async"}
        plugin_instance.embedding_search = True
        plugin_instance.similarity_threshold = 0.7

        ctx = PipelineContext(message="q", original_message="q", metadata={"chat_id": "c1"})
        ctx.history = [
            {"id": "sticky1", "role": "user", "content": "be concise"},
            {"id": "m1", "role": "user", "content": "How does async work in Python?"},
            {"id": "m2", "role": "user", "content": "What is the capital of France?"},
        ]

        topics_data = {"messages": ctx.history, "topics": [
            {"label": "Python Async", "count": 1},
            {"label": "Instructions & Preferences", "sticky": True,
             "message_ids": ["sticky1"], "count": 1},
        ]}

        with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
            mock_brain.execute_command = AsyncMock(
                return_value={"status": "success", "data": topics_data}
            )
            with patch("sidecar.services.llm_service.get_llm_service") as mock_get_llm:
                mock_llm = MagicMock()
                # Topic embedding: [0.9, 0.1]
                # sticky1 embedding: [0.0, 1.0] — orthogonal to topic, cosine ≈ 0.0 (below 0.7)
                # m1 embedding: [0.85, 0.15] — similar to topic, cosine ≈ 0.99 (above 0.7)
                # m2 embedding: [0.1, 0.95] — dissimilar to topic, cosine ≈ 0.15 (below 0.7)
                mock_llm.embed = AsyncMock(side_effect=[
                    [[0.9, 0.1]],                        # topic embedding
                    [[0.0, 1.0], [0.85, 0.15], [0.1, 0.95]]  # sticky1, m1, m2
                ])
                mock_get_llm.return_value = mock_llm
                await plugin_instance._on_pipeline_context(ctx)

        ids_in_history = {m["id"] for m in ctx.history}
        assert "sticky1" in ids_in_history  # kept via sticky logic despite low cosine
        assert "m1" in ids_in_history       # kept via similarity (cosine ≈ 0.99 >= 0.7)
        assert "m2" not in ids_in_history   # filtered out (cosine ≈ 0.15 < 0.7)

    @pytest.mark.asyncio
    async def test_context_injection_fallback_when_threshold_met_by_nothing(self, plugin_instance, mock_brain):
        """If nothing passes threshold (excluding sticky), return full history."""
        plugin_instance.active_topics = {"Exotic Topic"}
        plugin_instance.embedding_search = True
        plugin_instance.similarity_threshold = 0.99

        ctx = PipelineContext(message="q", original_message="q", metadata={"chat_id": "c1"})
        original_history = [{"id": "m1", "role": "user", "content": "hello"}]
        ctx.history = original_history.copy()

        with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
            mock_brain.execute_command = AsyncMock(return_value={
                "status": "success",
                "data": {"messages": original_history, "topics": []}
            })
            with patch("sidecar.services.llm_service.get_llm_service") as mock_get_llm:
                mock_llm = MagicMock()
                mock_llm.embed = AsyncMock(side_effect=[[[1.0, 0.0]], [[0.1, 0.9]]])
                mock_get_llm.return_value = mock_llm
                await plugin_instance._on_pipeline_context(ctx)

        assert len(ctx.history) == 1  # full history preserved

    @pytest.mark.asyncio
    async def test_set_filter_updates_active_topics_and_emits(self, plugin_instance, mock_brain):
        with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
            result = await plugin_instance.set_filter(topics=["Python Async", "LangGraph"])
        assert plugin_instance.active_topics == {"Python Async", "LangGraph"}
        assert result["status"] == "success"
        mock_brain.emit_to_frontend.assert_called()

    @pytest.mark.asyncio
    async def test_set_filter_empty_clears(self, plugin_instance, mock_brain):
        plugin_instance.active_topics = {"Python Async"}
        with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
            await plugin_instance.set_filter(topics=[])
        assert plugin_instance.active_topics == set()

    @pytest.mark.asyncio
    async def test_get_topics_reads_from_chat_file(self, plugin_instance, mock_brain):
        mock_brain.execute_command = AsyncMock(return_value={
            "status": "success",
            "data": {
                "messages": [{"id": "1"}],
                "topics": [{"label": "Python", "count": 3}]
            }
        })
        with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
            result = await plugin_instance.get_topics(chat_id="chat_123")
        assert result["status"] == "success"
        assert result["topics"][0]["label"] == "Python"
        assert result["total_messages"] == 1

    @pytest.mark.asyncio
    async def test_set_similarity_mode_toggles(self, plugin_instance, mock_brain):
        plugin_instance.embedding_search = True
        plugin_instance.active_topics = {"Python Async"}
        with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
            result = await plugin_instance.set_similarity_mode(enabled=False)
        assert plugin_instance.embedding_search is False
        assert plugin_instance.active_topics == set()  # cleared on disable
        assert result["status"] == "success"
        mock_brain.emit_to_frontend.assert_called()  # filter_changed emitted

    @pytest.mark.asyncio
    async def test_on_client_connected_loads_panel_html_when_exists(self, plugin_instance, mock_brain):
        (plugin_instance.plugin_dir / "panel.html").write_text("<div id='sc-panel'>test</div>")
        with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
            await plugin_instance.on_client_connected()
        set_calls = [
            c for c in mock_brain.emit_to_frontend.call_args_list
            if c.kwargs.get("data", {}).get("action") == "set_panel"
        ]
        assert any("sc-panel" in c.kwargs["data"]["html"] for c in set_calls)


def _load_embedding_cache():
    base = Path(__file__).resolve().parent.parent.parent
    spec = importlib.util.spec_from_file_location(
        "embedding_cache",
        base / "example-vault/plugins/smart_context/embedding_cache.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.EmbeddingCache

def test_embedding_cache_miss_returns_none(tmp_path):
    EmbeddingCache = _load_embedding_cache()
    cache = EmbeddingCache(tmp_path, "chat_abc")
    assert cache.get("msg1", "hello world") is None

def test_embedding_cache_stores_and_retrieves(tmp_path):
    EmbeddingCache = _load_embedding_cache()
    cache = EmbeddingCache(tmp_path, "chat_abc")
    cache.set("msg1", "hello world", [0.1, 0.2, 0.3])
    assert cache.get("msg1", "hello world") == [0.1, 0.2, 0.3]

def test_embedding_cache_persists_across_instances(tmp_path):
    EmbeddingCache = _load_embedding_cache()
    EmbeddingCache(tmp_path, "chat_abc").set("msg1", "text", [1.0, 2.0])
    assert EmbeddingCache(tmp_path, "chat_abc").get("msg1", "text") == [1.0, 2.0]

def test_embedding_cache_content_change_is_cache_miss(tmp_path):
    EmbeddingCache = _load_embedding_cache()
    cache = EmbeddingCache(tmp_path, "chat_abc")
    cache.set("msg1", "original", [0.1, 0.2])
    assert cache.get("msg1", "modified") is None
