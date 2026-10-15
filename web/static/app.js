// ==========================================================================
// ParallelMind — Frontend Application Logic
// ==========================================================================

// --- State Management ---
const state = {
  models: [],
  providers: [],
  busy: false,
  researchTargetsOpen: false,
  reviewTargetsOpen: false,
  currentConvId: null,
  conversations: [],
  sidebarOpen: false,
};

// Load conversations from localStorage
try {
  const stored = localStorage.getItem('pm_conversations');
  state.conversations = stored ? JSON.parse(stored) : [];
} catch {
  state.conversations = [];
}

// --- DOM Helpers ---
const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => ctx.querySelectorAll(sel);

function esc(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function createElement(html) {
  const template = document.createElement('template');
  template.innerHTML = html.trim();
  return template.content.firstElementChild;
}

// --- Utility Functions ---
function saveHistory() {
  try {
    localStorage.setItem('pm_conversations', JSON.stringify(state.conversations));
  } catch {}
  renderHistory();
}

function scrollChat() {
  const container = $('#research-messages');
  if (container) {
    container.scrollTop = container.scrollHeight;
  }
}

function setBusy(busy) {
  state.busy = busy;
  $('#btn-research').disabled = busy;
  $('#research-input').disabled = busy;
  $('#btn-review').disabled = busy;
  $('#review-path').disabled = busy;
  $('#review-mode').disabled = busy;
  $('#review-effort').disabled = busy;
}

function showToast(message, type = 'info') {
  // Simple toast notification
  const toast = createElement(`
    <div class="toast toast-${type}" role="alert" aria-live="polite">
      ${esc(message)}
    </div>
  `);
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

// --- Tab Navigation ---
function initTabs() {
  $$('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      if (!tab) return;

      $$('.nav-btn').forEach(b => {
        b.classList.remove('active');
        b.setAttribute('aria-selected', 'false');
      });
      $$('.tab-panel').forEach(p => {
        p.classList.remove('active');
        p.hidden = true;
      });

      btn.classList.add('active');
      btn.setAttribute('aria-selected', 'true');

      const panel = $(`#panel-${tab}`);
      if (panel) {
        panel.classList.add('active');
        panel.hidden = false;
      }

      // Load data for specific tabs
      if (tab === 'providers') loadProviders();
      if (tab === 'config') { loadConfig(); loadModels(); }

      // Close sidebar on mobile
      if (window.innerWidth < 1024) {
        $('.sidebar').classList.remove('open');
      }
    });
  });

  // Keyboard navigation for tabs
  $$('.nav-btn').forEach((btn, index) => {
    btn.addEventListener('keydown', (e) => {
      const tabs = $$('.nav-btn');
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault();
        tabs[(index + 1) % tabs.length].focus();
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault();
        tabs[(index - 1 + tabs.length) % tabs.length].focus();
      } else if (e.key === 'Home') {
        e.preventDefault();
        tabs[0].focus();
      } else if (e.key === 'End') {
        e.preventDefault();
        tabs[tabs.length - 1].focus();
      }
    });
  });
}

// --- History Management ---
function renderHistory() {
  const list = $('#history-list');
  if (!list) return;

  if (!state.conversations.length) {
    list.innerHTML = '<p class="history-empty">No conversations yet</p>';
    return;
  }

  const sorted = [...state.conversations].sort((a, b) => b.updatedAt - a.updatedAt);
  list.innerHTML = sorted.map(conv => {
    const activeCls = conv.id === state.currentConvId ? ' active' : '';
    const shortTitle = conv.title.length > 40 ? conv.title.substring(0, 40) + '…' : conv.title;
    const timeAgo = formatTimeAgo(conv.updatedAt);
    return `
      <div class="history-item${activeCls}" data-id="${conv.id}" role="option" aria-selected="${activeCls ? 'true' : 'false'}">
        <button class="history-item-btn" data-title="${esc(conv.title)}" title="${esc(conv.title)}">
          ${esc(shortTitle)}
          <span class="history-item-time">${esc(timeAgo)}</span>
        </button>
        <button class="history-item-delete" data-id="${conv.id}" aria-label="Delete conversation" title="Delete">✕</button>
      </div>`;
  }).join('');

  // Bind events
  list.querySelectorAll('.history-item-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.closest('.history-item').dataset.id;
      loadConversation(id);
    });
  });

  list.querySelectorAll('.history-item-delete').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const id = btn.dataset.id;
      if (confirm('Delete this conversation?')) {
        deleteConversation(id);
      }
    });
  });
}

