/**
 * Global Settings Page
 * Modern application-wide settings configuration
 */

import { settingsApi } from '../services/api.js';

export async function initSettings(container) {
    container.innerHTML = `
        <div class="settings-container">
            <div class="settings-header">
                <h1>Settings</h1>
                <p class="settings-subtitle">Manage application settings and preferences</p>
            </div>

            <div class="settings-content">
                <div class="settings-nav">
                    <div class="settings-nav-item active" data-section="general">
                        <i data-lucide="settings"></i>
                        <span>General</span>
                    </div>
                    <div class="settings-nav-item" data-section="api-keys">
                        <i data-lucide="key"></i>
                        <span>API Keys</span>
                    </div>
                    <div class="settings-nav-item" data-section="appearance">
                        <i data-lucide="palette"></i>
                        <span>Appearance</span>
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

    await loadSettings(container);
    setupSettingsNavigation(container);
}

async function loadSettings(container) {
    try {
        await showSection('general', container);
    } catch (error) {
        console.error('Error loading settings:', error);
        const contentArea = container.querySelector('#settings-content-area');
        contentArea.innerHTML = `<div class="error-message">Failed to load settings</div>`;
    }
}

async function showSection(section, container) {
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
                    <p class="settings-section-description">General application settings</p>
                    <div class="settings-group">
                        <div class="settings-item">
                            <label>App Theme</label>
                            <select class="filter-select">
                                <option>Light (Default)</option>
                                <option>Dark</option>
                                <option>System</option>
                            </select>
                        </div>
                        <div class="settings-item">
                            <label>Startup Behavior</label>
                            <select class="filter-select">
                                <option>Show Dashboard</option>
                                <option>Show Last Vault</option>
                                <option>Minimize to Tray</option>
                            </select>
                        </div>
                    </div>
                </div>
            `;
            break;

        case 'api-keys':
            contentArea.innerHTML = `
                <div class="settings-section">
                    <h2>API Keys</h2>
                    <p class="settings-section-description">Configure API keys for AI models and services</p>
                    
                    <div class="settings-group">
                        <div class="settings-item">
                            <label>OpenAI API Key</label>
                            <input type="password" class="filter-select" placeholder="sk-..." />
                            <span class="settings-item-hint">For GPT models (stored securely)</span>
                        </div>
                        <div class="settings-item">
                            <label>Anthropic API Key</label>
                            <input type="password" class="filter-select" placeholder="sk-ant-..." />
                            <span class="settings-item-hint">For Claude models (stored securely)</span>
                        </div>
                        <div class="settings-item">
                            <label>Google API Key</label>
                            <input type="password" class="filter-select" placeholder="AIza..." />
                            <span class="settings-item-hint">For Google services (stored securely)</span>
                        </div>
                    </div>
                </div>
            `;
            break;

        case 'appearance':
            contentArea.innerHTML = `
                <div class="settings-section">
                    <h2>Appearance</h2>
                    <p class="settings-section-description">Customize the look and feel</p>
                    <div class="settings-group">
                        <div class="settings-item">
                            <label>Font Size</label>
                            <input type="range" min="12" max="18" value="14" />
                            <span class="settings-item-hint">Adjust text size (12-18px)</span>
                        </div>
                        <div class="settings-item">
                            <label>Compact Mode</label>
                            <label style="display: flex; align-items: center; gap: var(--spacing-md); cursor: pointer; font-weight: normal;">
                                <input type="checkbox" /> Reduce spacing and sizing
                            </label>
                        </div>
                    </div>
                </div>
            `;
            break;
    }

    if (window.lucide) {
        window.lucide.createIcons();
    }
}

function setupSettingsNavigation(container) {
    const navItems = container.querySelectorAll('.settings-nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', async () => {
            const section = item.dataset.section;
            await showSection(section, container);
        });
    });
}

