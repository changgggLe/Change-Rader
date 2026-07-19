const api = require('../../services/api');

Page({
  data: {
    view: 'home',
    mode: 'intraday',
    marketState: '正在连接后端',
    refreshLabel: '等待接口响应',
    dataSourceLabel: '后端 Mock',
    loading: true,
    loadError: '',
    stocks: [],
    watchlistStocks: [],
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
    this.loadBackendData();
    this.startPolling();
    this._initialized = true;
  },

  onShow() {
    if (this._initialized) this.startPolling();
  },

  onHide() {
    this.stopPolling();
  },

  onUnload() {
    this.stopPolling();
  },

  onPullDownRefresh() {
    this.loadBackendData().finally(() => wx.stopPullDownRefresh());
  },

  loadBackendData() {
    this.setData({ loading: true, loadError: '' });
    return Promise.all([api.getMarketStatus(), api.getAnomalies(this.data.mode)])
      .then(([market, anomalies]) => {
        const stocks = anomalies.items.map(this.adaptApiStock);
        this.setData({
          stocks,
          stats: this.calculateStats(stocks),
          marketState: this.data.mode === 'intraday' ? '盘中监测中' : '盘后快照',
          refreshLabel: `${market.source === 'MOCK' ? 'Mock' : market.source} · 刚刚更新`,
          dataSourceLabel: market.source === 'MOCK' ? '后端 Mock' : market.source,
          loading: false,
          loadError: '',
        });
      })
      .catch(() => {
        this.setData({
          stocks: [],
          stats: { triggered: 0, near: 0, severe: 0 },
          loading: false,
          loadError: '无法连接后端，请确认 FastAPI 已在 8000 端口启动',
          marketState: '后端未连接',
          refreshLabel: '点击重试',
        });
      });
  },

  startPolling() {
    this.stopPolling();
    this._pollTimer = setInterval(() => {
      if (this.data.view === 'home') this.loadBackendData();
    }, 15000);
  },

  stopPolling() {
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
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

  onModeTap(event) {
    const mode = event.currentTarget.dataset.mode;
    const intraday = mode === 'intraday';
    this.setData({
      mode,
      marketState: intraday ? '盘中监测中' : '盘后快照',
      refreshLabel: intraday ? '12 秒前更新' : '15:30 已生成',
    }, () => this.loadBackendData());
  },

  onStockTap(event) {
    const id = event.currentTarget.dataset.id;
    const selectedStock = this.data.stocks.find((stock) => stock.id === id);
    if (!selectedStock) return;
    this.setData({ view: 'detail', selectedStock });
    api.getSecurity(id)
      .then((item) => this.setData({ selectedStock: this.adaptApiStock(item) }))
      .catch(() => wx.showToast({ title: '详情接口请求失败', icon: 'none' }));
  },

  onBack() {
    this.setData({ view: 'home' });
  },

  onNavTap(event) {
    const view = event.currentTarget.dataset.view;
    this.setData({ view });
    if (view === 'watch') this.loadWatchlist();
  },

  loadWatchlist() {
    return api.getWatchlist()
      .then((response) => this.setData({ watchlistStocks: response.items.map(this.adaptApiStock) }))
      .catch(() => wx.showToast({ title: '自选接口请求失败', icon: 'none' }));
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
