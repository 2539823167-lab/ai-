"""知识库管理面板：关键词检索 + 新增条目 + 删除 + 文档导入。"""
import tkinter as tk
from tkinter import ttk

from ui import theme


class KBPanel(theme.Card):
    def __init__(self, master, kb):
        super().__init__(master)
        self.kb = kb
        self._view = []  # 当前列表对应的条目（id/text），供删除定位

        # ---- 标题行：知识库 · 条目数 ----
        header = tk.Frame(self, bg=theme.CARD)
        header.pack(fill="x", padx=10, pady=(8, 4))
        ttk.Label(header, text="📚 知识库", style="Title.TLabel").pack(side="left")
        self.count_label = ttk.Label(header, text="0 条", style="Muted.TLabel")
        self.count_label.pack(side="left", padx=(8, 0))

        # ---- 检索区 ----
        search = tk.Frame(self, bg=theme.CARD)
        search.pack(fill="x", padx=8, pady=(0, 4))
        self.search_entry = theme.PlaceholderEntry(
            search, placeholder="搜索知识库，回车检索…")
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.search_entry.bind("<Return>", lambda _e: self._search())
        ttk.Button(search, text="检索", style="Tool.TButton",
                   command=self._search).pack(side="left", padx=(6, 0))

        # ---- 条目列表 ----
        list_body = tk.Frame(self, bg=theme.CARD)
        list_body.pack(fill="both", expand=True, padx=8)
        self.listbox = tk.Listbox(list_body, bg=theme.CARD_ALT, fg=theme.FG,
                                  relief="flat", borderwidth=0,
                                  highlightthickness=0, font=theme.FONT_BODY,
                                  selectbackground=theme.ACCENT,
                                  selectforeground="#000000",
                                  activestyle="none", height=6)
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.bind("<Double-Button-1>", self._copy_selected)
        scrollbar = ttk.Scrollbar(list_body, orient="vertical",
                                  style="Vertical.TScrollbar",
                                  command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scrollbar.set)

        # ---- 新增 / 删除区 ----
        add = tk.Frame(self, bg=theme.CARD)
        add.pack(fill="x", padx=8, pady=(6, 8))
        self.add_entry = theme.PlaceholderEntry(
            add, placeholder="输入一条知识，回车添加…")
        self.add_entry.pack(side="left", fill="x", expand=True)
        self.add_entry.bind("<Return>", lambda _e: self._add())
        ttk.Button(add, text="添加", style="Tool.TButton",
                   command=self._add).pack(side="left", padx=(6, 0))
        ttk.Button(add, text="添加文件", style="Tool.TButton",
                   command=self._add_file).pack(side="left", padx=(6, 0))
        ttk.Button(add, text="删除选中", style="Danger.TButton",
                   command=self._delete_selected).pack(side="left", padx=(6, 0))

        self._refresh()

    # ---------- 操作 ----------

    def _add(self):
        text = self.add_entry.get().strip()
        if text:
            self.kb.add(text)
            self.add_entry.clear()
            self._refresh()

    def _add_file(self):
        """选择文档/PDF 文件，提取文本后写入知识库。"""
        from tkinter import filedialog, messagebox
        from kb import loader

        path = filedialog.askopenfilename(
            title="选择文档或 PDF",
            filetypes=[
                ("PDF 文件", "*.pdf"),
                ("文本文件", "*.txt *.md"),
                ("所有文件", "*.*"),
            ],
        )
        if not path:
            return
        try:
            count = loader.load_file(self.kb, path)
            self._refresh()
            messagebox.showinfo("已添加", f"已从文件添加 {count} 条知识")
        except Exception as e:
            messagebox.showerror("添加失败", str(e))

    def _delete_selected(self):
        """删除当前选中的知识条目（浏览 / 检索两种视图都支持）。"""
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self._view):
            self.kb.delete(self._view[idx]["id"])
            self._refresh()

    def _copy_selected(self, _event=None):
        """双击条目复制全文。"""
        sel = self.listbox.curselection()
        if sel and 0 <= sel[0] < len(self._view):
            self.clipboard_clear()
            self.clipboard_append(self._view[sel[0]]["text"])

    def _search(self):
        query = self.search_entry.get().strip()
        if not query:
            self._refresh()
            return
        hits = self.kb.search(query, top_k=20)
        self._view = hits
        self.listbox.delete(0, "end")
        for item in hits:
            self.listbox.insert("end", f"[{item['score']:.1f}] {item['text'][:80]}")
        self.count_label.configure(text=f"命中 {len(hits)} 条")

    def _refresh(self):
        """重载全量列表（含来源标注，长文本截断显示）。"""
        items = self.kb.list_all()
        self._view = items
        self.listbox.delete(0, "end")
        for item in items:
            text = item["text"]
            meta = item.get("meta") or {}
            source = meta.get("source", "") if isinstance(meta, dict) else ""
            label = f"[{source}] {text}" if source else text
            self.listbox.insert("end", label[:80])
        self.count_label.configure(text=f"{len(items)} 条")
