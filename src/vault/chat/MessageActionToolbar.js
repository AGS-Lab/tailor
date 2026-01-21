/**
 * MessageActionToolbar - Extensible message action toolbar component
 * 
 * Provides copy, export, bookmark, delete, branch, and regenerate actions.
 * Supports plugin extensibility and responsive overflow handling.
 */

import { request } from '../connection.js';

// Action registry - stores all registered actions (core + plugins)
const actionRegistry = new Map();

// Overflow threshold - minimum width per action button
const ACTION_WIDTH = 36;
const OVERFLOW_BUTTON_WIDTH = 36;
const GAP_WIDTH = 4;

// Models cache
let modelsCache = null;

/**
 * Register core actions on module load
 */
function registerCoreActions() {
    // Copy action
    registerAction({
        id: 'copy',
        icon: 'copy',
        label: 'Copy',
        position: 10,
        type: 'button',
        location: 'message-actionbar',
        handler: async (message) => {
            try {
                await navigator.clipboard.writeText(message.content);
                showToast('Copied to clipboard');
            } catch (e) {
                console.error('[Toolbar] Copy failed:', e);
                showToast('Failed to copy', 'error');
            }
        }
    });

    // Export action
    registerAction({
        id: 'export',
        icon: 'download',
        label: 'Export',
        position: 20,
        type: 'dropdown',
        location: 'message-actionbar',
        dropdownItems: [
            { id: 'json', icon: 'braces', label: 'JSON' },
            { id: 'markdown', icon: 'file-code', label: 'Markdown' },
            { id: 'text', icon: 'file', label: 'Plain Text' }
        ],
        handler: async (message, format) => {
            try {
                downloadMessage(message, format);
                showToast(`Exported as ${format}`);
            } catch (e) {
                console.error('[Toolbar] Export failed:', e);
                showToast('Export failed', 'error');
            }
        }
    });

    // Bookmark action
    registerAction({
        id: 'bookmark',
        icon: 'bookmark',
        label: 'Save',
        position: 30,
        type: 'button',
        location: 'message-actionbar',
        handler: async (message, _, context) => {
            try {
                saveBookmarkLocally(message, context);
                showToast('Saved to bookmarks');
            } catch (e) {
                console.error('[Toolbar] Bookmark failed:', e);
                showToast('Failed to save', 'error');
            }
        }
    });

    // Delete action - removed as it's rarely needed and clutters the UI

    // Branch action
    registerAction({
        id: 'branch',
        icon: 'git-branch',
        label: 'Branch',
        position: 50,
        type: 'button',
        location: 'message-actionbar',
        handler: async (message, _, context) => {
            try {
                const historyUpToMessage = context?.history?.slice(0, (context?.index || 0) + 1) || [];
                window.dispatchEvent(new CustomEvent('chat:createBranch', {
                    detail: { branchFrom: message, history: historyUpToMessage }
                }));
                showToast('Branch created');
            } catch (e) {
                console.error('[Toolbar] Branch failed:', e);
                showToast('Failed to branch', 'error');
            }
        }
    });

    // Regenerate action
    registerAction({
        id: 'regenerate',
        icon: 'refresh-cw',
        label: 'Regenerate',
        position: 60,
        type: 'dropdown',
        location: 'message-actionbar',
        dropdownItems: [],
        getDropdownItems: async () => {
            const models = await getAvailableModels();
            return models.map(m => ({
                id: m.id,
                icon: getProviderIcon(m.provider),
                label: m.name
            }));
        },
        handler: async (message, modelId, context) => {
            try {
                window.dispatchEvent(new CustomEvent('chat:regenerate', {
                    detail: { messageIndex: context?.index, model: modelId }
                }));
                showToast(`Regenerating...`);
            } catch (e) {
                console.error('[Toolbar] Regenerate failed:', e);
                showToast('Regenerate failed', 'error');
            }
        }
    });

    // Note: Composer actions are registered by plugins via UI_COMMAND events
    // See prompt-refiner plugin for an example
}

/**
 * Register an action to the toolbar
 * @param {Object} action - Action config
 * @param {string} action.id - Unique action ID
 * @param {string} action.icon - Lucide icon name
 * @param {string} action.label - Button label/tooltip
 * @param {number} action.position - Sort order (lower = left)
 * @param {string} action.type - 'button' or 'dropdown'
 * @param {string} action.location - 'message-actionbar' or 'composer-actionbar'
 * @param {Function} action.handler - Click handler
 */
