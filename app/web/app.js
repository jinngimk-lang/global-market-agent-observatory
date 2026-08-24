const runtime = window.ObservatoryRuntime.resolve(window.OBSERVATORY_CONFIG);
const marketClient = window.ObservatoryMarketClient.create(runtime);

const state = {
  runtime,
  chart: null,
  series: null,
  symbol: runtime.market.symbol,
  interval: runtime.market.interval,
  disconnectMarket: null,
  tradingStatus: null,
  portfolio: null,
  orders: [],
  audit: [],
};

const money = (value) => value == null || value === ''
  ? '—'
  : Number(value).toLocaleString('en-US', {maximumFractionDigits: 2});
const number = (value, digits = 4) => value == null || value === ''
  ? '—'
  : Number(value).toLocaleString('en-US', {maximumFractionDigits: digits});
const percent = (value, digits = 2) => value == null || value === ''
  ? '—'
  : `${(Number(value) * 100).toFixed(digits)}%`;
const apiUrl = (path) => `${runtime.apiBase}${path}`;

const reasonLabels = {
  insufficient_structure: '缺少可验证的期权结构',
  missing_order_flow: '缺少主动买卖方向确认',
  no_gamma_level_trigger: '未触发 Put/Call Wall 条件',
  call_wall_breakout: '突破 Call Wall',
  positive_order_flow: '订单流偏多',
  put_wall_breakdown: '跌破 Put Wall',
  negative_order_flow: '订单流偏空',
  put_wall_support: 'Put Wall 附近获得支撑',
  call_wall_rejection: 'Call Wall 附近受阻',
  vwap_reclaim: '重新站上 VWAP',
  vwap_rejection: 'VWAP 附近受阻',
  no_vwap_trigger: '未触发 VWAP 状态穿越',
  insufficient_history: '历史数据不足',
};

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = value;
}

async function fetchJSON(path, fallback) {
  if (runtime.mode !== 'backend') return fallback;
  try {
    const response = await fetch(apiUrl(path), {cache: 'no-store'});
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return await response.json();
  } catch (error) {
    console.error(`failed to fetch ${path}`, error);
    return fallback;
  }
}

function initChart() {
  const container = document.getElementById('chart');
  if (!window.LightweightCharts) {
    container.textContent = '图表组件未加载，但交易状态与决策数据仍可查看。';
    container.classList.add('chart-fallback');
    return;
  }
  state.chart = LightweightCharts.createChart(container, {
    layout: {background: {color: 'transparent'}, textColor: '#8795aa'},
    grid: {
      vertLines: {color: 'rgba(145, 164, 196, .06)'},
      horzLines: {color: 'rgba(145, 164, 196, .06)'},
    },
    rightPriceScale: {borderColor: 'rgba(145, 164, 196, .12)'},
    timeScale: {borderColor: 'rgba(145, 164, 196, .12)', timeVisible: true},
    crosshair: {mode: LightweightCharts.CrosshairMode.Normal},
  });
  state.series = state.chart.addCandlestickSeries({
    upColor: '#46d99a', downColor: '#ff6474', borderVisible: false,
    wickUpColor: '#46d99a', wickDownColor: '#ff6474',
  });
  const resize = () => state.chart.applyOptions({
    width: container.clientWidth,
    height: container.clientHeight,
  });
  new ResizeObserver(resize).observe(container);
  resize();
}

function candlePoint(item) {
  return {
    time: Math.floor(new Date(item.open_time).getTime() / 1000),
    open: Number(item.open), high: Number(item.high),
    low: Number(item.low), close: Number(item.close),
  };
}

async function loadHistory() {
  if (!state.series) return;
  let candles = [];
  if (runtime.mode === 'backend') {
    candles = await fetchJSON(
      `/api/candles/${encodeURIComponent(state.symbol)}?interval=${encodeURIComponent(state.interval)}&limit=300`,
      [],
    );
  } else if (state.symbol === runtime.market.symbol) {
    candles = await marketClient.loadHistory();
  }
  state.series.setData(candles.map(candlePoint));
  if (candles.length) {
    const last = candles[candles.length - 1];
    setText('last-price', money(last.close));
    setText('feed-source', `${last.source} · ${last.interval}`);
  } else {
    setText('last-price', '—');
    setText('feed-source', '该标的暂无K线');
  }
  setText('symbol-title', `${state.symbol} · ${state.interval}`);
}

