import { describe, it, expect, vi, beforeEach } from 'vitest';
import { vaultApi, pluginStoreApi, settingsApi, developerApi } from '../services/api.js';

// Mock Tauri APIs
vi.mock('@tauri-apps/api/core', () => ({
    invoke: vi.fn((cmd, args) => Promise.resolve({ cmd, args }))
}));

vi.mock('@tauri-apps/plugin-dialog', () => ({
    open: vi.fn(() => Promise.resolve('/mock/path'))
}));

// We must import the mocked modules to track their calls
import { invoke } from '@tauri-apps/api/core';
import { open } from '@tauri-apps/plugin-dialog';

describe('API Services', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    describe('vaultApi', () => {
        it('calls openVault with dialog', async () => {
            await vaultApi.openVault();
            expect(open).toHaveBeenCalledWith({ directory: true, multiple: false });
            expect(invoke).toHaveBeenCalledWith('open_vault', { vaultPath: '/mock/path' });
        });

        it('calls openVaultByPath', async () => {
            await vaultApi.openVaultByPath('/some/path');
            expect(invoke).toHaveBeenCalledWith('open_vault', { vaultPath: '/some/path' });
        });

        it('calls listVaults', async () => {
            await vaultApi.listVaults();
            expect(invoke).toHaveBeenCalledWith('list_vaults', {});
        });

        it('calls createVault', async () => {
            await vaultApi.createVault('Test Vault', '/test/path');
            expect(invoke).toHaveBeenCalledWith('create_vault', { name: 'Test Vault', path: '/test/path' });
        });
    });

    describe('settingsApi', () => {
        it('calls getGlobalSettings', async () => {
            await settingsApi.getGlobalSettings();
            expect(invoke).toHaveBeenCalledWith('get_global_settings', {});
        });

        it('calls saveGlobalSettings', async () => {
            await settingsApi.saveGlobalSettings({ theme: 'dark' });
            expect(invoke).toHaveBeenCalledWith('save_global_settings', { settings: { theme: 'dark' } });
        });
    });

    describe('pluginStoreApi', () => {
        it('calls searchPlugins', async () => {
            await pluginStoreApi.searchPlugins('test');
            expect(invoke).toHaveBeenCalledWith('search_plugins', { query: 'test', category: null });
        });
    });
});
