# Smart Context Plugin Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the Smart Context plugin — LLM-extracted topic bubbles, embedding-based context filtering, sticky instructional messages, and chat message highlighting.

**Architecture:** Two pipeline subscribers (`pipeline.output` → async topic extraction, `pipeline.context` → embedding filter). Topics stored as flat list on chat JSON. Sticky instructional messages always injected. Embedding vectors cached in `.memory/{chat_id}.embeddings.json`. Panel HTML/JS communicates back via `window.request('execute_command', ...)`. Backend events arrive as `CustomEvent` on `window`.

**Tech Stack:** Python, LiteLLM (`aembedding`), vanilla JS, `cosine_similarity` in pure Python (no numpy).

---

### Task 1: Add `embed()` to LLMService

**Files:**
- Modify: `sidecar/services/llm_service.py`
- Modify: `sidecar/tests/test_llm_service.py`

**Step 1: Write the failing test**

```python
# sidecar/tests/test_llm_service.py — add inside or alongside existing tests
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pathlib import Path
from sidecar.services.llm_service import LLMService

@pytest.mark.asyncio
async def test_embed_returns_list_of_vectors():
    with patch("litellm.aembedding") as mock_embed:
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
```

**Step 2: Verify it fails**

Run: `pixi run pytest sidecar/tests/test_llm_service.py::test_embed_returns_list_of_vectors -v`
Expected: FAIL — `LLMService has no attribute 'embed'`

**Step 3: Implement `embed()`**

In `sidecar/services/llm_service.py`, add this method to `LLMService` after `_stream_completion` (around line 515):

```python
async def embed(
    self,
    texts: List[str],
    category: str = "embedding",
) -> List[List[float]]:
    """Generate embeddings for a list of texts via LiteLLM."""
    from litellm import aembedding

    model_id = self.get_model_for_category(category)
    if not model_id:
        raise ValueError(f"No model configured for category: {category}")

    litellm_model = self._format_model_for_litellm(model_id)
    self._logger.debug(f"Embedding {len(texts)} texts with {litellm_model}")
    response = await aembedding(model=litellm_model, input=texts)
    return [item["embedding"] for item in response.data]
```

**Step 4: Verify it passes**

Run: `pixi run pytest sidecar/tests/test_llm_service.py::test_embed_returns_list_of_vectors -v`
Expected: PASS

**Step 5: Commit**

```bash
git add sidecar/services/llm_service.py sidecar/tests/test_llm_service.py
git commit -m "feat: add embed() method to LLMService"
```

---

### Task 2: EmbeddingCache

**Files:**
- Create: `example-vault/plugins/smart_context/embedding_cache.py`
- Modify: `sidecar/tests/test_plugin_smart_context.py`

**Step 1: Write failing tests**

Add to `sidecar/tests/test_plugin_smart_context.py`:

```python
import importlib.util
from pathlib import Path

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
```

**Step 2: Verify they fail**

Run: `pixi run pytest sidecar/tests/test_plugin_smart_context.py -k "embedding_cache" -v`
Expected: FAIL — file not found

**Step 3: Create `embedding_cache.py`**

```python
"""Embedding cache backed by a JSON sidecar file."""
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional


class EmbeddingCache:
    """Caches message embeddings in .memory/{chat_id}.embeddings.json."""

    def __init__(self, memory_dir: Path, chat_id: str):
        safe_id = "".join(c for c in chat_id if c.isalnum() or c in "-_")
        self._path = memory_dir / f"{safe_id}.embeddings.json"
        self._data: Dict[str, List[float]] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f)

    @staticmethod
    def _key(message_id: str, content: str) -> str:
        h = hashlib.md5(content.encode()).hexdigest()[:8]
        return f"{message_id}:{h}"

    def get(self, message_id: str, content: str) -> Optional[List[float]]:
        return self._data.get(self._key(message_id, content))

    def set(self, message_id: str, content: str, embedding: List[float]) -> None:
        self._data[self._key(message_id, content)] = embedding
        self._save()
```

**Step 4: Verify all 4 tests pass**

