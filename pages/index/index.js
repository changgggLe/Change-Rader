const STOCKS = [
  {
    id: '603018',
    name: '华星科技',
    codeLabel: '603018 · 沪市主板',
    board: '沪市主板',
    price: '18.46',
    dayChange: '+9.98%',
    displayChange: '+22.31%',
    status: '系统触发',
    statusType: 'triggered',
    ruleNote: '3 日偏离值超过 20%',
    r3: '22.31% / 20%',
    r3Width: 100,
    r10: '48.20% / 100%',
    r10Width: 48,
    r30: '76.44% / 200%',
    r30Width: 38,
    stockReturn: '+24.08%',
    indexName: '上证指数',
    indexReturn: '+1.77%',
    deviation: '+22.31%',
    watched: false,
    alerted: false,
  },
  {
    id: '301219',
    name: '腾越新材',
    codeLabel: '301219 · 创业板',
    board: '创业板',
    price: '42.80',
    dayChange: '+15.36%',
    displayChange: '+103.42%',
    status: '严重异动',
    statusType: 'severe',
    ruleNote: '10 日偏离值超过 100%',
    r3: '31.20% / 30%',
    r3Width: 100,
    r10: '103.42% / 100%',
    r10Width: 100,
    r30: '164.50% / 200%',
    r30Width: 82,
    stockReturn: '+108.31%',
    indexName: '深证成指',
    indexReturn: '+4.89%',
    deviation: '+103.42%',
    watched: false,
    alerted: false,
  },
  {
    id: '688256',
    name: '云帆芯片',
    codeLabel: '688256 · 科创板',
    board: '科创板',
    price: '67.12',
    dayChange: '+18.66%',
    displayChange: '+18.66%',
    status: '严重异动',
    statusType: 'severe',
    ruleNote: '10 日内第 3 次同向异动',
    r3: '34.72% / 30%',
    r3Width: 100,
    r10: '第 3 次 / 3 次',
    r10Width: 100,
    r30: '128.30% / 200%',
    r30Width: 64,
    stockReturn: '+37.16%',
    indexName: '上证指数',
    indexReturn: '+2.44%',
    deviation: '+34.72%',
    watched: true,
    alerted: true,
  },
  {
    id: '002517',
    name: '东方智能',
    codeLabel: '002517 · 深市主板',
    board: '深市主板',
    price: '12.86',
    dayChange: '+9.21%',
    displayChange: '+9.21%',
    status: '接近异动',
    statusType: 'near',
    ruleNote: '今日涨停即可触发 3 日规则',
    r3: '19.21% / 20%',
    r3Width: 96,
    r10: '61.80% / 100%',
    r10Width: 62,
    r30: '96.40% / 200%',
    r30Width: 48,
    stockReturn: '+21.63%',
    indexName: '深证成指',
    indexReturn: '+2.42%',
    deviation: '+19.21%',
    watched: true,
    alerted: false,
  },
];

Page({
  data: {
    view: 'home',
    mode: 'intraday',
    marketState: '盘中监测中',
    refreshLabel: '12 秒前更新',
    stocks: STOCKS,
    selectedStock: STOCKS[0],
    wholeMarketAlert: true,
    notices: [
      { time: '10:00', title: '盘中异动摘要', state: '7 只', sent: true },
      { time: '11:00', title: '盘中异动摘要', state: '待发送', sent: false },
      { time: '14:00', title: '盘中异动摘要', state: '待发送', sent: false },
      { time: '15:30', title: '盘后异动汇总', state: '待发送', sent: false },
    ],
  },

  onPullDownRefresh() {
    this.setData({ refreshLabel: '刚刚更新' });
    setTimeout(() => wx.stopPullDownRefresh(), 350);
  },

  onModeTap(event) {
    const mode = event.currentTarget.dataset.mode;
    const intraday = mode === 'intraday';
    this.setData({
      mode,
      marketState: intraday ? '盘中监测中' : '盘后快照',
      refreshLabel: intraday ? '12 秒前更新' : '15:30 已生成',
    });
  },

  onStockTap(event) {
    const id = event.currentTarget.dataset.id;
    const selectedStock = this.data.stocks.find((stock) => stock.id === id);
    if (!selectedStock) return;
    this.setData({ view: 'detail', selectedStock });
  },

  onBack() {
    this.setData({ view: 'home' });
  },

  onNavTap(event) {
    this.setData({ view: event.currentTarget.dataset.view });
  },

  onToggleWatch() {
    this.updateSelectedStock('watched');
  },

  onToggleAlert() {
    this.updateSelectedStock('alerted');
  },

  updateSelectedStock(field) {
    const id = this.data.selectedStock.id;
    const stocks = this.data.stocks.map((stock) => (
      stock.id === id ? { ...stock, [field]: !stock[field] } : stock
    ));
    const selectedStock = stocks.find((stock) => stock.id === id);
    this.setData({ stocks, selectedStock });
    wx.showToast({
      title: selectedStock[field] ? '已开启' : '已关闭',
      icon: 'none',
    });
  },

  onWholeMarketAlertChange(event) {
    this.setData({ wholeMarketAlert: event.detail.value });
  },
});
