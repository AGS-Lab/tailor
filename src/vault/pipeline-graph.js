/**
 * Pipeline Graph Visualization
 * 
 * Renders the current LangGraph pipeline as a Mermaid diagram
 * in a GoldenLayout panel. Fetches graph data via `system.get_graph` RPC.
 */

/**
 * Register the Pipeline panel component with GoldenLayout.
 * @param {GoldenLayout} layout 
 */
export function registerPipelinePanel(layout) {
    layout.registerComponent('pipeline', function (container) {
        container.element.innerHTML = `
            <div class="panel-container" id="pipeline-graph-panel">
                <div class="scrollable" style="padding: 16px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                        <span class="text-label" style="font-family:var(--font-main); color: var(--accent-primary); font-weight: 600;">
                            Pipeline Graph
                        </span>
                        <button id="pipeline-refresh-btn" class="icon-btn" title="Refresh Graph">
                            <i data-lucide="refresh-cw" style="width:14px;height:14px;"></i>
                        </button>
                    </div>
                    <div id="pipeline-mermaid-container" style="
                        background: var(--bg-card);
                        border-radius: 12px;
                        border: 1px solid var(--border-subtle);
                        padding: 16px;
                        min-height: 120px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        color: var(--text-disabled);
                        overflow: hidden;
                    ">Loading graph...</div>
                    <div id="pipeline-tools-summary" style="
                        margin-top: 12px;
                        padding: 12px 16px;
                        background: var(--bg-card);
                        border-radius: 8px;
                        border: 1px solid var(--border-subtle);
                        font-size: 13px;
                        font-family: var(--font-main);
                        color: var(--text-secondary);
                    "></div>
                </div>
            </div>
        `;

        // Bind refresh button
        const refreshBtn = container.element.querySelector('#pipeline-refresh-btn');
        if (refreshBtn) {
            refreshBtn.onclick = () => loadAndRender();
        }

        // Re-init icons after DOM injection
        if (window.lucide) window.lucide.createIcons();

        // Wait for sidecar connection before fetching graph
        waitForConnectionThenRender();
    });
}

/**
 * Wait until window.request is available (sidecar connected), then render.
 * Retries every 1s up to 15 times.
 */
async function waitForConnectionThenRender() {
    const maxRetries = 15;
    for (let i = 0; i < maxRetries; i++) {
        if (typeof window.request === 'function') {
            await loadAndRender();
            return;
        }
        await new Promise(r => setTimeout(r, 1000));
    }
    const container = document.getElementById('pipeline-mermaid-container');
    if (container) container.textContent = 'Sidecar not connected. Click refresh to retry.';
}

// Track render count for unique SVG IDs (mermaid requires unique IDs)
let renderCount = 0;

/**
 * Fetch the pipeline graph from the sidecar and render it with Mermaid.
 */
async function loadAndRender() {
    // Lazy-load mermaid from CDN if not already loaded
    if (!window.mermaid) {
        try {
            await loadMermaidCDN();
        } catch (e) {
            const container = document.getElementById('pipeline-mermaid-container');
            if (container) container.textContent = 'Failed to load Mermaid.js library.';
            return;
        }
    }

    const container = document.getElementById('pipeline-mermaid-container');
    const toolsSummary = document.getElementById('pipeline-tools-summary');
    if (!container) return;

    container.innerHTML = '<span style="color:var(--text-disabled);">Fetching graph...</span>';

    try {
        const res = await window.request('system.get_graph', {});

        if (res.result?.status === 'success') {
            // Render Mermaid diagram
            renderCount++;
            const svgId = `pipeline-graph-svg-${renderCount}`;
            const { svg } = await window.mermaid.render(svgId, res.result.mermaid);
            container.innerHTML = svg;
            container.style.color = '';

            // Force the SVG to fit inside the container
            const svgEl = container.querySelector('svg');
            if (svgEl) {
                svgEl.removeAttribute('height');
                svgEl.style.width = '100%';
                svgEl.style.height = 'auto';
                svgEl.style.maxHeight = '500px';
            }

            // Show tools summary
            const tools = res.result.tools || [];
            if (toolsSummary) {
                if (tools.length > 0) {
                    const toolNames = tools
                        .map(t => `<code style="background:var(--bg-elevated);padding:2px 6px;border-radius:4px;font-size:12px;">${t.function.name}</code>`)
                        .join(' ');
                    toolsSummary.innerHTML = `<strong style="color:var(--accent-primary);">${tools.length}</strong> tool(s) registered: ${toolNames}`;
                } else {
                    toolsSummary.innerHTML = '<span style="color:var(--text-disabled);">No tools registered yet. Use <code>@tool</code> decorator in plugins to expose tools.</span>';
                }
            }
        } else {
            container.textContent = res.result?.error || 'Failed to load graph.';
        }
    } catch (e) {
        container.textContent = `Error: ${e.message || e}`;
    }
}

/**
 * Lazy-load Mermaid.js from CDN.
 * @returns {Promise<void>}
 */
function loadMermaidCDN() {
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js';
        script.onload = () => {
            window.mermaid.initialize({
                startOnLoad: false,
                theme: 'dark',
                themeVariables: {
                    fontSize: '14px',
                    nodePadding: 8,
                },
                flowchart: {
                    curve: 'linear',
                    nodeSpacing: 20,
                    rankSpacing: 30,
                    padding: 10,
                },
            });
            resolve();
        };
        script.onerror = () => reject(new Error('Failed to load Mermaid.js'));
        document.head.appendChild(script);
    });
}
