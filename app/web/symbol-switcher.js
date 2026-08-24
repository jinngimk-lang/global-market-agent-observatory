(function defineObservatorySymbolSwitcher(global) {
  'use strict';

  function normalizeSymbol(value) {
    return String(value || '').trim().toUpperCase();
  }

  function currentStatus() {
    return typeof state !== 'undefined' ? state.tradingStatus : null;
  }

  function selectedSymbol() {
    return typeof state !== 'undefined' ? normalizeSymbol(state.symbol) : '';
  }

  function setActiveButton(symbol) {
    const normalized = normalizeSymbol(symbol);
    document.querySelectorAll('#symbol-switcher [data-symbol]').forEach((button) => {
      button.classList.toggle('active', button.dataset.symbol === normalized);
      button.setAttribute('aria-pressed', button.dataset.symbol === normalized ? 'true' : 'false');
    });
  }

  async function switchSymbol(symbol) {
    const normalized = normalizeSymbol(symbol);
    if (!normalized || typeof state === 'undefined' || typeof loadHistory !== 'function') return;
    if (runtime.mode === 'static' && normalized !== runtime.market.symbol) return;

    state.symbol = normalized;
    setActiveButton(normalized);
    setText('symbol-title', `${normalized} · ${state.interval}`);
    setText('last-price', '—');
    setText('feed-source', '正在读取该标的行情…');
    if (state.series) state.series.setData([]);

    if (global.history && global.location) {
      const url = new URL(global.location.href);
      url.searchParams.set('symbol', normalized);
      global.history.replaceState({}, '', url);
    }

    await loadHistory();
  }

  function appendSymbolButton(root, symbol, roleLabel, roleClass) {
    const normalized = normalizeSymbol(symbol);
    if (!normalized) return;

    const button = document.createElement('button');
    button.type = 'button';
    button.className = `symbol-button ${roleClass}`;
    button.dataset.symbol = normalized;
    button.setAttribute('aria-pressed', 'false');

    const ticker = document.createElement('strong');
    ticker.textContent = normalized;
    const role = document.createElement('span');
    role.textContent = roleLabel;
    button.append(ticker, role);
    button.addEventListener('click', () => switchSymbol(normalized));
    root.appendChild(button);
  }

  function renderSymbolSwitcher(status) {
    const root = document.getElementById('symbol-switcher');
    if (!root) return;
    root.replaceChildren();

    const universe = [...new Set((status?.trading_universe || []).map(normalizeSymbol).filter(Boolean))].sort();
    const feedSymbol = normalizeSymbol(status?.market_symbol || runtime.market.symbol);
    const marketSource = String(status?.market_source || (runtime.mode === 'static' ? 'public' : 'unknown')).toLowerCase();

    if (universe.length) {
      for (const symbol of universe) {
        appendSymbolButton(root, symbol, '美股自动交易', 'universe-symbol');
      }
    }

    const shouldShowFeedSymbol = runtime.mode === 'static'
      || (marketSource !== 'alpaca' && feedSymbol && !universe.includes(feedSymbol));
    if (shouldShowFeedSymbol) {
      const divider = document.createElement('span');
      divider.className = 'symbol-divider';
      divider.textContent = universe.length ? '行情源' : '当前行情';
      root.appendChild(divider);
      appendSymbolButton(root, feedSymbol, marketSource === 'replay' ? 'Replay Feed' : 'Market Feed', 'feed-symbol');
    }

    if (!universe.length && !feedSymbol) {
      const empty = document.createElement('span');
      empty.className = 'symbol-empty';
      empty.textContent = '没有可切换标的';
      root.appendChild(empty);
    }

    setActiveButton(selectedSymbol() || feedSymbol || universe[0]);
    const context = document.getElementById('market-context-label');
    if (context) {
      const universeText = universe.length ? `美股交易池 ${universe.join(' / ')}` : '未配置自动交易池';
      const feedText = marketSource === 'alpaca'
        ? 'Alpaca 多标的实时流'
        : `${marketSource.toUpperCase()} ${feedSymbol || '—'}`;
      context.textContent = `${universeText} · ${feedText}`;
    }
  }

  async function loadSwitcherStatus() {
    if (runtime.mode !== 'backend') {
      return {
        trading_universe: [],
        market_symbol: runtime.market.symbol,
        market_source: 'public',
      };
    }
    if (currentStatus()) return currentStatus();
    try {
      const response = await fetch(`${runtime.apiBase}/api/trading/status`, {
        method: 'GET',
        credentials: 'same-origin',
        cache: 'no-store',
      });
      if (!response.ok) throw new Error(`status failed: ${response.status}`);
      return response.json();
    } catch (error) {
      console.error('failed to load symbol switcher status', error);
      return {
        trading_universe: [],
        market_symbol: runtime.market.symbol,
        market_source: runtime.mode,
      };
    }
  }

  const requested = global.location
    ? normalizeSymbol(new URLSearchParams(global.location.search).get('symbol'))
    : '';
  if (requested && typeof state !== 'undefined' && runtime.mode === 'backend') {
    state.symbol = requested;
  }

  global.addEventListener('DOMContentLoaded', async () => {
    const status = await loadSwitcherStatus();
    renderSymbolSwitcher(status);
  });

  global.ObservatorySymbolSwitcher = Object.freeze({
    renderSymbolSwitcher,
    switchSymbol,
  });
}(window));
