/**
 * Dashboard Page
 * Modern action-oriented dashboard with vault management
 */

import { vaultApi } from '../services/api.js';

// Track whether event listeners have been set up to prevent duplicates
let eventListenersInitialized = false;
let currentFilter = 'all';

export async function initDashboard(container) {
    container.innerHTML = `
        <div class="dashboard-container">
            <!-- Welcome Header -->
            <div class="dashboard-header">
                <div class="dashboard-header-content">
                    <h1>Welcome to Tailor</h1>
                    <p class="dashboard-tagline">Your AI-powered assistant workspace</p>
                </div>
                <div class="dashboard-header-actions">
                    <button class="btn btn-primary btn-lg" id="create-vault-btn" title="Create a new vault">
                        <i data-lucide="plus"></i>
                        New Vault
                    </button>
                    <button class="btn btn-secondary btn-lg" id="open-vault-btn" title="Open an existing vault folder">
                        <i data-lucide="folder-open"></i>
                        Open Existing
                    </button>
                </div>
            </div>

            <!-- Your Vaults Section -->
            <div class="dashboard-section vaults-section">
                <div class="section-header">
                    <h2>Your Vaults</h2>
                    <div class="vault-filters" id="vault-filters">
                        <button class="filter-btn active" data-filter="all">All</button>
                        <button class="filter-btn" data-filter="recent">Recent</button>
                        <button class="filter-btn" data-filter="name">A-Z</button>
                    </div>
                </div>
                <div class="vaults-grid" id="vaults-grid">
                    <!-- Vaults will be loaded here -->
                </div>
            </div>

            <!-- Quick Actions Section -->
            <div class="dashboard-section quick-actions-section">
                <div class="section-header">
                    <h2>Quick Actions</h2>
                </div>
                <div class="action-cards-grid">
                    <!-- Plugins Card -->
                    <div class="action-card" id="plugins-card">
                        <div class="action-card-icon">
                            <i data-lucide="puzzle"></i>
                        </div>
                        <div class="action-card-content">
                            <h3>Plugins</h3>
                            <p>Extend Tailor's capabilities with powerful plugins</p>
                            <span class="action-card-note">
                                <i data-lucide="info"></i>
                                Browse available plugins here. To install and enable them, open a vault first.
                            </span>
                        </div>
                        <button class="btn btn-secondary action-card-btn" id="browse-plugins-btn">
                            Browse Plugins
                            <i data-lucide="arrow-right"></i>
                        </button>
                    </div>
                </div>
            </div>

            <!-- Getting Started Section -->
            <div class="dashboard-section getting-started-section">
                <div class="section-header">
                    <h2>Getting Started</h2>
                    <a href="https://tailor.agslab.co.in/" target="_blank" rel="noopener noreferrer" class="btn btn-secondary docs-link-btn">
                        <i data-lucide="external-link"></i>
                        View Documentation
                    </a>
                </div>
                
                <div class="guide-cards">
                    <div class="guide-card">
                        <div class="guide-icon">
                            <i data-lucide="folder"></i>
                        </div>
                        <h4>Vaults</h4>
                        <p>Vaults are isolated workspaces for your conversations. Each vault has its own settings, plugins, and chat history.</p>
                    </div>
                    <div class="guide-card">
                        <div class="guide-icon">
                            <i data-lucide="puzzle"></i>
                        </div>
                        <h4>Plugins</h4>
                        <p>Extend Tailor with plugins. Browse the registry, then install and configure plugins within each vault.</p>
                    </div>
                    <div class="guide-card">
                        <div class="guide-icon">
                            <i data-lucide="settings"></i>
                        </div>
                        <h4>Settings</h4>
                        <p>Configure your API keys, models, and preferences in the global settings or per-vault settings.</p>
                    </div>
                    <div class="guide-card">
                        <div class="guide-icon">
                            <i data-lucide="message-circle"></i>
                        </div>
                        <h4>Conversations</h4>
                        <p>View and manage your chat history. Conversations are saved per-vault and can be exported.</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Plugins Modal -->
        <div class="modal-overlay" id="plugins-modal" style="display: none;">
            <div class="modal-container plugins-modal-container">
                <div class="modal-header">
                    <h2>Browse Plugins</h2>
                    <button class="modal-close-btn" id="close-plugins-modal">
                        <i data-lucide="x"></i>
                    </button>
                </div>
                <div class="modal-body" id="plugins-modal-body">
                    <!-- Plugins will be loaded here -->
                </div>
            </div>
        </div>
    `;

    // Initialize icons
    if (window.lucide) {
        window.lucide.createIcons();
    }

    // Load data
    await loadVaults(container);

    // Event listeners
    setupEventListeners(container);
}

