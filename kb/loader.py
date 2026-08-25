"""文档加载器：把文件提取成文本并写入知识库。

支持的文件类型：
  - .txt / .md / .markdown：纯文本，直接读取（零依赖）
  - .pdf：用 pypdf 提取文本（可选依赖，未安装时给出提示）

设计上把「文件 → 文本」和「文本 → 分块写入」分开，
方便后续扩展新格式（例如 .docx，只需在 extract_text 加一个分支）。
"""
import os


def extract_text(path):
    """按扩展名提取文件全文。"""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".txt", ".md", ".markdown"):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    if ext == ".pdf":
        return _extract_pdf(path)
    raise ValueError(f"暂不支持的文件类型：{ext}（支持 .txt / .md / .pdf）")


def _extract_pdf(path):
    """用 pypdf 提取 PDF 文本，兼容新版 pypdf 与旧版 PyPDF2。"""
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            raise ImportError(
                "解析 PDF 需要安装 pypdf：py -3.10 -m pip install pypdf"
            )
    reader = PdfReader(path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def split_text(text, chunk_size=500):
    """把长文本按固定长度切块。

    长文档整篇存一个向量会稀释语义，切块后检索更精准；
    默认 500 字一块，可按需调整。
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]


def load_file(kb, path, chunk_size=500):
    """提取文件文本并分块写入知识库，返回写入的块数。"""
    text = extract_text(path)
    chunks = split_text(text, chunk_size)
    for chunk in chunks:
        kb.add(chunk, meta={"source": os.path.basename(path)})
    return len(chunks)
