"""
大麦抢票系统 - 反检测模块

本文件为 Web 自动化技术学习示例，仅供开发者学习研究使用。
请勿用于任何商业或非法用途。使用前请阅读项目根目录下的 DISCLAIMER.md。

技术要点（仅供学习研究）：
1. 浏览器启动参数增强：禁用自动化标识
2. JS 注入：navigator.webdriver / plugins / languages / canvas / webgl 指纹伪造
3. User-Agent 轮换：30+ 真实 UA 池（桌面 + 移动端）
4. 操作间随机延迟：点击前 50-200ms，导航后 500-1500ms
5. 贝塞尔曲线鼠标移动模拟：带随机抖动和速度变化
6. 真人点击/输入模拟：逐字符输入、随机停顿

作者：小吴 (Xiao Wu)
许可证：MIT
"""

import random
import asyncio
import logging
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 真实桌面 User-Agent 池（Chrome 128-130 / Edge 128-130 on Windows 10/11）
# ---------------------------------------------------------------------------
USER_AGENTS: List[str] = [
    # Chrome 130 on Windows 11
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Chrome 129 on Windows 10/11
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    # Chrome 128 on Windows 10/11
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    # Edge 130 (Chromium-based)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    # Edge 129
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
    # Edge 128
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0",
    # Chrome 126-127 on Windows (still widely used)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
    # Chrome on macOS (补充多样性)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
]

# ---------------------------------------------------------------------------
# 移动端 User-Agent 池（iPhone Safari / Android Chrome）
# ---------------------------------------------------------------------------
MOBILE_USER_AGENTS: List[str] = [
    # iPhone Safari iOS 18
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Mobile/15E148 Safari/604.1",
    # iPhone Safari iOS 17
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.7 Mobile/15E148 Safari/604.1",
    # iPad Safari iOS 18
    "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1",
    # Android Chrome (various devices)
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-S926B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-A546B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; 23127PN0CC) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; V2305A) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; PGKM10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36",
]


def get_random_user_agent() -> str:
    """从桌面 UA 池中随机选取一个 User-Agent"""
    return random.choice(USER_AGENTS)


def get_random_mobile_user_agent() -> str:
    """从移动端 UA 池中随机选取一个 User-Agent（iPhone Safari / Android Chrome）"""
    return random.choice(MOBILE_USER_AGENTS)


# ---------------------------------------------------------------------------
# Chromium 启动参数
# ---------------------------------------------------------------------------
def get_browser_args(extra_args: Optional[List[str]] = None) -> List[str]:
    """
    返回统一的 Chromium 反检测启动参数。

    Args:
        extra_args: 额外追加的参数（不会覆盖默认参数）

    Returns:
        合并后的参数列表
    """
    args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--excludeSwitches=enable-automation",
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-extensions",
        "--disable-background-networking",
    ]
    if extra_args:
        args.extend(extra_args)
    return args


