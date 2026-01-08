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
        console.error('Error loading settings:', error);
        const contentArea = container.querySelector('#settings-content-area');
        contentArea.innerHTML = `<div class="error-message">Failed to load settings</div>`;
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
                    <div class="empty-state" style="padding: 40px;">
                        <i data-lucide="package"></i>
                        <div class="empty-state-title">No Plugins</div>
                        <div class="empty-state-subtitle">Install plugins from the Plugin Store</div>
                    </div>
                </div>
            `;
            if (window.lucide) window.lucide.createIcons();
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