function updateConnection(status) {
  const badge = document.getElementById('connection-badge');
  badge.textContent = status.label;
  badge.className = status.state === 'streaming' ? 'badge safe' : 'badge danger';
}

function updateMarketDisplay(candle) {
  if (candle.symbol === state.symbol && state.series) {
    state.series.update(candlePoint(candle));
    setText('last-price', money(candle.close));
    setText('feed-source', `${candle.source} · ${candle.interval}`);
  }
}

function connectMarket() {
  state.disconnectMarket = marketClient.connect(updateMarketDisplay, updateConnection);
}

function toneForAction(action) {
  if (action === 'buy') return 'safe';
  if (action === 'exit' || action === 'reduce') return 'danger';
  return 'muted';
}

function aggregateAction(signals) {
  const actions = signals.map((signal) => signal.action);
  if (actions.includes('exit')) return 'exit';
  if (actions.includes('reduce')) return 'reduce';
  if (actions.includes('buy')) return 'buy';
  return 'hold';
}

function explainRationales(codes) {
  if (!codes?.length) return '没有策略理由';
  return codes.map((code) => reasonLabels[code] || code).join(' · ');
}

function positionFor(symbol) {
  return state.portfolio?.positions?.find((position) => position.symbol === symbol) || null;
}

function actionableSignal(signals) {
  return signals.find((signal) => signal.action !== 'hold') || signals[0] || null;
}

function renderSystemSummary(status) {
  const summary = document.getElementById('system-summary');
  summary.replaceChildren();

  let headline = '自动交易尚未满足执行条件';
  let detail = '系统会继续观察并记录策略信号。';
  let tone = 'neutral';

  if (status.trading_state === 'halted') {
    headline = '风险已锁定：HALTED';
    detail = '行情和学习 loop 可以继续运行，但不会因为数据恢复而自动重新放开风险。';
    tone = 'danger';
  } else if (status.trading_state === 'reducing') {
    headline = '系统处于 REDUCING';
    detail = '策略健康或运行异常触发了风险收缩；不会自动恢复 ACTIVE。';
    tone = 'warning';
  } else if (!status.auto_trading_enabled) {
    headline = '当前只监控，不自动下单';
    detail = 'AUTO_TRADING_ENABLED=false；策略仍会计算并留下决策证据。';
  } else if (!status.promotion_execution_allowed) {
    headline = '策略晋级门正在阻止自动执行';
    detail = '券商执行能力和策略资金权限是两个独立 Gate；当前策略证据还不够。';
    tone = 'warning';
  } else if (!status.continuous_improvement?.health_execution_allowed) {
    headline = '策略健康门已阻止继续增加风险';
    detail = '持续评估发现策略健康不满足当前门槛。';
    tone = 'danger';
  } else if (status.autonomous_execution_enabled) {
    headline = '自动交易执行链已开启';
    detail = '每个订单仍必须依次通过 Strategy → Portfolio → Risk → Execution。';
    tone = 'safe';
  }

  const title = document.createElement('strong');
  title.className = `system-headline ${tone}`;
  title.textContent = headline;
  const body = document.createElement('p');
  body.textContent = detail;
  summary.append(title, body);

  const universe = status.trading_universe || [];
  const sourceWarning = document.createElement('div');
  sourceWarning.className = 'source-context';
  const targetText = universe.length ? universe.join(' / ') : '未配置';
  sourceWarning.textContent = `行情源：${String(status.market_source || '—').toUpperCase()} · 当前feed标的：${status.market_symbol || '—'} · 交易Universe：${targetText}`;
  summary.appendChild(sourceWarning);

  if (
    status.market_source === 'replay'
    && universe.length
    && !universe.includes(status.market_symbol)
  ) {
    const warning = document.createElement('div');
    warning.className = 'truth-warning';
    warning.textContent = `当前只是 ${status.market_symbol} 的 replay 行情；${targetText} 尚未收到对应实时市场 cycle。页面不会把跳动K线伪装成这些股票正在被自动交易。`;
    summary.appendChild(warning);
  }

  setText('data-source-label', `${status.execution_provider || '—'} · ${status.market_source || '—'}`);
}

