"""核心逻辑回归测试（仅 Python 标准库 unittest，不联网、不依赖 Ollama/DeepSeek）。

运行方式（在项目根目录）：
    py -3.10 -m unittest discover -s tests -t . -v

覆盖：模板 L1、敏感词过滤、预算器、SimpleKB 检索与持久化、
文档分块加载、Coordinator 三级阶梯与聚合窗口、话题生成降级。
"""
import os
import tempfile
import time
import unittest

from core.budget import BudgetGuard
from core.coordinator import Coordinator
from core.events import EVT_DANMAKU, EVT_LOG, EVT_REPLY, DanmakuEvent, EventBus
from core.httputil import normalize_localhost
from kb import loader
from kb.store import SimpleKB
from rules import sensitive, templates


# ---------- 测试替身（Fake） ----------

class RecordingBus(EventBus):
    """记录发布过的事件，便于断言。"""

    def __init__(self):
        super().__init__()
        self.published = []

    def publish(self, event_type, data):
        self.published.append((event_type, data))
        super().publish(event_type, data)


class FakeLocal:
    """本地 AI 替身：可配置成功返回或抛异常。"""

    def __init__(self, text="本地建议文案", fail=False):
        self.text = text
        self.fail = fail
        self.calls = 0

    def chat(self, messages):
        self.calls += 1
        if self.fail:
            raise ConnectionError("模拟 Ollama 未启动")
        return self.text


class FakeCloud:
    """云端 AI 替身：记录调用次数，可选抛异常。"""

    def __init__(self, text="云端建议文案", fail=False):
        self.text = text
        self.fail = fail
        self.calls = 0

    def chat(self, messages):
        self.calls += 1
        if self.fail:
            raise RuntimeError("模拟云端接口失败")
        return self.text


def make_coordinator(local_ai=None, cloud_ai=None, kb=None, agg=None, budget=None):
    """按测试需要装配一个 Coordinator（不启动定时器，靠条数阈值触发）。"""
    config = {"aggregate": agg or {"count": 2, "seconds": 20}}
    bus = RecordingBus()
    if budget is None:
        budget = BudgetGuard(max_calls=50, max_cost=2.0)
    if kb is None:
        kb = SimpleKB()
    coord = Coordinator(
        config=config, event_bus=bus, budget=budget,
        templates=templates, sensitive=sensitive,
        local_ai=local_ai, cloud_ai=cloud_ai, kb=kb,
    )
    return coord, bus


def danmaku(text):
    return DanmakuEvent(user="测试用户", content=text, timestamp=time.time())


def replies(bus):
    """取所有 EVT_REPLY 事件的数据。"""
    return [data for typ, data in bus.published if typ == EVT_REPLY]


# ---------- 用例 ----------

class TestTemplates(unittest.TestCase):
    def test_price_hit(self):
        self.assertIsNotNone(templates.match_template("这个多少钱？"))

    def test_follow_hit(self):
        self.assertIsNotNone(templates.match_template("已关注，加油！"))

    def test_viewer_thanks_not_gift_reply(self):
        """回归：观众道谢不能命中「打赏感谢」模板，回复方向不能反。"""
        reply = templates.match_template("谢谢主播的讲解")
        self.assertIsNotNone(reply)
        self.assertNotIn("礼物", reply)          # 不是感谢打赏的口径
        self.assertIn("不客气", reply)           # 是主播回应道谢的口径

    def test_real_gift_still_hits_gift_reply(self):
        reply = templates.match_template("送了个小心心")
        self.assertIn("礼物", reply)

    def test_miss_returns_none(self):
        self.assertIsNone(templates.match_template("主播唱首歌呗"))

    def test_new_hf_keywords(self):
        """新补充的高频模板都能命中。"""
        for text in ("怎么下单呀？", "能便宜点吗？", "有没有小样赠送？", "主播下次几点播？"):
            self.assertIsNotNone(templates.match_template(text), text)


class TestSensitive(unittest.TestCase):
    def test_replace_equal_length(self):
        self.assertEqual(sensitive.filter_text("你傻逼了"), "你**了")
        self.assertEqual(sensitive.filter_text("这是个垃圾"), "这是个**")

    def test_no_sensitive_unchanged(self):
        self.assertEqual(sensitive.filter_text("正常弹幕内容"), "正常弹幕内容")


