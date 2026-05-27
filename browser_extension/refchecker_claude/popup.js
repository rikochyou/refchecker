const fields = {
  serverUrl: document.getElementById('serverUrl'),
  threshold: document.getElementById('threshold'),
  searchMode: document.getElementById('searchMode'),
  llmParseMode: document.getElementById('llmParseMode'),
  outputDir: document.getElementById('outputDir'),
  pastedLinks: document.getElementById('pastedLinks'),
  pastedContext: document.getElementById('pastedContext'),
  enableFloatButton: document.getElementById('enableFloatButton'),
};
const statusEl = document.getElementById('status');
const sourceChipsEl = document.getElementById('sourceChips');
const sourceSummaryEl = document.getElementById('sourceSummary');
const sourceHelpEl = document.getElementById('sourceHelp');

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
let draggingSourceKey = '';
let suppressChipClick = false;

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
    searchMode: fields.searchMode.value || 'strict',
    doiCheck: 'auto',
    llmParseMode: fields.llmParseMode.value || 'off',
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

function moveSelectedSource(sourceKey, targetKey, position = 'before') {
  if (!sourceKey || !targetKey || sourceKey === targetKey) return false;
  const from = selectedSources.indexOf(sourceKey);
  const targetIndex = selectedSources.indexOf(targetKey);
  if (from < 0 || targetIndex < 0) return false;
  const next = [...selectedSources];
  const [item] = next.splice(from, 1);
  let insertIndex = next.indexOf(targetKey);
  if (insertIndex < 0) return false;
  if (position === 'after') insertIndex += 1;
  next.splice(insertIndex, 0, item);
  if (next.join(',') === selectedSources.join(',')) return false;
  selectedSources = next;
  return true;
}

function getDropPosition(event, row) {
  const rect = row.getBoundingClientRect();
  return event.clientX > rect.left + rect.width / 2 ? 'after' : 'before';
}

function setDropIndicator(row, position = '') {
  row.classList.toggle('drag-over', Boolean(position));
  row.classList.toggle('drag-over-before', position === 'before');
  row.classList.toggle('drag-over-after', position === 'after');
}

function clearDropIndicators() {
  sourceChipsEl
    .querySelectorAll('.drag-over, .drag-over-before, .drag-over-after')
    .forEach((row) => setDropIndicator(row));
}

function suppressNextChipClick() {
  suppressChipClick = true;
  setTimeout(() => {
    suppressChipClick = false;
  }, 250);
}

function createSourceChip(option, order) {
  const isSelected = order >= 0;
  const chip = document.createElement('button');
  chip.type = 'button';
  chip.className = `source-chip${isSelected ? ' selected' : ''}`;
  chip.dataset.source = option.key;
  chip.draggable = isSelected;
  chip.title = isSelected
    ? `已参与搜索链，优先级 ${order + 1}；拖拽排序，单击退出`
    : '未参与搜索链；单击加入';
  chip.innerHTML = isSelected
    ? `<span class="order">${order + 1}</span><span>${option.label}</span>`
    : `<span>${option.label}</span>`;

  if (isSelected) {
    chip.addEventListener('dragstart', (event) => {
      draggingSourceKey = option.key;
      chip.classList.add('dragging');
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', option.key);
    });
    chip.addEventListener('dragover', (event) => {
      event.preventDefault();
      if (draggingSourceKey && draggingSourceKey !== option.key) {
        setDropIndicator(chip, getDropPosition(event, chip));
        event.dataTransfer.dropEffect = 'move';
      }
    });
    chip.addEventListener('dragleave', () => setDropIndicator(chip));
    chip.addEventListener('drop', async (event) => {
      event.preventDefault();
      const position = getDropPosition(event, chip);
      clearDropIndicators();
      const sourceKey = event.dataTransfer.getData('text/plain') || draggingSourceKey;
      draggingSourceKey = '';
      suppressNextChipClick();
      if (moveSelectedSource(sourceKey, option.key, position)) {
        renderSourceChips();
        await saveSettings();
      }
    });
    chip.addEventListener('dragend', () => {
      if (draggingSourceKey) suppressNextChipClick();
      draggingSourceKey = '';
      chip.classList.remove('dragging');
      clearDropIndicators();
    });
  }

  chip.addEventListener('click', async (event) => {
    if (suppressChipClick) {
      event.preventDefault();
      event.stopPropagation();
      return;
    }
    if (selectedSources.includes(option.key)) {
      selectedSources = selectedSources.filter((key) => key !== option.key);
      if (!selectedSources.length) {
        selectedSources = [...RECOMMENDED_SOURCE_KEYS];
        setStatus('至少需要一个数据源，已恢复推荐组合。');
      }
    } else {
      selectedSources = [...selectedSources, option.key];
    }
    renderSourceChips();
    await saveSettings();
  });

  return chip;
}

function renderSourceChips() {
  const selectedSet = new Set(selectedSources);
  sourceChipsEl.innerHTML = '';

  const displayKeys = [
    ...selectedSources,
    ...SOURCE_OPTIONS.map((item) => item.key).filter((key) => !selectedSet.has(key)),
  ];
  displayKeys.forEach((key) => {
    const option = SOURCE_OPTIONS.find((item) => item.key === key);
    if (!option) return;
    sourceChipsEl.appendChild(createSourceChip(option, selectedSources.indexOf(key)));
  });

  const mode = fields.searchMode.value || 'strict';
  sourceHelpEl.textContent = mode === 'parallel'
    ? '快速并发：多源同时查询；拖拽带数字的小标签调整优先级，单击可加入/退出搜索链。Springer、IEEE、CORE 需要先配置 API Key。'
    : '严格顺序：按数字顺序逐个查询；拖拽小标签排序，单击可加入/退出搜索链。Springer、IEEE、CORE 需要先配置 API Key。';
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
  fields.searchMode.value = settings.searchMode || 'strict';
  fields.llmParseMode.value = settings.llmParseMode || 'off';
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
  input.addEventListener('change', async () => {
    if (input === fields.searchMode) renderSourceChips();
    await saveSettings();
  });
}

renderSourceChips();
loadSettings();
