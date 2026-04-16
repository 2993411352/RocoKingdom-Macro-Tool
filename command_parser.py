# -*- coding: utf-8 -*-
"""
洛克王国：世界 — Python 自动化工具
指令解析与执行引擎

支持的指令集:
  鼠标: LMouseDown, LMouseUp, WheelUp, WheelDown
  字母键: QDown/QUp, WDown/WUp, EDown/EUp, RDown/RUp, XDown/XUp, SDown/SUp
  功能键: ShiftDown/ShiftUp, SpaceDown/SpaceUp, Esc, Tab
  精灵切换: C1 ~ C6
  复合: Bow, Press[X]-[Y]-[0], Sound
  延迟: 纯数字 (毫秒)
"""

import re
import time
import random
import threading
import winsound

import pydirectinput

import config
import window_detector

# 禁用 pydirectinput 内置的 pause（我们自己控制延迟）
pydirectinput.PAUSE = 0.0

# ============================================================
# 按键映射表
# ============================================================
# XDown/XUp 格式的按键映射  →  pydirectinput 的键名
_KEY_MAP = {
    'q': 'q', 'w': 'w', 'e': 'e', 'r': 'r',
    'x': 'x', 's': 's', 'i': 'i', 'f': 'f',
}

# Press[X]-[Y]-[0] 正则
_PRESS_PATTERN = re.compile(r'^Press(\d+)-(\d+)-(\d+)$', re.IGNORECASE)


def parse(script_string: str) -> list[str]:
    """
    将宏脚本字符串解析为指令列表。
    支持空格和换行作为分隔符。
    """
    commands = script_string.replace('\n', ' ').replace('\r', ' ').split()
    return [c.strip() for c in commands if c.strip()]


