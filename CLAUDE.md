# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Windows 平台的 AI 直播助手（面向抖音直播间）：抓取弹幕 → 自动判断该不该回、怎么回 → 给主播一条「建议回复」，附带提词器、话题生成、知识库管理。**Demo 级可运行，核心功能零第三方依赖**（仅 Python 标准库）。

## 常用命令

环境用 Python 3.10（本机命令 `py -3.10`，勿用 3.14）。

```bash
# 运行（无 key / 无 Ollama 也能跑通，模拟弹幕 + 模板回复）
py -3.10 main.py

# 语法检查（全部 .py）
py -3.10 -m py_compile main.py core/*.py danmaku/*.py ai/*.py kb/*.py rules/*.py ui/*.py
```

没有测试、lint、构建系统。`requirements.txt` 里全是可选依赖（已注释），核心运行时无需安装任何包：

- `chromadb` + `ollama pull bge-m3`：启用语义检索（`kb.backend = "chroma"`）
- `pypdf`：知识库导入 PDF（txt/md 零依赖）
- `websocket-client` / `protobuf` / `PyExecJS`：接入抖音真实弹幕（见 [danmaku/抖音接入说明.md](danmaku/抖音接入说明.md)）

## 架构与数据流

分层结构（上层只依赖下层抽象，不 import 具体实现）：

```
ui/       界面层（Tkinter 面板，只做展示与交互）
core/     协调层（Coordinator 大脑 + BudgetGuard 预算器 + EventBus 事件总线）
danmaku/  ai/  kb/  rules/   能力模块，通过接口被 core 调用，可替换
```

**入口与依赖装配**：[main.py](main.py) 是唯一的「组合根」——加载 `config.json`，按配置装配各模块，然后注入给 `Coordinator`。核心逻辑 `Coordinator` 不 import 任何具体实现，只依赖传入的抽象（`DanmakuProvider`、`KBStore`、AI 的 `chat` 方法）。新增/替换实现时改 main.py 即可。

**核心数据流**：

```
DanmakuProvider（mock / douyin） → 回调 on_danmaku(DanmakuEvent)
  → Coordinator 聚合窗口（攒满 5 条 或 20 秒）→ 一批弹幕
  → 三级阶梯依次尝试 → ReplySuggestion → EventBus → ui/reply_panel 展示
```

**模块间通信全靠 EventBus 解耦**（[core/events.py](core/events.py)），只有三种事件类型：`EVT_DANMAKU` / `EVT_REPLY` / `EVT_LOG`。弹幕、回复建议先转成 `DanmakuEvent` / `ReplySuggestion` 数据类再发布。

## 关键机制：省 token 三级阶梯

Coordinator 的 `_flush()` 对每批弹幕按优先级依次尝试，命中即返回、不往下走（[core/coordinator.py](core/coordinator.py)）：

| 层级 | 引擎 | 成本 | 实现 |
| --- | --- | --- | --- |
| L1 | 本地模板 | 0 token | [rules/templates.py](rules/templates.py) 关键词匹配 |
| L2 | Ollama + Qwen3-4B | 0 元 | [ai/local.py](ai/local.py)，走 `/api/chat` |
| L3 | DeepSeek deepseek-chat | 按量计费 | [ai/cloud.py](ai/cloud.py)，OpenAI 兼容 `/chat/completions` |

配套省 token 手段（协同理解）：

- **聚合窗口**：多条弹幕合并成一次批量请求（`aggregate.count` / `aggregate.seconds` 配置）
- **BudgetGuard 预算器**（[core/budget.py](core/budget.py)）：上限 50 次 / 2 元，超限后 `can_call_cloud()` 返回 False，L3 自动降级
- **精简 prompt**（[ai/prompts.py](ai/prompts.py)）：`SYSTEM_PROMPT` 固定前缀以命中 DeepSeek 前缀缓存，批量请求一次产多条建议
- 三级都未产出时兜底返回 `source="fallback"` 的空建议，避免界面空着

`ReplySuggestion.source` 的取值 ∈ `{template, local, cloud, fallback}`，UI 据此着色/标中文名。

## 线程模型（易错点）

弹幕来自**后台线程**（`MockProvider` 的 daemon 线程循环，[danmaku/mock.py](danmaku/mock.py)），UI 是 Tkinter 主线程。**跨线程改 UI 必须回主线程**：`Coordinator` 里的 `EventBus.publish` 在后台线程触发，UI 侧回调统一用 `self.after(0, ...)` 把更新调度回主线程（见 [ui/app.py](ui/app.py) 的 `_on_danmaku` / `_on_reply`）。

`Coordinator` 内部用 `threading.Lock` 保护 `_buffer` / `_recent` 两个共享集合。话题生成 `generate_topic()` 是阻塞调用（AI 可能耗时数秒），由 UI 另起后台线程调用，再 `after(0, ...)` 回主线程。

## 配置与约定

- 全部配置在 [config.json](config.json)，`main.py` 启动时读取。云端 API key 优先读环境变量 `DEEPSEEK_API_KEY`，其次才用 `config.json` 里的 `ai.cloud.api_key`（避免明文）。
- `danmaku.provider` 取值 `mock`（默认）或 `douyin`。**抖音目前是接入脚手架**：`DouyinProvider` 的 URL→room_id 解析、线程/重连已实现，但签名、WebSocket、protobuf 三个接入点还是 `raise NotImplementedError`，需按 [danmaku/抖音接入说明.md](danmaku/抖音接入说明.md) 补全。
- **优雅降级是硬约束**：任何 AI 调用失败/不可用都要回退到下一级或模板兜底，绝不因异常卡死直播。`Coordinator` 对本地 AI 有 60 秒可用性缓存（失败后 60 秒内跳过 L2 避免反复连刷屏）。
- 代码注释与文档均为中文，新代码保持一致。

详细设计见 [方案.md](方案.md)（含接口签名、里程碑、验收标准）。