Run: `pixi run pytest sidecar/tests/test_plugin_smart_context.py -k "embedding_cache" -v`
Expected: 4 PASS

**Step 5: Commit**

```bash
git add example-vault/plugins/smart_context/embedding_cache.py sidecar/tests/test_plugin_smart_context.py
git commit -m "feat: EmbeddingCache for smart_context plugin"
```

---

### Task 3: Plugin Skeleton — Config, State, Subscriptions

**Files:**
- Modify: `example-vault/plugins/smart_context/main.py`
- Modify: `sidecar/tests/test_plugin_smart_context.py`

**Step 1: Write failing tests**

```python
# sidecar/tests/test_plugin_smart_context.py
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_plugin_loads_config_defaults(plugin_instance):
    assert plugin_instance.similarity_threshold == 0.4
    assert plugin_instance.embedding_search is True
    assert plugin_instance.active_topics == set()

@pytest.mark.asyncio
async def test_on_load_subscribes_to_pipeline_events(plugin_instance, mock_brain):
    with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
        await plugin_instance.on_load()
    subscribed = [c[0][0] for c in mock_brain.subscribe.call_args_list]
    assert "pipeline.output" in subscribed
    assert "pipeline.context" in subscribed
```

**Step 2: Verify they fail**

Run: `pixi run pytest sidecar/tests/test_plugin_smart_context.py::TestSmartContextPlugin::test_plugin_loads_config_defaults -v`
Expected: FAIL

**Step 3: Rewrite `main.py`**

```python
"""Smart Context Plugin — topic map + embedding-based context filtering."""
import asyncio
import json
import math
import sys
from pathlib import Path
from typing import Dict, Any, List, Set

# Make embedding_cache importable (same directory)
_plugin_dir = Path(__file__).parent
if str(_plugin_dir) not in sys.path:
    sys.path.insert(0, str(_plugin_dir))

from embedding_cache import EmbeddingCache

from sidecar.api.plugin_base import PluginBase
from sidecar.pipeline.events import PipelineEvents
from sidecar.pipeline.types import PipelineContext


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


TOPIC_EXTRACTION_PROMPT = """\
Analyze this conversation and extract the main topics discussed.
Return JSON only — no markdown, no prose.

Format:
{
  "topics": [{"label": "Topic Name", "count": N}],
  "sticky_message_ids": ["id1", "id2"]
}

Rules:
- 3-8 topics max, 2-4 words each, Title Case
- count = approximate number of messages related to this topic
- sticky_message_ids: IDs of SHORT instructional/preference messages
  (e.g. "be concise", "respond in French", "use Python 3")
- Return ONLY valid JSON"""


class Plugin(PluginBase):
    """Smart Context Plugin."""

    def __init__(self, plugin_dir: Path, vault_path: Path, config: Dict[str, Any] = None):
        super().__init__(plugin_dir, vault_path, config)
        self.panel_id = "smart-context-panel"

        self.similarity_threshold: float = float(self.config.get("similarity_threshold", 0.4))
        self.embedding_search: bool = bool(self.config.get("embedding_search", True))

        self.active_topics: Set[str] = set()
        self.current_chat_id: str = ""

        self.logger.info("Smart Context plugin initialized")

    def register_commands(self) -> None:
        self.brain.register_command("smart_context.set_filter", self.set_filter, self.name)
        self.brain.register_command("smart_context.get_topics", self.get_topics, self.name)
        self.brain.register_command("smart_context.set_similarity_mode", self.set_similarity_mode, self.name)

    async def on_load(self) -> None:
        await super().on_load()
        self.subscribe(PipelineEvents.OUTPUT, self._on_pipeline_output)
        self.subscribe(PipelineEvents.CONTEXT, self._on_pipeline_context)
        self.logger.info("Smart Context plugin loaded")

    async def on_client_connected(self) -> None:
        await self.register_panel(
            panel_id=self.panel_id,
            title="Smart Context",
            icon="brain",
            position="right",
        )
        panel_file = self.plugin_dir / "panel.html"
        html = panel_file.read_text(encoding="utf-8") if panel_file.exists() else \
            "<div style='padding:10px'><p>Waiting for context…</p></div>"
        await self.set_panel_content(panel_id=self.panel_id, html_content=html)

    async def on_unload(self) -> None:
        await self.remove_panel(self.panel_id)
        await super().on_unload()

    # =========================================================================
    # Pipeline Subscribers (stubs — filled in Tasks 4 & 5)
    # =========================================================================

    async def _on_pipeline_output(self, ctx: PipelineContext) -> None:
        pass

    async def _on_pipeline_context(self, ctx: PipelineContext) -> None:
        pass

    # =========================================================================
    # Commands (stubs — filled in Task 6)
    # =========================================================================

    async def set_filter(self, topics: List[str] = None, **kwargs) -> Dict[str, Any]:
        return {"status": "success"}

    async def get_topics(self, chat_id: str = "", **kwargs) -> Dict[str, Any]:
        return {"status": "success", "topics": []}

    async def set_similarity_mode(self, enabled: bool = True, **kwargs) -> Dict[str, Any]:
        return {"status": "success"}
```

