(function defineObservatoryBackendActions(global) {
  'use strict';

  function create(runtime) {
    const apiUrl = (path) => `${runtime.apiBase}${path}`;

    async function get(path, label) {
      const response = await fetch(apiUrl(path), {
        method: 'GET',
        credentials: 'same-origin',
        cache: 'no-store',
      });
      if (!response.ok) throw new Error(`${label} failed: ${response.status}`);
      return response.json();
    }

    const loadTradingStatus = () => get('/api/trading/status', 'trading status');
    const loadPortfolio = () => get('/api/portfolio', 'portfolio');
    const loadOrders = (limit = 50) => get(
      `/api/orders?limit=${encodeURIComponent(limit)}`,
      'order history',
    );
    const loadAudit = (limit = 80) => get(
      `/api/audit?limit=${encodeURIComponent(limit)}`,
      'audit history',
    );

    return Object.freeze({
      loadTradingStatus,
      loadPortfolio,
      loadOrders,
      loadAudit,
    });
  }

  global.ObservatoryBackendActions = Object.freeze({create});
}(window));
