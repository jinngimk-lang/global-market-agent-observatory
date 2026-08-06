(function defineObservatoryBackendActions(global) {
  'use strict';

  function create(runtime) {
    const apiUrl = (path) => `${runtime.apiBase}${path}`;

    async function loadOrders(limit = 50) {
      const response = await fetch(apiUrl(`/api/orders?limit=${encodeURIComponent(limit)}`), {
        credentials: 'same-origin',
      });
      if (!response.ok) throw new Error(`order history failed: ${response.status}`);
      return response.json();
    }

    async function submitOrder(payload) {
      const response = await fetch(apiUrl('/api/orders'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        credentials: 'same-origin',
        body: JSON.stringify(payload),
      });
      return Object.freeze({ok: response.ok, status: response.status, data: await response.json()});
    }

    async function refreshResearch() {
      const response = await fetch(apiUrl('/api/research/refresh'), {
        method: 'POST',
        credentials: 'same-origin',
      });
      if (!response.ok) throw new Error(`research refresh failed: ${response.status}`);
      return response.json();
    }

    return Object.freeze({loadOrders, submitOrder, refreshResearch});
  }

  global.ObservatoryBackendActions = Object.freeze({create});
}(window));
