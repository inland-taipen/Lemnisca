const API_BASE = 'http://localhost:8000';

const state = {
  conversationId: null,
  isLoading: false,
  stats: { queries: 0, tokens: 0, simple: 0, complex: 0 },
};

const messagesEl      = document.getElementById('messages');
const welcomeState    = document.getElementById('welcome-state');
const queryInput      = document.getElementById('query-input');
const sendBtn         = document.getElementById('send-btn');
const debugPanel      = document.getElementById('debug-panel');
const sourcesList     = document.getElementById('sources-list');
const sidebar         = document.getElementById('sidebar');
const sidebarOpenBtn  = document.getElementById('sidebar-open-btn');
const sidebarCloseBtn = document.getElementById('sidebar-close-btn');
const clearBtn        = document.getElementById('clear-btn');
const modelBadge      = document.getElementById('model-badge');

const statQueries = document.getElementById('stat-queries');
const statTokens  = document.getElementById('stat-tokens');
const statSimple  = document.getElementById('stat-simple');
const statComplex = document.getElementById('stat-complex');

// sidebar toggle
sidebarOpenBtn.addEventListener('click', () => sidebar.classList.toggle('hidden'));
sidebarCloseBtn.addEventListener('click', () => sidebar.classList.add('hidden'));

const charCount = document.getElementById('char-count');
const chatScroll = document.querySelector('.chat');

// auto-resize + char counter
queryInput.addEventListener('input', () => {
  queryInput.style.height = 'auto';
  queryInput.style.height = Math.min(queryInput.scrollHeight, 150) + 'px';
  sendBtn.disabled = !queryInput.value.trim() || state.isLoading;
  const len = queryInput.value.length;
  if (len > 0) {
    charCount.textContent = len;
    charCount.classList.toggle('warn', len > 800);
  } else {
    charCount.textContent = '';
  }
});

// enter to send
queryInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (!sendBtn.disabled) sendQuery();
  }
});
sendBtn.addEventListener('click', sendQuery);

// chips
document.querySelectorAll('.chip').forEach((c) => {
  c.addEventListener('click', () => {
    queryInput.value = c.dataset.query;
    queryInput.dispatchEvent(new Event('input'));
    sendQuery();
  });
});

// clear
clearBtn.addEventListener('click', () => {
  state.conversationId = null;
  messagesEl.querySelectorAll('.message').forEach((m) => m.remove());
  welcomeState.style.display = 'flex';
  welcomeState.classList.remove('welcome-reappear');
  void welcomeState.offsetWidth;
  welcomeState.classList.add('welcome-reappear');
  updateDebugPanel(null);
  updateSources([]);
  modelBadge.textContent = 'Ready';
  modelBadge.className = 'model-badge';
  charCount.textContent = '';
});

