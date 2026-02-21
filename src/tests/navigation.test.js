import { describe, it, expect, beforeEach, vi } from 'vitest';
import { createNavigation, initNavigation } from '../components/navigation.js';

describe('navigation.js', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
        window.router = {
            navigate: vi.fn()
        };
        window.lucide = {
            createIcons: vi.fn()
        };
    });

    it('creates navigation HTML', () => {
        const html = createNavigation();
        expect(html).toContain('<nav class="main-nav">');
        expect(html).toContain('Dashboard');
        expect(html).toContain('Themes');
        expect(html).toContain('Settings');
    });

    it('initializes click handlers and active states', () => {
        document.body.innerHTML = createNavigation();
        initNavigation();

        const dashItem = document.querySelector('[data-route="dashboard"]');
        const themeItem = document.querySelector('[data-route="themes"]');

        expect(dashItem.classList.contains('active')).toBe(true);
        expect(themeItem.classList.contains('active')).toBe(false);

        themeItem.click();

        expect(window.router.navigate).toHaveBeenCalledWith('themes');
        expect(dashItem.classList.contains('active')).toBe(false);
        expect(themeItem.classList.contains('active')).toBe(true);

        expect(window.lucide.createIcons).toHaveBeenCalled();
    });
});