async function loadVaults(container) {
    const vaultsGrid = container.querySelector('#vaults-grid');

    try {
        let vaults = [];

        try {
            vaults = await vaultApi.listVaults();
        } catch (e) {
            renderEmptyState(vaultsGrid);
            return;
        }

        if (!vaults || vaults.length === 0) {
            renderEmptyState(vaultsGrid);
            return;
        }

        // Apply current filter
        let sortedVaults = [...vaults];
        if (currentFilter === 'name') {
            sortedVaults.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
        } else if (currentFilter === 'recent') {
            // Sort by lastOpened if available, otherwise keep order
            sortedVaults.sort((a, b) => {
                const dateA = a.lastOpened ? new Date(a.lastOpened) : new Date(0);
                const dateB = b.lastOpened ? new Date(b.lastOpened) : new Date(0);
                return dateB - dateA;
            });
        }

        vaultsGrid.innerHTML = '';
        sortedVaults.forEach((vault, index) => {
            const card = document.createElement('div');
            card.className = 'vault-card';
            card.dataset.vaultPath = vault.path || '';
            card.style.animationDelay = `${index * 0.05}s`;

            const header = document.createElement('div');
            header.className = 'vault-card-header';

            const iconWrap = document.createElement('div');
            iconWrap.className = 'vault-icon';
            const icon = document.createElement('i');
            icon.dataset.lucide = 'folder';
            iconWrap.appendChild(icon);

            const info = document.createElement('div');
            info.className = 'vault-info';
            const title = document.createElement('h3');
            title.textContent = vault.name || 'Untitled Vault';
            const pathTxt = document.createElement('p');
            pathTxt.className = 'vault-path';
            pathTxt.title = vault.path || '';
            pathTxt.textContent = truncatePath(vault.path);

            info.appendChild(title);
            info.appendChild(pathTxt);

            header.appendChild(iconWrap);
            header.appendChild(info);

            const actions = document.createElement('div');
            actions.className = 'vault-card-actions';

            const openBtn = document.createElement('button');
            openBtn.className = 'btn btn-primary vault-open-btn';
            openBtn.dataset.action = 'open';
            openBtn.title = 'Open this vault';
            openBtn.innerHTML = '<i data-lucide="play-circle"></i> Open Vault';

            const settingsBtn = document.createElement('button');
            settingsBtn.className = 'btn-icon vault-settings-btn';
            settingsBtn.dataset.action = 'settings';
            settingsBtn.title = 'Vault settings';
            settingsBtn.innerHTML = '<i data-lucide="settings"></i>';

            actions.appendChild(openBtn);
            actions.appendChild(settingsBtn);

            card.appendChild(header);
            card.appendChild(actions);
            vaultsGrid.appendChild(card);
        });

        if (window.lucide) {
            window.lucide.createIcons();
        }

        setupVaultCardListeners(container);
    } catch (error) {
        console.error("DEBUG DASHBOARD ERROR:", error);
        if (vaultsGrid) vaultsGrid.innerHTML = '<div class="error-message">Failed to load vaults</div>';
    }
}

function renderEmptyState(vaultsGrid) {
    vaultsGrid.innerHTML = `
        <div class="empty-state-card">
            <div class="empty-state-icon">
                <i data-lucide="folder-plus"></i>
            </div>
            <h3>No Vaults Yet</h3>
            <p>Create your first vault to start chatting with AI assistants, or open an existing vault folder.</p>
            <div class="empty-state-actions">
                <button class="btn btn-primary" id="empty-create-vault-btn">
                    <i data-lucide="plus"></i>
                    Create Your First Vault
                </button>
                <button class="btn btn-secondary" id="empty-open-vault-btn">
                    <i data-lucide="folder-open"></i>
                    Open Existing
                </button>
            </div>
        </div>
    `;
    if (window.lucide) window.lucide.createIcons();

    // Add listeners for empty state buttons
    const emptyCreateBtn = vaultsGrid.querySelector('#empty-create-vault-btn');
    const emptyOpenBtn = vaultsGrid.querySelector('#empty-open-vault-btn');

    emptyCreateBtn?.addEventListener('click', async () => {
        await createNewVault(vaultsGrid.closest('.dashboard-container'));
    });

    emptyOpenBtn?.addEventListener('click', async () => {
        try {
            const result = await vaultApi.openVault();
            if (result) {
                await loadVaults(vaultsGrid.closest('.dashboard-container'));
            }
        } catch (error) {
            console.error('Error opening vault:', error);
            alert(`Failed to open vault: ${error}`);
        }
    });
}

