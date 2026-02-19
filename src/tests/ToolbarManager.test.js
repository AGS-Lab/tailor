import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ToolbarManager } from '../vault/managers/ToolbarManager.js';

describe('ToolbarManager', () => {
    let manager;

    beforeEach(() => {
        document.body.innerHTML = '<div id="activity-bar"></div>';
        window.lucide = { createIcons: vi.fn() };
        window.request = vi.fn();
        manager = new ToolbarManager();
    });

    it('creates toolbar container', () => {
        expect(document.getElementById('plugin-toolbar')).toBeTruthy();
    });

    it('registers button and handles click', async () => {
        manager.registerButton('b1', 'icon', 'Title', 'cmd.test');

        const btn = document.querySelector('.toolbar-btn');
        expect(btn).toBeTruthy();
        expect(btn.title).toBe('Title');

        await btn.click();
        expect(window.request).toHaveBeenCalledWith('cmd.test', {});
    });
});
