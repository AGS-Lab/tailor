/**
 * Simple client-side router for Tailor
 * Handles navigation between pages without full page reloads
 */

class Router {
    constructor() {
        this.routes = new Map();
        this.currentRoute = null;
        this.currentPage = null;
        this.init();
    }

    init() {
        // Handle browser back/forward buttons
        window.addEventListener('popstate', (e) => {
            this.loadRoute(window.location.hash.slice(1) || 'dashboard');
        });

        // Load initial route
        const hash = window.location.hash.slice(1) || 'dashboard';
        this.loadRoute(hash);
    }

    register(path, pageComponent) {
        this.routes.set(path, pageComponent);
    }

    navigate(path) {
        window.location.hash = path;
        this.loadRoute(path);
    }

    async loadRoute(path) {
        const route = path.split('?')[0]; // Remove query params
        const pageComponent = this.routes.get(route);

        if (!pageComponent) {
            console.warn(`Route not found: ${route}`);
            return;
        }

        this.currentRoute = route;

        // Hide current page
        if (this.currentPage) {
            this.currentPage.style.display = 'none';
        }

        // Load and show new page
        const container = document.getElementById('app-content');
        if (!container) {
            console.error('App content container not found');
            return;
        }

        // Check if page already exists in DOM
        let pageElement = document.getElementById(`page-${route}`);
        
        if (!pageElement) {
            // Create page container
            pageElement = document.createElement('div');
            pageElement.id = `page-${route}`;
            pageElement.className = 'page-container';
            container.appendChild(pageElement);
        }

        // Initialize page if it has an init function
        if (typeof pageComponent.init === 'function') {
            await pageComponent.init(pageElement);
        } else if (typeof pageComponent === 'function') {
            await pageComponent(pageElement);
        } else {
            pageElement.innerHTML = pageComponent;
        }

        pageElement.style.display = 'flex';
        this.currentPage = pageElement;

        // Update active nav item
        this.updateActiveNav(route);
    }

    updateActiveNav(route) {
        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            const itemRoute = item.dataset.route;
            if (itemRoute === route) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
    }

    getCurrentRoute() {
        return this.currentRoute;
    }
}

// Export singleton instance
window.router = new Router();

