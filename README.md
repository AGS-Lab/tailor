<div align="center">

#  Tailor

### The AI assistant that fits *you*.

**Build your own AI workspace with plugins, any model, and complete control.**

[Getting Started](#-getting-started) · [Plugins](#-plugins) · [Architecture](#-architecture) · [Contributing](#-contributing)


</div> 

> **🚧 Work in Progress:** Tailor is in active, early-stage development. The codebase is changing rapidly and feature implementation is ongoing. We welcome your ideas, feedback, and pull requests to help shape the future of modular AI!

## 🧠 What is Tailor?

Tailor is an **open-source desktop framework** for building personal AI assistants. Instead of one-size-fits-all chatbots, Tailor lets you assemble a workspace from plugins, models, and tools — all running locally on your machine.

**Core ideas:**

- **Vaults** — Each workspace is a self-contained folder. Open multiple vaults, each with its own plugins, models, and conversations. Nothing bleeds between them.
- **Plugins** — Small Python scripts that extend everything. Add UI panels, inject context, call APIs, process responses, or give the LLM new tools. The plugin system *is* the product.
- **Any model** — Use OpenAI, Gemini, Claude, Ollama, or any LiteLLM-supported provider. Assign different models to different tasks (thinking, fast, vision, code, embedding).
- **Local-first** — Your data stays on your machine. No cloud accounts required. Configs are TOML, settings are JSON — everything is readable and portable.

<br>

## ✨ Features

<table>
<tr>
<td width="50%">

### 🔌 Plugin Ecosystem
Four types of plugins that can be mixed freely:
- **User-callable** — buttons in toolbars, sidebars or golden-layout panels
- **LLM-callable** — tools the AI can use autonomously
- **Pipeline** — automatic hooks on every message
- **Hybrid** — any combination of the above

</td>
<td width="50%">

### 🤖 Model Agnostic
Works with every major LLM provider:
- OpenAI (GPT-4o, GPT-4, GPT-3.5)
- Google (Gemini Pro, Gemini Flash)
- Anthropic (Claude 3.5, Claude 3)
- Ollama (Llama, Mistral, any local model)
- Any LiteLLM-compatible provider

</td>
</tr>
<tr>
<td width="50%">

### 🏗️ Vault Isolation
Each vault runs its own process:
- Separate plugins, settings, and state
- Crash-contained — one vault can't affect another
- Portable — share vault folders with anyone
- Multi-window — use different vaults side by side

</td>
<td width="50%">

### 📊 Pipeline Visualization
See your AI's brain in real time:
- LangGraph pipeline rendered as interactive Mermaid diagrams
- View registered tools and their metadata
- Understand exactly how your assistant processes each message

</td>
</tr>
</table>

<br>

## 🚀 Getting Started

### Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| **Pixi** | Manages Python, Node.js, and Rust environments | [prefix.dev](https://prefix.dev/) |
| **Rust** | Required for the Tauri desktop shell | [rustup.rs](https://rustup.rs/) |

### Install & Run

```bash
# Clone
git clone https://github.com/AGS-Lab/tailor.git
cd tailor

# Install everything (Python, Node.js, Rust deps — all automatic)
pixi install

# Launch
pixi run dev
```

### Open Your First Vault

1. Click **Open Vault** in the launcher
2. Select the included `example-vault/` folder
3. Start chatting — plugins load automatically

That's it. Your AI workspace is running. 🎉

<br>

## 🧩 Plugins

Plugins are the heart of Tailor. Everything beyond the core chat is a plugin.

### Included Plugins

| Plugin | Type | What it does |
|--------|------|-------------|
| **Summarizer** | User-callable | One-click TL;DR of long AI responses |
| **Prompt Refiner** | Hybrid | Refines your prompts before sending (manual or auto) |
| **Smart Context** | Hybrid | Topic extraction + embedding-based context filtering |
| **Explorer** | User-callable | ChatGPT-style chat history sidebar |
| **Memory** | Pipeline | Auto-saves conversations to disk |
| **Chat Branches** | User-callable | Fork conversations to explore different paths |

### Write Your Own (It's Simple)

```python
# plugins/greeter/main.py
from sidecar.api.plugin_base import PluginBase

class Plugin(PluginBase):
    """A greeting plugin in 15 lines."""

    def register_commands(self):
        self.brain.register_command("greeter.hello", self.hello, self.name)

    async def hello(self, name="World", **kwargs):
        self.notify(f"Hello, {name}! 👋", severity="success")
        return {"status": "success", "message": f"Hello, {name}!"}
```

### Make Tools the LLM Can Call

```python
from sidecar.decorators import tool

@tool(name="search_web", category="information",
      description="Search the web for current information")
def search_web(query: str) -> str:
    """The LLM will call this autonomously when it needs web data."""
    return fetch_results(query)
```

> 📖 **Full guide:** [Plugin Development Guide](docs/PLUGIN_GUIDE.md) · [Plugin Architecture](docs/system/PLUGIN-ARCHITECTURE.md)

<br>

## 🏛️ Architecture

Three processes, communicating over WebSocket (JSON-RPC 2.0):

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Vite/JS)                    │
│          Chat UI · Panels · Toolbars · Plugin UIs       │
├─────────────────────────────────────────────────────────┤
│                   Rust/Tauri Backend                     │
│        Window management · Process orchestration        │
├─────────────────────────────────────────────────────────┤
│              Python Sidecar (per vault)                  │
│   Plugins · LLM Pipeline · Tool Registry · Commands     │
└─────────────────────────────────────────────────────────┘
              ↕ WebSocket (JSON-RPC 2.0) ↕
```

**Why this design?**
- **Vault isolation**: Each vault gets its own Python process. No shared state. Crash containment.
- **Language best-of-breed**: Rust for performance + system access, Python for AI/ML ecosystem, JS for UI.
- **Plugin safety**: Plugins run in their own process, can't crash the desktop shell.

> 📖 **Deep dive:** [Architecture](docs/system/ARCHITECTURE.md) · [Vision](docs/system/VISION.md)

<br>

## 🗂️ Project Structure

```
tailor/
├── src/                    Frontend (Vanilla JS + Vite)
│   ├── vault/              Vault window UI (chat, layout, panels)
│   ├── pages/              Dashboard pages (settings, themes, vault config)
│   └── services/           Tauri IPC wrappers
├── src-tauri/src/          Rust backend
│   ├── sidecar_manager.rs  Python process lifecycle
│   ├── window_manager.rs   Window tracking
│   ├── ipc_router.rs       Tauri command handlers
│   └── event_bus.rs        Event routing
├── sidecar/                Python sidecar
│   ├── vault_brain.py      Singleton orchestrator
│   ├── pipeline/           LangGraph pipeline + Tool Registry
│   ├── api/                Plugin base class
│   ├── services/           LLM, keyring, memory
│   └── decorators.py       @command, @tool, @on_event
├── example-vault/          Working example with 9 plugins
│   ├── .vault.toml         Vault configuration
│   └── plugins/            Plugin collection
└── docs/                   Documentation
    ├── system/             Architecture, vision, plugin taxonomy
    └── plans/              Implementation plans and TODOs
```

<br>

## 🧪 Development

```bash
pixi run dev              # Start dev server + Tauri window
pixi run test             # Run Python tests
pixi run test-rust        # Run Rust tests
pixi run lint             # Check Python with ruff
pixi run format           # Format Python with ruff
pixi run build            # Production build
```

Run a single test:
```bash
pixi run pytest sidecar/tests/test_vault_brain.py::test_function_name
```

<br>

## 📚 Documentation

| Document | What it covers |
|----------|---------------|
| [**Plugin Guide**](docs/PLUGIN_GUIDE.md) | Building plugins — commands, tools, lifecycle, UI |
| [**Plugin Architecture**](docs/system/PLUGIN-ARCHITECTURE.md) | Plugin type taxonomy, UI locations, hybrid patterns |
| [**Architecture**](docs/system/ARCHITECTURE.md) | Full technical architecture of all three layers |
| [**Vision**](docs/system/VISION.md) | Core principles, settled decisions, project direction |
| [**Plugin Commands**](docs/PLUGIN_COMMANDS.md) | Command registry pattern and examples |
| [**FAQ**](docs/FAQ.md) | Common questions answered simply |
| [**Setup Guide**](docs/SETUP.md) | Detailed installation instructions |
| [**UI Style Guide**](docs/UI_STYLE_GUIDE.md) | Design guidelines for plugin UIs |
| [**Contributing**](docs/CONTRIBUTING.md) | How to contribute |

<br>

## 🤝 Contributing

We are actively looking for contributors! Whether you want to build a new plugin, fix a bug, or improve the core framework, Tailor is a great place to hack on AI tooling.

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Write your code and verify with `pixi run test`
4. Submit a Pull Request

Not sure where to start? Check the [Issue tracker](https://github.com/AGS-Lab/tailor/issues) or read our [Contributing Guide](docs/CONTRIBUTING.md).

<br>

## ⚖️ License

MIT — see [LICENSE](LICENSE) for details.

<br>

---

<div align="center">

**Tailor** — *Your AI, your rules.*

Built with [Tauri](https://tauri.app/) · [LangGraph](https://github.com/langchain-ai/langgraph) · [LiteLLM](https://github.com/BerriAI/litellm) · [Pixi](https://prefix.dev/)

</div>
