# 异动偏离预警器

微信小程序内部 MVP，用于展示按公开规则计算的股票正向异动、接近异动与严重异常波动状态。

产品名称统一为“异动偏离预警器”，突出股票异动监测、涨幅偏离值计算和风险预警能力。

当前仓库已经实现 UI、持久化后端和首版真实行情候选池：

- 沪深主板、创业板、科创板展示
- 根据北京时间自动识别交易时间段 / 非交易时间段
- 3 日、10 日、30 日规则进度
- 股票详情、自选、提醒中心和个人中心
- 自选页支持输入六位代码添加；按设备用户标识隔离并持久化
- 下拉刷新和订阅状态交互

> 默认使用新浪财经公开网页行情，零付费且仅适合内部 MVP。当前每个板块按当日涨幅选取 20 只候选股并回填 45 日日线，不代表全市场完整扫描。所有“触发”均为系统计算结果，不代表交易所最终认定，也不构成投资建议。

## 如何启动

### 1. 安装微信开发者工具

从微信官方开发者工具页面下载稳定版并完成安装：

<https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html>

### 2. 导入项目

1. 打开微信开发者工具，选择“小程序”。
2. 点击“导入项目”。
3. 项目目录选择本仓库根目录 `yidong-project`。
4. AppID：仅预览 UI 时可使用测试号；已有小程序 AppID 时，将其填入 `project.config.json` 的 `appid`。
5. 点击“导入”，编译后即可看到首页。

仓库默认使用 `touristappid`，并关闭开发阶段的合法域名校验，便于先查看 UI。正式开发和上传前必须替换为真实 AppID。

### 3. 体验交互

- 工作日北京时间 09:15–11:30、13:00–15:00 显示“交易时间段”，其余时间显示“非交易时间段”。
- 点击任意股票进入规则详情。
- 在详情页切换自选和提醒状态。
- 使用底部导航查看自选、提醒和个人中心。
- 下拉页面可模拟刷新。

## 项目结构

```text
.
├─ app.js                    小程序入口
├─ app.json                  全局页面与窗口配置
├─ app.wxss                  全局样式
├─ project.config.json       微信开发者工具项目配置
├─ sitemap.json              页面索引配置
└─ pages/
   └─ index/
      ├─ index.js            后端接口调用和交互逻辑
      ├─ index.json          页面配置
      ├─ index.wxml          页面结构
      └─ index.wxss          页面样式
```

## 下一阶段

完整任务拆解见 [ROADMAP.md](ROADMAP.md)。当前已完成 FastAPI、SQLAlchemy、Alembic 和缓存层，小程序接口数据来自持久化数据库。开发环境默认使用 SQLite，Docker 部署使用 PostgreSQL 16 和 Redis 7。

## 启动后端接口

需要 Python 3.12：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

启动后访问：

- 健康检查：<http://127.0.0.1:8000/health>
- Swagger 接口文档：<http://127.0.0.1:8000/docs>
- 盘中榜单：<http://127.0.0.1:8000/api/v1/anomalies/intraday>

微信开发者工具继续导入仓库根目录。小程序默认访问 `http://127.0.0.1:8000/api/v1`；配置位于 `config/env.js`。页面股票、统计、详情、自选和提醒状态均以后端数据库接口为准；后端未启动时页面会明确显示连接失败。

首次打开小程序时，前端会生成匿名设备用户标识并保存到微信本地存储，请求通过 `X-User-Key` 传给后端。自选和提醒记录按该标识隔离；这满足内部 MVP 的用户级数据隔离，但不等同于微信身份认证，正式内部发布仍需接入 `code2Session`。

刷新策略：交易时间段每 15 秒轮询一次，每次请求均显示 Loading；非交易时间段不轮询行情。小程序会在下一个时间边界自动重新判断状态，用户不能手动切换。

本地首次启动会生成 `backend/change_radar.db`，该文件已被 Git 忽略。后端启动后会在后台同步四个板块的真实候选行情；首次同步期间接口返回 `PUBLIC_DATA_SYNCING`，完成后返回 `SINA_PUBLIC_PARTIAL`。盘中每 15 秒更新实时快照，盘后每天只固化一次。自选和提醒设置在服务重启后仍保留。

真实行情依赖公网访问。若电脑设置了不可用的系统代理，默认配置会绕过该代理直连新浪接口；可在 `.env` 中用 `MARKET_HTTP_USE_ENVIRONMENT_PROXY=true` 改回跟随系统代理。若只想运行离线接口测试，可设置 `MARKET_DATA_PROVIDER=database_demo`。

## PostgreSQL 与 Redis 模式

安装 Docker Desktop 后，在仓库根目录执行：

```powershell
docker compose up --build
```

该命令会启动 PostgreSQL 16、Redis 7 和后端 API，并自动执行 Alembic 迁移。生产部署前必须把 `compose.yaml` 中的开发数据库密码改为服务器密钥或 `.env` 注入。

环境变量示例见 `backend/.env.example`：

- `DATABASE_URL`：数据库连接地址。
- `CACHE_BACKEND`：`memory`、`redis` 或 `null`。
- `REDIS_URL`：Redis 连接地址。
- `AUTO_CREATE_TABLES`：仅自动化测试开启；日常开发和生产统一使用 Alembic，因此保持关闭。
- `SEED_DEMO_DATA`：是否为空数据库写入演示数据。
- `MARKET_DATA_PROVIDER`：`sina` 表示启用真实网页行情适配器，`database_demo` 表示离线演示模式。
- `MARKET_CANDIDATE_LIMIT_PER_BOARD`：每个板块回填历史的候选数，默认 20。
- `MARKET_HTTP_USE_ENVIRONMENT_PROXY`：真实行情请求是否沿用系统代理，默认 `false`。

运行后端测试：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```