# ---------------------------------------------------------------------------
# JS 注入脚本（页面加载前执行）
# ---------------------------------------------------------------------------
STEALTH_JS = """
(() => {
    // 1. 覆盖 navigator.webdriver 为 undefined
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
        configurable: true,
    });

    // 2. 覆盖 navigator.plugins 为非空数组
    Object.defineProperty(navigator, 'plugins', {
        get: () => {
            const plugins = [
                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
                { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' },
            ];
            plugins.length = 3;
            return plugins;
        },
        configurable: true,
    });

    // 3. 覆盖 navigator.languages 为 ['zh-CN', 'zh', 'en']
    Object.defineProperty(navigator, 'languages', {
        get: () => ['zh-CN', 'zh', 'en'],
        configurable: true,
    });

    // 4. 隐藏 chrome.runtime 的自动化痕迹
    if (!window.chrome) {
        window.chrome = {};
    }
    if (!window.chrome.runtime) {
        window.chrome.runtime = {};
    }

    // 5. 覆盖 permissions.query 使其对 notification 返回 "prompt" 而非暴露自动化状态
    const originalQuery = window.navigator.permissions?.query;
    if (originalQuery) {
        window.navigator.permissions.query = (parameters) => {
            if (parameters.name === 'notifications') {
                return Promise.resolve({ state: Notification.permission });
            }
            return originalQuery(parameters);
        };
    }

    // 6. Canvas 指纹噪声注入
    const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(type, quality) {
        const ctx = this.getContext('2d');
        if (ctx) {
            const imageData = ctx.getImageData(0, 0, this.width, this.height);
            const data = imageData.data;
            // 对少量像素添加微小随机扰动（人眼不可见，但改变指纹）
            for (let i = 0; i < data.length; i += 4) {
                data[i] = data[i] ^ (Math.floor(Math.random() * 3) - 1);     // R
                data[i+1] = data[i+1] ^ (Math.floor(Math.random() * 3) - 1); // G
                data[i+2] = data[i+2] ^ (Math.floor(Math.random() * 3) - 1); // B
            }
            ctx.putImageData(imageData, 0, 0);
        }
        return originalToDataURL.call(this, type, quality);
    };

    const originalToBlob = HTMLCanvasElement.prototype.toBlob;
    HTMLCanvasElement.prototype.toBlob = function(callback, type, quality) {
        const ctx = this.getContext('2d');
        if (ctx) {
            const imageData = ctx.getImageData(0, 0, this.width, this.height);
            const data = imageData.data;
            for (let i = 0; i < data.length; i += 4) {
                data[i] = data[i] ^ (Math.floor(Math.random() * 3) - 1);
                data[i+1] = data[i+1] ^ (Math.floor(Math.random() * 3) - 1);
                data[i+2] = data[i+2] ^ (Math.floor(Math.random() * 3) - 1);
            }
            ctx.putImageData(imageData, 0, 0);
        }
        return originalToBlob.call(this, callback, type, quality);
    };

    // getImageData 也添加噪声（部分指纹检测直接读像素）
    const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
    CanvasRenderingContext2D.prototype.getImageData = function(sx, sy, sw, sh) {
        const imageData = originalGetImageData.call(this, sx, sy, sw, sh);
        const data = imageData.data;
        for (let i = 0; i < data.length; i += 4) {
            data[i] = data[i] ^ (Math.floor(Math.random() * 3) - 1);
            data[i+1] = data[i+1] ^ (Math.floor(Math.random() * 3) - 1);
            data[i+2] = data[i+2] ^ (Math.floor(Math.random() * 3) - 1);
        }
        return imageData;
    };

    // 7. WebGL 指纹噪声（覆盖 WEBGL_debug_renderer_info）
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        // UNMASKED_VENDOR_WEBGL = 0x9245, UNMASKED_RENDERER_WEBGL = 0x9246
        if (parameter === 0x9245) {
            return 'Google Inc. (NVIDIA)';
        }
        if (parameter === 0x9246) {
            const renderers = [
                'ANGLE (NVIDIA, NVIDIA GeForce RTX 4060 Direct3D11 vs_5_0 ps_5_0, D3D11)',
                'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)',
                'ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11)',
                'ANGLE (Intel, Intel(R) UHD Graphics 770 Direct3D11 vs_5_0 ps_5_0, D3D11)',
                'ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)',
                'ANGLE (AMD, AMD Radeon RX 7800 XT Direct3D11 vs_5_0 ps_5_0, D3D11)',
            ];
            // 每次页面加载随机选一个，但同一页面内保持一致
            if (!window.__webglRenderer) {
                window.__webglRenderer = renderers[Math.floor(Math.random() * renderers.length)];
            }
            return window.__webglRenderer;
        }
        return getParameter.call(this, parameter);
    };

    // 同步覆盖 WebGL2
    if (typeof WebGL2RenderingContext !== 'undefined') {
        const getParameter2 = WebGL2RenderingContext.prototype.getParameter;
        WebGL2RenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 0x9245) {
                return 'Google Inc. (NVIDIA)';
            }
            if (parameter === 0x9246) {
                if (!window.__webglRenderer) {
                    const renderers = [
                        'ANGLE (NVIDIA, NVIDIA GeForce RTX 4060 Direct3D11 vs_5_0 ps_5_0, D3D11)',
                        'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)',
                        'ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11)',
                        'ANGLE (Intel, Intel(R) UHD Graphics 770 Direct3D11 vs_5_0 ps_5_0, D3D11)',
                        'ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)',
                        'ANGLE (AMD, AMD Radeon RX 7800 XT Direct3D11 vs_5_0 ps_5_0, D3D11)',
                    ];
                    window.__webglRenderer = renderers[Math.floor(Math.random() * renderers.length)];
                }
                return window.__webglRenderer;
            }
            return getParameter2.call(this, parameter);
        };
    }
})()
"""


# ---------------------------------------------------------------------------
# 随机延迟工具
# ---------------------------------------------------------------------------
async def random_click_delay():
    """点击前的随机延迟：50-200ms"""
    delay = random.uniform(0.05, 0.20)
    await asyncio.sleep(delay)


async def random_navigation_delay():
    """页面导航后的随机延迟：500-1500ms"""
    delay = random.uniform(0.5, 1.5)
    await asyncio.sleep(delay)


