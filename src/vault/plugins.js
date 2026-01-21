/**
 * Plugin Loading & Event Handling Module
 * 
 * Handles loading plugins and processing UI commands from the backend.
 * Chat is now a core feature, not a plugin.
 */

import { request } from './connection.js';
import { initChat } from './chat/index.js';

const log = () => window.log || console.log;

/**
 * Load plugins and initialize core chat
 */
export async function loadPlugins(retryCount = 0) {
    const maxRetries = 3;
    const retryDelay = 500;
    const logFn = log();

    try {
        // Notify Backend Client is Ready
        logFn('Notifying backend: system.client_ready', 'out');
        await request('system.client_ready', {})
            .catch(e => console.warn('system.client_ready failed', e));

        // Wait for sidecar to finish initializing
        const initDelay = retryCount === 0 ? 1000 : 300;
        await new Promise(resolve => setTimeout(resolve, initDelay));

        // Initialize Core Chat (always available, not a plugin)
        const chatArea = document.getElementById('chat-area');
        if (chatArea) {
            logFn('Initializing core chat module', 'info');
            initChat(chatArea);
            logFn('Core chat initialized', 'in');
        } else {
            logFn('Chat area not found', 'error');
        }

        // List Commands for plugins
        const res = await request('list_commands');
        logFn(`list_commands response: ${JSON.stringify(res).slice(0, 200)}`, 'in');

        const commands = res.result?.commands || {};
        const commandList = Object.keys(commands);
        logFn(`Available commands: ${commandList.length}`, 'info');

        // Retry if no commands found
        if (commandList.length === 0 && retryCount < maxRetries) {
            logFn(`No commands found, retrying in ${retryDelay}ms... (attempt ${retryCount + 1}/${maxRetries})`, 'info');
            await new Promise(resolve => setTimeout(resolve, retryDelay));
            return loadPlugins(retryCount + 1);
        }

    } catch (e) {
        logFn(`Plugin Load Error: ${e}`, 'error');
        console.error('loadPlugins error:', e);

        if (retryCount < maxRetries) {
            logFn(`Retrying after error... (attempt ${retryCount + 1}/${maxRetries})`, 'info');
            await new Promise(resolve => setTimeout(resolve, retryDelay));
            return loadPlugins(retryCount + 1);
        }
    }
}

/**
 * Handle events from the backend
 */
export function handleEvent(evt) {
    const logFn = log();
    logFn(`Event: ${evt.event_type}`, 'in');

    // Dispatch to window (plugins can listen)
    const eventType = evt.event_type;
    const detail = evt.data || {};

    const customEvent = new CustomEvent(eventType, { detail });
    window.dispatchEvent(customEvent);

    // Handle notifications
    if (eventType === 'NOTIFY') {
        const { message, severity } = evt.data || {};
        if (message) {
            window.ui.showToast(message, severity);
        }
    }

    // Handle UI Commands from Backend
    if (eventType === 'UI_COMMAND') {
        console.log('[handleEvent] UI_COMMAND received:', evt.data);
        const data = evt.data;

        switch (data.action) {
            // Sidebar
            case 'register_sidebar':
                console.log('[handleEvent] Registering sidebar:', data.id, data.icon, data.title);
                window.ui.registerSidebarView(data.id, data.icon, data.title);
                break;
            case 'set_sidebar':
                console.log('[handleEvent] Setting sidebar content:', data.id);
                window.ui.setSidebarContent(data.id, data.html);
                break;

            // Panels
            case 'register_panel':
                console.log('[handleEvent] Registering panel:', data.id, data.title);
                window.ui.registerPanel(data.id, data.title, data.icon, data.position);
                break;
            case 'set_panel':
                console.log('[handleEvent] Setting panel content:', data.id);
                window.ui.setPanelContent(data.id, data.html);
                break;
            case 'remove_panel':
                console.log('[handleEvent] Removing panel:', data.id);
                window.ui.removePanel(data.id);
                break;

            // Toolbar
            case 'register_toolbar':
                console.log('[handleEvent] Registering toolbar button:', data.id, data.command);
                window.ui.registerToolbarButton(data.id, data.icon, data.title, data.command);
                break;

            // Stage
            case 'set_stage':
                console.log('[handleEvent] Setting stage content');
                window.ui.setStageContent(data.html);
                break;

            // Modal
            case 'show_modal':
                console.log('[handleEvent] Showing modal:', data.title);
                window.ui.showModal(data.title, data.html, data.width);
                break;
            case 'close_modal':
                console.log('[handleEvent] Closing modal');
                window.ui.closeModal();
                break;

            // Message Action Toolbar
            case 'register_message_action':
                // Legacy - auto-set location
                console.log('[handleEvent] Registering message action (legacy):', data.id);
                if (window.ui.registerAction) {
                    window.ui.registerAction({
                        id: data.id,
                        icon: data.icon,
                        label: data.label,
                        position: data.position || 100,
                        type: data.type || 'button',
                        command: data.command,
                        location: 'message-actionbar'
                    });
                }
                break;

            // Action Toolbar (new API with location support)
            case 'register_action':
                console.log('[handleEvent] Registering action:', data.id, 'at', data.location);
                if (window.ui.registerAction) {
                    window.ui.registerAction({
                        id: data.id,
                        icon: data.icon,
                        label: data.label,
                        position: data.position || 100,
                        type: data.type || 'button',
                        command: data.command,
                        location: data.location || 'message-actionbar'
                    });
                }
                break;

            // Input field control
            case 'request_input':
                console.log('[handleEvent] Requesting input for:', data.callback_command);
                const inputEl = document.querySelector('#llm-input, #chat-input, .chat-input, .llm-input');
                const inputText = inputEl ? inputEl.value : '';
                if (data.callback_command && window.request) {
                    window.request(data.callback_command, { text: inputText });
                }
                break;
            case 'set_input':
                console.log('[handleEvent] Setting input text:', data.text);
                const targetInput = document.querySelector('#llm-input, #chat-input, .chat-input, .llm-input');
                if (targetInput) {
                    targetInput.value = data.text || '';
                    targetInput.dispatchEvent(new Event('input', { bubbles: true }));
                    targetInput.focus();
                }
                break;

            // ===== GENERIC PLUGIN UI INJECTION =====
            // These handlers allow plugins to dynamically inject HTML/CSS

            case 'inject_css':
                // Inject CSS styles for a plugin
                // data: { plugin_id, css }
                injectPluginCSS(data.plugin_id, data.css);
                break;

            case 'inject_html':
                // Inject HTML into a target element
                // data: { id, target, position, html }
                // position: 'beforeend' (default), 'afterbegin', 'beforebegin', 'afterend'
                injectPluginHTML(data.id, data.target, data.position || 'beforeend', data.html);
                break;

            case 'remove_html':
                // Remove an injected HTML element
                // data: { id } or { selector }
                removePluginHTML(data.id, data.selector);
                break;

            case 'update_html':
                // Update content of an existing element
                // data: { id, html } or { selector, html }
                updatePluginHTML(data.id, data.selector, data.html);
                break;

            default:
                console.warn('[handleEvent] Unknown UI action:', data.action);
        }
    }
}

