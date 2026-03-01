# Smart Context Plugin Design

**Date:** 2026-03-01
**Status:** Approved

## Overview

The Smart Context plugin gives users a visual map of the topics discussed in the current chat session. Topics are rendered as a sized bubble cloud in a dedicated panel. Clicking topic bubbles toggles a semantic filter that controls which messages are injected into the LLM pipeline as history. Short instructional messages (e.g. "be concise") are identified automatically and always injected regardless of filter state.

## Architecture

Four logical parts:

1. **Topic extractor** — subscribes to `pipeline.output`. After each assistant response, fires an async background LLM call (fast model) that reads the full conversation and returns a topic list. Writes the result back to the chat file via `memory.save_chat`.

2. **Panel UI** — registers the Smart Context panel on `on_client_connected`. Renders an HTML+JS bubble cloud. Listens for `smart_context.topics_updated` to re-render after extraction. Has an on/off toggle for similarity mode.

3. **Filter state** — the plugin holds `self.active_topics: set[str]` and `self.current_chat_id: str` in memory. `smart_context.set_filter` updates this and emits `smart_context.filter_changed` so the main chat view can apply/remove message highlights.

4. **Context injector** — subscribes to `pipeline.context`. Always injects sticky messages. If `embedding_search` is enabled and `active_topics` is non-empty, replaces `ctx.history` with only semantically relevant messages (cosine similarity ≥ threshold). If nothing clears the threshold, falls back to full history.

## Data Schema

Topics are stored as a flat list on the chat file (`.memory/{chat_id}.json`), not on individual messages:

```json
{
  "messages": [...],
  "topics": [
    {"label": "LangGraph", "count": 4},
    {"label": "Python Async", "count": 2},
    {"label": "Debugging", "count": 1},
    {"label": "Instructions & Preferences", "sticky": true, "message_ids": ["a1b2", "c3d4"]}
  ]
}
```

- Regular topics store only `label` and `count`. Message relevance is resolved at query time via vector embeddings.
- The sticky topic (`"sticky": true`) stores explicit `message_ids` because short instructional messages have no reliable embedding similarity to content topics. The LLM extraction prompt identifies and flags these explicitly.
- Topics are **fully regenerated** on each extraction (not appended), so stale topics from early in the conversation are pruned as the chat evolves.
- LLM extraction targets 3–8 topics per conversation.

## Embedding Cache

To avoid re-embedding messages on every filter interaction, embeddings are cached in a sidecar file:

```
.memory/{chat_id}.embeddings.json
```

Keyed by `{message_id}:{content_hash}`. When filtering is applied, only messages without a cached embedding are re-embedded. The vault's configured `embedding` model category is used.

## Context Injection Logic

When `pipeline.context` fires:

1. Always collect sticky messages (by stored `message_ids`).
2. If `embedding_search` is disabled or `active_topics` is empty → pass full `ctx.history` (plus sticky, deduplicated).
3. If `embedding_search` is enabled and topics are selected:
   - Embed each selected topic label.
   - Score each message by max cosine similarity across selected topics.
   - Collect messages with similarity ≥ `similarity_threshold`.
   - If no messages clear the threshold → fall back to full history.
   - Merge with sticky messages, deduplicate, restore chronological order.
   - Replace `ctx.history` with the result.

## Panel UI

- **Bubble cloud**: topic bubbles sized proportionally by `count`. Selected bubbles glow; unselected dim to ~40% opacity.
- **Sticky section**: "Instructions & Preferences" shown as a permanently-on locked indicator above the bubble cloud, not a toggleable bubble.
- **Status line**: `"5 of 14 messages in context"` below the cloud. Reads `"All messages in context"` when no filter is active.
- **Similarity mode toggle**: on/off switch in the panel. When off, bubbles are non-interactive (visualization only).
- **Re-render trigger**: panel JS listens for `smart_context.topics_updated` event to refresh the bubble cloud after a new extraction completes.

## Chat Highlighting

- When `smart_context.filter_changed` is emitted, the panel JS dispatches a `CustomEvent` on `document` with the set of included message IDs.
- The main chat JS listens for this event and applies/removes a highlight class (e.g. colored left-border) to message elements matching those IDs.
- Requires message elements in the main chat view to carry `data-message-id` attributes.

## Commands Registered

| Command | Description |
|---|---|
| `smart_context.set_filter` | Set active topic labels (array). Empty array clears filter. |
| `smart_context.get_topics` | Return current topics for the active chat. |
| `smart_context.set_similarity_mode` | Enable or disable embedding search. |

## Vault Configuration (`.vault.toml`)

```toml
[plugins.smart_context]
enabled = true
similarity_threshold = 0.4   # minimum cosine similarity to include a message
embedding_search = true       # set to false to disable context filtering
```

## Pipeline Hook Summary

| Phase | Action |
|---|---|
| `pipeline.output` | Trigger async topic extraction via fast LLM. Write to chat file. |
| `pipeline.context` | Inject filtered history (embedding search) + always inject sticky messages. |

## Dependencies

- `memory` plugin — `memory.load_chat` and `memory.save_chat` for reading/writing topics.
- `sidecar.services.llm_service` — fast model for topic extraction, embedding model for similarity search.
- Main chat frontend must expose `data-message-id` on message DOM elements for highlighting.
