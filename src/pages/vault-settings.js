/**
 * Vault Settings Page
 * Modern vault-specific configuration
 */

import { settingsApi, vaultApi } from '../services/api.js';

export async function initVaultSettings(container) {
    const params = new URLSearchParams(window.location.search);
    const vaultPath = params.get('path') || '';

    if (!vaultPath) {
        container.innerHTML = '<div class="error-message">No vault path provided</div>';
        return;
    }

    container.innerHTML = `
        <div class="vault-settings-container">
            <div class="vault-settings-header">
                <h1>Vault Settings</h1>
                <p class="settings-subtitle">${vaultPath}</p>
            </div>

            <div class="settings-content">
                <div class="settings-nav">
                    <div class="settings-nav-item active" data-section="general">
                        <i data-lucide="settings"></i>
                        <span>General</span>
                    </div>
                    <div class="settings-nav-item" data-section="ai-models">
                        <i data-lucide="brain"></i>
                        <span>AI Models</span>
                    </div>
                    <div class="settings-nav-item" data-section="api-keys">
                        <i data-lucide="key"></i>
                        <span>API Keys</span>
                    </div>
                    <div class="settings-nav-item" data-section="plugins">
                        <i data-lucide="package"></i>
                        <span>Plugins</span>
                    </div>
                </div>

                <div class="settings-panel">
                    <div id="settings-content-area">
                        <!-- Settings content will be loaded here -->
                    </div>
                </div>
            </div>
        </div>
    `;

    if (window.lucide) {
        window.lucide.createIcons();
    }

    await loadSettings(vaultPath, container);
    setupSettingsNavigation(container, vaultPath);
}

async function loadSettings(vaultPath, container) {
    try {
        await showSection('general', vaultPath, container);
    } catch (error) {
        console.error('DEBUG VAULT SETTINGS ERROR:', error);
        const contentArea = container.querySelector('#settings-content-area');
        if (contentArea) contentArea.innerHTML = `<div class="error-message">Failed to load settings</div>`;
    }
}

