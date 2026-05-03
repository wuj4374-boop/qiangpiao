"""
大麦抢票系统 - 轻量后端服务器

本文件为 Web 自动化技术学习示例，仅供开发者学习研究使用。
请勿用于任何商业或非法用途。使用前请阅读项目根目录下的 DISCLAIMER.md。

技术要点：
- FastAPI 异步 Web 框架（REST API + WebSocket）
- JWT 认证机制（HS256 签名）
- Playwright 浏览器自动化集成
- asyncio 并发任务管理

启动方式:
    cd damai_bot
    python -m backend.light_server
    或
    uvicorn backend.light_server:app --host 0.0.0.0 --port 8000 --reload

作者：小吴 (Xiao Wu)
许可证：MIT
"""

import asyncio
import importlib
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# 路径设置
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"
COOKIES_PATH = BACKEND_DIR / "cookies.json"
COOKIES_DIR = BACKEND_DIR / "cookies"
ACCOUNTS_PATH = BACKEND_DIR / "accounts.json"
CONFIG_PATH = PROJECT_DIR / "config.json"

# 确保项目根目录在 sys.path 中，方便导入同级模块
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("light_server")

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "damai-bot-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 小时

# 默认用户（简单版，无数据库）
DEFAULT_USERS = {
    "admin": {
        "username": "admin",
        "password": "admin123",
        "nickname": "管理员",
    }
}

# ---------------------------------------------------------------------------
# 全局状态
# ---------------------------------------------------------------------------
tasks_store: Dict[str, Dict[str, Any]] = {}          # task_id -> task info
ws_connections: Dict[str, Set[WebSocket]] = {}        # user_id -> set of websockets
task_cancel_events: Dict[str, asyncio.Event] = {}     # task_id -> cancel event
accounts_store: Dict[str, Dict[str, Any]] = {}        # account_id -> account info
task_groups: Dict[str, Dict[str, Any]] = {}           # group_id -> {task_ids: [...]}
qr_login_lock = asyncio.Lock()                        # 串行化扫码登录
_login_in_progress: Set[str] = set()                  # 正在扫码登录的 account_id 集合
_pw_instance = None  # playwright instance (lazy)
_browser = None      # shared browser (lazy)
_headless_pw = None  # headless playwright instance (lazy)
_headless_browser = None  # headless browser for status checks (lazy)

# ---------------------------------------------------------------------------
# Pydantic 模型
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str

class TaskConfigConcert(BaseModel):
    concert_name: str = ""
    city: str = ""
    event_id: str = ""
    session: str = ""
    prices: List[int] = []
    count: int = 1
    viewers: List[Dict[str, Any]] = []
    sale_time: str = ""

class TaskCreateRequest(BaseModel):
    name: str = ""
    config: TaskConfigConcert
    account_ids: List[str] = []

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    return {}

def save_config(cfg: dict):
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

def load_accounts() -> dict:
    if ACCOUNTS_PATH.exists():
        return json.loads(ACCOUNTS_PATH.read_text(encoding="utf-8-sig"))
    return {"accounts": []}

def save_accounts(data: dict):
    ACCOUNTS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def get_account_cookie_path(account_id: str) -> Path:
    return COOKIES_DIR / f"{account_id}.json"

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def broadcast_to_user(user_id: str, message: dict):
    """向指定用户的所有 WebSocket 连接广播消息"""
    conns = ws_connections.get(user_id, set())
    dead: List[WebSocket] = []
    for ws in conns:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        conns.discard(ws)

async def broadcast_all(message: dict):
    """向所有已连接用户广播消息"""
    for uid in list(ws_connections.keys()):
        await broadcast_to_user(uid, message)

async def group_cancel_others(task_id: str, group_id: str):
    """取消同组中其他任务"""
    group = task_groups.get(group_id, {})
    for other_tid in group.get("task_ids", []):
        if other_tid != task_id:
            evt = task_cancel_events.get(other_tid)
            if evt:
                evt.set()
            other_task = tasks_store.get(other_tid)
            if other_task and other_task["status"] in ("running", "waiting"):
                other_task["status"] = "cancelled"