function formatTimeAgo(timestamp) {
  const diff = Date.now() - timestamp;
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  return new Date(timestamp).toLocaleDateString();
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
  if (!confirm('Delete ALL conversations? This cannot be undone.')) return;
  state.conversations = [];
  state.currentConvId = null;
  clearChatUI();
  saveHistory();
}

function clearChatUI() {
  const container = $('#research-messages');
  const conv = state.conversations.find(c => c.id === state.currentConvId);

  if (conv) {
    container.innerHTML = '';
    conv.messages.forEach(m => addMessageDOM(m.role, m.content));
    $('#current-chat-title').textContent = conv.title;
    state.currentConvId = conv.id;
  } else {
    container.innerHTML = '';
    container.appendChild(createWelcomeScreen());
    $('#current-chat-title').textContent = '';
    state.currentConvId = null;
    bindExampleChips();
  }
  scrollChat();
  renderHistory();
}

function createWelcomeScreen() {
  return createElement(`
    <div class="chat-welcome" id="research-welcome">
      <div class="welcome-illustration" aria-hidden="true">
        <svg width="80" height="80" viewBox="0 0 100 100" fill="none">
          <circle cx="50" cy="50" r="45" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
          <circle cx="50" cy="50" r="35" stroke="currentColor" stroke-width="1.5" opacity="0.2"/>
          <path d="M50 20 L50 35 M50 65 L50 80" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          <path d="M20 50 L35 50 M65 50 L80 50" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          <circle cx="50" cy="50" r="15" stroke="currentColor" stroke-width="2" fill="currentColor" opacity="0.15"/>
        </svg>
      </div>
      <h2 class="welcome-title">Research Assistant</h2>
      <p class="welcome-description">Enter any topic and I'll decompose it into sub-questions, research them in parallel across multiple models, and synthesize a comprehensive report.</p>
      <div class="welcome-examples" role="group" aria-label="Example topics">
        <button type="button" class="example-chip" data-topic="Explain quantum computing fundamentals">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
          <span>Quantum Computing</span>
        </button>
        <button type="button" class="example-chip" data-topic="How do large language models work?">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          <span>LLMs Explained</span>
        </button>
        <button type="button" class="example-chip" data-topic="What are the latest advances in renewable energy?">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
          <span>Renewable Energy</span>
        </button>
      </div>
    </div>
  `);
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
  $('#research-input').focus();
}

function bindExampleChips() {
  $$('.example-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const input = $('#research-input');
      input.value = chip.dataset.topic;
      input.focus();
      startResearch();
    });
  });
}

// --- Research Mode Toggle ---
function initResearchModeToggle() {
  const modeSelect = $('#research-mode');
  const effortContainer = $('#research-effort-selector');

  modeSelect.addEventListener('change', () => {
    const isManual = modeSelect.value === 'manual';
    effortContainer.style.display = isManual ? 'block' : 'none';
    if (isManual && state.researchTargetsOpen) renderTargets('research-targets');
  });
}

// --- Targets Panel ---
function initTargetsToggle() {
  const btn = $('#btn-research-targets');
  const panel = $('#research-targets-panel');

  btn.addEventListener('click', () => {
    state.researchTargetsOpen = !state.researchTargetsOpen;
    panel.style.display = state.researchTargetsOpen ? 'block' : 'none';
    btn.setAttribute('aria-expanded', state.researchTargetsOpen);
    if (state.researchTargetsOpen) renderTargets('research-targets');
  });

  // Clear all targets
  $('#research-targets-panel .targets-clear')?.addEventListener('click', () => {
    $$('#research-targets .target-chip').forEach(c => c.classList.remove('selected'));
  });
}

