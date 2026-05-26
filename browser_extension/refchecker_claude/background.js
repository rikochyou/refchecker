const DEFAULT_SETTINGS = {
  serverUrl: 'http://127.0.0.1:8765',
  threshold: 0.85,
  outputDir: '',
  sources: '',
  enableFloatButton: true,
};
const KNOWN_SOURCES = [
  'crossref',
  'openalex',
  'semantic-scholar',
  'arxiv',
  'pubmed',
  'dblp',
  'url',
  'springer',
  'ieee',
  'core',
];

function unsupportedPageMessage(url) {
  try {
    const parsed = new URL(url || '');
    if (parsed.hostname.endsWith('claude.ai') && parsed.pathname.startsWith('/api/')) {
      return '当前打开的是 Claude 的接口 JSON 页面，不是正常聊天页面。请回到 https://claude.ai/new 或浏览器后退后再核查。';
    }
  } catch (error) {
    // Ignore invalid URLs.
  }
  return '';
}

async function getSettings() {
  const stored = await chrome.storage.sync.get(DEFAULT_SETTINGS);
  return { ...DEFAULT_SETTINGS, ...stored };
}

async function saveSettings(next) {
  await chrome.storage.sync.set(next);
  return getSettings();
}

async function sendToTab(tabId, message) {
  try {
    await chrome.tabs.sendMessage(tabId, message);
    return;
  } catch (error) {
    await chrome.scripting.insertCSS({
      target: { tabId },
      files: ['panel.css'],
    }).catch(() => {});
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ['content.js'],
    });
    await chrome.tabs.sendMessage(tabId, message);
  }
}

function collectSelectionPayloadInPage() {
  const text = window.getSelection ? window.getSelection().toString().trim() : '';
  return { text };
}

async function getSelectionPayloadFromTab(tabId) {
  const [result] = await chrome.scripting.executeScript({
    target: { tabId },
    func: collectSelectionPayloadInPage,
  });
  const payload = result && result.result ? result.result : {};
  return { text: (payload.text || '').trim() };
}

function normalizeServerUrl(url) {
  return (url || DEFAULT_SETTINGS.serverUrl).replace(/\/+$/, '');
}

function parseSources(value) {
  return String(value || '')
    .split(',')
    .map((item) => item.trim().toLowerCase())
    .filter((item) => KNOWN_SOURCES.includes(item));
}

function cleanCopiedUrl(value) {
  return String(value || '')
    .trim()
    .replace(/[，。；;、)）\]】>]+$/g, '');
}

function firstContextLine(value) {
  return (String(value || '').split(/\r?\n/).find((line) => {
    const clean = line.replace(/\s+/g, ' ').trim();
    return clean.length >= 8 && !/^https?:\/\//i.test(clean);
  }) || '').trim();
}

