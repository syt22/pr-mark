const editableFields = [
  'source_type', 'target', 'project_status', 'candidates', 'choice',
  'scope', 'evidence', 'rationale', 'other',
];

const state = { items: [], selectedId: null, saveTimer: null, loadingRecord: false };
const elements = {
  list: document.querySelector('#source-list'),
  count: document.querySelector('#record-count'),
  search: document.querySelector('#search'),
  scopeFilter: document.querySelector('#scope-filter'),
  typeFilter: document.querySelector('#type-filter'),
  form: document.querySelector('#annotation-form'),
  empty: document.querySelector('#empty-state'),
  saveStatus: document.querySelector('#save-status'),
  notice: document.querySelector('#notice'),
};

function escapeText(value) {
  const span = document.createElement('span');
  span.textContent = value || '';
  return span.innerHTML;
}

function sourceLabel(item) {
  const type = item.source_type.replace('github_', '').toUpperCase();
  const id = item.source_number_or_id ? ` #${item.source_number_or_id}` : '';
  return `${type}${id}`;
}

function sourceTitle(item) {
  if (item.repository) return item.repository;
  try { return new URL(item.url).hostname; } catch (_) { return item.url; }
}

function renderList() {
  elements.list.innerHTML = '';
  if (!state.items.length) {
    elements.list.innerHTML = '<p class="list-empty">No matching sources.</p>';
    return;
  }
  for (const item of state.items) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `source-item${item.id === state.selectedId ? ' selected' : ''}`;
    button.dataset.id = item.id;
    button.innerHTML = `
      <strong>${escapeText(sourceTitle(item))}</strong>
      <span>${escapeText(sourceLabel(item))}</span>
      <small>${escapeText(item.scope)}${item.choice ? ` | ${escapeText(item.choice)}` : ''}</small>
    `;
    button.addEventListener('click', () => selectSource(item.id));
    elements.list.appendChild(button);
  }
}

async function loadSources(preserveSelection = true) {
  const params = new URLSearchParams({
    q: elements.search.value.trim(),
    scope: elements.scopeFilter.value,
    source_type: elements.typeFilter.value,
  });
  const response = await fetch(`/api/sources?${params}`);
  if (!response.ok) throw new Error('Could not load sources.');
  const data = await response.json();
  state.items = data.items;
  elements.count.textContent = `${data.shown} / ${data.total}`;
  if (!preserveSelection || !state.items.some((item) => item.id === state.selectedId)) {
    state.selectedId = state.items[0]?.id ?? null;
  }
  renderList();
  if (state.selectedId) await selectSource(state.selectedId, false);
  else showEmptyState();
}

function showEmptyState() {
  elements.form.hidden = true;
  elements.empty.hidden = false;
}

async function selectSource(id, rerender = true) {
  flushPendingSave();
  state.selectedId = Number(id);
  if (rerender) renderList();
  const response = await fetch(`/api/sources/${state.selectedId}`);
  if (!response.ok) return showNotice('Could not load this source.', true);
  const item = await response.json();
  state.loadingRecord = true;
  for (const field of editableFields) elements.form.elements[field].value = item[field] || '';
  state.loadingRecord = false;
  document.querySelector('#summary-type').textContent = item.source_type;
  document.querySelector('#summary-repository').textContent = item.repository || '';
  document.querySelector('#summary-id').textContent = item.source_number_or_id || '';
  const sourceUrl = document.querySelector('#source-url');
  sourceUrl.textContent = item.url;
  sourceUrl.href = item.url;
  document.querySelector('#open-source').href = item.url;
  elements.empty.hidden = true;
  elements.form.hidden = false;
  elements.saveStatus.textContent = 'Saved';
  elements.saveStatus.className = 'save-status saved';
}

function collectFormData() {
  return Object.fromEntries(editableFields.map((field) => [field, elements.form.elements[field].value]));
}

function scheduleSave() {
  if (state.loadingRecord || !state.selectedId) return;
  clearTimeout(state.saveTimer);
  elements.saveStatus.textContent = 'Saving…';
  elements.saveStatus.className = 'save-status saving';
  state.saveTimer = setTimeout(saveCurrent, 650);
}

async function saveCurrent() {
  clearTimeout(state.saveTimer);
  state.saveTimer = null;
  if (!state.selectedId) return;
  const id = state.selectedId;
  try {
    const response = await fetch(`/api/sources/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(collectFormData()),
    });
    if (!response.ok) throw new Error();
    const updated = await response.json();
    const index = state.items.findIndex((item) => item.id === id);
    if (index >= 0) state.items[index] = updated;
    renderList();
    elements.saveStatus.textContent = 'Saved';
    elements.saveStatus.className = 'save-status saved';
  } catch (_) {
    elements.saveStatus.textContent = 'Save failed';
    elements.saveStatus.className = 'save-status failed';
  }
}

function flushPendingSave() {
  if (state.saveTimer) saveCurrent();
}

function showNotice(message, error = false) {
  elements.notice.textContent = message;
  elements.notice.className = `notice${error ? ' error' : ''}`;
  elements.notice.hidden = false;
  clearTimeout(showNotice.timer);
  showNotice.timer = setTimeout(() => { elements.notice.hidden = true; }, 7000);
}

async function syncSources() {
  const button = document.querySelector('#sync-button');
  button.disabled = true;
  button.textContent = 'Syncing…';
  try {
    const response = await fetch('/api/sync', { method: 'POST' });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Sync failed');
    showNotice(`Found ${data.found} URLs · Added ${data.added} new sources · Already existed ${data.existing} sources`);
    await loadSources();
  } catch (error) {
    showNotice(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = 'Sync from GoodData.md';
  }
}

let filterTimer;
function scheduleFilter() {
  clearTimeout(filterTimer);
  filterTimer = setTimeout(() => loadSources(), 250);
}

elements.form.addEventListener('input', scheduleSave);
elements.form.addEventListener('change', scheduleSave);
elements.search.addEventListener('input', scheduleFilter);
elements.scopeFilter.addEventListener('change', () => loadSources());
elements.typeFilter.addEventListener('change', () => loadSources());
document.querySelector('#sync-button').addEventListener('click', syncSources);
window.addEventListener('beforeunload', flushPendingSave);

loadSources().catch(() => showNotice('Could not connect to the local server.', true));
