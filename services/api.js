const { API_BASE_URL } = require('../config/env');

const USER_KEY_STORAGE = 'changeRadarUserKey';

function getUserKey() {
  let userKey = wx.getStorageSync(USER_KEY_STORAGE);
  if (!userKey) {
    userKey = `wx_${Date.now()}_${Math.random().toString(36).slice(2, 12)}`;
    wx.setStorageSync(USER_KEY_STORAGE, userKey);
  }
  return userKey;
}

function request(path, options = {}) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${API_BASE_URL}${path}`,
      method: options.method || 'GET',
      data: options.data,
      header: {
        'X-User-Key': getUserKey(),
        ...(options.header || {}),
      },
      timeout: 5000,
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(response.data);
          return;
        }
        const message = response.data && response.data.detail ? response.data.detail : `API ${response.statusCode}`;
        reject(new Error(message));
      },
      fail(error) {
        reject(error);
      },
    });
  });
}

module.exports = {
  getMarketStatus: () => request('/market/status'),
  getAnomalies: (mode) => request(mode === 'after' ? '/anomalies/confirmed' : '/anomalies/intraday'),
  getSecurity: (symbol) => request(`/securities/${symbol}`),
  getWatchlist: () => request('/watchlist'),
  addWatch: (symbol) => request(`/watchlist/${symbol}`, { method: 'POST' }),
  removeWatch: (symbol) => request(`/watchlist/${symbol}`, { method: 'DELETE' }),
  updateAlert: (symbol, enabled) => request(`/alerts/${symbol}`, { method: 'PUT', data: { enabled } }),
};
