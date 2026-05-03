# 大麦抢票系统 - Web 自动化学习示例

> **本项目仅供学习研究使用，请勿用于任何商业或非法用途。使用前请阅读 [免责声明](DISCLAIMER.md)。**

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-blue.svg" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/FastAPI-0.100+-green.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/Playwright-1.40+-orange.svg" alt="Playwright">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT License">
</p>

---

## 免责声明

> **在使用本项目之前，请务必仔细阅读 [免责声明 (DISCLAIMER.md)](DISCLAIMER.md)。**

本软件是一个基于 Python + Playwright 的 **Web 自动化技术学习示例项目**，仅供开发者学习以下技术：

- **Playwright 浏览器自动化**：页面导航、元素操作、Cookie 管理
- **FastAPI 后端开发**：RESTful API、WebSocket 实时通信、JWT 认证
- **前端 SPA 架构**：单页应用、实时日志推送、Dark Theme UI
- **反检测技术研究**：Canvas/WebGL 指纹、User-Agent 轮换、行为模拟
- **验证码识别**：ddddocr OCR 识别、滑块验证码处理
- **多任务并发**：asyncio 协程、策略模式、自动重连

**本软件不提供任何形式的票务抢购、代购或转售服务。** 使用者应遵守所在地区的法律法规以及相关平台的用户协议。因使用本软件而产生的一切后果由使用者自行承担，与本软件作者无关。

---

## 功能特性

### 核心功能

| 功能 | 说明 |
|------|------|
| Web 管理界面 | 暗色主题 SPA，支持实时日志查看 |
| 多账号管理 | 支持多个大麦网账号同时登录和管理 |
| 定时抢票 | 支持设置开售时间，提前 30 秒自动准备 |
| 多策略引擎 | 并发 / 轮询 / 随机三种抢票策略可选 |
| 验证码处理 | 自动识别图片验证码和滑块验证码 |
| 观演人管理 | 自动选择已保存的观演人信息 |
| 抢票成功通知 | 跨平台声音提示 + 系统通知 + 截图保存 |

### 技术特性

| 特性 | 说明 |
|------|------|
| 反检测系统 | Canvas/WebGL 指纹噪声、UA 轮换、行为模拟 |
| 贝塞尔曲线鼠标 | 模拟真人鼠标移动轨迹，带随机抖动 |
| 自动重连 | 网络异常/浏览器崩溃自动恢复 |
| 实时日志 | WebSocket 推送 + HTTP 轮询双通道 |
| Cookie 持久化 | 每个账号独立 Cookie 存储 |
| 跨平台通知 | Windows / macOS / Linux 系统通知支持 |

---

## 项目结构

```
qiangpiao/
├── README.md                  # 项目说明文档
├── LICENSE                    # MIT 开源许可证
├── DISCLAIMER.md              # 免责声明
├── CONTRIBUTING.md            # 贡献指南
├── .gitignore                 # Git 忽略规则
│
└── damai_bot/                 # 主程序目录
    ├── start_web.py           # 一键启动脚本
    ├── 启动抢票系统.bat        # Windows 启动器（含免责声明）
    ├── requirements.txt       # Python 依赖
    ├── config.example.json    # 配置文件模板
    ├── config.json            # 用户配置（已 gitignore）
    ├── 使用手册.html           # 用户使用手册
    │
    ├── backend/               # 后端模块
    │   ├── light_server.py    # FastAPI 主服务器（REST API + WebSocket）
    │   ├── 抢票.py             # 核心抢票引擎
    │   ├── strategies.py      # 多策略模式（并发/轮询/随机）
    │   ├── anti_detect.py     # 反检测模块（指纹伪造、行为模拟）
    │   ├── captcha_solver.py  # 验证码识别（ddddocr）
    │   ├── login.py           # 登录管理（Cookie 持久化）
    │   ├── notify.py          # 跨平台通知系统
    │   ├── logger.py          # 统一日志配置
    │   │
    │   ├── utils/             # 工具模块
    │   │   ├── core.py        # 核心工具函数
    │   │   ├── cookie_manager.py  # Cookie 管理
    │   │   ├── login_manager.py   # 登录状态管理
    │   │   ├── viewer_manager.py  # 观演人管理
    │   │   ├── simple_login.py    # 简化登录
    │   │   └── edge_login.py      # Edge 浏览器登录
    │   │
    │   └── features/          # 扩展功能
    │       ├── screenshot.py  # 成功截图
    │       └── auto_reconnect.py  # 自动重连
    │
    └── frontend/              # 前端模块
        ├── index.html         # 主页面
        ├── style.css          # 暗色主题样式
        ├── api.js             # API 客户端（REST + WebSocket）
        └── main.js            # 前端应用逻辑
```

---

## 快速开始

### 环境要求

- **Python 3.8+**（推荐 3.10+）
- **操作系统**：Windows 10/11、macOS、Linux
- **内存**：建议 4GB+

### 安装步骤

#### 方式一：Windows 一键启动（推荐）

