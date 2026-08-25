"""知识库管理面板：关键词检索 + 新增条目 + 列表展示。"""
import tkinter as tk
from tkinter import ttk

from ui import theme


class KBPanel(ttk.Frame):
    def __init__(self, master, kb):
        super().__init__(master, style="Card.TFrame")
        self.kb = kb
        ttk.Label(self, text="知识库", style="Title.TLabel").pack(
            anchor="w", padx=10, pady=(8, 4))

        # 检索区
        search = ttk.Frame(self, style="Card.TFrame")
        search.pack(fill="x", padx=8, pady=(0, 4))
        self.search_var = tk.StringVar()
        ttk.Entry(search, textvariable=self.search_var).pack(
            side="left", fill="x", expand=True)
        ttk.Button(search, text="检索", command=self._search).pack(
            side="left", padx=(6, 0))

        # 条目列表
        self.listbox = tk.Listbox(self, bg=theme.CARD_ALT, fg=theme.FG,
                                  relief="flat", borderwidth=0,
                                  highlightthickness=0, font=theme.FONT_BODY,
                                  selectbackground=theme.ACCENT,
                                  selectforeground="#000000")
        self.listbox.pack(fill="both", expand=True, padx=8)

        # 新增区
        add = ttk.Frame(self, style="Card.TFrame")
        add.pack(fill="x", padx=8, pady=(6, 8))
        self.add_var = tk.StringVar()
        ttk.Entry(add, textvariable=self.add_var).pack(
            side="left", fill="x", expand=True)
        ttk.Button(add, text="添加", command=self._add).pack(
            side="left", padx=(6, 0))
        ttk.Button(add, text="添加文件", command=self._add_file).pack(
            side="left", padx=(6, 0))

        self._refresh()

    def _add(self):
        text = self.add_var.get().strip()
        if text:
            self.kb.add(text)
            self.add_var.set("")
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

    def _search(self):
        query = self.search_var.get().strip()
        self.listbox.delete(0, "end")
        if not query:
            self._refresh()
            return
        for item in self.kb.search(query):
            self.listbox.insert("end", f"[{item['score']:.1f}] {item['text']}")

    def _refresh(self):
        """重载全量列表（含来源标注，长文本截断显示）。"""
        self.listbox.delete(0, "end")
        for item in self.kb.list_all():
            text = item["text"]
            meta = item.get("meta") or {}
            source = meta.get("source", "") if isinstance(meta, dict) else ""
            label = f"[{source}] {text}" if source else text
            self.listbox.insert("end", label[:80])
