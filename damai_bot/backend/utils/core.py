import asyncio
import datetime
import json
import os
import sys
import time
import threading
from functools import wraps

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

# 统一日志和通知：委托给 backend.logger / backend.notify
from backend.logger import log as _unified_log
from backend.notify import (
    beep_success as _beep_success,
    beep_failure as _beep_failure,
    beep_warning as _beep_warning,
    beep as _beep,
    notify_success as _notify_success,
    notify_error as _notify_error,
    system_notify as _system_notify,
    show_popup as _show_popup,
)


def log(message: str):
    """统一日志输出，委托给 backend.logger"""
    _unified_log(message)


async def safe_sleep(seconds: float):
    try:
        await asyncio.sleep(seconds)
    except Exception:
        time.sleep(seconds)


def load_json(path: str):
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path: str, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def play_sound(sound_type="success", volume=80, custom_file=None):
    """
    播放声音，委托给 backend.notify
    :param sound_type: "success", "failure", "warning", "custom"
    :param volume: 音量 0-100（仅 pygame 模式生效）
    :param custom_file: 自定义音频文件路径
    """
    try:
        # 如果有自定义文件且 pygame 可用，用 pygame 播放
        if custom_file and os.path.exists(custom_file) and PYGAME_AVAILABLE:
            import pygame as pg
            pg.mixer.init()
            normalized_volume = max(0.0, min(1.0, volume / 100.0))
            sound = pg.mixer.Sound(custom_file)
            sound.set_volume(normalized_volume)
            sound.play()
            return True

        # 否则使用统一的 beep 接口
        if sound_type == "success":
            _beep_success()
        elif sound_type == "failure":
            _beep_failure()
        elif sound_type == "warning":
            _beep_warning()
        else:
            _beep(1500, 700)
        return True
    except Exception as e:
        log(f"播放声音失败: {e}")
        return False


def beep_success():
    """播放成功声音（向后兼容）"""
    _beep_success()


def show_popup(title: str, message: str, level="info", timeout=5):
    """显示增强弹窗，委托给 backend.notify.show_popup"""
    return _show_popup(title, message, level=level, timeout=timeout)


def notify(title: str, message: str):
    """显示通知（向后兼容）"""
    _system_notify(title, message, timeout=5)


def retry_async(retries=3, delay=1.0, backoff=2.0):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            count = 0
            while True:
                try:
                    return await func(*args, **kwargs)
                except Exception as ex:
                    count += 1
                    if count > retries:
                        log(f"重试失败: {func.__name__} 已尝试 {count} 次, 异常: {ex}")
                        raise
                    log(f"执行 {func.__name__} 异常: {ex}, 第{count}次重试 {delay:.2f}s 后...")
                    await asyncio.sleep(delay)
                    delay *= backoff
        return wrapper
    return decorator


async def async_wait_until(target_time_str: str):
    """
    异步等待直到指定时间
    target_time_str: 格式 "YYYY-MM-DD HH:MM:SS"
    """
    target_time = datetime.datetime.strptime(target_time_str, "%Y-%m-%d %H:%M:%S")
    now = datetime.datetime.now()
    if target_time > now:
        delta = (target_time - now).total_seconds()
        log(f"等待 {delta:.2f} 秒直到 {target_time_str}")
        await asyncio.sleep(delta)
    else:
        log(f"目标时间 {target_time_str} 已过，立即执行")


def notify_success(title: str, message: str, play_sound_flag=True):
    """显示成功通知并播放声音，委托给 backend.notify"""
    _notify_success(title, message, play_sound=play_sound_flag)


def notify_error(title: str, message: str, play_sound_flag=True):
    """显示错误通知并播放声音，委托给 backend.notify"""
    _notify_error(title, message, play_sound=play_sound_flag)
