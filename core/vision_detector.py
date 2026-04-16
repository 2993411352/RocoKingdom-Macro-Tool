# -*- coding: utf-8 -*-
"""
洛克王国：世界 — Python 自动化工具
视觉检测模块 — 果冻状态识别 (X 图标)

工作原理：
  1. 在独立线程中以固定间隔截取游戏窗口的指定区域 (ROI)
  2. 使用 OpenCV 模板匹配检测 X 图标是否出现
  3. 匹配成功 → 设置果冻标志 → 宏引擎暂停并执行恢复动作
"""

import os
import time
import threading

import cv2
import numpy as np
from mss import mss

import config
from core import window_detector


class VisionDetector:
    """
    果冻状态视觉检测器。

    使用方法：
        detector = VisionDetector()
        detector.start()       # 启动后台检测线程
        ...
        if detector.is_jelly:  # 外部轮询果冻状态
            detector.clear_jelly()
        ...
        detector.stop()        # 停止检测
    """

    def __init__(self):
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        # 果冻状态标志 (线程安全)
        self._jelly_flag = threading.Event()

        # 关闭按钮标志和坐标
        self._close_flag = threading.Event()
        self._close_coords = (0, 0)

        # 加载模板图片
        self._template = None
        self._template_loaded = False
        self._close_template = None
        self._close_template_loaded = False
        self._load_templates()

    # ──────────────────────────────────────────────
    # 公开属性 / 方法
    # ──────────────────────────────────────────────

    @property
    def is_jelly(self) -> bool:
        """当前是否处于果冻状态。"""
        return self._jelly_flag.is_set()

    def clear_jelly(self):
        """外部恢复完成后清除果冻标志。"""
        self._jelly_flag.clear()

    @property
    def is_close_button(self) -> bool:
        """当前是否检测到关闭按钮弹窗。"""
        return self._close_flag.is_set()

    def get_close_coords(self) -> tuple[int, int]:
        """获取关闭按钮的绝对中心点坐标。"""
        return self._close_coords

    def clear_close(self):
        """外部点击完成后清除关闭标志。"""
        self._close_flag.clear()

    @property
    def template_loaded(self) -> bool:
        """模板图片是否已加载。"""
        return self._template_loaded

    def start(self):
        """启动后台检测线程。"""
        if not self._template_loaded and not self._close_template_loaded:
            print("  [视觉检测] [!] 没有任何模板图片，视觉检测功能未完全发挥作用。")
        self._stop_event.clear()
        self._jelly_flag.clear()
        self._close_flag.clear()
        self._thread = threading.Thread(
            target=self._detection_loop,
            name="VisionDetector",
            daemon=True,
        )
        self._thread.start()
        print("  [视觉检测] [OK] 后台检测线程已启动")

    def stop(self):
        """停止后台检测线程。"""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._jelly_flag.clear()
        print("  [视觉检测] [STOP] 检测线程已停止")

    def check_once(self) -> bool:
        """
        执行一次果冻状态检测。
        返回 True 表示检测到果冻状态。
        可供外部调用用于手动单次检查。
        """
        if not self._template_loaded:
            return False
        return self._do_match()

    def capture_template(self):
        """
        交互式截取模板图片。
        从当前游戏窗口的 ROI 区域截取一张图并保存。
        """
        print("\n  [模板截取] 请先将游戏切换到果冻状态画面，然后按回车键截取...")
        input("  > 按回车键开始截取")

        roi_img = self._capture_roi()
        if roi_img is None:
            print("  [模板截取] [X] 截取失败！请确保游戏窗口处于前台。")
            return False

        os.makedirs(config.TEMPLATES_DIR, exist_ok=True)
        cv2.imwrite(config.JELLY_TEMPLATE_PATH, roi_img)
        print(f"  [模板截取] [OK] 模板已保存到: {config.JELLY_TEMPLATE_PATH}")
        print(f"  [模板截取]   图片尺寸: {roi_img.shape[1]}x{roi_img.shape[0]}")

        # 重新加载模板
        self._load_template()
        return True

    # ──────────────────────────────────────────────
    # 内部方法
    # ──────────────────────────────────────────────

    def _load_templates(self):
        """尝试加载所有模板图片。"""
        # 加载果冻模板
        if os.path.exists(config.JELLY_TEMPLATE_PATH):
            self._template = cv2.imread(config.JELLY_TEMPLATE_PATH, cv2.IMREAD_COLOR)
            if self._template is not None:
                self._template_loaded = True
                h, w = self._template.shape[:2]
                print(f"  [视觉检测] [OK] 果冻模板已加载: {w}x{h}")
        
        # 加载关闭按钮模板
        if os.path.exists(config.CLOSE_TEMPLATE_PATH):
            self._close_template = cv2.imread(config.CLOSE_TEMPLATE_PATH, cv2.IMREAD_COLOR)
            if self._close_template is not None:
                self._close_template_loaded = True
                h, w = self._close_template.shape[:2]
                print(f"  [视觉检测] [OK] 关闭按钮模板已加载: {w}x{h}")

    def _get_roi_coords(self, roi_percent: tuple) -> tuple | None:
        """
        根据游戏窗口位置和传入的 ROI 百分比，计算截图的绝对坐标。
        返回 (left, top, right, bottom) 或 None。
        """
        rect = window_detector.get_foreground_window_rect()
        if rect is None:
            return None

        win_left, win_top, win_right, win_bottom = rect
        win_w = win_right - win_left
        win_h = win_bottom - win_top

        lp, tp, rp, bp = roi_percent
        roi_left = win_left + int(win_w * lp)
        roi_top = win_top + int(win_h * tp)
        roi_right = win_left + int(win_w * rp)
        roi_bottom = win_top + int(win_h * bp)

        return (roi_left, roi_top, roi_right, roi_bottom)

    def _capture_roi(self, roi_percent: tuple) -> tuple[np.ndarray | None, tuple | None]:
        """截取 ROI 区域。返回 (BGR numpy数组, absolute_coords)"""
        coords = self._get_roi_coords(roi_percent)
        if coords is None:
            return None, None

        left, top, right, bottom = coords
        monitor = {
            "left": left,
            "top": top,
            "width": right - left,
            "height": bottom - top,
        }

        try:
            with mss() as sct:
                screenshot = sct.grab(monitor)
                img = np.array(screenshot)
                # mss 返回 BGRA，转为 BGR
                img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                return img_bgr, coords
        except Exception as e:
            print(f"  [视觉检测] 截图异常: {e}")
            return None, None

    def _do_match(self) -> bool:
        """执行果冻模板匹配。"""
        roi_img, _ = self._capture_roi(config.JELLY_ROI_PERCENT)
        if roi_img is None or not self._template_loaded:
            return False

        # 确保模板尺寸不超过 ROI
        th, tw = self._template.shape[:2]
        rh, rw = roi_img.shape[:2]
        if tw > rw or th > rh:
            return False

        result = cv2.matchTemplate(roi_img, self._template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        return max_val >= config.JELLY_MATCH_THRESHOLD

    def _detection_loop(self):
        """后台检测循环。"""
        while not self._stop_event.is_set():
            # 只在目标窗口激活时检测
            if window_detector.is_target_window_active():
                try:
                    # 1. 检测果冻
                    if self._template_loaded and self._do_match():
                        if not self._jelly_flag.is_set():
                            print("  [视觉检测] [!!] 检测到果冻状态！")
                            self._jelly_flag.set()
                            
                    # 2. 检测关闭按钮
                    if self._close_template_loaded and not self._close_flag.is_set():
                        roi_img, coords = self._capture_roi(config.CLOSE_ROI_PERCENT)
                        if roi_img is not None and coords is not None:
                            th, tw = self._close_template.shape[:2]
                            rh, rw = roi_img.shape[:2]
                            if tw <= rw and th <= rh:
                                result = cv2.matchTemplate(roi_img, self._close_template, cv2.TM_CCOEFF_NORMED)
                                _, max_val, _, max_loc = cv2.minMaxLoc(result)
                                if max_val >= config.CLOSE_MATCH_THRESHOLD:
                                    print(f"  [视觉检测] [!!] 检测到弹窗关闭按钮！(置信度: {max_val:.2f})")
                                    # 计算中心点绝对坐标
                                    abs_x = coords[0] + max_loc[0] + tw // 2
                                    abs_y = coords[1] + max_loc[1] + th // 2
                                    self._close_coords = (abs_x, abs_y)
                                    self._close_flag.set()
                                    
                except Exception as e:
                    print(f"  [视觉检测] 检测异常: {e}")

            # 等待下一次检测
            self._stop_event.wait(timeout=config.VISION_CHECK_INTERVAL)


if __name__ == "__main__":
    # 独立测试
    print("=== 视觉检测模块测试 ===")
    detector = VisionDetector()

    if not detector.template_loaded:
        print("\n模板图片不存在，是否现在截取？(y/n)")
        choice = input("> ").strip().lower()
        if choice == 'y':
            detector.capture_template()

    if detector.template_loaded:
        print("\n开始检测（5 秒后自动停止）...")
        detector.start()
        time.sleep(5)
        print(f"检测结果: 果冻状态 = {detector.is_jelly}")
        detector.stop()
    else:
        print("无模板，跳过检测测试。")
