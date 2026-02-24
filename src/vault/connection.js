/**
 * Vault WebSocket Connection Module
 * 
 * Handles WebSocket connection to the sidecar, RPC requests,
 * and automatic reconnection.
 */

let ws = null;
let rpcId = 0;
const pending = new Map();
let reconnectAttempts = 0;
const maxReconnectAttempts = 10;
let currentPort = null;

// Import log from globals (set by layout module)
const getLog = () => window.log || console.log;

/**
 * Set connection status and trigger plugin loading
 */
function setConnected(isConnected, loadPluginsFn) {
    const log = getLog();

    if (isConnected) {
        log('Connected to Sidecar', 'in');
        // Wait for GoldenLayout to fully initialize and sidecar to be ready
        if (loadPluginsFn) loadPluginsFn();
    } else {
        log('Disconnected', 'error');
    }
}

/**
 * Connect to the WebSocket server
 * @param {string} explicitPort - Optional explicit port
 * @param {Function} loadPluginsFn - Callback to load plugins after connection
 * @param {Function} handleEventFn - Callback to handle events
 */
export function connect(explicitPort, loadPluginsFn, handleEventFn) {
    const log = getLog();

    // Priority: Explicit Arg > URL param > Default 9002
    let port = explicitPort || currentPort;
    if (!port) {
        const params = new URLSearchParams(window.location.search);
        port = params.get('port') || '9002';
    }
    currentPort = port;

    log(`Connecting to ws://127.0.0.1:${port}... (attempt ${reconnectAttempts + 1}/${maxReconnectAttempts})`);

    ws = new WebSocket(`ws://127.0.0.1:${port}`);

    ws.onopen = () => {
        reconnectAttempts = 0;
        setConnected(true, loadPluginsFn);
    };

    ws.onclose = () => {
        setConnected(false);
        scheduleReconnect(loadPluginsFn, handleEventFn);
    };

    ws.onerror = (e) => {
        log('WebSocket Error', 'error');
    };

    ws.onmessage = (e) => {
        try {
            const data = JSON.parse(e.data);
            if (data.method === 'trigger_event') {
                if (handleEventFn) handleEventFn(data.params);
            } else if (data.id && pending.has(data.id)) {
                pending.get(data.id)(data);
                pending.delete(data.id);
            }
        } catch (err) {
            log(`Parse Error: ${err}`, 'error');
        }
    };
}

/**
 * Schedule reconnection with exponential backoff
 */
function scheduleReconnect(loadPluginsFn, handleEventFn) {
    const log = getLog();

    if (reconnectAttempts >= maxReconnectAttempts) {
        log(`Max reconnect attempts (${maxReconnectAttempts}) reached. Please reload.`, 'error');
        return;
    }

    reconnectAttempts++;
    const delay = Math.min(500 * Math.pow(2, reconnectAttempts - 1), 5000);
    log(`Reconnecting in ${delay}ms...`, 'info');

    setTimeout(() => {
        connect(null, loadPluginsFn, handleEventFn);
    }, delay);
}

/**
 * Make a JSON-RPC request
 * @param {string} method - RPC method name
 * @param {object} params - Parameters
 * @returns {Promise} - Promise that resolves with the response
 */
export function request(method, params = {}) {
    const log = getLog();

    if (!ws || ws.readyState !== WebSocket.OPEN) {
        log('Not connected', 'error');
        return Promise.reject('Not connected');
    }

    return new Promise((resolve) => {
        const id = ++rpcId;
        const msg = { jsonrpc: '2.0', id, method, params };
        pending.set(id, resolve);
        ws.send(JSON.stringify(msg));
        log(`> ${method}`, 'out');
    });
}

// Expose request globally for plugins
window.request = request;

/**
 * Auto-connect based on URL params or Tauri IPC
 */
export async function autoConnect(loadPluginsFn, handleEventFn) {
    const log = getLog();
    let autoPort = null;

    // 1. Check URL Params
    const params = new URLSearchParams(window.location.search);
    if (params.has('port')) {
        autoPort = params.get('port');
        log(`Found port in URL: ${autoPort}`);
    }

    // 2. Try Tauri IPC
    if (!autoPort) {
        try {
            const { invoke } = await import('@tauri-apps/api/core');
            const vaultInfo = await invoke('get_current_vault_info');
            if (vaultInfo && vaultInfo.ws_port) {
                autoPort = vaultInfo.ws_port;
                log(`Found port via Tauri: ${autoPort}`);
            }
        } catch (e) {
            // Not in Tauri or API failed
        }
    }

    if (autoPort) {
        setTimeout(() => connect(autoPort, loadPluginsFn, handleEventFn), 300);
    } else {
        log('No auto-connect port found. Connection will use default (9002).');
        setTimeout(() => connect('9002', loadPluginsFn, handleEventFn), 300);
    }
}
