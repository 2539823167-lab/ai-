# Windows AI 直播助手（抖音）

抓取直播间弹幕 → 自动判断该不该回、怎么回 → 给主播一条「建议回复」，
附带提词器、话题生成、知识库管理。**Demo 级可运行，核心零第三方依赖**（仅 Python 标准库）。

深色主题界面：头部状态灯 + 统计卡，四象限布局（弹幕流 / 回复建议 / 知识库 / 提词器），
底部运行日志实时展示三级阶梯走向，状态栏显示待处理条数与云端预算。

## 功能特性

- **弹幕获取**：默认模拟弹幕，可插拔真实 Provider（抖音已实现真实接入，见 [danmaku/抖音接入说明.md](danmaku/抖音接入说明.md)）
- **AI 回复建议**：三级省 token 阶梯，高频问题秒回、复杂问题才上云
- **实时交互**：手动发送弹幕、⚡立即处理、弹幕源暂停/继续、聚合窗口在线调节、一键采纳上屏
- **提词器**：台本编辑 + 字号调节 + 自动滚动（可调速）+ 话题生成入口
- **话题生成**：基于近期弹幕 + 知识库生成聊天话题
- **知识库管理**：增删条目 + 文档/PDF 导入 + 关键词 / 语义检索 + 双击复制
- **驾驶舱视图**：统计卡（弹幕数 / 回复数 / 模板命中率 / 云端花费）+ 状态灯（弹幕源 / Ollama / 云端）+ 运行日志（三级阶梯实时走向）

## 实时交互说明

| 操作 | 位置 | 作用 |
| --- | --- | --- |
| 手动发送弹幕 | 弹幕流底部输入框，回车 | 模拟观众发言，直接进入与真实弹幕相同的 AI 处理管线（青色高亮区分） |
| ⚡ 立即处理 | 回复建议面板 | 不等聚合窗口攒满，立即处理已有弹幕出建议 |
| 聚合窗口调节 | 回复建议面板「攒 N 条 / M 秒」 | 运行时改聚合阈值，改完即生效 |
| 暂停 / 继续弹幕 | 头部按钮 | 暂停模拟弹幕源；手动发送不受影响 |
| ✅ 采纳上屏 | 回复建议面板 | 建议复制到剪贴板 + 以「📤 主播」消息显示在弹幕流，形成回复闭环 |
| 历史建议回看 | 回复建议面板下方列表 | 按来源着色，点击任意一条回看详情 |
| 自动滚动提词器 | 提词器「▶ 滚动」+ 速度滑杆 | 口播词自动滚动，滚到底自动停 |
| 状态灯 | 头部 | 弹幕源 / Ollama（每 15 秒自动探测）/ 云端配置，实时反映可用性 |

弹幕流做了智能滚动：上翻查看历史时不被打断，回到底部后恢复自动跟随。

## 快速开始

```bash
# 环境：Python 3.10（命令 py -3.10）
py -3.10 main.py
```

**无 key / 无 Ollama 也能跑通**：模拟弹幕持续刷出，高频弹幕（问价格、
求关注等）命中模板直接回复。无需安装任何第三方包。

## 三级省 token 阶梯

```
弹幕 → L1 模板命中（0 token / 0 元）
      └─ 未命中 → L2 本地 Ollama（0 元）
                  └─ 不可用 → L3 云端 DeepSeek（预算内，最少调用）
```

| 层级 | 引擎 | 成本 | 说明 |
| --- | --- | --- | --- |
| L1 | 本地模板 | 0 元 | 高频问题直接秒回 |
| L2 | Ollama + Qwen3-4B | 0 元 | 本地跑，不花钱 |
| L3 | DeepSeek deepseek-chat | 按量计费 | 批量生成，受预算器限制 |

配套手段：聚合窗口（5 条 / 20 秒）、`BudgetGuard` 预算器（上限 50 次 / 2 元，超限自动降级）、精简 prompt、吃 DeepSeek 前缀缓存。

## 可选增强

### 本地回复（L2）

