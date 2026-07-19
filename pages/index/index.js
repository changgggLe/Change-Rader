const api = require('../../services/api');

Page({
  data: {
    view: 'home',
    marketStatus: 'CLOSED',
    marketState: '正在连接后端',
    marketSectionTitle: '异动结果',
    marketSectionHint: '正在判断交易时段',
    refreshLabel: '等待接口响应',
    dataSourceLabel: '后端 Mock',
    loading: true,
    refreshing: false,
    loadError: '',
    stocks: [],
    watchlistStocks: [],
    watchSymbolInput: '',
    watchlistLoading: false,
    addingWatch: false,
    selectedStock: null,
    stats: { triggered: 0, near: 0, severe: 0 },
    wholeMarketAlert: true,
    notices: [
      { time: '10:00', title: '盘中异动摘要', state: '7 只', sent: true },
      { time: '11:00', title: '盘中异动摘要', state: '待发送', sent: false },
      { time: '14:00', title: '盘中异动摘要', state: '待发送', sent: false },
      { time: '15:30', title: '盘后异动汇总', state: '待发送', sent: false },
    ],
  },

  onLoad() {
    this._initialized = true;
    this.loadBackendData();
  },

  onShow() {
    if (this._initialized) this.loadBackendData();
  },

  onHide() {
    this.stopAutoRefresh();
  },

  onUnload() {
    this.stopAutoRefresh();
  },

  onPullDownRefresh() {
    if (this.data.marketStatus === 'CLOSED') {
      wx.stopPullDownRefresh();
      wx.showToast({ title: '非交易时间段，行情不刷新', icon: 'none' });
      return;
    }
    this.loadBackendData().finally(() => wx.stopPullDownRefresh());
  },

  loadBackendData() {
    if (this._loadingPromise) return this._loadingPromise;
    const firstLoading = this.data.stocks.length === 0;
    this.setData({ loading: firstLoading, refreshing: !firstLoading, loadError: '' });
    wx.showLoading({ title: firstLoading ? '加载中' : '更新中', mask: false });
    this._loadingPromise = api.getMarketStatus()
      .then((market) => {
        const requestMode = market.marketStatus === 'TRADING' ? 'intraday' : 'after';
        return api.getAnomalies(requestMode).then((anomalies) => ({ market, anomalies, requestMode }));
      })
      .then(({ market, anomalies }) => {
        const stocks = anomalies.items.map(this.adaptApiStock);
        const sourceLabels = {
          DATABASE_DEMO: '数据库演示数据',
          PUBLIC_DATA_SYNCING: '真实行情首次同步中',
          SINA_PUBLIC_PARTIAL: '新浪财经真实行情（候选池）',
        };
        const sourceLabel = sourceLabels[market.source] || market.source;
        const trading = market.marketStatus === 'TRADING';
        this.setData({
          stocks,
          stats: this.calculateStats(stocks),
          marketStatus: market.marketStatus,
          marketState: trading ? '交易时间段' : '非交易时间段',
          marketSectionTitle: trading ? '交易时间段异动动态' : '非交易时间段异动结果',
          marketSectionHint: trading ? '每 15 秒自动刷新' : '非交易时间段不刷新行情',
          refreshLabel: `${sourceLabel} · 刚刚更新`,
          dataSourceLabel: sourceLabel,
          loading: false,
          refreshing: false,
          loadError: '',
        }, () => this.configureAutoRefresh());
      })
      .catch(() => {
        this.stopAutoRefresh();
        this.setData({
          stocks: [],
          stats: { triggered: 0, near: 0, severe: 0 },
          loading: false,
          refreshing: false,
          loadError: '无法连接后端，请确认 FastAPI 已在 8000 端口启动',
          marketState: '后端未连接',
          refreshLabel: '点击重试',
        });
      })
      .finally(() => {
        wx.hideLoading();
        this._loadingPromise = null;
      });
    return this._loadingPromise;
  },

  configureAutoRefresh() {
    this.stopAutoRefresh();
    if (this.data.marketStatus !== 'TRADING') {
      this._boundaryTimer = setTimeout(() => this.loadBackendData(), this.getNextMarketBoundaryDelay());
      return;
    }
    this._pollTimer = setInterval(() => {
      if (this.data.view === 'home') this.loadBackendData();
    }, 15000);
  },

  stopAutoRefresh() {
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
    if (this._boundaryTimer) {
      clearTimeout(this._boundaryTimer);
      this._boundaryTimer = null;
    }
  },

  getNextMarketBoundaryDelay() {
    const hourMs = 60 * 60 * 1000;
    const nowMs = Date.now();
    const beijingNow = new Date(nowMs + 8 * hourMs);
    const year = beijingNow.getUTCFullYear();
    const month = beijingNow.getUTCMonth();
    const dayOfMonth = beijingNow.getUTCDate();
    const dayOfWeek = beijingNow.getUTCDay();
    const boundaries = [[9, 15, 2], [11, 30, 2], [13, 0, 2], [15, 0, 2]];

    for (let offset = 0; offset < 8; offset += 1) {
      const candidateWeekday = (dayOfWeek + offset) % 7;
      if (candidateWeekday === 0 || candidateWeekday === 6) continue;
      for (const [hour, minute, second] of boundaries) {
        const candidate = Date.UTC(year, month, dayOfMonth + offset, hour, minute, second) - 8 * hourMs;
        if (candidate > nowMs + 500) return Math.max(1000, candidate - nowMs);
      }
    }
    return hourMs;
  },

  onRetry() {
    this.loadBackendData();
  },

  calculateStats(stocks) {
    return stocks.reduce((stats, stock) => {
      if (stock.statusType === 'triggered') stats.triggered += 1;
      if (stock.statusType === 'near') stats.near += 1;
      if (stock.statusType === 'severe') stats.severe += 1;
      return stats;
    }, { triggered: 0, near: 0, severe: 0 });
  },

  adaptApiStock(item) {
    const metrics = item.metrics || [];
    const metric3 = metrics[0] || {};
    const metric10 = metrics[1] || {};
    const metric30 = metrics[2] || {};
    return {
      id: item.symbol,
      name: item.name,
      codeLabel: `${item.symbol} · ${item.boardLabel}`,
      board: item.boardLabel,
      price: item.lastPrice,
      dayChange: item.dayChange,
      displayChange: item.displayChange,
      status: item.statusLabel,
      statusType: item.statusType,
      ruleNote: item.ruleNote,
      r3: `${metric3.current || '--'} / ${metric3.threshold || '--'}`,
      r3Width: metric3.progress || 0,
      r10: `${metric10.current || '--'} / ${metric10.threshold || '--'}`,
      r10Width: metric10.progress || 0,
      r30: `${metric30.current || '--'} / ${metric30.threshold || '--'}`,
      r30Width: metric30.progress || 0,
      stockReturn: item.stockReturn,
      indexName: item.benchmarkName,
      indexReturn: item.benchmarkReturn,
      deviation: item.deviation,
      watched: item.watched,
      alerted: item.alerted,
    };
  },

  onStockTap(event) {
    const id = event.currentTarget.dataset.id;
    const selectedStock = this.data.stocks.find((stock) => stock.id === id)
      || this.data.watchlistStocks.find((stock) => stock.id === id);
    if (!selectedStock) return;
    this._detailOrigin = this.data.view;
    this.setData({ view: 'detail', selectedStock });
    api.getSecurity(id)
      .then((item) => this.setData({ selectedStock: this.adaptApiStock(item) }))
      .catch(() => wx.showToast({ title: '详情接口请求失败', icon: 'none' }));
  },

  onBack() {
    const view = this._detailOrigin || 'home';
    this._detailOrigin = null;
    this.setData({ view });
  },

  onNavTap(event) {
    const view = event.currentTarget.dataset.view;
    this.setData({ view });
    if (view === 'watch') this.loadWatchlist();
    if (view === 'home') this.loadBackendData();
  },

  loadWatchlist() {
    this.setData({ watchlistLoading: true });
    return api.getWatchlist()
      .then((response) => this.setData({ watchlistStocks: response.items.map(this.adaptApiStock) }))
      .catch(() => wx.showToast({ title: '自选接口请求失败', icon: 'none' }))
      .finally(() => this.setData({ watchlistLoading: false }));
  },

  onWatchSymbolInput(event) {
    this.setData({ watchSymbolInput: String(event.detail.value || '').replace(/\D/g, '').slice(0, 6) });
  },

  onAddWatch() {
    const symbol = this.data.watchSymbolInput.trim();
    if (!/^\d{6}$/.test(symbol)) {
      wx.showToast({ title: '请输入六位股票代码', icon: 'none' });
      return;
    }
    if (this.data.addingWatch) return;
    this.setData({ addingWatch: true });
    wx.showLoading({ title: '添加中', mask: true });
    api.addWatch(symbol)
      .then((response) => {
        this.setData({
          watchSymbolInput: '',
          watchlistStocks: response.items.map(this.adaptApiStock),
        });
        wx.showToast({ title: '已加入自选', icon: 'success' });
      })
      .catch((error) => wx.showToast({ title: error.message || '股票代码不存在', icon: 'none' }))
      .finally(() => {
        this.setData({ addingWatch: false });
        wx.hideLoading();
      });
  },

  onToggleWatch() {
    this.updateSelectedStock('watched');
  },

  onToggleAlert() {
    this.updateSelectedStock('alerted');
  },

  updateSelectedStock(field) {
    const id = this.data.selectedStock.id;
    const enabled = !this.data.selectedStock[field];
    const operation = field === 'watched'
      ? (enabled ? api.addWatch(id) : api.removeWatch(id))
      : api.updateAlert(id, enabled);
    operation
      .then(() => {
        const stocks = this.data.stocks.map((stock) => (
          stock.id === id ? { ...stock, [field]: enabled } : stock
        ));
        this.setData({
          stocks,
          selectedStock: { ...this.data.selectedStock, [field]: enabled },
        });
        if (field === 'watched') this.loadWatchlist();
        wx.showToast({ title: enabled ? '已开启' : '已关闭', icon: 'none' });
      })
      .catch(() => wx.showToast({ title: '后端保存失败', icon: 'none' }));
  },

  onWholeMarketAlertChange(event) {
    this.setData({ wholeMarketAlert: event.detail.value });
  },
});