// markdown
function md(text) {
  return text
    .replace(/```[\s\S]*?```/g, (m) => {
      const code = m.replace(/```\w*\n?/, '').replace(/```$/, '');
      return `<pre><code>${esc(code.trim())}</code></pre>`;
    })
    .replace(/`([^`]+)`/g, (_, c) => `<code>${esc(c)}</code>`)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>')
    .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>');
}
function esc(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

// message bubble
function createMessage(role, content, flagMsg = '') {
  const wrap = document.createElement('div');
  wrap.className = `message ${role}`;

  const av = document.createElement('div');
  av.className = 'msg-avatar';
  av.setAttribute('aria-hidden', 'true');
  av.textContent = role === 'user' ? 'Y' : 'C';

  const body = document.createElement('div');
  body.className = 'msg-body';

  const roleLabel = document.createElement('p');
  roleLabel.className = 'msg-role';
  roleLabel.textContent = role === 'user' ? 'You' : 'ClearPath';
  body.appendChild(roleLabel);

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  if (role === 'assistant') bubble.innerHTML = `<p>${md(content)}</p>`;
  else bubble.textContent = content;
  body.appendChild(bubble);

  const time = document.createElement('p');
  time.className = 'msg-time';
  time.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  body.appendChild(time);

  if (flagMsg) {
    const f = document.createElement('div');
    f.className = 'flag-message';
    f.textContent = flagMsg;
    body.appendChild(f);
  }

  wrap.appendChild(av);
  wrap.appendChild(body);
  return wrap;
}

// typing indicator
function createTypingIndicator() {
  const wrap = document.createElement('div');
  wrap.className = 'message assistant';
  wrap.id = 'typing-indicator';

  const av = document.createElement('div');
  av.className = 'msg-avatar';
  av.setAttribute('aria-hidden', 'true');
  av.textContent = 'C';

  const body = document.createElement('div');
  body.className = 'msg-body';
  const ind = document.createElement('div');
  ind.className = 'typing-indicator';

  const dots = document.createElement('span');
  dots.className = 'typing-dots';
  for (let i = 0; i < 3; i++) {
    const d = document.createElement('div');
    d.className = 'typing-dot';
    dots.appendChild(d);
  }
  ind.appendChild(dots);

  const lbl = document.createElement('span');
  lbl.className = 'typing-label';
  lbl.textContent = 'Thinking\u2026';
  ind.appendChild(lbl);

  body.appendChild(ind);
  wrap.appendChild(av);
  wrap.appendChild(body);
  return wrap;
}

// debug panel
function updateDebugPanel(data) {
  if (!data) { debugPanel.innerHTML = '<p class="empty-text">Send a message to inspect</p>'; return; }
  const m = data.metadata;
  const flags = m.evaluator_flags || [];
  const fHtml = flags.length
    ? flags.map((f) => `<span class="badge ${f === 'no_context' ? 'badge-error' : 'badge-warning'}">${f}</span>`).join(' ')
    : '<span style="color:var(--ok);font-size:.78rem">\u2713 None</span>';
  const cls = m.classification === 'simple' ? 'teal' : 'accent';
  debugPanel.innerHTML = `
    <div class="debug-row"><span class="debug-label">Model</span><span class="debug-value accent">${m.model_used}</span></div>
    <div class="debug-row"><span class="debug-label">Route</span><span class="debug-value ${cls}">${m.classification}</span></div>
    <div class="debug-row"><span class="debug-label">Rule</span><span class="debug-value">${m.rule_triggered || '\u2014'}</span></div>
    <div class="debug-row"><span class="debug-label">In</span><span class="debug-value">${m.tokens.input.toLocaleString()}</span></div>
    <div class="debug-row"><span class="debug-label">Out</span><span class="debug-value">${m.tokens.output.toLocaleString()}</span></div>
    <div class="debug-row"><span class="debug-label">Latency</span><span class="debug-value teal">${m.latency_ms} ms</span></div>
    <div class="debug-row"><span class="debug-label">Chunks</span><span class="debug-value">${m.chunks_retrieved}</span></div>
    <div class="debug-row"><span class="debug-label">Flags</span><span class="debug-value">${fHtml}</span></div>`;
}

// sources
function updateSources(sources) {
  if (!sources || !sources.length) { sourcesList.innerHTML = '<p class="empty-text">No sources yet</p>'; return; }
  sourcesList.innerHTML = sources.map((s) => `
    <div class="source-item">
      <div class="source-doc">${s.document}</div>
      <div class="source-meta">
        <span>pg ${s.page ?? '\u2014'}</span>
        <span class="source-score">${s.relevance_score !== undefined ? (s.relevance_score * 100).toFixed(0) + '%' : '\u2014'}</span>
      </div>
    </div>`).join('');
}

// stats
function updateStats(m) {
  state.stats.queries++;
  state.stats.tokens += m.tokens.input + m.tokens.output;
  if (m.classification === 'simple') state.stats.simple++; else state.stats.complex++;
  statQueries.textContent = state.stats.queries;
  statTokens.textContent  = state.stats.tokens.toLocaleString();
  statSimple.textContent  = state.stats.simple;
  statComplex.textContent = state.stats.complex;
}

function updateModelBadge(m) {
  modelBadge.textContent = m.classification === 'simple' ? '8B' : '70B';
  modelBadge.className = `model-badge ${m.classification}`;
}

// send
async function sendQuery() {
  const q = queryInput.value.trim();
  if (!q || state.isLoading) return;
  queryInput.value = '';
  queryInput.style.height = 'auto';
  sendBtn.disabled = true;
  charCount.textContent = '';
  if (welcomeState) welcomeState.style.display = 'none';

  messagesEl.appendChild(createMessage('user', q));
  const typing = createTypingIndicator();
  messagesEl.appendChild(typing);
  scrollToBottom();
  state.isLoading = true;
  sendBtn.classList.add('is-loading');

  try {
    const payload = { question: q };
    if (state.conversationId) payload.conversation_id = state.conversationId;
    const res = await fetch(`${API_BASE}/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || `Error ${res.status}`); }
    const data = await res.json();
    state.conversationId = data.conversation_id;
    typing.remove();
    messagesEl.appendChild(createMessage('assistant', data.answer, data.metadata.flag_message || ''));
    updateDebugPanel(data);
    updateSources(data.sources);
    updateStats(data.metadata);
    updateModelBadge(data.metadata);
  } catch (err) {
    typing.remove();
    messagesEl.appendChild(createMessage('assistant', `Could not reach the server. Make sure the backend is running on \`localhost:8000\`.\n\n_${err.message}_`));
  } finally {
    state.isLoading = false;
    sendBtn.classList.remove('is-loading');
    sendBtn.disabled = !queryInput.value.trim();
    scrollToBottom();
    queryInput.focus();
  }
}

function scrollToBottom() {
  chatScroll.scrollTo({ top: chatScroll.scrollHeight, behavior: 'smooth' });
}

queryInput.focus();
