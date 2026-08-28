# 为 itasca-mcp 做贡献

[English](CONTRIBUTING.md) | 简体中文

感谢你愿意花时间。Issue、语料修正、代码 PR 都欢迎——这份文档的目的是让你不必先把项目的约定逆向出来。

## 改动该提到哪个仓库

本项目横跨两个独立发布的运行时：

| 改动内容 | 仓库 |
| --- | --- |
| MCP 服务端、工具、文档语料 | 本仓库（`itasca-mcp`，Python >= 3.10） |
| 运行在 Itasca GUI 内的 bridge | [`itasca-mcp-bridge`](https://github.com/yusong652/itasca-mcp-bridge) |

bridge 以 git submodule 的形式挂在这里，方便你在一份 checkout 里同时改两边；
但 bridge 的改动必须提到 bridge 仓库的 PR——在本仓库更新 submodule 指针不会发布任何东西。

## 从哪里入手最合适

**文档语料**是最独立的切入点，也是领域经验比代码熟悉度更重要的地方。
如果你在用 PFC、FLAC、3DEC、MPoint 或 MassFlow，发现 agent 被喂了一条在你的版本里
根本不存在的命令——那就是一处语料缺陷，而你比任何照着厂商手册抄的人都更有资格修它。

## 文档语料

### 目录结构

```text
src/itasca_mcp/knowledge/resources/
├── _common/{command_docs,python_sdk_docs}/     # Itasca 9.0 统一内核共享文档
└── <software>/                                 # pfc | flac | 3dec | mpoint | massflow
    ├── command_docs/index.json + commands/<category>/<name>.json
    ├── python_sdk_docs/index.json + modules/<module>/
    └── references/index.json + <family>/       # contact-models、plot-items 等
```

凡是 9.0 内核在各引擎间共享的内容放进 `_common/`；引擎特有的行为放到该引擎目录下。
**如果一条命令在多个引擎里都存在但行为不同，保持各引擎独立，不要归并到共享层。**

### 一条命令的形状

一条命令就是一个 JSON 文件，按版本分键。例如
`pfc/command_docs/commands/ball/delete.json`：

```json
{
  "category": "ball",
  "search_keywords": ["delete", "remove"],
  "description": "Delete balls. If no range is specified, then all balls in the model are deleted.",
  "python_sdk_alternative": {
    "available": true,
    "workaround": "Ball.delete() method - requires iteration: for b in itasca.ball.list(): b.delete()"
  },
  "versions": {
    "7.0": {
      "command": "ball delete",
      "syntax": "ball delete [range]",
      "keywords": [],
      "examples": [
        { "command": "ball delete range group 'tunnel'", "description": "Delete all balls in group 'tunnel'" }
      ]
    }
  }
}
```

然后在该引擎的 `command_docs/index.json` 里，把它登记到
`categories.<category>.commands[]` 下。注意 `file` 指针是**相对 `resources/` 根目录**，
不是相对 index 文件：

```json
{ "name": "delete",
  "file": "pfc/command_docs/commands/ball/delete.json",
  "short_description": "Delete balls",
  "syntax": "ball delete [range]" }
```

### 语料的验证标准

每一个版本键都应当是**对着活引擎验证过的**，而不是从手册抄下来、再默认它跨版本成立。
本仓库的大部分语料是靠 dump 真实引擎、再和文档对账写出来的。

你不需要覆盖所有版本。如果你只验证了 `7.0`、没条件验 `6.0`，就只提交 `7.0` 这一个键，
并在 PR 里说明——**少一个版本没关系，猜一个版本才是让 agent 在跑了六小时之后翻车的原因。**
请写清楚你是在哪个引擎、哪个 build 上验证的：这部分是审阅者无法复现的信息。

已合并的语料 PR 范例：[#9](https://github.com/yusong652/itasca-mcp/pull/9)
（新增 `python_sdk_docs` 模块及其 index 条目和测试）、
[#12](https://github.com/yusong652/itasca-mcp/pull/12)（语料拆分，同时改了 loader 和类型层）。

## 代码改动

动工具接口之前请先读仓库根目录的 `CLAUDE.md`——审阅是按那里的架构约定来的，
尤其是统一的 `{ok, data, error}` 信封、MCP 侧与 bridge 侧的职责分离，
以及两种执行模型（同步 REPL 与异步 task）。

新行为要带测试。`tests/` 刻意基于 mock bridge：整个测试套件必须在没有 Itasca 安装、
没有 license 的机器上跑通。

## 开发环境

见[开发者指南](docs/development/source-install.zh-CN.md)
（[English](docs/development/source-install.md)）：从源码安装、submodule 工作流，
以及如何把 MCP 客户端指向本地 checkout。

## 提 PR 之前

CI 在每次 push 和 PR 上跑的就是下面四条命令，本地跑一遍就不会有意外：

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/itasca_mcp/
uv run pytest tests/ --cov=itasca_mcp --cov-report=term-missing
```

Commit message 使用常规前缀（`feat:`、`fix:`、`refactor:`、`test:`、`docs:`），
正文说明**为什么**需要这个改动——改了什么 diff 自己会说。
**commit message 一律用英文**，即使 issue 或讨论是中文的。

**你不需要改 `CHANGELOG.md`。** 维护者会在发版时从 commit 历史整理
`## [Unreleased]` 小节。一条清楚的 commit message 就是全部约定。

## 报告问题

Bug 提 [issue](https://github.com/yusong652/itasca-mcp/issues)，
安装和用法问题走 [discussions](https://github.com/yusong652/itasca-mcp/discussions)。
中文提问完全可以。

请附上：

- 引擎与版本（在 Itasca 的 Python 控制台里，`sys.executable` 同时编码了产品和版本）
- `itasca-mcp` 与 `itasca-mcp-bridge` 的版本
- 你用的是哪个 MCP 客户端
- agent 试图做什么、引擎实际做了什么

**即使没有附带修复，版本相关的发现同样有价值**——"这条命令在 PFC 6.00 里不存在"
本身就是一份语料缺陷报告，而且只有用那个版本的人才提得出来。

## 许可证

提交贡献即表示你同意这些贡献以本项目的 [MIT 许可证](LICENSE)发布。
