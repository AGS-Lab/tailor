import { describe, it, expect, beforeEach, vi } from 'vitest';
import { initDashboard } from '../pages/dashboard.js';
import { vaultApi } from '../services/api.js';

vi.mock('../services/api.js', () => ({
    vaultApi: {
        listVaults: vi.fn(),
        openVault: vi.fn(),
        createVault: vi.fn(),
        openVaultByPath: vi.fn(),
        selectDirectory: vi.fn()
    }
}));

// Mock global fetch
global.fetch = vi.fn(() =>
    Promise.resolve({
        json: () => Promise.resolve({ plugins: [] })
    })
);

describe('dashboard.js', () => {
    let container;

    beforeEach(() => {
        container = document.createElement('div');
        document.body.appendChild(container);
        vi.clearAllMocks();

        window.lucide = { createIcons: vi.fn() };
        window.router = { navigate: vi.fn() };
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    it('renders empty state when no vaults', async () => {
        vaultApi.listVaults.mockResolvedValue([]);

        await initDashboard(container);

        expect(container.innerHTML).toContain('No Vaults Yet');
    });

    it('renders vaults grid when vaults exist', async () => {
        vaultApi.listVaults.mockResolvedValue([
            { name: 'My Vault', path: '/test/vault' }
        ]);

        try {
            await initDashboard(container);
            const grid = container.querySelector('#vaults-grid');
            if (!grid) console.error("GRID IS NULL. HTML: ", container.innerHTML);
            expect(grid.innerHTML).toContain('My Vault');
            expect(grid.innerHTML).toContain('/test/vault');
        } catch (e) {
            console.error("DASHBOARD TEST ERROR:", e);
            throw e;
        }
    });

    it('handles open vault click', async () => {
        vaultApi.listVaults.mockResolvedValue([
            { name: 'My Vault', path: '/test/vault' }
        ]);

        await initDashboard(container);

        const openBtn = container.querySelector('.vault-open-btn');
        openBtn.click();

        expect(vaultApi.openVaultByPath).toHaveBeenCalledWith('/test/vault');
    });

    it('handles vault settings click navigating to vault-settings page', async () => {
        vaultApi.listVaults.mockResolvedValue([
            { name: 'Settings Vault', path: '/test/settings_vault' }
        ]);

        await initDashboard(container);

        const settingsBtn = container.querySelector('.vault-settings-btn');
        settingsBtn.click();

        expect(window.router.navigate).toHaveBeenCalledWith('vault-settings?path=' + encodeURIComponent('/test/settings_vault'));
    });
});
