# CloudBase MVP 上线手册

本项目采用以下 MVP 架构：

```text
微信小程序
  └─ wx.cloud.callContainer
      └─ CloudBase 云托管：deviation-alert-api
          ├─ FastAPI + SQLAlchemy + Alembic
          ├─ CloudBase MySQL（持久化）
          └─ 新浪/东方财富公开网页行情适配器
```

使用 `callContainer` 后，小程序不需要配置业务服务器域名。CloudBase 会把
`X-WX-OPENID` 和 `X-WX-APPID` 注入请求头，后端优先使用 OpenID 隔离自选股和提醒设置。

## 1. 创建并关联环境

1. 使用当前小程序 AppID 登录 CloudBase 控制台。
2. 创建一个云开发环境并记录环境 ID。
3. 将该环境与“异动偏离预警器”小程序关联。
4. 在数据库中开通 MySQL，并启用“直连服务”。
5. 为云托管和数据库启用同一私有网络，生产连接使用 MySQL 内网地址。

MVP 不单独部署 Redis，`CACHE_BACKEND` 使用 `memory`。当前用户量下足够，并能减少一个
需要运维和付费的服务。

## 2. 创建云托管服务

推荐配置：

| 配置 | 值 |
| --- | --- |
| 服务名 | `deviation-alert-api` |
| 代码目录 | 仓库中的 `backend` 文件夹 |
| Dockerfile | `backend/Dockerfile` |
| 服务端口 | `80` |
| CPU / 内存 | 0.5 核 / 1 GiB |
| 最小 / 最大实例 | 首次验证 `0 / 1`；盘中稳定采集使用 `1 / 1` |
| 健康检查路径 | `/health` |
| 公网访问 | 首次验证时开启；小程序验证后关闭 |

首次上线可以在 CloudBase 控制台选择“本地代码部署”，上传 `backend` 文件夹。也可以安装
CloudBase CLI 后执行：

```powershell
cd backend
tcb login
tcb cloudrun deploy -e <环境ID> -s deviation-alert-api --port 80
```

本地没有 Docker 不影响云端从 Dockerfile 构建。

## 3. 配置环境变量

在云托管服务版本配置中填写：

```dotenv
APP_ENV=production
DATABASE_URL=mysql+pymysql://<用户名>:<URL编码后的密码>@<MySQL内网地址>:3306/<数据库名>?charset=utf8mb4
CACHE_BACKEND=memory
AUTO_CREATE_TABLES=false
SEED_DEMO_DATA=true
INTERNAL_USER_KEY=internal-demo
WECHAT_APPID=<小程序AppID>
REQUIRE_WECHAT_IDENTITY=false
MARKET_DATA_PROVIDER=sina
MARKET_SYNC_INTERVAL_SECONDS=15
MARKET_CANDIDATE_LIMIT_PER_BOARD=20
MARKET_HTTP_TIMEOUT_SECONDS=12
MARKET_HTTP_USE_ENVIRONMENT_PROXY=false
```

说明：

- 第一次部署保持 `REQUIRE_WECHAT_IDENTITY=false`，方便通过公网域名检查接口。
- `SEED_DEMO_DATA=true` 仅用于冷启动占位；真实行情同步完成后会自动删除占位事件。
- 如果新浪接口在云端不可达，只需把 `MARKET_DATA_PROVIDER` 改为 `eastmoney` 后发布新版本。
- 数据库密码如果含有 `@`、`:`、`/`、`#` 等字符，必须进行 URL 编码。
- 密码只能配置在 CloudBase 环境变量中，不得写入 Git。

容器启动时会先执行 `alembic upgrade head`，随后启动 FastAPI。

## 4. 首次验证

部署成功后暂时保留公网访问，按顺序检查：

```text
https://<云托管默认域名>/health
https://<云托管默认域名>/docs
https://<云托管默认域名>/api/v1/market/status
https://<云托管默认域名>/api/v1/anomalies/confirmed
```

健康检查应至少返回：

```json
{
  "status": "ok",
  "service": "deviation-alert-api",
  "database": "ok",
  "cache": "ok",
  "market_sync": "idle"
}
```

真实行情首次回填期间，市场接口会返回 `PUBLIC_DATA_SYNCING`，页面明确显示
“真实行情同步中（暂显演示数据）”。同步完成后数据源会切换为
`SINA_PUBLIC_PARTIAL` 或 `EASTMONEY_PUBLIC_PARTIAL`。

## 5. 切换小程序到 CloudBase

修改 `config/env.js`：

```js
module.exports = {
  API_MODE: 'cloudbase',
  LOCAL_API_BASE_URL: 'http://127.0.0.1:8000/api/v1',
  CLOUDBASE_ENV_ID: '<实际环境ID>',
  CLOUDBASE_SERVICE_NAME: 'deviation-alert-api',
};
```

在微信开发者工具中重新编译，依次验证：

1. 首页能读取市场状态和榜单。
2. 添加一只六位代码的自选股。
3. 关闭并重新打开小程序，自选仍然存在。
4. 使用另一个微信账号体验，自选数据相互隔离。
5. 云托管日志中的请求包含 `X-WX-OPENID`。

完成后执行两项安全收口：

1. 把云托管环境变量 `REQUIRE_WECHAT_IDENTITY` 改为 `true` 并发布新版本。
2. 关闭云托管公网访问，只保留小程序 `callContainer` 私网调用。

## 6. 盘中实例计划

10～15 秒刷新依赖至少一个运行中的采集实例。建议在交易日配置定时扩缩容：

- 09:00：最小实例调为 1。
- 11:40：最小实例调为 0。
- 12:50：最小实例调为 1。
- 15:10：最小实例调为 0。

最大实例固定为 1，避免多个实例同时写入同一批行情。非交易时间即使用户打开小程序，也只读取
数据库中的盘后结果，不轮询行情。

## 7. MVP 已知限制

- 当前每个板块只扫描当日涨幅靠前的 20 只候选股，不是全市场完整扫描。
- 新浪和东方财富均属于未授权公开网页接口，只适合内部 MVP。
- 当前提醒开关已经持久化，但还没有发送微信订阅消息。
- 暂未接入交易所节假日日历，周末已正确识别，法定调休和临时休市待补充。
- 暂未完成10日内同向异动次数规则和30个以上历史案例回放。

这些限制不阻塞内部 MVP 上线，但在公开运营、接入广告或收费前必须重新评估数据授权和金融类目资质。