function renderTargets(containerId) {
  const container = $(`#${containerId}`);
  if (!container || container.dataset.rendered) return;
  container.dataset.rendered = 'true';

  state.models.forEach(m => {
    const chip = createElement(`
      <span class="target-chip selected" data-provider="${m.provider}" data-model="${m.id}" role="option" aria-selected="true" tabindex="0">
        <span class="chip-check">✓</span>${esc(m.display)}
      </span>
    `);
    chip.addEventListener('click', () => chip.classList.toggle('selected'));
    chip.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        chip.classList.toggle('selected');
      }
    });
    container.appendChild(chip);
  });
}

function getSelectedTargets(containerId) {
  const chips = $(`#${containerId}`)?.querySelectorAll('.target-chip.selected');
  return chips ? Array.from(chips).map(c => [c.dataset.provider, c.dataset.model]) : [];
}

// --- Chat Input Auto-resize ---
function initChatInput() {
  const input = $('#research-input');
  if (!input) return;

  input.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 160) + 'px';
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      startResearch();
    }
  });
}

// --- Message Rendering ---
function addMessageDOM(role, text, isTyping = false) {
  const container = $('#research-messages');
  const msg = createElement(`
    <div class="chat-message" data-role="${role}">
      <div class="message-avatar ${role}" aria-hidden="true">${role === 'user' ? '👤' : '⬡'}</div>
      <div class="message-content">
        <div class="message-label">${role === 'user' ? 'You' : 'Research Result'}</div>
        <div class="${role === 'assistant' ? 'markdown-body' : 'message-text'}"></div>
      </div>
    </div>
  `);

  const bodyEl = msg.querySelector('.markdown-body, .message-text');

  if (isTyping) {
    bodyEl.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
  } else if (role === 'assistant') {
    try { bodyEl.innerHTML = marked.parse(text); } catch { bodyEl.textContent = text; }
  } else {
    bodyEl.textContent = text;
  }

  // Remove welcome screen if present
  const welcome = $('#research-welcome');
  if (welcome) welcome.remove();

  // Remove parallel viz container if this is a new user message
  const vizContainer = $('#parallel-viz-container');
  if (vizContainer && role === 'user') {
    vizContainer.style.display = 'none';
    vizContainer.innerHTML = '';
  }

  container.appendChild(msg);
  scrollChat();
  return msg;
}

// --- Parallel Execution Visualization ---
let currentViz = null;

function createParallelViz(assistantEl) {
  const content = assistantEl.querySelector('.message-content');
  const oldBody = content.querySelector('.markdown-body');
  if (oldBody) oldBody.innerHTML = '';

  const vizContainer = $('#parallel-viz-container');
  vizContainer.style.display = 'block';

  const vizBox = createElement(`
    <div class="parallel-viz">
      <div class="parallel-viz-header">
        <div class="parallel-viz-title">
          <div class="parallel-viz-spinner" aria-hidden="true"></div>
          <span class="viz-stage-text">Running parallel agents…</span>
        </div>
        <div class="parallel-viz-stats">
          <span class="viz-stat-total">0 tasks</span>
          <span class="stat-done viz-stat-done">0 done</span>
          <span class="stat-fail viz-stat-fail">0 failed</span>
        </div>
      </div>
      <div class="parallel-viz-tasks" role="list" aria-label="Agent tasks"></div>
    </div>
  `);

  vizContainer.appendChild(vizBox);

  const resultBody = createElement('<div class="markdown-body"></div>');
  content.appendChild(resultBody);
  if (oldBody) oldBody.remove();

  return {
    box: vizBox,
    spinner: vizBox.querySelector('.parallel-viz-spinner'),
    stage: vizBox.querySelector('.viz-stage-text'),
    statTotal: vizBox.querySelector('.viz-stat-total'),
    statDone: vizBox.querySelector('.viz-stat-done'),
    statFail: vizBox.querySelector('.viz-stat-fail'),
    tasksEl: vizBox.querySelector('.parallel-viz-tasks'),
    resultBody,
    tasks: {},
    doneCount: 0,
    failCount: 0,
    totalCount: 0,
  };
}