async def get_browser():
    """懒加载共享的 Playwright 浏览器实例"""
    global _pw_instance, _browser
    if _browser is None:
        from playwright.async_api import async_playwright
        _pw_instance = await async_playwright().start()
        from backend.anti_detect import get_browser_args
        _browser = await _pw_instance.chromium.launch(
            headless=False,
            args=get_browser_args(),
        )
        logger.info("Playwright 浏览器已启动")
    return _browser


async def get_headless_browser():
    """懒加载 headless 浏览器实例（用于登录状态检查等不需要可见窗口的场景）"""
    global _headless_pw, _headless_browser
    if _headless_browser is None:
        from playwright.async_api import async_playwright
        _headless_pw = await async_playwright().start()
        from backend.anti_detect import get_browser_args
        _headless_browser = await _headless_pw.chromium.launch(
            headless=True,
            args=get_browser_args(),
        )
        logger.info("Playwright Headless 浏览器已启动")
    return _headless_browser

# ---------------------------------------------------------------------------
# 认证依赖
# ---------------------------------------------------------------------------
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token 已过期或无效")

    user = DEFAULT_USERS.get(username)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user

# ---------------------------------------------------------------------------
# FastAPI 应用
# ---------------------------------------------------------------------------
app = FastAPI(title="大麦抢票系统 - 轻量后端", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 前端静态文件
app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")


@app.get("/")
async def serve_index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/style.css")
async def serve_css():
    return FileResponse(str(FRONTEND_DIR / "style.css"), media_type="text/css")


@app.get("/api.js")
async def serve_api_js():
    return FileResponse(str(FRONTEND_DIR / "api.js"), media_type="application/javascript")


@app.get("/main.js")
async def serve_main_js():
    return FileResponse(str(FRONTEND_DIR / "main.js"), media_type="application/javascript")

# ---------------------------------------------------------------------------
# 启动 / 关闭事件
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def on_startup():
    global accounts_store
    logger.info("轻量后端启动中...")
    # 预加载 config.json
    cfg = load_config()
    logger.info(f"已加载 config.json，演出: {cfg.get('concert', {}).get('name', '未配置')}")
    # 创建 cookies 目录
    COOKIES_DIR.mkdir(parents=True, exist_ok=True)
    # 加载账号列表
    accounts_data = load_accounts()
    for acc in accounts_data.get("accounts", []):
        accounts_store[acc["id"]] = acc
    logger.info(f"已加载 {len(accounts_store)} 个账号")

@app.on_event("shutdown")
async def on_shutdown():
    global _pw_instance, _browser, _headless_pw, _headless_browser
    logger.info("正在关闭浏览器和 Playwright...")
    if _browser:
        try:
            await _browser.close()
        except Exception:
            pass
    if _headless_browser:
        try:
            await _headless_browser.close()
        except Exception:
            pass
    if _pw_instance:
        try:
            await _pw_instance.stop()
        except Exception:
            pass
    if _headless_pw:
        try:
            await _headless_pw.stop()
        except Exception:
            pass
    logger.info("后端已关闭")

# =========================== 健康检查 ===========================

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# =========================== 用户认证 ===========================

@app.post("/api/v1/auth/login")
async def auth_login(req: LoginRequest):
    user = DEFAULT_USERS.get(req.username)
    if not user or user["password"] != req.password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    token = create_access_token({"sub": user["username"]})
    return {
        "success": True,
        "data": {
            "token": token,
            "user": {"username": user["username"], "nickname": user["nickname"]},
        },
    }

@app.get("/api/v1/auth/me")
async def auth_me(current_user: dict = Depends(get_current_user)):
    return {"username": current_user["username"], "nickname": current_user["nickname"]}

# =========================== 大麦网登录 ===========================

@app.post("/api/v1/login/qrcode")
async def login_qrcode():
    """启动浏览器打开大麦登录页，等待用户扫码"""
    browser = await get_browser()

    from backend.anti_detect import create_stealth_context
    context = await create_stealth_context(browser)
    page = await context.new_page()

    await page.goto("https://passport.damai.cn/login")
    await page.wait_for_load_state("networkidle", timeout=30000)
    logger.info("大麦登录页已打开，等待扫码...")

    # 后台轮询检测登录状态
    async def poll_login():
        try:
            await page.wait_for_selector('text="退出登录"', timeout=120000)
            # 登录成功，保存 cookie
            cookies = await context.cookies()
            COOKIES_PATH.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info(f"登录成功，Cookie 已保存到 {COOKIES_PATH}")
        except Exception as e:
            logger.warning(f"扫码登录超时或失败: {e}")
        finally:
            try:
                await page.close()
                await context.close()
            except Exception:
                pass

    asyncio.create_task(poll_login())

    return {"status": "waiting", "message": "请扫码登录，浏览器窗口已打开"}

@app.get("/api/v1/login/test")
async def login_test():
    """通过 Cookie 文件验证是否已登录（不启动浏览器）"""
    if not COOKIES_PATH.exists():
        return {"logged_in": False, "nickname": "", "message": "未找到 Cookie 文件"}

    try:
        raw = json.loads(COOKIES_PATH.read_text(encoding="utf-8-sig"))
        cookies = raw.get("cookies", raw) if isinstance(raw, dict) else raw

        # 检查是否包含大麦网登录标识 Cookie
        auth_names = {"_m_h5_tk", "_m_h5_tk_enc", "cookie2", "munb", "t", "sgcookie", "unb"}
        has_auth = any(
            c.get("name") in auth_names and c.get("domain", "").endswith("damai.cn")
            for c in cookies
        )

        if has_auth:
            return {"logged_in": True, "nickname": ""}
        else:
            return {"logged_in": False, "nickname": "", "message": "Cookie 中未找到登录标识"}

    except Exception as e:
        logger.error(f"检查登录状态失败: {e}")
        return {"logged_in": False, "nickname": "", "message": f"检查失败: {str(e)}"}

# =========================== 多账号管理 ===========================

@app.get("/api/v1/accounts")
async def list_accounts(current_user: dict = Depends(get_current_user)):
    """列出所有已注册账号"""
    accounts = list(accounts_store.values())
    return {"accounts": accounts}

@app.post("/api/v1/accounts")
async def create_account(current_user: dict = Depends(get_current_user)):
    """注册新账号，返回 account_id"""
    account_id = "acc_" + str(uuid.uuid4())[:8]
    account = {
        "id": account_id,
        "nickname": "",
        "status": "not_logged_in",
        "created_at": datetime.utcnow().isoformat(),
        "last_login": None,
    }
    accounts_store[account_id] = account
    # 持久化
    data = load_accounts()
    data.setdefault("accounts", []).append(account)
    save_accounts(data)
    logger.info(f"新账号已注册: {account_id}")
    return account

@app.delete("/api/v1/accounts/{account_id}")
async def delete_account(account_id: str, current_user: dict = Depends(get_current_user)):
    """删除账号及其 Cookie 文件"""
    if account_id not in accounts_store:
        raise HTTPException(status_code=404, detail="账号不存在")
    # 删除 cookie 文件
    cookie_path = get_account_cookie_path(account_id)
    if cookie_path.exists():
        cookie_path.unlink()
    # 从内存和文件中移除
    del accounts_store[account_id]
    data = load_accounts()
    data["accounts"] = [a for a in data.get("accounts", []) if a["id"] != account_id]
    save_accounts(data)
    logger.info(f"账号已删除: {account_id}")
    return {"status": "deleted", "account_id": account_id}

@app.post("/api/v1/accounts/{account_id}/login")
async def account_qrcode_login(account_id: str, current_user: dict = Depends(get_current_user)):
    """为指定账号启动扫码登录"""
    if account_id not in accounts_store:
        raise HTTPException(status_code=404, detail="账号不存在")

    # 串行化扫码登录（同一时间只能有一个扫码窗口）
    if qr_login_lock.locked():
        raise HTTPException(status_code=429, detail="已有扫码登录进行中，请稍后再试")

    async with qr_login_lock:
        browser = await get_browser()
        from backend.anti_detect import create_stealth_context
        context = await create_stealth_context(browser)
        page = await context.new_page()

        await page.goto("https://passport.damai.cn/login")
        await page.wait_for_load_state("networkidle", timeout=30000)
        logger.info(f"账号 {account_id} 大麦登录页已打开，等待扫码...")

        # 标记该账号正在扫码登录中（状态检查端点会跳过浏览器验证）
        _login_in_progress.add(account_id)

        async def poll_login():
            try:
                login_detected = False
                login_url = "https://passport.damai.cn/login"
                start_url = page.url

                # 方法1：等待页面出现"退出登录"文本（15秒超时）
                try:
                    await asyncio.wait_for(
                        page.wait_for_selector('text="退出登录"', timeout=15000),
                        timeout=16
                    )
                    login_detected = True
                    logger.info(f"账号 {account_id} 方法1(页面文本)检测到登录成功")
                except (asyncio.TimeoutError, Exception):
                    logger.info(f"账号 {account_id} 方法1未命中")

                # 方法2：检测页面 URL 是否已离开登录页（扫码后直接跳转）
                if not login_detected:
                    try:
                        current_url = page.url
                        if current_url != login_url and "damai.cn" in current_url and "passport" not in current_url:
                            login_detected = True
                            logger.info(f"账号 {account_id} 方法2(URL跳转)检测到登录成功: {current_url}")
                    except Exception:
                        pass

                # 方法3：检查 cookies 是否包含登录标识
                if not login_detected:
                    try:
                        cookies = await context.cookies()
                        auth_names = {"_m_h5_tk", "_m_h5_tk_enc", "cookie2", "munb", "t", "sgcookie", "unb"}
                        auth_cookies = [c for c in cookies
                                        if c.get("domain", "").endswith("damai.cn")
                                        and c.get("name") in auth_names]
                        if auth_cookies:
                            login_detected = True
                            logger.info(f"账号 {account_id} 方法3(Cookie)检测到登录成功: {[c['name'] for c in auth_cookies]}")
                    except Exception as e:
                        logger.warning(f"账号 {account_id} Cookie 检测异常: {e}")

                # 方法4：导航到大麦首页验证
                if not login_detected:
                    try:
                        await page.goto("https://www.damai.cn", timeout=15000)
                        await page.wait_for_load_state("networkidle", timeout=10000)
                        await page.wait_for_selector('text="退出登录"', timeout=5000)
                        login_detected = True
                        logger.info(f"账号 {account_id} 方法4(首页导航)检测到登录成功")
                    except Exception:
                        logger.info(f"账号 {account_id} 所有方法均未命中")

                if login_detected:
                    # 登录成功，保存 cookie
                    cookies = await context.cookies()
                    cookie_path = get_account_cookie_path(account_id)
                    cookie_path.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
                    # 获取昵称
                    nickname = ""
                    try:
                        if "damai.cn" not in page.url:
                            await page.goto("https://www.damai.cn", timeout=15000)
                            await page.wait_for_load_state("networkidle", timeout=10000)
                        nick_el = await page.query_selector(".user-nickname, .header-user-name, .dm-header-nick")
                        if nick_el:
                            nickname = (await nick_el.inner_text()).strip()
                    except Exception:
                        pass
                    # 更新账号状态（必须在清除 _login_in_progress 之前完成）
                    accounts_store[account_id]["status"] = "logged_in"
                    accounts_store[account_id]["nickname"] = nickname or f"账号_{account_id[-4:]}"
                    accounts_store[account_id]["last_login"] = datetime.utcnow().isoformat()
                    # 持久化
                    data = load_accounts()
                    for acc in data.get("accounts", []):
                        if acc["id"] == account_id:
                            acc.update(accounts_store[account_id])
                            break
                    save_accounts(data)
                    logger.info(f"账号 {account_id} 登录成功，昵称: {nickname}")
                else:
                    logger.warning(f"账号 {account_id} 所有登录检测方法均未命中")
                    accounts_store[account_id]["status"] = "not_logged_in"
            except Exception as e:
                logger.warning(f"账号 {account_id} 扫码登录超时或失败: {e}")
                accounts_store[account_id]["status"] = "not_logged_in"
            finally:
                # 先更新状态，再清除标记，确保状态检查端点不会看到中间状态
                _login_in_progress.discard(account_id)
                try:
                    await page.close()
                    await context.close()
                except Exception:
                    pass

        asyncio.create_task(poll_login())

    return {"status": "waiting", "account_id": account_id, "message": "请扫码登录，浏览器窗口已打开"}

@app.get("/api/v1/accounts/{account_id}/login/status")
async def account_login_status(account_id: str, current_user: dict = Depends(get_current_user)):
    """检查指定账号的登录状态（不启动浏览器，通过 Cookie 文件判断）"""
    if account_id not in accounts_store:
        raise HTTPException(status_code=404, detail="账号不存在")

    # 如果该账号正在扫码登录中，直接返回等待状态
    if account_id in _login_in_progress:
        return {"logged_in": False, "account_id": account_id, "waiting": True, "message": "扫码登录进行中，请稍候"}

    account = accounts_store[account_id]
    cookie_path = get_account_cookie_path(account_id)

    if not cookie_path.exists():
        account["status"] = "not_logged_in"
        return {"logged_in": False, "nickname": "", "account_id": account_id}

    # 通过 Cookie 文件内容判断登录状态（不启动浏览器）
    try:
        raw = json.loads(cookie_path.read_text(encoding="utf-8-sig"))
        cookies = raw.get("cookies", raw) if isinstance(raw, dict) else raw

        # 检查是否包含大麦网登录标识 Cookie
        auth_names = {"_m_h5_tk", "_m_h5_tk_enc", "cookie2", "munb", "t", "sgcookie", "unb"}
        has_auth = any(
            c.get("name") in auth_names and c.get("domain", "").endswith("damai.cn")
            for c in cookies
        )

        if has_auth:
            # Cookie 有效，更新账号状态
            if account.get("status") != "logged_in":
                account["status"] = "logged_in"
                account["last_login"] = datetime.utcnow().isoformat()
                # 尝试从 cookie 中获取用户信息
                nickname = account.get("nickname", "") or f"账号_{account_id[-4:]}"
                account["nickname"] = nickname
                # 持久化
                data = load_accounts()
                for acc in data.get("accounts", []):
                    if acc["id"] == account_id:
                        acc.update(account)
                        break
                save_accounts(data)
            return {
                "logged_in": True,
                "nickname": account.get("nickname", ""),
                "account_id": account_id
            }
        else:
            account["status"] = "not_logged_in"
            return {"logged_in": False, "nickname": "", "account_id": account_id}

    except Exception as e:
        logger.error(f"检查账号 {account_id} Cookie 失败: {e}")
        return {
            "logged_in": account.get("status") == "logged_in",
            "nickname": account.get("nickname", ""),
            "account_id": account_id,
            "error": str(e)
        }

# =========================== 任务管理 ===========================

@app.post("/api/v1/tasks")
async def create_task(req: TaskCreateRequest, current_user: dict = Depends(get_current_user)):
    """创建抢票任务（支持多账号并发）"""

    # 合并配置：将请求的 config 覆盖到 config.json
    cfg = load_config()
    cfg.setdefault("concert", {})
    cfg.setdefault("ticket", {})
    cfg.setdefault("engine", {})

    c = req.config
    if c.concert_name:
        cfg["concert"]["name"] = c.concert_name
    if c.city:
        cfg["concert"]["city"] = c.city
    if c.event_id:
        cfg["concert"]["event_id"] = c.event_id
    if c.session:
        cfg["ticket"]["session"] = c.session
    if c.prices:
        cfg["ticket"]["prices"] = c.prices
    if c.count:
        cfg["ticket"]["count"] = c.count
    if c.viewers:
        cfg["viewers"] = c.viewers

    save_config(cfg)

    account_ids = req.account_ids
    task_name = req.name or cfg["concert"].get("name", "未命名任务")

    # 多账号模式
    if account_ids:
        group_id = "grp_" + str(uuid.uuid4())[:8]
        task_ids = []

        for acc_id in account_ids:
            if acc_id not in accounts_store:
                continue
            account = accounts_store[acc_id]
            cookie_path = get_account_cookie_path(acc_id)
            if not cookie_path.exists():
                continue

            task_id = str(uuid.uuid4())[:8]
            cancel_event = asyncio.Event()
            task_cancel_events[task_id] = cancel_event

            tasks_store[task_id] = {
                "id": task_id,
                "name": task_name,
                "status": "running",
                "current_attempt": 0,
                "max_attempts": cfg.get("engine", {}).get("retry_count", 999),
                "logs": [],
                "created_at": datetime.utcnow().isoformat(),
                "config": cfg,
                "sale_time": c.sale_time,
                "account_id": acc_id,
                "account_label": account.get("nickname", f"账号_{acc_id[-4:]}"),
                "group_id": group_id,
            }

            task_ids.append(task_id)
            asyncio.create_task(run_ticket_task(
                task_id, cfg, c.sale_time, cancel_event,
                account_id=acc_id, group_id=group_id,
            ))

        task_groups[group_id] = {"task_ids": task_ids, "config": cfg}

        return {
            "group_id": group_id,
            "tasks": [
                {"account_id": aid, "task_id": tid, "status": "running"}
                for aid, tid in zip(account_ids, task_ids)
            ],
        }

    # 单账号模式（向后兼容）
    task_id = str(uuid.uuid4())[:8]
    cancel_event = asyncio.Event()
    task_cancel_events[task_id] = cancel_event

    tasks_store[task_id] = {
        "id": task_id,
        "name": task_name,
        "status": "running",
        "current_attempt": 0,
        "max_attempts": cfg.get("engine", {}).get("retry_count", 999),
        "logs": [],
        "created_at": datetime.utcnow().isoformat(),
        "config": cfg,
        "sale_time": c.sale_time,
    }

    asyncio.create_task(run_ticket_task(task_id, cfg, c.sale_time, cancel_event))

    return {"id": task_id, "status": "running"}

@app.get("/api/v1/tasks/{task_id}")
async def get_task(task_id: str, current_user: dict = Depends(get_current_user)):
    task = tasks_store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "id": task["id"],
        "status": task["status"],
        "current_attempt": task["current_attempt"],
        "max_attempts": task["max_attempts"],
        "logs": task["logs"][-50:],  # 只返回最近 50 条日志
    }

