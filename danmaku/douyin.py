"""抖音直播间弹幕源 —— 真实接入（移植自 DouyinLiveWebFetcher，AGPL-3.0）。

抖音直播弹幕走 WebSocket + Protobuf + X-Bogus 签名，流程：
  1) 从直播间首页拿 ttwid Cookie，再正则提取真正的 room_id；
  2) 构造 WebSocket 地址，用 sign.js（MiniRacer / 内置 V8 执行）算出 X-Bogus 签名；
  3) 连上后收二进制帧：PushFrame → gzip 解压 → Response → 过滤 WebcastChatMessage；
  4) 解析出 user.nick_name + content，转成 DanmakuEvent 回调 on_danmaku。

签名与协议定义来自开源项目 DouyinLiveWebFetcher（AGPL-3.0），
详见 danmaku/douyin_protocol/NOTICE.md。抖音协议频繁变更，失效时对照上游仓库更新。

用法（接入完成后）：
    from danmaku.douyin import DouyinProvider
    provider = DouyinProvider(on_danmaku, live_url="https://live.douyin.com/xxxx")
    provider.start()   # 后台线程持续吐弹幕，断线自动重连
    ...
    provider.stop()
"""
import gzip
import hashlib
import os
import random
import re
import string
import threading
import time
import urllib.parse

from core.events import DanmakuEvent
from danmaku.base import DanmakuProvider

# 第三方依赖：仅 provider=douyin 时才需要（见 requirements-douyin.txt）
try:
    import requests
    import websocket
    from py_mini_racer import MiniRacer
    from danmaku.douyin_protocol.protobuf.douyin import (
        ChatMessage,
        PushFrame,
        Response,
    )
except ImportError as e:
    raise ImportError(
        "抖音真实弹幕需要额外依赖，请先安装："
        "py -3.10 -m pip install -r requirements-douyin.txt"
    ) from e


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

# 固定设备 / 用户 id（上游实测值，学习演示用）
_DID = "7319483754668557238"

# WebSocket 推送地址模板（webcast 系列域名会按房间哈希分发，不唯一）
# {room_id} 与 {did} 在 _build_wss_url 里填充。
WSS_TEMPLATE = (
    "wss://webcast100-ws-web-lq.douyin.com/webcast/im/push/v2/"
    "?app_name=douyin_web&version_code=180800"
    "&webcast_sdk_version=1.0.14-beta.0&update_version_code=1.0.14-beta.0"
    "&compress=gzip&device_platform=web&cookie_enabled=true"
    "&screen_width=1536&screen_height=864&browser_language=zh-CN"
    "&browser_platform=Win32&browser_name=Mozilla"
    "&browser_version=5.0%20(Windows%20NT%2010.0;%20Win64;%20x64)%20"
    "AppleWebKit/537.36%20(KHTML,%20like%20Gecko)%20Chrome/126.0.0.0%20Safari/537.36"
    "&browser_online=true&tz_name=Asia/Shanghai"
    "&cursor=d-1_u-1_fh-7392091211001140287_t-1721106114633_r-1"
    "&internal_ext=internal_src:dim|wss_push_room_id:{room_id}|wss_push_did:{did}"
    "|first_req_ms:1721106114541|fetch_time:1721106114633|seq:1|wss_info:0-1721106114633-0-0|"
    "wrds_v:7392094459690748497"
    "&host=https://live.douyin.com&aid=6383&live_id=1&did_rule=3"
    "&endpoint=live_pc&support_wrds=1"
    "&user_unique_id={did}&im_path=/webcast/im/fetch/&identity=audience"
    "&need_persist_msg_count=15&insert_task_id=&live_reason="
    "&room_id={room_id}&heartbeatDuration=0"
)

# sign.js 要求按固定顺序取这些参数拼串后再 MD5（顺序不能改）
_SIGN_PARAMS = (
    "live_id,aid,version_code,webcast_sdk_version,room_id,sub_room_id,"
    "sub_channel_id,did_rule,user_unique_id,device_platform,device_type,ac,identity"
).split(",")


