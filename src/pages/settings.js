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

    const globalSettings = await settingsApi.getGlobalSettings();

    switch (section) {
        case 'general':
            contentArea.innerHTML = `
                <div class="settings-section">
                    <h2>General</h2>
                    <p class="settings-section-description">General application settings</p>
                    <div class="settings-group">
                        <div class="settings-item">
                            <label>App Theme</label>
                            <select class="filter-select" id="global-theme-select">
                                <option value="light" ${globalSettings.theme === 'light' ? 'selected' : ''}>Light</option>
                                <option value="dark" ${globalSettings.theme === 'dark' ? 'selected' : ''}>Dark</option>
                                <option value="system" ${globalSettings.theme === 'system' ? 'selected' : ''}>System</option>
                            </select>
                        </div>
                    </div>
                </div>
            `;

            // Attach listener
            const themeSelect = contentArea.querySelector('#global-theme-select');
            themeSelect.addEventListener('change', async (e) => {
                const newTheme = e.target.value;
                globalSettings.theme = newTheme;
                await settingsApi.saveGlobalSettings(globalSettings);

                // Apply immediately
                // We need to import applyTheme dynamically or dispatch event?
                // For now, let's just reload or alert. 
                // Actually, themes.js handles application if we call it.
                // But themes.js is separate.

                // Let's just reload for now or dispatch event that themes.js listens to?
                // Better: Just update localStorage too for sync.
                if (newTheme !== 'system') {
                    localStorage.setItem('tailor-theme', newTheme === 'dark' ? 'tokyo-night' : 'default');
                    // Force reload to apply theme changes cross-module
                    window.location.reload();
                } else {
                    window.location.reload();
                }
            });
            break;

        case 'api-keys':
            // ... (keep existing or implement fully)
            // For MVP, just theme syncing is priority
            break;

        case 'appearance':
            // ...
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