@app.post("/api/v1/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, current_user: dict = Depends(get_current_user)):
    task = tasks_store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task["status"] not in ("running", "waiting"):
        return {"id": task_id, "status": task["status"], "message": "任务已结束，无法取消"}

    cancel_event = task_cancel_events.get(task_id)
    if cancel_event:
        cancel_event.set()

    task["status"] = "cancelled"
    await broadcast_to_user(current_user["username"], {
        "type": "task_status",
        "task_id": task_id,
        "status": "cancelled",
        "attempt": task["current_attempt"],
        "message": "任务已取消",
    })
    return {"id": task_id, "status": "cancelled"}

@app.post("/api/v1/tasks/group/{group_id}/cancel")
async def cancel_task_group(group_id: str, current_user: dict = Depends(get_current_user)):
    """取消整个任务组（多账号模式）"""
    group = task_groups.get(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="任务组不存在")

    cancelled = []
    for task_id in group.get("task_ids", []):
        task = tasks_store.get(task_id)
        if task and task["status"] in ("running", "waiting"):
            cancel_event = task_cancel_events.get(task_id)
            if cancel_event:
                cancel_event.set()
            task["status"] = "cancelled"
            cancelled.append(task_id)

    await broadcast_all({
        "type": "group_status",
        "group_id": group_id,
        "overall_status": "cancelled",
        "message": "任务组已取消",
    })
    return {"group_id": group_id, "cancelled_tasks": cancelled}

# =========================== WebSocket ===========================

@app.websocket("/api/v1/tasks/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await websocket.accept()
    if user_id not in ws_connections:
        ws_connections[user_id] = set()
    ws_connections[user_id].add(websocket)
    logger.info(f"WebSocket 已连接: {user_id}")

    try:
        while True:
            # 保持连接，接收客户端心跳或消息
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        logger.info(f"WebSocket 已断开: {user_id}")
    finally:
        ws_connections.get(user_id, set()).discard(websocket)

# =========================== 任务执行核心逻辑 ===========================

async def run_ticket_task(task_id: str, config: dict, sale_time: str, cancel_event: asyncio.Event,
                          account_id: str = None, group_id: str = None):
    """
    后台抢票任务主函数。
    使用 Playwright 浏览器 + 已有模块执行抢票。
    支持多账号模式：指定 account_id 时使用对应账号的 Cookie。
    """
    task = tasks_store[task_id]
    account_label = task.get("account_label", "")

    async def log_and_broadcast(msg: str):
        entry = {"time": datetime.utcnow().isoformat(), "message": msg}
        task["logs"].append(entry)
        prefix = f"[{account_label}] " if account_label else ""
        logger.info(f"[任务{task_id}] {prefix}{msg}")
        # 广播给所有已连接的用户
        ws_msg = {
            "type": "task_log",
            "task_id": task_id,
            "status": task["status"],
            "attempt": task["current_attempt"],
            "message": msg,
        }
        if account_id:
            ws_msg["account_id"] = account_id
            ws_msg["account_label"] = account_label
        if group_id:
            ws_msg["group_id"] = group_id
        await broadcast_all(ws_msg)

    try:
        await log_and_broadcast("任务开始，正在初始化浏览器...")

        # 获取浏览器和创建上下文
        browser = await get_browser()

        # 动态导入反检测模块
        from backend.anti_detect import create_stealth_context
        context = await create_stealth_context(browser)

        # 加载 cookie（优先使用账号专属 cookie）
        cookie_loaded = False
        if account_id:
            cookie_path = get_account_cookie_path(account_id)
            if cookie_path.exists():
                cookies = json.loads(cookie_path.read_text(encoding="utf-8-sig"))
                await context.add_cookies(cookies)
                await log_and_broadcast(f"已加载账号 {account_label} 的 Cookie")
                cookie_loaded = True

        if not cookie_loaded and COOKIES_PATH.exists():
            cookies = json.loads(COOKIES_PATH.read_text(encoding="utf-8-sig"))
            await context.add_cookies(cookies)
            await log_and_broadcast("已加载本地 Cookie")
            cookie_loaded = True

        if not cookie_loaded:
            await log_and_broadcast("未找到 Cookie 文件，请先扫码登录")

        # 如果有 sale_time，等待放票时间
        if sale_time:
            task["status"] = "waiting"
            await log_and_broadcast(f"等待放票时间: {sale_time}")

            try:
                # 解析放票时间
                sale_dt = datetime.strptime(sale_time, "%Y-%m-%d %H:%M:%S")
                advance = int(config.get("schedule", {}).get("advance_seconds", 30))
                target_dt = sale_dt - timedelta(seconds=advance)

                while True:
                    now = datetime.now()
                    remaining = (target_dt - now).total_seconds()
                    if remaining <= 0:
                        break
                    if cancel_event.is_set():
                        task["status"] = "cancelled"
                        await log_and_broadcast("任务已取消")
                        return
                    # 每 10 秒输出一次倒计时
                    if int(remaining) % 10 == 0 or remaining < 5:
                        await log_and_broadcast(f"距离开售还有 {remaining:.0f} 秒")
                    await asyncio.sleep(1)

                await log_and_broadcast("放票时间到，开始抢票！")
                task["status"] = "running"
            except ValueError as e:
                await log_and_broadcast(f"放票时间格式错误: {e}，跳过等待直接抢票")
            except Exception as e:
                await log_and_broadcast(f"等待放票异常: {e}")

        # 动态导入抢票模块（文件名含中文）
        ticket_module = importlib.import_module("backend.抢票")
        attempt_purchase = ticket_module.attempt_purchase

        max_attempts = task["max_attempts"]

        for attempt in range(1, max_attempts + 1):
            if cancel_event.is_set():
                task["status"] = "cancelled"
                await log_and_broadcast("任务已取消")
                return

            task["current_attempt"] = attempt
            await log_and_broadcast(f"第 {attempt} 次抢票尝试...")

            try:
                success = await attempt_purchase(context, config, task_id=attempt)
                if success:
                    task["status"] = "success"
                    await log_and_broadcast("抢票成功！请尽快完成支付。")

                    # 广播成功通知
                    status_msg = {
                        "type": "task_status",
                        "task_id": task_id,
                        "status": "success",
                        "attempt": attempt,
                        "message": "抢票成功！",
                    }
                    if account_id:
                        status_msg["account_id"] = account_id
                        status_msg["account_label"] = account_label
                    if group_id:
                        status_msg["group_id"] = group_id
                    await broadcast_all(status_msg)

                    # 多账号模式：取消同组其他任务
                    if group_id:
                        await group_cancel_others(task_id, group_id)
                        # 广播组状态
                        group_tasks = []
                        for tid in task_groups.get(group_id, {}).get("task_ids", []):
                            t = tasks_store.get(tid, {})
                            group_tasks.append({
                                "account_id": t.get("account_id", ""),
                                "task_id": tid,
                                "status": t.get("status", "unknown"),
                            })
                        await broadcast_all({
                            "type": "group_status",
                            "group_id": group_id,
                            "overall_status": "success",
                            "winning_account": account_id,
                            "tasks": group_tasks,
                        })
                    return
                else:
                    await log_and_broadcast(f"第 {attempt} 次尝试未成功")
            except Exception as e:
                await log_and_broadcast(f"第 {attempt} 次尝试异常: {e}")

            # 避免请求过快
            await asyncio.sleep(config.get("engine", {}).get("interval", 0.3))

        # 用尽所有尝试
        task["status"] = "failed"
        await log_and_broadcast(f"已达最大尝试次数 ({max_attempts})，任务失败")

    except Exception as e:
        task["status"] = "error"
        await log_and_broadcast(f"任务异常终止: {e}")
        logger.exception(f"任务 {task_id} 异常")
    finally:
        # 广播最终状态
        final_msg = {
            "type": "task_status",
            "task_id": task_id,
            "status": task["status"],
            "attempt": task["current_attempt"],
            "message": f"任务结束: {task['status']}",
        }
        if account_id:
            final_msg["account_id"] = account_id
            final_msg["account_label"] = account_label
        if group_id:
            final_msg["group_id"] = group_id
        await broadcast_all(final_msg)
        task_cancel_events.pop(task_id, None)

# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
