# Tailor — Vision & Direction

## What Tailor Is

Tailor is a **modular AI assistant desktop framework** — Obsidian-level modularity applied to AI workflows. Users open vaults (project directories) and assemble a personal AI assistant from plugins, models, and tools. The framework handles orchestration; plugins define the behavior.

The closest analogy: if Obsidian is a modular note-taking tool, Tailor is a modular AI chat tool. The core app is minimal; everything interesting lives in plugins and vault configuration.

## Core Principles

**Vault isolation.** Each vault is a separate process, separate config, separate plugin state. Nothing bleeds between vaults. This is non-negotiable.

**Plugin-first.** The built-in chat interface is a convenience, not the product. The product is the plugin API. Every first-party feature should be something a plugin could also do.

**Model-agnostic.** LiteLLM provides the abstraction. Tailor doesn't care whether you're running Ollama locally or hitting OpenAI. Model categories (thinking, fast, vision, code, embedding) are configured per vault.

**No lock-in.** Vault configs are TOML files. Plugin settings are JSON. Everything is readable and editable outside the app.

## What Tailor Is Not

- Not a generic chat UI wrapper (the plugin system is the point)
- Not opinionated about which model or provider to use
- Not a cloud product — vaults are local directories

## Direction

Active development areas (as of Feb 2026):

- **Time management / scheduling** — in progress (see `pre time management commit`)
- **Model selector UX** — recently overhauled (`src/vault/chat/ModelSelector.js`)
- **Plugin store** — install/update/search flow partially implemented (`src/vault/plugin-store.js`)
- **Settings merge** — global defaults + vault overrides working, schema-driven

## Settled Decisions

These are not up for debate. Don't propose alternatives without a strong reason.

| Decision | Rationale |
|----------|-----------|
| JSON-RPC 2.0 over WebSocket | Standard protocol, easy to debug, works bidirectionally |
| One Python process per vault | Hard isolation, no shared state, crash containment |
| Ports allocated from 9000+ | Simple, predictable, no registry needed |
| TOML for vault config (`.vault.toml`) | Human-readable, structured, standard in Rust ecosystem |
| LangGraph for LLM pipelines | Stateful graph execution, supports streaming and branching |
| Pixi for environment management | Reproducible Python + Node + Rust in one tool |
| PluginBase abstract class | Forces explicit lifecycle implementation, prevents footguns |

## Update Protocol

When a design decision is made or revisited, add it to the **Settled Decisions** table above. When the project direction shifts, update the **Direction** section. Keep this file honest — remove stale direction items.
