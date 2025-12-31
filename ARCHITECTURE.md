# Tailor Application - Complete Implementation Flow

## **Overview**

**Tailor** is a multi-window AI workspace framework built with **Rust/Tauri** (backend), **Python** (sidecar processes), and **WebSocket** communication. It allows users to open multiple independent "vaults" (project directories), each running isolated Python processes with custom plugins and AI capabilities.

---

## **Architecture Components**

### **1. Rust/Tauri Backend** (`src-tauri/`)

The Tauri application manages windows, processes, and event routing.

#### **Key Modules:**

- **`main.rs`**: Entry point that initializes three core managers:
  - `WindowManager`: Tracks vault windows
  - `SidecarManager`: Spawns/terminates Python processes
  - `EventBus`: Routes events between sidecars and UI

- **`sidecar_manager.rs`**: 
  - Spawns isolated Python processes for each vault
  - Allocates unique WebSocket ports (9000+)
  - Captures stdout/stderr for debugging
  - Terminates processes on window close

- **`event_bus.rs`**:
  - Routes events based on scope: `window` (single window), `vault` (all windows with same vault), `global` (all windows)
  - Maps windows to vault IDs for proper routing

- **`ipc_router.rs`**:
  - **`open_vault`**: Creates window → spawns sidecar → returns WebSocket port
  - **`send_to_sidecar`**: Communicates with Python via WebSocket (placeholder)
  - **`close_vault`**: Terminates sidecar → removes window

---

### **2. Python Sidecar** (`sidecar/`)

Each vault gets its own isolated Python process.

#### **`main.py`** (Entry Point)

```
CLI Args: --vault <path> --ws-port <port>
```

**Flow:**
1. Validates vault path exists
2. Adds `vault/lib/` to `PYTHONPATH` for isolated dependencies
3. Initializes `WebSocketServer` on allocated port
4. Creates `EventEmitter` for plugins
5. Initializes `VaultBrain` (orchestrator)
6. Runs WebSocket server + tick loop concurrently

#### **`websocket_server.py`**

**JSON-RPC Server** for bi-directional communication:
- **Receives**: Commands from Rust (e.g., `chat.send_message`, `execute_command`)
- **Sends**: Responses + events back to Rust
- **Handlers**: Registered by `VaultBrain` at startup

**Key Methods:**
- `register_handler(method, handler)`: Plugins register custom commands
- `send_to_rust(data)`: Queue messages to Rust (async-safe)
- `handle_message(message)`: Parse JSON-RPC → call handler → send response

#### **`event_emitter.py`**

**Plugin API** for emitting events to the UI:

```python
emitter.notify("Task complete!", severity="success")       # Window-scoped
emitter.progress(75, "Processing...")                      # Progress bar
emitter.update_state("key", value)                         # UI state
emitter.global_event("ALERT", {...})                       # All windows
emitter.vault_event("SYNC", {...})                         # Same vault
```

Each call sends JSON-RPC message via WebSocket to Rust → EventBus routes to UI.

#### **`vault_brain.py`**

**LangGraph Orchestrator** that manages vault-specific operations:

**Initialization:**
1. Loads `.vault.json` config
2. Creates `.memory/` directory
3. Discovers and loads plugins from `plugins/*.py`
4. Builds LangGraph instance (placeholder)
5. Registers command handlers with WebSocket server

**Plugin Loading:**
- Scans `vault/plugins/*.py`
- Dynamically imports each module
- Finds `Plugin` class → instantiates with `EventEmitter`

**Tick Loop:**
- Runs every 5 seconds
- Calls `plugin.on_tick(emitter)` for each plugin
- Allows plugins to emit periodic events

**Command Handlers:**
- `chat.send_message`: Processes chat (placeholder echoes back)
- `execute_command`: Calls plugin methods dynamically (e.g., `example_plugin.custom_action`)

---

### **3. Plugin System**

#### **Example Plugin Structure** (`example-vault/plugins/example_plugin.py`)

**Required Structure:**
```python
class Plugin:
    def __init__(self, emitter):
        self.emitter = emitter
        self.name = "example_plugin"
        # Send init notification
        emitter.notify("Plugin loaded!", severity="success")
    
    async def on_tick(self, emitter):
        """Called every 5 seconds"""
        # Every 15 seconds (3 ticks), send notification
        if self.tick_count % 3 == 0:
            emitter.notify("Heartbeat!", severity="info")
    
    async def custom_action(self, **kwargs):
        """Custom command via execute_command"""
        emitter.notify("Action executed!", severity="success")
        return {"status": "completed"}
```

