# -*- coding: utf-8 -*-
"""
ROI 区域可视化工具

用于调试视觉检测的判定区域。运行该脚本后，会捕捉当前游戏窗口的截图，
并在上面画出一个红色的框，显示 config.py 中配置的 JELLY_ROI_PERCENT 到底包括了哪里。
"""

import os
import cv2
import numpy as np
from mss import mss

import config
import window_detector

def debug_roi():
    # 获取游戏窗口位置
    rect = window_detector.get_foreground_window_rect()
    if not rect:
        print("[!] 找不到游戏窗口！请确保《洛克王国：世界》正在运行且未被完全遮挡。")
        print("    如果你想截到游戏窗口，请先点一下游戏窗口激活它，")
        print("    然后再在 3 秒内切回命令行运行这段代码（或者在 VSCode 里直接加个 3 秒延迟）。")
        return
        
    win_left, win_top, win_right, win_bottom = rect
    monitor = {
        "left": win_left,
        "top": win_top,
        "width": win_right - win_left,
        "height": win_bottom - win_top,
    }
    
    # 截图
    with mss() as sct:
        screenshot = sct.grab(monitor)
    img = np.array(screenshot)
    img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    
    # 计算红框的物理坐标
    win_w = monitor["width"]
    win_h = monitor["height"]
    lp, tp, rp, bp = config.JELLY_ROI_PERCENT
    
    x1 = int(win_w * lp)
    y1 = int(win_h * tp)
    x2 = int(win_w * rp)
    y2 = int(win_h * bp)
    
    # 画果冻红框
    cv2.rectangle(img_bgr, (x1, y1), (x2, y2), (0, 0, 255), 3)
    cv2.putText(
        img_bgr, "Jelly ROI", (x1, y1 - 10), 
        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2
    )
    
    # 画关闭弹窗蓝框
    clp, ctp, crp, cbp = config.CLOSE_ROI_PERCENT
    cx1 = int(win_w * clp)
    cy1 = int(win_h * ctp)
    cx2 = int(win_w * crp)
    cy2 = int(win_h * cbp)
    cv2.rectangle(img_bgr, (cx1, cy1), (cx2, cy2), (255, 0, 0), 3)
    cv2.putText(
        img_bgr, "Close ROI", (cx1 - 50, cy2 + 20), 
        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2
    )

    # 保存图片
    output_path = os.path.join(os.path.dirname(__file__), "roi_debug.png")
    cv2.imwrite(output_path, img_bgr)
    print(f"\n[OK] 截图已保存至: {output_path}")
    print("     请打开这幅图片，图片中的红框就是程序寻找 'X' 图标的监控范围。")
    print("     如果 X 不在红框里，请去 config.py 修改 JELLY_ROI_PERCENT。")

if __name__ == "__main__":
    # 为了方便你切窗口，给 2 秒缓冲时间
    import time
    print("等待 2 秒...请确保此刻游戏窗口在最前面。")
    time.sleep(2)
    debug_roi()
