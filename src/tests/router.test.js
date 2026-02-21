import { describe, it, expect, beforeEach, vi, beforeAll } from 'vitest';
import '../utils/router.js';

describe('router.js', () => {
    beforeEach(() => {
        document.body.innerHTML = '<div id="app-content"></div>';
        window.location.hash = '';

        if (window.router) {
            window.router.routes.clear();
            window.router.currentRoute = null;
            window.router.currentPage = null;
        }
    });

    it('registers routes', () => {
        const mockComponent = () => { };
        window.router.register('test', mockComponent);
        expect(window.router.routes.has('test')).toBe(true);
        expect(window.router.routes.get('test')).toBe(mockComponent);
    });

    it('navigates and loads route', async () => {
        const mockComponent = vi.fn();
        window.router.register('test-route', mockComponent);

        // Use the router's navigate method
        await window.router.navigate('test-route');

        expect(window.location.hash).toBe('#test-route');
        expect(mockComponent).toHaveBeenCalled();
        expect(window.router.getCurrentRoute()).toBe('test-route');

        const page = document.getElementById('page-test-route');
        expect(page).toBeDefined();
        expect(page.style.display).toBe('flex');
    });

    it('updates active nav item', async () => {
        document.body.innerHTML = `
            <div id="app-content"></div>
            <div class="nav-item" data-route="dashboard"></div>
            <div class="nav-item" data-route="test-route"></div>
        `;
        const mockComponent = () => { };
        window.router.register('test-route', mockComponent);

        await window.router.navigate('test-route');

        const testNavItem = document.querySelector('[data-route="test-route"]');
        const dashNavItem = document.querySelector('[data-route="dashboard"]');

        expect(testNavItem.classList.contains('active')).toBe(true);
        expect(dashNavItem.classList.contains('active')).toBe(false);
    });
});
