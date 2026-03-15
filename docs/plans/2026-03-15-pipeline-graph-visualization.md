# LangGraph Visualization Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Add a read-only pipeline graph visualization to Tailor — the sidecar serializes the LangGraph as Mermaid syntax, a new RPC command exposes it, and the frontend renders it in a GoldenLayout panel using Mermaid.js.

**Architecture:** Backend `system.get_graph` command → Mermaid string → Frontend panel with Mermaid.js CDN rendering.

**Tech Stack:** LangGraph `draw_mermaid()`, Mermaid.js (CDN), vanilla JS.

---

### Task 1: Backend — `system.get_graph` RPC Command

**Files:**
- Modify: `sidecar/vault_brain.py`
- Modify: `sidecar/tests/test_pipeline.py`

**Step 1: Write the failing test**

```python
# Append to sidecar/tests/test_pipeline.py
def test_default_pipeline_has_mermaid(mock_brain):
    """Pipeline graph can be serialized to Mermaid."""
    config = PipelineConfig()
    pipeline = DefaultPipeline(config)

    mermaid = pipeline.graph.get_graph().draw_mermaid()

    assert "graph TD" in mermaid
    assert "input" in mermaid
    assert "llm" in mermaid
    assert "output" in mermaid
```

**Step 2: Run test to verify it passes** (this should already pass since `draw_mermaid()` is built into LangGraph)

Run: `pixi run pytest sidecar/tests/test_pipeline.py::test_default_pipeline_has_mermaid -v`

**Step 3: Add `system.get_graph` command to VaultBrain**

```python
# In sidecar/vault_brain.py, near the other system.* commands
@command("system.get_graph", constants.CORE_PLUGIN_NAME)
async def get_graph(self) -> Dict[str, Any]:
    """Get the current pipeline graph as Mermaid markup."""
    if not self.pipeline or not hasattr(self.pipeline, "graph"):
        return {"status": "error", "error": "No pipeline graph available"}

    try:
        mermaid = self.pipeline.graph.get_graph().draw_mermaid()

        # Also include tool registry info
        tools = self.tool_registry.get_all_schemas()

        return {
            "status": "success",
            "mermaid": mermaid,
            "tools": tools,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

**Step 4: Run existing pipeline tests to verify no breakage**

Run: `pixi run pytest sidecar/tests/test_pipeline.py -v`

**Step 5: Commit**

```bash
git add sidecar/vault_brain.py sidecar/tests/test_pipeline.py
git commit -m "feat(pipeline): add system.get_graph command for Mermaid visualization"
```

---

### Task 2: Frontend — Pipeline Visualization Panel

**Files:**
- Create: `src/vault/pipeline-graph.js`
- Modify: `src/vault/layout.js`

**Step 1: Create `pipeline-graph.js`**

This module:
1. Registers a new GoldenLayout component called `'pipeline'`
2. Loads Mermaid.js from CDN (lazy, only when the panel is opened)
3. Calls `system.get_graph` via `window.request()`
4. Renders the Mermaid markup in the panel
5. Includes a "Refresh" button and shows registered tools count

```javascript
// src/vault/pipeline-graph.js
export function registerPipelinePanel(layout) {
    layout.registerComponent('pipeline', function (container) {
        container.element.innerHTML = `
            <div class="panel-container" id="pipeline-graph-panel">
                <div class="scrollable" style="padding: 16px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                        <span class="text-label" style="color: var(--accent-primary);">Pipeline Graph</span>
                        <button id="pipeline-refresh-btn" class="icon-btn" title="Refresh">
                            <i data-lucide="refresh-cw" style="width:14px;height:14px;"></i> Refresh
                        </button>
                    </div>
                    <div id="pipeline-mermaid-container" style="
                        background: var(--bg-card);
                        border-radius: 12px;
                        border: 1px solid var(--border-subtle);
                        padding: 20px;
                        min-height: 200px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        color: var(--text-disabled);
                    ">Loading graph...</div>
                    <div id="pipeline-tools-summary" style="
                        margin-top: 12px;
                        padding: 12px 16px;
                        background: var(--bg-card);
                        border-radius: 8px;
                        border: 1px solid var(--border-subtle);
                        font-size: 13px;
                        color: var(--text-secondary);
                    "></div>
                </div>
            </div>
        `;

        // Load mermaid and render
        loadAndRender();

        // Bind refresh
        const refreshBtn = container.element.querySelector('#pipeline-refresh-btn');
        if (refreshBtn) {
            refreshBtn.onclick = () => loadAndRender();
        }
    });
}

async function loadAndRender() {
    // Lazy-load mermaid from CDN if not already loaded
    if (!window.mermaid) {
        await loadMermaidCDN();
    }

    const container = document.getElementById('pipeline-mermaid-container');
    const toolsSummary = document.getElementById('pipeline-tools-summary');
    if (!container) return;

    try {
        const res = await window.request('system.get_graph', {});
        if (res.result?.status === 'success') {
            // Render mermaid
            const { svg } = await window.mermaid.render('pipeline-graph-svg', res.result.mermaid);
            container.innerHTML = svg;
            container.style.color = '';

            // Show tools summary
            const tools = res.result.tools || [];
            if (toolsSummary) {
                toolsSummary.innerHTML = tools.length > 0
                    ? `<strong>${tools.length}</strong> tool(s) registered: ${tools.map(t => `<code>${t.function.name}</code>`).join(', ')}`
                    : 'No tools registered yet.';
            }
        } else {
            container.textContent = res.result?.error || 'Failed to load graph';
        }
    } catch (e) {
        container.textContent = `Error: ${e.message || e}`;
    }
}

function loadMermaidCDN() {
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js';
        script.onload = () => {
            window.mermaid.initialize({
                startOnLoad: false,
                theme: 'dark',
                flowchart: { curve: 'linear' },
            });
            resolve();
        };
        script.onerror = reject;
        document.head.appendChild(script);
    });
}
```

**Step 2: Register the panel in `layout.js`**

```javascript
// In src/vault/layout.js, add import at top:
import { registerPipelinePanel } from './pipeline-graph.js';

// Before myLayout.init(), add:
registerPipelinePanel(myLayout);

// Add 'pipeline' tab to the right sidebar stack in the config:
// In the config object, add to the first stack in the right column:
{
    type: 'component',
    componentName: 'pipeline',
    title: 'Pipeline'
}
```

**Step 3: Verify manually**

Start the dev server with `pixi run dev` and check:
1. The "Pipeline" tab appears in the right sidebar
2. It shows the Mermaid graph with nodes: `__start__` → `input` → `context` → `prompt` → `llm` → `post_process` → `output` → `__end__`
3. The "Refresh" button re-fetches and re-renders
4. The tools summary shows registered tool count

**Step 4: Commit**

```bash
git add src/vault/pipeline-graph.js src/vault/layout.js
git commit -m "feat(ui): add Pipeline visualization panel with Mermaid.js"
```

---

## Verification Plan

### Automated Tests

Run: `pixi run pytest sidecar/tests -v`
- All existing tests must still pass (186+)
- New `test_default_pipeline_has_mermaid` must pass

### Manual Verification

1. Run `pixi run dev`
2. Open a vault
3. Look for "Pipeline" tab in the right panel area (next to Toolbox/Log)
4. Confirm the graph renders showing the pipeline flow
5. Click "Refresh" — graph should re-render
6. Check the tools summary at the bottom shows tool count
