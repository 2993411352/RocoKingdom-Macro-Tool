# -*- coding: utf-8 -*-
"""
洛克王国：世界 — Python 自动化工具
宏执行引擎

状态机驱动的宏执行器，支持:
  - 窗口失焦自动暂停 / 恢复
  - 果冻状态检测 + 自动按 X 恢复
  - 可中断的循环执行
"""

import time
import random
import threading
from enum import Enum

import pydirectinput

import config
import command_parser
import window_detector
from vision_detector import VisionDetector


class MacroState(Enum):
    """宏引擎运行状态。"""
    IDLE = "空闲"
    RUNNING = "运行中"
    PAUSED_WINDOW = "暂停（窗口失焦）"
    JELLY_RECOVERY = "恢复中（果冻）"
    STOPPING = "停止中"


class MacroEngine:
    """
    宏执行引擎。

    使用方法:
        engine = MacroEngine()
        engine.start(preset_key="single_6")  # 启动预设
        engine.stop()                          # 停止
        engine.toggle(preset_key="single_6")   # 热键切换
    """

    def __init__(self):
        self._state = MacroState.IDLE
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._vision = VisionDetector()

        # 当前使用的预设名称（仅用于 toggle 记忆）
        self._current_preset_key: str = "single_6"

        # 统计
        self._commands_executed = 0
        self._jelly_recoveries = 0
        self._loop_count = 0

    # ──────────────────────────────────────────────
    # 公开属性
    # ──────────────────────────────────────────────

    @property
    def state(self) -> MacroState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._state not in (MacroState.IDLE, MacroState.STOPPING)

    @property
    def stats(self) -> dict:
        return {
            "commands_executed": self._commands_executed,
            "jelly_recoveries": self._jelly_recoveries,
            "loop_count": self._loop_count,
        }

    # ──────────────────────────────────────────────
    # 控制方法
    # ──────────────────────────────────────────────

    def start(self, init_commands: str, loop_commands: str, preset_key: str = ""):
        """
        启动宏执行。

        参数:
            init_commands: 初始化指令字符串（一次性执行）
            loop_commands: 循环指令字符串（持续执行）
            preset_key: 预设名称（可选，仅用于显示）
        """
        if self.is_running:
            print("  [引擎] [!] 宏已在运行中，请先停止")
            return

        if not loop_commands.strip():
            print("  [引擎] [X] 循环指令为空，无法启动")
            return

        self._stop_event.clear()
        self._commands_executed = 0
        self._jelly_recoveries = 0
        self._loop_count = 0

        if preset_key:
            self._current_preset_key = preset_key

        # 启动视觉检测
        self._vision.start()

        # 启动执行线程
        self._thread = threading.Thread(
            target=self._run,
            args=(init_commands, loop_commands),
            name="MacroEngine",
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        """停止宏执行。"""
        if not self.is_running:
            return
        print("  [引擎] [STOP] 正在停止...")
        self._state = MacroState.STOPPING
        self._stop_event.set()
        self._vision.stop()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._state = MacroState.IDLE
        self._print_stats()

    def toggle(self, init_commands: str = "", loop_commands: str = "",
               preset_key: str = ""):
        """热键触发：启动或停止。"""
        if self.is_running:
            self.stop()
        else:
            self.start(init_commands, loop_commands, preset_key)

    # ──────────────────────────────────────────────
    # 主执行流程
    # ──────────────────────────────────────────────

    def _run(self, init_commands: str, loop_commands: str):
        """主执行线程。"""
        self._state = MacroState.PAUSED_WINDOW
        print("  [引擎] [PAUSE] 等待游戏窗口激活以开始...")
        
        # Phase 1: 等待目标窗口 (不触发恢复指令)
        while not window_detector.is_target_window_active():
            if self._stop_event.is_set():
                self._state = MacroState.IDLE
                return
            time.sleep(config.WINDOW_CHECK_INTERVAL)
            
        self._state = MacroState.RUNNING
        print("  [引擎] [>] 宏开始执行")

        # Phase 2: 执行初始化指令
        if init_commands.strip():
            print("  [引擎] [INIT] 执行初始化指令...")
            init_list = command_parser.parse(init_commands)
            if not self._execute_sequence(init_list):
                self._finalize()
                return
            print("  [引擎] [OK] 初始化完成")

        # Phase 3: 循环执行
        loop_list = command_parser.parse(loop_commands)
        print(f"  [引擎] [LOOP] 进入循环 ({len(loop_list)} 条指令/轮)")
        
        # RE-INIT 计时器：只计算正常运行时间，不计入窗口等待或果冻恢复时间
        self._reinit_active_start = time.time()
        self._reinit_accumulated = 0.0

        while not self._stop_event.is_set():
            # 检查是否需要每隔一段时间重新执行初始化指令
            if hasattr(config, 'REINIT_INTERVAL') and config.REINIT_INTERVAL > 0:
                active_time = self._reinit_accumulated + (time.time() - self._reinit_active_start)
                if active_time >= config.REINIT_INTERVAL:
                    if init_commands.strip():
                        print(f"  [引擎] [RE-INIT] 运行满 {config.REINIT_INTERVAL} 秒，正在重新执行初始化指令补发精灵...")
                        if not self._execute_sequence(command_parser.parse(init_commands)):
                            break
                        # 重置计时器
                        self._reinit_active_start = time.time()
                        self._reinit_accumulated = 0.0

            self._loop_count += 1
            if not self._execute_sequence(loop_list):
                break

        self._finalize()

    def _execute_sequence(self, commands: list[str]) -> bool:
        """
        顺序执行指令列表。

        在每条指令执行前进行检查:
          1. 停止信号
          2. 果冻状态 → 恢复
          3. 窗口焦点 → 暂停/等待

        返回:
            True  — 全部指令执行完成
            False — 被中断（停止或超时）
        """
        for cmd in commands:
            if self._stop_event.is_set():
                return False

            # ── 视觉预警检查 (果冻/关闭弹窗) ──
            if not self._handle_visual_triggers():
                return False

            # ── 窗口焦点检查 ──
            if not self._handle_window_check():
                return False

            # ── 执行指令 ──
            self._state = MacroState.RUNNING
            success = command_parser.execute(cmd, self._stop_event)
            if not success:
                return False
            self._commands_executed += 1

            # 指令间小间隙 (+微量随机延时)
            time.sleep(config.COMMAND_GAP + random.uniform(0.01, 0.04))

        return True

    # ──────────────────────────────────────────────
    # 果冻恢复
    # ──────────────────────────────────────────────

    def _handle_visual_triggers(self) -> bool:
        """
        检查视觉状态（果冻或弹窗），如果检测到则执行恢复。
        返回 True 表示可以继续，False 表示由于严重状态（如果是果冻中断循环）需要重新开始指令。
        """
        # =======================
        # 1. 关窗口弹窗抢救
        # =======================
        if self._vision.is_close_button:
            print("  [引擎] [!] 被弹窗遮挡，正在点击 X 按钮自动关闭...")
            x, y = self._vision.get_close_coords()
            
            # 保存当前鼠标位置以备后用
            orig_pos = pydirectinput.position()
            
            # 点击关闭按钮
            pydirectinput.moveTo(x, y)
            time.sleep(config.MOUSE_CLICK_DELAY + random.uniform(0.01, 0.03))
            pydirectinput.click(button='left')
            time.sleep(config.MOUSE_CLICK_DELAY + random.uniform(0.1, 0.2))
            
            # 重设鼠标坐标
            pydirectinput.moveTo(orig_pos[0], orig_pos[1])
            
            self._vision.clear_close()
            print("  [引擎] [!] 弹窗已清理，恢复当前操作。")
            # 关个菜单而已，没必要打断当前连招，直接继续
            return True

        # =======================
        # 2. 判断是否变成变成
        # =======================
        if not self._vision.is_jelly:
            return True

        self._state = MacroState.JELLY_RECOVERY
        print("  [引擎] [JELLY] 进入果冻恢复流程")

        for attempt in range(1, config.JELLY_RECOVERY_MAX_RETRIES + 1):
            if self._stop_event.is_set():
                return False

            print(f"  [引擎]   恢复尝试 {attempt}/{config.JELLY_RECOVERY_MAX_RETRIES}")

            # 确保窗口在前台
            if not window_detector.is_target_window_active():
                print("  [引擎]   窗口失焦，等待中...")
                if not self._wait_for_window():
                    return False

            # 按 X 解除果冻
            pydirectinput.keyDown(config.JELLY_RECOVERY_KEY)
            time.sleep(config.KEY_PRESS_DELAY + random.uniform(0.01, 0.03))
            pydirectinput.keyUp(config.JELLY_RECOVERY_KEY)
            time.sleep(config.JELLY_RECOVERY_WAIT + random.uniform(0.1, 0.3))

            # 清除果冻标志，等待视觉检测器重新判定
            self._vision.clear_jelly()
            time.sleep(config.JELLY_RECOVERY_RETRY_INTERVAL)

            # 再次检查是否仍处于果冻状态
            if not self._vision.is_jelly:
                print("  [引擎] [OK] 果冻恢复成功！")
                self._jelly_recoveries += 1

                # 恢复后重置 UI 状态
                self._execute_recovery_commands()
                return True

        # 达到最大重试次数
        print("  [引擎] [X] 果冻恢复失败，已达最大重试次数")

        # 即使恢复失败也清除标志，尝试继续
        self._vision.clear_jelly()
        self._execute_recovery_commands()
        return True

    def _execute_recovery_commands(self):
        """执行恢复指令序列，重置 UI 状态。"""
        recovery_cmds = config.REFOCUS_RECOVERY_COMMANDS
        print("  [引擎]   执行 UI 状态重置...")
        for cmd in recovery_cmds:
            if self._stop_event.is_set():
                return
            command_parser.execute(cmd, self._stop_event)

    # ──────────────────────────────────────────────
    # 窗口焦点管理
    # ──────────────────────────────────────────────

    def _handle_window_check(self) -> bool:
        """
        检查窗口焦点。如果失焦，暂停并等待重新获得焦点。
        返回 True 表示窗口恢复（可继续），False 表示超时或停止。
        """
        if window_detector.is_target_window_active():
            return True

        return self._wait_for_window()

    def _wait_for_window(self) -> bool:
        """
        等待目标窗口获得焦点。

        返回 True 表示窗口已恢复，False 表示超时或收到停止信号。
        """
        prev_state = self._state
        self._state = MacroState.PAUSED_WINDOW
        print("  [引擎] [PAUSE] 窗口失焦，已暂停 (等待目标窗口回到前台...)")

        # 冻结 RE-INIT 计时器（只在有该属性时生效）
        if hasattr(self, '_reinit_active_start'):
            self._reinit_accumulated += (time.time() - self._reinit_active_start)

        start_time = time.time()
        while not self._stop_event.is_set():
            if window_detector.is_target_window_active():
                print("  [引擎] [>] 窗口恢复，继续执行")
                self._state = MacroState.RUNNING

                # 恢复 RE-INIT 计时器
                if hasattr(self, '_reinit_active_start'):
                    self._reinit_active_start = time.time()

                # 窗口恢复时执行重置指令
                if prev_state == MacroState.RUNNING:
                    self._execute_recovery_commands()
                return True

            # 检查超时
            if time.time() - start_time > config.WINDOW_REFOCUS_TIMEOUT:
                print(f"  [引擎] [X] 窗口恢复等待超时 ({config.WINDOW_REFOCUS_TIMEOUT}s)")
                # 超时后重置计时器，继续等待（不放弃）
                start_time = time.time()
                print("  [引擎]   继续等待窗口...")

            time.sleep(config.WINDOW_CHECK_INTERVAL)

        return False

    # ──────────────────────────────────────────────
    # 辅助
    # ──────────────────────────────────────────────

    def _finalize(self):
        """清理并进入空闲状态。"""
        self._vision.stop()
        self._state = MacroState.IDLE
        self._print_stats()
        print("  [引擎] [STOP] 宏已停止")

    def _print_stats(self):
        """打印统计信息。"""
        print(f"\n  -- 运行统计 --")
        print(f"  总循环次数:       {self._loop_count}")
        print(f"  执行指令条数:     {self._commands_executed}")
        print(f"  果冻恢复次数:     {self._jelly_recoveries}")
        print()