def _generate_ms_token(length=182):
    """产生 Cookie 里的 msToken 随机字段（上游做法：随机 107 位字符）。"""
    base = string.ascii_letters + string.digits + "-_"
    return "".join(random.choice(base) for _ in range(length))


class DouyinProvider(DanmakuProvider):
    def __init__(self, on_danmaku, live_url=None, room_id=None,
                 reconnect_interval=5.0):
        super().__init__(on_danmaku)
        self.live_url = live_url
        # room_id 即网页版 web_rid（https://live.douyin.com/xxxx 的 xxxx）
        self.room_id = room_id
        self.reconnect_interval = reconnect_interval

        self._running = False
        self._thread = None
        self._ws = None

        self._session = requests.Session()
        self._session.headers["User-Agent"] = USER_AGENT

        # 解析结果缓存
        self._ttwid = None
        self._real_room_id = None

        # sign.js 与 MiniRacer 惰性加载（首次连接时才初始化，避免无网络时也编译）
        self._js_ctx = None

    # ---------- 第 1 步：URL / 首页 → room_id ----------

    def _resolve_web_rid(self):
        """从分享链接/直播间 URL 解析 web_rid。

        支持：
          - https://live.douyin.com/123456789
          - https://v.douyin.com/xxxxxx/  （短链，requests 自动跟随重定向）
        """
        if self.room_id:
            return str(self.room_id)

        if not self.live_url:
            raise ValueError("请提供 live_url 或 room_id")

        resp = self._session.get(self.live_url, timeout=10)
        final_url = resp.url  # 短链重定向后的最终地址
        m = re.search(r"live\.douyin\.com/(\d+)", final_url)
        if not m:
            raise ValueError(f"无法从链接解析直播间 id：{final_url}")
        return m.group(1)

    def _get_ttwid(self):
        """访问直播首页，从响应 Cookie 拿 ttwid（匿名即可，无需登录）。"""
        if self._ttwid:
            return self._ttwid
        resp = self._session.get("https://live.douyin.com/", timeout=10)
        self._ttwid = resp.cookies.get("ttwid")
        if not self._ttwid:
            raise ValueError("未能获取 ttwid Cookie，抖音可能已变更接口或要求登录")
        return self._ttwid

    def _get_real_room_id(self, web_rid, ttwid):
        """从直播间 HTML 里正则提取真正的 room_id（数字型，供 WebSocket 用）。"""
        if self._real_room_id:
            return self._real_room_id
        url = f"https://live.douyin.com/{web_rid}"
        headers = {
            "Cookie": (
                f"ttwid={ttwid}; msToken={_generate_ms_token()}; "
                "__ac_nonce=0123407cc00a9e438deb4"
            ),
        }
        resp = self._session.get(url, headers=headers, timeout=10)
        room_id = self._extract_room_id(resp.text)
        if not room_id:
            raise ValueError("未能从直播间页面解析 room_id，协议可能已变更")
        self._real_room_id = room_id
        return room_id

    @staticmethod
    def _extract_room_id(html):
        """兼容 roomId 的转义与未转义两种写法，命中返回数字 id。"""
        for pattern in (
            r'roomId\\":\\"(\d+)\\"',   # HTML 内嵌 JSON 转义引号（上游实测）
            r'roomId":"(\d+)"',          # 未转义形式
        ):
            m = re.search(pattern, html)
            if m:
                return m.group(1)
        return None

    # ---------- 第 2 步：签名（sign.js，MiniRacer/V8 执行） ----------

    def _get_js_ctx(self):
        """惰性加载 sign.js 到 MiniRacer，复用同一 V8 上下文。"""
        if self._js_ctx is None:
            sign_path = os.path.join(
                os.path.dirname(__file__), "douyin_protocol", "sign.js")
            with open(sign_path, "r", encoding="utf-8") as f:
                script = f.read()
            self._js_ctx = MiniRacer()
            self._js_ctx.eval(script)
        return self._js_ctx

    def _signature(self, wss):
        """按 sign.js 要求：固定顺序拼参数 → MD5 → 调用 get_sign 得到签名。"""
        query = urllib.parse.urlparse(wss).query
        wss_maps = {}
        for item in query.split("&"):
            if "=" not in item:
                continue
            wss_maps[item.split("=")[0]] = item.split("=")[-1]

        param = ",".join(f"{k}={wss_maps.get(k, '')}" for k in _SIGN_PARAMS)
        md5 = hashlib.md5(param.encode("utf-8")).hexdigest()
        return self._get_js_ctx().call("get_sign", md5)

    def _build_wss_url(self, room_id):
        """构造 WebSocket 连接地址。"""
        return WSS_TEMPLATE.format(room_id=room_id, did=_DID)

    # ---------- 第 3 步：WebSocket 连接与消息循环 ----------

    def _connect(self, room_id, ttwid):
        """建立连接并阻塞接收（run_forever 直到断线才返回）。"""
        wss = self._build_wss_url(room_id)
        signature = self._signature(wss)
        wss += f"&signature={signature}"

        self._ws = websocket.WebSocketApp(
            wss,
            header={"Cookie": f"ttwid={ttwid}", "User-Agent": USER_AGENT},
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        self._ws.run_forever()

    def _on_open(self, ws):
        print("[Douyin] WebSocket 连接成功")
        threading.Thread(target=self._send_heartbeat, args=(ws,), daemon=True).start()

    def _send_heartbeat(self, ws):
        """心跳线程：每 5s 发一个 hb 帧保活，连接关闭则退出。"""
        while self._running:
            try:
                ws.send(PushFrame(payload_type="hb").SerializeToString(),
                        websocket.ABNF.OPCODE_PING)
            except Exception:
                break
            time.sleep(5)

    def _on_message(self, ws, message):
        """收到二进制帧：PushFrame → gzip 解压 → Response → 过滤聊天消息。"""
        try:
            frame = PushFrame().parse(message)
            if not frame.payload:
                return
            resp = Response().parse(gzip.decompress(frame.payload))
        except Exception:
            return  # 单帧解析失败忽略，不中断连接

        # 需要 ack 的帧回确认，服务器才会继续推送
        if resp.need_ack:
            try:
                ack = PushFrame(
                    log_id=frame.log_id,
                    payload_type="ack",
                    payload=resp.internal_ext.encode("utf-8"),
                ).SerializeToString()
                ws.send(ack, websocket.ABNF.OPCODE_BINARY)
            except Exception:
                pass

        for msg in resp.messages_list:
            if msg.method == "WebcastChatMessage" and msg.payload:
                try:
                    chat = ChatMessage().parse(msg.payload)
                    self._emit(chat.user.nick_name, chat.content)
                except Exception:
                    continue

    def _on_error(self, ws, error):
        print(f"[Douyin] WebSocket 错误：{error}")

    def _on_close(self, ws, *args):
        print("[Douyin] WebSocket 连接关闭")

    # ---------- 线程生命周期 ----------

    def _run(self):
        """后台线程主循环：解析房间 → 连接 → 断线重连。"""
        try:
            web_rid = self._resolve_web_rid()
            ttwid = self._get_ttwid()
            real_room_id = self._get_real_room_id(web_rid, ttwid)
            print(f"[Douyin] 房间解析成功：web_rid={web_rid}，room_id={real_room_id}")
        except Exception as e:
            print(f"[Douyin] 房间解析失败：{e}")
            return

        while self._running:
            try:
                self._connect(real_room_id, ttwid)
            except Exception as e:
                print(f"[Douyin] 连接异常，{self.reconnect_interval}s 后重连：{e}")
            if not self._running:
                break
            time.sleep(self.reconnect_interval)

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass

    # ---------- 工具：把解析结果转成统一事件 ----------

    def _emit(self, nick_name, content):
        """把一条弹幕转成 DanmakuEvent 回调出去。"""
        self.on_danmaku(DanmakuEvent(
            user=nick_name,
            content=content,
            timestamp=time.time(),
        ))