function vizTaskStarted(viz, task_id, prompt) {
  viz.totalCount++;
  const index = Object.keys(viz.tasks).length + 1;
  const shortPrompt = prompt.length > 80 ? prompt.substring(0, 80) + '…' : prompt;

  const taskEl = createElement(`
    <div class="viz-task running" data-id="${task_id}" role="listitem">
      <span class="viz-task-index">${index}</span>
      <div class="viz-task-info">
        <div class="viz-task-prompt">${esc(shortPrompt)}</div>
      </div>
      <div class="viz-task-progress"><div class="viz-task-progress-bar"></div></div>
      <span class="viz-task-badge running">running</span>
    </div>
  `);

  viz.tasksEl.appendChild(taskEl);
  viz.tasks[task_id] = { el: taskEl, index, startedAt: performance.now() };
  updateVizStats(viz);
  scrollChat();
}

function vizTaskDone(viz, task_id, success, provider, model, latency, error) {
  const t = viz.tasks[task_id];
  if (!t) return;

  t.el.classList.remove('running');

  const progress = t.el.querySelector('.viz-task-progress');
  if (progress) progress.remove();

  const badge = t.el.querySelector('.viz-task-badge');
  const indexEl = t.el.querySelector('.viz-task-index');

  let metaDiv = t.el.querySelector('.viz-task-meta');
  if (!metaDiv) {
    metaDiv = createElement('<div class="viz-task-meta"></div>');
    t.el.querySelector('.viz-task-info').appendChild(metaDiv);
  }

  if (success) {
    t.el.classList.add('success');
    indexEl.textContent = '✓';
    indexEl.style.background = 'var(--color-success-glow)';
    indexEl.style.color = 'var(--color-success)';
    badge.className = 'viz-task-badge success';
    badge.innerHTML = `${esc(provider || '')}/${esc(model || '')} <span class="timing">${latency?.toFixed(2) ?? '?'}s</span>`;
    viz.doneCount++;
  } else {
    t.el.classList.add('fail');
    indexEl.textContent = '✕';
    indexEl.style.background = 'var(--color-error-glow)';
    indexEl.style.color = 'var(--color-error)';
    badge.className = 'viz-task-badge fail';
    badge.textContent = 'failed';
    metaDiv.textContent = error || 'Unknown error';
    badge.title = error || '';
    viz.failCount++;
  }

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

// --- Research Execution ---
async function startResearch() {
  const input = $('#research-input');
  const topic = input.value.trim();
  if (!topic || state.busy) return;

  setBusy(true);

  const mode = $('#research-mode').value;
  const effort = $('#research-effort').value;
  const targets = getSelectedTargets('research-targets');

  // Create new conversation if needed
  if (!state.currentConvId) {
    const convId = 'conv_' + Date.now();
    const title = topic.length > 50 ? topic.substring(0, 50) + '…' : topic;
    const conv = {
      id: convId,
      title,
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    state.conversations.unshift(conv);
    state.currentConvId = convId;
  }

  const conv = state.conversations.find(c => c.id === state.currentConvId);

  // Add user message
  conv.messages.push({ role: 'user', content: topic, timestamp: Date.now() });
  conv.updatedAt = Date.now();
  addMessageDOM('user', topic);

  // Add assistant placeholder
  const assistantEl = addMessageDOM('assistant', '', true);
  currentViz = createParallelViz(assistantEl);

  // Clear input
  input.value = '';
  input.style.height = 'auto';

  // Update title
  $('#current-chat-title').textContent = conv.title;

  try {
    const response = await fetch('/api/research', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic, mode, effort, targets }),
    });

    await handleStream(response, assistantEl, conv);
  } catch (err) {
    renderFinal(assistantEl, currentViz, '**Error:** ' + err.message);
    conv.messages.push({ role: 'assistant', content: err.message, timestamp: Date.now() });
  } finally {
    setBusy(false);
    input.focus();
    saveHistory();
    renderHistory();
  }
}