function extractPastedLinks(text, fallbackLabel = '') {
  const links = [];
  const seen = new Set();
  const contextLabel = firstContextLine(fallbackLabel);
  const surroundingText = [fallbackLabel, text]
    .filter(Boolean)
    .join('\n')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 600);
  const add = (label, href) => {
    const cleanHref = cleanCopiedUrl(href);
    if (!cleanHref) return;
    const normalizedHref = cleanHref.startsWith('http')
      ? cleanHref
      : `https://doi.org/${cleanHref.replace(/^doi:\s*/i, '')}`;
    const key = normalizedHref.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    links.push({
      text: (label || contextLabel || normalizedHref).trim().slice(0, 240),
      href: normalizedHref,
      title: '',
      ariaLabel: '',
      surroundingText,
    });
  };

  const markdownRe = /\[([^\]]{1,240})\]\((https?:\/\/[^)\s]+)\)/gi;
  let match;
  while ((match = markdownRe.exec(text)) !== null) {
    add(match[1], match[2]);
  }

  for (const line of String(text || '').split(/\r?\n/)) {
    const urlRe = /https?:\/\/[^\s"'<>]+/gi;
    let urlMatch;
    while ((urlMatch = urlRe.exec(line)) !== null) {
      const url = cleanCopiedUrl(urlMatch[0]);
      const label = line.replace(urlMatch[0], '').replace(/[\[\]():：-]+/g, ' ').replace(/\s+/g, ' ').trim();
      add(label || url, url);
    }
  }

  const doiRe = /(?:doi:\s*|https?:\/\/(?:dx\.)?doi\.org\/)?(10\.\d{4,9}\/[^\s"'<>，。；;、)）\]】]+)/gi;
  while ((match = doiRe.exec(text)) !== null) {
    add(fallbackLabel || 'DOI', match[1]);
  }

  return links;
}

async function callRefChecker(text, settings, context = {}) {
  const serverUrl = normalizeServerUrl(settings.serverUrl);
  const selectedSources = parseSources(settings.sources);
  const controller = new AbortController();
  const timeoutMs = Boolean(context.linksOnly) ? 45000 : 180000;
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${serverUrl}/check-text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: controller.signal,
      body: JSON.stringify({
        text,
        threshold: Number(settings.threshold || DEFAULT_SETTINGS.threshold),
        output_dir: settings.outputDir || '',
        sources: settings.sources || '',
        disabled_sources: selectedSources.length
          ? KNOWN_SOURCES.filter((source) => !selectedSources.includes(source))
          : [],
        links: Array.isArray(context.links) ? context.links : [],
        links_only: Boolean(context.linksOnly),
      }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.message || payload.error || `HTTP ${response.status}`);
    }
    return payload;
  } catch (error) {
    if (error && error.name === 'AbortError') {
      throw new Error(`核查超时（${Math.round(timeoutMs / 1000)} 秒）。请减少选中文本/链接数量，或只粘贴要核查的单个链接。`);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

async function runCheck(tabId, text, context = {}) {
  const links = Array.isArray(context.links) ? context.links : [];
  const selected = (text || '').trim()
    || links.map((link) => link.text || link.href).filter(Boolean).join('\n');
  if (!selected) {
    await sendToTab(tabId, {
      type: 'REFCHECKER_ERROR',
      message: '请先在当前网页中选中需要核查的参考文献、DOI、URL 或引用文本。',
    });
    return;
  }

  if (!context.linksOnly && selected.length < 20) {
    await sendToTab(tabId, {
      type: 'REFCHECKER_ERROR',
      message: '选中的内容太短，已不再自动识别 arXiv / PNAS 这类短标签或隐藏链接。核查链接请复制完整 URL/DOI 到插件面板粘贴；核查文献请选中完整参考文献。',
    });
    return;
  }

  const settings = await getSettings();
  await sendToTab(tabId, { type: 'REFCHECKER_LOADING', selectedText: selected });
  try {
    const result = await callRefChecker(selected, settings, context);
    await sendToTab(tabId, { type: 'REFCHECKER_RESULT', result });
  } catch (error) {
    await sendToTab(tabId, {
      type: 'REFCHECKER_ERROR',
      message: `${error.name || 'Error'}: ${error.message || error}`,
    });
  }
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'refchecker-check-selection',
    title: '用 RefChecker 核查选中文献',
    contexts: ['selection'],
    documentUrlPatterns: ['http://*/*', 'https://*/*'],
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === 'refchecker-check-selection' && tab && tab.id) {
    if (unsupportedPageMessage(tab.url)) return;
    getSelectionPayloadFromTab(tab.id)
      .then((payload) => runCheck(tab.id, payload.text || info.selectionText || ''))
      .catch(() => runCheck(tab.id, info.selectionText || ''));
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    if (message.type === 'GET_SETTINGS') {
      sendResponse({ ok: true, settings: await getSettings() });
      return;
    }
    if (message.type === 'SAVE_SETTINGS') {
      sendResponse({ ok: true, settings: await saveSettings(message.settings || {}) });
      return;
    }
    if (message.type === 'HEALTH_CHECK') {
      const settings = await getSettings();
      const response = await fetch(`${normalizeServerUrl(settings.serverUrl)}/health`);
      sendResponse({ ok: response.ok, payload: await response.json().catch(() => ({})) });
      return;
    }
    if (message.type === 'CHECK_ACTIVE_SELECTION') {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab || !tab.id) {
        sendResponse({ ok: false, error: 'No active tab.' });
        return;
      }
      const unsupported = unsupportedPageMessage(tab.url);
      if (unsupported) {
        sendResponse({ ok: false, error: unsupported });
        return;
      }
      const selection = await getSelectionPayloadFromTab(tab.id);
      await runCheck(tab.id, selection.text);
      sendResponse({ ok: true });
      return;
    }
    if (message.type === 'CHECK_PASTED_LINKS') {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab || !tab.id) {
        sendResponse({ ok: false, error: 'No active tab.' });
        return;
      }
      const unsupported = unsupportedPageMessage(tab.url);
      if (unsupported) {
        sendResponse({ ok: false, error: unsupported });
        return;
      }
      let fallbackLabel = String(message.context || '').trim();
      try {
        const selection = await getSelectionPayloadFromTab(tab.id);
        if (!fallbackLabel) fallbackLabel = selection.text || '';
      } catch (error) {
        // Keep manually pasted context if available.
      }
      const pastedText = String(message.text || '').trim();
      const links = extractPastedLinks(pastedText, fallbackLabel);
      if (!links.length) {
        sendResponse({ ok: false, error: '未识别到可核查的 URL 或 DOI。' });
        return;
      }
      await runCheck(tab.id, pastedText, { links, linksOnly: true });
      sendResponse({ ok: true });
      return;
    }
    if (message.type === 'CHECK_TEXT_FROM_CONTENT') {
      const tabId = sender.tab && sender.tab.id;
      if (!tabId) {
        sendResponse({ ok: false, error: 'No sender tab.' });
        return;
      }
      await runCheck(tabId, message.text || '');
      sendResponse({ ok: true });
      return;
    }
  })().catch((error) => {
    sendResponse({ ok: false, error: `${error.name || 'Error'}: ${error.message || error}` });
  });
  return true;
});