**Plugin Lifecycle:**
1. **Load**: `VaultBrain._load_plugins()` imports module
2. **Init**: `Plugin(emitter)` constructor called
3. **Tick**: `on_tick()` called every 5s by tick loop
4. **Commands**: Custom methods invoked via `execute_command`

---

### **4. Frontend** (`index.html`)

Simple launcher UI:

```javascript
// User clicks "Open Vault" → selects directory
const result = await invoke('open_vault', { vaultPath: selected });
// Returns: { window_label: "vault_1", ws_port: 9001 }
```

**New Window Created:**
- Separate Tauri window for each vault
- Connects to WebSocket at `ws://localhost:{ws_port}`
- Listens for events via `sidecar-event` channel

---

## **Complete Flow Examples**

### **Flow 1: User Opens a Vault**

```mermaid
sequenceDiagram
    actor User
    participant UI as Frontend (HTML)
    participant Rust as Tauri/Rust
    participant SM as SidecarManager
    participant Python as Python Sidecar
    participant Plugin as Example Plugin
    
    User->>UI: Clicks "Open Vault"
    UI->>UI: Select directory (example-vault/)
    UI->>Rust: invoke('open_vault', {vaultPath})
    Rust->>Rust: DependencyChecker.check_and_install()
    Rust->>Rust: WindowManager.create_vault_window()
    Rust->>SM: spawn_sidecar(window_label, vault_path)
    SM->>SM: Allocate port 9001
    SM->>Python: Spawn process: python main.py --vault ... --ws-port 9001
    Python->>Python: Load .vault.json config
    Python->>Python: Create .memory/ directory
    Python->>Python: Initialize WebSocketServer(9001)
    Python->>Plugin: Load plugins/example_plugin.py
    Plugin->>Plugin: __init__(emitter)
    Plugin->>Python: emitter.notify("Plugin loaded!")
    Python->>Rust: WebSocket: trigger_event(NOTIFY)
    Rust->>Rust: EventBus.route_from_sidecar()
    Rust->>UI: Emit "sidecar-event" to window
    UI->>User: Show notification: "Plugin loaded!"
    Python->>Python: Start tick loop (every 5s)
    SM->>Rust: Return ws_port: 9001
    Rust->>UI: Return {window_label, ws_port}
    UI->>User: Display status: "Opened: vault_1 (Port: 9001)"
```

**Step-by-Step:**

1. **User clicks "Open Vault"** → selects `example-vault/`
2. **Rust**: `ipc_router::open_vault()` called
3. **Dependency Check**: Installs `plugins/requirements.txt` to `lib/`
4. **Window Creation**: `WindowManager` creates new window `vault_1`
5. **Sidecar Spawn**: 
   - `SidecarManager` allocates port `9001`
   - Spawns: `python -u sidecar/main.py --vault example-vault --ws-port 9001`
6. **Python Sidecar Starts**:
   - Loads config from `.vault.json`
   - Creates `.memory/` directory
   - Loads `plugins/example_plugin.py`
   - Starts WebSocket server on port `9001`
   - Starts tick loop
7. **Plugin Initialization**:
   - `example_plugin.Plugin(emitter)` constructor runs
   - Emits: `emitter.notify("Plugin loaded!", severity="success")`
8. **WebSocket** → **Rust EventBus** → **Window UI** shows notification

---

### **Flow 2: Plugin Emits Event Every 15 Seconds**

```mermaid
sequenceDiagram
    participant Loop as Tick Loop
    participant Plugin as Example Plugin
    participant Emitter as EventEmitter
    participant WS as WebSocket Server
    participant Rust as Tauri/Rust
    participant UI as Window UI
    
    Loop->>Loop: Sleep 5 seconds
    Loop->>Plugin: on_tick(emitter)
    Plugin->>Plugin: Check tick_count % 3 == 0
    Plugin->>Emitter: notify("Heartbeat #5", severity="info")
    Emitter->>Emitter: Build JSON-RPC message
    Emitter->>WS: send_to_rust({method: "trigger_event", ...})
    WS->>Rust: WebSocket send JSON
    Rust->>Rust: EventBus.route_from_sidecar()
    Rust->>Rust: Match scope: "window"
    Rust->>UI: window.emit("sidecar-event", event)
    UI->>UI: Show notification toast
```

**Step-by-Step:**

1. **Tick Loop** (every 5s): Calls `example_plugin.on_tick(emitter)`
2. **Every 3rd tick** (15s):
   ```python
   emitter.notify("Heartbeat #5 from example_plugin", severity="info")
   ```
3. **EventEmitter** sends JSON-RPC:
   ```json
   {
     "jsonrpc": "2.0",
     "method": "trigger_event",
     "params": {
       "event_type": "NOTIFY",
       "scope": "window",
       "data": {"message": "Heartbeat #5", "severity": "info"}
     }
   }
   ```
