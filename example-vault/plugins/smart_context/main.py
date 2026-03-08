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
- If existing topics are provided, REUSE their exact labels whenever a new topic
  is the same or very similar concept. Only introduce a new label when the topic
  is genuinely distinct.
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
        self._background_tasks: Set[asyncio.Task] = set()
        # Accumulated topic set — built incrementally, one exchange at a time
        self._current_topics: List[Dict[str, Any]] = []

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
            "<div style='padding:10px'><p>Waiting for context\u2026</p></div>"
        await self.set_panel_content(panel_id=self.panel_id, html_content=html)

        # Re-emit accumulated topics so the panel is populated on reconnect
        if self._current_topics and self.current_chat_id:
            self.emit("smart_context.topics_updated", {
                "chat_id": self.current_chat_id,
                "topics": self._current_topics,
                "total_messages": 0,
            })

    async def on_unload(self) -> None:
        await self.remove_panel(self.panel_id)
        await super().on_unload()

    # =========================================================================
    # Pipeline Subscribers
    # =========================================================================

    async def _on_pipeline_output(self, ctx: PipelineContext) -> None:
        """After each LLM response: incrementally extract topics in background."""
        if not ctx.response:
            return
        chat_id = ctx.metadata.get("chat_id")
        if not chat_id:
            return
        task = asyncio.create_task(self._run_topic_extraction(chat_id))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _extract_topics(
        self,
        messages: List[Dict[str, Any]],
        existing_topics: List[Dict[str, Any]] | None = None,
    ) -> List[Dict[str, Any]]:
        """Call LLM to extract topics and identify sticky messages."""
        from sidecar.services.llm_service import get_llm_service

        conversation = "\n".join(
            f"[{m.get('id', '?')}] {m.get('role', 'user')}: "
            f"{str(m.get('content', ''))[:200]}"
            for m in messages
        )

        if existing_topics:
            regular = [t for t in existing_topics if not t.get("sticky")]
            labels = ", ".join(f'"{t["label"]}"' for t in regular)
            user_content = f"Existing topics: {labels}\n\nConversation:\n{conversation}"
        else:
            user_content = conversation

        llm_messages = [
            {"role": "system", "content": TOPIC_EXTRACTION_PROMPT},
            {"role": "user", "content": user_content},
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
            raw = raw.strip()  # remove any leftover whitespace/newlines after fence removal

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

    async def _run_topic_extraction(self, chat_id: str) -> None:
        """Incrementally extract topics from the latest exchange and merge into running set."""
        try:
            result = await self.brain.execute_command("memory.load_chat", chat_id=chat_id)
            if result.get("status") != "success":
                return
            data = result.get("data", {})
            messages = data.get("messages", [])
            if not messages:
                return

            # Only analyse the latest exchange (last 2 messages: user + assistant)
            latest = messages[-2:] if len(messages) >= 2 else messages
            new_topics = await self._extract_topics(latest, existing_topics=self._current_topics)

            # Merge into running accumulation — topics grow over time, never fully reset
            if chat_id != self.current_chat_id:
                # New chat: seed from whatever is already saved
                self._current_topics = list(data.get("topics", []))
            self._current_topics = self._merge_topics(self._current_topics, new_topics)

            data["topics"] = self._current_topics
            await self.brain.execute_command("memory.save_chat", chat_id=chat_id, data=data)

            self.current_chat_id = chat_id
            self.emit("smart_context.topics_updated", {
                "chat_id": chat_id,
                "topics": self._current_topics,
                "total_messages": len(messages),
            })
            self.logger.info(f"Topics for {chat_id}: {[t['label'] for t in self._current_topics]}")
        except Exception as e:
            self.logger.error(f"Topic extraction failed for {chat_id}: {e}")

    def _merge_topics(
        self, existing: List[Dict[str, Any]], new: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Merge newly extracted topics into the existing accumulated set.

        Regular topics: union by label; count increments on each re-mention.
        Sticky topic: replaced by the latest extraction's sticky entry.
        """
        regular = {t["label"]: dict(t) for t in existing if not t.get("sticky")}
        for t in new:
            if t.get("sticky"):
                continue
            if t["label"] in regular:
                regular[t["label"]]["count"] += 1
            else:
                regular[t["label"]] = dict(t)

        # Sticky: use the latest extraction's sticky entry if present, else keep existing
        new_sticky = next((t for t in new if t.get("sticky")), None)
        old_sticky = next((t for t in existing if t.get("sticky")), None)
        sticky = [new_sticky or old_sticky] if (new_sticky or old_sticky) else []

        return list(regular.values()) + sticky

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
        need_embed: List[Dict[str, Any]] = []
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
            cache.save()  # flush all new embeddings in one write

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

    # =========================================================================
    # Commands
    # =========================================================================

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
            task = asyncio.create_task(self._emit_highlight_ids(self.current_chat_id))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

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
