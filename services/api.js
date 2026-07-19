const { API_BASE_URL } = require('../config/env');

function request(path, options = {}) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${API_BASE_URL}${path}`,
      method: options.method || 'GET',
      data: options.data,
      timeout: 5000,
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(response.data);
          return;
        }
        reject(new Error(`API ${response.statusCode}`));
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