// ===== PLUGIN UI INJECTION HELPERS =====

/**
 * Inject CSS styles for a plugin
 * @param {string} pluginId - Unique plugin identifier
 * @param {string} css - CSS styles to inject
 */
function injectPluginCSS(pluginId, css) {
    if (!pluginId || !css) {
        console.warn('[UI] inject_css requires plugin_id and css');
        return;
    }

    const styleId = `plugin-css-${pluginId}`;

    // Remove existing style if present (for hot reload)
    const existing = document.getElementById(styleId);
    if (existing) {
        existing.remove();
    }

    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = css;
    document.head.appendChild(style);

    console.log(`[UI] Injected CSS for plugin: ${pluginId}`);
}
/**
 * Inject HTML into a target element
 * @param {string} id - Unique ID for the injected element
 * @param {string} target - CSS selector for target element
 * @param {string} position - Insert position (beforeend, afterbegin, beforebegin, afterend)
 * @param {string} html - HTML to inject
 */
function injectPluginHTML(id, target, position, html) {
    if (!target || !html) {
        console.warn('[UI] inject_html requires target and html');
        return;
    }

    const targetEl = document.querySelector(target);
    if (!targetEl) {
        console.warn(`[UI] Target element not found: ${target}`);
        return;
    }

    // Check if element with this ID already exists
    if (id) {
        const existing = document.getElementById(id);
        if (existing) {
            console.log(`[UI] Element ${id} already exists, skipping`);
            return;
        }
    }

    // Check if this is a script injection
    if (html.trim().startsWith('<script')) {
        // Extract script content and execute it properly
        const scriptMatch = html.match(/<script[^>]*>([\s\S]*?)<\/script>/i);
        if (scriptMatch) {
            const script = document.createElement('script');
            if (id) script.id = id;
            script.textContent = scriptMatch[1];
            document.head.appendChild(script);
            console.log(`[UI] Executed script${id ? ` (id: ${id})` : ''}`);
            return;
        }
    }

    // Insert HTML
    targetEl.insertAdjacentHTML(position, html);

    // Execute any scripts in the inserted content
    executeScriptsIn(targetEl);

    // Initialize Lucide icons in injected content
    initializeLucideIcons();

    console.log(`[UI] Injected HTML${id ? ` (id: ${id})` : ''} into ${target}`);
}

/**
 * Execute script tags in an element (scripts inserted via innerHTML don't auto-execute)
 */
function executeScriptsIn(container) {
    const scripts = container.querySelectorAll('script');
    scripts.forEach(oldScript => {
        const newScript = document.createElement('script');
        // Copy attributes
        Array.from(oldScript.attributes).forEach(attr => {
            newScript.setAttribute(attr.name, attr.value);
        });
        // Copy content
        newScript.textContent = oldScript.textContent;
        // Replace old with new (this causes execution)
        oldScript.parentNode.replaceChild(newScript, oldScript);
    });
}


/**
 * Remove an injected HTML element
 * @param {string} id - Element ID to remove
 * @param {string} selector - CSS selector to remove (fallback)
 */
function removePluginHTML(id, selector) {
    let el = null;

    if (id) {
        el = document.getElementById(id);
    } else if (selector) {
        el = document.querySelector(selector);
    }

    if (el) {
        el.remove();
        console.log(`[UI] Removed element: ${id || selector}`);
    } else {
        console.warn(`[UI] Element not found: ${id || selector}`);
    }
}

/**
 * Update content of an existing element
 * @param {string} id - Element ID
 * @param {string} selector - CSS selector (fallback)
 * @param {string} html - New HTML content
 */
function updatePluginHTML(id, selector, html) {
    let el = null;

    if (id) {
        el = document.getElementById(id);
    } else if (selector) {
        el = document.querySelector(selector);
    }

    if (el) {
        el.innerHTML = html;
        initializeLucideIcons();
        console.log(`[UI] Updated element: ${id || selector}`);
    } else {
        console.warn(`[UI] Element not found for update: ${id || selector}`);
    }
}

/**
 * Initialize Lucide icons in recently added content
 */
function initializeLucideIcons() {
    if (window.lucide) {
        setTimeout(() => window.lucide.createIcons(), 0);
    }
}

