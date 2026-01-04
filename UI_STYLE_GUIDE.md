 Tailor UI Style Guide

Design principles and patterns for building consistent, minimal UIs across the Tailor project.

## Core Philosophy

**Ultra Minimal, Dense, Developer-First**
- Dark theme (GitHub Dark Dimmed inspiration)
- **Source of Truth**: All styling must use variables from `frontend/theme.css`.
- External dependencies (fonts, libraries) are permitted when they add value.
- Fast to load, highly functional.

## Design Principles

### 1. **Use the Theme**
- Do not hardcode hex values. Use CSS variables.
- Example: Use `var(--bg-app)` instead of `#0d1117`.

### 2. **Consistency**
- Reuse `theme.css` classes (`.btn`, `.input`, `.panel-container`).
- Follow the spacing variables (`--spacing-sm`, etc.).

## CSS Variables (`theme.css`)

### Typography
```css
font-family: var(--font-main);  /* UI Elements */
font-family: var(--font-mono);  /* Code/Logs */
```

### Colors (Semantic)
```css
/* Backgrounds */
background: var(--bg-app);      /* Main App */
background: var(--bg-panel);    /* Panels/Sidebars */
background: var(--bg-input);    /* Inputs */

/* Text */
color: var(--text-primary);     /* Main Content */
color: var(--text-secondary);   /* Labels/Muted */
color: var(--text-disabled);    /* Inactive */

/* Accents */
color: var(--accent-primary);   /* Blue/Links */
color: var(--accent-secondary); /* Success/Green */
color: var(--accent-error);     /* Error/Red */
```

## Components

### Buttons
Use the `.btn` class hierarchy.
```html
<button class="btn">Default</button>
<button class="btn btn-primary">Primary Action</button>
<button class="btn btn-secondary">Secondary</button>
```

### Inputs
Use standard input elements; `theme.css` handles the rest.
```html
<input type="text" placeholder="Command...">
<textarea rows="3"></textarea>
```

### Layout Patterns

#### Standard Panel
```html
<div class="panel-container">
    <div class="toolbar">
        <!-- Controls -->
    </div>
    <div class="scrollable">
        <!-- Content -->
    </div>
</div>
```

## JavaScript Patterns

### JSON-RPC
Use the standard `request` and `notify` patterns to communicate with the backend.

```javascript
// Execute Command
await request('execute_command', { command: 'my_plugin.action' });

// Listen for Events
window.addEventListener('MY_EVENT', (e) => {
    console.log(e.detail);
});
```

## Verification Checklist

- [ ] Are all colors using `var(--name)`?
- [ ] Are fonts using `var(--font-...)`?
- [ ] Is the spacing consistent with `theme.css`?
- [ ] Does it work in Dark Mode (default)?
