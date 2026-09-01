(function defineNativeMarketChart(global) {
  'use strict';

  // Lightweight Charts remains the preferred renderer. This module is a
  // first-party fallback for environments where the external CDN is blocked.
  if (global.LightweightCharts) return;

  const PERIODS = Object.freeze({
    '1m': Object.freeze({label: '分时', timeframe: '1Min', limit: 300}),
    '1Day': Object.freeze({label: '日K', timeframe: '1Day', limit: 260}),
    '1Week': Object.freeze({label: '周K', timeframe: '1Week', limit: 260}),
    '1Month': Object.freeze({label: '月K', timeframe: '1Month', limit: 120}),
  });
  const COVERAGE_LABELS = Object.freeze({
    'single-exchange': 'IEX · 单交易所',
    'consolidated-us-market': 'SIP · 全美市场汇总',
    'consolidated-us-market-delayed': 'SIP · 延迟汇总',
    'runtime-feed': '本地已验证实时存储',
  });
  const SVG_NS = 'http://www.w3.org/2000/svg';

  function create() {
    const runtime = global.ObservatoryRuntime.resolve(global.OBSERVATORY_CONFIG);
    const backend = global.ObservatoryBackendActions?.create(runtime) || null;
    const marketClient = global.ObservatoryMarketClient.create(runtime);
    let currentSymbol = runtime.market.symbol;
    let activePeriod = '1m';
    let activeCandles = [];
    let lastPayload = null;
    let disconnect = null;

    const byId = (id) => document.getElementById(id);
    const money = (value) => Number(value).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });

    function movingAverage(items, length) {
      const output = [];
      let sum = 0;
      const queue = [];
      for (let index = 0; index < items.length; index += 1) {
        const value = Number(items[index].close);
        queue.push(value);
        sum += value;
        if (queue.length > length) sum -= queue.shift();
        if (queue.length === length) output.push({index, value: sum / length});
      }
      return output;
    }

    function localLevels(items, width = 2) {
      if (!items.length) return {support: null, resistance: null};
      if (items.length < width * 2 + 1) {
        return {
          support: Math.min(...items.map((item) => Number(item.low))),
          resistance: Math.max(...items.map((item) => Number(item.high))),
        };
      }
      const latest = Number(items.at(-1).close);
      const lows = [];
      const highs = [];
      for (let index = width; index < items.length - width; index += 1) {
        const item = items[index];
        const neighbors = [
          ...items.slice(index - width, index),
          ...items.slice(index + 1, index + width + 1),
        ];
        if (neighbors.every((candidate) => Number(item.low) < Number(candidate.low))) {
          lows.push(Number(item.low));
        }
        if (neighbors.every((candidate) => Number(item.high) > Number(candidate.high))) {
          highs.push(Number(item.high));
        }
      }
      const supportCandidates = lows.filter((value) => value <= latest);
      const resistanceCandidates = highs.filter((value) => value >= latest);
      return {
        support: supportCandidates.length
          ? Math.max(...supportCandidates)
          : Math.min(...items.map((item) => Number(item.low))),
        resistance: resistanceCandidates.length
          ? Math.min(...resistanceCandidates)
          : Math.max(...items.map((item) => Number(item.high))),
      };
    }

    function element(name, attrs = {}) {
      const node = document.createElementNS(SVG_NS, name);
      for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
      return node;
    }

    function setLoading(value) {
      const node = byId('market-chart-loading');
      if (node) node.hidden = !value;
    }

    function setEmpty(message = '') {
      const node = byId('market-chart-empty');
      if (!node) return;
      node.textContent = message;
      node.hidden = !message;
    }

    function setPeriodButtons() {
      document.querySelectorAll('[data-market-period]').forEach((button) => {
        const selected = button.dataset.marketPeriod === activePeriod;
        button.classList.toggle('active', selected);
        button.setAttribute('aria-pressed', String(selected));
      });
      const title = byId('market-chart-title');
      if (title) title.textContent = `${currentSymbol} · ${PERIODS[activePeriod].label}`;
    }

    function setSource(payload) {
      const node = byId('market-chart-source');
      if (!node) return;
      const coverage = COVERAGE_LABELS[payload?.coverage] || payload?.coverage || '覆盖未知';
      node.textContent = `${payload?.source || '来源未知'} · ${coverage}`;
    }

    function renderLevelLabels(levels) {
      const support = byId('market-support-value');
      const resistance = byId('market-resistance-value');
      if (support) support.textContent = levels?.support == null ? '—' : `$${money(levels.support)}`;
      if (resistance) resistance.textContent = levels?.resistance == null ? '—' : `$${money(levels.resistance)}`;
    }

    function pathFor(points, xFor, yFor) {
      return points.map((point, index) => `${index ? 'L' : 'M'} ${xFor(point)} ${yFor(point.value)}`).join(' ');
    }

    function renderNativeChart(items, payload = null) {
      const container = byId('advanced-market-chart');
      if (!container) return;
      container.replaceChildren();
      if (!items.length) {
        setEmpty('无可验证历史数据');
        return;
      }
      setEmpty('');

      const width = Math.max(container.clientWidth || 900, 420);
      const height = Math.max(container.clientHeight || 428, 300);
      const left = 12;
      const right = 64;
      const top = 18;
      const priceBottom = Math.round(height * 0.76);
      const volumeTop = Math.round(height * 0.80);
      const volumeBottom = height - 22;
      const plotWidth = Math.max(width - left - right, 100);
      const priceHeight = Math.max(priceBottom - top, 100);

      const visible = items.slice(-Math.max(1, Math.floor(plotWidth / 4)));
      const lows = visible.map((item) => Number(item.low));
      const highs = visible.map((item) => Number(item.high));
      const minPrice = Math.min(...lows);
      const maxPrice = Math.max(...highs);
      const priceRange = Math.max(maxPrice - minPrice, Math.max(maxPrice * 0.001, 0.01));
      const maxVolume = Math.max(...visible.map((item) => Number(item.volume || 0)), 1);
      const step = plotWidth / Math.max(visible.length, 1);
      const candleWidth = Math.max(1, Math.min(step * 0.62, 9));
      const yPrice = (price) => top + ((maxPrice - Number(price)) / priceRange) * priceHeight;
      const xAt = (index) => left + step * index + step / 2;

      const svg = element('svg', {
        viewBox: `0 0 ${width} ${height}`,
        width: '100%',
        height: '100%',
        role: 'img',
        'aria-label': `${currentSymbol} ${PERIODS[activePeriod].label} 本地K线图`,
      });

      for (let row = 0; row <= 4; row += 1) {
        const y = top + (priceHeight * row) / 4;
        svg.appendChild(element('line', {
          x1: left,
          x2: width - right,
          y1: y,
          y2: y,
          stroke: 'rgba(145,164,196,.10)',
          'stroke-width': 1,
        }));
        const label = element('text', {
          x: width - right + 8,
          y: y + 4,
          fill: '#8795aa',
          'font-size': 10,
        });
        label.textContent = money(maxPrice - (priceRange * row) / 4);
        svg.appendChild(label);
      }

      visible.forEach((item, index) => {
        const open = Number(item.open);
        const close = Number(item.close);
        const high = Number(item.high);
        const low = Number(item.low);
        const volume = Number(item.volume || 0);
        const rising = close >= open;
        const color = rising ? '#46d99a' : '#ff6474';
        const x = xAt(index);
        svg.appendChild(element('line', {
          x1: x,
          x2: x,
          y1: yPrice(high),
          y2: yPrice(low),
          stroke: color,
          'stroke-width': 1,
        }));
        const bodyTop = Math.min(yPrice(open), yPrice(close));
        const bodyHeight = Math.max(Math.abs(yPrice(open) - yPrice(close)), 1);
        svg.appendChild(element('rect', {
          x: x - candleWidth / 2,
          y: bodyTop,
          width: candleWidth,
          height: bodyHeight,
          fill: color,
          rx: 0.5,
        }));
        const volumeHeight = ((volume / maxVolume) * Math.max(volumeBottom - volumeTop, 1));
        svg.appendChild(element('rect', {
          x: x - candleWidth / 2,
          y: volumeBottom - volumeHeight,
          width: candleWidth,
          height: volumeHeight,
          fill: rising ? 'rgba(70,217,154,.36)' : 'rgba(255,100,116,.32)',
        }));
      });

      const offset = items.length - visible.length;
      const ma20 = movingAverage(items, 20)
        .filter((point) => point.index >= offset)
        .map((point) => ({...point, localIndex: point.index - offset}));
      const ma60 = movingAverage(items, 60)
        .filter((point) => point.index >= offset)
        .map((point) => ({...point, localIndex: point.index - offset}));
      if (ma20.length) {
        svg.appendChild(element('path', {
          d: pathFor(ma20, (point) => xAt(point.localIndex), yPrice),
          fill: 'none',
          stroke: '#7fa5ff',
          'stroke-width': 1.35,
        }));
      }
      if (ma60.length) {
        svg.appendChild(element('path', {
          d: pathFor(ma60, (point) => xAt(point.localIndex), yPrice),
          fill: 'none',
          stroke: '#d3a4ff',
          'stroke-width': 1.35,
        }));
      }

      const levels = payload?.levels || localLevels(items);
      for (const [kind, price, color] of [
        ['支撑', levels?.support, '#46d99a'],
        ['压力', levels?.resistance, '#ffb454'],
      ]) {
        if (price == null) continue;
        const y = yPrice(price);
        svg.appendChild(element('line', {
          x1: left,
          x2: width - right,
          y1: y,
          y2: y,
          stroke: color,
          'stroke-width': 1,
          'stroke-dasharray': '5 5',
        }));
        const label = element('text', {
          x: left + 5,
          y: Math.max(y - 4, 10),
          fill: color,
          'font-size': 10,
        });
        label.textContent = `${kind} ${money(price)}`;
        svg.appendChild(label);
      }

      container.appendChild(svg);
      renderLevelLabels(levels);
      const last = items.at(-1);
      const price = byId('market-chart-last-price');
      if (price) price.textContent = `$${money(last.close)}`;
      setSource(payload || {
        source: last.source,
        coverage: activePeriod === '1m' ? 'runtime-feed' : '覆盖未知',
      });
      const streamState = byId('market-chart-stream-state');
      if (streamState) {
        streamState.textContent = '实时图表本地渲染';
        streamState.className = 'market-stream-state safe';
      }
    }

    async function loadMarketHistory(period) {
      const config = PERIODS[period];
      if (!config) return;
      if (runtime.mode === 'backend' && backend) {
        return backend.loadMarketHistory(currentSymbol, config.timeframe, config.limit);
      }
      if (period === '1m' && currentSymbol === runtime.market.symbol) {
        const candles = await marketClient.loadHistory(currentSymbol, '1m');
        return {
          symbol: currentSymbol,
          timeframe: '1Min',
          source: candles.at(-1)?.source || 'public-observe',
          coverage: 'public-observe',
          candles,
          levels: localLevels(candles),
        };
      }
      throw new Error('静态预览没有可验证的美股历史行情源');
    }

    async function loadPeriod(period) {
      if (!PERIODS[period]) return;
      activePeriod = period;
      setPeriodButtons();
      setLoading(true);
      setEmpty('');
      try {
        const payload = await loadMarketHistory(period);
        lastPayload = payload;
        activeCandles = payload?.candles || [];
        renderNativeChart(activeCandles, payload);
      } catch (error) {
        console.error('native market chart load failed', error);
        activeCandles = [];
        lastPayload = null;
        const message = String(error?.message || error);
        setSource({source: '历史行情不可用', coverage: '未验证'});
        setEmpty(message.includes('503')
          ? '无可验证历史数据：请在本机 .env 配置 Alpaca 市场数据凭据'
          : `无可验证历史数据：${message}`);
      } finally {
        setLoading(false);
      }
    }

    function updateRealtimeCandle(candle) {
      if (activePeriod !== '1m' || candle.symbol !== currentSymbol) return;
      const index = activeCandles.findIndex((item) => item.open_time === candle.open_time);
      if (index >= 0) activeCandles[index] = candle;
      else activeCandles.push(candle);
      activeCandles = activeCandles.slice(-PERIODS['1m'].limit);
      renderNativeChart(activeCandles, lastPayload || {
        source: candle.source,
        coverage: 'runtime-feed',
        levels: localLevels(activeCandles),
      });
    }

    function bindControls() {
      document.querySelectorAll('[data-market-period]').forEach((button) => {
        button.addEventListener('click', () => loadPeriod(button.dataset.marketPeriod));
      });
    }

    function start() {
      const container = byId('advanced-market-chart');
      if (!container) return;
      bindControls();
      setPeriodButtons();
      loadPeriod(activePeriod);
      disconnect = marketClient.connect(updateRealtimeCandle, () => {});
    }

    function stop() {
      if (disconnect) disconnect();
      disconnect = null;
    }

    return Object.freeze({start, stop, loadPeriod});
  }

  global.ObservatoryNativeMarketChart = Object.freeze({create});
  global.addEventListener('DOMContentLoaded', () => {
    const controller = create();
    global.__observatoryNativeMarketChart = controller;
    controller.start();
  });
}(window));
