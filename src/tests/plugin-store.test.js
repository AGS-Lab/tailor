import { describe, it, expect, vi, beforeEach } from 'vitest';
import { initPluginStore } from '../vault/plugin-store.js';

describe('Plugin Store', () => {
    let checkBtn;

    beforeEach(() => {
        document.body.innerHTML = '<button id="plugin-store-btn">Store</button>';
        checkBtn = document.getElementById('plugin-store-btn');
        window.ui = { showModal: vi.fn(), closeModal: vi.fn() };
        window.request = vi.fn().mockResolvedValue({ result: { plugins: [] } });
        window.lucide = { createIcons: vi.fn() };
    });

    it('initializes button listener', () => {
        initPluginStore();
        checkBtn.click();
        expect(window.ui.showModal).toHaveBeenCalled();
    });
});
