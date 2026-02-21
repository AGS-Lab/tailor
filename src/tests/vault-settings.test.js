import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { initVaultSettings } from '../pages/vault-settings.js';
import { vaultApi } from '../services/api.js';

// Mock the vaultApi
vi.mock('../services/api.js', () => ({
    settingsApi: {},
    vaultApi: {
        updatePluginConfig: vi.fn()
    }
}));

describe('vault-settings.js', () => {
    let container;

    beforeEach(() => {
        container = document.createElement('div');
        document.body.appendChild(container);
        vi.clearAllMocks();
        window.lucide = { createIcons: vi.fn() };

        Object.defineProperty(window, 'location', {
            value: { search: '?path=/mock/vault' },
            writable: true
        });

        // Mock window.request for plugins list
        window.request = vi.fn().mockResolvedValue({
            plugins: [
                { id: 'plugin_a', name: 'Plugin A', version: '1.0.0', enabled: true },
                { id: 'plugin_b', name: 'Plugin B', version: '2.0.0', enabled: false }
            ]
        });

        // To mock confirm prompts
        window.confirm = vi.fn(() => true);
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    it('renders error if no vault path in URL', async () => {
        Object.defineProperty(window, 'location', {
            value: { search: '' },
            writable: true
        });

        await initVaultSettings(container);
        expect(container.innerHTML).toContain('No vault path provided');
    });

    it('renders vault settings layout', async () => {
        await initVaultSettings(container);

        expect(container.innerHTML).toContain('Vault Settings');
        expect(container.innerHTML).toContain('/mock/vault');
        expect(container.innerHTML).toContain('General');

        const contentArea = container.querySelector('#settings-content-area');
        expect(contentArea.innerHTML).toContain('Vault Name');
    });

    it('navigates to plugins section and renders plugins list', async () => {
        await initVaultSettings(container);

        const pluginsNav = container.querySelector('[data-section="plugins"]');
        pluginsNav.click();

        await new Promise(resolve => setTimeout(resolve, 0));

        const contentArea = container.querySelector('#settings-content-area');
        expect(contentArea.innerHTML).toContain('Plugin A');
        expect(contentArea.innerHTML).toContain('Plugin B');
        expect(window.request).toHaveBeenCalledWith('plugins.list', {});
    });

    it('allows toggling a plugin enable/disable state', async () => {
        await initVaultSettings(container);
        const pluginsNav = container.querySelector('[data-section="plugins"]');
        pluginsNav.click();

        await new Promise(resolve => setTimeout(resolve, 0));

        // Get checkout input for plugin A
        const toggleA = container.querySelector('.plugin-toggle[data-plugin-id="plugin_a"]');

        // Simulate change event to disable it
        toggleA.checked = false;
        toggleA.dispatchEvent(new Event('change'));

        await new Promise(resolve => setTimeout(resolve, 0));

        expect(vaultApi.updatePluginConfig).toHaveBeenCalledWith('/mock/vault', 'plugin_a', { enabled: false });
    });
});