export function registerAction(action) {
    if (!action.id) {
        console.error('[Toolbar] Action must have an id');
        return;
    }
    // Default location is message-actionbar for backwards compatibility
    if (!action.location) {
        action.location = 'message-actionbar';
    }
    actionRegistry.set(action.id, action);
}

/**
 * Unregister an action from the toolbar
 */
export function unregisterAction(actionId) {
    actionRegistry.delete(actionId);
}

/**
 * Get actions filtered by location
 * @param {string} location - 'message-actionbar' or 'composer-actionbar'
 */
function getActionsByLocation(location) {
    return Array.from(actionRegistry.values())
        .filter(a => a.location === location)
        .sort((a, b) => a.position - b.position);
}

/**
 * Create toolbar element for a message
 */
export function createToolbar(message, context = {}) {
    const toolbar = document.createElement('div');
    toolbar.className = 'message-action-toolbar';
    toolbar.dataset.messageId = message.id || context.index;

    // Create visible actions container
    const actionsContainer = document.createElement('div');
    actionsContainer.className = 'toolbar-actions';
    toolbar.appendChild(actionsContainer);

    // Render actions for message-actionbar location
    renderActions(toolbar, actionsContainer, 'message-actionbar', message, context);

    // Setup resize observer for overflow handling
    setupOverflowHandler(toolbar, actionsContainer, 'message-actionbar', message, context);

    return toolbar;
}

/**
 * Create composer toolbar element (below message input)
 */
export function createComposerToolbar() {
    const toolbar = document.createElement('div');
    toolbar.className = 'composer-action-toolbar';
    toolbar.id = 'composer-toolbar';

    // Create actions container
    const actionsContainer = document.createElement('div');
    actionsContainer.className = 'toolbar-actions';
    toolbar.appendChild(actionsContainer);

    // Render actions for composer-actionbar location
    const actions = getActionsByLocation('composer-actionbar');

    actions.forEach(action => {
        const btn = createActionButton(action, {}, {});
        actionsContainer.appendChild(btn);
    });

    // Initialize icons
    if (window.lucide) {
        setTimeout(() => window.lucide.createIcons(), 0);
    }

    return toolbar;
}

/**
 * Refresh composer toolbar (call when actions are registered)
 */
export function refreshComposerToolbar() {
    const existing = document.getElementById('composer-toolbar');
    if (existing) {
        const actionsContainer = existing.querySelector('.toolbar-actions');
        if (actionsContainer) {
            actionsContainer.innerHTML = '';
            const actions = getActionsByLocation('composer-actionbar');
            actions.forEach(action => {
                const btn = createActionButton(action, {}, {});
                actionsContainer.appendChild(btn);
            });
            if (window.lucide) {
                setTimeout(() => window.lucide.createIcons(), 0);
            }
        }
    }
}

/**
 * Render action buttons
 */
function renderActions(toolbar, container, location, message, context, maxVisible = Infinity) {
    const actions = getActionsByLocation(location);
    container.innerHTML = '';

    // Remove existing overflow menu
    const existingOverflow = toolbar.querySelector('.toolbar-overflow');
    if (existingOverflow) existingOverflow.remove();

    const visibleActions = actions.slice(0, maxVisible);
    const overflowActions = actions.slice(maxVisible);

    // Render visible actions
    visibleActions.forEach(action => {
        const btn = createActionButton(action, message, context);
        container.appendChild(btn);
    });

    // Render overflow menu if needed
    if (overflowActions.length > 0) {
        const overflowBtn = createOverflowButton(overflowActions, message, context);
        toolbar.appendChild(overflowBtn);
    }

    // Initialize Lucide icons
    if (window.lucide) {
        setTimeout(() => window.lucide.createIcons(), 0);
    }
}

/**
 * Create an action button element
 */
function createActionButton(action, message, context) {
    const btn = document.createElement('button');
    btn.className = 'toolbar-action-btn';
    btn.title = action.label;
    btn.dataset.actionId = action.id;
    btn.innerHTML = `<i data-lucide="${action.icon}"></i>`;

    if (action.type === 'dropdown') {
        btn.classList.add('has-dropdown');
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            await showDropdown(btn, action, message, context);
        });
    } else {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            action.handler(message, null, context);
        });
    }

    return btn;
}

/**
 * Create overflow (three-dot) button
 */
