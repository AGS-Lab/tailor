/**
 * Plugin Store Modal Module
 * 
 * Handles the plugin store button and modal for browsing,
 * installing, and managing plugins.
 */

/**
 * Initialize the plugin store button
 */
export function initPluginStore() {
    const pluginStoreBtn = document.getElementById('plugin-store-btn');
    if (!pluginStoreBtn) return;

    pluginStoreBtn.addEventListener('click', async () => {
        console.log('[PluginStore] Opening plugin store');

        if (!window.ui || !window.ui.showModal) {
            alert('Plugin store is loading...');
            return;
        }

        // Build modal HTML
        const modalHtml = `
            <div class="plugin-store-modal">
                <div class="plugin-tabs">
                    <button class="plugin-tab active" data-tab="installed">
                        <i data-lucide="package"></i>
                        Installed Plugins
                    </button>
                    <button class="plugin-tab" data-tab="store">
                        <i data-lucide="shopping-bag"></i>
                        Plugin Store
                    </button>
                </div>
                
                <div id="plugin-tab-content" class="plugin-tab-content">
                    <div class="loading-indicator" style="text-align: center; padding: 40px;">
                        <i data-lucide="loader" class="spinning"></i>
                        <span>Loading plugins...</span>
                    </div>
                </div>
                
                <div id="plugin-restart-banner" class="plugin-restart-banner" style="display: none;">
                    <i data-lucide="alert-circle"></i>
                    <span>Restart vault to apply changes</span>
                    <button class="btn btn-primary" id="restart-vault-btn">
                        <i data-lucide="refresh-cw"></i>
                        Restart Vault
                    </button>
                </div>
            </div>
        `;

        window.ui.showModal('Plugin Manager', modalHtml, '700px');

        // Init icons and tabs
        setTimeout(() => {
            if (window.lucide) window.lucide.createIcons();
            initPluginTabs();
            loadInstalledPlugins();
        }, 50);
    });
}

/**
 * Setup tab switching
 */
function initPluginTabs() {
    const tabs = document.querySelectorAll('.plugin-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            const tabName = tab.dataset.tab;
            if (tabName === 'installed') {
                loadInstalledPlugins();
            } else {
                loadPluginStore();
            }
        });
    });
}

/**
 * Load installed plugins list
 */
async function loadInstalledPlugins() {
    const content = document.getElementById('plugin-tab-content');
    if (!content) return;

    content.innerHTML = '<div class="loading-indicator" style="text-align: center; padding: 40px;"><i data-lucide="loader" class="spinning"></i> Loading...</div>';
    if (window.lucide) window.lucide.createIcons();

    try {
        const response = await window.request('plugins.list', {});
        console.log('[PluginStore] plugins.list response:', response);

        const result = response.result || response;
        const plugins = result.plugins || [];

        if (plugins.length === 0) {
            content.innerHTML = `
                <div class="empty-state" style="padding: 40px; text-align: center;">
                    <i data-lucide="package-x" style="width: 48px; height: 48px; margin-bottom: 16px; color: var(--text-disabled);"></i>
                    <h3 style="margin: 0 0 8px 0; color: var(--text-primary);">No Plugins Installed</h3>
                    <p style="color: var(--text-secondary); margin: 0;">Browse the Plugin Store to find and install plugins</p>
                </div>
            `;
        } else {
            content.innerHTML = '';
            const listContainer = document.createElement('div');
            listContainer.className = 'installed-plugins-list';

            plugins.forEach(plugin => {
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
                desc.className = 'plugin-desc';
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
                btn.title = 'Uninstall';

                const icon = document.createElement('i');
                icon.dataset.lucide = 'trash-2';
                btn.appendChild(icon);

                actions.appendChild(label);
                actions.appendChild(btn);

                item.appendChild(info);
                item.appendChild(actions);
                listContainer.appendChild(item);
            });
            content.appendChild(listContainer);
        }

        if (window.lucide) window.lucide.createIcons();
        setupInstalledPluginListeners();
    } catch (e) {
        console.error('Failed to load plugins:', e);
        content.innerHTML = '<div class="error-message">Failed to load plugins</div>';
    }
}

/**
 * Setup listeners for installed plugins
 */
function setupInstalledPluginListeners() {
    // Toggle switches
    document.querySelectorAll('.plugin-toggle').forEach(toggle => {
        toggle.addEventListener('change', async (e) => {
            const pluginId = toggle.dataset.pluginId;
            const enabled = toggle.checked;

            try {
                await window.request('plugins.toggle', { plugin_id: pluginId, enabled });
                showRestartBanner();
            } catch (err) {
                console.error('Toggle failed:', err);
                toggle.checked = !enabled;
            }
        });
    });

    // Uninstall buttons
    document.querySelectorAll('.plugin-uninstall').forEach(btn => {
        btn.addEventListener('click', async () => {
            const pluginId = btn.dataset.pluginId;
            if (!confirm(`Uninstall "${pluginId}"?`)) return;

            try {
                await window.request('plugins.uninstall', { plugin_id: pluginId });
                showRestartBanner();
                loadInstalledPlugins();
            } catch (err) {
                console.error('Uninstall failed:', err);
                alert('Failed to uninstall plugin');
            }
        });
    });
}

/**
 * Load plugin store from registry
 */
