# Plugin UI Injection Guide

This guide explains how Tailor plugins can dynamically inject UI components (HTML, CSS) into the frontend from Python.

## Overview

Plugins can inject custom UI elements without requiring any frontend code changes. All UI is sent dynamically via WebSocket `UI_COMMAND` events.

## Available UI Commands

### 1. `inject_css` - Add Plugin Styles

Inject CSS styles for your plugin. Styles are scoped by plugin ID.

```python
self.brain.emit_to_frontend(
    event_type=EventType.UI_COMMAND,
    data={
        "action": "inject_css",
        "plugin_id": "my-plugin",  # Unique plugin identifier
        "css": """
            .my-plugin-container {
                background: #f5f5f5;
                padding: 12px;
                border-radius: 8px;
            }
            .my-plugin-btn {
                color: var(--accent-primary);
            }
        """
    }
)
```

**Notes:**
- CSS is injected into `<head>` as a `<style>` tag with ID `plugin-css-{plugin_id}`
- Existing styles with same ID are replaced (hot reload support)
- Use CSS variables for theme compatibility: `var(--text-primary)`, `var(--bg-card)`, etc.

---

### 2. `inject_html` - Add HTML Elements

Inject HTML into any target element in the DOM.

```python
self.brain.emit_to_frontend(
    event_type=EventType.UI_COMMAND,
    data={
        "action": "inject_html",
        "id": "my-element-id",           # Optional: ID for the root element
        "target": ".message-content",     # CSS selector for target element
        "position": "beforeend",          # Where to insert (see positions below)
        "html": """
            <div id="my-element-id" class="my-plugin-container">
                <span>Hello from plugin!</span>
                <button class="my-plugin-btn" onclick="window.myPluginAction()">
                    <i data-lucide="star"></i> Click me
                </button>
            </div>
        """
    }
)
```

**Position Options:**
| Position | Description |
|----------|-------------|
| `beforeend` | Inside target, after last child (default) |
| `afterbegin` | Inside target, before first child |
| `beforebegin` | Before target element |
| `afterend` | After target element |

**Notes:**
- If `id` is provided and element exists, it will be **updated** instead of duplicated
- Lucide icons (`<i data-lucide="icon-name">`) are auto-initialized
- Use `onclick="window.myFunction()"` for interactivity

---

### 3. `remove_html` - Remove Elements

Remove an injected HTML element from the DOM.

```python
self.brain.emit_to_frontend(
    event_type=EventType.UI_COMMAND,
    data={
        "action": "remove_html",
        "id": "my-element-id"         # Element ID to remove
        # OR
        "selector": ".my-plugin-item"  # CSS selector (fallback)
    }
)
```

---

### 4. `update_html` - Update Element Content

Update the innerHTML of an existing element.

```python
self.brain.emit_to_frontend(
    event_type=EventType.UI_COMMAND,
    data={
        "action": "update_html",
        "id": "my-element-id",          # Element ID
        "html": "<span>New content!</span>"
    }
)
```

---

## Adding Interactivity

For interactive elements, inject a `<script>` tag that defines global functions:

```python
def _inject_plugin_js(self):
    """Inject JavaScript helpers for plugin interactivity."""
    js_code = '''
    <script id="my-plugin-js">
    window.myPluginAction = function() {
        alert('Button clicked!');
    };
    
    window.myPluginSubmit = async function(value) {
        // Call backend command
        await window.request('execute_command', {
            command: 'my-plugin.handle_submit',
            args: { value: value }
        });
    };
    </script>
    '''
    
    self.brain.emit_to_frontend(
        event_type=EventType.UI_COMMAND,
        data={
            "action": "inject_html",
            "id": "my-plugin-js",
            "target": "head",
            "position": "beforeend",
            "html": js_code
        }
    )
```

---

## Common Target Selectors

| Target | Description |
|--------|-------------|
| `#chat-area` | Main chat container |
| `#chat-messages` | Messages list |
| `[data-message-id='msg-1']` | Specific message by ID |
| `.message-toolbar-container` | Message toolbar area |
| `.chat-composer` | Chat input area |
| `head` | Document head (for scripts) |

---

## Best Practices

1. **Unique IDs**: Always use unique, prefixed IDs: `my-plugin-container`, `my-plugin-btn`
2. **CSS Variables**: Use theme variables for colors to support dark/light modes
3. **Idempotent Injection**: Check if elements exist before injecting to avoid duplicates
4. **Cleanup**: Remove injected elements in `on_unload()` if needed
5. **Error Handling**: Wrap interactivity in try/catch blocks

---

## Example: Complete Pattern

```python
# In your plugin's on_client_connected():
async def on_client_connected(self) -> None:
    # 1. Inject CSS
    self.brain.emit_to_frontend(
        event_type=EventType.UI_COMMAND,
        data={"action": "inject_css", "plugin_id": self.name, "css": MY_CSS}
    )
    
    # 2. Register toolbar button
    self.brain.emit_to_frontend(
        event_type=EventType.UI_COMMAND,
        data={
            "action": "register_action",
            "id": "my-action",
            "icon": "star",
            "label": "My Action",
            "location": "message-actionbar",
            "command": "my-plugin.do_action"
        }
    )

# In your command handler:
async def _handle_do_action(self, message_id, content, **kwargs):
    # 3. Inject UI
    self.brain.emit_to_frontend(
        event_type=EventType.UI_COMMAND,
        data={
            "action": "inject_html",
            "id": f"my-result-{message_id}",
            "target": f"[data-message-id='{message_id}'] .message-toolbar-container",
            "position": "beforebegin",
            "html": f'<div id="my-result-{message_id}">Result: {content[:50]}...</div>'
        }
    )
```

---

## Reference: Summarizer Plugin

See `example-vault/plugins/summarizer/main.py` for a complete working example that:
- Injects CSS styles on connect
- Injects interactive HTML with expand/collapse
- Injects JavaScript for client-side interactivity
- Uses `remove_html` and `update_html` for menu actions