function createOverflowButton(actions, message, context) {
    const wrapper = document.createElement('div');
    wrapper.className = 'toolbar-overflow';

    const btn = document.createElement('button');
    btn.className = 'toolbar-action-btn toolbar-overflow-btn';
    btn.title = 'More actions';
    btn.innerHTML = `<i data-lucide="more-horizontal"></i>`;

    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        showOverflowMenu(wrapper, actions, message, context);
    });

    wrapper.appendChild(btn);
    return wrapper;
}

/**
 * Show dropdown menu for an action
 */
async function showDropdown(btn, action, message, context) {
    // Close any existing dropdowns
    closeAllDropdowns();

    const dropdown = document.createElement('div');
    dropdown.className = 'toolbar-dropdown';

    // Get dropdown items (may be async for regenerate)
    let items = action.dropdownItems || [];
    if (action.getDropdownItems) {
        dropdown.innerHTML = '<div class="dropdown-loading"><i data-lucide="loader-2" class="spin"></i> Loading...</div>';
        btn.parentElement.appendChild(dropdown);
        if (window.lucide) window.lucide.createIcons();

        items = await action.getDropdownItems();
        dropdown.innerHTML = '';
    }

    items.forEach(item => {
        const itemEl = document.createElement('div');
        itemEl.className = 'dropdown-item';
        itemEl.innerHTML = `<i data-lucide="${item.icon}"></i><span>${item.label}</span>`;
        itemEl.addEventListener('click', (e) => {
            e.stopPropagation();
            action.handler(message, item.id, context);
            closeAllDropdowns();
        });
        dropdown.appendChild(itemEl);
    });

    if (!btn.parentElement.contains(dropdown)) {
        btn.parentElement.appendChild(dropdown);
    }

    if (window.lucide) window.lucide.createIcons();

    // Close on outside click
    setTimeout(() => {
        document.addEventListener('click', closeAllDropdowns, { once: true });
    }, 0);
}

/**
 * Show overflow menu
 */
function showOverflowMenu(wrapper, actions, message, context) {
    closeAllDropdowns();

    const menu = document.createElement('div');
    menu.className = 'toolbar-dropdown overflow-menu';

    actions.forEach(action => {
        const itemEl = document.createElement('div');
        itemEl.className = 'dropdown-item';
        itemEl.innerHTML = `<i data-lucide="${action.icon}"></i><span>${action.label}</span>`;

        if (action.type === 'dropdown') {
            itemEl.classList.add('has-submenu');
            itemEl.innerHTML += `<i data-lucide="chevron-right" class="submenu-arrow"></i>`;
            itemEl.addEventListener('click', async (e) => {
                e.stopPropagation();
                await showSubmenu(itemEl, action, message, context);
            });
        } else {
            itemEl.addEventListener('click', (e) => {
                e.stopPropagation();
                action.handler(message, null, context);
                closeAllDropdowns();
            });
        }

        menu.appendChild(itemEl);
    });

    wrapper.appendChild(menu);

    if (window.lucide) window.lucide.createIcons();

    setTimeout(() => {
        document.addEventListener('click', closeAllDropdowns, { once: true });
    }, 0);
}

/**
 * Show submenu for overflow dropdown items
 */
async function showSubmenu(parentItem, action, message, context) {
    // Remove existing submenus
    document.querySelectorAll('.toolbar-submenu').forEach(s => s.remove());

    const submenu = document.createElement('div');
    submenu.className = 'toolbar-dropdown toolbar-submenu';

    let items = action.dropdownItems || [];
    if (action.getDropdownItems) {
        submenu.innerHTML = '<div class="dropdown-loading"><i data-lucide="loader-2" class="spin"></i></div>';
        parentItem.appendChild(submenu);
        if (window.lucide) window.lucide.createIcons();

        items = await action.getDropdownItems();
        submenu.innerHTML = '';
    }

    items.forEach(item => {
        const itemEl = document.createElement('div');
        itemEl.className = 'dropdown-item';
        itemEl.innerHTML = `<i data-lucide="${item.icon}"></i><span>${item.label}</span>`;
        itemEl.addEventListener('click', (e) => {
            e.stopPropagation();
            action.handler(message, item.id, context);
            closeAllDropdowns();
        });
        submenu.appendChild(itemEl);
    });

    parentItem.appendChild(submenu);
    if (window.lucide) window.lucide.createIcons();
}

/**
 * Close all dropdown menus
 */
function closeAllDropdowns() {
    document.querySelectorAll('.toolbar-dropdown').forEach(d => d.remove());
}

/**
 * Setup resize observer for overflow handling
 */
