import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

class FakeElement {
  constructor(id = '') {
    this.id = id;
    this.textContent = '';
    this.className = '';
    this.hidden = false;
    this.disabled = false;
    this.value = '';
    this.innerHTML = '';
    this.title = '';
    this.clientWidth = 1280;
    this.clientHeight = 720;
    this.children = [];
    this.elements = [];
    this.listeners = new Map();
  }

  addEventListener(type, handler) {
    const handlers = this.listeners.get(type) || [];
    handlers.push(handler);
    this.listeners.set(type, handlers);
  }

  async dispatch(type) {
    const event = {preventDefault() {}};
    for (const handler of this.listeners.get(type) || []) await handler(event);
  }

  replaceChildren() {
    this.children = [];
    this.innerHTML = '';
  }

  appendChild(child) {
    this.children.push(child);
    return child;
  }
}

const elements = new Map();
const element = (id) => {
  if (!elements.has(id)) elements.set(id, new FakeElement(id));
  return elements.get(id);
};

for (const id of [
  'chart', 'connection-badge', 'mode-badge', 'capability-badge', 'symbol-title',
  'last-price', 'feed-source', 'equity', 'cash', 'gross-exposure', 'realized-pnl',
  'positions-body', 'orders-body', 'external-accounts-body', 'crisis-winners-body',
  'partnerships-body', 'evidence-body', 'refresh-status', 'retry-button',
  'refresh-button', 'order-form', 'order-message', 'client-order-id', 'side', 'quantity',
  'research-button', 'research-status', 'research-retry-button',
]) element(id);
element('order-form').elements = [element('side'), element('quantity'), element('client-order-id')];

const windowListeners = new Map();
const runtime = {
  mode: 'backend',
  observeOnly: false,
  apiBase: '',
  market: {symbol: 'BTCUSDT', interval: '1m'},
  capabilities: {paperOrders: true, researchRefresh: true, accountRefresh: true},
};

let researchCalls = 0;
let releaseResearch = null;
const backendActions = {
  async loadOrders() { return []; },
  async submitOrder() { return {ok: false, data: {detail: {code: 'disabled'}}}; },
  async refreshResearch() {
    researchCalls += 1;
    if (releaseResearch) {
      await new Promise((resolve) => {
        const release = releaseResearch;
        releaseResearch = () => { release(); resolve(); };
      });
    }
    return {stored: 1};
  },
};

globalThis.window = {
  OBSERVATORY_CONFIG: {},
  ObservatoryRuntime: {resolve: () => runtime},
  ObservatoryMarketClient: {
    create: () => ({
      async loadHistory() { return []; },
      connect() { return () => {}; },
    }),
  },
  ObservatoryBackendActions: {create: () => backendActions},
  addEventListener(type, handler) {
    const handlers = windowListeners.get(type) || [];
    handlers.push(handler);
    windowListeners.set(type, handlers);
  },
  open() {},
};

globalThis.document = {
  getElementById: element,
  createElement: () => new FakeElement(),
};

globalThis.LightweightCharts = {
  CrosshairMode: {Normal: 0},
  createChart: () => ({
    addCandlestickSeries: () => ({setData() {}, update() {}, setMarkers() {}}),
    applyOptions() {},
  }),
};

globalThis.ResizeObserver = class {
  constructor(callback) { this.callback = callback; }
  observe() { this.callback(); }
};

globalThis.fetch = async (url) => {
  const path = String(url);
  if (path.includes('/api/health')) {
    return {async json() { return {trading_mode: 'paper', market_symbol: 'BTCUSDT'}; }};
  }
  if (path.includes('/api/portfolio')) {
    return {async json() { return {equity: 0, cash: 0, gross_exposure: 0, realized_pnl_today: 0, positions: []}; }};
  }
  if (path.includes('/api/accounts')) {
    return {async json() { return {accounts: []}; }};
  }
  return {async json() { return []; }};
};

globalThis.setInterval = () => 1;
globalThis.clearInterval = () => {};

const appSource = fs.readFileSync(new URL('../../app/web/app.js', import.meta.url), 'utf8');
const recoverySource = fs.readFileSync(new URL('../../app/web/lifecycle-recovery.js', import.meta.url), 'utf8');
vm.runInThisContext(appSource, {filename: 'app/web/app.js'});
vm.runInThisContext(recoverySource, {filename: 'app/web/lifecycle-recovery.js'});

for (const handler of windowListeners.get('DOMContentLoaded') || []) await handler();

releaseResearch = () => {};
const staleResearch = element('research-button').dispatch('click');
await Promise.resolve();
assert.equal(element('research-button').disabled, true, 'in-flight research must disable the primary control');
assert.equal(element('research-retry-button').disabled, true, 'in-flight research must disable retry');

for (const handler of windowListeners.get('pagehide') || []) await handler({persisted: true});
for (const handler of windowListeners.get('pageshow') || []) await handler({persisted: true});

assert.equal(element('research-button').disabled, false, 'bfcache recovery must restore the research primary control for the current lifecycle');
assert.equal(element('research-retry-button').disabled, false, 'bfcache recovery must restore research retry so navigation cannot leave a dead end');
assert.equal(element('research-retry-button').hidden, false, 'recovery must expose a visible retry route');
assert.match(element('research-status').textContent, /页面已恢复|可重试/);

releaseResearch();
await staleResearch;
releaseResearch = null;
assert.equal(researchCalls, 1, 'the stale pre-navigation request must complete without being replayed');

await element('research-button').dispatch('click');
assert.equal(researchCalls, 2, 'a fresh post-recovery research action must remain reachable');
assert.match(element('research-status').textContent, /采集完成/);