async def random_action_delay(min_ms: float = 50, max_ms: float = 200):
    """通用操作间随机延迟，单位毫秒"""
    delay = random.uniform(min_ms / 1000, max_ms / 1000)
    await asyncio.sleep(delay)


# ---------------------------------------------------------------------------
# 贝塞尔曲线鼠标移动模拟
# ---------------------------------------------------------------------------
def _bezier_curve(
    start: Tuple[float, float],
    end: Tuple[float, float],
    control1: Tuple[float, float],
    control2: Tuple[float, float],
    t: float,
) -> Tuple[float, float]:
    """计算三阶贝塞尔曲线上的点 (0 <= t <= 1)"""
    u = 1 - t
    x = u**3 * start[0] + 3 * u**2 * t * control1[0] + 3 * u * t**2 * control2[0] + t**3 * end[0]
    y = u**3 * start[1] + 3 * u**2 * t * control1[1] + 3 * u * t**2 * control2[1] + t**3 * end[1]
    return (x, y)


async def human_like_mouse_move(page, x: float, y: float):
    """
    使用贝塞尔曲线模拟真人鼠标移动轨迹。
    从当前位置移动到目标 (x, y)，路径带有随机曲线和速度变化。

    Args:
        page: Playwright Page 对象
        x: 目标 x 坐标
        y: 目标 y 坐标
    """
    # 获取当前鼠标位置（默认从视口中心附近开始）
    viewport = page.viewport_size or {"width": 1440, "height": 900}
    start_x = random.uniform(viewport["width"] * 0.3, viewport["width"] * 0.7)
    start_y = random.uniform(viewport["height"] * 0.3, viewport["height"] * 0.7)

    # 随机生成两个控制点，使轨迹带有自然弧度
    dist_x = x - start_x
    dist_y = y - start_y
    ctrl1_x = start_x + dist_x * random.uniform(0.1, 0.4) + random.uniform(-80, 80)
    ctrl1_y = start_y + dist_y * random.uniform(0.1, 0.4) + random.uniform(-80, 80)
    ctrl2_x = start_x + dist_x * random.uniform(0.6, 0.9) + random.uniform(-80, 80)
    ctrl2_y = start_y + dist_y * random.uniform(0.6, 0.9) + random.uniform(-80, 80)

    # 步数根据距离动态调整
    distance = ((dist_x ** 2 + dist_y ** 2) ** 0.5)
    steps = max(15, min(50, int(distance / 10)))

    for i in range(steps + 1):
        t = i / steps
        # 添加微小的随机抖动，模拟手抖
        jitter_x = random.uniform(-1.5, 1.5)
        jitter_y = random.uniform(-1.5, 1.5)
        px, py = _bezier_curve(
            (start_x, start_y), (x, y),
            (ctrl1_x, ctrl1_y), (ctrl2_x, ctrl2_y),
            t,
        )
        await page.mouse.move(px + jitter_x, py + jitter_y)
        # 速度变化：开头和结尾慢，中间快（模拟真人手臂运动）
        speed_factor = 1.0 - abs(t - 0.5) * 0.6  # 0.7 ~ 1.0 ~ 0.7
        base_delay = random.uniform(0.005, 0.02) / speed_factor
        # 偶尔有更长停顿（模拟微犹豫）
        if random.random() < 0.05:
            base_delay += random.uniform(0.03, 0.1)
        await asyncio.sleep(base_delay)


async def human_like_click(page, selector: str):
    """
    真人模拟点击：先移动鼠标到目标（带随机偏移），再点击。

    Args:
        page: Playwright Page 对象
        selector: CSS 选择器
    """
    element = await page.query_selector(selector)
    if not element:
        logger.warning(f"human_like_click: 未找到元素 {selector}")
        return

    box = await element.bounding_box()
    if not box:
        logger.warning(f"human_like_click: 元素 {selector} 不可见")
        return

    # 目标位置加随机偏移（不精确点中心）
    target_x = box["x"] + box["width"] * random.uniform(0.2, 0.8)
    target_y = box["y"] + box["height"] * random.uniform(0.2, 0.8)

    # 移动鼠标
    await human_like_mouse_move(page, target_x, target_y)

    # 点击前随机延迟 50-300ms
    await asyncio.sleep(random.uniform(0.05, 0.30))

    await page.mouse.click(target_x, target_y)

    # 点击后随机延迟 100-500ms
    await asyncio.sleep(random.uniform(0.10, 0.50))


