# -*- coding: utf-8 -*-
"""
洛克王国：世界 — Python 自动化工具
预设场景模板

每个预设包含:
  - name: 显示名称
  - description: 简要说明
  - init_commands: 初始化指令（一次性执行）
  - loop_commands: 循环指令（持续重复执行）
"""

PRESETS = {
    # ===========================================================
    # 1) 自定义连招 — 用户自行输入
    # ===========================================================
    "custom": {
        "name": "自定义连招",
        "description": "用户自行输入宏指令字符串执行",
        "init_commands": "",
        "loop_commands": "",
    },

    # ===========================================================
    # 2) 主座设置
    # ===========================================================
    # 流程：
    #   初始化：扔出 2~6 号精灵
    #   循环：使用 1 号精灵骑乘，每 20 秒按一次 R 防掉线
    "multi_ride": {
        "name": "主座设置",
        "description": "扔出2~6号精灵后骑乘1号，每20秒按R防掉线",
        "init_commands": (
            "500 IUp RUp LMouseUp "
            # 扔出 2~6 号精灵
            "C2 800 LMouseDown 300 LMouseUp 1500 "
            "C3 800 LMouseDown 300 LMouseUp 1500 "
            "C4 800 LMouseDown 300 LMouseUp 1500 "
            "C5 800 LMouseDown 300 LMouseUp 1500 "
            "C6 800 LMouseDown 300 LMouseUp 1500 "
            # 骑乘 1 号精灵 (按 R)
            "C1 800 RDown 200 RUp 1000 "
        ),
        "loop_commands": (
            # 每 20 秒按一次 R 防掉线
            "RDown 200 RUp 20000 "
        ),
    },

    # ===========================================================
    # 3) 纯鞠躬小号设置
    # ===========================================================
    # 流程：
    #   初始化：扔出 1~6 号精灵
    #   循环：Tab → Bow鞠躬 → Esc，不断重复
    "multi_bow": {
        "name": "纯鞠躬小号设置",
        "description": "扔出1~6号精灵后，持续循环: Tab→鞠躬→Esc",
        "init_commands": (
            "500 IUp RUp LMouseUp "
            "C1  LMouseDown 1000 LMouseUp 200 "
            "C2  LMouseDown 1000 LMouseUp 200 "
            "C3  LMouseDown 1000 LMouseUp 200 "
            "C4  LMouseDown 1000 LMouseUp 200 "
            "C5  LMouseDown 1000 LMouseUp 200 "
            "C6  LMouseDown 1000 LMouseUp 200 "
        ),
        "loop_commands": (
            "2000 Tab 500 Bow 1500 Esc 300 SpaceDown 100 SpaceUp 8000 "
        ),
    },

    # ===========================================================
    # 4) 单人采集设置
    # ===========================================================
    # 流程：
    #   初始化：扔出 2~6 号精灵
    #   循环：Tab → 鞠躬 → Esc → 跳跃(Space) →RDown→  RUp 
    "jump_bow": {
        "name": "单人采集设置",
        "description": "扔出2~6号精灵，循环: Tab→鞠躬→Esc→跳跃→ RDown → RUp",
        "init_commands": (
            "500 IUp RUp LMouseUp "
            "C2  LMouseDown 1000 LMouseUp 200 "
            "C3  LMouseDown 1000 LMouseUp 200 "
            "C4  LMouseDown 1000 LMouseUp 200 "
            "C5  LMouseDown 1000 LMouseUp 200 "
            "C6  LMouseDown 1000 LMouseUp 200 "
        ),
        "loop_commands": (
            "2000 Tab 500 Bow 1500 Esc 500 SpaceDown 100 SpaceUp 500 C1 800 RDown 200 RUp 8000 XDown 200 XUp 500 "
        ),
    },
}


def get_preset_names() -> list[str]:
    """返回所有预设的 key 列表。"""
    return list(PRESETS.keys())


def get_preset(key: str) -> dict | None:
    """根据 key 获取预设字典。"""
    return PRESETS.get(key)
