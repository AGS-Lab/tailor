/**
 * GoldenLayout Configuration & Initialization
 * 
 * Sets up the main editor layout with panels for stage, chat, log, and controls.
 */

import { GoldenLayout } from 'golden-layout';
import 'golden-layout/dist/css/goldenlayout-base.css';

/**
 * Default layout configuration
 */
const config = {
    header: {
        popout: false
    },
    content: [{
        type: 'row',
        content: [
            {
                type: 'stack', // Main Chat Area
                width: 65,
                content: [
                    {
                        type: 'component',
                        componentName: 'chat',
                        title: 'LLM Chat'
                    }
                ]
            },
            {
                type: 'column', // Right Sidebar
                width: 35,
                content: [
                    {
                        type: 'stack',
                        height: 60,
                        content: [
                            {
                                type: 'component',
                                componentName: 'toolbox',
                                title: 'Toolbox'
                            },
                            {
                                type: 'component',
                                componentName: 'log',
                                title: 'System Log'
                            }
                        ]
                    },
                    {
                        type: 'component',
                        componentName: 'controls',
                        title: 'Inspector',
                        height: 40
                    }
                ]
            }
        ]
    }]
};

/**
 * Initialize GoldenLayout with component registrations
 */
export function initLayout() {
    const layoutRoot = document.getElementById('layout-root');
    const myLayout = new GoldenLayout(config, layoutRoot);

    // Component: Stage
    // Component: Toolbox
    myLayout.registerComponent('toolbox', function (container, state) {
        container.element.innerHTML = `
            <div class="panel-container">
                <div class="scrollable" id="toolbox-area" style="padding: 10px;">
                    <!-- Default Plugin Area -->
                    <div class="text-empty default-text">
                        Toolbox Empty
                    </div>
                </div>
            </div>
        `;
    });

    // Backward compatibility for stage
    myLayout.registerComponent('stage', function (container, state) {
        container.element.innerHTML = `
            <div class="panel-container">
                <div class="scrollable">
                        <div class="text-empty">
                        Legacy Stage
                    </div>
                </div>
            </div>
        `;
    });

    // Component: Chat
    myLayout.registerComponent('chat', function (container, state) {
        container.element.innerHTML = `
            <div class="panel-container">
                <div class="scrollable" id="chat-area">
                    <div style="color:var(--text-disabled); text-align:center; padding-top:20px;">
                        Waiting for LLM...
                    </div>
                </div>
            </div>
        `;
    });

    // Component: Log
    myLayout.registerComponent('log', function (container, state) {
        container.element.innerHTML = `
            <div class="panel-container">
                <div class="scrollable" id="log-output"></div>
                <div class="toolbar flex-between">
                    <span class="text-label" style="font-family:var(--font-main);">SYSTEM OUTPUT</span>
                    <button id="clearLog" class="icon-btn" title="Clear Log">Clear</button>
                </div>
            </div>
        `;

        // Bind Clear Log
        const clearBtn = container.element.querySelector('#clearLog');
        if (clearBtn) {
            clearBtn.onclick = () => {
                const out = document.getElementById('log-output');
                if (out) out.innerHTML = '';
            };
        }
    });

    // Component: Controls
    myLayout.registerComponent('controls', function (container, state) {
        container.element.innerHTML = `
            <div class="panel-container" style="background: transparent; box-shadow: none; border: none;">
                <div class="scrollable" style="padding: 16px;">
                    <div style="background: var(--bg-card); border-radius: 12px; border: 1px solid var(--border-subtle); padding: 16px; box-shadow: var(--shadow-sm);">
                        <div style="margin-bottom: 16px;">
                            <label class="text-label" style="display:block; margin-bottom:8px; color: var(--accent-primary);">Command</label>
                            <textarea id="cmd-input" rows="1" class="w-full" style="padding: 10px 12px; font-family: var(--font-mono); font-size: 13px; resize: none; overflow: hidden; height: auto; min-height: 42px;" placeholder="e.g. demo.hello"></textarea>
                        </div>
                        
                        <div style="margin-bottom: 20px;">
                            <label class="text-label" style="display:block; margin-bottom:8px; color: var(--accent-primary);">Arguments</label>
                            <input id="arg-input" class="w-full" style="padding: 10px 12px; font-family: var(--font-mono); font-size: 13px;" placeholder='{"key": "value"}'>
                        </div>
                        
                        <button id="execBtn" class="btn btn-primary w-full" style="justify-content: center;">
                            <span style="font-weight: 700; letter-spacing: 0.05em;">EXECUTE</span>
                        </button>
                    </div>
                </div>
            </div>
        `;

        // Bind Execute
        const execBtn = container.element.querySelector('#execBtn');
        if (execBtn) {
            execBtn.onclick = async () => {
                const cmd = document.getElementById('cmd-input').value;
                let args = {};
                try {
                    args = JSON.parse(document.getElementById('arg-input').value || '{}');
                    if (typeof args !== 'object' || args === null || Array.isArray(args)) {
                        throw new Error("Arguments must be a JSON object");
                    }
                } catch (e) {
                    window.log(`Invalid JSON args: ${e.message}`, 'error');
                    return;
                }

                try {
                    const res = await window.request(cmd, args);
                    window.log(JSON.stringify(res.result, null, 2));
                } catch (e) {
                    window.log(`Exec failed: ${e}`, 'error');
                }
            };
        }
    });

    myLayout.init();
    window.myLayout = myLayout;

    // Handle window resize
    window.addEventListener('resize', () => {
        if (myLayout.isInitialised) myLayout.updateSize();
    });

    return myLayout;
}

/**
 * Initialize sidebar resize functionality
 */
export function initResize() {
    const panel = document.getElementById('side-panel');
    const handle = document.getElementById('side-panel-resize');
    const mainEditor = document.querySelector('.main-editor');

    if (!panel || !handle || !mainEditor) return;

    let isResizing = false;
    let startX = 0;
    let startWidth = 0;

    handle.addEventListener('mousedown', (e) => {
        if (!panel.classList.contains('open')) return;
        isResizing = true;
        startX = e.clientX;
        startWidth = panel.offsetWidth;
        handle.classList.add('resizing');
        document.body.style.cursor = 'ew-resize';
        document.body.style.userSelect = 'none';
        mainEditor.style.pointerEvents = 'none';
        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;
        const delta = e.clientX - startX;
        const newWidth = Math.max(150, Math.min(500, startWidth + delta));
        panel.style.width = newWidth + 'px';
        if (window.myLayout) window.myLayout.updateSize();
    });

    document.addEventListener('mouseup', () => {
        if (isResizing) {
            isResizing = false;
            handle.classList.remove('resizing');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
            mainEditor.style.pointerEvents = '';
            if (window.myLayout) window.myLayout.updateSize();
        }
    });
}

/**
 * Logging function
 */
export function log(msg, type = 'info') {
    const out = document.getElementById('log-output');
    if (!out) return;

    const div = document.createElement('div');
    div.className = `log-entry ${type}`;
    const time = new Date().toLocaleTimeString().split(' ')[0];
    div.innerHTML = `<span class="ts">${time}</span>${msg}`;
    out.appendChild(div);
    out.scrollTop = out.scrollHeight;
}