**Step 4: Run all existing tests**

Run: `pixi run pytest sidecar/tests/test_plugin_smart_context.py -v`
Expected: All PASS (new tests + pre-existing panel tests)

**Step 5: Commit**

```bash
git add example-vault/plugins/smart_context/main.py sidecar/tests/test_plugin_smart_context.py
git commit -m "feat: smart_context skeleton — config, state, subscriptions"
```

---

### Task 4: Topic Extraction (`pipeline.output` subscriber)

**Files:**
- Modify: `example-vault/plugins/smart_context/main.py`
- Modify: `sidecar/tests/test_plugin_smart_context.py`

**Step 1: Write failing test**

```python
import json
from unittest.mock import AsyncMock, MagicMock, patch
from sidecar.pipeline.types import PipelineContext

@pytest.mark.asyncio
async def test_extract_topics_parses_llm_response(plugin_instance, mock_brain):
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
```

**Step 2: Verify it fails**

Run: `pixi run pytest sidecar/tests/test_plugin_smart_context.py::TestSmartContextPlugin::test_extract_topics_parses_llm_response -v`
Expected: FAIL — `_extract_topics` not defined

**Step 3: Implement `_extract_topics` and `_on_pipeline_output`**

Replace the `_on_pipeline_output` stub and add new methods in `main.py`:

```python
async def _extract_topics(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Call LLM to extract topics and identify sticky messages."""
    from sidecar.services.llm_service import get_llm_service

    conversation = "\n".join(
        f"[{m.get('id', '?')}] {m.get('role', 'user')}: "
        f"{str(m.get('content', ''))[:200]}"
        for m in messages
    )

    llm_messages = [
        {"role": "system", "content": TOPIC_EXTRACTION_PROMPT},
        {"role": "user", "content": conversation},
    ]

    llm = get_llm_service()
    category = self.config.get("extraction_category", "fast")
    response = await llm.complete(
        messages=llm_messages,
        category=category,
        max_tokens=512,
        temperature=0.2,
    )

    raw = response.content.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"):
            raw = raw[:-3]

    data = json.loads(raw)
    topics: List[Dict[str, Any]] = data.get("topics", [])
    sticky_ids: List[str] = data.get("sticky_message_ids", [])

    if sticky_ids:
        topics.append({
            "label": "Instructions & Preferences",
            "sticky": True,
            "message_ids": sticky_ids,
            "count": len(sticky_ids),
        })

    return topics


async def _on_pipeline_output(self, ctx: PipelineContext) -> None:
    """After each LLM response: extract topics in background."""
    if not ctx.response:
        return
    chat_id = ctx.metadata.get("chat_id")
    if not chat_id:
        return
    asyncio.create_task(self._run_topic_extraction(chat_id))


async def _run_topic_extraction(self, chat_id: str) -> None:
    """Background: extract topics from chat and save + notify panel."""
    try:
        result = await self.brain.execute_command("memory.load_chat", chat_id=chat_id)
        if result.get("status") != "success":
            return
        data = result.get("data", {})
        messages = data.get("messages", [])
        if not messages:
            return

        topics = await self._extract_topics(messages)
        data["topics"] = topics
        await self.brain.execute_command("memory.save_chat", chat_id=chat_id, data=data)

        self.current_chat_id = chat_id
        self.emit("smart_context.topics_updated", {
            "chat_id": chat_id,
            "topics": topics,
            "total_messages": len(messages),
        })
        self.logger.info(f"Topics extracted for {chat_id}: {[t['label'] for t in topics]}")
    except Exception as e:
        self.logger.error(f"Topic extraction failed for {chat_id}: {e}")
```

