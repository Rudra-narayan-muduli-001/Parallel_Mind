// ===== STATE =====
const state = {
    models: [],
    busy: false,
    researchTargetsOpen: false,
    currentConvId: null,
    conversations: [],
};

// Try to load from localStorage, fallback to empty array
try {
    const stored = localStorage.getItem('pm_conversations');
    state.conversations = stored ? JSON.parse(stored) : [];
} catch (e) {
    state.conversations = [];
}

// ===== Helpers =====
function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }
function esc(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ===== TAB NAV =====
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

// ===== HISTORY =====
function saveHistory() {
    try {
        localStorage.setItem('pm_conversations', JSON.stringify(state.conversations));
    } catch (e) {}
    renderHistory();
}

function renderHistory() {
    const list = $('#history-list');
    if (!list) return;

    if (!state.conversations.length) {
        list.innerHTML = '<p class="history-empty">No conversations</p>';
        return;
    }

    const sorted = [...state.conversations].sort((a, b) => b.updatedAt - a.updatedAt);
    let html = '';

    sorted.forEach(conv => {
        const activeCls = conv.id === state.currentConvId ? ' active' : '';
        const shortTitle = conv.title.length > 40 ? conv.title.substring(0, 40) + '…' : conv.title;
        html += `
            <div class="history-item${activeCls}" data-id="${conv.id}">
                <button class="history-item-btn" data-title="${esc(conv.title)}" title="${esc(conv.title)}">${esc(shortTitle)}</button>
                <button class="history-item-delete" data-id="${conv.id}" title="Delete">✕</button>
            </div>`;
    });

    list.innerHTML = html;

    // Bind click events
    list.querySelectorAll('.history-item-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const id = btn.closest('.history-item').dataset.id;
            loadConversation(id);
        });
    });

    list.querySelectorAll('.history-item-delete').forEach(btn => {
        btn.addEventListener('click', () => {
            const id = btn.dataset.id;
            if (confirm('Delete this conversation?')) {
                deleteConversation(id);
            }
        });
    });
}

function deleteConversation(id) {
    state.conversations = state.conversations.filter(c => c.id !== id);
    if (state.currentConvId === id) {
        state.currentConvId = null;
        clearChatUI();
    }
    saveHistory();
}

function clearAllHistory() {
    if (!state.conversations.length) return;
    if (!confirm('Delete ALL conversations?')) return;
    state.conversations = [];
    state.currentConvId = null;
    clearChatUI();
    saveHistory();
}