async function handleStream(response, assistantEl, conv) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalText = '';

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

        switch (event.type) {
          case 'task_start':
            if (currentViz) vizTaskStarted(currentViz, event.task_id, event.prompt);
            break;
          case 'task_success':
            if (currentViz) vizTaskDone(currentViz, event.task_id, true, event.provider, event.model, event.latency_sec);
            break;
          case 'task_fail':
            if (currentViz) vizTaskDone(currentViz, event.task_id, false, null, null, event.latency_sec, event.error);
            break;
          case 'result':
            finalText = typeof event.output === 'string'
              ? event.output
              : JSON.stringify(event.output, null, 2);
            renderFinal(assistantEl, currentViz, finalText);
            if (conv) {
              conv.messages.push({ role: 'assistant', content: finalText, timestamp: Date.now() });
              conv.updatedAt = Date.now();
            }
            break;
          case 'error':
            finalText = '**Error:** ' + event.message;
            renderFinal(assistantEl, currentViz, finalText);
            if (conv) {
              conv.messages.push({ role: 'assistant', content: finalText, timestamp: Date.now() });
            }
            break;
        }
      } catch {}
    }
  }
}

function renderFinal(assistantEl, viz, text) {
  let target;
  if (viz && viz.resultBody) {
    target = viz.resultBody;
  } else {
    const body = assistantEl.querySelector('.markdown-body');
    if (body) {
      body.innerHTML = '';
      target = body;
    }
  }
  if (target) {
    try { target.innerHTML = marked.parse(text); } catch { target.textContent = text; }
  }
  scrollChat();
}

// --- Review Tab ---
function initReviewTab() {
  const modeSelect = $('#review-mode');
  const effortField = $('#review-effort-field');
  const targetsField = $('#review-targets-field');

  modeSelect.addEventListener('change', () => {
    const isManual = modeSelect.value === 'manual';
    effortField.hidden = !isManual;
    targetsField.hidden = !isManual;
    if (isManual) renderTargets('review-targets');
  });

  $('#review-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    await runReview();
  });
}

async function runReview() {
  const path = $('#review-path').value.trim() || '.';
  const mode = $('#review-mode').value;
  const effort = $('#review-effort').value;
  const targets = getSelectedTargets('review-targets');

  const resultCard = $('#review-result');
  const output = $('#review-output');
  const status = $('#review-status');

  resultCard.hidden = false;
  status.className = 'status-badge running';
  status.textContent = 'Running…';
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
}

async function handleStreamReview(response, outputEl, statusEl) {
  const reader = response.body.getReader();
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
      } catch {}
    }
  }
}

// --- Providers Tab ---
async function loadProviders() {
  const container = $('#providers-list');
  container.innerHTML = '<div class="loading-state"><div class="spinner"></div><span>Loading providers…</span></div>';

  try {
    const resp = await fetch('/api/providers');
    const data = await resp.json();
    state.providers = data.providers;

    if (!data.providers.length) {
      container.innerHTML = '<p class="loading" style="text-align:center;grid-column:1/-1">No providers configured. Add API keys to .env</p>';
      return;
    }

    container.innerHTML = data.providers.map(p => {
      const dotClass = !p.enabled ? 'disabled' : (p.healthy ? 'healthy' : 'unhealthy');
      const statusText = !p.enabled ? 'Disabled' : (p.healthy ? 'Healthy' : 'Unhealthy');
      return `
        <div class="provider-card" role="listitem">
          <span class="provider-name">${esc(p.name)}</span>
          <span class="provider-status"><span class="status-dot ${dotClass}" aria-hidden="true"></span>${esc(statusText)}</span>
          <span class="provider-model">${esc(p.default_model || 'No default model')}</span>
        </div>
      `;
    }).join('');
  } catch (err) {
    container.innerHTML = `<p class="loading" style="text-align:center;grid-column:1/-1">Error: ${esc(err.message)}</p>`;
  }
}

