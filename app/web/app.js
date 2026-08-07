const runtime = window.ObservatoryRuntime.resolve(window.OBSERVATORY_CONFIG);
const marketClient = window.ObservatoryMarketClient.create(runtime);
const backendActions = window.ObservatoryBackendActions?.create(runtime) || null;

const state = {
  runtime,
  chart: null,
  series: null,
  symbol: runtime.market.symbol,
  interval: runtime.market.interval,
  markers: [],
  disconnectMarket: null,
  refreshInterval: null,
  startupReady: false,
  refreshPromise: null,
  researchPromise: null,
};

const money = (value) => Number(value || 0).toLocaleString('en-US', {maximumFractionDigits: 2});
const number = (value, digits = 6) => Number(value || 0).toLocaleString('en-US', {maximumFractionDigits: digits});
const text = (value) => value ?? '—';
const apiUrl = (path) => `${runtime.apiBase}${path}`;

function initChart() {
  const container = document.getElementById('chart');
  state.chart = LightweightCharts.createChart(container, {
    layout: {background: {color: 'transparent'}, textColor: '#8e9bb1'},
    grid: {vertLines: {color: 'rgba(160,180,215,.06)'}, horzLines: {color: 'rgba(160,180,215,.06)'}},
    rightPriceScale: {borderColor: 'rgba(160,180,215,.12)'},
    timeScale: {borderColor: 'rgba(160,180,215,.12)', timeVisible: true, secondsVisible: false},
    crosshair: {mode: LightweightCharts.CrosshairMode.Normal},
  });
  state.series = state.chart.addCandlestickSeries({
    upColor: '#50e3a4', downColor: '#ff6b7a', borderVisible: false,
    wickUpColor: '#50e3a4', wickDownColor: '#ff6b7a',
  });
  const resize = () => state.chart.applyOptions({width: container.clientWidth, height: container.clientHeight});
  new ResizeObserver(resize).observe(container);
  resize();
}

function candlePoint(item) {
  return {
    time: Math.floor(new Date(item.open_time).getTime() / 1000),
    open: Number(item.open),
    high: Number(item.high),
    low: Number(item.low),
    close: Number(item.close),
  };
}

function updateMarketDisplay(candle) {
  state.series.update(candlePoint(candle));
  document.getElementById('last-price').textContent = money(candle.close);
  document.getElementById('feed-source').textContent = `${candle.source} · ${candle.interval}`;
}

function updateConnection(status) {
  const badge = document.getElementById('connection-badge');
  badge.textContent = status.label;
  badge.className = status.state === 'streaming' ? 'badge safe' : 'badge danger';
}

async function loadHistory() {
  const candles = await marketClient.loadHistory();
  if (candles.length) {
    state.series.setData(candles.map(candlePoint));
    const last = candles[candles.length - 1];
    document.getElementById('last-price').textContent = money(last.close);
    document.getElementById('feed-source').textContent = `${last.source} · ${last.interval}`;
  }
}

function connectMarket() {
  if (state.disconnectMarket) return;
  state.disconnectMarket = marketClient.connect(updateMarketDisplay, updateConnection);
}

function disconnectMarket() {
  if (!state.disconnectMarket) return;
  state.disconnectMarket();
  state.disconnectMarket = null;
}

function startBackgroundRefresh() {
  if (runtime.mode !== 'backend' || state.refreshInterval !== null) return;
  state.refreshInterval = setInterval(runRefresh, 5000);
}

function stopBackgroundRefresh() {
  if (state.refreshInterval === null) return;
  clearInterval(state.refreshInterval);
  state.refreshInterval = null;
}

function suspendPage() {
  stopBackgroundRefresh();
  disconnectMarket();
}

function restorePage(event) {
  if (!event.persisted) return;
  connectMarket();
  startBackgroundRefresh();
}

async function loadHealth() {
  const modeBadge = document.getElementById('mode-badge');
  const capabilityBadge = document.getElementById('capability-badge');
  document.getElementById('symbol-title').textContent = `${state.symbol} · ${state.interval}`;

  if (runtime.observeOnly) {
    modeBadge.textContent = 'OBSERVE ONLY';
    modeBadge.className = 'badge safe';
    capabilityBadge.textContent = 'PUBLIC DATA';
    capabilityBadge.className = 'badge muted';
    return;
  }

  const health = await fetch(apiUrl('/api/health')).then((response) => response.json());
  modeBadge.textContent = health.trading_mode.toUpperCase();
  capabilityBadge.textContent = 'PRIVATE BACKEND';
  state.symbol = health.market_symbol;
  document.getElementById('symbol-title').textContent = `${health.market_symbol} · ${state.interval}`;
}