function setupOverflowHandler(toolbar, actionsContainer, location, message, context) {
    const resizeObserver = new ResizeObserver(entries => {
        for (const entry of entries) {
            const availableWidth = entry.contentRect.width;
            const actions = getActionsByLocation(location);

            // Calculate how many actions fit
            const totalActions = actions.length;
            const widthPerAction = ACTION_WIDTH + GAP_WIDTH;
            let maxVisible = Math.floor((availableWidth - OVERFLOW_BUTTON_WIDTH) / widthPerAction);

            // If all actions fit without overflow button, show them all
            if (maxVisible >= totalActions) {
                maxVisible = totalActions;
            } else {
                // Ensure at least the overflow button shows
                maxVisible = Math.max(0, maxVisible);
            }

            renderActions(toolbar, actionsContainer, location, message, context, maxVisible);
        }
    });

    resizeObserver.observe(toolbar);

    // Store observer for cleanup
    toolbar._resizeObserver = resizeObserver;
}

/**
 * Cleanup toolbar resources
 */
export function destroyToolbar(toolbar) {
    if (toolbar._resizeObserver) {
        toolbar._resizeObserver.disconnect();
    }
}

/**
 * Get available models for regeneration
 */
async function getAvailableModels() {
    if (modelsCache) return modelsCache;

    try {
        // Try to fetch from backend
        const result = await request('execute_command', {
            command: 'models.list',
            args: {}
        });

        if (result?.result?.models) {
            modelsCache = result.result.models;
            return modelsCache;
        }
    } catch (e) {
        console.warn('[Toolbar] Could not fetch models from backend');
    }

    // Fallback: use common models
    modelsCache = [
        { id: 'gpt-4o', name: 'GPT-4o', provider: 'OpenAI' },
        { id: 'gpt-4o-mini', name: 'GPT-4o Mini', provider: 'OpenAI' },
        { id: 'claude-3-5-sonnet-20241022', name: 'Claude 3.5 Sonnet', provider: 'Anthropic' },
        { id: 'claude-3-5-haiku-20241022', name: 'Claude 3.5 Haiku', provider: 'Anthropic' },
        { id: 'gemini-2.0-flash-exp', name: 'Gemini 2.0 Flash', provider: 'Google' },
        { id: 'gemini-1.5-pro', name: 'Gemini 1.5 Pro', provider: 'Google' }
    ];
    return modelsCache;
}

/**
 * Get icon for a provider
 */
function getProviderIcon(provider) {
    const icons = {
        'OpenAI': 'bot',
        'Anthropic': 'message-circle',
        'Google': 'sparkles',
        'Mistral': 'wind',
        'Groq': 'zap',
        'Ollama': 'server'
    };
    return icons[provider] || 'cpu';
}

/**
 * Show toast notification
 */
/**
 * Show toast notification
 */
export function showToast(message, type = 'success') {
    // Check if toast container exists
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <i data-lucide="${type === 'success' ? 'check-circle' : 'alert-circle'}"></i>
        <span>${message}</span>
    `;

    container.appendChild(toast);
    if (window.lucide) window.lucide.createIcons();

    // Auto-remove after 3 seconds
    setTimeout(() => {
        toast.classList.add('toast-fade-out');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

/**
 * Download message in specified format (fallback)
 */
function downloadMessage(message, format) {
    let content, filename, mimeType;

    switch (format) {
        case 'json':
            content = JSON.stringify({ role: message.role, content: message.content, timestamp: new Date().toISOString() }, null, 2);
            filename = `message-${Date.now()}.json`;
            mimeType = 'application/json';
            break;
        case 'markdown':
            content = `## ${message.role === 'user' ? 'User' : 'Assistant'}\n\n${message.content}`;
            filename = `message-${Date.now()}.md`;
            mimeType = 'text/markdown';
            break;
        case 'text':
        default:
            content = message.content;
            filename = `message-${Date.now()}.txt`;
            mimeType = 'text/plain';
            break;
    }

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}

/**
 * Save bookmark locally (fallback)
 */
function saveBookmarkLocally(message, context) {
    const bookmarks = JSON.parse(localStorage.getItem('chat_bookmarks') || '[]');
    bookmarks.push({
        id: Date.now(),
        content: message.content,
        role: message.role,
        vault: context?.vault || 'default',
        timestamp: new Date().toISOString()
    });
    localStorage.setItem('chat_bookmarks', JSON.stringify(bookmarks));
}

// Initialize core actions
registerCoreActions();

// Export for global access
export default {
    createToolbar,
    destroyToolbar,
    registerAction,
    unregisterAction
};