async function loadPluginStore() {
    const content = document.getElementById('plugin-tab-content');
    if (!content) return;

    content.innerHTML = '<div class="loading-indicator" style="text-align: center; padding: 40px;"><i data-lucide="loader" class="spinning"></i> Loading store...</div>';
    if (window.lucide) window.lucide.createIcons();

    try {
        // Fetch plugin registry
        const registryRes = await fetch('/plugin-registry.json');
        const registry = await registryRes.json();
        const availablePlugins = registry.plugins || [];

        // Get installed plugins
        const installedRes = await window.request('plugins.list', {});
        const installedData = installedRes.result || installedRes;
        const installedIds = (installedData.plugins || []).map(p => p.id);

        content.innerHTML = '';
        const gridContainer = document.createElement('div');
        gridContainer.className = 'plugin-store-grid';

        availablePlugins.forEach(plugin => {
            const isInstalled = installedIds.includes(plugin.id);

            const card = document.createElement('div');
            card.className = 'plugin-card';
            card.dataset.pluginId = plugin.id || '';

            const header = document.createElement('div');
            header.className = 'plugin-card-header';

            const iconWrap = document.createElement('div');
            iconWrap.className = 'plugin-icon';
            const icon = document.createElement('i');
            icon.dataset.lucide = plugin.icon || 'package';
            iconWrap.appendChild(icon);

            const meta = document.createElement('div');
            meta.className = 'plugin-meta';
            const title = document.createElement('h4');
            title.textContent = plugin.name || '';
            const author = document.createElement('span');
            author.className = 'plugin-author';
            author.textContent = `by ${plugin.author || 'Unknown'}`;
            meta.appendChild(title);
            meta.appendChild(author);

            header.appendChild(iconWrap);
            header.appendChild(meta);

            const desc = document.createElement('p');
            desc.className = 'plugin-desc';
            desc.textContent = plugin.description || '';

            const footer = document.createElement('div');
            footer.className = 'plugin-card-footer';

            const stats = document.createElement('div');
            stats.className = 'plugin-stats';
            stats.innerHTML = `<span><i data-lucide="star"></i> ${plugin.stars || 0}</span><span><i data-lucide="download"></i> ${plugin.installs || 0}</span>`;

            footer.appendChild(stats);

            if (isInstalled) {
                const btn = document.createElement('button');
                btn.className = 'btn btn-success btn-sm';
                btn.disabled = true;
                btn.innerHTML = '<i data-lucide="check"></i> Installed';
                footer.appendChild(btn);
            } else {
                const btn = document.createElement('button');
                btn.className = 'btn btn-primary btn-sm plugin-install-btn';
                btn.dataset.pluginId = plugin.id || '';
                btn.dataset.downloadUrl = plugin.download_url || '';
                btn.innerHTML = '<i data-lucide="download"></i> Install';
                footer.appendChild(btn);
            }

            card.appendChild(header);
            card.appendChild(desc);
            card.appendChild(footer);
            gridContainer.appendChild(card);
        });
        content.appendChild(gridContainer);

        if (window.lucide) window.lucide.createIcons();
        setupStoreListeners();
    } catch (e) {
        console.error('Failed to load store:', e);
        content.innerHTML = '<div class="error-message">Failed to load plugin store</div>';
    }
}

/**
 * Setup listeners for store install buttons
 */
function setupStoreListeners() {
    document.querySelectorAll('.plugin-install-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const pluginId = btn.dataset.pluginId;
            const downloadUrl = btn.dataset.downloadUrl;

            btn.disabled = true;
            btn.innerHTML = '<i data-lucide="loader" class="spinning"></i> Installing...';
            if (window.lucide) window.lucide.createIcons();

            try {
                const response = await window.request('plugins.install', {
                    plugin_id: pluginId,
                    download_url: downloadUrl
                });
                const result = response.result || response;

                if (result.status === 'success' || result.status === 'already_exists') {
                    btn.innerHTML = '<i data-lucide="check"></i> Installed';
                    btn.classList.remove('btn-primary');
                    btn.classList.add('btn-success');
                    showRestartBanner();
                } else {
                    throw new Error(result.message || 'Install failed');
                }
            } catch (err) {
                console.error('Install failed:', err);
                btn.innerHTML = '<i data-lucide="download"></i> Install';
                btn.disabled = false;
                alert(`Failed to install: ${err.message || err}`);
            }

            if (window.lucide) window.lucide.createIcons();
        });
    });
}

/**
 * Show restart banner
 */
function showRestartBanner() {
    const banner = document.getElementById('plugin-restart-banner');
    if (banner) {
        banner.style.display = 'flex';
        if (window.lucide) window.lucide.createIcons();

        const restartBtn = document.getElementById('restart-vault-btn');
        if (restartBtn && !restartBtn._hasListener) {
            restartBtn._hasListener = true;
            restartBtn.addEventListener('click', async () => {
                restartBtn.disabled = true;
                restartBtn.innerHTML = '<i data-lucide="loader" class="spinning"></i> Restarting...';
                if (window.lucide) window.lucide.createIcons();

                try {
                    await window.request('system.restart_vault', {});
                    banner.style.display = 'none';
                    window.ui.closeModal();
                    if (window.log) window.log('Vault restarted successfully', 'info');
                } catch (err) {
                    console.error('Restart failed:', err);
                    restartBtn.innerHTML = '<i data-lucide="refresh-cw"></i> Restart Vault';
                    restartBtn.disabled = false;
                    if (window.lucide) window.lucide.createIcons();
                }
            });
        }
    }
}
