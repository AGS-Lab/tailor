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
        """Store an embedding. Call save() to persist."""
        self._data[self._key(message_id, content)] = embedding

    def save(self) -> None:
        """Flush all cached embeddings to disk."""
        self._save()