function demoData(key, fallback) {
  const source = window.OBSERVATORY_DEMO_DATA || {};
  return source[key] ?? fallback;
}

async function loadPortfolio() {
  const portfolio = runtime.mode === 'backend'
    ? await fetch(apiUrl('/api/portfolio')).then((response) => response.json())
    : demoData('portfolio', {equity: 0, cash: 0, gross_exposure: 0, realized_pnl_today: 0, positions: []});
  document.getElementById('equity').textContent = money(portfolio.equity);
  document.getElementById('cash').textContent = money(portfolio.cash);
  document.getElementById('gross-exposure').textContent = money(portfolio.gross_exposure);
  const realized = Number(portfolio.realized_pnl_today);
  const realizedNode = document.getElementById('realized-pnl');
  realizedNode.textContent = money(realized);
  realizedNode.className = realized >= 0 ? 'positive' : 'negative';
  const body = document.getElementById('positions-body');
  body.replaceChildren();
  if (!portfolio.positions.length) {
    body.innerHTML = `<tr><td colspan="5" class="empty">${runtime.observeOnly ? '静态观察版不读取账户持仓' : '暂无持仓'}</td></tr>`;
    return;
  }
  for (const position of portfolio.positions) {
    const pnl = Number(position.quantity) * (Number(position.market_price) - Number(position.average_price));
    const row = document.createElement('tr');
    for (const value of [position.symbol, number(position.quantity), money(position.average_price), money(position.market_price)]) {
      const cell = document.createElement('td'); cell.textContent = value; row.appendChild(cell);
    }
    const pnlCell = document.createElement('td'); pnlCell.textContent = money(pnl); pnlCell.className = pnl >= 0 ? 'positive' : 'negative'; row.appendChild(pnlCell);
    body.appendChild(row);
  }
}

async function loadOrders() {
  const orders = runtime.mode === 'backend'
    ? await backendActions.loadOrders(50)
    : demoData('orders', []);
  const body = document.getElementById('orders-body');
  body.replaceChildren();
  state.markers = [];
  if (!orders.length) {
    body.innerHTML = `<tr><td colspan="6" class="empty">${runtime.observeOnly ? '观察模式不提交订单' : '暂无订单'}</td></tr>`;
    return;
  }
  for (const order of orders) {
    const row = document.createElement('tr');
    const values = [
      new Date(order.filled_at || order.intent.requested_at).toLocaleString(),
      order.intent.side.toUpperCase(), order.intent.symbol, number(order.intent.quantity),
      money(order.filled_price), order.status.toUpperCase(),
    ];
    for (const value of values) { const cell = document.createElement('td'); cell.textContent = value; row.appendChild(cell); }
    body.appendChild(row);
    if (order.filled_at && order.filled_price) {
      state.markers.push({
        time: Math.floor(new Date(order.filled_at).getTime() / 1000),
        position: order.intent.side === 'buy' ? 'belowBar' : 'aboveBar',
        color: order.intent.side === 'buy' ? '#50e3a4' : '#ff6b7a',
        shape: order.intent.side === 'buy' ? 'arrowUp' : 'arrowDown',
        text: `${order.intent.side.toUpperCase()} ${number(order.intent.quantity)}`,
      });
    }
  }
  state.markers.sort((a, b) => a.time - b.time);
  state.series.setMarkers(state.markers);
}

async function loadExternalAccounts() {
  const payload = runtime.mode === 'backend'
    ? await fetch(apiUrl('/api/accounts')).then((response) => response.json())
    : demoData('accounts', {accounts: []});
  const body = document.getElementById('external-accounts-body');
  body.replaceChildren();
  if (!payload.accounts.length) {
    body.innerHTML = `<tr><td colspan="6" class="empty">${runtime.observeOnly ? '静态观察版不连接账户' : '未配置只读账户'}</td></tr>`;
    return;
  }
  for (const account of payload.accounts) {
    const snapshot = account.snapshot;
    const row = document.createElement('tr');
    const values = [
      account.name,
      snapshot?.mode || 'connecting',
      account.status,
      snapshot?.equity == null ? '—' : money(snapshot.equity),
      snapshot?.positions?.length ?? 0,
      snapshot?.orders?.length ?? 0,
    ];
    for (const value of values) {
      const cell = document.createElement('td');
      cell.textContent = value;
      row.appendChild(cell);
    }
    if (account.status === 'error') row.title = account.error || 'observer error';
    body.appendChild(row);
  }
}

