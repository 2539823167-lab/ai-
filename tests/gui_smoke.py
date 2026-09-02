"""GUI 冒烟测试（手动运行，非 unittest 用例）：真实装配 App 并跑 6 秒主循环。

验证：界面能否正常构建、弹幕/回复事件流是否贯通、关窗是否干净退出。
无桌面环境（Tk 创建失败）时自动跳过，不影响 CI。

用法（项目根目录）：py -3.10 tests/gui_smoke.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main as entry

RUN_SECONDS = float(os.environ.get("GUI_SMOKE_SECONDS", "6"))


def run():
    try:
        import tkinter as tk
        root = tk.Tk()
        root.destroy()
    except Exception as e:
        print(f"[gui_smoke] 当前环境无法创建窗口，跳过：{e}")
        return 0

    config = entry.load_config()
    config["danmaku"]["mock_interval"] = 0.3  # 加速弹幕便于观察

    event_bus = entry.EventBus()
    budget = entry.BudgetGuard(config["budget"]["max_calls"], config["budget"]["max_cost"])
    kb = entry.build_kb(config)
    local_ai, cloud_ai = entry.build_ai(config)
    coordinator = entry.Coordinator(
        config=config, event_bus=event_bus, budget=budget,
        templates=entry.templates, sensitive=entry.sensitive,
        local_ai=local_ai, cloud_ai=cloud_ai, kb=kb,
    )

    def on_danmaku(event):
        event_bus.publish("danmaku", event)   # 与 main.py 一致：先通知 UI 显示
        coordinator.on_danmaku(event)          # 再进入聚合判断

    provider = entry.build_provider(config, on_danmaku)

    from ui.app import App
    app = App(config, event_bus, coordinator, provider, kb)
    app.withdraw()  # 隐藏窗口，仍走真实 mainloop

    def report_and_close():
        stats = app._stats
        shown = app.danmaku_panel.count_label.cget("text")
        app._on_close()
        print(f"[gui_smoke] 弹幕总数={stats['danmaku']} 回复={stats['reply']} "
              f"模板命中={stats['template']} 兜底={stats['fallback']} | 上屏条数={shown}")
        print("[gui_smoke] GUI-SMOKE-OK")

    app.after(int(RUN_SECONDS * 1000), report_and_close)
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(run())