function renderBadges(status) {
  const mode = document.getElementById('mode-badge');
  mode.textContent = `MODE ${String(status.trading_mode || '—').toUpperCase()}`;
  mode.className = 'badge muted';

  const trading = document.getElementById('trading-state-badge');
  trading.textContent = `STATE ${String(status.trading_state || '—').toUpperCase()}`;
  trading.className = status.trading_state === 'active'
    ? 'badge safe'
    : status.trading_state === 'halted' ? 'badge danger' : 'badge warning';

  const execution = document.getElementById('execution-badge');
  execution.textContent = status.autonomous_execution_enabled ? 'AUTO EXEC ON' : 'AUTO EXEC OFF';
  execution.className = status.autonomous_execution_enabled ? 'badge safe' : 'badge muted';
}

function renderDecisionCards(status) {
  const root = document.getElementById('decision-cards');
  root.replaceChildren();
  const universe = status.trading_universe?.length
    ? status.trading_universe
    : Object.keys(status.last_cycles || {});

  if (!universe.length) {
    const empty = document.createElement('article');
    empty.className = 'decision-card placeholder';
    empty.textContent = '没有配置交易标的。';
    root.appendChild(empty);
    return;
  }

  for (const symbol of universe) {
    const cycle = status.last_cycles?.[symbol];
    const signals = cycle?.signals || [];
    const action = aggregateAction(signals);
    const primary = actionableSignal(signals);
    const position = positionFor(symbol);
    const card = document.createElement('article');
    card.className = `decision-card action-${action}`;

    const header = document.createElement('div');
    header.className = 'decision-card-header';
    const symbolBlock = document.createElement('div');
    const symbolName = document.createElement('strong');
    symbolName.className = 'symbol-name';
    symbolName.textContent = symbol;
    const price = document.createElement('span');
    price.textContent = position
      ? `$${money(position.market_price)}`
      : primary?.entry_price != null ? `$${money(primary.entry_price)}` : '暂无价格';
    symbolBlock.append(symbolName, price);
    const badge = document.createElement('span');
    badge.className = `decision-action ${toneForAction(action)}`;
    badge.textContent = action.toUpperCase();
    header.append(symbolBlock, badge);
    card.appendChild(header);

    if (!cycle) {
      const empty = document.createElement('p');
      empty.className = 'decision-explanation warning-text';
      empty.textContent = '尚无该标的 market cycle。当前页面不会猜测 BUY/SELL。';
      card.appendChild(empty);
      root.appendChild(card);
      continue;
    }

    const strategyList = document.createElement('div');
    strategyList.className = 'strategy-list';
    if (!signals.length) {
      const row = document.createElement('div');
      row.className = 'strategy-row';
      row.textContent = '没有策略输出';
      strategyList.appendChild(row);
    }
    for (const signal of signals) {
      const row = document.createElement('div');
      row.className = 'strategy-row';
      const top = document.createElement('div');
      const name = document.createElement('strong');
      name.textContent = `${signal.strategy_id}@${signal.version}`;
      const stateNode = document.createElement('span');
      stateNode.className = `mini-action ${toneForAction(signal.action)}`;
      stateNode.textContent = `${signal.action.toUpperCase()} · ${percent(signal.confidence)}`;
      top.append(name, stateNode);
      const rationale = document.createElement('p');
      rationale.textContent = explainRationales(signal.rationale_codes);
      row.append(top, rationale);
      strategyList.appendChild(row);
    }
    card.appendChild(strategyList);

    const facts = document.createElement('div');
    facts.className = 'decision-facts';
    const allocation = cycle.allocations?.find((item) => item.intent) || cycle.allocations?.[0];
    const execution = cycle.executions?.[cycle.executions.length - 1];
    const pnl = position
      ? Number(position.quantity) * (Number(position.market_price) - Number(position.average_price))
      : null;
    const factItems = [
      ['持仓', position ? `${number(position.quantity)} @ ${money(position.average_price)}` : '无'],
      ['失效价', primary?.invalidation_price != null ? money(primary.invalidation_price) : '—'],
      ['组合分配', allocation ? `${allocation.code}${allocation.requested_notional != null ? ` · $${money(allocation.requested_notional)}` : ''}` : '无订单意图'],
      ['执行结果', execution ? `${String(execution.status).toUpperCase()} · ${execution.code || '—'}` : '未送单'],
      ['浮盈亏', pnl == null ? '—' : `${pnl >= 0 ? '+' : ''}${money(pnl)}`],
    ];
    for (const [label, value] of factItems) {
      const item = document.createElement('div');
      const labelNode = document.createElement('span');
      labelNode.textContent = label;
      const valueNode = document.createElement('strong');
      valueNode.textContent = value;
      item.append(labelNode, valueNode);
      facts.appendChild(item);
    }
    card.appendChild(facts);

    const explanation = document.createElement('p');
    explanation.className = 'decision-explanation';
    if (cycle.skipped_reason) {
      explanation.textContent = `本周期跳过：${cycle.skipped_reason}`;
    } else if (signals.every((signal) => signal.action === 'hold')) {
      explanation.textContent = '策略已经评估，但当前没有满足可执行条件，所以 HOLD。';
    } else if (allocation && !allocation.intent) {
      explanation.textContent = `出现策略触发，但组合层未生成订单：${allocation.message || allocation.code}`;
    } else if (!status.autonomous_execution_enabled) {
      explanation.textContent = '出现策略/分配结果，但自动执行 Gate 当前关闭，因此不会送往券商。';
    } else if (execution) {
      explanation.textContent = `订单已经进入执行链：${execution.message || execution.code || execution.status}`;
    } else {
      explanation.textContent = '策略输出已记录，等待组合/风控/执行链下一步结果。';
    }
    card.appendChild(explanation);

    card.addEventListener('click', async () => {
      state.symbol = symbol;
      await loadHistory();
    });
    root.appendChild(card);
  }
}

