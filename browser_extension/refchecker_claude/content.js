(function () {
  if (
    document.contentType === 'application/json'
    || document.contentType === 'text/json'
    || (location.hostname.endsWith('claude.ai') && location.pathname.startsWith('/api/'))
  ) {
    return;
  }

  if (window.__refcheckerWebContentLoaded) {
    return;
  }
  window.__refcheckerWebContentLoaded = true;

  const PANEL_ID = 'refchecker-claude-panel-host';
  const LEGACY_PANEL_ID = 'refchecker-claude-panel';
  const FLOAT_ID = 'refchecker-claude-float';
  const MAX_Z_INDEX = '2147483647';
  let lastSelectedText = '';
  let floatButtonEnabled = true;

  function applyFloatButtonSetting(value) {
    floatButtonEnabled = value !== false;
    if (!floatButtonEnabled) removeFloat();
  }

  if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.sync) {
    chrome.storage.sync.get({ enableFloatButton: true }, (settings) => {
      applyFloatButtonSetting(settings.enableFloatButton);
    });
    chrome.storage.onChanged.addListener((changes, areaName) => {
      if (areaName === 'sync' && changes.enableFloatButton) {
        applyFloatButtonSetting(changes.enableFloatButton.newValue);
      }
    });
  }

  const PANEL_CSS = `
    :host {
      all: initial;
      color-scheme: light;
      pointer-events: none;
    }
    .rc-panel,
    .rc-panel * {
      box-sizing: border-box;
    }
    .rc-panel {
      pointer-events: auto;
      width: 100%;
      max-height: calc(100vh - 32px);
      overflow: hidden;
      border: 1px solid #d5ded5;
      border-radius: 14px;
      background: #ffffff;
      color: #18211f;
      box-shadow: 0 18px 50px rgba(0, 0, 0, 0.22);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei UI", sans-serif;
      font-size: 13px;
      line-height: 1.45;
      text-align: left;
    }
    .rc-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      padding: 12px 14px;
      background: #eef6f2;
      border-bottom: 1px solid #d5ded5;
    }
    .rc-title {
      font-size: 16px;
      font-weight: 750;
    }
    .rc-subtitle,
    .rc-muted {
      color: #5a655e;
      font-size: 12px;
    }
    .rc-close {
      border: 0;
      background: transparent;
      color: #35413b;
      cursor: pointer;
      font-size: 24px;
      line-height: 1;
      padding: 0 4px;
    }
    .rc-body {
      overflow: auto;
      max-height: calc(100vh - 92px);
      padding: 14px;
    }
    h3 {
      margin: 16px 0 8px;
      font-size: 14px;
    }
    code,
    pre {
      font-family: "Cascadia Mono", Consolas, monospace;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    pre {
      margin: 8px 0;
      padding: 10px;
      border-radius: 8px;
      background: #f6f7f4;
    }
    .rc-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 8px;
    }
    .rc-grid div {
      padding: 8px;
      border: 1px solid #e2e7df;
      border-radius: 10px;
      background: #fbfcfa;
      text-align: center;
    }
    .rc-grid b {
      display: block;
      font-size: 18px;
    }
    .rc-grid span {
      color: #667166;
      font-size: 12px;
    }
    .rc-item {
      margin: 10px 0;
      padding: 10px;
      border: 1px solid #e2e7df;
      border-radius: 10px;
      background: #fffefa;
    }
    .rc-item-head {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 6px;
    }
    .rc-badge {
      display: inline-block;
      padding: 2px 7px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 700;
      background: #e8eee9;
    }
    .rc-high,
    .rc-not_found {
      background: #ffe2de;
      color: #9b2f24;
    }
    .rc-medium {
      background: #fff0c7;
      color: #7a5200;
    }
    .rc-low {
      background: #e9f6ff;
      color: #205c86;
    }
    .rc-none,
    .rc-found {
      background: #e9f7ef;
      color: #1e6b3f;
    }
    .rc-source {
      color: #5a655e;
    }
    .rc-loading {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 16px 0;
    }
    .rc-spinner {
      width: 18px;
      height: 18px;
      border: 3px solid #d8e5dd;
      border-top-color: #1f7a6d;
      border-radius: 50%;
      animation: rc-spin 1s linear infinite;
    }
    .rc-error {
      padding: 10px;
      border: 1px solid #ffc8c1;
      border-radius: 10px;
      background: #fff3f1;
    }
    .rc-copy {
      cursor: pointer;
      border: 1px solid #1f7a6d;
      border-radius: 8px;
      padding: 7px 10px;
      background: #1f7a6d;
      color: #fff;
    }
    .rc-paths {
      padding-left: 18px;
    }
    @keyframes rc-spin {
      to {
        transform: rotate(360deg);
      }
    }
  `;

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function setImportantStyle(element, styles) {
    for (const [name, value] of Object.entries(styles)) {
      element.style.setProperty(name, value, 'important');
    }
  }

  function stylePanelHost(host) {
    setImportantStyle(host, {
      all: 'initial',
      position: 'fixed',
      top: '16px',
      right: '16px',
      left: 'auto',
      bottom: 'auto',
      width: 'min(420px, calc(100vw - 32px))',
      'max-width': 'calc(100vw - 32px)',
      'max-height': 'calc(100vh - 32px)',
      'z-index': MAX_Z_INDEX,
      display: 'block',
      margin: '0',
      padding: '0',
      transform: 'none',
      overflow: 'visible',
      'pointer-events': 'none',
    });
  }

  function installShadowStyles(root) {
    if (root.adoptedStyleSheets && typeof CSSStyleSheet !== 'undefined') {
      const sheet = new CSSStyleSheet();
      sheet.replaceSync(PANEL_CSS);
      root.adoptedStyleSheets = [sheet];
      return;
    }
    const style = document.createElement('style');
    style.textContent = PANEL_CSS;
    root.appendChild(style);
  }

  function removePanel() {
    const old = document.getElementById(PANEL_ID);
    if (old) old.remove();
    const legacy = document.getElementById(LEGACY_PANEL_ID);
    if (legacy) legacy.remove();
  }

  function getPanel() {
    let host = document.getElementById(PANEL_ID);
    if (host && host.shadowRoot) {
      stylePanelHost(host);
      const existing = host.shadowRoot.querySelector('.rc-panel');
      if (existing) return existing;
    }

    if (host) host.remove();
    const legacy = document.getElementById(LEGACY_PANEL_ID);
    if (legacy) legacy.remove();
    host = document.createElement('div');
    host.id = PANEL_ID;
    stylePanelHost(host);

    const root = host.attachShadow({ mode: 'open' });
    installShadowStyles(root);

    const panel = document.createElement('aside');
    panel.className = 'rc-panel';
    panel.innerHTML = `
      <div class="rc-header">
        <div>
          <div class="rc-title">RefChecker</div>
          <div class="rc-subtitle">网页文献核查</div>
        </div>
        <button class="rc-close" title="关闭">×</button>
      </div>
      <div class="rc-body"></div>
    `;
    root.appendChild(panel);
    document.documentElement.appendChild(host);
    root.querySelector('.rc-close').addEventListener('click', removePanel);
    return panel;
  }

  function setBody(html) {
    const panel = getPanel();
    panel.querySelector('.rc-body').innerHTML = html;
  }

  function renderLoading() {
    setBody(`
      <div class="rc-loading">
        <div class="rc-spinner"></div>
        <div>正在调用本地 RefChecker 核查选中文献……</div>
      </div>
    `);
  }

  function renderError(message) {
    setBody(`
      <div class="rc-error">
        <strong>核查失败</strong>
        <p>${escapeHtml(message)}</p>
        <p class="rc-muted">请确认 RefChecker 桌面版已经打开，或手动启动：<code>python .\\refchecker_http_server.py</code></p>
      </div>
    `);
  }

  function itemBadge(item) {
    const risk = item.risk_level || item.status || 'unknown';
    return `<span class="rc-badge rc-${escapeHtml(risk)}">${escapeHtml(risk)}</span>`;
  }

  function renderItem(item, index) {
    const corrected = item.corrected_apa
      ? `<details class="rc-details" open>
          <summary>候选修正版 APA</summary>
          <pre>${escapeHtml(item.corrected_apa)}</pre>
        </details>`
      : '';
    const url = item.correct_url
      ? `<div><strong>正确 DOI/URL：</strong><code>${escapeHtml(item.correct_url)}</code></div>`
      : '';
    return `
      <div class="rc-item">
        <div class="rc-item-head">
          <span>#${index + 1}</span>
          ${itemBadge(item)}
          <span class="rc-source">${escapeHtml(item.source || '')}</span>
        </div>
        <div><strong>原标题：</strong>${escapeHtml(item.input_title || '(未识别标题)')}</div>
        ${item.matched_title ? `<div><strong>匹配标题：</strong>${escapeHtml(item.matched_title)}</div>` : ''}
        ${url}
        ${item.doi_reason ? `<div><strong>DOI：</strong>${escapeHtml(item.doi_reason)}</div>` : ''}
        ${item.suggested_action ? `<div><strong>建议：</strong>${escapeHtml(item.suggested_action)}</div>` : ''}
        ${item.evidence_basis ? `<div class="rc-muted"><strong>依据：</strong>${escapeHtml(item.evidence_basis)}</div>` : ''}
        ${corrected}
      </div>
    `;
  }

  function renderLinkCheck(item, index) {
    const expected = Array.isArray(item.expected_domains) && item.expected_domains.length
      ? `<div><strong>预期域名：</strong>${escapeHtml(item.expected_domains.join(' / '))}</div>`
      : '';
    const authors = Array.isArray(item.target_authors) && item.target_authors.length
      ? item.target_authors.slice(0, 6).join('; ')
      : '';
    const targetMeta = item.target_title
      ? `<div class="rc-target">
          <div><strong>目标论文标题：</strong>${escapeHtml(item.target_title)}</div>
          ${authors ? `<div><strong>目标作者：</strong>${escapeHtml(authors)}</div>` : ''}
          ${item.target_year ? `<div><strong>目标年份：</strong>${escapeHtml(item.target_year)}</div>` : ''}
          ${item.expected_title ? `<div><strong>网页显示标题：</strong>${escapeHtml(item.expected_title)}</div>` : ''}
          ${item.target_title_similarity ? `<div><strong>标题相似度：</strong>${escapeHtml(Math.round(Number(item.target_title_similarity) * 100))}%</div>` : ''}
        </div>`
      : (item.target_error ? `<div class="rc-muted"><strong>目标元数据：</strong>${escapeHtml(item.target_error)}</div>` : '');
    const redirect = item.redirect_target
      ? `<div><strong>跳转目标：</strong><code>${escapeHtml(item.redirect_target)}</code></div>`
      : '';
    const context = item.surrounding_text
      ? `<details class="rc-details">
          <summary>链接所在上下文</summary>
          <pre>${escapeHtml(item.surrounding_text)}</pre>
        </details>`
      : '';
    return `
      <div class="rc-item">
        <div class="rc-item-head">
          <span>链接 #${index + 1}</span>
          ${itemBadge(item)}
          <span class="rc-source">${escapeHtml(item.host || '')}</span>
        </div>
        <div><strong>页面显示：</strong>${escapeHtml(item.label || '(空标签)')}</div>
        <div><strong>真实链接：</strong><code>${escapeHtml(item.href || '')}</code></div>
        ${redirect}
        ${expected}
        ${targetMeta}
        <div><strong>判断：</strong>${escapeHtml(item.message || '')}</div>
        ${item.suggestion ? `<div class="rc-muted"><strong>建议：</strong>${escapeHtml(item.suggestion)}</div>` : ''}
        ${context}
      </div>
    `;
  }

  function renderResult(result) {
    const summary = result.summary || {};
    const items = result.priority_items && result.priority_items.length
      ? result.priority_items
      : (result.items || []);
    const paths = result.paths || {};
    const corrected = result.corrected_references || '';
    const linkChecks = Array.isArray(result.link_checks) ? result.link_checks : [];
    const panel = getPanel();
    panel.querySelector('.rc-body').innerHTML = `
      <section class="rc-summary">
        <div class="rc-grid">
          <div><b>${escapeHtml(summary.total ?? 0)}</b><span>总数</span></div>
          <div><b>${escapeHtml(summary.found ?? 0)}</b><span>找到</span></div>
          <div><b>${escapeHtml(summary.not_found ?? 0)}</b><span>未找到</span></div>
          <div><b>${escapeHtml(summary.needs_review ?? 0)}</b><span>需核查</span></div>
        </div>
        ${summary.report_summary ? `<p>${escapeHtml(summary.report_summary)}</p>` : ''}
        ${summary.link_checks ? `<p class="rc-muted">粘贴链接核查：${escapeHtml(summary.link_checks)} 个链接，${escapeHtml(summary.link_alerts || 0)} 个可疑。</p>` : ''}
      </section>
      ${linkChecks.length ? `<h3>粘贴链接核查</h3>${linkChecks.map(renderLinkCheck).join('')}` : ''}
      ${items.length
        ? `<h3>重点问题 / 校正建议</h3>${items.map(renderItem).join('')}`
        : (linkChecks.length ? '' : '<p>未发现明显文献或链接问题。</p>')}
      ${corrected ? `
        <h3>可复制的候选修正版</h3>
        <pre class="rc-corrected">${escapeHtml(corrected)}</pre>
        <button class="rc-copy" data-copy="corrected">复制候选修正版</button>
      ` : ''}
      <h3>输出文件</h3>
      <ul class="rc-paths">
        ${paths.output_dir ? `<li>目录：<code>${escapeHtml(paths.output_dir)}</code></li>` : ''}
        ${paths.markdown_path ? `<li>报告：<code>${escapeHtml(paths.markdown_path)}</code></li>` : ''}
        ${paths.csv_path ? `<li>CSV：<code>${escapeHtml(paths.csv_path)}</code></li>` : ''}
      </ul>
    `;
    const copyButton = panel.querySelector('.rc-copy[data-copy="corrected"]');
    if (copyButton) {
      copyButton.addEventListener('click', async () => {
        await navigator.clipboard.writeText(corrected);
        copyButton.textContent = '已复制';
        setTimeout(() => { copyButton.textContent = '复制候选修正版'; }, 1500);
      });
    }
  }

  function getSelectedText() {
    return window.getSelection ? window.getSelection().toString().trim() : '';
  }

  function removeFloat() {
    const old = document.getElementById(FLOAT_ID);
    if (old) old.remove();
  }

  function styleFloatButton(button, x, y) {
    setImportantStyle(button, {
      all: 'initial',
      position: 'fixed',
      left: `${Math.min(x, window.innerWidth - 160)}px`,
      top: `${Math.max(8, y - 44)}px`,
      'z-index': String(Number(MAX_Z_INDEX) - 1),
      border: '1px solid #1f7a6d',
      'border-radius': '999px',
      padding: '7px 10px',
      background: '#1f7a6d',
      color: '#fff',
      'box-shadow': '0 10px 25px rgba(0, 0, 0, 0.18)',
      cursor: 'pointer',
      font: '12px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      margin: '0',
      display: 'block',
    });
  }

  function showFloatButton(x, y) {
    removeFloat();
    if (!floatButtonEnabled) return;
    const text = getSelectedText();
    if (!text.trim()) return;
    lastSelectedText = text;
    const button = document.createElement('button');
    button.id = FLOAT_ID;
    button.textContent = 'RefChecker 核查';
    button.dataset.refcheckerText = text;
    const capturedText = text;
    styleFloatButton(button, x, y);
    button.addEventListener('mousedown', (event) => {
      event.preventDefault();
      event.stopPropagation();
    });
    button.addEventListener('mouseup', (event) => {
      event.preventDefault();
      event.stopPropagation();
    });
    button.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      const selected = button.dataset.refcheckerText || capturedText || lastSelectedText || getSelectedText();
      removeFloat();
      const requestText = selected.trim();
      if (!requestText) {
        renderError('选中文本已丢失，请重新选中完整参考文献后再点击核查。');
        return;
      }
      if (requestText.length < 20) {
        renderError('选中的内容太短，已不再自动识别 arXiv / PNAS 这类短标签或隐藏链接。核查链接请复制完整 URL/DOI 到插件面板粘贴；核查文献请选中完整参考文献。');
        return;
      }
      renderLoading();
      chrome.runtime.sendMessage(
        {
          type: 'CHECK_TEXT_FROM_CONTENT',
          text: requestText,
        },
        (response) => {
          const error = chrome.runtime.lastError;
          if (error) {
            renderError(error.message || String(error));
            return;
          }
          if (response && response.ok === false) {
            renderError(response.error || '核查请求发送失败。');
          }
        },
      );
    });
    document.documentElement.appendChild(button);
  }

  document.addEventListener('mouseup', (event) => {
    if (event.target.closest && event.target.closest(`#${FLOAT_ID}`)) return;
    setTimeout(() => showFloatButton(event.clientX, event.clientY), 20);
  });
  document.addEventListener('mousedown', (event) => {
    if (!event.target.closest || !event.target.closest(`#${FLOAT_ID}`)) removeFloat();
  });

  chrome.runtime.onMessage.addListener((message) => {
    if (message.type === 'REFCHECKER_LOADING') renderLoading();
    if (message.type === 'REFCHECKER_ERROR') renderError(message.message);
    if (message.type === 'REFCHECKER_RESULT') renderResult(message.result);
  });
})();
