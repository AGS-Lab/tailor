/**
 * Dashboard Page
 * Modern ChatGPT-style dashboard with vault management
 */

import { vaultApi } from '../services/api.js';

// Track whether event listeners have been set up to prevent duplicates
let eventListenersInitialized = false;

export async function initDashboard(container) {
    container.innerHTML = `
        <div class="dashboard-container">
            <div class="dashboard-header">
                <div>
                    <h1>Dashboard</h1>
                </div>
                <div class="dashboard-header-actions">
                    <button class="btn btn-primary" id="create-vault-btn" title="Create a new vault">
                        <i data-lucide="plus"></i>
                        New Vault
                    </button>
                    <button class="btn btn-secondary" id="open-vault-btn" title="Open an existing vault">
                        <i data-lucide="folder-open"></i>
                        Open
                    </button>
                </div>
            </div>

            <div class="dashboard-stats" id="dashboard-stats">
                <!-- Stats will be loaded here -->
            </div>

            <div class="dashboard-section">
                <div class="section-header">
                    <h2>Your Vaults</h2>
                </div>
                <div class="vaults-grid" id="vaults-grid">
                    <!-- Vaults will be loaded here -->
                </div>
            </div>
        </div>
    `;

    // Initialize icons
    if (window.lucide) {
        window.lucide.createIcons();
    }

    // Load data
    await loadDashboardData(container);

    // Event listeners
    setupEventListeners(container);
}

async function loadDashboardData(container) {
    try {
        // Load stats
        await loadStats(container);

        // Load vaults list
        await loadVaults(container);
    } catch (error) {
        console.error('Error loading dashboard data:', error);
        showError(container, 'Failed to load dashboard data');
    }
}

async function loadStats(container) {
    const statsContainer = container.querySelector('#dashboard-stats');

    try {
        const stats = {
            totalVaults: 0,
            activeVaults: 0,
            totalPlugins: 0,
            totalConversations: 0,
        };

        try {
            const vaults = await vaultApi.listVaults();
            stats.totalVaults = vaults?.length || 0;
        } catch (e) {
            // API not implemented yet
        }

        statsContainer.innerHTML = `
            <div class="stat-card">
                <div class="stat-icon">
                    <i data-lucide="folder"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${stats.totalVaults}</div>
                    <div class="stat-label">Vaults</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">
                    <i data-lucide="zap"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${stats.activeVaults}</div>
                    <div class="stat-label">Active</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">
                    <i data-lucide="package"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${stats.totalPlugins}</div>
                    <div class="stat-label">Plugins</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">
                    <i data-lucide="message-square"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${stats.totalConversations}</div>
                    <div class="stat-label">Messages</div>
                </div>
            </div>
        `;

        if (window.lucide) {
            window.lucide.createIcons();
        }
    } catch (error) {
        statsContainer.innerHTML = '<div class="error-message">Failed to load stats</div>';
    }
}