async function showSection(section, vaultPath, container) {
    const contentArea = container.querySelector('#settings-content-area');

    const navItems = container.querySelectorAll('.settings-nav-item');
    navItems.forEach(item => {
        item.classList.toggle('active', item.dataset.section === section);
    });

    switch (section) {
        case 'general':
            contentArea.innerHTML = `
                <div class="settings-section">
                    <h2>General</h2>
                    <div class="settings-group">
                        <div class="settings-item">
                            <label>Vault Name</label>
                            <input type="text" class="settings-item" placeholder="Enter vault name" />
                        </div>
                        <div class="settings-item">
                            <label>Description</label>
                            <textarea rows="3" placeholder="Describe your vault..."></textarea>
                        </div>
                    </div>
                </div>
            `;
            break;
        case 'ai-models':
            contentArea.innerHTML = `
                <div class="settings-section">
                    <h2>AI Models</h2>
                    <div class="settings-group">
                        <div class="settings-item">
                            <label>Default Model</label>
                            <select>
                                <option>GPT-4</option>
                                <option>GPT-3.5 Turbo</option>
                                <option>Claude 3 Opus</option>
                            </select>
                        </div>
                        <div class="settings-item">
                            <label>Temperature</label>
                            <input type="range" min="0" max="2" step="0.1" value="0.7" />
                        </div>
                    </div>
                </div>
            `;
            break;
        case 'api-keys':
            contentArea.innerHTML = `
                <div class="settings-section">
                    <h2>API Keys</h2>
                    <p class="settings-section-description">Manage API keys for third-party integrations</p>
                    <div class="settings-group">
                        <div class="settings-item">
                            <label>OpenAI API Key</label>
                            <input type="password" placeholder="sk-..." />
                            <span class="settings-item-hint">Your API key is stored securely</span>
                        </div>
                    </div>
                </div>
            `;
            break;
        case 'plugins':
            contentArea.innerHTML = `
                <div class="settings-section">
                    <h2>Plugins</h2>
                    <p class="settings-section-description">Manage plugins installed in this vault</p>
                    <div id="installed-plugins-list" class="plugins-list">
                        <div class="loading-indicator">
                            <i data-lucide="loader" class="spinning"></i>
                            Loading plugins...
                        </div>
                    </div>
                    <div class="settings-actions" style="margin-top: 20px;">
                        <a href="#plugin-store" class="btn btn-primary">
                            <i data-lucide="plus"></i>
                            Browse Plugin Store
                        </a>
                    </div>
                </div>
            `;
            if (window.lucide) window.lucide.createIcons();

            // Load installed plugins
            try {
                const listEl = contentArea.querySelector('#installed-plugins-list');

                // Fetch plugins via WebSocket if available
                if (typeof window.request === 'function') {
                    const result = await window.request('plugins.list', {});

                    if (result.plugins && result.plugins.length > 0) {
                        listEl.innerHTML = '';
                        result.plugins.forEach(plugin => {
                            const item = document.createElement('div');
                            item.className = 'plugin-item';
                            item.dataset.pluginId = plugin.id || '';

                            const info = document.createElement('div');
                            info.className = 'plugin-item-info';

                            const header = document.createElement('div');
                            header.className = 'plugin-item-header';

                            const title = document.createElement('h4');
                            title.textContent = plugin.name || plugin.id || '';

                            const version = document.createElement('span');
                            version.className = 'plugin-version';
                            version.textContent = `v${plugin.version || '0.0.0'}`;

                            header.appendChild(title);
                            header.appendChild(version);

                            const desc = document.createElement('p');
                            desc.className = 'plugin-description';
                            desc.textContent = plugin.description || '';

                            info.appendChild(header);
                            info.appendChild(desc);

                            const actions = document.createElement('div');
                            actions.className = 'plugin-item-actions';

                            const label = document.createElement('label');
                            label.className = 'toggle-switch';

                            const input = document.createElement('input');
                            input.type = 'checkbox';
                            input.className = 'plugin-toggle';
                            input.dataset.pluginId = plugin.id || '';
                            input.checked = !!plugin.enabled;

                            const slider = document.createElement('span');
                            slider.className = 'toggle-slider';

                            label.appendChild(input);
                            label.appendChild(slider);

                            const btn = document.createElement('button');
                            btn.className = 'btn btn-icon btn-danger plugin-uninstall';
                            btn.dataset.pluginId = plugin.id || '';
                            btn.title = 'Uninstall plugin';

                            const icon = document.createElement('i');
                            icon.dataset.lucide = 'trash-2';
                            btn.appendChild(icon);

                            actions.appendChild(label);
                            actions.appendChild(btn);

                            item.appendChild(info);
                            item.appendChild(actions);
                            listEl.appendChild(item);
                        });
                    } else {
                        listEl.innerHTML = `
                            <div class="empty-state" style="padding: 40px;">
                                <i data-lucide="package"></i>
                                <div class="empty-state-title">No Plugins Installed</div>
                                <div class="empty-state-subtitle">Install plugins from the Plugin Store to extend functionality</div>
                            </div>
                        `;
                    }
                } else {
                    // No WebSocket, show manual instructions
                    listEl.innerHTML = `
                        <div class="info-message">
                            <i data-lucide="info"></i>
                            <span>Open a vault to manage plugins</span>
                        </div>
                    `;
                }

                if (window.lucide) window.lucide.createIcons();

                // Setup toggle listeners
                const toggles = contentArea.querySelectorAll('.plugin-toggle');
                toggles.forEach(toggle => {
                    toggle.addEventListener('change', async (e) => {
                        const pluginId = toggle.dataset.pluginId;
                        const enabled = toggle.checked;

                        // Update .vault.toml
                        try {
                            await vaultApi.updatePluginConfig(vaultPath, pluginId, { enabled });
                            console.log(`Plugin ${pluginId} config updated in TOML to ${enabled}`);

                            // Immediately signal hot-reload to the backend if WebSocket is active
                            if (typeof window.request === 'function') {
                                if (enabled) {
                                    const res = await window.request('system.reload_plugin', { plugin_id: pluginId });
                                    if (res.status === 'success') {
                                        console.log(`[Hot Reload] Plugin ${pluginId} forcefully reloaded into memory.`);
                                    } else {
                                        throw new Error(res.error || 'Failed to reload plugin');
                                    }
                                } else {
                                    const res = await window.request('system.unload_plugin', { plugin_id: pluginId });
                                    if (res.status === 'success') {
                                        console.log(`[Hot Reload] Plugin ${pluginId} forcefully unloaded from memory.`);
                                    } else {
                                        throw new Error(res.error || 'Failed to unload plugin');
                                    }
                                }
                            }
                        } catch (err) {
                            console.error('Failed to update plugin config/state:', err);
                            toggle.checked = !enabled; // Revert visually
                            alert(`Failed to ${enabled ? 'enable' : 'disable'} plugin: ${err.message || err}`);
                        }
                    });
                });

                // Setup uninstall listeners
                const uninstallBtns = contentArea.querySelectorAll('.plugin-uninstall');
                uninstallBtns.forEach(btn => {
                    btn.addEventListener('click', async (e) => {
                        const pluginId = btn.dataset.pluginId;

                        if (confirm(`Are you sure you want to uninstall "${pluginId}"?`)) {
                            try {
                                if (typeof window.request === 'function') {
                                    await window.request('plugins.uninstall', { plugin_id: pluginId });
                                    // Refresh the list
                                    await showSection('plugins', vaultPath, container);
                                }
                            } catch (err) {
                                console.error('Failed to uninstall plugin:', err);
                                alert('Failed to uninstall plugin');
                            }
                        }
                    });
                });

            } catch (err) {
                console.error('Error loading plugins:', err);
                const listEl = contentArea.querySelector('#installed-plugins-list');
                listEl.innerHTML = `<div class="error-message">Failed to load plugins</div>`;
            }
            break;
    }

    if (window.lucide) {
        window.lucide.createIcons();
    }
}

function setupSettingsNavigation(container, vaultPath) {
    const navItems = container.querySelectorAll('.settings-nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', async () => {
            const section = item.dataset.section;
            await showSection(section, vaultPath, container);
        });
    });
}