class TestBudget(unittest.TestCase):
    def test_call_limit(self):
        b = BudgetGuard(max_calls=3, max_cost=10)
        self.assertTrue(b.can_call_cloud())
        b.record_call(0.01)
        b.record_call(0.01)
        b.record_call(0.01)
        self.assertFalse(b.can_call_cloud())
        self.assertEqual(b.remaining_calls, 0)

    def test_cost_limit(self):
        b = BudgetGuard(max_calls=100, max_cost=0.5)
        b.record_call(0.4)
        self.assertTrue(b.can_call_cloud())
        b.record_call(0.2)  # 累计 0.6 > 0.5
        self.assertFalse(b.can_call_cloud())

    def test_spent(self):
        b = BudgetGuard(max_calls=50, max_cost=2.0)
        b.record_call(0.01)
        b.record_call(0.02)
        self.assertAlmostEqual(b.spent, 0.03)


class TestSimpleKB(unittest.TestCase):
    def test_add_search_delete(self):
        kb = SimpleKB()
        kb.add("我们主营蓝牙耳机，支持降噪")
        kb.add("全场满 99 包邮，偏远地区除外")
        kb.add("发货时间：付款后 48 小时内")

        hits = kb.search("耳机", top_k=3)
        self.assertTrue(hits)
        self.assertEqual(hits[0]["text"], "我们主营蓝牙耳机，支持降噪")
        self.assertGreaterEqual(hits[0]["score"], 3.0)

        # 删除后检索不到
        kb.delete(hits[0]["id"])
        self.assertNotIn("耳机", [i["text"] for i in kb.list_all()])

    def test_persist_roundtrip(self):
        """写入文件 → 重建实例 → 数据还在（重启不丢）。"""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "simple_kb.json")
            kb1 = SimpleKB(persist_path=path)
            kb1.add("第一条知识：苹果产地山东")
            kb1.add("第二条知识：甜度 15 以上")

            kb2 = SimpleKB(persist_path=path)
            texts = [i["text"] for i in kb2.list_all()]
            self.assertEqual(len(texts), 2)
            self.assertIn("第一条知识：苹果产地山东", texts)

            # 删除也要落盘
            kb2.delete(kb2.list_all()[0]["id"])
            kb3 = SimpleKB(persist_path=path)
            self.assertEqual(len(kb3.list_all()), 1)


class TestLoader(unittest.TestCase):
    def test_split_text(self):
        self.assertEqual(loader.split_text("短文本"), ["短文本"])
        chunks = loader.split_text("长" * 1200, chunk_size=500)
        self.assertEqual(len(chunks), 3)
        self.assertEqual("".join(chunks), "长" * 1200)

    def test_extract_txt_and_load_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "资料.txt")
            with open(p, "w", encoding="utf-8") as f:
                f.write("知识点A\n" * 10)
            self.assertIn("知识点A", loader.extract_text(p))

            kb = SimpleKB()
            n = loader.load_file(kb, p, chunk_size=50)
            self.assertGreaterEqual(n, 1)
            metas = [i.get("meta", {}) for i in kb.list_all()]
            self.assertTrue(all(m.get("source") == "资料.txt" for m in metas))

    def test_unsupported_type(self):
        with self.assertRaises(ValueError):
            loader.extract_text("x.docx")


class TestHttputil(unittest.TestCase):
    def test_localhost_normalized(self):
        self.assertEqual(normalize_localhost("http://localhost:11434"),
                         "http://127.0.0.1:11434")
        self.assertEqual(normalize_localhost("http://localhost:11434/api"),
                         "http://127.0.0.1:11434/api")
        # 非 localhost 地址不受影响
        self.assertEqual(normalize_localhost("https://api.deepseek.com"),
                         "https://api.deepseek.com")
        self.assertEqual(normalize_localhost(""), "")