async function loadVaults(container) {
    const vaultsGrid = container.querySelector('#vaults-grid');

    try {
        let vaults = [];

        try {
            vaults = await vaultApi.listVaults();
        } catch (e) {
            vaultsGrid.innerHTML = `
                <div class="empty-state" style="grid-column: 1 / -1;">
                    <i data-lucide="folder-x"></i>
                    <div class="empty-state-title">No Vaults Yet</div>
                    <div class="empty-state-subtitle">Create or open a vault to get started</div>
                </div>
            `;
            if (window.lucide) window.lucide.createIcons();
            return;
        }

        if (!vaults || vaults.length === 0) {
            vaultsGrid.innerHTML = `
                <div class="empty-state" style="grid-column: 1 / -1;">
                    <i data-lucide="folder-x"></i>
                    <div class="empty-state-title">No Vaults Yet</div>
                    <div class="empty-state-subtitle">Click "New Vault" or "Open" to get started</div>
                </div>
            `;
            if (window.lucide) window.lucide.createIcons();
            return;
        }

        vaultsGrid.innerHTML = vaults.map(vault => `
            <div class="vault-card" data-vault-path="${vault.path}">
                <div class="vault-card-header">
                    <div class="vault-icon">
                        <i data-lucide="folder"></i>
                    </div>
                    <div class="vault-info">
                        <h3>${vault.name || 'Untitled Vault'}</h3>
                        <p class="vault-path" title="${vault.path}">${vault.path}</p>
                    </div>
                </div>
                <div class="vault-stats">
                    <div class="vault-stat">
                        <div class="vault-stat-value">-</div>
                        <div class="vault-stat-label">Messages</div>
                    </div>
                    <div class="vault-stat">
                        <div class="vault-stat-value">-</div>
                        <div class="vault-stat-label">Plugins</div>
                    </div>
                    <div class="vault-stat">
                        <div class="vault-stat-value">-</div>
                        <div class="vault-stat-label">Size</div>
                    </div>
                </div>
                <div class="vault-card-footer">
                    <button class="btn btn-primary vault-action-btn" data-action="open" title="Open this vault">
                        <i data-lucide="play"></i>
                        Open
                    </button>
                    <button class="btn btn-secondary vault-action-btn" data-action="settings" title="Vault settings">
                        <i data-lucide="settings"></i>
                        Settings
                    </button>
                </div>
            </div>
        `).join('');

        if (window.lucide) {
            window.lucide.createIcons();
        }

        setupVaultCardListeners(container);
    } catch (error) {
        vaultsGrid.innerHTML = '<div class="error-message">Failed to load vaults</div>';
    }
}

function setupVaultCardListeners(container) {
    const vaultCards = container.querySelectorAll('.vault-card');
    vaultCards.forEach(card => {
        const openBtn = card.querySelector('[data-action="open"]');
        const settingsBtn = card.querySelector('[data-action="settings"]');
        const vaultPath = card.dataset.vaultPath;

        openBtn?.addEventListener('click', async (e) => {
            e.stopPropagation();
            await openVault(vaultPath);
        });

        settingsBtn?.addEventListener('click', async (e) => {
            e.stopPropagation();
            window.router.navigate(`vault-settings?path=${encodeURIComponent(vaultPath)}`);
        });
    });
}

function setupEventListeners(container) {
    // Only set up event listeners once to prevent duplicates
    if (eventListenersInitialized) {
        return;
    }
    eventListenersInitialized = true;

    const openVaultBtn = container.querySelector('#open-vault-btn');
    const createVaultBtn = container.querySelector('#create-vault-btn');

    openVaultBtn?.addEventListener('click', async () => {
        try {
            const result = await vaultApi.openVault();
            if (result) {
                await loadVaults(container);
                await loadStats(container);
            }
        } catch (error) {
            console.error('Error opening vault:', error);
            alert(`Failed to open vault: ${error}`);
        }
    });

    createVaultBtn?.addEventListener('click', async () => {
        await createNewVault(container);
    });
}

async function openVault(vaultPath) {
    try {
        await vaultApi.openVaultByPath(vaultPath);
    } catch (error) {
        console.error('Error opening vault:', error);
        alert(`Failed to open vault: ${error}`);
    }
}

async function createNewVault(container) {
    const name = prompt('Enter vault name:');
    if (!name || name.trim() === '') return;

    try {
        const parentDir = await vaultApi.selectDirectory();
        if (!parentDir) return;

        const sanitizedName = name.trim().replace(/[<>:"/\\|?*]/g, '_');
        const separator = parentDir.includes('\\') ? '\\' : '/';
        const vaultPath = parentDir.endsWith(separator)
            ? parentDir + sanitizedName
            : parentDir + separator + sanitizedName;

        await vaultApi.createVault(name.trim(), vaultPath);

        await loadVaults(container);
        await loadStats(container);

        const shouldOpen = confirm('Vault created! Open it now?');
        if (shouldOpen) {
            await vaultApi.openVaultByPath(vaultPath);
        }
    } catch (error) {
        console.error('Error creating vault:', error);
        alert(`Failed to create vault: ${error}`);
    }
}

function showError(container, message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    container.appendChild(errorDiv);
}

