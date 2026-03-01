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
            "<div style='padding:10px'><p>Waiting for context\u2026</p></div>"
        await self.set_panel_content(panel_id=self.panel_id, html_content=html)

    async def on_unload(self) -> None:
        await self.remove_panel(self.panel_id)
        await super().on_unload()

    # =========================================================================
    # Pipeline Subscribers (stubs — filled in Tasks 4 & 5)
    # =========================================================================

    async def _on_pipeline_output(self, ctx: PipelineContext) -> None:
        """After each LLM response: extract topics in background."""
        if not ctx.response:
            return
        chat_id = ctx.metadata.get("chat_id")
        if not chat_id:
            return
        asyncio.create_task(self._run_topic_extraction(chat_id))

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