async function loadCrisisWinners() {
  const winners = runtime.mode === 'backend'
    ? await fetch(apiUrl('/api/research/crisis-winners?limit=100')).then((response) => response.json())
    : demoData('crisisWinners', []);
  const body = document.getElementById('crisis-winners-body');
  body.replaceChildren();
  if (!winners.length) {
    body.innerHTML = '<tr><td colspan="6" class="empty">尚无 A/B 级验证案例</td></tr>';
    return;
  }
  for (const winner of winners) {
    const row = document.createElement('tr');
    const values = [
      winner.case.actor_name,
      winner.case.actor_type,
      winner.case.instrument,
      winner.window.name,
      money(winner.net_pnl),
      winner.case.evidence_grade,
    ];
    for (const value of values) {
      const cell = document.createElement('td');
      cell.textContent = value;
      row.appendChild(cell);
    }
    body.appendChild(row);
  }
}

async function loadPartnerships() {
  const assessments = runtime.mode === 'backend'
    ? await fetch(apiUrl('/api/research/partnerships?limit=100')).then((response) => response.json())
    : demoData('partnerships', []);
  const body = document.getElementById('partnerships-body');
  body.replaceChildren();
  if (!assessments.length) {
    body.innerHTML = '<tr><td colspan="4" class="empty">等待监管或公司披露</td></tr>';
    return;
  }
  for (const assessment of assessments) {
    const row = document.createElement('tr');
    const values = [
      assessment.entity || '—',
      assessment.maturity,
      assessment.confidence,
      assessment.validation_metrics.join(' · '),
    ];
    for (const value of values) {
      const cell = document.createElement('td');
      cell.textContent = value;
      row.appendChild(cell);
    }
    body.appendChild(row);
  }
}

async function loadEvidence() {
  const evidence = runtime.mode === 'backend'
    ? await fetch(apiUrl('/api/evidence?limit=100')).then((response) => response.json())
    : demoData('evidence', []);
  const body = document.getElementById('evidence-body');
  body.replaceChildren();
  if (!evidence.length) {
    body.innerHTML = '<tr><td colspan="5" class="empty">等待研究数据</td></tr>';
    return;
  }
  for (const item of evidence) {
    const row = document.createElement('tr');
    const gradeCell = document.createElement('td');
    const gradeBadge = document.createElement('span');
    gradeBadge.className = 'grade';
    gradeBadge.textContent = text(item.grade);
    gradeCell.appendChild(gradeBadge);
    row.appendChild(gradeCell);
    for (const value of [new Date(item.event_date || item.observed_at).toLocaleDateString(), text(item.entity), item.title, item.tags.join(', ')]) {
      const cell = document.createElement('td'); cell.textContent = value; row.appendChild(cell);
    }
    if (item.source_url) row.addEventListener('click', () => window.open(item.source_url, '_blank', 'noopener,noreferrer'));
    body.appendChild(row);
  }
}

async function refreshAll() {
  const tasks = [loadPortfolio(), loadOrders(), loadEvidence(), loadExternalAccounts(), loadCrisisWinners(), loadPartnerships()];
  const results = await Promise.allSettled(tasks);
  return results.filter((result) => result.status === 'rejected');
}

function setRefreshStatus(message, failed = false) {
  const status = document.getElementById('refresh-status');
  const retryButton = document.getElementById('retry-button');
  status.textContent = message;
  status.className = failed ? 'message negative' : 'message positive';
  retryButton.hidden = !failed;
}

async function runRefresh() {
  if (state.refreshPromise) return state.refreshPromise;

  const button = document.getElementById('refresh-button');
  const refreshPromise = (async () => {
    button.disabled = true;
    setRefreshStatus('刷新中…');
    try {
      const failures = await refreshAll();
      if (failures.length) {
        setRefreshStatus(`部分刷新失败（${failures.length} 项），可重试。`, true);
        return false;
      }
      setRefreshStatus('刷新完成');
      return true;
    } catch (_) {
      setRefreshStatus('刷新失败，可重试。', true);
      return false;
    } finally {
      button.disabled = !runtime.capabilities.accountRefresh;
    }
  })();

  state.refreshPromise = refreshPromise;
  try {
    return await refreshPromise;
  } finally {
    if (state.refreshPromise === refreshPromise) state.refreshPromise = null;
  }
}

