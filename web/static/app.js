// State
const state = {
    models: [],
    providers: {},
    researchTargetsOpen: false,
    researchBusy: false,
    conversations: JSON.parse(localStorage.getItem('pm_conversations') || '[]'),
    currentConvId: null,
};

// DOM Helpers
function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }

// ===== TAB NAVIGATION =====
$$('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        $$('.nav-btn').forEach(b => b.classList.remove('active'));
        $$('.tab-content').forEach(t => t.classList.remove('active'));
        btn.classList.add('active');
        $(`#tab-${btn.dataset.tab}`).classList.add('active');

        if (btn.dataset.tab === 'providers') loadProviders();
        if (btn.dataset.tab === 'config') { loadConfig(); loadModels(); }
    });
});

// ===== HISTORY MANAGEMENT =====
function saveConversations() {
    localStorage.setItem('pm_conversations', JSON.stringify(state.conversations));
    renderHistory();
}

function renderHistory() {
    const list = $('#history-list');
    if (state.conversations.length === 0) {
        list.innerHTML = '<p class="history-empty">No conversations yet</p>';
        return;
    }

    list.innerHTML = '';
    const sorted = [...state.conversations].sort((a, b) => b.updatedAt - a.updatedAt);

    sorted.forEach(conv => {
        const item = document.createElement('div');
        item.className = 'history-item' + (conv.id === state.currentConvId ? ' active' : '');

        const btn = document.createElement('button');
        btn.className = 'history-item-btn';
        btn.textContent = conv.title;
        btn.title = conv.title;
        btn.addEventListener('click', () => loadConversation(conv.id));

        const del = document.createElement('button');
        del.className = 'history-item-delete';
        del.textContent = '✕';
        del.title = 'Delete conversation';
        del.addEventListener('click', (e) => {
            e.stopPropagation();
            if (confirm('Delete this conversation?')) {
                deleteConversation(conv.id);
            }
        });

        item.appendChild(btn);
        item.appendChild(del);
        list.appendChild(item);
    });
}

function deleteConversation(id) {
    state.conversations = state.conversations.filter(c => c.id !== id);
    if (state.currentConvId === id) {
        state.currentConvId = null;
        clearChatMessages();
    }
    saveConversations();
}

function clearAllHistory() {
    if (state.conversations.length === 0) return;
    if (!confirm('Delete ALL conversation history?')) return;
    state.conversations = [];
    state.currentConvId = null;
    clearChatMessages();
    saveConversations();
}

function clearChatMessages() {
    const container = $('#research-messages');
    container.innerHTML = '';
    const welcome = document.createElement('div');
    welcome.className = 'chat-welcome';
    welcome.id = 'research-welcome';
    welcome.innerHTML = `
        <div class="welcome-icon">📚</div>
        <h2>Research Assistant</h2>
        <p>Ask me any topic and I'll decompose it into sub-questions, research them in parallel, and synthesize a comprehensive report.</p>
        <div class="welcome-examples">
            <button class="example-chip" data-topic="Explain quantum computing fundamentals">Quantum Computing</button>
            <button class="example-chip" data-topic="How do large language models work?">LLMs Explained</button>
            <button class="example-chip" data-topic="What are the latest advances in renewable energy?">Renewable Energy</button>
        </div>
    `;
    container.appendChild(welcome);
    rebindExampleChips();
    $('#current-chat-title').textContent = '';
}

function newConversation() {
    state.currentConvId = null;
    clearChatMessages();
    renderHistory();
    researchInput.focus();
}

function loadConversation(id) {
    const conv = state.conversations.find(c => c.id === id);
    if (!conv) return;

    state.currentConvId = id;
    renderHistory();

    const container = $('#research-messages');
    container.innerHTML = '';

    conv.messages.forEach(msg => {
        if (msg.role === 'user') {
            addMessageRaw('user', msg.content);
        } else {
            addMessageRaw('assistant', msg.content);
        }
    });

    $('#current-chat-title').textContent = conv.title;
    scrollToBottom();
}