function clearChatUI() {
    const container = document.getElementById('research-messages');
    const conv = state.conversations.find(c => c.id === state.currentConvId);
    if (conv) {
        // load messages
        container.innerHTML = '';
        conv.messages.forEach(m => addMessageDOM(m.role, m.content));
        document.getElementById('current-chat-title').textContent = conv.title;
        state.currentConvId = conv.id;
    } else {
        // show welcome
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
            </div>`;
        container.appendChild(welcome);
        document.getElementById('current-chat-title').textContent = '';
        state.currentConvId = null;
        rebindChips();
    }
    renderHistory();
    scrollChat();
}

function loadConversation(id) {
    const conv = state.conversations.find(c => c.id === id);
    if (!conv) return;
    state.currentConvId = id;
    clearChatUI();
}

function newConversation() {
    state.currentConvId = null;
    clearChatUI();
    document.getElementById('research-input').focus();
}

// Bind buttons
$('#btn-new-chat').addEventListener('click', newConversation);
$('#btn-clear-all').addEventListener('click', clearAllHistory);

// ===== CHAT UI =====
const chatInput = $('#research-input');
const btnSend = $('#btn-research');

// Auto-resize textarea
chatInput.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 150) + 'px';
});

// Enter to send (Shift+Enter = newline)
chatInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        startResearch();
    }
});

btnSend.addEventListener('click', startResearch);

// Example chips click
function rebindChips() {
    $$('.example-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            chatInput.value = chip.dataset.topic;
            chatInput.focus();
            startResearch();
        });
    });
}
rebindChips();

// Mode toggle (research)
$('#research-mode').addEventListener('change', function () {
    const isManual = this.value === 'manual';
    $('#research-effort').style.display = isManual ? 'block' : 'none';
    if (isManual && state.researchTargetsOpen) renderTargets('research-targets');
});

// Targets toggle
const btnTargets = $('#btn-research-targets');
btnTargets.addEventListener('click', () => {
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

function addMessageDOM(role, text, isTyping = false) {
    const container = document.getElementById('research-messages');
    const msg = document.createElement('div');
    msg.className = 'chat-message';
    msg.dataset.role = role;

    const avatar = document.createElement('div');
    avatar.className = `message-avatar ${role}`;
    avatar.textContent = role === 'user' ? '👤' : '⬡';

    const content = document.createElement('div');
    content.className = 'message-content';

    const label = document.createElement('div');
    label.className = 'message-label';
    label.textContent = role === 'user' ? 'You' : 'Research Result';

    const bodyEl = document.createElement('div');
    bodyEl.className = role === 'assistant' ? 'markdown-body' : 'message-text';

    if (isTyping) {
        bodyEl.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
    } else if (role === 'assistant') {
        try { bodyEl.innerHTML = marked.parse(text); } catch(e) { bodyEl.textContent = text; }
    } else {
        bodyEl.textContent = text;
    }

    content.appendChild(label);
    content.appendChild(bodyEl);
    msg.appendChild(avatar);
    msg.appendChild(content);
    container.appendChild(msg);
    scrollChat();
    return msg;
}

function scrollChat() {
    const c = document.getElementById('research-messages');
    if (c) c.scrollTop = c.scrollHeight;
}

// ===== PARALLEL EXECUTION VIZ =====
function createParallelViz(msgEl) {
    const content = msgEl.querySelector('.message-content');
    const oldBody = content.querySelector('.markdown-body');
    if (oldBody) oldBody.innerHTML = '';

    const vizBox = document.createElement('div');
    vizBox.className = 'parallel-viz';
    vizBox.innerHTML = `
        <div class="parallel-viz-header">
            <div class="parallel-viz-title">
                <div class="parallel-viz-spinner"></div>
                <span class="viz-stage-text">Running parallel agents…</span>
            </div>
            <div class="parallel-viz-stats">
                <span class="viz-stat-total">0 tasks</span>
                <span class="stat-done viz-stat-done">0 done</span>
                <span class="stat-fail viz-stat-fail">0 failed</span>
            </div>
        </div>
        <div class="parallel-viz-tasks"></div>
    `;

    content.insertBefore(vizBox, oldBody);

    const resultBody = document.createElement('div');
    resultBody.className = 'markdown-body';
    content.appendChild(resultBody);
    oldBody.remove();

    return {
        box: vizBox,
        spinner: vizBox.querySelector('.parallel-viz-spinner'),
        stage: vizBox.querySelector('.viz-stage-text'),
        statTotal: vizBox.querySelector('.viz-stat-total'),
        statDone: vizBox.querySelector('.viz-stat-done'),
        statFail: vizBox.querySelector('.viz-stat-fail'),
        tasksEl: vizBox.querySelector('.parallel-viz-tasks'),
        resultBody: resultBody,
        tasks: {},
        doneCount: 0,
        failCount: 0,
        totalCount: 0,
    };
}

function vizTaskStarted(viz, task_id, prompt) {
    viz.totalCount++;
    const index = Object.keys(viz.tasks).length + 1;
    const shortPrompt = prompt.length > 70 ? prompt.substring(0, 70) + '…' : prompt;

    const taskEl = document.createElement('div');
    taskEl.className = 'viz-task running';
    taskEl.dataset.id = task_id;
    taskEl.innerHTML = `
        <span class="viz-task-index">${index}</span>
        <div class="viz-task-info">
            <div class="viz-task-prompt"></div>
        </div>
        <div class="viz-task-progress"><div class="viz-task-progress-bar"></div></div>
        <span class="viz-task-badge running">running</span>
    `;
    taskEl.querySelector('.viz-task-prompt').textContent = shortPrompt;

    viz.tasksEl.appendChild(taskEl);
    viz.tasks[task_id] = { el: taskEl, index: index, startedAt: performance.now() };
    updateVizStats(viz);
    scrollChat();
}

function vizTaskDone(viz, task_id, success, provider, model, latency, error) {
    const t = viz.tasks[task_id];
    if (!t) return;
    t.el.classList.remove('running');
    const info = t.el.querySelector('.viz-task-info');
    let metaDiv = info.querySelector('.viz-task-meta');
    if (!metaDiv) {
        metaDiv = document.createElement('div');
        metaDiv.className = 'viz-task-meta';
        info.appendChild(metaDiv);
    }
    const progress = t.el.querySelector('.viz-task-progress');
    if (progress) progress.remove();
    const badge = t.el.querySelector('.viz-task-badge');

    if (success) {
        t.el.classList.add('success');
        t.el.querySelector('.viz-task-index').textContent = '✓';
        badge.className = 'viz-task-badge success';
        badge.innerHTML = `${escapeHtml(provider || '')}/${escapeHtml(model || '')} <span class="timing">${latency}s</span>`;
    } else {
        t.el.classList.add('fail');
        t.el.querySelector('.viz-task-index').textContent = '✕';
        badge.className = 'viz-task-badge fail';
        badge.textContent = 'failed';
        metaDiv.textContent = error || '';
        badge.title = error || '';
    }

    if (success) viz.doneCount++; else viz.failCount++;
    updateVizStats(viz);
    if (viz.totalCount > 0 && viz.doneCount + viz.failCount >= viz.totalCount) {
        viz.spinner.classList.add('done');
        viz.stage.textContent = `Completed ${viz.doneCount} agent${viz.doneCount !== 1 ? 's' : ''} in parallel`;
    }
    scrollChat();
}

function updateVizStats(viz) {
    viz.statTotal.textContent = `${viz.totalCount} task${viz.totalCount !== 1 ? 's' : ''}`;
    viz.statDone.textContent = `${viz.doneCount} done`;
    viz.statFail.textContent = `${viz.failCount} failed`;
}

function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({'&':'&','<':'<','>':'>','"':'"',"'":'&#39;'}[c]));
}

function startResearch() {
    const topic = chatInput.value.trim();
    if (!topic || state.busy) return;

    state.busy = true;
    btnSend.disabled = true;
    chatInput.disabled = true;

    const mode = $('#research-mode').value;
    const effort = $('#research-effort').value;
    const targets = getSelectedTargets('research-targets');

    // Hide welcome
    const welcome = $('#research-welcome');
    if (welcome) welcome.style.display = 'none';

    // Create new conversation if current is null
    if (!state.currentConvId) {
        const convId = 'conv_' + Date.now();
        const title = topic.length > 40 ? topic.substring(0, 40) + '…' : topic;
        const conv = {
            id: convId,
            title: title,
            messages: [],
            createdAt: Date.now(),
            updatedAt: Date.now(),
        };
        state.conversations.unshift(conv);
        state.currentConvId = convId;
    }

    // Add user message to conversation + UI
    const conv = state.conversations.find(c => c.id === state.currentConvId);
    conv.messages.push({ role: 'user', content: topic, timestamp: Date.now() });
    conv.updatedAt = Date.now();
    addMessageDOM('user', topic);

    // Add assistant typing placeholder
    const assistantEl = addMessageDOM('assistant', '', true);

    // Clear input
    chatInput.value = '';
    chatInput.style.height = 'auto';

    // Fetch
    fetch('/api/research', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic, mode, effort, targets }),
    })
    .then(resp => handleStream(resp, assistantEl, conv))
    .catch(err => {
        renderFinal(assistantEl, null, '**Error:** ' + err.message);
        conv.messages.push({ role: 'assistant', content: err.message });
    })
    .finally(() => {
        state.busy = false;
        btnSend.disabled = false;
        chatInput.disabled = false;
        chatInput.focus();
        saveHistory();
        renderHistory();
        // Update title display
        document.getElementById('current-chat-title').textContent = conv.title;
    });
}

async function handleStream(resp, assistantEl, conv) {
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finalText = '';
    let viz = null;

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
                    // keep typing until tasks begin
                } else if (event.type === 'task_start') {
                    if (!viz) viz = createParallelViz(assistantEl);
                    vizTaskStarted(viz, event.task_id, event.prompt);
                } else if (event.type === 'task_success') {
                    if (viz) vizTaskDone(viz, event.task_id, true, event.provider, event.model, event.latency_sec);
                } else if (event.type === 'task_fail') {
                    if (viz) vizTaskDone(viz, event.task_id, false, null, null, event.latency_sec, event.error);
                } else if (event.type === 'result') {
                    finalText = typeof event.output === 'string'
                        ? event.output
                        : JSON.stringify(event.output, null, 2);
                    renderFinal(assistantEl, viz, finalText);
                    if (conv) {
                        conv.messages.push({ role: 'assistant', content: finalText });
                        conv.updatedAt = Date.now();
                    }
                } else if (event.type === 'error') {
                    finalText = '**Error:** ' + event.message;
                    renderFinal(assistantEl, viz, finalText);
                    if (conv) {
                        conv.messages.push({ role: 'assistant', content: finalText });
                    }
                }
            } catch (e) {}
        }
    }
}

function renderFinal(assistantEl, viz, text) {
    let target;
    if (viz && viz.resultBody) {
        target = viz.resultBody;
    } else {
        // fallback: replace typing indicator body
        const body = assistantEl.querySelector('.markdown-body');
        if (body) {
            body.innerHTML = '';
            target = body;
        }
    }
    if (target) {
        try { target.innerHTML = marked.parse(text); } catch(e) { target.textContent = text; }
    }
    scrollChat();
}

// ===== REVIEW TAB =====
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
                if (event.type === 'result') {
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
            } catch (e) {}
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
        state.providers = data.providers;

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
                <span class="provider-name">${esc(p.name)}</span>
                <span class="provider-status"><span class="status-dot ${dotClass}"></span>${statusText}</span>
                <span class="provider-model">${esc(p.default_model || 'No default model')}</span>
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
            ['Default Provider', data.default_provider],
            ['Free Models Only', data.free_models_only ? 'Yes' : 'No'],
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
            row.innerHTML = `<span class="config-key">${esc(key)}</span><span class="config-value">${esc(val)}</span>`;
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
        renderModels(container, data.models);
    } catch (err) {
        container.innerHTML = `<p class="loading">Error: ${err.message}</p>`;
    }
}

function renderModels(container, models) {
    if (!models.length) {
        container.innerHTML = '<p class="loading">No models found</p>';
        return;
    }
    const groups = {};
    models.forEach(m => {
        if (!groups[m.provider]) groups[m.provider] = [];
        groups[m.provider].push(m);
    });
    container.innerHTML = '';
    Object.entries(groups).forEach(([provider, items]) => {
        const group = document.createElement('div');
        group.className = 'model-group';
        group.innerHTML = `<div class="model-group-title">${esc(provider)} <span class="model-count">(${items.length})</span></div>`;
        items.forEach(m => {
            const item = document.createElement('div');
            item.className = 'model-item';
            item.innerHTML = `
                <span class="model-id">${esc(m.id)}</span>
                <span class="model-display">${esc(m.display)}</span>
            `;
            group.appendChild(item);
        });
        container.appendChild(group);
    });
}

async function refreshModels() {
    const btn = $('#btn-refresh-models');
    if (!btn) return;
    btn.classList.add('spinning');
    btn.disabled = true;
    try {
        const resp = await fetch('/api/models/refresh', { method: 'POST' });
        const data = await resp.json();
        state.models = data.models;
        const container = $('#models-list');
        renderModels(container, data.models);
    } catch (err) {
        alert('Refresh failed: ' + err.message);
    } finally {
        btn.classList.remove('spinning');
        btn.disabled = false;
    }
}

const refreshBtn = $('#btn-refresh-models');
if (refreshBtn) refreshBtn.addEventListener('click', refreshModels);

// Configure marked on load
if (typeof marked !== 'undefined') {
    marked.setOptions({ breaks: true, gfm: true });
}

// Init
renderHistory();