4. **WebSocket** → **Rust**: Receives event
5. **EventBus**: Routes to `vault_1` window (scope: `window`)
6. **UI**: Shows notification toast

---

### **Flow 3: User Sends Chat Message** (Future Implementation)

```mermaid
sequenceDiagram
    actor User
    participant UI as Window UI
    participant Rust as Tauri/Rust
    participant WS as WebSocket Server
    participant Brain as VaultBrain
    participant LLM as LangGraph
    
    User->>UI: Types "Hello" in chat
    UI->>Rust: invoke('send_to_sidecar', {command: {...}})
    Rust->>WS: WebSocket connect ws://localhost:9001
    Rust->>WS: Send JSON-RPC: chat.send_message
    WS->>WS: Parse JSON, lookup handler
    WS->>Brain: handle_chat({message: "Hello"})
    Brain->>LLM: Process with LangGraph
    LLM->>Brain: Return response
    Brain->>WS: Return {response: "...", status: "success"}
    WS->>Rust: WebSocket send response
    Rust->>UI: Return result
    UI->>User: Display AI response
```

**Step-by-Step:**

1. **UI**: User types "Hello" → calls `invoke('send_to_sidecar', {...})`
2. **Rust**: Forwards to WebSocket `ws://localhost:9001`
3. **WebSocket Server**: Receives `chat.send_message` command
4. **VaultBrain**: Handler processes with LangGraph (currently echoes)
5. **Response**: `{"response": "Echo: Hello", "status": "success"}`
6. **WebSocket** → **Rust** → **UI**: Displays response

---

### **Flow 4: User Closes Vault**

```mermaid
sequenceDiagram
    actor User
    participant UI as Window
    participant Rust as Tauri/Rust
    participant SM as SidecarManager
    participant Python as Python Sidecar
    
    User->>UI: Closes window
    UI->>Rust: invoke('close_vault', {window_label})
    Rust->>SM: terminate_sidecar(window_label)
    SM->>Python: process.child.kill()
    Python->>Python: Process exits
    SM->>Rust: Return OK
    Rust->>Rust: WindowManager.remove_window()
    Rust->>Rust: EventBus.unregister_window()
    Rust->>UI: Return success
    UI->>UI: Window closes
```

**Step-by-Step:**

1. **Window Close Event** → `ipc_router::close_vault(vault_1)`
2. **SidecarManager**: `process.child.kill()` terminates Python
3. **WindowManager**: Removes window tracking
4. **EventBus**: Unregisters window from vault mapping

---

## **Event Routing Scopes**

The EventBus supports three routing scopes:

### **1. Window Scope** (Default)
```python
emitter.notify("Task complete!")  # scope="window"
```
- Routes to **only** the window that spawned this sidecar
- Most common for plugin notifications

### **2. Vault Scope**
```python
emitter.vault_event("STATE_CHANGED", {...})
```
- Routes to **all windows** that have the same vault open
- Useful for synchronized state across multiple windows

### **3. Global Scope**
```python
emitter.global_event("SYSTEM_ALERT", {...})
```
- Routes to **every window** in the application
- Useful for system-wide notifications

---

## **Data Flow: JSON-RPC Communication**

### **Command (Rust → Python)**
```json
{
  "jsonrpc": "2.0",
  "method": "chat.send_message",
  "params": {
    "message": "Hello, world!"
  },
  "id": "cmd_123"
}
```

