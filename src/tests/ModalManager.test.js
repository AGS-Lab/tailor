import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ModalManager } from '../vault/managers/ModalManager.js';

describe('ModalManager', () => {
    let manager;

    beforeEach(() => {
        document.body.innerHTML = ''; // Start clean
        window.lucide = { createIcons: vi.fn() };
        manager = new ModalManager();
    });

    it('creates overlay on first use', () => {
        expect(document.getElementById('plugin-modal-overlay')).toBeTruthy();
    });

    it('shows modal with content', () => {
        manager.show('My Title', '<p>Hello</p>');

        const overlay = document.getElementById('plugin-modal-overlay');
        expect(overlay.style.display).toBe('flex');
        expect(document.getElementById('modal-title').textContent).toBe('My Title');
        expect(document.getElementById('modal-content').innerHTML).toBe('<p>Hello</p>');
        expect(manager.isOpen).toBe(true);
    });

    it('closes modal', () => {
        manager.show('Title', 'Content');
        manager.close();

        const overlay = document.getElementById('plugin-modal-overlay');
        expect(overlay.style.display).toBe('none');
        expect(manager.isOpen).toBe(false);
    });
});