1. 确保已安装 [Python 3.8+](https://www.python.org/downloads/)，安装时勾选 "Add Python to PATH"
2. 双击运行 `damai_bot/启动抢票系统.bat`
3. 阅读并同意免责声明
4. 系统自动安装依赖并启动

#### 方式二：手动安装

```bash
# 1. 克隆仓库
git clone https://github.com/YOUR_USERNAME/qiangpiao.git
cd qiangpiao/damai_bot

# 2. 创建虚拟环境（推荐）
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 安装浏览器驱动
python -m playwright install chromium

# 5. 复制配置文件模板
cp config.example.json config.json

# 6. 启动系统
python start_web.py
```

启动后浏览器会自动打开 `http://localhost:8000`。

### 默认登录

| 字段 | 值 |
|------|-----|
| 用户名 | `admin` |
| 密码 | `admin123` |

> **安全提示**：默认凭据仅用于本地学习测试，请勿在公网暴露。

---

## 使用说明

### 1. 登录系统

启动后在浏览器中打开系统，使用默认账号登录。

### 2. 添加大麦网账号

1. 点击"添加账号"按钮
2. 系统会打开浏览器窗口，显示大麦网登录页面
3. 使用大麦 APP 扫码登录
4. 登录成功后 Cookie 自动保存

### 3. 配置抢票任务

在左侧控制面板填写：

| 字段 | 说明 |
|------|------|
| 演出名称 | 大麦网演出名称（如"周杰伦"） |
| 城市 | 演出城市（如"上海"） |
| 场次 | 选择场次时间 |
| 票价 | 选择目标票价（可多选） |
| 数量 | 购票数量 |
| 观演人 | 选择已保存的观演人 |
| 开售时间 | 设置定时抢票时间（可选） |

### 4. 开始抢票

点击"开始抢票"按钮，系统将：

1. 等待开售时间（如已设置）
2. 自动打开演出页面
3. 选择场次和票价
4. 处理验证码
5. 选择观演人
6. 提交订单

### 5. 抢票成功

成功后系统会：
- 播放提示音
- 显示系统通知
- 自动截图保存
- 取消其他账号的抢票任务

---

## 配置说明

复制 `config.example.json` 为 `config.json` 后编辑：

### 演出配置 (concert)

```json
{
  "concert": {
    "name": "演出名称",
    "city": "城市",
    "event_id": "大麦网演出ID（可选，填写后跳过搜索直接访问）",
    "session_id": "场次ID（可选）",
    "ticket_id": "票档ID（可选）"
  }
}
```

### 引擎配置 (engine)

```json
{
  "engine": {
    "concurrency": 2,        // 并发数
    "retry_count": 999,      // 最大重试次数
    "interval": 0.3,         // 重试间隔（秒）
    "headless": false,       // 是否无头模式（false = 显示浏览器）
    "stop_on_success": true  // 成功后是否停止
  }
}
```

### 定时配置 (schedule)

```json
{
  "schedule": {
    "enabled": true,
    "sale_time": "2025-01-01 10:00:00",  // 开售时间
    "advance_seconds": 30                  // 提前秒数
  }
}
```

### 反检测配置 (anti_detect)

```json
{
  "anti_detect": {
    "enabled": true,          // 启用反检测
    "random_delay": true,     // 随机延迟
    "user_agent_rotate": true // UA 轮换
  }
}
```

---

## 技术架构

```
┌─────────────────┐     HTTP/WS      ┌─────────────────┐
│   Web 前端      │ <===============> │  FastAPI 后端    │
│  (HTML/CSS/JS)  │  localhost:8000   │  (light_server)  │
└─────────────────┘                   └─────────────────┘
                                              │
                                         Playwright
                                              │
                                              v
                                    ┌─────────────────┐
                                    │  Chromium 浏览器  │
                                    │  (反检测注入)     │
                                    └─────────────────┘
                                              │
                                         自动化操作
                                              │
                                              v
                                    ┌─────────────────┐
                                    │   m.damai.cn     │
                                    │   (移动端 H5)     │
                                    └─────────────────┘
```

### 通信流程

1. **前端** → REST API 创建任务
2. **后端** → 启动 Playwright 浏览器上下文
3. **后端** → 注入反检测脚本、加载 Cookie
4. **后端** → 自动化操作：导航 → 选座 → 验证码 → 提交
5. **后端** → WebSocket 实时推送日志到前端
6. **成功后** → 截图 + 通知 + 取消其他任务

---

## 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| 后端 | Python 3.8+ | 主要编程语言 |
| 后端 | FastAPI | Web 框架（REST + WebSocket） |
| 后端 | Playwright | 浏览器自动化 |
| 后端 | ddddocr | 验证码 OCR 识别 |
| 后端 | python-jose | JWT 认证 |
| 前端 | HTML5 / CSS3 | 单页应用界面 |
| 前端 | JavaScript ES6+ | API 客户端、WebSocket |
| 工具 | uvicorn | ASGI 服务器 |

---

## 常见问题

### Q: 启动后浏览器没有自动打开？

手动访问 `http://localhost:8000`。

### Q: 提示"未找到 Python"？

请安装 [Python 3.8+](https://www.python.org/downloads/)，安装时勾选 "Add Python to PATH"。

### Q: Playwright 报错找不到浏览器？

```bash
python -m playwright install chromium
```

### Q: Cookie 过期了怎么办？

重新扫码登录即可，系统会自动更新 Cookie。

### Q: 如何在 macOS/Linux 上使用？

```bash
cd damai_bot
python start_web.py
```

不支持 `.bat` 启动器，直接用 Python 启动即可。

---

## 许可证

本项目基于 [MIT 许可证](LICENSE) 开源。

---

## 免责声明（再次提醒）

**本软件仅供学习研究使用。** 使用者应遵守所在地区的法律法规以及相关平台的用户协议。因使用本软件而产生的一切后果由使用者自行承担，与本软件作者无关。

完整免责声明请参阅 [DISCLAIMER.md](DISCLAIMER.md)。

---

> 作者：[小吴 (wuj4374-boop)](https://github.com/wuj4374-boop)
>
> 性质：开源学习项目 / Open Source Learning Project