function summarizeAudit(event) {
  const payload = event.payload || {};
  switch (event.event_type) {
    case 'strategy_signal':
      return `${payload.strategy_id || 'strategy'} → ${String(payload.action || 'hold').toUpperCase()} · ${explainRationales(payload.rationale_codes || [])}`;
    case 'risk_decision':
      return `${payload.allowed ? 'APPROVED' : 'REJECTED'} · ${payload.code || 'risk'} · ${payload.message || ''}`;
    case 'execution':
      return `${String(payload.status || 'unknown').toUpperCase()} · ${payload.code || 'execution'} · ${payload.message || ''}`;
    case 'kill_switch':
      return `HALT · ${payload.reason || 'kill switch'}`;
    case 'reconciliation':
      return `${payload.code || 'reconciliation'} · ${payload.message || ''}`;
    case 'system':
      return `${payload.kind || payload.code || 'system'} · ${payload.message || payload.reason || ''}`;
    default:
      return JSON.stringify(payload);
  }
}

function renderDecisionChain(audit) {
  const root = document.getElementById('decision-chain');
  root.replaceChildren();
  const relevant = audit
    .filter((event) => ['strategy_signal', 'risk_decision', 'execution', 'kill_switch', 'reconciliation', 'system'].includes(event.event_type))
    .slice(0, 16);
  if (!relevant.length) {
    const empty = document.createElement('p');
    empty.className = 'empty-state';
    empty.textContent = '还没有策略 / 风控 / 执行事件。';
    root.appendChild(empty);
    return;
  }

  for (const event of relevant) {
    const item = document.createElement('article');
    item.className = `chain-event type-${event.event_type}`;
    const top = document.createElement('div');
    const type = document.createElement('strong');
    type.textContent = event.event_type.replaceAll('_', ' ').toUpperCase();
    const time = document.createElement('span');
    time.textContent = new Date(event.occurred_at).toLocaleTimeString();
    top.append(type, time);
    const subject = document.createElement('span');
    subject.className = 'chain-subject';
    subject.textContent = event.subject || 'runtime';
    const detail = document.createElement('p');
    detail.textContent = summarizeAudit(event);
    item.append(top, subject, detail);
    root.appendChild(item);
  }
}