async function runStartupLoad() {
  try {
    await loadHealth();
    await loadHistory();
    state.startupReady = true;
    return await runRefresh();
  } catch (_) {
    setRefreshStatus('启动数据加载失败，可重试。', true);
    return false;
  }
}

async function retryRefresh() {
  return state.startupReady ? runRefresh() : runStartupLoad();
}

async function submitOrder(event) {
  event.preventDefault();
  const message = document.getElementById('order-message');
  if (!runtime.capabilities.paperOrders) {
    message.textContent = '静态观察模式已禁用所有订单操作。';
    message.className = 'message negative';
    return;
  }
  const payload = {
    client_order_id: document.getElementById('client-order-id').value,
    symbol: state.symbol,
    side: document.getElementById('side').value,
    quantity: document.getElementById('quantity').value,
  };
  try {
    if (!backendActions) throw new Error('backend actions are unavailable');
    const result = await backendActions.submitOrder(payload);
    const data = result.data;
    if (!result.ok) {
      message.textContent = `拒绝：${data.detail?.code || 'request_failed'} · ${data.detail?.message || ''}`;
      message.className = 'message negative';
      return;
    }
    message.textContent = `成交：${data.intent.side.toUpperCase()} ${data.intent.quantity} @ ${data.filled_price}`;
    message.className = 'message positive';
    document.getElementById('client-order-id').value = crypto.randomUUID();
    await runRefresh();
  } catch (_) {
    message.textContent = '提交失败：请求未完成，可重试。';
    message.className = 'message negative';
  }
}

function setResearchStatus(message, failed = false) {
  const status = document.getElementById('research-status');
  const retryButton = document.getElementById('research-retry-button');
  status.textContent = message;
  status.className = failed ? 'message negative' : 'message positive';
  retryButton.hidden = !failed;
}

async function refreshResearch() {
  if (state.researchPromise) return state.researchPromise;
  if (!runtime.capabilities.researchRefresh) return false;

  const button = document.getElementById('research-button');
  const retryButton = document.getElementById('research-retry-button');
  const researchPromise = (async () => {
    button.disabled = true;
    retryButton.disabled = true;
    button.textContent = '采集中…';
    setResearchStatus('正在拉取官方更新…');
    try {
      if (!backendActions) throw new Error('backend actions are unavailable');
      const result = await backendActions.refreshResearch();
      await loadEvidence();
      setResearchStatus(`采集完成 · 新增 ${result.stored || 0} 条`);
      return true;
    } catch (_) {
      setResearchStatus('采集失败，可重试。', true);
      return false;
    } finally {
      button.disabled = !runtime.capabilities.researchRefresh;
      button.textContent = '拉取官方更新';
      retryButton.disabled = false;
    }
  })();

  state.researchPromise = researchPromise;
  try {
    return await researchPromise;
  } finally {
    if (state.researchPromise === researchPromise) state.researchPromise = null;
  }
}

function applyCapabilities() {
  const orderForm = document.getElementById('order-form');
  const researchButton = document.getElementById('research-button');
  const refreshButton = document.getElementById('refresh-button');
  if (!runtime.capabilities.paperOrders) {
    for (const control of orderForm.elements) control.disabled = true;
    document.getElementById('order-message').textContent = 'PUBLIC DATA / OBSERVE ONLY · 不连接账户，不提交订单。';
  }
  researchButton.disabled = !runtime.capabilities.researchRefresh;
  refreshButton.disabled = !runtime.capabilities.accountRefresh;
}

window.addEventListener('pagehide', suspendPage);
window.addEventListener('pageshow', restorePage);

window.addEventListener('DOMContentLoaded', async () => {
  initChart();
  document.getElementById('client-order-id').value = crypto.randomUUID();
  document.getElementById('order-form').addEventListener('submit', submitOrder);
  document.getElementById('refresh-button').addEventListener('click', runRefresh);
  document.getElementById('retry-button').addEventListener('click', retryRefresh);
  document.getElementById('research-button').addEventListener('click', refreshResearch);
  document.getElementById('research-retry-button').addEventListener('click', refreshResearch);
  applyCapabilities();
  try {
    await runStartupLoad();
  } finally {
    connectMarket();
  }
  startBackgroundRefresh();
});