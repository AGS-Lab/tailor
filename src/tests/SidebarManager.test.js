import { describe, it, expect, vi, beforeEach } from 'vitest';
import { SidebarManager } from '../vault/managers/SidebarManager.js';

describe('SidebarManager', () => {
    let manager;

    beforeEach(() => {
        document.body.innerHTML = `
            <div id="activity-bar-top"></div>
            <div id="side-panel">
                <div id="side-panel-title"></div>
                <div id="side-panel-content"></div>
            </div>
        `;
        window.lucide = { createIcons: vi.fn() };
        window.myLayout = { updateSize: vi.fn() };
        manager = new SidebarManager();
    });

    it('registers a view and creates a button', () => {
        manager.registerView('test-view', 'icon', 'Test Title');

        const btn = document.querySelector('.activity-action');
        expect(btn).toBeTruthy();
        expect(btn.title).toBe('Test Title');
        expect(btn.dataset.id).toBe('test-view');
    });

    it('toggles view open and closed', () => {
        manager.registerView('v1', 'icon', 'Title');
        const btn = document.querySelector('.activity-action');

        // Open
        btn.click();
        expect(manager.activeViewId).toBe('v1');
        expect(document.getElementById('side-panel').classList.contains('open')).toBe(true);
        expect(document.getElementById('side-panel-title').textContent).toBe('Title');

        // Close
        btn.click();
        expect(manager.activeViewId).toBe(null);
        expect(document.getElementById('side-panel').classList.contains('open')).toBe(false);
    });

    it('updates content when active', () => {
        manager.registerView('v1', 'icon', 'Title');
        manager.toggle('v1');

        manager.setContent('v1', '<p>New Content</p>');
        expect(document.getElementById('side-panel-content').innerHTML).toBe('<p>New Content</p>');
    });
});
