# -*- coding: utf-8 -*-
"""
洛克王国：世界 — Python 自动化工具
图形界面版本 (tkinter)
"""

import sys
import os
import queue
import time
import threading
import tkinter as tk
from tkinter import scrolledtext

import keyboard

import config
from presets import PRESETS
from core import window_detector
from core.macro_engine import MacroEngine
from core.vision_detector import VisionDetector


# ============================================================
# 配色方案 (Catppuccin Mocha)
# ============================================================
C = {
    'bg':       '#1e1e2e',
    'surface':  '#313244',
    'overlay':  '#45475a',
    'text':     '#cdd6f4',
    'subtext':  '#a6adc8',
    'dim':      '#6c7086',
    'blue':     '#89b4fa',
    'green':    '#a6e3a1',
    'red':      '#f38ba8',
    'yellow':   '#f9e2af',
    'mauve':    '#cba6f7',
    'teal':     '#94e2d5',
    'log_bg':   '#181825',
    'input_bg': '#313244',
}

FONT_FAMILY = 'Microsoft YaHei'
FONT        = (FONT_FAMILY, 10)
FONT_BOLD   = (FONT_FAMILY, 10, 'bold')
FONT_TITLE  = (FONT_FAMILY, 14, 'bold')
FONT_SMALL  = (FONT_FAMILY, 9)
FONT_MONO   = ('Consolas', 9)


# ============================================================
# stdout 重定向器
# ============================================================
class StdoutRedirector:
    """将 print() 输出捕获到队列，同时保留原始控制台输出。"""

    def __init__(self, log_queue, original):
        self.queue = log_queue
        self.original = original

    def write(self, text):
        if text and text.strip():
            self.queue.put(text.rstrip('\n'))
        if self.original:
            try:
                self.original.write(text)
                self.original.flush()
            except Exception:
                pass

    def flush(self):
        if self.original:
            try:
                self.original.flush()
            except Exception:
                pass


