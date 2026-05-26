const fields = {
  serverUrl: document.getElementById('serverUrl'),
  threshold: document.getElementById('threshold'),
  outputDir: document.getElementById('outputDir'),
  pastedLinks: document.getElementById('pastedLinks'),
  pastedContext: document.getElementById('pastedContext'),
  enableFloatButton: document.getElementById('enableFloatButton'),
};
const statusEl = document.getElementById('status');
const sourceChipsEl = document.getElementById('sourceChips');
const sourceSummaryEl = document.getElementById('sourceSummary');

const SOURCE_OPTIONS = [
  { key: 'crossref', label: 'CrossRef' },
  { key: 'openalex', label: 'OpenAlex' },
  { key: 'semantic-scholar', label: 'Semantic Scholar' },
  { key: 'arxiv', label: 'arXiv' },
  { key: 'pubmed', label: 'PubMed' },
  { key: 'dblp', label: 'DBLP' },
  { key: 'url', label: 'URL 链接核查' },
  { key: 'springer', label: 'Springer' },
  { key: 'ieee', label: 'IEEE' },
  { key: 'core', label: 'CORE' },
];
const RECOMMENDED_SOURCE_KEYS = [
  'crossref',
  'openalex',
  'semantic-scholar',
  'arxiv',
  'pubmed',
  'dblp',
  'url',
];
const SOURCE_KEY_SET = new Set(SOURCE_OPTIONS.map((item) => item.key));
const SOURCE_LABELS = Object.fromEntries(SOURCE_OPTIONS.map((item) => [item.key, item.label]));
let selectedSources = [...RECOMMENDED_SOURCE_KEYS];

function setStatus(text, isError = false) {
  statusEl.textContent = text;
  statusEl.style.color = isError ? '#a23a33' : '#52615a';
}

function sendMessage(message) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(message, (response) => {
      const error = chrome.runtime.lastError;
      if (error) {
        resolve({ ok: false, error: error.message });
      } else {
        resolve(response || { ok: false, error: 'No response.' });
      }
    });
  });
}

function collectSettings() {
  return {
    serverUrl: fields.serverUrl.value.trim(),
    threshold: Number(fields.threshold.value || 0.85),
    sources: selectedSources.join(','),
    outputDir: fields.outputDir.value.trim(),
    enableFloatButton: fields.enableFloatButton.checked,
  };
}

async function saveSettings() {
  const response = await sendMessage({ type: 'SAVE_SETTINGS', settings: collectSettings() });
  if (!response.ok) {
    setStatus(response.error || '保存设置失败', true);
    return null;
  }
  return response.settings;
}

function parseSources(value) {
  const parsed = String(value || '')
    .split(',')
    .map((item) => item.trim().toLowerCase())
    .filter((item) => SOURCE_KEY_SET.has(item));
  return parsed.length ? [...new Set(parsed)] : [...RECOMMENDED_SOURCE_KEYS];
}

function renderSourceChips() {
  const selectedSet = new Set(selectedSources);
  sourceChipsEl.innerHTML = '';
  for (const option of SOURCE_OPTIONS) {
    const order = selectedSources.indexOf(option.key);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `source-chip${selectedSet.has(option.key) ? ' selected' : ''}`;
    button.dataset.source = option.key;
    button.title = selectedSet.has(option.key)
      ? `已选择，优先级 ${order + 1}；点击取消`
      : '点击加入数据源优先级';
    button.innerHTML = selectedSet.has(option.key)
      ? `<span class="order">${order + 1}</span><span>${option.label}</span>`
      : `<span>${option.label}</span>`;
    button.addEventListener('click', async () => {
      if (selectedSet.has(option.key)) {
        selectedSources = selectedSources.filter((key) => key !== option.key);
      } else {
        selectedSources = [...selectedSources, option.key];
      }
      if (!selectedSources.length) {
        selectedSources = [...RECOMMENDED_SOURCE_KEYS];
      }
      renderSourceChips();
      await saveSettings();
    });
    sourceChipsEl.appendChild(button);
  }

  sourceSummaryEl.textContent = `当前优先级：${selectedSources.map((key) => SOURCE_LABELS[key] || key).join(' → ')}`;
}

async function loadSettings() {
  const response = await sendMessage({ type: 'GET_SETTINGS' });
  if (!response.ok) {
    setStatus(response.error || '读取设置失败', true);
    return;
  }
  const settings = response.settings || {};
  fields.serverUrl.value = settings.serverUrl || 'http://127.0.0.1:8765';
  fields.threshold.value = settings.threshold || 0.85;
  fields.outputDir.value = settings.outputDir || '';
  fields.enableFloatButton.checked = settings.enableFloatButton !== false;
  selectedSources = parseSources(settings.sources);
  renderSourceChips();
}

document.getElementById('recommendedSources').addEventListener('click', async () => {
  selectedSources = [...RECOMMENDED_SOURCE_KEYS];
  renderSourceChips();
  await saveSettings();
});

document.getElementById('allSources').addEventListener('click', async () => {
  selectedSources = SOURCE_OPTIONS.map((item) => item.key);
  renderSourceChips();
  await saveSettings();
});

document.getElementById('health').addEventListener('click', async () => {
  await saveSettings();
  setStatus('正在测试连接……');
  const response = await sendMessage({ type: 'HEALTH_CHECK' });
  if (response.ok) {
    setStatus(`连接正常：RefChecker ${response.payload && response.payload.version ? response.payload.version : ''}`);
  } else {
    setStatus(response.error || '连接失败，请确认 RefChecker 桌面版已打开。', true);
  }
});

document.getElementById('checkSelection').addEventListener('click', async () => {
  await saveSettings();
  setStatus('已发送核查请求，弹窗将自动收起，请查看网页右侧面板。');
  const request = sendMessage({ type: 'CHECK_ACTIVE_SELECTION' });
  setTimeout(() => window.close(), 180);
  const response = await request;
  if (!response.ok) setStatus(response.error || '核查失败', true);
});

document.getElementById('checkPasted').addEventListener('click', async () => {
  await saveSettings();
  const text = fields.pastedLinks.value.trim();
  if (!text) {
    setStatus('请先粘贴复制到的 URL 或 DOI。', true);
    return;
  }
  if (!/(https?:\/\/|doi\.org\/|(?:^|\s)10\.\d{4,9}\/)/i.test(text)) {
    setStatus('未识别到 URL 或 DOI，请粘贴复制到的真实链接。', true);
    return;
  }
  setStatus('已发送链接核查请求，弹窗将自动收起，请查看网页右侧面板。');
  const request = sendMessage({
    type: 'CHECK_PASTED_LINKS',
    text,
    context: fields.pastedContext.value.trim(),
  });
  setTimeout(() => window.close(), 180);
  const response = await request;
  if (!response.ok) setStatus(response.error || '链接核查失败', true);
});

for (const input of Object.values(fields)) {
  input.addEventListener('change', saveSettings);
}

renderSourceChips();
loadSettings();
