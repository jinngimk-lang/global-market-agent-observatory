(function defineObservatoryRuntime(global) {
  'use strict';

  const MODES = new Set(['backend', 'static']);

  function normalizeBase(value) {
    const text = String(value || '').trim();
    return text === '/' ? '' : text.replace(/\/$/, '');
  }

  function resolve(input) {
    const config = input && typeof input === 'object' ? input : {};
    const requestedMode = String(config.mode || 'backend').toLowerCase();
    const mode = MODES.has(requestedMode) ? requestedMode : 'backend';
    const marketConfig = config.market && typeof config.market === 'object' ? config.market : {};
    const capabilities = mode === 'backend'
      ? {paperOrders: true, researchRefresh: true, accountRefresh: true}
      : {paperOrders: false, researchRefresh: false, accountRefresh: false};

    return Object.freeze({
      mode,
      apiBase: normalizeBase(config.apiBase),
      market: Object.freeze({
        symbol: String(marketConfig.symbol || 'BTCUSDT').toUpperCase(),
        interval: String(marketConfig.interval || '1m'),
      }),
      capabilities: Object.freeze(capabilities),
      observeOnly: mode === 'static',
    });
  }

  global.ObservatoryRuntime = Object.freeze({resolve});
}(window));