# ============================================================
# 主界面
# ============================================================
class RocoApp:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("RocoKingdom 自动化工具")
        self.root.geometry("720x700")
        self.root.minsize(640, 560)
        self.root.configure(bg=C['bg'])

        # DPI 感知
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        # --- 日志队列 & stdout 重定向 ---
        self.log_queue = queue.Queue()
        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr
        sys.stdout = StdoutRedirector(self.log_queue, sys.stdout)
        sys.stderr = StdoutRedirector(self.log_queue, sys.stderr)

        # --- 引擎 ---
        self.engine = MacroEngine()

        # --- 预设映射 ---
        self.preset_keys  = list(PRESETS.keys())
        self.preset_names = [PRESETS[k]['name'] for k in self.preset_keys]
        self.selected_preset_name = tk.StringVar(value=self.preset_names[1])

        # --- 构建 UI ---
        self._build_ui()

        # --- 注册全局热键 ---
        try:
            keyboard.add_hotkey(
                config.HOTKEY_TOGGLE,
                lambda: self.root.after(0, self._toggle_macro),
                suppress=False,
            )
            keyboard.add_hotkey(
                config.HOTKEY_TOGGLE_ALT,
                lambda: self.root.after(0, self._toggle_macro),
                suppress=False,
            )
        except Exception as e:
            self._log(f"[!] 热键注册失败: {e}")

        # --- 周期任务 ---
        self._poll_log()
        self._update_status()

        # --- 关闭回调 ---
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # --- 启动日志 ---
        self._log("[*] 洛克王国自动化工具已启动")
        self._log(f"    热键: {config.HOTKEY_TOGGLE} / {config.HOTKEY_TOGGLE_ALT}")

    # ================================================================
    # UI 构建
    # ================================================================

    def _build_ui(self):
        main = tk.Frame(self.root, bg=C['bg'])
        main.pack(fill='both', expand=True, padx=18, pady=14)

        # ---- 标题 ----
        tk.Label(
            main, text="洛克王国 : 世界  自动化工具",
            font=FONT_TITLE, fg=C['blue'], bg=C['bg'],
        ).pack(anchor='w', pady=(0, 12))

        # ---- 状态栏 ----
        self._build_status(main)

        # ---- 预设 + 按钮 ----
        self._build_controls(main)

        # ---- 脚本编辑器 ----
        self._build_editor(main)

        # ---- 日志区域 ----
        self._build_log(main)

        # ---- 底部提示 ----
        tk.Label(
            main,
            text=(f"快捷键: {config.HOTKEY_TOGGLE} 启动/停止  |  "
                  f"关闭窗口退出"),
            font=FONT_SMALL, fg=C['dim'], bg=C['bg'],
        ).pack(anchor='w', pady=(8, 0))

    # ---- 状态栏 ----
    def _build_status(self, parent):
        frame = tk.Frame(parent, bg=C['surface'])
        frame.pack(fill='x', pady=(0, 10))
        inner = tk.Frame(frame, bg=C['surface'])
        inner.pack(fill='x', padx=14, pady=8)

        # 左侧：状态指示
        left = tk.Frame(inner, bg=C['surface'])
        left.pack(side='left')

        self.state_dot = tk.Label(
            left, text="\u25cf", font=(FONT_FAMILY, 13),
            fg=C['dim'], bg=C['surface'],
        )
        self.state_dot.pack(side='left')

        self.state_label = tk.Label(
            left, text=" 空闲", font=FONT_BOLD,
            fg=C['text'], bg=C['surface'],
        )
        self.state_label.pack(side='left')

        # 右侧：统计
        self.stats_label = tk.Label(
            inner,
            text="循环: 0  |  指令: 0  |  恢复: 0",
            font=FONT_SMALL, fg=C['subtext'], bg=C['surface'],
        )
        self.stats_label.pack(side='right')

    # ---- 预设选择 + 按钮 ----
    def _build_controls(self, parent):
        # 预设行
        row = tk.Frame(parent, bg=C['bg'])
        row.pack(fill='x', pady=(0, 6))

        tk.Label(
            row, text="预设模板:", font=FONT,
            fg=C['text'], bg=C['bg'],
        ).pack(side='left')

        self.preset_menu = tk.OptionMenu(
            row, self.selected_preset_name,
            *self.preset_names,
            command=self._on_preset_change,
        )
        self.preset_menu.configure(
            font=FONT, bg=C['surface'], fg=C['text'],
            activebackground=C['overlay'], activeforeground=C['text'],
            highlightthickness=0, bd=1, relief='flat',
        )
        self.preset_menu['menu'].configure(
            font=FONT, bg=C['surface'], fg=C['text'],
            activebackground=C['blue'], activeforeground=C['bg'],
        )
        self.preset_menu.pack(side='left', padx=(8, 0), fill='x', expand=True)

        # 预设说明
        self.preset_desc = tk.Label(
            parent, text="", font=FONT_SMALL,
            fg=C['subtext'], bg=C['bg'], anchor='w',
        )
        self.preset_desc.pack(fill='x', pady=(0, 8))
        self._update_preset_desc()

        # 按钮行
        btn_row = tk.Frame(parent, bg=C['bg'])
        btn_row.pack(fill='x', pady=(0, 10))

        self.start_btn = self._make_btn(
            btn_row, "  START  ", C['green'], self._start_macro,
        )
        self.start_btn.pack(side='left', padx=(0, 8))

        self.stop_btn = self._make_btn(
            btn_row, "  STOP  ", C['red'], self._stop_macro,
        )
        self.stop_btn.configure(state='disabled')
        self.stop_btn.pack(side='left', padx=(0, 8))

        self.tpl_btn = self._make_btn(
            btn_row, "  打开模板文件夹  ", C['yellow'], self._open_template_dir,
        )
        self.tpl_btn.pack(side='left')

    # ---- 脚本编辑器 ----
    def _build_editor(self, parent):
        tk.Label(
            parent, text="脚本指令 (可手动编辑)",
            font=FONT_BOLD, fg=C['mauve'], bg=C['bg'],
        ).pack(anchor='w', pady=(0, 4))

        box = tk.Frame(parent, bg=C['surface'])
        box.pack(fill='x', pady=(0, 10))
        inner = tk.Frame(box, bg=C['surface'])
        inner.pack(fill='x', padx=12, pady=10)

        # Init
        tk.Label(
            inner, text="初始化指令 (一次性执行):", font=FONT_SMALL,
            fg=C['subtext'], bg=C['surface'],
        ).pack(anchor='w')

        self.init_text = tk.Text(
            inner, height=3, font=FONT_MONO,
            bg=C['input_bg'], fg=C['text'],
            insertbackground=C['text'],
            selectbackground=C['blue'], selectforeground=C['bg'],
            relief='flat', bd=0, wrap='word', padx=6, pady=4,
        )
        self.init_text.pack(fill='x', pady=(2, 8))

        # Loop
        tk.Label(
            inner, text="循环指令 (持续重复):", font=FONT_SMALL,
            fg=C['subtext'], bg=C['surface'],
        ).pack(anchor='w')

        self.loop_text = tk.Text(
            inner, height=3, font=FONT_MONO,
            bg=C['input_bg'], fg=C['text'],
            insertbackground=C['text'],
            selectbackground=C['blue'], selectforeground=C['bg'],
            relief='flat', bd=0, wrap='word', padx=6, pady=4,
        )
        self.loop_text.pack(fill='x', pady=(2, 0))

        # 填充默认预设
        self._fill_preset('single_6')

    # ---- 日志区域 ----
    def _build_log(self, parent):
        header = tk.Frame(parent, bg=C['bg'])
        header.pack(fill='x', pady=(0, 4))

        tk.Label(
            header, text="运行日志", font=FONT_BOLD,
            fg=C['teal'], bg=C['bg'],
        ).pack(side='left')

        tk.Button(
            header, text="清除", font=FONT_SMALL,
            bg=C['overlay'], fg=C['subtext'],
            activebackground=C['surface'], activeforeground=C['text'],
            relief='flat', padx=8, cursor='hand2',
            command=self._clear_log,
        ).pack(side='right')

        log_frame = tk.Frame(parent, bg=C['log_bg'])
        log_frame.pack(fill='both', expand=True)

        self.log_text = tk.Text(
            log_frame, font=FONT_MONO,
            bg=C['log_bg'], fg=C['text'],
            insertbackground=C['text'],
            relief='flat', bd=0, wrap='word',
            padx=8, pady=6, state='disabled',
        )

        # 颜色标签
        self.log_text.tag_configure('info',    foreground=C['text'])
        self.log_text.tag_configure('success', foreground=C['green'])
        self.log_text.tag_configure('warn',    foreground=C['yellow'])
        self.log_text.tag_configure('error',   foreground=C['red'])
        self.log_text.tag_configure('jelly',   foreground=C['mauve'])
        self.log_text.tag_configure('time',    foreground=C['dim'])

        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side='right', fill='y')
        self.log_text.pack(side='left', fill='both', expand=True)

    # ================================================================
    # 辅助：按钮工厂
    # ================================================================

    def _make_btn(self, parent, text, color, command):
        btn = tk.Button(
            parent, text=text, font=FONT_BOLD,
            bg=color, fg='#1e1e2e',
            activebackground=color, activeforeground='#1e1e2e',
            relief='flat', padx=16, pady=5, cursor='hand2',
            command=command,
        )
        # 悬停效果
        def on_enter(e, b=btn, c=color):
            try:
                # 稍微变亮
                r = int(c[1:3], 16)
                g = int(c[3:5], 16)
                b_val = int(c[5:7], 16)
                r = min(255, r + 20)
                g = min(255, g + 20)
                b_val = min(255, b_val + 20)
                b.configure(bg=f'#{r:02x}{g:02x}{b_val:02x}')
            except Exception:
                pass

        def on_leave(e, b=btn, c=color):
            b.configure(bg=c)

        btn.bind('<Enter>', on_enter)
        btn.bind('<Leave>', on_leave)
        return btn

    # ================================================================
    # 操作
    # ================================================================

    def _toggle_macro(self):
        if self.engine.is_running:
            self._stop_macro()
        else:
            self._start_macro()

    def _start_macro(self):
        if self.engine.is_running:
            return

        init_cmds = self.init_text.get('1.0', 'end-1c').strip()
        loop_cmds = self.loop_text.get('1.0', 'end-1c').strip()

        if not loop_cmds:
            self._log("[!] 循环指令不能为空!")
            return

        key = self._current_preset_key()
        name = PRESETS.get(key, {}).get('name', key)
        self._log(f"[>] 启动: {name}")

        self.start_btn.configure(state='disabled')
        self.stop_btn.configure(state='normal')

        self.engine.start(init_cmds, loop_cmds, key)

    def _stop_macro(self):
        if not self.engine.is_running:
            return
        self._log("[STOP] 正在停止...")
        self.engine.stop()
        self.start_btn.configure(state='normal')
        self.stop_btn.configure(state='disabled')

    def _open_template_dir(self):
        """打开模板文件夹，提示用户手动放入精确图标截图。"""
        os.makedirs(config.TEMPLATES_DIR, exist_ok=True)
        try:
            os.startfile(config.TEMPLATES_DIR)
            self._log("[OK] 已打开 templates 文件夹")
            self._log("     请用系统截图工具截取纯净的'X'图标")
            self._log("     保存为 jelly_template.png 并放入此文件夹")
        except Exception as e:
            self._log(f"[X] 无法打开文件夹: {e}")

    # ================================================================
    # 预设切换
    # ================================================================

    def _current_preset_key(self) -> str:
        name = self.selected_preset_name.get()
        for i, n in enumerate(self.preset_names):
            if n == name:
                return self.preset_keys[i]
        return self.preset_keys[0]

    def _on_preset_change(self, *_args):
        key = self._current_preset_key()
        self._fill_preset(key)
        self._update_preset_desc()

    def _fill_preset(self, key):
        preset = PRESETS.get(key)
        if not preset:
            return

        self.init_text.delete('1.0', 'end')
        self.init_text.insert('1.0', preset.get('init_commands', '').strip())

        self.loop_text.delete('1.0', 'end')
        self.loop_text.insert('1.0', preset.get('loop_commands', '').strip())

    def _update_preset_desc(self):
        key = self._current_preset_key()
        desc = PRESETS.get(key, {}).get('description', '')
        self.preset_desc.configure(text=f"  {desc}")

    # ================================================================
    # 周期任务
    # ================================================================

    def _poll_log(self):
        """从队列中读取日志并显示。"""
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self._append_log(msg)
        except queue.Empty:
            pass
        self.root.after(80, self._poll_log)

    def _update_status(self):
        """刷新状态指示和统计数字。"""
        state = self.engine.state
        stats = self.engine.stats

        state_map = {
            'IDLE':           (C['dim'],    '空闲'),
            'RUNNING':        (C['green'],  '运行中'),
            'PAUSED_WINDOW':  (C['yellow'], '暂停(窗口失焦)'),
            'JELLY_RECOVERY': (C['mauve'],  '恢复中(果冻)'),
            'STOPPING':       (C['red'],    '停止中'),
        }
        color, text = state_map.get(state.name, (C['dim'], str(state.value)))
        self.state_dot.configure(fg=color)
        self.state_label.configure(text=f" {text}")

        self.stats_label.configure(
            text=(f"循环: {stats['loop_count']}  |  "
                  f"指令: {stats['commands_executed']}  |  "
                  f"恢复: {stats['jelly_recoveries']}")
        )

        # 同步按钮状态
        if self.engine.is_running:
            self.start_btn.configure(state='disabled')
            self.stop_btn.configure(state='normal')
        else:
            self.start_btn.configure(state='normal')
            self.stop_btn.configure(state='disabled')

        self.root.after(200, self._update_status)

    # ================================================================
    # 日志
    # ================================================================

    def _log(self, msg):
        self.log_queue.put(msg)

    def _append_log(self, msg):
        msg = msg.lstrip()
        # 根据内容选择颜色标签
        if any(k in msg for k in ('[OK]', '[>]', 'START')):
            tag = 'success'
        elif any(k in msg for k in ('[!]', '[X]', 'STOP')):
            tag = 'warn'
        elif any(k in msg for k in ('JELLY', '[!!]')):
            tag = 'jelly'
        elif 'ERROR' in msg.upper() or 'EXCEPTION' in msg.upper():
            tag = 'error'
        else:
            tag = 'info'

        timestamp = time.strftime('%H:%M:%S')

        self.log_text.configure(state='normal')
        self.log_text.insert('end', f"[{timestamp}] ", 'time')
        self.log_text.insert('end', f"{msg}\n", tag)
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

    def _clear_log(self):
        self.log_text.configure(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.configure(state='disabled')

    # ================================================================
    # 关闭
    # ================================================================

    def _on_close(self):
        if self.engine.is_running:
            self.engine.stop()

        sys.stdout = self._orig_stdout
        sys.stderr = self._orig_stderr

        try:
            keyboard.unhook_all()
        except Exception:
            pass

        self.root.destroy()

    # ---- 启动 ----
    def run(self):
        self.root.mainloop()


# ============================================================
# 入口
# ============================================================

def main():
    # 管理员权限提示
    try:
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            print("[!] 建议以管理员身份运行")
    except Exception:
        pass

    app = RocoApp()
    app.run()


if __name__ == "__main__":
    main()