function addMessageRaw(role, text) {
    const container = $('#research-messages');
    const msg = document.createElement('div');
    msg.className = 'chat-message';

    const avatar = document.createElement('div');
    avatar.className = `message-avatar ${role}`;
    avatar.textContent = role === 'user' ? '👤' : '⬡';

    const content = document.createElement('div');
    content.className = 'message-content';

    const label = document.createElement('div');
    label.className = 'message-label';
    label.textContent = role === 'user' ? 'You' : 'Research Result';

    const textEl = document.createElement('div');
    textEl.className = role === 'assistant' ? 'markdown-body' : 'message-text';

    if (role === 'assistant') {
        textEl.innerHTML = marked.parse(text);
    } else {
        textEl.textContent = text;
    }

    content.appendChild(label);
    content.appendChild(textEl);
    msg.appendChild(avatar);
    msg.appendChild(content);
    container.appendChild(msg);
}

// ===== RESEARCH CHAT =====
const researchInput = $('#research-input');
const btnResearch = $('#btn-research');

researchInput.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 150) + 'px';
});

researchInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        startResearch();
    }
});

btnResearch.addEventListener('click', startResearch);

function rebindExampleChips() {
    $$('.example-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            researchInput.value = chip.dataset.topic;
            researchInput.focus();
            startResearch();
        });
    });
}
rebindExampleChips();

// Mode toggle
$('#research-mode').addEventListener('change', function () {
    const isManual = this.value === 'manual';
    $('#research-effort').style.display = isManual ? 'block' : 'none';
    if (isManual && state.researchTargetsOpen) renderTargets('research-targets');
});

// Targets toggle
$('#btn-research-targets').addEventListener('click', () => {
    state.researchTargetsOpen = !state.researchTargetsOpen;
    $('#research-targets-panel').style.display = state.researchTargetsOpen ? 'block' : 'none';
    if (state.researchTargetsOpen) renderTargets('research-targets');
});

function renderTargets(containerId) {
    const container = $(`#${containerId}`);
    if (container.dataset.rendered) return;
    container.dataset.rendered = 'true';

    state.models.forEach(m => {
        const chip = document.createElement('span');
        chip.className = 'target-chip selected';
        chip.innerHTML = `<span class="chip-check">✓</span>${m.display}`;
        chip.dataset.provider = m.provider;
        chip.dataset.model = m.id;
        chip.addEventListener('click', () => chip.classList.toggle('selected'));
        container.appendChild(chip);
    });
}

function getSelectedTargets(containerId) {
    const chips = $(`#${containerId}`).querySelectorAll('.target-chip.selected');
    return Array.from(chips).map(c => [c.dataset.provider, c.dataset.model]);
}

function startResearch() {
    const topic = researchInput.value.trim();
    if (!topic || state.researchBusy) return;

    state.researchBusy = true;
    btnResearch.disabled = true;
    researchInput.disabled = true;

    const mode = $('#research-mode').value;
    const effort = $('#research-effort').value;
    const targets = getSelectedTargets('research-targets');

    // Hide welcome
    const welcome = $('#research-welcome');
    if (welcome) welcome.style.display = 'none';

    // Add user message
    addMessage('user', topic);

    // Add assistant message with typing indicator
    const assistantEl = addMessage('assistant', '', true);

    // Clear input
    researchInput.value = '';
    researchInput.style.height = 'auto';

    // Create conversation if new
    if (!state.currentConvId) {
        state.currentConvId = 'conv_' + Date.now();
        state.conversations.push({
            id: state.currentConvId,
            title: topic.length > 40 ? topic.substring(0, 40) + '...' : topic,
            messages: [],
            createdAt: Date.now(),
            updatedAt: Date.now(),
        });
    }

    // Save user message
    const conv = state.conversations.find(c => c.id === state.currentConvId);
    conv.messages.push({ role: 'user', content: topic });
    conv.updatedAt = Date.now();
    $('#current-chat-title').textContent = conv.title;
    saveConversations();

    fetch('/api/research', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic, mode, effort, targets }),
    })
    .then(resp => handleStream(resp, assistantEl, conv))
    .catch(err => {
        updateMessage(assistantEl, '**Error:** ' + err.message, false);
    })
    .finally(() => {
        state.researchBusy = false;
        btnResearch.disabled = false;
        researchInput.disabled = false;
        researchInput.focus();
    });
}