**Step 4: Run tests**

Run: `pixi run pytest sidecar/tests/test_plugin_smart_context.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add example-vault/plugins/smart_context/main.py sidecar/tests/test_plugin_smart_context.py
git commit -m "feat: smart_context topic extraction via pipeline.output"
```

---

### Task 5: Context Injection (`pipeline.context` subscriber)

**Files:**
- Modify: `example-vault/plugins/smart_context/main.py`
- Modify: `sidecar/tests/test_plugin_smart_context.py`

**Step 1: Write failing tests**

```python
@pytest.mark.asyncio
async def test_context_injection_passthrough_when_no_active_topics(plugin_instance, mock_brain):
    plugin_instance.active_topics = set()
    ctx = PipelineContext(message="hi", original_message="hi", metadata={})
    ctx.history = [{"id": "1", "role": "user", "content": "hello"}]
    await plugin_instance._on_pipeline_context(ctx)
    assert len(ctx.history) == 1  # unchanged


@pytest.mark.asyncio
async def test_context_injection_filters_by_similarity(plugin_instance, mock_brain):
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
async def test_context_injection_always_includes_sticky(plugin_instance, mock_brain):
    plugin_instance.active_topics = {"Python Async"}
    plugin_instance.embedding_search = True
    plugin_instance.similarity_threshold = 0.99  # impossibly high

    ctx = PipelineContext(message="q", original_message="q", metadata={"chat_id": "c1"})
    ctx.history = [
        {"id": "sticky1", "role": "user", "content": "be concise"},
        {"id": "m1", "role": "user", "content": "something about python async"},
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
            mock_llm.embed = AsyncMock(side_effect=[
                [[1.0, 0.0]],             # topic
                [[0.1, 0.9], [0.0, 1.0]] # both low similarity
            ])
            mock_get_llm.return_value = mock_llm
            await plugin_instance._on_pipeline_context(ctx)

    assert any(m["id"] == "sticky1" for m in ctx.history)


@pytest.mark.asyncio
async def test_context_injection_fallback_when_threshold_met_by_nothing(plugin_instance, mock_brain):
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
```

**Step 2: Verify they fail**

Run: `pixi run pytest sidecar/tests/test_plugin_smart_context.py -k "context_injection" -v`
Expected: All FAIL

**Step 3: Implement shared helper + `_on_pipeline_context`**

Add `_compute_relevant_ids` (shared by context injection and highlight computation) and replace the stub:

