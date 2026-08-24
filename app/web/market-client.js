(function defineObservatoryMarketClient(global) {
  'use strict';

  const BINANCE_REST = 'https://api.binance.com/api/v3/klines';
  const BINANCE_STREAM = 'wss://stream.binance.com:9443/ws/';

  function intervalMilliseconds(interval) {
    const value = Number.parseInt(interval, 10) || 1;
    if (interval.endsWith('h')) return value * 60 * 60 * 1000;
    if (interval.endsWith('d')) return value * 24 * 60 * 60 * 1000;
    return value * 60 * 1000;
  }

  function seededRandom(seedText) {
    let state = 2166136261;
    for (const character of seedText) {
      state ^= character.charCodeAt(0);
      state = Math.imul(state, 16777619);
    }
    return function next() {
      state = Math.imul(state ^ (state >>> 15), 2246822507);
      state = Math.imul(state ^ (state >>> 13), 3266489909);
      state ^= state >>> 16;
      return (state >>> 0) / 4294967296;
    };
  }

  function fallbackHistory(symbol, interval, limit = 240) {
    const step = intervalMilliseconds(interval);
    const end = Math.floor(Date.now() / step) * step;
    const random = seededRandom(`${symbol}:${interval}:${Math.floor(end / step)}`);
    const startPrice = symbol.startsWith('BTC') ? 64000 : 100;
    let close = startPrice * (0.96 + random() * 0.08);
    const candles = [];

    for (let index = limit - 1; index >= 0; index -= 1) {
      const open = close;
      const drift = (random() - 0.49) * open * 0.004;
      close = Math.max(0.000001, open + drift);
      const spread = open * (0.001 + random() * 0.003);
      candles.push({
        symbol,
        interval,
        open_time: new Date(end - index * step).toISOString(),
        open,
        high: Math.max(open, close) + spread,
        low: Math.max(0.000001, Math.min(open, close) - spread),
        close,
        volume: 0,
        source: 'deterministic-replay',
      });
    }
    return candles;
  }

  function nextFallbackCandle(previous, sequence, now = Date.now()) {
    const symbol = previous.symbol;
    const interval = previous.interval;
    const step = intervalMilliseconds(interval);
    const random = seededRandom(`${symbol}:${interval}:stream:${sequence}:${Math.floor(now / 1000)}`);
    const open = Number(previous.close);
    const close = Math.max(0.000001, open * (1 + (random() - 0.5) * 0.0025));
    const spread = open * (0.0004 + random() * 0.0012);
    return {
      symbol,
      interval,
      open_time: new Date(Math.floor(now / step) * step).toISOString(),
      open,
      high: Math.max(open, close) + spread,
      low: Math.max(0.000001, Math.min(open, close) - spread),
      close,
      volume: 0,
      source: 'deterministic-replay',
    };
  }

  function normalizeBinanceKline(symbol, interval, item) {
    return {
      symbol,
      interval,
      open_time: new Date(Number(item[0])).toISOString(),
      open: Number(item[1]),
      high: Number(item[2]),
      low: Number(item[3]),
      close: Number(item[4]),
      volume: Number(item[5]),
      source: 'binance-public',
    };
  }

  function normalizeBinanceStream(symbol, interval, payload) {
    const item = payload.k;
    return {
      symbol,
      interval,
      open_time: new Date(Number(item.t)).toISOString(),
      open: Number(item.o),
      high: Number(item.h),
      low: Number(item.l),
      close: Number(item.c),
      volume: Number(item.v),
      source: 'binance-public',
    };
  }

  function backendSocketUrl(runtime) {
    if (!runtime.apiBase) {
      const protocol = global.location.protocol === 'https:' ? 'wss' : 'ws';
      return `${protocol}://${global.location.host}/ws/market`;
    }
    const url = new URL(runtime.apiBase, global.location.href);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    url.pathname = `${url.pathname.replace(/\/$/, '')}/ws/market`;
    url.search = '';
    return url.toString();
  }

  function create(runtime) {
    const symbol = runtime.market.symbol;
    const interval = runtime.market.interval;

    async function loadHistory(requestedSymbol = symbol, requestedInterval = interval) {
      const targetSymbol = String(requestedSymbol || symbol).trim().toUpperCase();
      const targetInterval = String(requestedInterval || interval).trim() || interval;

      if (runtime.mode === 'backend') {
        const response = await fetch(
          `${runtime.apiBase}/api/candles/${encodeURIComponent(targetSymbol)}?interval=${encodeURIComponent(targetInterval)}&limit=500`,
          {credentials: 'same-origin'},
        );
        if (!response.ok) throw new Error(`backend history failed: ${response.status}`);
        return response.json();
      }

      if (targetSymbol !== symbol || targetInterval !== interval) return [];

      try {
        const query = new URLSearchParams({symbol, interval, limit: '500'});
        const response = await fetch(`${BINANCE_REST}?${query}`, {
          method: 'GET',
          credentials: 'omit',
          cache: 'no-store',
          referrerPolicy: 'no-referrer',
        });
        if (!response.ok) throw new Error(`public history failed: ${response.status}`);
        const payload = await response.json();
        return payload.map((item) => normalizeBinanceKline(symbol, interval, item));
      } catch (_) {
        return fallbackHistory(symbol, interval, 500);
      }
    }

    function connect(onCandle, onStatus) {
      let stopped = false;
      let reconnectTimer = null;
      let replayTimer = null;
      let socket = null;
      let attempts = 0;
      let replayHistory = fallbackHistory(symbol, interval, 2);
      let replaySequence = 0;

      function stopReplay() {
        if (replayTimer !== null) {
          global.clearInterval(replayTimer);
          replayTimer = null;
        }
      }

      function startReplay() {
        if (replayTimer !== null || stopped) return;
        onStatus({state: 'degraded', label: 'REPLAY FALLBACK'});
        replayTimer = global.setInterval(() => {
          const previous = replayHistory[replayHistory.length - 1];
          replaySequence += 1;
          const next = nextFallbackCandle(previous, replaySequence);
          replayHistory = [previous, next];
          onCandle(next);
        }, Math.max(1000, intervalMilliseconds(interval) / 60));
      }

      function scheduleReconnect(openSocket) {
        if (stopped || reconnectTimer !== null) return;
        attempts += 1;
        if (runtime.mode === 'static' && attempts >= 3) startReplay();
        const delay = Math.min(30000, 1000 * (2 ** Math.min(attempts, 5)));
        onStatus({state: 'reconnecting', label: `RECONNECTING ${Math.round(delay / 1000)}s`});
        reconnectTimer = global.setTimeout(() => {
          reconnectTimer = null;
          openSocket();
        }, delay);
      }

      function openSocket() {
        if (stopped) return;
        const url = runtime.mode === 'backend'
          ? backendSocketUrl(runtime)
          : `${BINANCE_STREAM}${symbol.toLowerCase()}@kline_${interval}`;
        try {
          socket = new WebSocket(url);
        } catch (_) {
          onStatus({state: 'degraded', label: 'STREAM BLOCKED'});
          scheduleReconnect(openSocket);
          return;
        }
        socket.addEventListener('open', () => {
          attempts = 0;
          stopReplay();
          onStatus({state: 'streaming', label: runtime.mode === 'static' ? 'PUBLIC STREAM' : 'STREAMING'});
        });
        socket.addEventListener('message', (event) => {
          try {
            const payload = JSON.parse(event.data);
            const candle = runtime.mode === 'backend'
              ? (payload.type === 'candle' ? payload.data : null)
              : (payload.k ? normalizeBinanceStream(symbol, interval, payload) : null);
            if (candle) {
              if (runtime.mode === 'backend') onCandle(candle);
              else if (candle.symbol === symbol) onCandle(candle);
            }
          } catch (_) {
            onStatus({state: 'degraded', label: 'INVALID STREAM DATA'});
          }
        });
        socket.addEventListener('error', () => {
          onStatus({state: 'degraded', label: 'STREAM ERROR'});
        });
        socket.addEventListener('close', () => scheduleReconnect(openSocket));
      }

      openSocket();
      return function disconnect() {
        stopped = true;
        if (reconnectTimer !== null) global.clearTimeout(reconnectTimer);
        stopReplay();
        if (socket && socket.readyState < 2) socket.close();
      };
    }

    return Object.freeze({loadHistory, connect});
  }

  global.ObservatoryMarketClient = Object.freeze({create, fallbackHistory, nextFallbackCandle});
}(window));