function addMessage(role, text, isTyping = false) {
    const container = $('#research-messages');
    const msg = document.createElement('div');
    msg.className = 'chat-message';

    const avatar = document.createElement('div');
    avatar.className = `message-avatar ${role}`;
    avatar.textContent = role === 'user' ? '👤' : '⬡';

    const content = document.createElement('div');
    content.className = 'message-content';

    const label = document.createElement('div');
    label.className = 'message-label';
    label.textContent = role === 'user' ? 'You' : 'Research Result';

    const textEl = document.createElement('div');
    textEl.className = role === 'assistant' ? 'markdown-body' : 'message-text';

    if (isTyping) {
        textEl.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
    } else if (role === 'assistant') {
        textEl.innerHTML = marked.parse(text);
    } else {
        textEl.textContent = text;
    }

    content.appendChild(label);
    content.appendChild(textEl);
    msg.appendChild(avatar);
    msg.appendChild(content);
    container.appendChild(msg);
    scrollToBottom();
    return msg;
}

function updateMessage(msgEl, text, isTyping) {
    const textEl = msgEl.querySelector('.markdown-body');
    if (textEl) {
        if (isTyping) {
            textEl.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
        } else {
            textEl.innerHTML = marked.parse(text);
        }
    }
    scrollToBottom();
}

function scrollToBottom() {
    const container = $('#research-messages');
    container.scrollTop = container.scrollHeight;
}

// ===== NEW CONVERSATION & CLEAR ALL =====
$('#btn-new-chat').addEventListener('click', newConversation);
$('#btn-clear-all').addEventListener('click', clearAllHistory);

// ===== REVIEW =====
$('#review-mode').addEventListener('change', function () {
    const isManual = this.value === 'manual';
    $$('#tab-review .manual-only').forEach(el => {
        el.style.display = isManual ? 'block' : 'none';
    });
    if (isManual) renderTargets('review-targets');
});

$('#btn-review').addEventListener('click', async () => {
    const path = $('#review-path').value.trim() || '.';
    const mode = $('#review-mode').value;
    const effort = $('#review-effort').value;
    const targets = getSelectedTargets('review-targets');

    const resultCard = $('#review-result');
    const output = $('#review-output');
    const status = $('#review-status');

    resultCard.style.display = 'block';
    status.className = 'status-badge running';
    status.textContent = 'Running...';
    output.textContent = '';
    $('#btn-review').disabled = true;

    try {
        const resp = await fetch('/api/review', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path, mode, effort, targets }),
        });
        await handleStreamReview(resp, output, status);
    } catch (err) {
        status.className = 'status-badge error';
        status.textContent = 'Error';
        output.textContent = err.message;
    } finally {
        $('#btn-review').disabled = false;
    }
});

// ===== STREAM HANDLERS =====
async function handleStream(resp, assistantEl, conv) {
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let fullText = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const data = line.slice(6);
            if (data === '[DONE]') continue;

            try {
                const event = JSON.parse(data);
                if (event.type === 'status') {
                    // typing indicator stays
                } else if (event.type === 'result') {
                    fullText = typeof event.output === 'string'
                        ? event.output
                        : JSON.stringify(event.output, null, 2);
                    updateMessage(assistantEl, fullText, false);
                    if (conv) {
                        conv.messages.push({ role: 'assistant', content: fullText });
                        conv.updatedAt = Date.now();
                        saveConversations();
                    }
                } else if (event.type === 'error') {
                    updateMessage(assistantEl, '**Error:** ' + event.message, false);
                }
            } catch (e) {
                // skip
            }
        }
    }
}

