(function defineStrategyHealthAttribution(global) {
  'use strict';

  function percent(value, digits = 2) {
    if (value == null || value === '') return '—';
    return `${(Number(value) * 100).toFixed(digits)}%`;
  }

  function render(root, reports) {
    root.replaceChildren();
    const attributions = (reports || []).flatMap((report) =>
      (report.symbol_attribution || []).map((item) => ({
        strategy_id: report.strategy_id,
        version: report.version,
        ...item,
      })),
    );

    if (!attributions.length) {
      const empty = document.createElement('p');
      empty.className = 'empty-state';
      empty.textContent = '标的归因：等待足够的已结算策略样本。';
      root.appendChild(empty);
      return;
    }

    for (const item of attributions) {
      const card = document.createElement('article');
      card.className = 'loop-card';

      const top = document.createElement('div');
      const identity = document.createElement('strong');
      identity.textContent = `${item.strategy_id}@${item.version} · ${item.symbol}`;
      const status = document.createElement('span');
      status.className = item.degraded ? 'mini-status danger' : 'mini-status safe';
      status.textContent = item.degraded ? 'DEGRADED' : 'HEALTHY';
      top.append(identity, status);

      const metrics = document.createElement('p');
      metrics.textContent = `标的归因 · 样本 ${item.closed_observations ?? 0} · 期望 ${percent(item.expectancy_after_costs)} · 回撤 ${percent(item.max_drawdown)}`;
      card.append(top, metrics);

      if (item.degraded) {
        const warning = document.createElement('small');
        warning.className = 'negative';
        warning.textContent = (item.degradation_reasons || []).join(' · ') || 'symbol health degraded';
        card.appendChild(warning);
      }
      root.appendChild(card);
    }
  }

  async function refresh() {
    const root = document.getElementById('strategy-symbol-attribution');
    if (!root) return;
    const runtime = global.ObservatoryRuntime.resolve(global.OBSERVATORY_CONFIG);
    if (runtime.mode !== 'backend') {
      render(root, []);
      return;
    }
    try {
      const response = await fetch(`${runtime.apiBase}/api/trading/status`, {
        method: 'GET',
        credentials: 'same-origin',
        cache: 'no-store',
      });
      if (!response.ok) throw new Error(`strategy health attribution failed: ${response.status}`);
      const status = await response.json();
      render(root, status.continuous_improvement?.strategy_health || []);
    } catch (error) {
      root.replaceChildren();
      const warning = document.createElement('p');
      warning.className = 'warning-text';
      warning.textContent = `标的归因读取失败：${error.message}`;
      root.appendChild(warning);
    }
  }

  global.ObservatoryStrategyHealthAttribution = Object.freeze({render, refresh});
  global.addEventListener('DOMContentLoaded', async () => {
    await refresh();
    const runtime = global.ObservatoryRuntime.resolve(global.OBSERVATORY_CONFIG);
    if (runtime.mode === 'backend') global.setInterval(refresh, 3000);
  });
}(window));
