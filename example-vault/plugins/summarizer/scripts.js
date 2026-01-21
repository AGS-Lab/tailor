// Summarizer Plugin - Client-side Interactivity

// Toggle expand/collapse
window.toggleSummaryExpand = function (btn) {
    const container = btn.closest('.summary-container');
    const fullDiv = container.querySelector('.summary-full');
    const isCollapsed = fullDiv.classList.contains('collapsed');

    fullDiv.classList.toggle('collapsed');
    btn.innerHTML = isCollapsed
        ? '<i data-lucide="chevron-up"></i><span>Show less</span>'
        : '<i data-lucide="chevron-down"></i><span>Show more</span>';

    if (window.lucide) window.lucide.createIcons();
};

// Toggle menu
window.toggleSummaryMenu = function (btn) {
    const wrapper = btn.closest('.summary-menu-wrapper');
    let menu = wrapper.querySelector('.summary-dropdown');

    if (menu) {
        menu.remove();
        return;
    }

    const container = btn.closest('.summary-container');
    const messageId = container.dataset.messageId;
    const messageIndex = container.dataset.messageIndex;
    const chatId = container.dataset.chatId;

    menu = document.createElement('div');
    menu.className = 'summary-dropdown';
    menu.innerHTML = `
        <div class="summary-menu-item" onclick="window.summaryAction('save', '${messageId}', ${messageIndex}, '${chatId}')">
            <i data-lucide="bookmark"></i>
            <span>Save to bookmarks</span>
        </div>
        <div class="summary-menu-item" onclick="window.summaryAction('replace', '${messageId}', ${messageIndex}, '${chatId}')">
            <i data-lucide="replace"></i>
            <span>Replace message</span>
        </div>
        <div class="summary-menu-item summary-menu-danger" onclick="window.summaryAction('delete', '${messageId}', ${messageIndex}, '${chatId}')">
            <i data-lucide="trash-2"></i>
            <span>Delete summary</span>
        </div>
    `;
    wrapper.appendChild(menu);
    if (window.lucide) window.lucide.createIcons();

    // Close on outside click
    setTimeout(() => {
        document.addEventListener('click', function closeMenu(e) {
            if (!wrapper.contains(e.target)) {
                menu.remove();
                document.removeEventListener('click', closeMenu);
            }
        });
    }, 0);
};

// Handle menu actions
window.summaryAction = async function (action, messageId, messageIndex, chatId) {
    document.querySelectorAll('.summary-dropdown').forEach(m => m.remove());

    try {
        if (action === 'save') {
            await window.request('execute_command', {
                command: 'summarizer.save_bookmark',
                args: { message_id: messageId, message_index: messageIndex, chat_id: chatId }
            });
        } else if (action === 'replace') {
            await window.request('execute_command', {
                command: 'summarizer.replace_message',
                args: { message_id: messageId, message_index: messageIndex, chat_id: chatId }
            });
        } else if (action === 'delete') {
            await window.request('execute_command', {
                command: 'summarizer.delete_summary',
                args: { message_id: messageId, message_index: messageIndex, chat_id: chatId }
            });
        }
    } catch (e) {
        console.error('[Summarizer] Action failed:', e);
    }
};
