# 异动雷达

微信小程序内部 MVP，用于展示按公开规则计算的股票正向异动、接近异动与严重异常波动状态。

当前仓库先实现已确认的 UI：

- 沪深主板、创业板、科创板展示
- 盘中 / 盘后状态切换
- 3 日、10 日、30 日规则进度
- 股票详情、自选、提醒中心和个人中心
- 下拉刷新和订阅状态交互

> 当前行情均为模拟数据，所有“触发”均为系统计算结果，不代表交易所最终认定，也不构成投资建议。

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

- 点击“盘中 / 盘后”切换行情状态。
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
      ├─ index.js            模拟数据和交互逻辑
      ├─ index.json          页面配置
      ├─ index.wxml          页面结构
      └─ index.wxss          页面样式
```

## 下一阶段

完整任务拆解见 [ROADMAP.md](ROADMAP.md)。当前已完成 FastAPI 接口骨架与小程序请求适配，接口暂由内存模拟仓储提供数据。

## 启动后端接口

需要 Python 3.12：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

启动后访问：

- 健康检查：<http://127.0.0.1:8000/health>
- Swagger 接口文档：<http://127.0.0.1:8000/docs>
- 盘中榜单：<http://127.0.0.1:8000/api/v1/anomalies/intraday>

微信开发者工具继续导入仓库根目录。小程序默认访问 `http://127.0.0.1:8000/api/v1`；配置位于 `config/env.js`。页面股票、统计、详情、自选和提醒状态均以后端 Mock 接口为准；后端未启动时页面会明确显示连接失败。

运行后端测试：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```
