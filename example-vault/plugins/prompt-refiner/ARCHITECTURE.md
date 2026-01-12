# Prompt Refiner Plugin - Architecture

## Overview

The Prompt Refiner plugin demonstrates the complete plugin communication flow in Tailor, showing how plugins interact with both the Python backend and the frontend UI.

## High-Level Flow

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend (vault.html)
    participant WS as WebSocket Server
    participant B as VaultBrain
    participant P as Prompt Refiner Plugin
    participant L as LLM Pipeline

    Note over U,L: Initialization Phase
    P->>B: register_command("refiner.refine")
    P->>WS: register_handler("refiner.refine_from_ui")
    P->>F: UI_COMMAND: register_toolbar (sparkle button)

    Note over U,L: User Clicks Refine Button
    U->>F: Click ✨ button
    F->>WS: execute_command("refiner.refine_from_ui")
    WS->>P: _handle_refine_from_ui()
    P->>F: UI_COMMAND: request_input

    Note over U,L: Get Input Text
    F->>F: querySelector("#llm-input")
    F->>WS: refiner.refine({text: "..."})
    WS->>B: lookup brain.commands
    B->>P: _handle_refine(text)

    Note over U,L: LLM Processing
    P->>P: Validate text not empty
    P->>L: run(text, system_prompt)
    L-->>P: refined_text

    Note over U,L: Update UI
    P->>F: UI_COMMAND: set_input(refined_text)
    F->>F: Set #llm-input.value
    P->>F: NOTIFY: "Prompt refined!"
    F->>U: See refined prompt in input
```

## Component Architecture

```mermaid
flowchart TB
    subgraph Frontend["Frontend (vault.html)"]
        TB[Toolbar Button ✨]
        HE[handleEvent]
        INP[#llm-input]
        NM[Notification Manager]
    end

    subgraph Sidecar["Python Sidecar"]
        WS[WebSocket Server]
        VB[VaultBrain]
        
        subgraph Plugin["Prompt Refiner Plugin"]
            RC[register_commands]
            HUI[_handle_refine_from_ui]
            HR[_handle_refine]
        end
        
        LLM[LLM Pipeline]
    end

    TB -->|"execute_command"| WS
    WS -->|"lookup handler"| HUI
    HUI -->|"UI_COMMAND: request_input"| HE
    HE -->|"read value"| INP
    INP -->|"refiner.refine(text)"| WS
    WS -->|"lookup brain.commands"| VB
    VB -->|"call handler"| HR
    HR -->|"run()"| LLM
    LLM -->|"refined text"| HR
    HR -->|"UI_COMMAND: set_input"| HE
    HE -->|"set value"| INP
    HR -->|"NOTIFY"| NM
```

## Detailed Process Flow

### Phase 1: Plugin Initialization

```mermaid
flowchart LR
    A[Plugin Loaded] --> B[register_commands]
    B --> C["brain.register_command('refiner.refine')"]
    
    A --> D[on_client_connected]
    D --> E["register_toolbar_button()"]
    D --> F["ws_server.register_handler('refiner.refine_from_ui')"]
    
    E --> G[UI_COMMAND: register_toolbar]
    G --> H[ToolbarManager.registerButton]
    H --> I[✨ Button in Activity Bar]
```

### Phase 2: Button Click → Get Input

```mermaid
flowchart TB
    A["User clicks ✨"] --> B["ToolbarManager.onClick"]
    B --> C["window.request('execute_command', {command: 'refiner.refine_from_ui'})"]
    C --> D[WebSocket: JSON-RPC Request]
    D --> E["ws_server.handle_message()"]
    E --> F{"Method in command_handlers?"}
    F -->|Yes| G["_handle_refine_from_ui()"]
    G --> H["emit UI_COMMAND: request_input"]
    H --> I["handleEvent() in vault.html"]
    I --> J["querySelector('#llm-input')"]
    J --> K["window.request('refiner.refine', {text: inputValue})"]
```

### Phase 3: Refine Processing

```mermaid
flowchart TB
    A["refiner.refine called"] --> B["ws_server.handle_message()"]
    B --> C{"Method in command_handlers?"}
    C -->|No| D{"Method in brain.commands?"}
    D -->|Yes| E["_handle_refine(text)"]
    
    E --> F{"text empty?"}
    F -->|Yes| G["NOTIFY: 'Please enter text'"]
    F -->|No| H["pipeline.run()"]
    
    H --> I[System Prompt: Refiner Expert]
    H --> J[User Message: Original Text]
    
    I --> K[LLM API Call]
    J --> K
    K --> L[Refined Text Response]
    
    L --> M["emit UI_COMMAND: set_input"]
    M --> N["handleEvent() sets #llm-input.value"]
    
    L --> O["emit NOTIFY: 'Prompt refined!'"]
```

## Key Files

| File | Purpose |
|------|---------|
| [`main.py`](file:///d:/tailor/example-vault/plugins/prompt-refiner/main.py) | Plugin logic, LLM refinement |
| [`vault_brain.py`](file:///d:/tailor/sidecar/vault_brain.py) | Command registry, bidirectional lookup |
| [`websocket_server.py`](file:///d:/tailor/sidecar/websocket_server.py) | WebSocket RPC, fallback to brain commands |
| [`vault.html`](file:///d:/tailor/vault.html) | UI command handlers, input field control |
| [`plugin_base.py`](file:///d:/tailor/sidecar/api/plugin_base.py) | Base class with UI helper methods |

## Command Registration

```
┌─────────────────────────────────────────────────────────────┐
│                    Command Lookup Order                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  WebSocket Server receives method                            │
│          │                                                   │
│          ▼                                                   │
│  ┌───────────────────┐                                       │
│  │ ws_server.        │  ◄─── Plugins can register here       │
│  │ command_handlers  │       via ws_server.register_handler()│
│  └─────────┬─────────┘                                       │
│            │ Not found?                                      │
│            ▼                                                 │
│  ┌───────────────────┐                                       │
│  │ brain.commands    │  ◄─── Plugins register here           │
│  │                   │       via brain.register_command()    │
│  └─────────┬─────────┘                                       │
│            │ Not found?                                      │
│            ▼                                                 │
│  ┌───────────────────┐                                       │
│  │ Method Not Found  │                                       │
│  │ Error Response    │                                       │
│  └───────────────────┘                                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## LLM System Prompt

The refiner uses a specialized system prompt:

```
You are a prompt engineering expert. Your job is to take a user's 
rough prompt and refine it to be:

1. **Clear**: Remove ambiguity and be specific
2. **Concise**: Remove unnecessary words
3. **Structured**: Add structure if complex
4. **Complete**: Add missing context

Rules:
- Return ONLY the refined prompt, no explanations
- Preserve the original intent completely
- Keep the same language/tone
```
