(function defineAdvancedMarketChart(global) {
  'use strict';

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

  function create() {
    const runtime = global.ObservatoryRuntime.resolve(global.OBSERVATORY_CONFIG);
    const backend = global.ObservatoryBackendActions?.create(runtime) || null;
    const marketClient = global.ObservatoryMarketClient.create(runtime);
    let chart = null;
    let candleSeries = null;
    let volumeSeries = null;
    let ma20Series = null;
    let ma60Series = null;
    let supportLine = null;
    let resistanceLine = null;
    let disconnect = null;
    let currentSymbol = runtime.market.symbol;
    let activePeriod = '1m';
    let activeCandles = [];

    const byId = (id) => document.getElementById(id);
    const money = (value) => Number(value).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });

    function candlePoint(item) {
      return {
        time: Math.floor(new Date(item.open_time).getTime() / 1000),
        open: Number(item.open),
        high: Number(item.high),
        low: Number(item.low),
        close: Number(item.close),
      };
    }

    function volumePoint(item) {
      return {
        time: Math.floor(new Date(item.open_time).getTime() / 1000),
        value: Number(item.volume || 0),
        color: Number(item.close) >= Number(item.open)
          ? 'rgba(71, 216, 153, .42)'
          : 'rgba(255, 102, 117, .38)',
      };
    }

    function movingAverage(items, length) {
      const points = [];
      let total = 0;
      const queue = [];
      for (const item of items) {
        const close = Number(item.close);
        queue.push(close);
        total += close;
        if (queue.length > length) total -= queue.shift();
        if (queue.length === length) {
          points.push({
            time: Math.floor(new Date(item.open_time).getTime() / 1000),
            value: total / length,
          });
        }
      }
      return points;
    }

    function localLevels(items, width = 2) {
      if (items.length < width * 2 + 1) return {support: null, resistance: null};
      const latest = Number(items[items.length - 1].close);
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
      const supports = lows.filter((value) => value <= latest);
      const resistances = highs.filter((value) => value >= latest);
      return {
        support: supports.length ? Math.max(...supports) : Math.min(...items.map((item) => Number(item.low))),
        resistance: resistances.length ? Math.min(...resistances) : Math.max(...items.map((item) => Number(item.high))),
      };
    }

    function clearPriceLines() {
      if (!candleSeries) return;
      if (supportLine) candleSeries.removePriceLine(supportLine);
      if (resistanceLine) candleSeries.removePriceLine(resistanceLine);
      supportLine = null;
      resistanceLine = null;
    }

    function renderLevels(levels) {
      clearPriceLines();
      if (levels?.support != null) {
        supportLine = candleSeries.createPriceLine({
          price: Number(levels.support),
          title: '算法支撑',
          lineWidth: 1,
          lineStyle: LightweightCharts.LineStyle.Dashed,
          axisLabelVisible: true,
        });
      }
      if (levels?.resistance != null) {
        resistanceLine = candleSeries.createPriceLine({
          price: Number(levels.resistance),
          title: '算法压力',
          lineWidth: 1,
          lineStyle: LightweightCharts.LineStyle.Dashed,
          axisLabelVisible: true,
        });
      }
      const support = byId('market-support-value');
      const resistance = byId('market-resistance-value');
      if (support) support.textContent = levels?.support == null ? '—' : `$${money(levels.support)}`;
      if (resistance) resistance.textContent = levels?.resistance == null ? '—' : `$${money(levels.resistance)}`;
    }

    function setEmpty(message = '') {
      const node = byId('market-chart-empty');
      if (!node) return;
      node.textContent = message;
      node.hidden = !message;
    }

    function setLoading(loading) {
      const node = byId('market-chart-loading');
      if (node) node.hidden = !loading;
    }

    function setSource(source, coverage) {
      const node = byId('market-chart-source');
      if (!node) return;
      const coverageText = COVERAGE_LABELS[coverage] || coverage || '覆盖未知';
      node.textContent = `${source || '来源未知'} · ${coverageText}`;
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

    function renderCandles(items, *, levels = null, source = null, coverage = null) {
      activeCandles = [...items];
      candleSeries.setData(items.map(candlePoint));
      volumeSeries.setData(items.map(volumePoint));
      ma20Series.setData(movingAverage(items, 20));
      ma60Series.setData(movingAverage(items, 60));
      renderLevels(levels || localLevels(items));
      setEmpty(items.length ? '' : '无可验证历史数据');
      if (items.length) {
        const last = items[items.length - 1];
        const price = byId('market-chart-last-price');
        if (price) price.textContent = `$${money(last.close)}`;
      }
      setSource(source || items.at(-1)?.source || '来源未知', coverage);
      chart.timeScale().fitContent();
    }

    async function loadVerifiedPeriod(period) {
      const config = PERIODS[period];
      if (runtime.mode === 'backend' && backend) {
        const payload = await backend.loadMarketHistory(
          currentSymbol,
          config.timeframe,
          config.limit,
        );
        renderCandles(payload.candles || [], {
          levels: payload.levels || null,
          source: payload.source,
          coverage: payload.coverage,
        });
        return;
      }
      if (period === '1m' && currentSymbol === runtime.market.symbol) {
        const candles = await marketClient.loadHistory(currentSymbol, '1m');
        renderCandles(candles, {
          source: candles.at(-1)?.source || 'public observe feed',
          coverage: 'public observe feed',
        });
        return;
      }
      throw new Error('无可验证历史数据：静态预览没有服务器端历史行情凭据');
    }

    async function loadPeriod(period) {
      if (!PERIODS[period]) return;
      activePeriod = period;
      setPeriodButtons();
      setLoading(true);
      setEmpty('');
      try {
        await loadVerifiedPeriod(period);
      } catch (error) {
        console.error('advanced market chart load failed', error);
        activeCandles = [];
        candleSeries.setData([]);
        volumeSeries.setData([]);
        ma20Series.setData([]);
        ma60Series.setData([]);
        clearPriceLines();
        setSource('历史行情不可用', '未验证');
        const message = String(error?.message || error);
        setEmpty(message.includes('503')
          ? '无可验证历史数据：请在本机 .env 配置可用的 Alpaca 市场数据凭据'
          : `无可验证历史数据：${message}`);
      } finally {
        setLoading(false);
      }
    }

    function updateRealtimeCandle(candle) {
      if (activePeriod !== '1m') return;
      if (candle.symbol !== currentSymbol) return;
      const index = activeCandles.findIndex((item) => item.open_time === candle.open_time);
      if (index >= 0) activeCandles[index] = candle;
      else activeCandles.push(candle);
      activeCandles = activeCandles.slice(-PERIODS['1m'].limit);
      candleSeries.update(candlePoint(candle));
      volumeSeries.update(volumePoint(candle));
      ma20Series.setData(movingAverage(activeCandles, 20));
      ma60Series.setData(movingAverage(activeCandles, 60));
      renderLevels(localLevels(activeCandles));
      const price = byId('market-chart-last-price');
      if (price) price.textContent = `$${money(candle.close)}`;
      setSource(candle.source, '实时 feed 覆盖见 Feed 状态');
      setEmpty('');
    }

    function updateConnection(status) {
      const node = byId('market-chart-stream-state');
      if (!node) return;
      node.textContent = status.state === 'streaming' ? '实时流已连接' : status.label;
      node.className = status.state === 'streaming' ? 'market-stream-state safe' : 'market-stream-state warning';
    }

    async function setSymbol(symbol) {
      const normalized = String(symbol || '').trim().toUpperCase();
      if (!normalized || normalized === currentSymbol) return;
      currentSymbol = normalized;
      await loadPeriod(activePeriod);
    }

    function bindControls() {
      document.querySelectorAll('[data-market-period]').forEach((button) => {
        button.addEventListener('click', () => loadPeriod(button.dataset.marketPeriod));
      });
      document.addEventListener('click', (event) => {
        const card = event.target.closest?.('.decision-card');
        if (!card) return;
        const symbol = card.querySelector('.symbol-name')?.textContent;
        if (symbol) queueMicrotask(() => setSymbol(symbol));
      });
    }

    function initChart() {
      const container = byId('advanced-market-chart');
      if (!container) return false;
      if (!global.LightweightCharts) {
        setEmpty('图表组件未加载；正在切换到本地图表渲染。');
        return false;
      }
      chart = LightweightCharts.createChart(container, {
        layout: {background: {color: 'transparent'}, textColor: '#8795aa'},
        grid: {
          vertLines: {color: 'rgba(145, 164, 196, .06)'},
          horzLines: {color: 'rgba(145, 164, 196, .06)'},
        },
        rightPriceScale: {borderColor: 'rgba(145, 164, 196, .12)'},
        timeScale: {
          borderColor: 'rgba(145, 164, 196, .12)',
          timeVisible: true,
          secondsVisible: false,
        },
        crosshair: {mode: LightweightCharts.CrosshairMode.Normal},
      });
      candleSeries = chart.addCandlestickSeries({
        upColor: '#46d99a',
        downColor: '#ff6474',
        borderVisible: false,
        wickUpColor: '#46d99a',
        wickDownColor: '#ff6474',
        priceScaleId: 'right',
      });
      volumeSeries = chart.addHistogramSeries({
        priceFormat: {type: 'volume'},
        priceScaleId: 'volume',
      });
      chart.priceScale('volume').applyOptions({
        scaleMargins: {top: 0.78, bottom: 0},
      });
      ma20Series = chart.addLineSeries({title: 'MA20', lineWidth: 1});
      ma60Series = chart.addLineSeries({title: 'MA60', lineWidth: 1});

      const resize = () => chart.applyOptions({
        width: container.clientWidth,
        height: container.clientHeight,
      });
      new ResizeObserver(resize).observe(container);
      resize();
      return true;
    }

    async function start() {
      if (!initChart()) return;
      bindControls();
      setPeriodButtons();
      await loadPeriod(activePeriod);
      disconnect = marketClient.connect(updateRealtimeCandle, updateConnection);
    }

    function stop() {
      if (disconnect) disconnect();
      disconnect = null;
    }

    return Object.freeze({start, stop, loadPeriod, setSymbol});
  }

  global.ObservatoryAdvancedMarketChart = Object.freeze({create});

  global.addEventListener('DOMContentLoaded', () => {
    const controller = create();
    global.__observatoryAdvancedMarketChart = controller;
    controller.start();
  });
}(window));
