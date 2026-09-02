"""HTTP 小工具：统一处理 base_url 的本地回环写法，避免无谓的等待。

Windows / 部分网络环境下，连 "localhost" 时 DNS 会优先解析到 IPv6 的 ::1，
若本机未监听或防火墙拦截，一次「连接被拒绝」可能要等好几秒才报错，
再退回 IPv4。AI 引擎 / 向量服务的 base_url 默认就是 localhost，
服务没启动时每次降级探测都会被拖慢，体验像“卡住”。

这里统一把 host 为 localhost 的地址规范成 127.0.0.1（IPv4 直连），
仅改写 scheme://localhost 部分，不影响用户配置里的其他内容。
"""


def normalize_localhost(base_url):
    """把 http://localhost:端口/... 规范成 http://127.0.0.1:端口/...。

    只替换「://localhost:」（带端口的常见写法）与「://localhost/」，
    避免误伤路径或参数里出现的 localhost 字样。
    """
    if not base_url:
        return base_url
    out = base_url.replace("://localhost:", "://127.0.0.1:")
    return out.replace("://localhost/", "://127.0.0.1/")