function renderPortfolio(portfolio) {
  setText('equity', money(portfolio.equity));
  setText('cash', money(portfolio.cash));
  setText('gross-exposure', money(portfolio.gross_exposure));
  setText('portfolio-mode', String(portfolio.mode || '—').toUpperCase());
  const realized = Number(portfolio.realized_pnl_today || 0);
  const realizedNode = document.getElementById('realized-pnl');
  realizedNode.textContent = `${realized >= 0 ? '+' : ''}${money(realized)}`;
  realizedNode.className = realized >= 0 ? 'positive' : 'negative';

  const body = document.getElementById('positions-body');
  body.replaceChildren();
  if (!portfolio.positions?.length) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 6;
    cell.className = 'empty';
    cell.textContent = '暂无持仓；系统不会为了让页面好看而伪造仓位。';
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }

  for (const position of portfolio.positions) {
    const pnl = Number(position.quantity) * (Number(position.market_price) - Number(position.average_price));
    const returnRate = Number(position.average_price)
      ? (Number(position.market_price) - Number(position.average_price)) / Number(position.average_price)
      : 0;
    const row = document.createElement('tr');
    const values = [
      position.symbol,
      number(position.quantity),
      money(position.average_price),
      money(position.market_price),
      `${pnl >= 0 ? '+' : ''}${money(pnl)}`,
      `${returnRate >= 0 ? '+' : ''}${percent(returnRate)}`,
    ];
    values.forEach((value, index) => {
      const cell = document.createElement('td');
      cell.textContent = value;
      if (index >= 4) cell.className = pnl >= 0 ? 'positive' : 'negative';
      row.appendChild(cell);
    });
    body.appendChild(row);
  }
}

function renderExecutions(orders) {
  const body = document.getElementById('executions-body');
  body.replaceChildren();
  if (!orders.length) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 6;
    cell.className = 'empty';
    cell.textContent = '暂无订单；请先看上方决策卡确认是“没有信号”还是“Gate 阻止执行”。';
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }

  for (const order of orders.slice(0, 30)) {
    const row = document.createElement('tr');
    const intent = order.intent || {};
    const timestamp = order.filled_at || intent.requested_at;
    const values = [
      timestamp ? new Date(timestamp).toLocaleString() : '—',
      intent.symbol || '—',
      String(intent.side || '—').toUpperCase(),
      number(intent.quantity),
      order.filled_price != null ? money(order.filled_price) : money(intent.reference_price),
      String(order.status || '—').toUpperCase(),
    ];
    values.forEach((value) => {
      const cell = document.createElement('td');
      cell.textContent = value;
      row.appendChild(cell);
    });
    body.appendChild(row);
  }
}

function renderStrategyHealth(status) {
  const body = document.getElementById('strategy-health-body');
  body.replaceChildren();
  const promotions = status.strategy_promotion || [];
  const health = status.continuous_improvement?.strategy_health || [];
  if (!promotions.length && !health.length) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 7;
    cell.className = 'empty';
    cell.textContent = '暂无策略证据状态。';
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }

  const identities = new Set([
    ...promotions.map((item) => `${item.strategy_id}@${item.version}`),
    ...health.map((item) => `${item.strategy_id}@${item.version}`),
  ]);
  for (const identity of identities) {
    const [strategyId, version] = identity.split('@');
    const promotion = promotions.find((item) => item.strategy_id === strategyId && item.version === version);
    const report = health.find((item) => item.strategy_id === strategyId && item.version === version);
    const row = document.createElement('tr');
    const promotionText = promotion
      ? `${promotion.allowed ? 'ALLOWED' : 'BLOCKED'} · ${promotion.current_stage}→${promotion.required_stage}`
      : '—';
    const healthText = report
      ? report.degraded ? `DEGRADED · ${(report.degradation_reasons || []).join(', ')}` : 'HEALTHY'
      : '等待样本';
    const values = [
      strategyId,
      version,
      promotionText,
      healthText,
      report?.closed_observations ?? 0,
      percent(report?.expectancy_after_costs),
      percent(report?.max_drawdown),
    ];
    values.forEach((value, index) => {
      const cell = document.createElement('td');
      cell.textContent = value;
      if (index === 2 && promotion && !promotion.allowed) cell.className = 'warning-text';
      if (index === 3 && report?.degraded) cell.className = 'negative';
      row.appendChild(cell);
    });
    body.appendChild(row);
  }
}