```python
async def _compute_relevant_ids(
    self, chat_id: str, messages: List[Dict[str, Any]], sticky_ids: Set[str]
) -> List[str]:
    """
    Return IDs of messages relevant to active_topics via cosine similarity.
    Sticky IDs are always included. Returns empty list if nothing passes threshold
    (caller should fall back to full history).
    """
    from sidecar.services.llm_service import get_llm_service

    llm = get_llm_service()
    topic_embeddings = await llm.embed(list(self.active_topics))

    cache = EmbeddingCache(self.vault_path / ".memory", chat_id)
    need_embed = []
    cached: Dict[str, List[float]] = {}

    for msg in messages:
        msg_id = msg.get("id", "")
        content = str(msg.get("content", ""))
        emb = cache.get(msg_id, content)
        if emb is not None:
            cached[msg_id] = emb
        else:
            need_embed.append(msg)

    if need_embed:
        texts = [str(m.get("content", "")) for m in need_embed]
        new_embeddings = await llm.embed(texts)
        for msg, emb in zip(need_embed, new_embeddings):
            msg_id = msg.get("id", "")
            content = str(msg.get("content", ""))
            cache.set(msg_id, content, emb)
            cached[msg_id] = emb

    included: List[str] = []
    for msg in messages:
        msg_id = msg.get("id", "")
        if msg_id in sticky_ids:
            included.append(msg_id)
            continue
        emb = cached.get(msg_id)
        if emb is None:
            continue
        max_sim = max(_cosine_similarity(emb, t_emb) for t_emb in topic_embeddings)
        if max_sim >= self.similarity_threshold:
            included.append(msg_id)

    return included


async def _on_pipeline_context(self, ctx: PipelineContext) -> None:
    """Filter ctx.history using embedding similarity to active topics."""
    if not self.active_topics or not self.embedding_search:
        return

    chat_id = ctx.metadata.get("chat_id")
    if not chat_id or not ctx.history:
        return

    try:
        result = await self.brain.execute_command("memory.load_chat", chat_id=chat_id)
        data = result.get("data", {})
        topics_list = data.get("topics", [])

        sticky_ids: Set[str] = set()
        for t in topics_list:
            if t.get("sticky"):
                sticky_ids.update(t.get("message_ids", []))

        included = await self._compute_relevant_ids(chat_id, ctx.history, sticky_ids)

        non_sticky_included = [i for i in included if i not in sticky_ids]
        if not non_sticky_included:
            return  # nothing passed threshold — keep full history

        included_set = set(included)
        ctx.history = [m for m in ctx.history if m.get("id", "") in included_set]

    except Exception as e:
        self.logger.error(f"Context injection failed: {e}")
```

**Step 4: Run tests**

Run: `pixi run pytest sidecar/tests/test_plugin_smart_context.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add example-vault/plugins/smart_context/main.py sidecar/tests/test_plugin_smart_context.py
git commit -m "feat: smart_context context injection with embedding similarity"
```

---

### Task 6: Commands — `set_filter`, `get_topics`, `set_similarity_mode`

**Files:**
- Modify: `example-vault/plugins/smart_context/main.py`
- Modify: `sidecar/tests/test_plugin_smart_context.py`

**Step 1: Write failing tests**

```python
@pytest.mark.asyncio
async def test_set_filter_updates_active_topics_and_emits(plugin_instance, mock_brain):
    with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
        result = await plugin_instance.set_filter(topics=["Python Async", "LangGraph"])
    assert plugin_instance.active_topics == {"Python Async", "LangGraph"}
    assert result["status"] == "success"
    mock_brain.emit_to_frontend.assert_called()


@pytest.mark.asyncio
async def test_set_filter_empty_clears(plugin_instance, mock_brain):
    plugin_instance.active_topics = {"Python Async"}
    with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
        await plugin_instance.set_filter(topics=[])
    assert plugin_instance.active_topics == set()


@pytest.mark.asyncio
async def test_get_topics_reads_from_chat_file(plugin_instance, mock_brain):
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
async def test_set_similarity_mode_toggles(plugin_instance, mock_brain):
    plugin_instance.embedding_search = True
    result = await plugin_instance.set_similarity_mode(enabled=False)
    assert plugin_instance.embedding_search is False
    assert result["status"] == "success"
```

**Step 2: Verify they fail**

