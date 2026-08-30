"""主窗口：状态头部 + 统计卡 + 四象限布局 + 运行日志 + 状态栏。

布局：
  头部 标题 + 实时状态灯（弹幕源 / Ollama / 云端）+ 暂停按钮
  统计 弹幕总数 / 回复建议 / 模板命中率 / 云端花费
  左上 弹幕流 ｜ 右上 回复建议
  左下 知识库 ｜ 右下 提词器
  日志 三级阶梯实时走向
  底部 状态栏（当前提示 + 待处理条数 + 云端预算）
"""
import threading
import time
import tkinter as tk
from tkinter import ttk

from core.events import EVT_DANMAKU, EVT_REPLY, EVT_LOG, DanmakuEvent
from ui import theme
from ui.danmaku_panel import DanmakuPanel
from ui.kb_panel import KBPanel
from ui.reply_panel import ReplyPanel
from ui.teleprompter import TeleprompterPanel

# 回复来源 → 中文名（状态栏提示用）
SOURCE_NAMES = {
    "template": "模板秒回",
    "local": "本地AI",
    "cloud": "云端AI",
    "fallback": "兜底",
}

HEALTH_CHECK_INTERVAL = 15  # Ollama 健康检查周期（秒）


class StatusDot(tk.Label):
    """头部状态灯：● + 文本。绿=正常 / 红=异常 / 灰=未知或暂停。"""

    def __init__(self, master, text):
        super().__init__(master, text=f"● {text}", bg=theme.BG, fg=theme.MUTED,
                         font=theme.FONT_SMALL)

    def set_state(self, ok, text):
        color = {True: theme.SUCCESS, False: theme.DANGER, None: theme.MUTED}[ok]
        self.configure(text=f"● {text}", fg=color)


