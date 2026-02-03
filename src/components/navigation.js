/**
 * Navigation component
 * Modern ChatGPT-style sidebar navigation
 */

export function createNavigation() {
    const navHTML = `
        <nav class="main-nav">
            <div class="nav-brand">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm0-13c-2.76 0-5 2.24-5 5s2.24 5 5 5 5-2.24 5-5-2.24-5-5-5z" fill="var(--accent-primary)"/>
                </svg>
                <span>Tailor</span>
            </div>

            <div class="nav-section">
                <div class="nav-item active" data-route="dashboard">
                    <i data-lucide="layout-dashboard"></i>
                    <span>Dashboard</span>
                </div>
                <div class="nav-item" data-route="conversations">
                    <i data-lucide="message-square"></i>
                    <span>Conversations</span>
                </div>
                <div class="nav-item" data-route="themes">
                    <i data-lucide="palette"></i>
                    <span>Themes</span>
                </div>
            </div>

            <div class="nav-section nav-section-bottom">
                <div class="nav-item" data-route="settings">
                    <i data-lucide="settings"></i>
                    <span>Settings</span>
                </div>
            </div>
        </nav>
    `;

    return navHTML;
}

export function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            // Remove active class from all items
            navItems.forEach(i => i.classList.remove('active'));

            // Add active class to clicked item
            item.classList.add('active');

            // Navigate to route
            const route = item.dataset.route;
            if (route && window.router) {
                window.router.navigate(route);
            }
        });
    });

    // Initialize Lucide icons
    if (window.lucide) {
        window.lucide.createIcons();
    }
}


