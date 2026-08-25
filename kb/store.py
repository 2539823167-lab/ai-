"""知识库：SimpleKB（内置零依赖）+ ChromaKB（可选语义检索）。

默认用 SimpleKB（子串匹配 + 简单打分），零第三方依赖、学习友好；
需要语义检索时再装 chromadb，走 ChromaKB（bge-m3 向量模型）。
"""
import json
import urllib.request
import uuid
from abc import ABC, abstractmethod


class KBStore(ABC):
    """知识库抽象：新增 / 检索 / 删除 / 全量列表。"""

    @abstractmethod
    def add(self, text, meta=None):
        """新增一条知识，返回条目 id。"""

    @abstractmethod
    def search(self, query, top_k=3):
        """按 query 检索，返回 [{id, text, score}, ...]。"""

    @abstractmethod
    def delete(self, item_id):
        """删除指定条目。"""

    @abstractmethod
    def list_all(self):
        """返回全部条目列表。"""


class SimpleKB(KBStore):
    """零依赖实现：子串命中计分，适合小数据量演示。"""

    def __init__(self):
        self._items = {}  # id -> {"id", "text", "meta"}

    def add(self, text, meta=None):
        item_id = uuid.uuid4().hex
        self._items[item_id] = {"id": item_id, "text": text, "meta": meta or {}}
        return item_id

    def search(self, query, top_k=3):
        scored = []
        for item in self._items.values():
            score = self._score(query, item["text"])
            if score > 0:
                scored.append({"id": item["id"], "text": item["text"], "score": score})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    @staticmethod
    def _score(query, text):
        """子串命中计分：整条包含得高分，逐字命中再叠加。"""
        if query in text:
            return 3.0
        return sum(0.5 for ch in query if ch in text)

    def delete(self, item_id):
        self._items.pop(item_id, None)

    def list_all(self):
        return list(self._items.values())


class OllamaEmbeddingFunction:
    """用标准库 urllib 直接调 Ollama 的 /api/embeddings，零额外依赖。

    不依赖 `ollama` python 包（chromadb 内置实现需要它），
    与项目「核心零第三方依赖、HTTP 用 urllib」的风格一致。
    chromadb 会以 list[str] 调用本对象，需返回 list[list[float]]。
    """

    def __init__(self, base_url="http://localhost:11434", model="bge-m3"):
        self.url = f"{base_url.rstrip('/')}/api/embeddings"
        self.model = model

    def name(self):
        """chromadb 用它记录 collection 的 embedding 配置。"""
        return f"ollama/{self.model}"

    def __call__(self, input):
        return [self._embed(text) for text in input]

    def _embed(self, text):
        payload = json.dumps({"model": self.model, "prompt": text}).encode("utf-8")
        req = urllib.request.Request(
            self.url, data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["embedding"]


class ChromaKB(KBStore):
    """语义检索实现：基于 chromadb 向量数据库 + 可配置 embedding 模型。

    默认用本地 Ollama 的 bge-m3 做向量化（免费、离线、契合项目技术栈），
    也可把 embedding 设为 "default" 使用 chromadb 内置默认模型。

    依赖：py -3.10 -m pip install chromadb
    向量模型（Ollama embedding 时）：ollama pull bge-m3
    """

    def __init__(self, collection="live_kb", persist_dir="./chroma_data",
                 embedding="ollama", embedding_url="http://localhost:11434",
                 embedding_model="bge-m3"):
        try:
            import chromadb
        except ImportError as e:
            raise ImportError(
                "ChromaKB 需要先安装 chromadb：py -3.10 -m pip install chromadb"
            ) from e

        embedding_fn = self._build_embedding_function(
            embedding, embedding_url, embedding_model)

        # 持久化到磁盘，重启后知识不丢失
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=collection, embedding_function=embedding_fn)

    @staticmethod
    def _build_embedding_function(embedding, base_url, model):
        """构造 embedding function：ollama（bge-m3）或 chromadb 默认。"""
        if embedding == "ollama":
            return OllamaEmbeddingFunction(base_url=base_url, model=model)
        # "default" 或 None：chromadb 内置默认模型（all-MiniLM-L6-v2）
        return None

    def add(self, text, meta=None):
        item_id = uuid.uuid4().hex
        self._collection.add(
            ids=[item_id],
            documents=[text],
            metadatas=[meta or {}],
        )
        return item_id

    def search(self, query, top_k=3):
        res = self._collection.query(query_texts=[query], n_results=top_k)
        ids = res.get("ids", [[]])[0]
        docs = res.get("documents", [[]])[0]
        dists = res.get("distances", [[]])[0]

        out = []
        for i, item_id in enumerate(ids):
            distance = dists[i] if i < len(dists) else 0.0
            # 距离越小越相似，映射到 (0, 1]，分数越大越相关
            score = 1.0 / (1.0 + distance)
            out.append({"id": item_id, "text": docs[i], "score": round(score, 3)})
        return out

    def delete(self, item_id):
        self._collection.delete(ids=[item_id])

    def list_all(self):
        res = self._collection.get()
        return [
            {"id": i, "text": d}
            for i, d in zip(res.get("ids", []), res.get("documents", []))
        ]
