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
    .rc-decision {
      display: grid;
      grid-template-columns: 1fr;
      gap: 6px;
      margin: 10px 0;
      padding: 10px;
      border: 1px solid #d5ded5;
      border-radius: 10px;
      background: #f7fbf8;
    }
    .rc-decision div {
      overflow-wrap: anywhere;
    }
    .rc-hero {
      margin: 0 0 12px;
      padding: 14px;
      border: 1px solid #d5ded5;
      border-left-width: 5px;
      border-radius: 14px;
      background: #f7fbf8;
    }
    .rc-hero h3 {
      margin: 8px 0 6px;
      font-size: 18px;
      line-height: 1.25;
    }
    .rc-hero p {
      margin: 0 0 10px;
      color: #33413a;
    }
    .rc-hero-label {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      font-weight: 800;
    }
    .rc-hero-high {
      border-left-color: #d92d20;
      background: #fff6f4;
    }
    .rc-hero-medium {
      border-left-color: #dc8a00;
      background: #fff9ed;
    }
    .rc-hero-low {
      border-left-color: #2878b8;
      background: #f2f8ff;
    }
    .rc-hero-none {
      border-left-color: #1f7a6d;
      background: #f4fbf7;
    }
    .rc-hero-high .rc-hero-label {
      color: #b42318;
    }
    .rc-hero-medium .rc-hero-label {
      color: #9a5b00;
    }
    .rc-hero-low .rc-hero-label {
      color: #205c86;
    }
    .rc-hero-none .rc-hero-label {
      color: #1e6b3f;
    }
    .rc-compact-summary {
      margin: 8px 0 12px;
    }
    .rc-card {
      margin: 10px 0;
      padding: 12px;
      border: 1px solid #e2e7df;
      border-left-width: 4px;
      border-radius: 12px;
      background: #fffefa;
    }
    .rc-card-high {
      border-left-color: #d92d20;
      background: #fffaf8;
    }
    .rc-card-medium {
      border-left-color: #dc8a00;
    }
    .rc-card-low {
      border-left-color: #2878b8;
    }
    .rc-card-none {
      border-left-color: #1f7a6d;
      background: #fbfffc;
    }
    .rc-card-top {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 10px;
      margin-bottom: 8px;
    }
    .rc-card-title {
      font-size: 15px;
      font-weight: 800;
      color: #17231f;
    }
    .rc-primary-issue {
      margin: 6px 0 10px;
      color: #33413a;
    }
    .rc-compare {
      display: grid;
      grid-template-columns: 1fr;
      gap: 8px;
      margin: 8px 0;
    }
    .rc-compare div,
    .rc-title-line,
    .rc-action-box {
      padding: 9px;
      border: 1px solid #e3e9e1;
      border-radius: 10px;
      background: #ffffff;
    }
    .rc-compare span,
    .rc-title-line span,
    .rc-detail-row > span {
      display: block;
      margin-bottom: 3px;
      color: #687269;
      font-size: 11px;
      font-weight: 700;
    }
    .rc-compare strong,
    .rc-title-line strong {
      display: block;
      overflow-wrap: anywhere;
      font-size: 13px;
    }
    .rc-action-box {
      margin-top: 8px;
      background: #f7fbf8;
    }
    .rc-action-box strong {
      display: block;
      margin-bottom: 4px;
    }
    .rc-meta-row,
    .rc-card-actions,
    .rc-trace {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 8px;
    }
    .rc-meta-row span,
    .rc-step,
    .rc-action {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 4px 8px;
      background: #ffffff;
      border: 1px solid #dbe4db;
      color: #35413b;
      font-size: 12px;
      text-decoration: none;
    }
    .rc-action {
      border-color: #1f7a6d;
      color: #1f7a6d;
      font-weight: 700;
    }
    .rc-step-good {
      background: #e9f7ef;
      border-color: #bfe3cb;
      color: #1e6b3f;
    }
    .rc-step-bad {
      background: #ffe8e3;
      border-color: #ffc8c1;
      color: #9b2f24;
    }
    .rc-step-muted {
      color: #687269;
    }
    .rc-details {
      margin-top: 10px;
      border-top: 1px solid #edf1ea;
      padding-top: 8px;
    }
    .rc-details summary {
      cursor: pointer;
      color: #1f7a6d;
      font-weight: 700;
    }
    .rc-detail-row {
      margin-top: 8px;
    }
    .rc-detail-row code {
      display: block;
      padding: 7px;
      border-radius: 8px;
      background: #f7f8f5;
    }
    .rc-evidence-list {
      display: grid;
      gap: 6px;
      margin: 4px 0 0;
      padding: 0;
      list-style: none;
    }
    .rc-evidence-list li {
      padding: 8px;
      border: 1px solid #e3e9e1;
      border-left: 3px solid #cfd8cf;
      border-radius: 8px;
      background: #f7f8f5;
      overflow-wrap: anywhere;
    }
    .rc-evidence-list .rc-evidence-good {
      border-left-color: #1f7a6d;
      background: #f4fbf7;
    }
    .rc-evidence-list .rc-evidence-warn {
      border-left-color: #dc8a00;
      background: #fff9ed;
    }
    .rc-evidence-list .rc-evidence-bad {
      border-left-color: #d92d20;
      background: #fff6f4;
    }
    .rc-evidence-key {
      display: block;
      margin-bottom: 3px;
      color: #52615a;
      font-size: 11px;
      font-weight: 800;
    }
    .rc-evidence-value {
      display: block;
      color: #25302b;
    }
    .rc-web-evidence {
      margin-top: 8px;
      padding: 10px;
      border: 1px solid #f0d8a8;
      border-radius: 10px;
      background: #fffaf0;
      color: #3f3826;
    }
    .rc-web-evidence p {
      margin: 6px 0 8px;
      color: #6b5b2a;
    }
    .rc-web-evidence-list {
      margin: 0;
      padding-left: 18px;
      display: grid;
      gap: 8px;
    }
    .rc-web-evidence-list a {
      color: #1f5fbf;
      font-weight: 800;
      text-decoration: none;
    }
    .rc-web-evidence-list a:hover {
      text-decoration: underline;
    }
    .rc-web-evidence-title {
      display: flex;
      align-items: flex-start;
      gap: 6px;
    }
    .rc-web-evidence-sim {
      flex: 0 0 auto;
      padding: 1px 6px;
      border-radius: 999px;
      background: #fff0cc;
      color: #8a5a00;
      font-size: 11px;
      font-weight: 800;
    }
    .rc-web-evidence-snippet {
      margin-top: 3px;
      color: #52615a;
      font-size: 12px;
      line-height: 1.35;
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

  function riskClass(value) {
    const key = String(value || '').toLowerCase();
    if (['high', 'not_found', 'warning', 'error'].includes(key)) return 'high';
    if (['medium', 'needs_review'].includes(key)) return 'medium';
    if (['low'].includes(key)) return 'low';
    if (['none', 'found', 'ok', 'matched'].includes(key)) return 'none';
    return 'none';
  }

  function riskLabel(value) {
    const key = String(value || '').toLowerCase();
    return {
      high: '高风险',
      medium: '需确认',
      low: '低风险',
      none: '正常',
      found: '正常',
      ok: '正常',
      not_found: '未找到',
      warning: '需确认',
      skipped: '已跳过',
    }[key] || (value || '正常');
  }

  function severityMeta(level) {
    const key = riskClass(level);
    return {
      high: { icon: '●', title: '高风险', tone: 'high' },
      medium: { icon: '●', title: '需确认', tone: 'medium' },
      low: { icon: '●', title: '低风险', tone: 'low' },
      none: { icon: '●', title: '正常', tone: 'none' },
    }[key];
  }

  function itemBadge(item) {
    const risk = item.risk_level || item.status || 'none';
    const klass = riskClass(risk);
    return `<span class="rc-badge rc-${escapeHtml(klass)}">${escapeHtml(riskLabel(risk))}</span>`;
  }

  function doiStatusLabel(status) {
    return {
      matched: '通过',
      mismatch: '不匹配',
      unresolved: '无法解析',
      no_metadata: '无元数据',
      not_provided: '未提供',
    }[status || 'not_provided'] || (status || '未提供');
  }

  function modeLabel(mode) {
    return mode === 'parallel' ? '快速并发' : '严格顺序';
  }

  function parserLabel(item) {
    const parser = {
      llm: '大模型辅助解析',
      rules: '本地规则解析',
      bibtex: 'BibTeX 结构化字段',
    }[item.parser || 'rules'] || item.parser || '本地规则解析';
    const mode = {
      auto: 'LLM 优先',
      always: '总是 LLM',
      off: '规则解析',
    }[item.llm_parse_mode || 'off'] || item.llm_parse_mode || '规则解析';
    const confidence = item.parser_confidence ? `，置信度 ${item.parser_confidence}` : '';
    const note = item.parser_note ? `；${item.parser_note}` : '';
    return `${parser}（${mode}${confidence}）${note}`;
  }

  function shortText(value, max = 180) {
    const text = String(value || '').replace(/\s+/g, ' ').trim();
    return text.length > max ? `${text.slice(0, max - 1)}…` : text;
  }

  function firstUsefulItem(items) {
    return items.find((item) => item.risk_level === 'high')
      || items.find((item) => item.risk_level === 'medium' || item.status === 'not_found' || item.link_issue)
      || items[0]
      || {};
  }

  function firstProblemLink(linkChecks) {
    return linkChecks.find((item) => item.status !== 'ok') || null;
  }

  function overallSeverity(summary, allItems, linkChecks) {
    if ((summary.high_risk || 0) > 0
      || (summary.not_found || 0) > 0
      || allItems.some((item) => item.risk_level === 'high' || item.status === 'not_found')
      || linkChecks.some((item) => item.risk_level === 'high')) return 'high';
    if ((summary.medium_risk || 0) > 0
      || (summary.needs_review || 0) > 0
      || allItems.some((item) => item.risk_level === 'medium')
      || linkChecks.some((item) => item.status !== 'ok' || item.risk_level === 'medium')) return 'medium';
    if ((summary.low_risk || 0) > 0 || allItems.some((item) => item.risk_level === 'low')) return 'low';
    return 'none';
  }

  function referenceIssueLabel(item) {
    if (!item || !Object.keys(item).length) return '未发现明显问题';
    if (isWebEvidenceItem(item) && item.status === 'found') return '网页搜索证据，需人工核对';
    if (item.link_issue === 'input_doi_mismatch' || item.doi_check_status === 'mismatch') return 'DOI 指向另一篇论文';
    if (item.status === 'not_found') return '未找到可靠匹配';
    if (item.doi_check === 'mismatch') return 'DOI 与候选结果不一致';
    if (item.author_check === 'mismatch') return '作者不一致';
    if (item.year_check === 'mismatch') return '年份不一致';
    if (Number(item.similarity || 1) > 0 && Number(item.similarity || 1) < 0.90) return '标题匹配偏低';
    if (item.risk_level === 'medium') return '需要人工确认';
    if (item.doi_check_status === 'unresolved' || item.doi_check_status === 'no_metadata') return 'DOI 暂时无法确认';
    return '未发现明显冲突';
  }

  function referenceIssueMessage(item) {
    if (!item || !Object.keys(item).length) return '当前结果未发现明显标题、DOI、作者或年份冲突。';
    if (isWebEvidenceItem(item) && item.status === 'found') {
      const title = item.matched_title ? `最接近网页标题为「${shortText(item.matched_title, 120)}」。` : '';
      return `${item.source || '网页搜索源'} 只返回网页候选，不返回结构化作者、年份、DOI 等文献元数据。${title}请打开链接人工核对。`;
    }
    if (item.doi_check_status === 'mismatch' && item.doi_target_title) {
      return `输入 DOI 实际指向「${shortText(item.doi_target_title, 120)}」，与页面/输入标题不一致。`;
    }
    if (item.status === 'not_found') return item.matched_title
      ? `未找到高可信结果，最接近候选是「${shortText(item.matched_title, 120)}」。`
      : '没有数据源返回达到阈值的可靠匹配。';
    if (item.doi_check === 'mismatch') return item.doi_reason || '输入 DOI 与数据源候选 DOI 不一致。';
    if (item.author_check === 'mismatch') return item.author_reason || '作者列表与数据源不一致。';
    if (item.year_check === 'mismatch') return item.year_reason || '年份与数据源不一致。';
    if (item.matched_title && item.matched_title !== item.input_title) {
      return `当前采用来源匹配到「${shortText(item.matched_title, 120)}」。`;
    }
    return item.suggested_action && item.suggested_action !== '无需处理。'
      ? item.suggested_action
      : 'DOI、标题、作者和年份未发现明显冲突。';
  }

  function linkIssueLabel(item) {
    return {
      target_title_mismatch: '链接指向另一篇论文',
      label_domain_mismatch: '显示标签与真实域名不一致',
      visible_url_mismatch: '可见 URL 与真实链接不一致',
      redirect_wrapper: '链接存在跳转包装',
      unsafe_scheme: '链接协议不安全',
      missing_href: '无法读取真实链接',
    }[item.issue || ''] || (item.status === 'ok' ? '链接未发现明显问题' : '链接需要确认');
  }

  function heroTitle(summary, allItems, linkChecks) {
    const problemLink = firstProblemLink(linkChecks);
    if (problemLink) return linkIssueLabel(problemLink);
    return referenceIssueLabel(firstUsefulItem(allItems));
  }

  function heroMessage(summary, allItems, linkChecks) {
    const problemLink = firstProblemLink(linkChecks);
    if (problemLink) return shortText(problemLink.message || '链接目标需要人工确认。', 220);
    return shortText(referenceIssueMessage(firstUsefulItem(allItems)), 220);
  }

  function heroAction(summary, allItems, linkChecks) {
    const problemLink = firstProblemLink(linkChecks);
    if (problemLink) return shortText(problemLink.suggestion || '建议打开真实链接并人工核对标题、作者和年份。', 220);
    const item = firstUsefulItem(allItems);
    if (isWebEvidenceItem(item)) {
      return '点击网页证据链接，优先核对出版社/DOI/论文原文页面中的标题、作者、年份和 DOI；不要把网页搜索命中直接视为验证通过。';
    }
    return shortText(item.suggested_action || item.fix_suggestion || '无需处理，必要时打开 DOI/出版社页面抽查。', 220);
  }

  function safeHttpUrl(value) {
    const text = String(value || '').trim();
    return /^https?:\/\//i.test(text) ? text : '';
  }

  function isWebEvidenceItem(item) {
    const source = String((item && (item.adopted_source || item.source)) || '').toLowerCase();
    const flag = String((item && item.web_evidence) || '').toLowerCase();
    const kind = String((item && item.evidence_kind) || '').toLowerCase();
    return flag === 'yes'
      || flag === 'true'
      || kind === 'web'
      || source.includes('web evidence')
      || source.startsWith('brave ');
  }

  function webEvidenceRows(item) {
    const raw = item && item.web_evidence_results;
    if (Array.isArray(raw)) {
      return raw.filter((row) => row && typeof row === 'object');
    }
    if (typeof raw === 'string' && raw.trim()) {
      try {
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed)
          ? parsed.filter((row) => row && typeof row === 'object')
          : [];
      } catch (error) {
        return [];
      }
    }
    return [];
  }

  function webEvidenceLinksFromText(value) {
    const text = String(value || '');
    const links = [];
    const seen = new Set();
    const urlRe = /https?:\/\/[^\s<>"\]）)}；;，,。]+/gi;
    let match;
    while ((match = urlRe.exec(text)) !== null) {
      const href = safeHttpUrl(match[0]);
      if (!href || seen.has(href)) continue;
      seen.add(href);
      links.push({ title: href, url: href, source: '', snippet: '' });
    }
    return links;
  }

  function webEvidenceActionLinks(item) {
    const rows = webEvidenceRows(item);
    const fallback = rows.length ? [] : webEvidenceLinksFromText(item && item.web_evidence_links);
    return [...rows, ...fallback]
      .map((row, index) => ({
        label: `打开网页证据 ${index + 1}`,
        href: row.url,
      }))
      .filter((link) => safeHttpUrl(link.href));
  }

  function renderWebEvidence(item) {
    if (!isWebEvidenceItem(item)) return '';
    const rows = webEvidenceRows(item);
    const fallback = rows.length ? [] : webEvidenceLinksFromText(item.web_evidence_links);
    const evidenceRows = [...rows, ...fallback].slice(0, 5);
    const note = item.web_evidence_note
      || '网页搜索源只返回候选页面，不返回结构化作者、年份、DOI 等文献元数据；请点击页面人工核对。';
    const list = evidenceRows.length
      ? `<ol class="rc-web-evidence-list">
          ${evidenceRows.map((row, index) => {
            const href = safeHttpUrl(row.url);
            const label = row.title || row.source || href || `网页证据 ${index + 1}`;
            const simValue = Number(row.similarity);
            const sim = Number.isFinite(simValue)
              ? `<span class="rc-web-evidence-sim">${Math.round(simValue * 100)}%</span>`
              : '';
            return `<li>
              <div class="rc-web-evidence-title">
                ${href
                  ? `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(shortText(label, 120))}</a>`
                  : `<strong>${escapeHtml(shortText(label, 120))}</strong>`}
                ${sim}
              </div>
              ${row.source ? `<div class="rc-muted">${escapeHtml(row.source)}</div>` : ''}
              ${row.snippet ? `<div class="rc-web-evidence-snippet">${escapeHtml(shortText(row.snippet, 180))}</div>` : ''}
            </li>`;
          }).join('')}
        </ol>`
      : '<p class="rc-muted">未返回可解析的网页候选链接。</p>';
    return `
      <div class="rc-web-evidence">
        <strong>网页搜索证据（仅辅助）</strong>
        <p>${escapeHtml(note)}</p>
        ${list}
      </div>
    `;
  }

  function detailRows(rows) {
    const html = rows
      .filter((row) => String(row.value || '').trim() || String(row.html || '').trim())
      .map((row) => `
        <div class="rc-detail-row">
          <span>${escapeHtml(row.label)}</span>
          ${row.html || `<code>${escapeHtml(row.value)}</code>`}
        </div>
      `)
      .join('');
    return html || '<p class="rc-muted">暂无更多证据详情。</p>';
  }

  function splitEvidenceBasis(value) {
    const text = String(value || '').replace(/\s+/g, ' ').trim();
    if (!text) return [];
    const primary = text.split(/；+/).map((part) => part.trim()).filter(Boolean);
    if (primary.length > 1) return primary;
    return text
      .split(/;\s+(?=(?:[A-Za-z][A-Za-z ]{1,24}|[\u4e00-\u9fffA-Za-z /]{2,24})[：:])|;\s+(?=(?:OpenAlex|CrossRef|Semantic Scholar|PubMed|arXiv|DBLP)\b)/)
      .map((part) => part.trim())
      .filter(Boolean);
  }

  function evidenceTone(part) {
    const text = String(part || '').toLowerCase();
    if (/不一致|不匹配|未返回|未找到|缺少|无法|失败|mismatch|not found|failed/.test(text)) {
      return 'bad';
    }
    if (/偏低|抽查|需|候选|仲裁|相似度|warning/.test(text)) {
      return 'warn';
    }
    if (/一致|通过|匹配标题|返回 doi|返回年份|返回作者|输入记录|找到|exact|matched|found/.test(text)) {
      return 'good';
    }
    return 'neutral';
  }

  function renderEvidenceBasis(value) {
    const parts = splitEvidenceBasis(value);
    if (!parts.length) return '';
    return `
      <ul class="rc-evidence-list">
        ${parts.map((part) => {
          const match = part.match(/^(.{2,36}?)[：:]\s*(.*)$/);
          const tone = evidenceTone(part);
          if (match && match[2]) {
            return `
              <li class="rc-evidence-${tone}">
                <span class="rc-evidence-key">${escapeHtml(match[1])}</span>
                <span class="rc-evidence-value">${escapeHtml(match[2])}</span>
              </li>
            `;
          }
          return `<li class="rc-evidence-${tone}">${escapeHtml(part)}</li>`;
        }).join('')}
      </ul>
    `;
  }

  function traceLabel(part) {
    return String(part || '')
      .replace(/DOI exact check/gi, 'DOI 核验')
      .replace(/matched/gi, '通过')
      .replace(/mismatch/gi, '不匹配')
      .replace(/unresolved/gi, '无法解析')
      .replace(/no_candidate/gi, '无候选')
      .replace(/found/gi, '找到')
      .replace(/candidate/gi, '候选')
      .replace(/error/gi, '错误');
  }

  function traceClass(part) {
    const lower = String(part || '').toLowerCase();
    if (/mismatch|error|unresolved|failed/.test(lower)) return 'bad';
    if (/matched|found|passed/.test(lower)) return 'good';
    if (/no_candidate|skipped/.test(lower)) return 'muted';
    return 'neutral';
  }

  function renderTrace(trace) {
    const parts = String(trace || '')
      .split(/[;；]/)
      .map((part) => part.trim())
      .filter(Boolean);
    if (!parts.length) return '';
    return `
      <div class="rc-trace" aria-label="实际查询路径">
        ${parts.map((part) => `<span class="rc-step rc-step-${traceClass(part)}">${escapeHtml(traceLabel(part))}</span>`).join('')}
      </div>
    `;
  }

  function renderHero(summary, allItems, linkChecks) {
    const severity = overallSeverity(summary, allItems, linkChecks);
    const meta = severityMeta(severity);
    const firstItem = firstUsefulItem(allItems);
    const mode = summary.search_mode || firstItem.search_mode || 'strict';
    const chain = summary.source_order || firstItem.source_order || '';
    const adopted = firstItem.adopted_source || firstItem.source || '';
    const doi = summary.doi_check_status || firstItem.doi_check_status || 'not_provided';
    const trace = summary.actual_query_trace || firstItem.actual_query_trace || '';
    const parserSummary = summary.parser_summary || firstItem.parser || '';
    const llmMode = summary.llm_parse_mode || firstItem.llm_parse_mode || 'off';
    return `
      <section class="rc-hero rc-hero-${meta.tone}">
        <div class="rc-hero-label"><span>${meta.icon}</span><strong>${meta.title}</strong></div>
        <h3>${escapeHtml(heroTitle(summary, allItems, linkChecks))}</h3>
        <p>${escapeHtml(heroMessage(summary, allItems, linkChecks))}</p>
        <div class="rc-action-box">
          <strong>建议动作</strong>
          <div>${escapeHtml(heroAction(summary, allItems, linkChecks))}</div>
        </div>
        <div class="rc-meta-row">
          <span>DOI：${escapeHtml(doiStatusLabel(doi))}</span>
          <span>模式：${escapeHtml(modeLabel(mode))}${mode === 'parallel' ? '（并发仲裁）' : ''}</span>
          <span>解析：${escapeHtml(llmMode === 'off' ? '规则解析' : (llmMode === 'auto' ? 'LLM 优先' : '总是 LLM'))}${parserSummary ? ` · ${escapeHtml(parserSummary)}` : ''}</span>
          ${adopted ? `<span>采用：${escapeHtml(adopted)}</span>` : ''}
        </div>
        ${chain ? `<div class="rc-muted"><strong>搜索链：</strong>${escapeHtml(chain)}</div>` : ''}
        ${renderTrace(trace)}
      </section>
    `;
  }

  function renderActionLinks(links) {
    const deduped = [];
    const seen = new Set();
    for (const link of links) {
      const href = safeHttpUrl(link.href);
      if (!href || seen.has(href)) continue;
      seen.add(href);
      deduped.push({ ...link, href });
    }
    if (!deduped.length) return '';
    return `
      <div class="rc-card-actions">
        ${deduped.map((link) => `<a class="rc-action" href="${escapeHtml(link.href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(link.label)}</a>`).join('')}
      </div>
    `;
  }

  function renderItem(item, index) {
    const webEvidence = isWebEvidenceItem(item);
    const issue = referenceIssueLabel(item);
    const message = referenceIssueMessage(item);
    const action = webEvidence
      ? '请点击网页证据链接人工核对；Brave/网页搜索命中不能单独证明文献真实或元数据正确。'
      : (item.suggested_action || item.fix_suggestion || '无需处理，必要时人工抽查 DOI/出版社页面。');
    const compareTitle = webEvidence
      ? '网页候选标题'
      : (item.doi_check_status === 'mismatch' ? 'DOI 实际指向' : '匹配结果');
    const compareValue = item.doi_check_status === 'mismatch'
      ? (item.doi_target_title || item.matched_title)
      : item.matched_title;
    const compare = compareValue ? `
      <div class="rc-compare">
        <div><span>输入标题</span><strong>${escapeHtml(shortText(item.input_title || '(未识别标题)', 160))}</strong></div>
        <div><span>${escapeHtml(compareTitle)}</span><strong>${escapeHtml(shortText(compareValue, 160))}</strong></div>
      </div>
    ` : `<div class="rc-title-line"><span>输入标题</span><strong>${escapeHtml(shortText(item.input_title || '(未识别标题)', 180))}</strong></div>`;
    const corrected = item.corrected_apa
      ? `<details class="rc-details">
          <summary>候选修正版 APA</summary>
          <pre>${escapeHtml(item.corrected_apa)}</pre>
        </details>`
      : '';
    return `
      <article class="rc-card rc-card-${escapeHtml(riskClass(item.risk_level || item.status))}">
        <div class="rc-card-top">
          <div>
            <div class="rc-card-title">${escapeHtml(issue)}</div>
            <div class="rc-muted">#${index + 1} ${item.key ? `· ${escapeHtml(item.key)}` : ''} ${item.source ? `· ${escapeHtml(item.source)}` : ''}</div>
          </div>
          ${itemBadge(item)}
        </div>
        <p class="rc-primary-issue">${escapeHtml(message)}</p>
        ${compare}
        <div class="rc-action-box">
          <strong>建议动作</strong>
          <div>${escapeHtml(shortText(action, 240))}</div>
        </div>
        ${renderActionLinks([
          { label: '打开 DOI', href: item.doi_resolved_url },
          { label: '打开匹配网页', href: item.matched_url },
          { label: '打开候选 DOI/URL', href: item.correct_url },
          ...webEvidenceActionLinks(item),
        ])}
        ${corrected}
        <details class="rc-details">
          <summary>查看证据详情</summary>
          ${detailRows([
            { label: 'DOI 精确核验', value: `${doiStatusLabel(item.doi_check_status)} ${item.doi_check_message || ''}`.trim() },
            { label: '解析方式', value: parserLabel(item) },
            { label: '解析提示', value: item.parser_warning },
            { label: 'DOI 指向标题', value: item.doi_target_title },
            { label: 'DOI 解析地址', value: item.doi_resolved_url },
            { label: '最终采用', value: item.adopted_source || item.source },
            { label: '搜索链', value: item.source_order },
            { label: '实际查询路径', value: item.actual_query_trace },
            { label: '作者核验', value: item.author_reason },
            { label: '年份核验', value: item.year_reason },
            { label: 'DOI 对比', value: item.doi_reason },
            { label: '网页证据', html: renderWebEvidence(item) },
            { label: '依据', html: renderEvidenceBasis(item.evidence_basis) },
          ])}
        </details>
      </article>
    `;
  }

  function renderLinkCheck(item, index) {
    const authors = Array.isArray(item.target_authors) && item.target_authors.length
      ? item.target_authors.slice(0, 6).join('; ')
      : '';
    const compare = item.target_title ? `
      <div class="rc-compare">
        <div><span>页面显示</span><strong>${escapeHtml(shortText(item.expected_title || item.label || '(空标签)', 160))}</strong></div>
        <div><span>真实目标</span><strong>${escapeHtml(shortText(item.target_title, 160))}</strong></div>
      </div>
    ` : `<div class="rc-title-line"><span>页面显示</span><strong>${escapeHtml(shortText(item.label || '(空标签)', 180))}</strong></div>`;
    return `
      <article class="rc-card rc-card-${escapeHtml(riskClass(item.risk_level || item.status))}">
        <div class="rc-card-top">
          <div>
            <div class="rc-card-title">${escapeHtml(linkIssueLabel(item))}</div>
            <div class="rc-muted">链接 #${index + 1} ${item.host ? `· ${escapeHtml(item.host)}` : ''}</div>
          </div>
          ${itemBadge(item)}
        </div>
        <p class="rc-primary-issue">${escapeHtml(shortText(item.message || '', 220))}</p>
        ${compare}
        <div class="rc-action-box">
          <strong>建议动作</strong>
          <div>${escapeHtml(shortText(item.suggestion || '建议打开真实链接人工核对标题、作者和年份。', 240))}</div>
        </div>
        ${renderActionLinks([
          { label: '打开真实链接', href: item.href },
          { label: '打开跳转目标', href: item.redirect_target },
        ])}
        <details class="rc-details">
          <summary>查看链接证据</summary>
          ${detailRows([
            { label: '真实链接', value: item.href },
            { label: '跳转目标', value: item.redirect_target },
            { label: '预期域名', value: Array.isArray(item.expected_domains) ? item.expected_domains.join(' / ') : '' },
            { label: '目标作者', value: authors },
            { label: '目标年份', value: item.target_year },
            { label: '目标来源', value: item.target_source },
            { label: '标题相似度', value: item.target_title_similarity ? `${Math.round(Number(item.target_title_similarity) * 100)}%` : '' },
            { label: '目标元数据错误', value: item.target_error },
            { label: '链接上下文', value: item.surrounding_text },
          ])}
        </details>
      </article>
    `;
  }

  function renderResult(result) {
    const summary = result.summary || {};
    const allItems = result.items || [];
    const priorityItems = result.priority_items && result.priority_items.length
      ? result.priority_items
      : allItems;
    const paths = result.paths || {};
    const corrected = result.corrected_references || '';
    const linkChecks = Array.isArray(result.link_checks) ? result.link_checks : [];
    const linkProblems = linkChecks.filter((item) => item.status !== 'ok');
    const panel = getPanel();
    panel.querySelector('.rc-body').innerHTML = `
      ${renderHero(summary, allItems, linkChecks)}
      <section class="rc-summary rc-compact-summary">
        <div class="rc-grid">
          <div><b>${escapeHtml(summary.total ?? 0)}</b><span>文献</span></div>
          <div><b>${escapeHtml(summary.found ?? 0)}</b><span>找到</span></div>
          <div><b>${escapeHtml(summary.not_found ?? 0)}</b><span>未找到</span></div>
          <div><b>${escapeHtml(summary.link_alerts || 0)}</b><span>可疑链接</span></div>
        </div>
      </section>
      ${linkProblems.length
        ? `<h3>需要优先处理的链接</h3>${linkProblems.map(renderLinkCheck).join('')}`
        : (linkChecks.length ? `<p class="rc-muted">已检查 ${escapeHtml(linkChecks.length)} 个链接，未发现明显链接跳转问题。</p>` : '')}
      ${priorityItems.length
        ? `<h3>文献核查结果</h3>${priorityItems.map(renderItem).join('')}`
        : (linkProblems.length ? '' : '<p>未发现明显文献或链接问题。</p>')}
      ${corrected ? `
        <details class="rc-details rc-corrected-wrap">
          <summary>可复制的候选修正版</summary>
          <pre class="rc-corrected">${escapeHtml(corrected)}</pre>
          <button class="rc-copy" data-copy="corrected">复制候选修正版</button>
        </details>
      ` : ''}
      <details class="rc-details rc-output-details">
        <summary>输出文件</summary>
        <ul class="rc-paths">
          ${paths.output_dir ? `<li>目录：<code>${escapeHtml(paths.output_dir)}</code></li>` : ''}
          ${paths.markdown_path ? `<li>报告：<code>${escapeHtml(paths.markdown_path)}</code></li>` : ''}
          ${paths.csv_path ? `<li>CSV：<code>${escapeHtml(paths.csv_path)}</code></li>` : ''}
        </ul>
      </details>
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
