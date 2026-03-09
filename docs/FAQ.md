# Frequently Asked Questions

---

## General

### What is Tailor?

Tailor is a **modular AI assistant desktop app**. It lets you create customizable AI workspaces called "vaults," each with its own plugins, models, and settings. Think of it as Obsidian, but for AI workflows instead of notes.

### Is Tailor free?

Yes. Tailor is open-source under the MIT license. However, if you use cloud AI models (like OpenAI or Anthropic), those providers may charge separately for API usage.

### Does Tailor require an internet connection?

Not necessarily. If you use **local models** (e.g., via [Ollama](https://ollama.ai)), Tailor works entirely offline. You only need internet if you're calling cloud-based AI providers.

### What operating systems does Tailor support?

Tailor is built with Tauri, which supports **Windows**, **macOS**, and **Linux**. Development is currently focused on Windows, but cross-platform support is a core goal.

### Is my data sent to the cloud?

Only if you choose to use a cloud AI provider (like OpenAI). All your vault data, conversation history, and plugin settings stay **on your local machine**. Tailor never phones home.

---

## Vaults

### What is a vault?

A vault is simply a **folder on your computer** that Tailor uses as a workspace. It contains your plugins, AI model configuration, conversation history, and settings — all in one self-contained directory.

### Can I have multiple vaults open at the same time?

Yes! Each vault opens in its own window and runs its own isolated Python process. They don't share any state, so you can have completely different setups running simultaneously.

### Can I share a vault with someone else?

Absolutely. A vault is just a folder of files. You can zip it up, put it on a USB drive, or push it to a Git repo. Just be careful not to share sensitive data like API keys (those are stored in your vault's `.vault.toml` file).

### Where is my conversation history stored?

In the `.memory/` folder inside your vault. It's stored as local files — no databases, no cloud sync. You can back it up, move it, or delete it at any time.

### What is `.vault.toml`?

It's your vault's configuration file, written in [TOML format](https://toml.io/) (similar to INI files, but better). It defines:
- Which AI models to use
- Which plugins are enabled
- Plugin-specific settings
- LLM provider configuration (API URLs, etc.)

You can edit it with any text editor.

**Example:**
```toml
version = "1.0.0"
name = "My Workspace"

[llm.categories]
thinking = "gpt-3.5-turbo"
fast = "gpt-3.5-turbo"

[plugins.summarizer]
enabled = true

[plugins.memory]
enabled = true
```

---

## Plugins

### What are plugins?

Plugins are small Python scripts that extend Tailor's capabilities. Each plugin lives in its own folder inside your vault's `plugins/` directory. They can add new features, connect to services, process AI responses, add UI elements, and more.

### How do I install a plugin?

Drop the plugin folder into your vault's `plugins/` directory. That's it. Tailor will automatically detect and load it the next time you open the vault.

```
my-vault/
└── plugins/
    └── my_new_plugin/     ← Just put the folder here
        └── main.py
```

### How do I enable or disable a plugin?

Add an entry to your `.vault.toml`:

```toml
[plugins.my_plugin]
enabled = true    # or false to disable
```

### Can plugins talk to each other?

Yes! Tailor uses a **command registry** (similar to VSCode). Plugins register commands that any other plugin can call:

```python
# Plugin A registers a command
self.brain.register_command("cache.get", self.get_cached, self.name)

# Plugin B calls it
result = await self.brain.execute_command("cache.get", key="users")
```

Plugins don't need to know about each other directly — they communicate through the command registry.

### Can plugins add buttons and UI elements?

Yes. Plugins can inject HTML, CSS, and JavaScript into the frontend dynamically. They can add toolbar buttons, panels, modals, and custom UI components. See the [Plugin UI Injection Guide](plugin-ui-injection.md) for details.

### Do plugins need external dependencies?

They can. If a plugin needs Python packages, add a `requirements.txt` file to the vault's `plugins/` directory. Tailor automatically installs them to an isolated `lib/` folder when you open the vault.

### Can a plugin crash my whole app?

No. Each plugin runs in isolation. If one plugin throws an error, it won't affect other plugins or the main application. Errors are caught and logged.

---

## AI Models

### Which AI models does Tailor support?

Tailor uses **LiteLLM** under the hood, which supports 100+ LLM providers including:
- **OpenAI** (GPT-4, GPT-3.5, etc.)
- **Anthropic** (Claude 3, Claude 3.5)
- **Ollama** (Llama, Mistral, CodeLlama — run locally)
- **Google** (Gemini)
- **And many more**

### How do I use local models (Ollama)?

1. Install [Ollama](https://ollama.ai) and pull a model (e.g., `ollama pull llama3`)
2. In your `.vault.toml`, configure the provider:

```toml
[llm.providers.ollama]
base_url = "http://localhost:11434"

[llm.categories]
fast = "ollama/llama3"
thinking = "ollama/llama3"
```

### What are model categories?

Instead of picking one model for everything, Tailor lets you assign different models to different tasks:

| Category | Best for |
|----------|----------|
| **thinking** | Complex reasoning, planning, analysis |
| **fast** | Quick answers, simple tasks, chat |
| **vision** | Understanding images and screenshots |
| **code** | Writing, reviewing, and debugging code |
| **embedding** | Semantic search, finding similar content |

This way, you can use a fast cheap model for simple questions and a powerful expensive model only when you need deep reasoning.

### Where do I put my API keys?

In your `.vault.toml` file. For OpenAI, you can also set the `OPENAI_API_KEY` environment variable. LiteLLM supports standard environment variables for most providers.

---

## Technical

### What tech stack does Tailor use?

| Layer | Technology |
|-------|-----------|
| Desktop shell | **Tauri 2** (Rust) |
| Frontend | **Vanilla JavaScript** + Vite |
| Backend logic | **Python 3.12+** (asyncio) |
| Communication | **WebSocket** (JSON-RPC 2.0) |
| AI Orchestration | **LangGraph** + **LiteLLM** |
| Environment | **Pixi** (manages Python, Node.js, Rust) |

### Why Python for plugins?

Python is the language of AI and machine learning. Most AI libraries, model frameworks, and data tools are Python-first. By using Python for plugins, you get access to the entire AI ecosystem — LangChain, Hugging Face, scikit-learn, and everything else.

### Why not Electron?

Tauri uses Rust instead of Node.js for the backend, resulting in **smaller binaries** (~10MB vs ~150MB), **less memory usage**, and **better performance**. It uses the system's built-in web view instead of bundling Chromium.

### How do the frontend and backend communicate?

Via **WebSocket** using the **JSON-RPC 2.0** protocol. The Rust backend acts as a bridge between the JavaScript frontend and the Python sidecar. Messages are standard JSON — easy to inspect, debug, and extend.

### Is there hot reload for plugins?

Not yet, but it's on the roadmap. Currently, you need to restart the vault (close and reopen it) to reload plugins. The tick loop (which runs every 5 seconds) does allow plugins to update their state dynamically.

---

## Troubleshooting

### The app won't start — "Rust not found"

Make sure Rust is installed and available in your PATH:
```powershell
cargo --version
```
If the command isn't found, install Rust from [rustup.rs](https://rustup.rs/) and restart your terminal.

### The sidecar won't start — "Python not found"

Tailor uses Pixi to manage Python. Make sure you've run:
```bash
pixi install
```
If issues persist, verify Python is accessible:
```bash
python --version    # Should show 3.12+
```

### My plugin isn't loading

Check these common issues:
1. **File structure** — The plugin must be a folder with a `main.py` file inside `plugins/`
2. **Class name** — The file must contain a class called `Plugin`
3. **Inheritance** — The class must inherit from `PluginBase`
4. **Enabled** — Make sure it's not disabled in `.vault.toml`
5. **Logs** — Run with verbose logging to see the error:
   ```bash
   pixi run sidecar --vault my-vault --ws-port 9001 --verbose
   ```

### Events aren't showing up in the UI

- Verify the WebSocket connection is active (check the browser console)
- Check that the event scope is correct (`window`, `vault`, or `global`)
- Make sure the frontend is listening for the right event type

### Port conflict — "Address already in use"

Tailor allocates WebSocket ports starting at 9000. If another application is using that port:
1. Close the conflicting application, or
2. The sidecar will automatically try the next available port

---

## Development

### How do I run tests?

```bash
# Python (sidecar) tests
pixi run test

# Frontend tests
npm run test

# Rust tests
pixi run test-rust
```

### How do I lint and format code?

```bash
# Check for issues
pixi run lint

# Auto-format
pixi run format
```

### How do I contribute?

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests (`pixi run test`)
5. Submit a Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) for full guidelines.

---

## Still have questions?

- 📖 Read the [Plugin Development Guide](PLUGIN_GUIDE.md)
- 🏗️ Explore the [Architecture docs](ARCHITECTURE.md)
- 🐛 File an issue on [GitHub](https://github.com/ARC345/tailor/issues)
