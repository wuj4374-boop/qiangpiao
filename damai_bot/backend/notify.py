"""
大麦抢票系统 - 跨平台通知模块

本文件为 Web 自动化技术学习示例，仅供开发者学习研究使用。

技术要点：
- 跨平台声音提示：Windows (winsound) / macOS (afplay) / Linux (终端蜂鸣)
- 跨平台系统通知：Windows (plyer/PowerShell toast) / macOS (osascript) / Linux (notify-send)
- PySide6 弹窗通知（可选依赖）

作者：小吴 (Xiao Wu)
许可证：MIT
"""

import os
import sys
import subprocess

from backend.logger import get_logger

logger = get_logger("notify")

# ── 平台检测 ──

IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")


# ── 声音提示 ──

def beep(frequency: int = 2000, duration: int = 800):
    """
    跨平台蜂鸣声
    :param frequency: 频率（Hz），仅 Windows 生效
    :param duration: 时长（ms），仅 Windows 生效
    """
    try:
        if IS_WINDOWS:
            import winsound
            winsound.Beep(frequency, duration)
        elif IS_MACOS:
            # macOS: 使用 afplay 播放系统声音
            subprocess.Popen(
                ["afplay", "/System/Library/Sounds/Glass.aiff"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            # Linux: 终端蜂鸣
            print("\a", end="", flush=True)
    except Exception as e:
        logger.warning("播放声音失败: %s", e)


def beep_success():
    """播放成功提示音"""
    beep(frequency=2000, duration=800)


def beep_failure():
    """播放失败提示音"""
    beep(frequency=800, duration=1000)


def beep_warning():
    """播放警告提示音"""
    beep(frequency=1200, duration=600)


# ── 系统通知 ──

def system_notify(title: str, message: str, timeout: int = 5):
    """
    跨平台系统通知

    :param title: 通知标题
    :param message: 通知内容
    :param timeout: 显示时长（秒）
    """
    try:
        if IS_WINDOWS:
            _windows_notify(title, message, timeout)
        elif IS_MACOS:
            _macos_notify(title, message)
        else:
            _linux_notify(title, message, timeout)
    except Exception as e:
        logger.warning("系统通知失败: %s", e)
        # 回退到控制台输出
        logger.info("通知: %s - %s", title, message)


def _windows_notify(title: str, message: str, timeout: int = 5):
    """Windows 系统通知"""
    # 优先使用 plyer
    try:
        from plyer import notification as plyer_notification
        plyer_notification.notify(title=title, message=message, timeout=timeout)
        return
    except ImportError:
        pass
    except Exception:
        pass

    # 回退到 PowerShell toast notification
    try:
        ps_script = f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

        $template = @"
<toast>
    <visual>
        <binding template="ToastGeneric">
            <text>{title}</text>
            <text>{message}</text>
        </binding>
    </visual>
</toast>
"@

        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml($template)
        $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("大麦抢票").Show($toast)
        """
        subprocess.Popen(
            ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        logger.debug("PowerShell 通知失败: %s", e)


def _macos_notify(title: str, message: str):
    """macOS 系统通知（osascript）"""
    script = f'display notification "{message}" with title "{title}"'
    subprocess.Popen(
        ["osascript", "-e", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _linux_notify(title: str, message: str, timeout: int = 5):
    """Linux 系统通知（notify-send）"""
    subprocess.Popen(
        ["notify-send", title, message, f"--expire-time={timeout * 1000}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# ── 高级通知接口 ──

def notify_success(title: str, message: str, play_sound: bool = True):
    """
    成功通知：播放成功声音 + 显示系统通知

    :param title: 通知标题
    :param message: 通知内容
    :param play_sound: 是否播放声音
    """
    if play_sound:
        beep_success()
    system_notify(title, message, timeout=5)


def notify_error(title: str, message: str, play_sound: bool = True):
    """
    错误通知：播放失败声音 + 显示系统通知

    :param title: 通知标题
    :param message: 通知内容
    :param play_sound: 是否播放声音
    """
    if play_sound:
        beep_failure()
    system_notify(title, message, timeout=8)


def notify_warning(title: str, message: str, play_sound: bool = True):
    """
    警告通知：播放警告声音 + 显示系统通知

    :param title: 通知标题
    :param message: 通知内容
    :param play_sound: 是否播放声音
    """
    if play_sound:
        beep_warning()
    system_notify(title, message, timeout=6)


# ── PySide6 弹窗（可选，从 core.py 迁移） ──

def show_popup(title: str, message: str, level: str = "info", timeout: int = 5):
    """
    显示 PySide6 弹窗（如可用），否则回退到系统通知

    :param title: 标题
    :param message: 消息内容
    :param level: "info", "success", "warning", "error"
    :param timeout: 自动关闭时间（秒），0 表示不自动关闭
    """
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        from PySide6.QtCore import QTimer
        import threading

        def show_dialog():
            app = QApplication.instance()
            if not app:
                app = QApplication([])

            msg_box = QMessageBox()
            msg_box.setWindowTitle(title)
            msg_box.setText(message)

            if level == "success":
                msg_box.setIcon(QMessageBox.Icon.Information)
            elif level == "warning":
                msg_box.setIcon(QMessageBox.Icon.Warning)
            elif level == "error":
                msg_box.setIcon(QMessageBox.Icon.Critical)
            else:
                msg_box.setIcon(QMessageBox.Icon.Information)

            msg_box.setStyleSheet("""
                QMessageBox { background-color: #1e1e1e; color: #ffffff; }
                QMessageBox QLabel { color: #ffffff; }
                QMessageBox QPushButton {
                    background-color: #333333; color: #ffffff;
                    border: 1px solid #555555; padding: 5px 15px;
                }
                QMessageBox QPushButton:hover { background-color: #444444; }
            """)

            if timeout > 0:
                timer = QTimer()
                timer.timeout.connect(msg_box.close)
                timer.start(timeout * 1000)

            msg_box.exec()

        if threading.current_thread() == threading.main_thread():
            show_dialog()
        else:
            from PySide6.QtCore import QMetaObject, Qt, Q_ARG
            QMetaObject.invokeMethod(
                QApplication.instance(), show_dialog,
                Qt.ConnectionType.QueuedConnection,
            )
        return True

    except ImportError:
        # PySide6 不可用，回退到系统通知
        system_notify(title, message, timeout=timeout)
        return True
    except Exception as e:
        logger.warning("显示弹窗失败: %s", e)
        system_notify(title, message, timeout=timeout)
        return False
