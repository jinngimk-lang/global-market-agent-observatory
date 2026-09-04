(function defineContextIntelligencePanel(global) {
  'use strict';

  const FRESHNESS_LABELS = Object.freeze({
    realtime: 'REALTIME · 实时',
    'near-realtime': 'NEAR-REALTIME · 近实时',
    'official-current': 'OFFICIAL-CURRENT · 官方当前',
    delayed: 'DELAYED · 延迟',
    stale: 'STALE · 已过期',
    unknown: 'UNKNOWN · 未知',
  });
  const KIND_LABELS = Object.freeze({
    fact: 'FACT · 事实',
    derived: 'DERIVED · 派生指标',
    inference: 'INFERENCE · 推断',
    hypothesis: 'HYPOTHESIS · 假设',
  });
  const CATEGORY_LABELS = Object.freeze({
    news: '实时新闻',
    filings: 'SEC / 公司披露',
    government: '政府 / 监管',
    flow: '资金行为',
  });

  function create() {
    const runtime = global.ObservatoryRuntime.resolve(global.OBSERVATORY_CONFIG);
    const backend = global.ObservatoryBackendActions?.create(runtime) || null;
    let currentSymbol = runtime.market.symbol;
    let refreshTimer = null;
    let requestGeneration = 0;

    const byId = (id) => document.getElementById(id);

    function text(value, fallback = '—') {
      if (value == null || value === '') return fallback;
      return String(value);
    }

    function formatSeconds(value) {
      const seconds = Number(value);
      if (!Number.isFinite(seconds)) return '—';
      if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
      if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 1 : 0)}s`;
      if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
      if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`;
      return `${(seconds / 86400).toFixed(1)}d`;
    }

    function formatTime(value) {
      if (!value) return '—';
      const parsed = new Date(value);
      if (Number.isNaN(parsed.getTime())) return text(value);
      return new Intl.DateTimeFormat('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      }).format(parsed);
    }

    function freshnessLabel(value) {
      return FRESHNESS_LABELS[value] || FRESHNESS_LABELS.unknown;
    }

    function kindLabel(value) {
      return KIND_LABELS[value] || text(value, 'UNKNOWN');
    }

    function freshnessClass(value) {
      if (value === 'realtime' || value === 'near-realtime') return 'safe';
      if (value === 'official-current') return 'official';
      if (value === 'delayed' || value === 'stale') return 'warning';
      return 'muted';
    }

    function sourceLabel(item) {
      const source = item?.source || {};
      const official = source.official ? '官方源' : '数据源';
      return `${official}：${text(source.provider, '未知')} · ${text(source.coverage, '覆盖未知')}`;
    }

    function newest(items) {
      if (!items?.length) return null;
      return [...items].sort((a, b) => {
        const right = Date.parse(b.source_updated_at || b.published_at || b.event_time || '') || 0;
        const left = Date.parse(a.source_updated_at || a.published_at || a.event_time || '') || 0;
        return right - left;
      })[0];
    }

    function categoryFreshness(items) {
      const item = newest(items);
      if (!item) return {state: 'unknown', age: null, latency: null};
      return {
        state: item.freshness || 'unknown',
        age: item.age_seconds,
        latency: item.provider_latency_seconds,
      };
    }

    function renderFreshness(snapshot) {
      const strip = byId('context-freshness-strip');
      if (!strip) return;
      strip.replaceChildren();
      for (const key of ['news', 'filings', 'government', 'flow']) {
        const result = categoryFreshness(snapshot[key] || []);
        const card = document.createElement('article');
        card.className = 'context-freshness-card';
        const label = document.createElement('span');
        label.textContent = CATEGORY_LABELS[key];
        const state = document.createElement('strong');
        state.className = freshnessClass(result.state);
        state.textContent = freshnessLabel(result.state);
        const detail = document.createElement('small');
        detail.textContent = result.age == null
          ? 'NO VERIFIED DATA'
          : `信息年龄 ${formatSeconds(result.age)} · 接收延迟 ${formatSeconds(result.latency)}`;
        card.append(label, state, detail);
        strip.appendChild(card);
      }
    }

    function renderItems(containerId, items, emptyText) {
      const container = byId(containerId);
      if (!container) return;
      container.replaceChildren();
      if (!items?.length) {
        const empty = document.createElement('p');
        empty.className = 'context-empty';
        empty.textContent = `NO VERIFIED DATA · ${emptyText}`;
        container.appendChild(empty);
        return;
      }

      const ordered = [...items].sort((a, b) => {
        const right = Date.parse(b.source_updated_at || b.published_at || b.event_time || '') || 0;
        const left = Date.parse(a.source_updated_at || a.published_at || a.event_time || '') || 0;
        return right - left;
      });

      for (const item of ordered.slice(0, 8)) {
        const article = document.createElement('article');
        article.className = 'context-item';

        const badges = document.createElement('div');
        badges.className = 'context-item-badges';
        const kind = document.createElement('span');
        kind.className = 'context-kind';
        kind.textContent = kindLabel(item.evidence_kind);
        const freshness = document.createElement('span');
        freshness.className = `context-freshness ${freshnessClass(item.freshness)}`;
        freshness.textContent = freshnessLabel(item.freshness);
        badges.append(kind, freshness);

        const headline = document.createElement('strong');
        headline.className = 'context-headline';
        headline.textContent = text(item.label || item.headline, '未命名事实');

        const summary = document.createElement('p');
        summary.className = 'context-summary';
        summary.textContent = text(item.summary, '来源未提供摘要；保留原始事实，不生成猜测。');

        const meta = document.createElement('div');
        meta.className = 'context-meta';
        const published = item.published_at || item.event_time;
        meta.textContent = `${sourceLabel(item)} · 发布 ${formatTime(published)} · 接收延迟 ${formatSeconds(item.provider_latency_seconds)} · 信息年龄 ${formatSeconds(item.age_seconds)}`;

        article.append(badges, headline, summary, meta);

        const url = item?.source?.source_url;
        if (url) {
          const link = document.createElement('a');
          link.className = 'context-source-link';
          link.href = url;
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
          link.textContent = '查看原始来源';
          article.appendChild(link);
        }
        container.appendChild(article);
      }
    }

    function renderStatus(status) {
      const node = byId('context-source-health');
      if (!node) return;
      const sources = status?.sources || {};
      const entries = Object.entries(sources);
      if (!entries.length) {
        node.textContent = '情报源状态：未配置';
        return;
      }
      node.textContent = entries.map(([name, health]) => {
        const state = health?.status || health?.state || 'unknown';
        return `${name} ${String(state).toUpperCase()}`;
      }).join(' · ');
    }

    function renderSnapshot(snapshot) {
      const symbol = byId('context-intelligence-symbol');
      if (symbol) symbol.textContent = snapshot.symbol || currentSymbol;
      const synthesis = byId('context-synthesis');
      if (synthesis) synthesis.textContent = snapshot.synthesis || 'NO VERIFIED DATA';
      const authority = byId('context-execution-authority');
      if (authority) {
        const raw = String(snapshot.execution_authority || 'none').toLowerCase();
        authority.textContent = raw === 'none'
          ? '仅作上下文证据，不代表交易许可'
          : `执行权限：${raw}`;
      }
      renderFreshness(snapshot);
      renderItems('context-news', snapshot.news || [], '暂无该标的已验证新闻');
      renderItems('context-filings', snapshot.filings || [], '暂无该标的已验证 SEC / 公司披露');
      renderItems('context-government', snapshot.government || [], '暂无该标的已验证政府 / 监管事件');
      renderItems('context-flow', snapshot.flow || [], '暂无该标的可验证资金行为结构');
    }

    function renderUnavailable(message) {
      const symbol = byId('context-intelligence-symbol');
      if (symbol) symbol.textContent = currentSymbol;
      const synthesis = byId('context-synthesis');
      if (synthesis) synthesis.textContent = `NO VERIFIED DATA · ${message}`;
      renderFreshness({news: [], filings: [], government: [], flow: []});
      renderItems('context-news', [], message);
      renderItems('context-filings', [], message);
      renderItems('context-government', [], message);
      renderItems('context-flow', [], message);
    }

    async function loadForSymbol(symbol = currentSymbol) {
      currentSymbol = String(symbol || runtime.market.symbol).trim().toUpperCase();
      const generation = ++requestGeneration;
      if (runtime.mode !== 'backend' || !backend) {
        renderUnavailable('静态预览未连接实时情报后端');
        return;
      }
      try {
        const [snapshot, status] = await Promise.all([
          backend.loadIntelligence(currentSymbol),
          backend.loadIntelligenceStatus(),
        ]);
        if (generation !== requestGeneration) return;
        renderSnapshot(snapshot);
        renderStatus(status);
      } catch (error) {
        if (generation !== requestGeneration) return;
        console.error('context intelligence refresh failed', error);
        renderUnavailable('情报服务暂不可用；保留 fail-closed，不展示猜测数据');
      }
    }

    async function setSymbol(symbol) {
      const normalized = String(symbol || '').trim().toUpperCase();
      if (!normalized || normalized === currentSymbol) return;
      await loadForSymbol(normalized);
    }

    function bindSymbolFollowing() {
      document.addEventListener('click', (event) => {
        const decisionCard = event.target.closest?.('.decision-card');
        if (decisionCard) {
          const symbol = decisionCard.querySelector('.symbol-name')?.textContent;
          if (symbol) queueMicrotask(() => setSymbol(symbol));
          return;
        }
        const symbolButton = event.target.closest?.('.symbol-button');
        if (symbolButton) {
          const symbol = symbolButton.querySelector('strong')?.textContent;
          if (symbol) queueMicrotask(() => setSymbol(symbol));
        }
      });
    }

    function start() {
      bindSymbolFollowing();
      loadForSymbol(currentSymbol);
      if (runtime.mode === 'backend') {
        refreshTimer = global.setInterval(() => loadForSymbol(currentSymbol), 5000);
      }
    }

    function stop() {
      if (refreshTimer !== null) global.clearInterval(refreshTimer);
      refreshTimer = null;
    }

    return Object.freeze({start, stop, loadForSymbol, setSymbol});
  }

  global.ObservatoryContextIntelligence = Object.freeze({create});
  global.addEventListener('DOMContentLoaded', () => {
    const controller = create();
    global.__observatoryContextIntelligence = controller;
    controller.start();
  });
}(window));
