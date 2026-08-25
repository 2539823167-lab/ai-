# 来源说明

本目录内的文件移植自开源项目 **DouyinLiveWebFetcher**：

- 仓库：https://github.com/saermart/DouyinLiveWebFetcher
- 原始作者：bubu（见各文件头注释）

## 文件对应关系

| 本目录文件 | 上游文件 | 用途 |
| --- | --- | --- |
| `sign.js` | `sign.js` | X-Bogus 签名算法（MiniRacer/V8 执行） |
| `protobuf/douyin.py` | `protobuf/douyin.py` | betterproto 生成的抖音弹幕协议类 |
| `protobuf/douyin.proto` | `protobuf/douyin.proto` | 协议源文件（再生成用） |
| `LICENSE` | `LICENSE` | AGPL-3.0 全文 |

## 协议声明

上游项目以 **GNU Affero General Public License v3.0（AGPL-3.0）** 发布。
移植这些文件意味着本项目整体受 AGPL-3.0 约束：**仅限个人学习、技术研究交流使用，
请勿用于商业用途或闭源分发**。

签名算法为抖音网页端逆向所得，抖音协议与签名随时可能变更，
失效时请对照上游仓库更新 `sign.js`、WebSocket 模板与 `.proto` 定义。
