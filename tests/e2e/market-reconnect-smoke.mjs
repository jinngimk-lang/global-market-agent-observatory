import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const statuses = [];
const candles = [];
const timeoutQueue = [];
const intervalCallbacks = new Map();
let nextTimerId = 1;

class FakeWebSocket {
  static instances = [];

  constructor(url) {
    this.url = url;
    this.readyState = 0;
    this.listeners = new Map();
    FakeWebSocket.instances.push(this);
  }

  addEventListener(type, handler) {
    const handlers = this.listeners.get(type) || [];
    handlers.push(handler);
    this.listeners.set(type, handlers);
  }

  emit(type, payload = {}) {
    for (const handler of this.listeners.get(type) || []) handler(payload);
  }

  open() {
    this.readyState = 1;
    this.emit('open');
  }

  closeFromServer() {
    this.readyState = 3;
    this.emit('close');
  }

  close() {
    this.readyState = 3;
    this.emit('close');
  }
}

const fakeWindow = {
  location: {protocol: 'https:', host: 'example.test', href: 'https://example.test/'},
  setTimeout(callback) {
    const id = nextTimerId++;
    timeoutQueue.push({id, callback});
    return id;
  },
  clearTimeout(id) {
    const index = timeoutQueue.findIndex((item) => item.id === id);
    if (index >= 0) timeoutQueue.splice(index, 1);
  },
  setInterval(callback) {
    const id = nextTimerId++;
    intervalCallbacks.set(id, callback);
    return id;
  },
  clearInterval(id) {
    intervalCallbacks.delete(id);
  },
};

globalThis.window = fakeWindow;
globalThis.WebSocket = FakeWebSocket;

const source = fs.readFileSync(new URL('../../app/web/market-client.js', import.meta.url), 'utf8');
vm.runInThisContext(source, {filename: 'app/web/market-client.js'});

const runtime = {
  mode: 'static',
  apiBase: '',
  market: {symbol: 'BTCUSDT', interval: '1m'},
};
const client = window.ObservatoryMarketClient.create(runtime);
const disconnect = client.connect(
  (candle) => candles.push(candle),
  (status) => statuses.push(status),
);

assert.equal(FakeWebSocket.instances.length, 1, 'connect must attempt a stream immediately');

for (let attempt = 0; attempt < 3; attempt += 1) {
  const socket = FakeWebSocket.instances.at(-1);
  socket.closeFromServer();
  assert.equal(statuses.at(-1).state, attempt === 2 ? 'reconnecting' : 'reconnecting');
  const scheduled = timeoutQueue.shift();
  assert.ok(scheduled, 'disconnect must schedule a reconnect');
  scheduled.callback();
}

assert.ok(statuses.some((status) => status.label === 'REPLAY FALLBACK'), 'repeated static disconnects must enter replay fallback');
assert.ok(intervalCallbacks.size > 0, 'replay fallback must keep the market view producing data');

for (const callback of intervalCallbacks.values()) callback();
assert.equal(candles.length, 1, 'replay fallback must emit a candle');
assert.equal(candles[0].source, 'deterministic-replay');

const recoveredSocket = FakeWebSocket.instances.at(-1);
recoveredSocket.open();
assert.equal(statuses.at(-1).state, 'streaming', 'successful reconnect must restore streaming state');
assert.equal(intervalCallbacks.size, 0, 'successful reconnect must stop replay fallback');

disconnect();
assert.equal(timeoutQueue.length, 0, 'manual disconnect must not leave a reconnect timer behind');
assert.equal(intervalCallbacks.size, 0, 'manual disconnect must leave no replay timer behind');