def execute(cmd: str, stop_event: threading.Event) -> bool:
    """
    解析并执行单条指令。

    参数:
        cmd: 指令字符串
        stop_event: 停止事件，用于检查是否需要中断

    返回:
        True  — 指令执行成功，可以继续
        False — 需要停止（窗口失焦或收到停止信号）
    """
    # 每条指令执行前检查停止信号
    if stop_event.is_set():
        return False

    # ----------------------------------------------------------
    # 1) 纯数字 → 延迟 (毫秒)
    # ----------------------------------------------------------
    if cmd.isdigit():
        delay_sec = int(cmd) / 1000.0
        # 增加 10 ~ 80 毫秒的随机延时防检测
        fuzz = random.uniform(0.01, 0.08)
        # 将长延迟拆分为短段，以便及时响应停止信号
        _interruptible_sleep(delay_sec + fuzz, stop_event)
        return not stop_event.is_set()

    # ----------------------------------------------------------
    # 2) 鼠标操作
    # ----------------------------------------------------------
    if cmd == 'LMouseDown':
        pydirectinput.mouseDown(button='left')
        _fuzzed_sleep(config.MOUSE_CLICK_DELAY)
        return True

    if cmd == 'LMouseUp':
        pydirectinput.mouseUp(button='left')
        _fuzzed_sleep(config.MOUSE_CLICK_DELAY)
        return True

    if cmd == 'WheelUp':
        pydirectinput.scroll(3)
        _fuzzed_sleep(config.MOUSE_CLICK_DELAY)
        return True

    if cmd == 'WheelDown':
        pydirectinput.scroll(-3)
        _fuzzed_sleep(config.MOUSE_CLICK_DELAY)
        return True

    # ----------------------------------------------------------
    # 3) 字母键 Down / Up
    # ----------------------------------------------------------
    for letter, key_name in _KEY_MAP.items():
        up_cmd = f'{letter.upper()}Up'
        down_cmd = f'{letter.upper()}Down'
        if cmd == down_cmd:
            pydirectinput.keyDown(key_name)
            _fuzzed_sleep(config.KEY_DOWN_UP_GAP)
            return True
        if cmd == up_cmd:
            pydirectinput.keyUp(key_name)
            _fuzzed_sleep(config.KEY_DOWN_UP_GAP)
            return True

    # ----------------------------------------------------------
    # 4) Shift / Space Down / Up
    # ----------------------------------------------------------
    if cmd == 'ShiftDown':
        pydirectinput.keyDown('shift')
        _fuzzed_sleep(config.KEY_DOWN_UP_GAP)
        return True
    if cmd == 'ShiftUp':
        pydirectinput.keyUp('shift')
        _fuzzed_sleep(config.KEY_DOWN_UP_GAP)
        return True
    if cmd == 'SpaceDown':
        pydirectinput.keyDown('space')
        _fuzzed_sleep(config.KEY_DOWN_UP_GAP)
        return True
    if cmd == 'SpaceUp':
        pydirectinput.keyUp('space')
        _fuzzed_sleep(config.KEY_DOWN_UP_GAP)
        return True

    # ----------------------------------------------------------
    # 5) Esc / Tab — press (按下再释放)
    # ----------------------------------------------------------
    if cmd == 'Esc':
        pydirectinput.keyDown('escape')
        _fuzzed_sleep(config.KEY_PRESS_DELAY)
        pydirectinput.keyUp('escape')
        _fuzzed_sleep(config.KEY_PRESS_DELAY)
        return True

    if cmd == 'Tab':
        pydirectinput.keyDown('tab')
        _fuzzed_sleep(config.KEY_PRESS_DELAY)
        pydirectinput.keyUp('tab')
        _fuzzed_sleep(config.KEY_PRESS_DELAY)
        return True

    # ----------------------------------------------------------
    # 6) C1 ~ C6 — 精灵切换（数字键 1-6 + 微延迟）
    # ----------------------------------------------------------
    if len(cmd) == 2 and cmd[0].upper() == 'C' and cmd[1] in '123456':
        key = cmd[1]
        pydirectinput.keyDown(key)
        _fuzzed_sleep(config.KEY_PRESS_DELAY)
        pydirectinput.keyUp(key)
        _fuzzed_sleep(config.KEY_PRESS_DELAY)
        return True

    # ----------------------------------------------------------
    # 7) Bow — 鞠躬
    # ----------------------------------------------------------
    if cmd == 'Bow':
        pydirectinput.keyDown(config.BOW_KEY)
        _fuzzed_sleep(config.KEY_PRESS_DELAY)
        pydirectinput.keyUp(config.BOW_KEY)
        _fuzzed_sleep(config.KEY_PRESS_DELAY)
        return True

    # ----------------------------------------------------------
    # 8) Sound — 声音提示
    # ----------------------------------------------------------
    if cmd == 'Sound':
        try:
            winsound.Beep(config.BEEP_FREQUENCY, config.BEEP_DURATION)
        except RuntimeError:
            pass  # 某些环境下 Beep 可能失败
        return True

    # ----------------------------------------------------------
    # 9) Press[X]-[Y]-[0] — 绝对坐标点击
    # ----------------------------------------------------------
    match = _PRESS_PATTERN.match(cmd)
    if match:
        raw_x, raw_y, button = int(match.group(1)), int(match.group(2)), int(match.group(3))
        # 坐标缩放
        screen_size = window_detector.get_game_window_size()
        if screen_size:
            cur_w, cur_h = screen_size
        else:
            # 后备：使用当前屏幕分辨率
            cur_w = pydirectinput.size()[0]
            cur_h = pydirectinput.size()[1]
        base_w, base_h = config.BASE_RESOLUTION
        scaled_x = int(raw_x * cur_w / base_w)
        scaled_y = int(raw_y * cur_h / base_h)

        # 需要加上窗口偏移
        rect = window_detector.get_foreground_window_rect()
        if rect:
            scaled_x += rect[0]
            scaled_y += rect[1]

        pydirectinput.moveTo(scaled_x, scaled_y)
        _fuzzed_sleep(config.MOUSE_CLICK_DELAY)
        if button == 0:
            pydirectinput.click(scaled_x, scaled_y, button='left')
        else:
            pydirectinput.click(scaled_x, scaled_y, button='right')
        _fuzzed_sleep(config.MOUSE_CLICK_DELAY)
        return True

    # ----------------------------------------------------------
    # 未知指令 → 警告但不中断
    # ----------------------------------------------------------
    print(f"  [!] 未知指令: {cmd}")
    return True

def _fuzzed_sleep(base_time: float):
    """加上微小随机延时（10~40毫秒）的睡眠，破坏规律特征防封"""
    time.sleep(base_time + random.uniform(0.01, 0.04))


def _interruptible_sleep(seconds: float, stop_event: threading.Event,
                         granularity: float = 0.1):
    """
    可中断的 sleep：将总延迟拆分为小段，期间轮询 stop_event。
    """
    elapsed = 0.0
    while elapsed < seconds:
        if stop_event.is_set():
            return
        chunk = min(granularity, seconds - elapsed)
        time.sleep(chunk)
        elapsed += chunk