Run: `pixi run pytest sidecar/tests/test_plugin_smart_context.py -k "test_set_filter or test_get_topics or test_set_similarity" -v`
Expected: FAIL (stubs return success but don't update state)

**Step 3: Implement commands**

Replace the three stub command methods in `main.py`:

```python
async def set_filter(self, topics: List[str] = None, **kwargs) -> Dict[str, Any]:
    """Set active topic filter. Empty list clears it."""
    if topics is None:
        p = kwargs.get("p") or kwargs.get("params", {})
        topics = p.get("topics", [])

    self.active_topics = set(topics)
    self.emit("smart_context.filter_changed", {
        "active_topics": list(self.active_topics),
        "chat_id": self.current_chat_id,
    })

    if self.current_chat_id and self.active_topics and self.embedding_search:
        asyncio.create_task(self._emit_highlight_ids(self.current_chat_id))

    return {"status": "success", "active_topics": list(self.active_topics)}


async def get_topics(self, chat_id: str = "", **kwargs) -> Dict[str, Any]:
    """Return topics for the given chat."""
    if not chat_id:
        p = kwargs.get("p") or kwargs.get("params", {})
        chat_id = p.get("chat_id", self.current_chat_id)

    if not chat_id:
        return {"status": "success", "topics": [], "total_messages": 0}

    result = await self.brain.execute_command("memory.load_chat", chat_id=chat_id)
    if result.get("status") != "success":
        return {"status": "success", "topics": [], "total_messages": 0}

    data = result.get("data", {})
    return {
        "status": "success",
        "topics": data.get("topics", []),
        "total_messages": len(data.get("messages", [])),
    }


async def set_similarity_mode(self, enabled: bool = True, **kwargs) -> Dict[str, Any]:
    """Toggle embedding-based context filtering."""
    if not isinstance(enabled, bool):
        p = kwargs.get("p") or kwargs.get("params", {})
        enabled = bool(p.get("enabled", True))
    self.embedding_search = enabled
    if not enabled:
        self.active_topics.clear()
        self.emit("smart_context.filter_changed", {
            "active_topics": [],
            "chat_id": self.current_chat_id,
        })
    return {"status": "success", "embedding_search": self.embedding_search}


async def _emit_highlight_ids(self, chat_id: str) -> None:
    """Background: compute filtered message IDs and emit for chat highlighting."""
    try:
        result = await self.brain.execute_command("memory.load_chat", chat_id=chat_id)
        data = result.get("data", {})
        messages = data.get("messages", [])
        topics_list = data.get("topics", [])

        sticky_ids: Set[str] = set()
        for t in topics_list:
            if t.get("sticky"):
                sticky_ids.update(t.get("message_ids", []))

        included = await self._compute_relevant_ids(chat_id, messages, sticky_ids)
        self.emit("smart_context.highlight_applied", {"message_ids": included})
    except Exception as e:
        self.logger.error(f"Highlight computation failed: {e}")
```

**Step 4: Run tests**

Run: `pixi run pytest sidecar/tests/test_plugin_smart_context.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add example-vault/plugins/smart_context/main.py sidecar/tests/test_plugin_smart_context.py
git commit -m "feat: smart_context commands — set_filter, get_topics, set_similarity_mode"
```

---

### Task 7: Panel HTML

**Files:**
- Create: `example-vault/plugins/smart_context/panel.html`
- Modify: `sidecar/tests/test_plugin_smart_context.py`

**Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_on_client_connected_loads_panel_html_when_exists(plugin_instance, mock_brain):
    (plugin_instance.plugin_dir / "panel.html").write_text("<div id='sc-panel'>test</div>")
    with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
        await plugin_instance.on_client_connected()
    set_calls = [
        c for c in mock_brain.emit_to_frontend.call_args_list
        if c[1].get("data", {}).get("action") == "set_panel"
    ]
    assert any("sc-panel" in c[1]["data"]["html"] for c in set_calls)
```

**Step 2: Verify it fails**

Run: `pixi run pytest sidecar/tests/test_plugin_smart_context.py::TestSmartContextPlugin::test_on_client_connected_loads_panel_html_when_exists -v`
Expected: FAIL — test file content `sc-panel` not found in HTML (fallback placeholder used instead)

**Step 3: Create `panel.html`**

```html
<!DOCTYPE html>
<html>
<head>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: transparent; }
#sc-panel {
  padding: 12px;
  font-family: var(--font-sans, system-ui, sans-serif);
  font-size: 13px;
  color: var(--text-primary, #e0e0e0);
  height: 100%;
}
.sc-sticky-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: rgba(255,255,255,0.06);
  border-radius: 6px;
  font-size: 12px;
  margin-bottom: 12px;
  color: var(--text-muted, #aaa);
}
.sc-sticky-bar strong { margin-left: auto; color: var(--text-primary, #e0e0e0); }
.sc-mode-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.sc-mode-row input { cursor: pointer; }
#sc-bubbles {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
  min-height: 36px;
}
.sc-bubble {
  cursor: pointer;
  border-radius: 20px;
  padding: 4px 12px;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.12);
  transition: all 0.15s ease;
  user-select: none;
  white-space: nowrap;
}
.sc-bubble:hover { background: rgba(255,255,255,0.15); }
.sc-bubble.sc-active {
  background: rgba(99,179,237,0.25);
  border-color: rgba(99,179,237,0.6);
  box-shadow: 0 0 8px rgba(99,179,237,0.3);
}
.sc-bubble.sc-dim { opacity: 0.35; }
.sc-no-topics { opacity: 0.4; font-size: 12px; font-style: italic; }
#sc-status { font-size: 12px; color: var(--text-muted, #888); }
</style>
</head>
<body>
<div id="sc-panel">

  <div class="sc-sticky-bar">
    <span>🔒</span>
    <span>Instructions always in context</span>
    <strong id="sc-sticky-count">0</strong>
  </div>

  <div class="sc-mode-row">
    <input type="checkbox" id="sc-toggle" checked
           onchange="window.scToggleSimilarity(this.checked)">
    <label for="sc-toggle">Similarity filter</label>
  </div>

  <div id="sc-bubbles">
    <span class="sc-no-topics">Waiting for context…</span>
  </div>

  <div id="sc-status">All messages in context</div>