async function handleStreamReview(resp, outputEl, statusEl) {
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const data = line.slice(6);
            if (data === '[DONE]') continue;

            try {
                const event = JSON.parse(data);
                if (event.type === 'status') {
                    statusEl.className = 'status-badge running';
                    statusEl.textContent = 'Running...';
                } else if (event.type === 'result') {
                    const text = typeof event.output === 'string'
                        ? event.output
                        : JSON.stringify(event.output, null, 2);
                    outputEl.innerHTML = marked.parse(text);
                    statusEl.className = 'status-badge success';
                    statusEl.textContent = 'Complete';
                } else if (event.type === 'error') {
                    outputEl.textContent = event.message;
                    statusEl.className = 'status-badge error';
                    statusEl.textContent = 'Error';
                }
            } catch (e) {
                // skip
            }
        }
    }
}

// ===== PROVIDERS =====
async function loadProviders() {
    const container = $('#providers-list');
    container.innerHTML = '<p class="loading">Loading providers...</p>';

    try {
        const resp = await fetch('/api/providers');
        const data = await resp.json();

        if (!data.providers.length) {
            container.innerHTML = '<p class="loading">No providers configured. Add API keys to .env</p>';
            return;
        }

        container.innerHTML = '';
        data.providers.forEach(p => {
            const card = document.createElement('div');
            card.className = 'provider-card';
            const dotClass = !p.enabled ? 'disabled' : (p.healthy ? 'healthy' : 'unhealthy');
            const statusText = !p.enabled ? 'Disabled' : (p.healthy ? 'Healthy' : 'Unhealthy');
            card.innerHTML = `
                <span class="provider-name">${p.name}</span>
                <span class="provider-status"><span class="status-dot ${dotClass}"></span>${statusText}</span>
                <span class="provider-model">${p.default_model || 'No default model'}</span>
            `;
            container.appendChild(card);
        });
    } catch (err) {
        container.innerHTML = `<p class="loading">Error: ${err.message}</p>`;
    }
}

// ===== CONFIG =====
async function loadConfig() {
    const container = $('#config-list');
    container.innerHTML = '<p class="loading">Loading config...</p>';

    try {
        const resp = await fetch('/api/config');
        const data = await resp.json();

        const rows = [
            ['Routing Mode', data.routing_mode],
            ['Max Concurrency', data.max_concurrency],
            ['Timeout (sec)', data.timeout_sec],
            ['CB Fail Threshold', data.circuit_breaker_fail_threshold],
            ['CB Reset (sec)', data.circuit_breaker_reset_sec],
            ['Active Providers', data.providers.join(', ') || 'None'],
        ];

        container.innerHTML = '';
        rows.forEach(([key, val]) => {
            const row = document.createElement('div');
            row.className = 'config-row';
            row.innerHTML = `<span class="config-key">${key}</span><span class="config-value">${val}</span>`;
            container.appendChild(row);
        });
    } catch (err) {
        container.innerHTML = `<p class="loading">Error: ${err.message}</p>`;
    }
}

// ===== MODELS =====
async function loadModels() {
    const container = $('#models-list');
    container.innerHTML = '<p class="loading">Loading models...</p>';

    try {
        const resp = await fetch('/api/models');
        const data = await resp.json();
        state.models = data.models;

        const groups = {};
        data.models.forEach(m => {
            if (!groups[m.provider]) groups[m.provider] = [];
            groups[m.provider].push(m);
        });

        container.innerHTML = '';
        Object.entries(groups).forEach(([provider, models]) => {
            const group = document.createElement('div');
            group.className = 'model-group';
            group.innerHTML = `<div class="model-group-title">${provider}</div>`;
            models.forEach(m => {
                const item = document.createElement('div');
                item.className = 'model-item';
                item.innerHTML = `
                    <span class="model-id">${m.id}</span>
                    <span class="model-display">${m.display}</span>
                `;
                group.appendChild(item);
            });
            container.appendChild(group);
        });
    } catch (err) {
        container.innerHTML = `<p class="loading">Error: ${err.message}</p>`;
    }
}

// Configure marked
if (typeof marked !== 'undefined') {
    marked.setOptions({
        breaks: true,
        gfm: true,
    });
}

// Init
renderHistory();