function truncatePath(path, maxLength = 40) {
    if (!path || path.length <= maxLength) return path;
    const parts = path.split(/[/\\]/);
    if (parts.length <= 3) return path;
    return `...${path.slice(-maxLength)}`;
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

        // Also allow clicking the whole card to open
        card.addEventListener('click', async (e) => {
            if (!e.target.closest('button')) {
                await openVault(vaultPath);
            }
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
    const browsePluginsBtn = container.querySelector('#browse-plugins-btn');
    const pluginsModal = container.querySelector('#plugins-modal');
    const closePluginsModalBtn = container.querySelector('#close-plugins-modal');
    const filterBtns = container.querySelectorAll('.filter-btn');

    openVaultBtn?.addEventListener('click', async () => {
        try {
            const result = await vaultApi.openVault();
            if (result) {
                await loadVaults(container);
            }
        } catch (error) {
            console.error('Error opening vault:', error);
            alert(`Failed to open vault: ${error}`);
        }
    });

    createVaultBtn?.addEventListener('click', async () => {
        await createNewVault(container);
    });

    // Filter buttons
    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            filterBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFilter = btn.dataset.filter;
            loadVaults(container);
        });
    });

    // Plugins modal
    browsePluginsBtn?.addEventListener('click', () => {
        openPluginsModal(container);
    });

    closePluginsModalBtn?.addEventListener('click', () => {
        pluginsModal.style.display = 'none';
    });

    pluginsModal?.addEventListener('click', (e) => {
        if (e.target === pluginsModal) {
            pluginsModal.style.display = 'none';
        }
    });
}

async function openPluginsModal(container) {
    const modal = container.querySelector('#plugins-modal');
    const modalBody = container.querySelector('#plugins-modal-body');

    modal.style.display = 'flex';
    modalBody.innerHTML = '<div class="loading-state"><i data-lucide="loader" class="loading-spinner"></i> Loading plugins...</div>';
    if (window.lucide) window.lucide.createIcons();

    try {
        // Fetch plugin registry
        const response = await fetch('/plugin-registry.json');
        const registry = await response.json();

        if (!registry.plugins || registry.plugins.length === 0) {
            modalBody.innerHTML = `
                <div class="empty-plugins-state">
                    <i data-lucide="puzzle"></i>
                    <p>No plugins available yet.</p>
                </div>
            `;
        } else {
            modalBody.innerHTML = `
                <div class="plugins-info-banner">
                    <i data-lucide="info"></i>
                    <p>These plugins can be installed within individual vaults. Open a vault and go to Settings → Plugin Store to install.</p>
                </div>
            `;
            const list = document.createElement('div');
            list.className = 'plugins-list';
            registry.plugins.forEach(plugin => {
                const item = document.createElement('div');
                item.className = 'plugin-browse-item';

                const iconWrap = document.createElement('div');
                iconWrap.className = 'plugin-browse-icon';
                const icon = document.createElement('i');
                icon.dataset.lucide = plugin.icon || 'puzzle';
                iconWrap.appendChild(icon);

                const info = document.createElement('div');
                info.className = 'plugin-browse-info';

                const title = document.createElement('h4');
                title.textContent = plugin.name || '';
                const desc = document.createElement('p');
                desc.textContent = plugin.description || '';

                const meta = document.createElement('div');
                meta.className = 'plugin-meta';

                const authorSpan = document.createElement('span');
                authorSpan.innerHTML = `<i data-lucide="user"></i> ${plugin.author || 'Unknown'}`;

                const versionSpan = document.createElement('span');
                versionSpan.innerHTML = `<i data-lucide="tag"></i> v${plugin.version || '0.0.0'}`;

                meta.appendChild(authorSpan);
                meta.appendChild(versionSpan);

                if (plugin.homepage) {
                    const link = document.createElement('a');
                    link.href = plugin.homepage;
                    link.target = '_blank';
                    link.rel = 'noopener noreferrer';
                    link.innerHTML = '<i data-lucide="external-link"></i> View Source';
                    meta.appendChild(link);
                }

                info.appendChild(title);
                info.appendChild(desc);
                info.appendChild(meta);

                item.appendChild(iconWrap);
                item.appendChild(info);
                list.appendChild(item);
            });
            modalBody.appendChild(list);
        }

        if (window.lucide) window.lucide.createIcons();
    } catch (error) {
        modalBody.innerHTML = `
            <div class="error-message">
                Failed to load plugins. Please try again later.
            </div>
        `;
    }
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

        const shouldOpen = confirm('Vault created! Open it now?');
        if (shouldOpen) {
            await vaultApi.openVaultByPath(vaultPath);
        }
    } catch (error) {
        console.error('Error creating vault:', error);
        alert(`Failed to create vault: ${error}`);
    }
}
