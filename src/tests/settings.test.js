import { describe, it, expect, beforeEach, vi } from 'vitest';
import { initSettings } from '../pages/settings.js';
import { settingsApi } from '../services/api.js';

vi.mock('../services/api.js', () => ({
    settingsApi: {
        getGlobalSettings: vi.fn(),
        saveGlobalSettings: vi.fn()
    }
}));

// Mock window.location.reload
Object.defineProperty(window, 'location', {
    value: { reload: vi.fn() },
    writable: true
});

global.localStorage = {
    getItem: vi.fn(),
    setItem: vi.fn(),
    removeItem: vi.fn()
};

describe('settings.js', () => {
    let container;

    beforeEach(() => {
        container = document.createElement('div');
        document.body.appendChild(container);
        vi.clearAllMocks();
        window.lucide = { createIcons: vi.fn() };
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    it('renders settings layout and general section', async () => {
        settingsApi.getGlobalSettings.mockResolvedValue({ theme: 'dark' });

        await initSettings(container);

        expect(container.innerHTML).toContain('Settings');
        expect(container.innerHTML).toContain('General');
        expect(settingsApi.getGlobalSettings).toHaveBeenCalled();

        const contentArea = container.querySelector('#settings-content-area');
        expect(contentArea.innerHTML).toContain('App Theme');
    });

    it('changes theme and saves global settings', async () => {
        settingsApi.getGlobalSettings.mockResolvedValue({ theme: 'light' });
        await initSettings(container);

        const themeSelect = container.querySelector('#global-theme-select');
        themeSelect.value = 'dark';
        themeSelect.dispatchEvent(new Event('change'));

        await new Promise(resolve => setTimeout(resolve, 0));

        expect(settingsApi.saveGlobalSettings).toHaveBeenCalledWith({ theme: 'dark' });
        expect(window.location.reload).toHaveBeenCalled();
    });

    it('navigates between sections', async () => {
        settingsApi.getGlobalSettings.mockResolvedValue({});
        await initSettings(container);

        const apiKeysNav = container.querySelector('[data-section="api-keys"]');
        apiKeysNav.click();

        // As of the current component implementation, the API keys section might be rendering empty or just activating the tab
        // Let's assert the nav item became active
        const apiKeysTab = container.querySelector('[data-section="api-keys"]');
        expect(apiKeysTab.classList.contains('active')).toBe(true);
    });
});
