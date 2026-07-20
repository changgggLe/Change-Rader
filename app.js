const { CLOUDBASE_ENV_ID } = require('./config/env');

App({
  onLaunch() {
    if (CLOUDBASE_ENV_ID && wx.cloud) {
      wx.cloud.init({ env: CLOUDBASE_ENV_ID });
    }
  },

  globalData: {
    appName: '异动偏离预警器',
    refreshInterval: 15000,
  },
});