async def human_like_type(page, selector: str, text: str):
    """
    真人模拟输入：逐字符输入，带有随机延迟和偶尔停顿。

    Args:
        page: Playwright Page 对象
        selector: CSS 选择器
        text: 要输入的文本
    """
    element = await page.query_selector(selector)
    if not element:
        logger.warning(f"human_like_type: 未找到元素 {selector}")
        return

    await element.click()
    await asyncio.sleep(random.uniform(0.1, 0.3))

    for i, char in enumerate(text):
        await page.keyboard.type(char)

        # 基础字符间延迟 50-200ms
        delay = random.uniform(0.05, 0.20)

        # 偶尔模拟思考停顿（约 8% 概率）
        if random.random() < 0.08:
            delay += random.uniform(0.2, 0.6)

        # 在空格或标点后偶尔多停一下
        if char in " ，。、！？,.!?;:" and random.random() < 0.3:
            delay += random.uniform(0.1, 0.3)

        await asyncio.sleep(delay)


# ---------------------------------------------------------------------------
# 上下文创建辅助函数
# ---------------------------------------------------------------------------
async def apply_stealth_to_context(context):
    """
    向已有的 BrowserContext 注入反检测 JS 脚本。

    Args:
        context: Playwright BrowserContext 对象
    """
    await context.add_init_script(STEALTH_JS)
    logger.info("反检测 JS 脚本已注入上下文")


async def create_stealth_context(
    browser,
    viewport: Optional[Dict[str, int]] = None,
    user_agent: Optional[str] = None,
    **kwargs,
):
    """
    创建带有反检测措施的 BrowserContext。

    随机选取 User-Agent，注入 stealth JS。

    Args:
        browser: Playwright Browser 对象
        viewport: 视口大小，默认 1440x900
        user_agent: 自定义 UA，默认随机选取
        **kwargs: 传递给 browser.new_context() 的其他参数

    Returns:
        配置好反检测的 BrowserContext
    """
    if viewport is None:
        viewport = {"width": 1440, "height": 900}
    if user_agent is None:
        user_agent = get_random_user_agent()

    context = await browser.new_context(
        viewport=viewport,
        user_agent=user_agent,
        **kwargs,
    )
    await apply_stealth_to_context(context)
    logger.info(f"反检测上下文已创建 (UA: {user_agent[:60]}...)")
    return context


async def launch_stealth_browser(
    playwright,
    headless: bool = False,
    extra_args: Optional[List[str]] = None,
    channel: Optional[str] = None,
    **kwargs,
):
    """
    启动带有反检测参数的浏览器（非持久化上下文）。

    Args:
        playwright: async_playwright 实例
        headless: 是否无头模式
        extra_args: 额外 Chromium 参数
        channel: 浏览器频道（如 "msedge"）
        **kwargs: 传递给 chromium.launch() 的其他参数

    Returns:
        Browser 对象
    """
    args = get_browser_args(extra_args)
    launch_kwargs: Dict[str, Any] = {
        "headless": headless,
        "args": args,
    }
    if channel:
        launch_kwargs["channel"] = channel
    launch_kwargs.update(kwargs)

    browser = await playwright.chromium.launch(**launch_kwargs)
    logger.info(f"反检测浏览器已启动 (headless={headless}, channel={channel})")
    return browser


async def launch_stealth_persistent_context(
    playwright,
    context_dir: str,
    headless: bool = False,
    extra_args: Optional[List[str]] = None,
    channel: Optional[str] = None,
    user_agent: Optional[str] = None,
    **kwargs,
):
    """
    启动带有反检测参数的持久化上下文。

    Args:
        playwright: async_playwright 实例
        context_dir: 持久化数据目录
        headless: 是否无头模式
        extra_args: 额外 Chromium 参数
        channel: 浏览器频道（如 "msedge"）
        user_agent: 自定义 UA，默认随机选取
        **kwargs: 传递给 chromium.launch_persistent_context() 的其他参数

    Returns:
        BrowserContext 对象
    """
    if user_agent is None:
        user_agent = get_random_user_agent()

    args = get_browser_args(extra_args)
    launch_kwargs: Dict[str, Any] = {
        "headless": headless,
        "viewport": {"width": 1440, "height": 900},
        "user_agent": user_agent,
        "args": args,
        "ignore_https_errors": True,
    }
    if channel:
        launch_kwargs["channel"] = channel
    launch_kwargs.update(kwargs)

    context = await playwright.chromium.launch_persistent_context(
        context_dir, **launch_kwargs
    )
    await apply_stealth_to_context(context)
    logger.info(f"反检测持久化上下文已创建 (UA: {user_agent[:60]}...)")
    return context