</div>
<script>
var scTopics = [];
var scActive = new Set();
var scSimilarity = true;

function scRender() {
  var bubblesEl = document.getElementById('sc-bubbles');
  var statusEl  = document.getElementById('sc-status');
  var stickyEl  = document.getElementById('sc-sticky-count');

  var sticky = scTopics.find(function(t){ return t.sticky; });
  stickyEl.textContent = sticky ? sticky.count : 0;

  var regular = scTopics.filter(function(t){ return !t.sticky; });
  if (!regular.length) {
    bubblesEl.innerHTML = '<span class="sc-no-topics">No topics yet…</span>';
    statusEl.textContent = 'All messages in context';
    return;
  }

  var maxCount = Math.max.apply(null, regular.map(function(t){ return t.count; }));
  var hasFilter = scSimilarity && scActive.size > 0;

  bubblesEl.innerHTML = regular.map(function(t) {
    var scale = (0.85 + 0.3 * (t.count / maxCount)).toFixed(2);
    var cls = 'sc-bubble';
    if (hasFilter) cls += scActive.has(t.label) ? ' sc-active' : ' sc-dim';
    var safeLbl = t.label.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    return '<div class="' + cls + '" style="font-size:' + scale + 'em" ' +
           'onclick="window.scToggleTopic(\'' + safeLbl + '\')">' +
           t.label + '</div>';
  }).join('');

  statusEl.textContent = hasFilter
    ? scActive.size + ' topic(s) selected — context filtered'
    : 'All messages in context';
}

window.scToggleTopic = function(label) {
  if (!scSimilarity) return;
  if (scActive.has(label)) scActive.delete(label);
  else scActive.add(label);
  scRender();
  window.request('execute_command', {
    command: 'smart_context.set_filter',
    args: { topics: Array.from(scActive) }
  }).catch(function(e){ console.error('[SmartContext] set_filter:', e); });
};

window.scToggleSimilarity = function(enabled) {
  scSimilarity = enabled;
  if (!enabled) {
    scActive.clear();
    window.request('execute_command', {
      command: 'smart_context.set_filter',
      args: { topics: [] }
    }).catch(console.error);
  }
  window.request('execute_command', {
    command: 'smart_context.set_similarity_mode',
    args: { enabled: enabled }
  }).catch(console.error);
  scRender();
};

// Backend pushes new topics after each response
window.addEventListener('smart_context.topics_updated', function(e) {
  var d = e.detail || {};
  if (d.topics) {
    scTopics = d.topics;
    scActive.clear();
    scRender();
  }
});