装 [Ollama](https://ollama.com)，拉取模型并启动：

```bash
ollama pull qwen3:4b
```

`ai.local.enabled` 默认已开，启动后自动启用。

### 云端回复（L3）

设 config.json 里 `ai.cloud.enabled` 为 `true`，并设置 DeepSeek API key（推荐用环境变量，避免明文写进配置文件）：

```bash
# PowerShell
$env:DEEPSEEK_API_KEY="sk-xxxx"
# CMD
set DEEPSEEK_API_KEY=sk-xxxx
```

也可以直接填 config.json 的 `ai.cloud.api_key`（**环境变量优先**）。

### 语义检索知识库（ChromaKB）

默认用零依赖的 SimpleKB（关键词匹配）。想用语义检索：

```bash
py -3.10 -m pip install chromadb
ollama pull bge-m3          # 向量模型
```

config.json 里 `kb.backend` 改为 `chroma`。之后知识库按语义相似度检索，话题生成也会用它找素材。

### 文档 / PDF 导入

知识库面板点「添加文件」即可导入：

- `.txt` / `.md`：零依赖，直接读取
- `.pdf`：需先安装 `py -3.10 -m pip install pypdf`

导入后自动按 500 字符分块存入知识库，列表标注来源文件名。

### 抖音真实弹幕

默认用模拟数据（`danmaku.provider = "mock"`）。切到抖音：

```json
"danmaku": { "provider": "douyin", "live_url": "https://live.douyin.com/你的直播间id" }
```

`live_url` 填一个**正在直播**的房间链接（或直接填 `room_id`）。切换前先安装依赖：

```bash
py -3.10 -m pip install -r requirements-douyin.txt
```

签名与协议解析移植自开源项目 [DouyinLiveWebFetcher](https://github.com/saermart/DouyinLiveWebFetcher)（AGPL-3.0，仅供学习交流），详见 [danmaku/douyin_protocol/NOTICE.md](danmaku/douyin_protocol/NOTICE.md)。
抖音协议与签名频繁变更，可能随时失效，失效时需对照上游仓库更新 `sign.js`、WebSocket 模板与协议定义（见 [danmaku/抖音接入说明.md](danmaku/抖音接入说明.md)）。

## 配置说明（config.json）

```json
{
  "danmaku":  { "provider": "mock", "mock_interval": 2.0, "live_url": "", "room_id": "" },
  "aggregate": { "count": 5, "seconds": 20 },
  "ai": {
    "local":  { "enabled": true,  "base_url": "http://localhost:11434", "model": "qwen3:4b" },
    "cloud":  { "enabled": true, "api_key": "", "base_url": "https://api.deepseek.com", "model": "deepseek-chat" }
  },
  "budget": { "max_calls": 50, "max_cost": 2.0 },
  "kb": {
    "backend": "simple",
    "collection": "live_kb",
    "persist_dir": "./chroma_data",
    "embedding": "ollama",
    "embedding_url": "http://localhost:11434",
    "embedding_model": "bge-m3"
  }
}
```

| 段 | 关键字段 | 说明 |
| --- | --- | --- |
| `danmaku` | `provider` | `mock`（默认）或 `douyin`（真实接入，需装 `requirements-douyin.txt`）；`live_url` 填抖音直播间链接 |
| `aggregate` | `count` / `seconds` | 聚合窗口：攒满条数或到时间就处理一批 |
| `ai.local` | `enabled` / `model` | 本地 Ollama，0 元 |
| `ai.cloud` | `enabled` / `api_key` | 云端 DeepSeek，填 key 后启用 |
| `budget` | `max_calls` / `max_cost` | 单场云端调用上限，超限降级 |
| `kb` | `backend` | `simple`（零依赖）或 `chroma`（语义检索） |

## 目录结构

```
直播软件/
├── main.py                     # 入口：装配各模块并启动 UI
├── config.json                 # 配置文件
├── requirements.txt            # 依赖（核心零依赖，chromadb / pypdf 可选）
├── requirements-douyin.txt     # 抖音真实弹幕可选依赖（requests / websocket-client / py-mini-racer / betterproto）
├── core/                       # 协调层：事件总线、预算器、协调器
├── danmaku/                    # 弹幕源：抽象 + 模拟 + 抖音真实接入
│   └── douyin_protocol/        # 抖音签名与协议（移植自 DouyinLiveWebFetcher，AGPL-3.0）
├── ai/                         # AI 引擎：prompt + 本地 Ollama + 云端 DeepSeek
├── kb/                         # 知识库：SimpleKB + ChromaKB 语义检索 + 文档加载器
├── rules/                      # 规则：L1 模板、敏感词
└── ui/                         # 界面：主题 + 主窗口 + 各面板
```

详细设计见 [方案.md](方案.md)。

## 免责声明

本项目仅供学习、技术研究交流使用。抖音弹幕协议为逆向所得，随时可能变更，
请勿用于商业用途或大规模采集；接入真实弹幕时请遵守平台规则与相关法律法规。

抖音接入部分（`danmaku/douyin_protocol/`）移植自 [DouyinLiveWebFetcher](https://github.com/saermart/DouyinLiveWebFetcher)（AGPL-3.0），
整体项目因此受 AGPL-3.0 约束，禁止闭源分发或商业使用。
