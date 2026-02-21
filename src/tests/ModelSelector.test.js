import { describe, it, expect, beforeEach, vi } from 'vitest';
import { getModelSelector } from '../vault/chat/ModelSelector.js';
import { request } from '../vault/connection.js';

vi.mock('../vault/connection.js', () => ({
    request: vi.fn()
}));

// Mock window.ui.showModal
Object.defineProperty(window, 'ui', {
    value: { showModal: vi.fn(), closeModal: vi.fn() },
    writable: true
});

describe('ModelSelector.js', () => {
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

    it('initializes and requests categories', async () => {
        request.mockResolvedValueOnce({
            result: { status: 'success', categories_info: { 'fast': { name: 'Fast' } }, configured: {} }
        });
        request.mockResolvedValueOnce({
            result: { status: 'success', models: {} }
        });

        const selector = getModelSelector();
        await selector.init(container);

        expect(request).toHaveBeenCalledWith('settings.get_model_categories', {});
        expect(request).toHaveBeenCalledWith('settings.get_available_models', {});

        // Assert DOM presence
        expect(container.innerHTML).toContain('Fast');
    });

    it('toggles dropdown visibility', async () => {
        request.mockResolvedValueOnce({
            result: { status: 'success', categories_info: { 'fast': { name: 'Fast' } }, configured: {} }
        });
        request.mockResolvedValueOnce({
            result: { status: 'success', models: {} }
        });

        const selector = getModelSelector();
        await selector.init(container);

        const btn = container.querySelector('#model-selector-btn');
        const dropdown = container.querySelector('#model-selector-dropdown');

        expect(dropdown.classList.contains('hidden')).toBe(true);
        btn.click();
        expect(dropdown.classList.contains('hidden')).toBe(false);
    });

    it('opens advanced picker when click More models', async () => {
        request.mockResolvedValueOnce({
            result: { status: 'success', categories_info: { 'fast': { name: 'Fast' } }, configured: {} }
        });
        request.mockResolvedValueOnce({
            result: { status: 'success', models: {} }
        });

        const selector = getModelSelector();
        await selector.init(container);

        const advancedBtn = container.querySelector('#model-selector-advanced');
        advancedBtn.click();

        expect(window.ui.showModal).toHaveBeenCalledWith('Select Model', expect.any(String), '700px');
    });
});
