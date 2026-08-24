(function defineObservatorySymbolSwitcher(global) {
  'use strict';

  function normalizeSymbol(value) {
    return String(value || '').trim().toUpperCase();
  }

  function requestedSymbol() {
    if (!global.location) return '';
    return normalizeSymbol(new URLSearchParams(global.location.search).get('symbol'));
  }

  function applyRequestedSymbolToConfig() {
    const config = global.OBSERVATORY_CONFIG;
    const requested = requestedSymbol();
    if (!config || config.mode !== 'backend' || !requested) return;

    global.OBSERVATORY_CONFIG = Object.freeze({
      ...config,
      market: Object.freeze({
        ...(config.market || {}),
        symbol: requested,
      }),
    });
  }

  // This script is intentionally loaded before runtime.js. The selected symbol
  // therefore becomes part of the runtime configuration before app.js creates
  // its chart state and market client.
  applyRequestedSymbolToConfig();

  async function loadStatus() {
    const config = global.OBSERVATORY_CONFIG || {};
    if (config.mode !== 'backend') {
      return {
        trading_universe: [],
        market_symbol: config.market?.symbol || '',
        market_source: 'public',
      };
    }

    try {
      const response = await fetch(`${config.apiBase || ''}/api/trading/status`, {
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
        market_symbol: config.market?.symbol || '',
        market_source: config.mode || 'unknown',
      };
    }
  }

  function navigateToSymbol(symbol) {
    const normalized = normalizeSymbol(symbol);
    const config = global.OBSERVATORY_CONFIG || {};
    if (!normalized || config.mode !== 'backend' || !global.location) return;

    const url = new URL(global.location.href);
    url.searchParams.set('symbol', normalized);
    global.location.assign(url.toString());
  }

  function appendSymbolButton(root, symbol, roleLabel, roleClass, selected) {
    const normalized = normalizeSymbol(symbol);
    if (!normalized) return;

    const button = document.createElement('button');
    button.type = 'button';
    button.className = `symbol-button ${roleClass}${normalized === selected ? ' active' : ''}`;
    button.dataset.symbol = normalized;
    button.setAttribute('aria-pressed', normalized === selected ? 'true' : 'false');

    const ticker = document.createElement('strong');
    ticker.textContent = normalized;
    const role = document.createElement('span');
    role.textContent = roleLabel;
    button.append(ticker, role);
    button.addEventListener('click', () => navigateToSymbol(normalized));
    root.appendChild(button);
  }

  function renderSymbolSwitcher(status) {
    const root = document.getElementById('symbol-switcher');
    if (!root) return;
    root.replaceChildren();

    const config = global.OBSERVATORY_CONFIG || {};
    const selected = normalizeSymbol(config.market?.symbol);
    const universe = [...new Set((status?.trading_universe || []).map(normalizeSymbol).filter(Boolean))].sort();
    const feedSymbol = normalizeSymbol(status?.market_symbol || selected);
    const marketSource = String(status?.market_source || (config.mode === 'static' ? 'public' : 'unknown')).toLowerCase();

    for (const symbol of universe) {
      appendSymbolButton(root, symbol, '美股自动交易', 'universe-symbol', selected);
    }

    const shouldShowFeedSymbol = config.mode === 'static'
      || (marketSource !== 'alpaca' && feedSymbol && !universe.includes(feedSymbol));
    if (shouldShowFeedSymbol) {
      const divider = document.createElement('span');
      divider.className = 'symbol-divider';
      divider.textContent = universe.length ? '行情源' : '当前行情';
      root.appendChild(divider);
      appendSymbolButton(
        root,
        feedSymbol,
        marketSource === 'replay' ? 'Replay Feed' : 'Market Feed',
        'feed-symbol',
        selected,
      );
    }

    if (!universe.length && !feedSymbol) {
      const empty = document.createElement('span');
      empty.className = 'symbol-empty';
      empty.textContent = '没有可切换标的';
      root.appendChild(empty);
    }

    const context = document.getElementById('market-context-label');
    if (context) {
      const universeText = universe.length ? `美股交易池 ${universe.join(' / ')}` : '未配置自动交易池';
      const feedText = marketSource === 'alpaca'
        ? 'Alpaca 多标的实时流'
        : `${marketSource.toUpperCase()} ${status?.market_symbol || feedSymbol || '—'}`;
      context.textContent = `${universeText} · ${feedText}`;
    }
  }

  global.addEventListener('DOMContentLoaded', async () => {
    renderSymbolSwitcher(await loadStatus());
  });

  global.ObservatorySymbolSwitcher = Object.freeze({
    renderSymbolSwitcher,
    navigateToSymbol,
  });
}(window));
