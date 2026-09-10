const editableFields = [
  'source_type', 'target', 'project_status', 'candidates', 'choice',
  'scope', 'evidence', 'rationale', 'other',
];

const translations = {
  'zh-CN': {
    appTitle: '语言选择证据标注工具', appSubtitle: 'MLCA 人工标注工作区', pageLanguage: '页面语言',
    syncButton: '从 GoodData.md 同步', syncing: '同步中…', exportCsv: '导出 CSV', exportJson: '导出 JSON',
    sources: '数据源', searchPlaceholder: '搜索 URL、仓库、Choice 或 Target…', scope: '范围', sourceType: '数据源类型', all: '全部',
    noSourceTitle: '尚未选择数据源', noSourceText: '请先同步 Markdown 输入文件，然后从左侧选择一条记录。',
    openSource: '打开原始页面', target: 'Target', targetHint: '在给哪个 function / feature / module 选语言',
    status: 'Status', statusHint: '决策时点、已有语言、依赖、FFI、build support 等项目上下文',
    candidates: 'Candidates', candidatesHint: '当时现实可行的候选语言', choice: 'Choice', choiceHint: '最终采用的语言',
    evidence: 'Evidence', evidenceHint: '支持判断的证据，可包含多条说明和 URL',
    rationale: 'Rationale', rationaleHint: '没有明确证据时填写 unknown',
    other: 'Other', otherHint: '边界情况、AI assistance、待检查链接等研究备注',
    noMatches: '没有符合筛选条件的数据源。', loadSourcesFailed: '无法加载数据源。', loadSourceFailed: '无法加载这条数据源。',
    saving: '保存中…', saved: '已保存', saveFailed: '保存失败', connectionFailed: '无法连接本地服务器。', syncFailed: '同步失败',
    syncResult: ({ found, added, existing }) => `找到 ${found} 个 URL · 新增 ${added} 条数据源 · 已存在 ${existing} 条数据源`,
    scopeValues: { all: '全部', function: '函数', module: '模块', project: '项目', unknown: '未知' },
  },
  en: {
    appTitle: 'Language-Choice Evidence Annotation Tool', appSubtitle: 'MLCA manual annotation workspace', pageLanguage: 'Language',
    syncButton: 'Sync from GoodData.md', syncing: 'Syncing…', exportCsv: 'Export CSV', exportJson: 'Export JSON',
    sources: 'Sources', searchPlaceholder: 'Search URL, repository, choice…', scope: 'Scope', sourceType: 'Source type', all: 'all',
    noSourceTitle: 'No source selected', noSourceText: 'Sync the Markdown input, then select a source from the list.',
    openSource: 'Open Source', target: 'Target', targetHint: 'Function, feature, or module for which a language was selected',
    status: 'Status', statusHint: 'Decision point, existing languages, dependencies, FFI, build support, and project context',
    candidates: 'Candidates', candidatesHint: 'Languages that were realistically viable at the time', choice: 'Choice', choiceHint: 'Language ultimately selected',
    evidence: 'Evidence', evidenceHint: 'Supporting evidence, including multiple notes or URLs',
    rationale: 'Rationale', rationaleHint: 'Enter unknown when there is no explicit evidence',
    other: 'Other', otherHint: 'Boundary cases, AI assistance, follow-up links, and research notes',
    noMatches: 'No matching sources.', loadSourcesFailed: 'Could not load sources.', loadSourceFailed: 'Could not load this source.',
    saving: 'Saving…', saved: 'Saved', saveFailed: 'Save failed', connectionFailed: 'Could not connect to the local server.', syncFailed: 'Sync failed',
    syncResult: ({ found, added, existing }) => `Found ${found} URLs · Added ${added} new sources · Already existed ${existing} sources`,
    scopeValues: { all: 'all', function: 'function', module: 'module', project: 'project', unknown: 'unknown' },
  },
};

let currentLanguage = localStorage.getItem('pr-mark-language') || (navigator.language.toLowerCase().startsWith('zh') ? 'zh-CN' : 'en');
if (!translations[currentLanguage]) currentLanguage = 'en';

function t(key, data) {
  const value = translations[currentLanguage][key];
  return typeof value === 'function' ? value(data) : (value ?? key);
}

function translatedScope(value) {
  return translations[currentLanguage].scopeValues[value] || value;
}

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
  languageSelect: document.querySelector('#language-select'),
};

function setSaveStatus(status) {
  elements.saveStatus.dataset.status = status;
  elements.saveStatus.textContent = t(status);
  const cssClass = status === 'saveFailed' ? 'failed' : status;
  elements.saveStatus.className = `save-status ${cssClass}`;
}

function applyLanguage() {
  document.documentElement.lang = currentLanguage;
  document.title = t('appTitle');
  elements.languageSelect.value = currentLanguage;
  document.querySelectorAll('[data-i18n]').forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach((element) => {
    element.placeholder = t(element.dataset.i18nPlaceholder);
  });
  document.querySelectorAll('[data-enum-kind="scope"]').forEach((option) => {
    option.textContent = translatedScope(option.value);
  });
  if (elements.saveStatus.dataset.status) setSaveStatus(elements.saveStatus.dataset.status);
  renderList();
}

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
    elements.list.innerHTML = `<p class="list-empty">${escapeText(t('noMatches'))}</p>`;
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
      <small>${escapeText(translatedScope(item.scope))}${item.choice ? ` | ${escapeText(item.choice)}` : ''}</small>
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
  if (!response.ok) throw new Error(t('loadSourcesFailed'));
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
  if (!response.ok) return showNotice(t('loadSourceFailed'), true);
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
  setSaveStatus('saved');
}

function collectFormData() {
  return Object.fromEntries(editableFields.map((field) => [field, elements.form.elements[field].value]));
}

function scheduleSave() {
  if (state.loadingRecord || !state.selectedId) return;
  clearTimeout(state.saveTimer);
  setSaveStatus('saving');
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
    setSaveStatus('saved');
  } catch (_) {
    setSaveStatus('saveFailed');
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
  button.textContent = t('syncing');
  try {
    const response = await fetch('/api/sync', { method: 'POST' });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || t('syncFailed'));
    showNotice(t('syncResult', data));
    await loadSources();
  } catch (error) {
    showNotice(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = t('syncButton');
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
elements.languageSelect.addEventListener('change', () => {
  currentLanguage = elements.languageSelect.value;
  localStorage.setItem('pr-mark-language', currentLanguage);
  applyLanguage();
});
window.addEventListener('beforeunload', flushPendingSave);

applyLanguage();
loadSources().catch(() => showNotice(t('connectionFailed'), true));