class TestCoordinatorPipeline(unittest.TestCase):
    def test_aggregate_flush_on_count(self):
        """攒满 max_count 条才触发一次处理，未攒满不回复。"""
        coord, bus = make_coordinator(agg={"count": 3, "seconds": 20})
        coord.on_danmaku(danmaku("闲聊弹幕"))
        self.assertEqual(replies(bus), [])          # 1/3，不触发
        coord.on_danmaku(danmaku("继续闲聊"))
        self.assertEqual(replies(bus), [])          # 2/3，不触发
        coord.on_danmaku(danmaku("主播今天状态不错"))
        self.assertEqual(len(replies(bus)), 1)      # 3/3，触发

    def test_l1_template_reply(self):
        coord, bus = make_coordinator()
        coord.on_danmaku(danmaku("这个多少钱？"))
        coord.on_danmaku(danmaku("随便聊聊"))
        sug = replies(bus)[0]
        self.assertEqual(sug.source, "template")

    def test_l2_local_reply(self):
        local = FakeLocal(text="本地生成的回复")
        coord, bus = make_coordinator(local_ai=local)
        coord.on_danmaku(danmaku("主播唱首歌吧"))
        coord.on_danmaku(danmaku("来一段"))
        sug = replies(bus)[0]
        self.assertEqual(sug.source, "local")
        self.assertEqual(sug.content, "本地生成的回复")
        self.assertGreaterEqual(local.calls, 1)

    def test_l2_failure_falls_to_cloud(self):
        """本地挂了 → 自动降级云端；云端也不可用 → 兜底 fallback。"""
        local = FakeLocal(text="x", fail=True)
        cloud = FakeCloud(text="云端救场", fail=False)
        coord, bus = make_coordinator(local_ai=local, cloud_ai=cloud)
        coord.on_danmaku(danmaku("主播讲个笑话吧"))
        coord.on_danmaku(danmaku("气氛有点安静"))
        sug = replies(bus)[0]
        self.assertEqual(sug.source, "cloud")
        self.assertEqual(cloud.calls, 1)

    def test_no_ai_fallback(self):
        """无本地无云端 → 兜底建议，绝不卡死。"""
        coord, bus = make_coordinator()
        coord.on_danmaku(danmaku("主播讲个笑话吧"))
        coord.on_danmaku(danmaku("气氛有点安静"))
        sug = replies(bus)[0]
        self.assertEqual(sug.source, "fallback")

    def test_l2_retry_cache(self):
        """本地失败后 60 秒缓存：后续批次不再反复尝试（避免连不上还一直打）。"""
        local = FakeLocal(text="x", fail=True)
        coord, bus = make_coordinator(local_ai=local)
        coord.on_danmaku(danmaku("主播讲个笑话吧"))
        coord.on_danmaku(danmaku("气氛有点安静"))
        self.assertEqual(local.calls, 1)            # 第一次失败
        self.assertFalse(coord._local_ok)

        # 到期前：跳过 L2（calls 不再增加）
        coord.on_danmaku(danmaku("再聊两句"))
        coord.on_danmaku(danmaku("继续继续"))
        self.assertEqual(local.calls, 1)

        # 手动把重试时间拨回过去，模拟 60 秒到期 → 会再试一次
        coord._local_retry_at = 0
        coord.on_danmaku(danmaku("再来两句"))
        coord.on_danmaku(danmaku("继续继续"))
        self.assertEqual(local.calls, 2)

    def test_cloud_budget_gate(self):
        """云端预算用尽后自动降级，不再调用云端。"""
        cloud = FakeCloud(text="云端建议")
        budget = BudgetGuard(max_calls=1, max_cost=2.0)
        coord, bus = make_coordinator(cloud_ai=cloud, budget=budget)
        coord.on_danmaku(danmaku("主播讲个笑话吧"))
        coord.on_danmaku(danmaku("气氛有点安静"))
        self.assertEqual(replies(bus)[0].source, "cloud")
        self.assertEqual(cloud.calls, 1)

        coord.on_danmaku(danmaku("再来一个笑话"))
        coord.on_danmaku(danmaku("讲嘛讲嘛"))
        self.assertEqual(cloud.calls, 1)            # 预算用尽，不再调用
        self.assertEqual(replies(bus)[1].source, "fallback")

    def test_sensitive_filter_before_ai(self):
        """进 AI 前先过滤敏感词，模板匹配拿到的是清洗后的文本。"""
        coord, bus = make_coordinator()
        coord.on_danmaku(danmaku("你傻逼，多少钱？"))
        coord.on_danmaku(danmaku("随便聊聊"))
        sug = replies(bus)[0]
        self.assertEqual(sug.source, "template")

    def test_generate_topic_no_ai(self):
        """无可用 AI 时生成话题返回 None（UI 负责提示用户）。"""
        coord, _ = make_coordinator()
        coord.on_danmaku(danmaku("最近天气好热"))
        self.assertIsNone(coord.generate_topic())

    def test_generate_topic_local(self):
        """本地 AI 可用时，话题由本地生成。"""
        local = FakeLocal(text="聊聊夏日消暑小妙招～")
        coord, _ = make_coordinator(local_ai=local)
        coord.on_danmaku(danmaku("最近天气好热"))
        self.assertEqual(coord.generate_topic(), "聊聊夏日消暑小妙招～")


if __name__ == "__main__":
    unittest.main(verbosity=2)
