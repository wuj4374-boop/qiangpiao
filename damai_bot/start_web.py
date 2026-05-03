"""
大麦抢票系统 - 一键启动脚本

本文件为 Web 自动化技术学习示例，仅供开发者学习研究使用。
请勿用于任何商业或非法用途。使用前请阅读项目根目录下的 DISCLAIMER.md。

功能：启动 FastAPI 后端服务 + 自动打开浏览器
使用方式：python start_web.py

作者：小吴 (Xiao Wu)
许可证：MIT
"""

import signal
import subprocess
import sys
import time
import webbrowser
from urllib.request import urlopen
from urllib.error import URLError

HOST = "0.0.0.0"
PORT = 8000
URL = f"http://127.0.0.1:{PORT}"
HEALTH_URL = f"{URL}/health"
MAX_WAIT = 30  # 最长等待秒数


def wait_for_backend():
    """轮询 /health 直到后端就绪"""
    print(f"等待后端就绪 ({HEALTH_URL}) ...")
    start = time.time()
    while time.time() - start < MAX_WAIT:
        try:
            resp = urlopen(HEALTH_URL, timeout=2)
            if resp.status == 200:
                return True
        except (URLError, OSError):
            pass
        time.sleep(0.5)
    return False


def main():
    print("=" * 50)
    print("  大麦抢票系统 - 一键启动")
    print("=" * 50)
    print(f"后端地址: {URL}")
    print()

    # 启动 uvicorn 后端
    print("正在启动后端服务...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.light_server:app",
         "--host", HOST, "--port", str(PORT)],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parent),
    )

    # 优雅退出：Ctrl+C 时终止子进程
    def shutdown(sig=None, frame=None):
        print("\n正在关闭后端服务...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("已退出。")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # 等待后端就绪
    if wait_for_backend():
        print("后端已就绪！")
        print(f"正在打开浏览器: {URL}")
        webbrowser.open(URL)
    else:
        print(f"警告: 后端在 {MAX_WAIT} 秒内未就绪，请手动访问 {URL}")

    print()
    print("按 Ctrl+C 停止服务")
    print("-" * 50)

    # 保持主线程运行
    try:
        proc.wait()
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