function renderRuntimeLoops(status) {
  const root = document.getElementById('runtime-loops');
  root.replaceChildren();
  const loops = status.runtime_loops || {};
  const labels = {
    market_feed: 'Market Feed',
    continuous_improvement: 'Continuous Improvement',
    options_structure: 'Options Structure',
    account_observers: 'Account Observers',
  };
  for (const [key, label] of Object.entries(labels)) {
    const loop = loops[key] || {};
    const card = document.createElement('article');
    card.className = 'loop-card';
    const top = document.createElement('div');
    const name = document.createElement('strong');
    name.textContent = label;
    const badge = document.createElement('span');
    const configured = loop.enabled === false || loop.configured === 0 || loop.configured === false
      ? false : true;
    const running = Boolean(loop.running);
    badge.textContent = !configured ? 'NOT CONFIGURED' : running ? 'RUNNING' : 'STOPPED';
    badge.className = !configured ? 'mini-status muted' : running ? 'mini-status safe' : 'mini-status danger';
    top.append(name, badge);
    card.appendChild(top);

    const details = document.createElement('p');
    const failures = loop.failure_count != null ? `failures ${loop.failure_count}` : '';
    const error = loop.last_error || (loop.errors && Object.keys(loop.errors).length ? 'observer errors' : '');
    details.textContent = [failures, error].filter(Boolean).join(' · ') || 'no reported loop error';
    card.appendChild(details);

    if (loop.symbol_errors && Object.keys(loop.symbol_errors).length) {
      const errors = document.createElement('small');
      errors.textContent = Object.entries(loop.symbol_errors).map(([symbol, message]) => `${symbol}: ${message}`).join(' | ');
      card.appendChild(errors);
    }
    root.appendChild(card);
  }
}

async function refreshAll() {
  const [status, portfolio, orders, audit] = await Promise.all([
    fetchJSON('/api/trading/status', {
      trading_mode: 'observe', execution_provider: 'none', auto_trading_enabled: false,
      promotion_execution_allowed: false, autonomous_execution_enabled: false,
      trading_state: 'active', market_source: 'static', market_symbol: runtime.market.symbol,
      trading_universe: [runtime.market.symbol], last_cycles: {}, strategy_promotion: [],
      continuous_improvement: {health_execution_allowed: true, strategy_health: []}, runtime_loops: {},
    }),
    fetchJSON('/api/portfolio', {equity: 0, cash: 0, gross_exposure: 0, realized_pnl_today: 0, mode: 'observe', positions: []}),
    fetchJSON('/api/orders?limit=50', []),
    fetchJSON('/api/audit?limit=80', []),
  ]);

  state.tradingStatus = status;
  state.portfolio = portfolio;
  state.orders = orders;
  state.audit = audit;

  renderBadges(status);
  renderSystemSummary(status);
  renderPortfolio(portfolio);
  renderDecisionCards(status);
  renderDecisionChain(audit);
  renderExecutions(orders);
  renderStrategyHealth(status);
  renderRuntimeLoops(status);

  if (!state.symbol || state.symbol === runtime.market.symbol) {
    state.symbol = status.market_symbol || runtime.market.symbol;
    setText('symbol-title', `${state.symbol} · ${state.interval}`);
  }
}

window.addEventListener('DOMContentLoaded', async () => {
  initChart();
  await refreshAll();
  await loadHistory();
  connectMarket();
  if (runtime.mode === 'backend') {
    setInterval(refreshAll, 3000);
  }
});