### **Response (Python → Rust)**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "response": "Echo: Hello, world!",
    "status": "success"
  },
  "id": "cmd_123"
}
```

### **Event (Python → Rust)**
```json
{
  "jsonrpc": "2.0",
  "method": "trigger_event",
  "params": {
    "event_type": "NOTIFY",
    "scope": "window",
    "data": {
      "message": "Plugin loaded!",
      "severity": "success"
    },
    "timestamp": 1234567890.123
  },
  "id": "evt_1"
}
```

---

## **Key Design Patterns**

1. **Process Isolation**: Each vault = separate Python process (no shared state)
2. **Portable Vaults**: `vault/` folder is self-contained (plugins + deps + memory)
3. **Bi-Directional Events**: Plugins can push events to UI (not just request/response)
4. **Scoped Routing**:
   - `window`: Single window only
   - `vault`: All windows with same vault
   - `global`: Every window in the app
5. **Dynamic Plugin Loading**: Drop `.py` files in `plugins/` → auto-loaded
6. **Async Tick System**: Plugins run periodic tasks without blocking WebSocket

---

## **File Structure**

```
tailor/
├── src-tauri/                    # Rust backend
│   ├── src/
│   │   ├── main.rs               # Entry point (AppState init)
│   │   ├── window_manager.rs    # Window lifecycle management
│   │   ├── sidecar_manager.rs   # Python process orchestration
│   │   ├── event_bus.rs          # Event routing (window/vault/global)
│   │   ├── ipc_router.rs         # IPC commands (open/close/send)
│   │   └── dependency_checker.rs # Auto pip install
│   └── Cargo.toml
├── sidecar/                      # Python sidecar
│   ├── main.py                   # Entry point (CLI args parser)
│   ├── websocket_server.py       # JSON-RPC WebSocket server
│   ├── event_emitter.py          # Plugin API for events
│   ├── vault_brain.py            # LangGraph orchestrator
│   └── requirements.txt
├── example-vault/                # Example vault
│   ├── .vault.json               # Vault metadata
│   ├── plugins/
│   │   ├── example_plugin.py     # Demo plugin
│   │   └── requirements.txt      # Plugin dependencies
│   ├── lib/                      # Auto-managed dependencies (gitignored)
│   └── .memory/                  # Conversation history (gitignored)
├── index.html                    # Frontend launcher
└── README.md
```

---

## **Current State vs. Future**

### **✅ Implemented:**
- Multi-window vault management
- Isolated Python sidecars per vault
- WebSocket JSON-RPC communication
- Plugin loading + tick loop system
- Event emission API (notify, progress, state)
- Event routing (window/vault/global scopes)
- Dependency auto-installation

### **🚧 Placeholders/TODO:**
- **LangGraph Integration**: Currently just a dict in `vault_brain.py`
- **Memory System**: Directory created but no actual memory storage
- **Rust WebSocket Client**: `send_to_sidecar` in `ipc_router.rs` needs implementation
- **Full Chat Processing**: `handle_chat` currently echoes instead of using LLM
- **Window UI**: Each vault window needs actual UI (currently just shows launcher)

---

## **Development Workflow**

### **Running the Application**
```powershell
npm run tauri:dev
```

This will:
1. Start Vite dev server for frontend
2. Compile Rust backend
3. Launch Tauri application

### **Testing a Plugin**
1. Create `my-vault/.vault.json`
2. Add `my-vault/plugins/my_plugin.py`
3. Open vault in Tailor
4. Watch console for sidecar logs
5. Observe `on_tick` notifications every 5 seconds

### **Creating a New Plugin**
```python
# my-vault/plugins/my_plugin.py
class Plugin:
    def __init__(self, emitter):
        self.emitter = emitter
        self.name = "my_plugin"
    
    async def on_tick(self, emitter):
        """Called every 5 seconds"""
        pass
    
    async def custom_method(self, **kwargs):
        """Call via: execute_command("my_plugin.custom_method", {...})"""
        return {"status": "ok"}
```

---

## **Technology Stack**

- **Frontend**: HTML + Vanilla JavaScript + Tauri API
- **Backend**: Rust + Tauri Framework
- **Sidecar**: Python 3.10+ (asyncio)
- **Communication**: WebSocket (JSON-RPC 2.0)
- **Process Management**: Rust `std::process::Command`
- **Event System**: Tauri event emitter + custom EventBus
- **Future**: LangGraph for AI orchestration

---

## **Security & Isolation**

1. **Process Isolation**: Each vault runs in separate Python process
2. **Port Allocation**: Unique WebSocket port per vault (9000+)
3. **Dependency Isolation**: Each vault has its own `lib/` directory
4. **No Shared State**: Vaults cannot interfere with each other
5. **Local-Only**: WebSocket listens on `localhost` only

---

## **Troubleshooting**

### **Sidecar Not Starting**
- Check Python is in PATH: `python --version`
- Check sidecar logs in Rust console
- Verify `sidecar/requirements.txt` installed

### **Plugin Not Loading**
- Ensure plugin has `class Plugin` with `__init__(self, emitter)`
- Check sidecar console for import errors
- Verify plugin file doesn't start with `_`

### **Events Not Reaching UI**
- Verify WebSocket connection established (check port)
- Check EventBus routing scope matches expectation
- Inspect browser console for `sidecar-event` listener

---

## **Next Steps for Development**

1. **Implement LangGraph**: Replace placeholder with actual LangGraph orchestration
2. **Memory System**: Implement conversation history persistence
3. **Rust WebSocket Client**: Complete `send_to_sidecar` functionality
4. **Vault Window UI**: Build React/Vue UI for each vault window (chat, tools, etc.)
5. **Plugin Marketplace**: Sharing and discovering community plugins
6. **Hot Reload**: Reload plugins without restarting sidecar
