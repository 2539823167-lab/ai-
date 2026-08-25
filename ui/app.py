"""主窗口：卡片式四象限布局 + 底部状态栏。

布局：
  左上 弹幕流 ｜ 右上 回复建议
  左下 知识库 ｜ 右下 提词器
  底部 状态栏（弹幕数 / 云端预算 / 花费）
"""
import tkinter as tk
from tkinter import ttk

from core.events import EVT_DANMAKU, EVT_REPLY, EVT_LOG
from ui import theme
from ui.danmaku_panel import DanmakuPanel
from ui.kb_panel import KBPanel
from ui.reply_panel import ReplyPanel
from ui.teleprompter import TeleprompterPanel


class App(tk.Tk):
    def __init__(self, config, event_bus, coordinator, provider, kb):
        super().__init__()
        self.title("AI 直播助手（抖音）")
        self.geometry("1000x680")
        self.minsize(860, 560)

        self.event_bus = event_bus
        self.coordinator = coordinator
        self.provider = provider
        self._danmaku_count = 0

        theme.apply_style(self)
        self._build_header()
        self._build_panels(kb)
        self._build_statusbar()

        event_bus.subscribe(EVT_DANMAKU, self._on_danmaku)
        event_bus.subscribe(EVT_REPLY, self._on_reply)
        event_bus.subscribe(EVT_LOG, self._on_log)

        coordinator.start()
        provider.start()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- 构建界面 ----------

    def _build_header(self):
        header = ttk.Frame(self, style="App.TFrame")
        header.pack(fill="x", padx=14, pady=(12, 4))
        ttk.Label(header, text="🎙️ AI 直播助手",
                  background=theme.BG, foreground=theme.FG,
                  font=(theme.FONT_FAMILY, 16, "bold")).pack(side="left")
        ttk.Label(header, text="抖音 · 弹幕回复建议",
                  background=theme.BG, foreground=theme.MUTED,
                  font=theme.FONT_SMALL).pack(side="left", padx=(10, 0))

    def _build_panels(self, kb):
        body = ttk.Frame(self, style="App.TFrame")
        body.pack(fill="both", expand=True, padx=14, pady=6)

        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=3)
        body.rowconfigure(1, weight=2)

        self.danmaku_panel = DanmakuPanel(body)
        self.danmaku_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=(0, 5))

        self.reply_panel = ReplyPanel(body)
        self.reply_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=(0, 5))

        self.kb_panel = KBPanel(body, kb)
        self.kb_panel.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=(5, 0))

        self.teleprompter_panel = TeleprompterPanel(body, on_generate=self._on_generate_topic)
        self.teleprompter_panel.grid(row=1, column=1, sticky="nsew", padx=(5, 0), pady=(5, 0))

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=theme.CARD_ALT)
        bar.pack(fill="x", side="bottom")
        self.status_label = tk.Label(bar, text="就绪", bg=theme.CARD_ALT,
                                     fg=theme.MUTED, anchor="w",
                                     font=theme.FONT_SMALL)
        self.status_label.pack(side="left", fill="x", expand=True, padx=12, pady=4)

    # ---------- 事件回调（UI 更新回主线程） ----------

    def _on_danmaku(self, event):
        self._danmaku_count += 1
        self.after(0, self.danmaku_panel.append, event)
        self.after(0, self._update_status)

    def _on_reply(self, suggestion):
        self.after(0, self.reply_panel.show, suggestion)
        self.after(0, self._update_status)

    def _on_log(self, msg):
        # 日志仅走控制台打印（main.py 里订阅），不占用状态栏，避免刷屏
        pass

    def _on_generate_topic(self):
        """点击「生成话题」：后台线程生成，避免阻塞 UI。"""
        import threading

        self.status_label.config(text="正在生成话题…")

        def work():
            topic = self.coordinator.generate_topic()
            self.after(0, self._show_topic, topic)

        threading.Thread(target=work, daemon=True).start()

    def _show_topic(self, topic):
        if topic:
            self.teleprompter_panel.set_text(topic)
            self.status_label.config(text="话题已生成")
        else:
            self.teleprompter_panel.set_text(
                "（暂无法生成话题：请启动本地 Ollama 或配置云端 key）")
            self.status_label.config(text="话题生成失败（无可用 AI）")

    def _update_status(self):
        b = self.coordinator.budget
        self.status_label.config(
            text=f"弹幕 {self._danmaku_count} 条　|　"
                 f"云端预算：{b.remaining_calls}/{b.max_calls} 次　|　"
                 f"已花费 ¥{b.spent:.2f}"
        )

    def _on_close(self):
        """关闭窗口时优雅停止后台线程。"""
        self.provider.stop()
        self.coordinator.stop()
        self.destroy()