$('#btn-refresh-providers')?.addEventListener('click', loadProviders);

// --- Config Tab ---
async function loadConfig() {
  const container = $('#config-list');
  container.innerHTML = '<div class="loading-state"><div class="spinner"></div><span>Loading config…</span></div>';

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

    container.innerHTML = rows.map(([key, val]) => `
      <div class="config-row" role="listitem">
        <span class="config-key">${esc(key)}</span>
        <span class="config-value">${esc(val)}</span>
      </div>
    `).join('');
  } catch (err) {
    container.innerHTML = `<p class="loading">Error: ${esc(err.message)}</p>`;
  }
}

// --- Models Tab ---
async function loadModels() {
  const container = $('#models-list');
  container.innerHTML = '<div class="loading-state"><div class="spinner"></div><span>Loading models…</span></div>';

  try {
    const resp = await fetch('/api/models');
    const data = await resp.json();
    state.models = data.models;
    renderModels(container, data.models);
  } catch (err) {
    container.innerHTML = `<p class="loading">Error: ${esc(err.message)}</p>`;
  }
}

function renderModels(container, models) {
  if (!models.length) {
    container.innerHTML = '<p class="loading" style="text-align:center">No models found</p>';
    return;
  }

  const groups = {};
  models.forEach(m => {
    if (!groups[m.provider]) groups[m.provider] = [];
    groups[m.provider].push(m);
  });

  container.innerHTML = Object.entries(groups).map(([provider, items]) => `
    <div class="model-group" role="listitem">
      <div class="model-group-title">
        ${esc(provider)} <span class="model-count">(${items.length})</span>
      </div>
      ${items.map(m => `
        <div class="model-item">
          <span class="model-id">${esc(m.id)}</span>
          <span class="model-display">${esc(m.display)}</span>
        </div>
      `).join('')}
    </div>
  `).join('');
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
    renderModels($('#models-list'), data.models);
    showToast('Models refreshed', 'success');
  } catch (err) {
    showToast('Refresh failed: ' + err.message, 'error');
  } finally {
    btn.classList.remove('spinning');
    btn.disabled = false;
  }
}

$('#btn-refresh-models')?.addEventListener('click', refreshModels);

// --- Keyboard Shortcuts ---
function initKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    // ⌘/Ctrl + 1-4 for tabs
    if ((e.metaKey || e.ctrlKey) && e.key >= '1' && e.key <= '4') {
      e.preventDefault();
      const tabs = $$('.nav-btn');
      const index = parseInt(e.key) - 1;
      if (tabs[index]) tabs[index].click();
    }

    // ⌘/Ctrl + N for new conversation
    if ((e.metaKey || e.ctrlKey) && e.key === 'n') {
      e.preventDefault();
      if (!$('#panel-research').hidden) newConversation();
    }

    // Escape to close targets panel
    if (e.key === 'Escape') {
      if (state.researchTargetsOpen) {
        state.researchTargetsOpen = false;
        $('#research-targets-panel').style.display = 'none';
        $('#btn-research-targets').setAttribute('aria-expanded', 'false');
      }
    }
  });
}

// --- Initialize ---
function init() {
  // Configure marked
  if (typeof marked !== 'undefined') {
    marked.setOptions({ breaks: true, gfm: true });
  }

  // Initialize all modules
  initTabs();
  initResearchModeToggle();
  initTargetsToggle();
  initChatInput();
  initReviewTab();
  initKeyboardShortcuts();

  // Bind buttons
  $('#btn-new-chat')?.addEventListener('click', newConversation);
  $('#btn-clear-all')?.addEventListener('click', clearAllHistory);

  // Initial render
  renderHistory();
  loadProviders(); // Load providers early for targets
}

// Start when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}