class App(tk.Tk):
    def __init__(self, config, event_bus, coordinator, provider, kb):
        super().__init__()
        self.title("AI 直播助手（抖音）")
        # 窗口尺寸按屏幕自适应（不同 DPI 的虚拟分辨率差异较大）
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{min(1200, int(sw * 0.92))}x{min(860, int(sh * 0.88))}")
        self.minsize(920, 600)

        self.event_bus = event_bus
        self.coordinator = coordinator
        self.provider = provider
        self._provider_paused = False
        self._stats = {"danmaku": 0, "reply": 0,
                       "template": 0, "local": 0, "cloud": 0, "fallback": 0}

        theme.apply_style(self)
        # pack 顺序即空间优先级：状态栏 / 日志先占位，中间面板吃剩余空间
        self._build_statusbar()
        self._build_header()
        self._build_stats()
        self._build_log()
        self._build_panels(kb)

        event_bus.subscribe(EVT_DANMAKU, self._on_danmaku)
        event_bus.subscribe(EVT_REPLY, self._on_reply)
        event_bus.subscribe(EVT_LOG, self._on_log)

        coordinator.start()
        provider.start()
        self.dot_provider.set_state(True, "弹幕源运行中")

        # 后台线程定期探测 Ollama，头部状态灯实时反映可用性
        threading.Thread(target=self._health_loop, daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- 构建界面 ----------

    def _build_header(self):
        header = tk.Frame(self, bg=theme.BG)
        header.pack(fill="x", padx=16, pady=(12, 6))

        left = tk.Frame(header, bg=theme.BG)
        left.pack(side="left")
        tk.Label(left, text="🎙️ AI 直播助手", bg=theme.BG, fg=theme.FG,
                 font=(theme.FONT_FAMILY, 16, "bold")).pack(side="left")
        tk.Label(left, text="抖音 · 弹幕实时回复", bg=theme.BG, fg=theme.MUTED,
                 font=theme.FONT_SMALL).pack(side="left", padx=(10, 0), pady=(6, 0))

        right = tk.Frame(header, bg=theme.BG)
        right.pack(side="right")
        # side=right 先 pack 的在最右：暂停按钮 → 云端 → Ollama → 弹幕源
        self.pause_btn = ttk.Button(right, text="⏸ 暂停弹幕", style="Tool.TButton",
                                    command=self._toggle_pause)
        self.pause_btn.pack(side="right", padx=(12, 0))
        self.dot_cloud = StatusDot(right, "云端")
        cloud_on = self.coordinator.cloud_ai is not None
        self.dot_cloud.set_state(cloud_on,
                                 "云端已配置" if cloud_on else "云端未配置")
        self.dot_cloud.pack(side="right", padx=(12, 0))
        self.dot_ollama = StatusDot(right, "Ollama 检测中…")
        self.dot_ollama.pack(side="right", padx=(12, 0))
        self.dot_provider = StatusDot(right, "弹幕源")
        self.dot_provider.pack(side="right")

    def _build_stats(self):
        bar = tk.Frame(self, bg=theme.BG)
        bar.pack(fill="x", padx=16, pady=(0, 6))
        self.stat_values = {}
        defs = [
            ("danmaku", "弹幕总数", theme.ACCENT),
            ("reply", "回复建议", theme.SUCCESS),
            ("hit", "模板命中率", theme.WARNING),
            ("cost", "云端花费", "#CE93D8"),
        ]
        for i, (key, label, color) in enumerate(defs):
            card = tk.Frame(bar, bg=theme.CARD,
                            highlightbackground=theme.BORDER, highlightthickness=1)
            card.pack(side="left", fill="x", expand=True,
                      padx=(0 if i == 0 else 8, 0 if i == len(defs) - 1 else 8))
            val = tk.Label(card, text="—", bg=theme.CARD, fg=color,
                           font=theme.FONT_NUM)
            val.pack(pady=(5, 0))
            tk.Label(card, text=label, bg=theme.CARD, fg=theme.MUTED,
                     font=theme.FONT_SMALL).pack(pady=(0, 5))
            self.stat_values[key] = val

    def _build_panels(self, kb):
        body = tk.Frame(self, bg=theme.BG)
        body.pack(fill="both", expand=True, padx=16, pady=6)

        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=3)
        body.rowconfigure(1, weight=2)

        self.danmaku_panel = DanmakuPanel(body, on_send=self._send_manual,
                                          on_clear=self._clear_danmaku)
        self.danmaku_panel.grid(row=0, column=0, sticky="nsew",
                                padx=(0, 5), pady=(0, 5))

        self.reply_panel = ReplyPanel(
            body,
            on_flush=self._flush_now,
            on_adopt=self._adopt_reply,
            on_aggregate=self._set_aggregate,
            init_count=self.coordinator.max_count,
            init_seconds=self.coordinator.max_seconds,
        )
        self.reply_panel.grid(row=0, column=1, sticky="nsew",
                              padx=(5, 0), pady=(0, 5))

        self.kb_panel = KBPanel(body, kb)
        self.kb_panel.grid(row=1, column=0, sticky="nsew",
                           padx=(0, 5), pady=(5, 0))

        self.teleprompter_panel = TeleprompterPanel(
            body, on_generate=self._on_generate_topic)
        self.teleprompter_panel.grid(row=1, column=1, sticky="nsew",
                                     padx=(5, 0), pady=(5, 0))

    def _build_log(self):
        card = theme.Card(self)
        card.pack(fill="x", side="bottom", padx=16, pady=(6, 0))
        header = tk.Frame(card, bg=theme.CARD)
        header.pack(fill="x", padx=10, pady=(6, 0))
        tk.Label(header, text="📜 运行日志（三级阶梯走向）", bg=theme.CARD,
                 fg=theme.MUTED, font=theme.FONT_SMALL).pack(side="left")
        self.log_text = tk.Text(card, bg=theme.CARD, fg=theme.MUTED,
                                relief="flat", borderwidth=0, wrap="word",
                                font=("Consolas", 9), height=3, padx=10, pady=4,
                                highlightthickness=0, state="disabled")
        self.log_text.pack(fill="x", padx=8, pady=(2, 8))

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=theme.CARD_DEEP)
        bar.pack(fill="x", side="bottom")
        self.status_label = tk.Label(bar, text="就绪", bg=theme.CARD_DEEP,
                                     fg=theme.MUTED, anchor="w",
                                     font=theme.FONT_SMALL)
        self.status_label.pack(side="left", fill="x", expand=True, padx=12, pady=4)
        self.pending_label = tk.Label(bar, text="", bg=theme.CARD_DEEP,
                                      fg=theme.MUTED, anchor="e",
                                      font=theme.FONT_SMALL)
        self.pending_label.pack(side="right", padx=12)
        self._tick_pending()

    # ---------- 事件回调（UI 更新统一回主线程） ----------

    def _on_danmaku(self, event):
        self._stats["danmaku"] += 1
        self.after(0, self.danmaku_panel.append, event)
        self.after(0, self._update_stats)

    def _on_reply(self, suggestion):
        self._stats["reply"] += 1
        self._stats[suggestion.source] = self._stats.get(suggestion.source, 0) + 1
        name = SOURCE_NAMES.get(suggestion.source, suggestion.source)
        self.after(0, self.reply_panel.show, suggestion)
        self.after(0, self._update_stats)
        self.after(0, self._set_status, f"收到新回复建议（{name}）")

    def _on_log(self, msg):
        self.after(0, self._append_log, msg)

    # ---------- 实时交互动作 ----------

    def _send_manual(self, content):
        """手动发送弹幕：进入与真实弹幕完全相同的处理管线。"""
        event = DanmakuEvent(user="演示观众", content=content,
                             timestamp=time.time(), manual=True)
        self.event_bus.publish(EVT_DANMAKU, event)
        self.coordinator.on_danmaku(event)
        self._set_status("已发送手动弹幕，进入实时处理管线")

    def _flush_now(self):
        """⚡ 立即处理：不等聚合窗口攒满，马上出建议。"""
        n = self.coordinator.pending_count
        self.coordinator.process_buffer()
        self._set_status(f"已立即处理 {n} 条待处理弹幕" if n
                         else "当前没有待处理弹幕")

    def _set_aggregate(self, count, seconds):
        """聚合窗口在线调节，改完即生效。"""
        try:
            c, s = int(count), int(seconds)
        except (TypeError, ValueError):
            return
        if c < 1 or s < 1:
            return
        self.coordinator.set_aggregate(c, s)
        self._set_status(f"聚合窗口已调整为：攒 {c} 条 / {s} 秒")

    def _adopt_reply(self, content):
        """采纳建议：复制到剪贴板 + 弹幕流上屏标记为主播回复。"""
        self.clipboard_clear()
        self.clipboard_append(content)
        self.danmaku_panel.append_host(content)
        self._set_status("已复制建议并上屏为主播回复")

    def _toggle_pause(self):
        """暂停 / 继续弹幕源（手动发送不受影响）。"""
        pause = getattr(self.provider, "pause", None)
        resume = getattr(self.provider, "resume", None)
        if not pause or not resume:
            self._set_status("当前弹幕源不支持暂停")
            return
        if self._provider_paused:
            resume()
            self._provider_paused = False
            self.pause_btn.configure(text="⏸ 暂停弹幕")
            self.dot_provider.set_state(True, "弹幕源运行中")
            self._set_status("弹幕源已继续")
        else:
            pause()
            self._provider_paused = True
            self.pause_btn.configure(text="▶ 继续弹幕")
            self.dot_provider.set_state(None, "弹幕源已暂停")
            self._set_status("弹幕源已暂停（手动发送不受影响）")

    def _clear_danmaku(self):
        self.danmaku_panel.clear()
        self._set_status("弹幕流已清空")

    # ---------- 统计 / 日志 / 状态 ----------

    def _update_stats(self):
        s = self._stats
        self.stat_values["danmaku"].configure(text=str(s["danmaku"]))
        self.stat_values["reply"].configure(text=str(s["reply"]))
        total = s["template"] + s["local"] + s["cloud"] + s["fallback"]
        hit = f"{s['template'] * 100 // total}%" if total else "—"
        self.stat_values["hit"].configure(text=hit)
        b = self.coordinator.budget
        self.stat_values["cost"].configure(text=f"¥{b.spent:.2f}")

    def _tick_pending(self):
        """每 2 秒刷新右下角的待处理数与云端预算。"""
        n = self.coordinator.pending_count
        b = self.coordinator.budget
        self.pending_label.configure(
            text=f"待处理 {n} 条　·　云端预算 {b.remaining_calls}/{b.max_calls} 次")
        self.after(2000, self._tick_pending)

    def _append_log(self, msg):
        t = time.strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{t}] {msg}\n")
        lines = int(self.log_text.index("end-1c").split(".")[0])
        if lines > 300:  # 只保留最近 300 行，防止长时间直播内存膨胀
            self.log_text.delete("1.0", f"{lines - 300}.0")
        self.log_text.configure(state="disabled")
        self.log_text.see("end")

    def _set_status(self, msg):
        self.status_label.configure(text=msg)

    # ---------- 后台健康检查 ----------

    def _health_loop(self):
        while True:
            local = self.coordinator.local_ai
            if local is None:
                state = (None, "本地AI未启用")
            else:
                try:
                    ok = local.is_available()
                except Exception:
                    ok = False
                state = (True, "Ollama 在线") if ok else (False, "Ollama 离线")
            try:
                self.after(0, self.dot_ollama.set_state, *state)
            except Exception:
                return  # 窗口已关闭，退出线程
            time.sleep(HEALTH_CHECK_INTERVAL)

    # ---------- 话题生成 ----------

    def _on_generate_topic(self):
        """点击「生成话题」：后台线程生成，避免阻塞 UI。"""
        self._set_status("正在生成话题…")

        def work():
            topic = self.coordinator.generate_topic()
            self.after(0, self._show_topic, topic)

        threading.Thread(target=work, daemon=True).start()

    def _show_topic(self, topic):
        if topic:
            self.teleprompter_panel.set_text(topic)
            self._set_status("话题已生成")
        else:
            self.teleprompter_panel.set_text(
                "（暂无法生成话题：请启动本地 Ollama 或配置云端 key）")
            self._set_status("话题生成失败（无可用 AI）")

    def _on_close(self):
        """关闭窗口时优雅停止后台线程。"""
        self.provider.stop()
        self.coordinator.stop()
        self.destroy()
