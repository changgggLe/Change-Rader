const {
  API_MODE,
  LOCAL_API_BASE_URL,
  CLOUDBASE_ENV_ID,
  CLOUDBASE_SERVICE_NAME,
} = require('../config/env');

const USER_KEY_STORAGE = 'changeRadarUserKey';

function getUserKey() {
  let userKey = wx.getStorageSync(USER_KEY_STORAGE);
  if (!userKey) {
    userKey = `wx_${Date.now()}_${Math.random().toString(36).slice(2, 12)}`;
    wx.setStorageSync(USER_KEY_STORAGE, userKey);
  }
  return userKey;
}

function parseResponse(response, resolve, reject) {
  if (response.statusCode >= 200 && response.statusCode < 300) {
    resolve(response.data);
    return;
  }
  const message = response.data && response.data.detail ? response.data.detail : `API ${response.statusCode}`;
  reject(new Error(message));
}

function localRequest(path, options = {}) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${LOCAL_API_BASE_URL}${path}`,
      method: options.method || 'GET',
      data: options.data,
      header: {
        'X-User-Key': getUserKey(),
        ...(options.header || {}),
      },
      timeout: 15000,
      success(response) {
        parseResponse(response, resolve, reject);
      },
      fail(error) {
        reject(error);
      },
    });
  });
}

function cloudbaseRequest(path, options = {}) {
  return new Promise((resolve, reject) => {
    wx.cloud.callContainer({
      config: { env: CLOUDBASE_ENV_ID },
      path: `/api/v1${path}`,
      method: options.method || 'GET',
      data: options.data,
      header: {
        'X-WX-SERVICE': CLOUDBASE_SERVICE_NAME,
        'Content-Type': 'application/json',
        ...(options.header || {}),
      },
      timeout: 15000,
      success(response) {
        parseResponse(response, resolve, reject);
      },
      fail(error) {
        reject(error);
      },
    });
  });
}

function request(path, options = {}) {
  const useCloudBase = API_MODE === 'cloudbase'
    || (API_MODE === 'auto' && Boolean(CLOUDBASE_ENV_ID));
  return useCloudBase ? cloudbaseRequest(path, options) : localRequest(path, options);
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
