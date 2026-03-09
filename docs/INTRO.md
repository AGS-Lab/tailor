# Welcome to Tailor

> Your personal, modular AI assistant — built to fit the way *you* work.

## What is Tailor?

Tailor is a **desktop AI assistant** that you can customize with plugins, models, and tools. Think of it like Obsidian, but instead of notes, you're building your own AI workspace.

The core idea is simple:

1. **You create a "vault"** — a regular folder on your computer.
2. **You add plugins** — small Python scripts that give your assistant new abilities.
3. **You pick your AI models** — local (Ollama) or cloud (OpenAI, Anthropic, etc.).
4. **Tailor stitches it all together** into an assistant that works exactly the way you want.

No cloud accounts required. No lock-in. Everything stays on your machine.

---

## Key Concepts

### 🗂️ Vaults

A vault is just a folder on your computer. Each vault is completely independent — it has its own plugins, settings, conversation history, and AI model configuration.

You can have multiple vaults open at once, each in its own window, doing completely different things. They don't interfere with each other.

**What's inside a vault:**

```
my-vault/
├── .vault.toml          ← Your vault's settings (models, plugins, etc.)
├── plugins/             ← Your plugins live here
│   ├── summarizer/
│   │   └── main.py
│   └── memory/
│       └── main.py
├── .memory/             ← Conversation history (auto-managed)
└── lib/                 ← Plugin dependencies (auto-managed)
```

### 🧩 Plugins

Plugins are the heart of Tailor. They're self-contained Python scripts that extend what your assistant can do. Some examples of what plugins can do:

- **Summarizer** — Automatically summarize long AI responses
- **Memory** — Remember important things across conversations
- **Explorer** — Browse and search files in your vault
- **Smart Context** — Intelligently pull relevant context from past conversations
- **Chat Branches** — Fork conversations to explore different directions

Plugins can:
- Add buttons and panels to the UI
- Run background tasks
- Talk to each other
- Connect to external services
- Process and transform AI responses

### 🤖 Models

Tailor is **model-agnostic**. You choose which AI models to use, and you can assign different models to different tasks:

| Category | What it's for | Example |
|----------|---------------|---------|
| **Thinking** | Complex reasoning, planning | GPT-4, Claude 3.5 |
| **Fast** | Quick responses, simple tasks | GPT-3.5, Llama 3 |
| **Vision** | Understanding images | GPT-4o, LLaVA |
| **Code** | Writing and reviewing code | GPT-4o, CodeLlama |
| **Embedding** | Semantic search, similarity | text-embedding-3 |

All model configuration lives in your vault's `.vault.toml` file — a simple, human-readable config file.

---

## Getting Started

### Step 1: Install Prerequisites

You need two things installed:

- **[Pixi](https://prefix.dev/)** — Manages all project dependencies (Python, Node.js, Rust) in one tool
- **[Rust](https://rustup.rs/)** — Required to build the desktop app

**On Windows (PowerShell):**
```powershell
# Install Pixi
iwr -useb https://pixi.sh/install.ps1 | iex

# Install Rust
winget install Rustlang.Rustup
```

### Step 2: Install Tailor

```bash
# Clone the repository
git clone https://github.com/ARC345/tailor.git
cd tailor

# Install all dependencies (Python, Node.js, Rust — all handled automatically)
pixi install
```

### Step 3: Launch Tailor

```bash
pixi run dev
```

This starts Tailor in development mode. The app window will open automatically.

### Step 4: Open a Vault

1. Click **"Open Vault"** in the launcher
2. Select the `example-vault` folder (included in the repo) to try it out
3. A new window opens with your AI workspace ready to go

That's it! You're up and running. 🎉

---

## Creating Your First Vault

Ready to create your own workspace? Here's how:

### 1. Create a folder

Create a new folder anywhere on your computer — say `my-workspace/`.

### 2. Add a `.vault.toml` file

Create a file called `.vault.toml` in your folder with your settings:

```toml
version = "1.0.0"
name = "My Workspace"
description = "My personal AI workspace"

[llm.providers.ollama]
base_url = "http://localhost:11434"

[llm.categories]
thinking = "gpt-3.5-turbo"
fast = "gpt-3.5-turbo"
code = "openai/gpt-4o"

[llm.defaults]
temperature = 0.7
max_tokens = 4096
```

### 3. Add plugins

Create a `plugins/` folder and drop in any plugins you want to use. Each plugin is its own subfolder with a `main.py` file.

### 4. Open in Tailor

Click "Open Vault" and select your new folder. Tailor will:
- Auto-install any plugin dependencies
- Load all enabled plugins  
- Start an isolated background process for your vault
- Connect everything together

---

## Writing Your First Plugin

Plugins are surprisingly simple. Here's a complete plugin in under 20 lines:

```python
# plugins/greeter/main.py
from api.plugin_base import PluginBase

class Plugin(PluginBase):
    """A simple greeting plugin."""
    
    def __init__(self, emitter, brain, plugin_dir, vault_path):
        super().__init__(emitter, brain, plugin_dir, vault_path)
        self.register_commands()
        self.logger.info("Greeter plugin ready!")
    
    def register_commands(self):
        self.brain.register_command("greeter.hello", self.say_hello, self.name)
    
    async def say_hello(self, name="World", **kwargs):
        message = f"Hello, {name}! 👋"
        self.emitter.notify(message, severity="success")
        return {"status": "ok", "message": message}
```

**What this does:**
- Registers a command called `greeter.hello`
- When called, it sends a greeting notification to the UI
- Other plugins can also call this command

See the full [Plugin Development Guide](PLUGIN_GUIDE.md) for more advanced features like background tasks, UI injection, settings management, and plugin-to-plugin communication.

---

## How Tailor Works (The Big Picture)

Tailor has three layers that work together:

```
┌──────────────────────────────────────────┐
│         Your Browser Window (UI)          │
│   Chat interface, panels, plugin UIs      │
├──────────────────────────────────────────┤
│         Rust/Tauri Backend                │
│   Window management, event routing        │
├──────────────────────────────────────────┤
│         Python Sidecar (per vault)        │
│   Plugins, AI models, command registry    │
└──────────────────────────────────────────┘
        ↕ WebSocket (JSON-RPC 2.0) ↕
```

- The **frontend** is what you see — the chat window, toolbars, and panels.
- The **Rust backend** manages windows and routes messages between the UI and Python.
- The **Python sidecar** is where the action happens — it loads your plugins, manages AI models, and processes your requests.

Each vault gets its own Python process, so they're completely isolated from each other.

---

## What's Next?

- 📖 **[Plugin Guide](PLUGIN_GUIDE.md)** — Deep dive into building plugins
- 🏗️ **[Architecture](ARCHITECTURE.md)** — Understand the full technical design
- ⚙️ **[Setup Guide](SETUP.md)** — Detailed installation instructions
- 🎨 **[UI Style Guide](UI_STYLE_GUIDE.md)** — Design guidelines for plugin UIs
- 🤝 **[Contributing](CONTRIBUTING.md)** — How to contribute to Tailor
