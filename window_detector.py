# -*- coding: utf-8 -*-
"""
洛克王国：世界 — Python 自动化工具
窗口检测模块

使用原生 ctypes 调用 user32.dll，零外部依赖。
"""

import ctypes
import ctypes.wintypes as wintypes

import config

# Windows API 函数
user32 = ctypes.windll.user32


def get_foreground_window_title() -> str:
    """获取当前前台窗口的标题字符串。"""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def is_target_window_active() -> bool:
    """
    判断当前前台窗口标题是否同时包含所有关键词。
    关键词在 config.WINDOW_KEYWORDS 中定义。
    """
    title = get_foreground_window_title()
    if not title:
        return False
    return all(kw in title for kw in config.WINDOW_KEYWORDS)


def get_foreground_window_rect() -> tuple | None:
    """
    获取当前前台窗口的客户区矩形 (left, top, right, bottom)。
    如果前台窗口不是目标游戏窗口，返回 None。
    """
    if not is_target_window_active():
        return None

    hwnd = user32.GetForegroundWindow()
    rect = wintypes.RECT()
    # 获取客户区在屏幕上的坐标
    client_point = wintypes.POINT(0, 0)
    ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(client_point))
    ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect))

    left = client_point.x
    top = client_point.y
    right = left + rect.right
    bottom = top + rect.bottom
    return (left, top, right, bottom)


def get_game_window_size() -> tuple | None:
    """
    获取游戏窗口的客户区尺寸 (width, height)。
    """
    rect = get_foreground_window_rect()
    if rect is None:
        return None
    left, top, right, bottom = rect
    return (right - left, bottom - top)


if __name__ == "__main__":
    # 测试用
    import time
    print("3 秒后检测前台窗口…")
    time.sleep(3)
    title = get_foreground_window_title()
    print(f"前台窗口标题: {title}")
    print(f"是否为目标窗口: {is_target_window_active()}")
    rect = get_foreground_window_rect()
    print(f"窗口区域: {rect}")
    size = get_game_window_size()
    print(f"窗口尺寸: {size}")
