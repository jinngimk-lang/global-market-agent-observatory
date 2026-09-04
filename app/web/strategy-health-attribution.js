(function defineStrategyHealthAttribution(global) {
  'use strict';

  function percent(value, digits = 2) {
    if (value == null || value === '') return '—';
    return `${(Number(value) * 100).toFixed(digits)}%`;
  }

  function bps(value, digits = 2) {
    if (value == null || value === '') return '—';
    return `${Number(value).toFixed(digits)} bps`;
  }

  function seconds(value, digits = 2) {
    if (value == null || value === '') return '—';
    return `${Number(value).toFixed(digits)} s`;
  }

  function emptyState(root, message) {
    if (!root) return;
    root.replaceChildren();
    const empty = document.createElement('p');
    empty.className = 'empty-state';
    empty.textContent = message;
    root.appendChild(empty);
  }

  function renderExecutionFriction(root, reports) {
    if (!root) return;
    root.replaceChildren();
    if (!(reports || []).length) {
      emptyState(root, '成交摩擦：等待足够的已结算策略样本。');
      return;
    }

    for (const report of reports) {
      const friction = report.execution_friction || {};
      const observed = Number(friction.observed_fill_observations || 0);
      const closed = Number(friction.closed_observations || 0);
      const modeled = Number(friction.modeled_entry_observations || 0);

      const card = document.createElement('article');
      card.className = 'loop-card';

      const top = document.createElement('div');
      const identity = document.createElement('strong');
      identity.textContent = `${report.strategy_id}@${report.version}`;
      const status = document.createElement('span');
      status.className = observed > 0 ? 'mini-status safe' : 'mini-status';
      status.textContent = observed > 0
        ? `OBSERVED FILL ${observed} / ${closed}`
        : 'NO OBSERVED FILLS';
      top.append(identity, status);

      const actual = document.createElement('p');
      actual.textContent = [
        `Observed Fill Rate ${percent(friction.observed_fill_rate)}`,
        `真实入场滑点 ${bps(friction.mean_observed_entry_slippage_bps)}`,
        `Signal→Fill 延迟 ${seconds(friction.mean_execution_latency_seconds)}`,
      ].join(' · ');

      const assumptions = document.createElement('small');
      assumptions.textContent = [
        `MODELED COST ${bps(friction.current_transaction_cost_bps)}`,
        `MODELED ENTRY ${bps(friction.current_modeled_entry_slippage_bps)}`,
        `MODELED EXIT ${bps(friction.current_modeled_exit_slippage_bps)}`,
      ].join(' · ');

      const provenance = document.createElement('small');
      provenance.className = observed > 0 ? 'positive' : 'warning-text';
      provenance.textContent = `证据来源 · observed ${observed} · modeled ${modeled} · closed ${closed}`;

      card.append(top, actual, assumptions, provenance);
      root.appendChild(card);
    }
  }

  function renderSymbolAttribution(root, reports) {
    if (!root) return;
    root.replaceChildren();
    const attributions = (reports || []).flatMap((report) =>
      (report.symbol_attribution || []).map((item) => ({
        strategy_id: report.strategy_id,
        version: report.version,
        ...item,
      })),
    );

    if (!attributions.length) {
      emptyState(root, '标的归因：等待足够的已结算策略样本。');
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
    const frictionRoot = document.getElementById('strategy-execution-friction');
    const symbolRoot = document.getElementById('strategy-symbol-attribution');
    if (!frictionRoot && !symbolRoot) return;

    const runtime = global.ObservatoryRuntime.resolve(global.OBSERVATORY_CONFIG);
    if (runtime.mode !== 'backend') {
      renderExecutionFriction(frictionRoot, []);
      renderSymbolAttribution(symbolRoot, []);
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
      const reports = status.continuous_improvement?.strategy_health || [];
      renderExecutionFriction(frictionRoot, reports);
      renderSymbolAttribution(symbolRoot, reports);
    } catch (error) {
      emptyState(frictionRoot, `成交摩擦归因读取失败：${error.message}`);
      emptyState(symbolRoot, `标的归因读取失败：${error.message}`);
    }
  }

  global.ObservatoryStrategyHealthAttribution = Object.freeze({
    render: renderSymbolAttribution,
    renderExecutionFriction,
    renderSymbolAttribution,
    refresh,
  });
  global.addEventListener('DOMContentLoaded', async () => {
    await refresh();
    const runtime = global.ObservatoryRuntime.resolve(global.OBSERVATORY_CONFIG);
    if (runtime.mode === 'backend') global.setInterval(refresh, 3000);
  });
}(window));
