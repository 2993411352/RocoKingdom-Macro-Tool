# -*- coding: utf-8 -*-
"""
视觉检测准度实时测试器

这个工具会实时读取当前游戏屏幕，并给你打印出 "你的图片" 和 "游戏实时画面" 的相似度百分比。
可以通过这个数值精确调试 config.py 里的 JELLY_MATCH_THRESHOLD 阈值！
"""

import time
import cv2
import config
from vision_detector import VisionDetector
import window_detector

def test_vision():
    # 强制在控制台也能输出颜色
    import os
    os.system('color')
    
    print("=== 初始化视觉检测器 ===")
    detector = VisionDetector()
    if not detector.template_loaded:
        print("[!] 错误：没有找到模板图片！请先将 'jelly_template.png' 放入 templates 文件夹中。")
        return
        
    print("\n[OK] 开始实时监测果冻状态！请切换到游戏并保持操作。")
    print("--------------------------------------------------")
    print(f"当前设定的及格线 (阈值) 为: {config.JELLY_MATCH_THRESHOLD}")
    print("提示：如果即使变果冻了，得分也达不到及格线，请降低 config.py 里的及格线。")
    print("      如果没变果冻得分却经常超过及格线，说明框进去了相同的背景，请重新抠图！")
    print("--------------------------------------------------")
    print("(在此命令行窗口按 Ctrl+C 可以停止测试)\n")
    
    try:
        while True:
            # 只有游戏在前台才检测
            if window_detector.is_target_window_active():
                out_str = ""
                
                # 1. 测果冻
                if detector.template_loaded:
                    roi_img, _ = detector._capture_roi(config.JELLY_ROI_PERCENT)
                    if roi_img is not None:
                        th, tw = detector._template.shape[:2]
                        rh, rw = roi_img.shape[:2]
                        if tw <= rw and th <= rh:
                            result = cv2.matchTemplate(roi_img, detector._template, cv2.TM_CCOEFF_NORMED)
                            _, max_val, _, _ = cv2.minMaxLoc(result)
                            matched = max_val >= config.JELLY_MATCH_THRESHOLD
                            if matched:
                                out_str += f"\033[92m[✓ 果冻] 得分: {max_val:.2f}\033[0m | "
                            else:
                                out_str += f"[- 果冻正常] 得分: {max_val:.2f} | "
                                
                # 2. 测弹窗
                if getattr(detector, '_close_template_loaded', False):
                    roi_img2, _ = detector._capture_roi(config.CLOSE_ROI_PERCENT)
                    if roi_img2 is not None:
                        th, tw = detector._close_template.shape[:2]
                        rh, rw = roi_img2.shape[:2]
                        if tw <= rw and th <= rh:
                            result2 = cv2.matchTemplate(roi_img2, detector._close_template, cv2.TM_CCOEFF_NORMED)
                            _, max_val2, _, _ = cv2.minMaxLoc(result2)
                            matched2 = max_val2 >= config.CLOSE_MATCH_THRESHOLD
                            if matched2:
                                out_str += f"\033[91m[✓ 弹窗 X] 得分: {max_val2:.2f} (触发!)\033[0m"
                            else:
                                out_str += f"[- 弹窗正常] 得分: {max_val2:.2f}"
                                
                print(out_str if out_str else "[!] 截图范围异常")
            else:
                print("[zZ] 游戏未置顶，等待中...")
                
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n监测已停止！")

if __name__ == "__main__":
    test_vision()
