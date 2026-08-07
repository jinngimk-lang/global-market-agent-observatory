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
    for (const handler of this.listeners.get(type) || []) {
      await handler(event);
    }
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

element('side').value = 'buy';
element('quantity').value = '0.001';
element('order-form').elements = [element('side'), element('quantity'), element('client-order-id')];

const windowListeners = new Map();
const runtime = {
  mode: 'backend',
  observeOnly: false,
  apiBase: '',
  market: {symbol: 'BTCUSDT', interval: '1m'},
  capabilities: {paperOrders: true, researchRefresh: true, accountRefresh: true},
};

let historyCalls = 0;
const fakeBackendActions = {
  async loadOrders() { return []; },
  async submitOrder() { throw new Error('simulated transport failure'); },
  async refreshResearch() { return {stored: 0}; },
};

globalThis.window = {
  OBSERVATORY_CONFIG: {},
  ObservatoryRuntime: {resolve: () => runtime},
  ObservatoryMarketClient: {
    create: () => ({
      async loadHistory() { historyCalls += 1; return []; },
      connect() { return () => {}; },
    }),
  },
  ObservatoryBackendActions: {create: () => fakeBackendActions},
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

let healthCalls = 0;
let portfolioCalls = 0;
let releasePortfolio = null;
globalThis.fetch = async (url) => {
  const path = String(url);
  if (path.includes('/api/health')) {
    healthCalls += 1;
    if (healthCalls === 1) throw new Error('simulated startup health failure');
    return {ok: true, status: 200, async json() { return {trading_mode: 'paper', market_symbol: 'BTCUSDT'}; }};
  }
  if (path.includes('/api/portfolio')) {
    portfolioCalls += 1;
    if (releasePortfolio) {
      await new Promise((resolve) => {
        const release = releasePortfolio;
        releasePortfolio = () => { release(); resolve(); };
      });
    }
    return {ok: true, status: 200, async json() { return {equity: 0, cash: 0, gross_exposure: 0, realized_pnl_today: 0, positions: []}; }};
  }
  const data = path.includes('/api/accounts') ? {accounts: []} : [];
  return {ok: true, status: 200, async json() { return data; }};
};

globalThis.setInterval = () => 0;

const source = fs.readFileSync(new URL('../../app/web/app.js', import.meta.url), 'utf8');
vm.runInThisContext(source, {filename: 'app/web/app.js'});

for (const handler of windowListeners.get('DOMContentLoaded') || []) {
  await handler();
}

assert.equal(healthCalls, 1, 'startup should attempt health exactly once before recovery');
assert.equal(historyCalls, 0, 'history should not run after a failed health load');
assert.match(element('refresh-status').textContent, /启动.*失败|重试/);
assert.equal(element('retry-button').hidden, false, 'startup failure must expose recovery');

await element('retry-button').dispatch('click');

assert.equal(healthCalls, 2, 'retry must replay the failed startup health load');
assert.equal(historyCalls, 1, 'retry must continue the startup chain through history');
assert.equal(element('mode-badge').textContent, 'PAPER');
assert.match(element('refresh-status').textContent, /完成/);
assert.equal(element('retry-button').hidden, true, 'successful startup recovery must clear retry state');

const portfolioCallsBeforeOverlap = portfolioCalls;
releasePortfolio = () => {};
const firstRefresh = element('refresh-button').dispatch('click');
await Promise.resolve();
const secondRefresh = element('refresh-button').dispatch('click');
await Promise.resolve();
assert.equal(
  portfolioCalls,
  portfolioCallsBeforeOverlap + 1,
  'overlapping refresh triggers must coalesce into one in-flight dashboard refresh',
);
releasePortfolio();
await Promise.all([firstRefresh, secondRefresh]);
assert.match(element('refresh-status').textContent, /完成/);

let rejected = false;
try {
  await element('order-form').dispatch('submit');
} catch (_) {
  rejected = true;
}

assert.equal(rejected, false, 'paper-order transport failure must be handled by the action chain');
assert.match(element('order-message').textContent, /失败|不可用|重试/);
assert.equal(element('order-message').className, 'message negative');
assert.equal(element('side').disabled, false, 'paper form must remain recoverable after a failed request');