// Relay filter_changed → chat highlighting
window.addEventListener('smart_context.filter_changed', function(e) {
  window.dispatchEvent(new CustomEvent('smart_context.highlight_request', {
    detail: e.detail || {}
  }));
});
</script>
</body>
</html>
```

**Step 4: Run tests**

Run: `pixi run pytest sidecar/tests/test_plugin_smart_context.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add example-vault/plugins/smart_context/panel.html sidecar/tests/test_plugin_smart_context.py
git commit -m "feat: smart_context bubble cloud panel HTML/JS"
```

---

### Task 8: Chat Message Highlighting (Frontend)

**Files:**
- Modify: `src/vault/chat/chat.js`
- Modify the main CSS file (find it under `src/` — check for `style.css` or `index.css`)

**Step 1: Locate the CSS file**

Run: `find src -name "*.css" | head -5`

Open the file and add the highlight class:

```css
/* Smart Context — active filter highlight */
.sc-highlight {
    border-left: 3px solid rgba(99, 179, 237, 0.7) !important;
    background: rgba(99, 179, 237, 0.05) !important;
    transition: background 0.2s, border-left 0.2s;
}
```

**Step 2: Add listeners to `chat.js`**

Open `src/vault/chat/chat.js`. Find the `initChatGlobals` function (or the block that sets up `window.addEventListener` calls). Add after existing listeners:

```javascript
// Smart Context: highlight messages included in current filter
window.addEventListener('smart_context.highlight_applied', function(e) {
    var messageIds = (e.detail && e.detail.message_ids) ? e.detail.message_ids : [];

    // Remove all existing highlights
    document.querySelectorAll('[data-message-id].sc-highlight')
        .forEach(function(el) { el.classList.remove('sc-highlight'); });

    // Apply to matching elements
    messageIds.forEach(function(id) {
        var el = document.querySelector('[data-message-id="' + id + '"]');
        if (el) el.classList.add('sc-highlight');
    });
});

// Clear all highlights when filter is cleared
window.addEventListener('smart_context.filter_changed', function(e) {
    var active = (e.detail && e.detail.active_topics) ? e.detail.active_topics : [];
    if (active.length === 0) {
        document.querySelectorAll('[data-message-id].sc-highlight')
            .forEach(function(el) { el.classList.remove('sc-highlight'); });
    }
});
```

**Step 3: Verify with manual test**

Start the sidecar:
```bash
pixi run sidecar --vault example-vault --ws-port 9001 --verbose
```

Open the UI, send a few messages on different topics, then click a topic bubble. Messages in the chat matching the filter should get a left-border highlight. Messages not matching should be unhighlighted.

**Step 4: Commit**

```bash
git add src/vault/chat/chat.js src/
git commit -m "feat: chat message highlighting for smart_context filter"
```

---

### Task 9: Update `.vault.toml` and Run All Tests

**Files:**
- Modify: `example-vault/.vault.toml` (confirm smart_context is enabled with defaults)

**Step 1: Confirm vault config**

The `[plugins.smart_context]` section should already exist (from before). Verify it reads:

```toml
[plugins.smart_context]
enabled = true
```

Optionally add defaults explicitly:

```toml
[plugins.smart_context]
enabled = true
similarity_threshold = 0.4
embedding_search = true
```

**Step 2: Run full test suite**

Run: `pixi run test`
Expected: All sidecar tests PASS, no regressions

**Step 3: Run smart_context tests specifically**

Run: `pixi run pytest sidecar/tests/test_plugin_smart_context.py -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add example-vault/.vault.toml
git commit -m "chore: confirm smart_context vault config"
```

---

## Summary of New Files

| File | Purpose |
|------|---------|
| `example-vault/plugins/smart_context/main.py` | Plugin: full implementation |
| `example-vault/plugins/smart_context/panel.html` | Bubble cloud UI |
| `example-vault/plugins/smart_context/embedding_cache.py` | Embedding cache |
| `sidecar/tests/test_plugin_smart_context.py` | Tests (replace existing stub tests) |

## Modified Files

| File | Change |
|------|--------|
| `sidecar/services/llm_service.py` | Add `embed()` method |
| `sidecar/tests/test_llm_service.py` | Add embed test |
| `src/vault/chat/chat.js` | Add highlight listeners |
| `src/` (CSS file) | Add `.sc-highlight` class |
| `example-vault/.vault.toml` | Confirm plugin config |
