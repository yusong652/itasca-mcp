<p align="center">
  <img src="https://raw.githubusercontent.com/yusong652/itasca-mcp/assets/header.webp" alt="itasca-mcp" width="70%">
</p>

# itasca-mcp

[English](https://github.com/yusong652/itasca-mcp/blob/main/README.md) | [简体中文](https://github.com/yusong652/itasca-mcp/blob/main/README.zh-CN.md)

[![PyPI](https://img.shields.io/pypi/v/itasca-mcp)](https://pypi.org/project/itasca-mcp/)
[![Downloads](https://static.pepy.tech/badge/itasca-mcp)](https://pepy.tech/project/itasca-mcp)
[![GitHub stars](https://img.shields.io/github/stars/yusong652/itasca-mcp)](https://github.com/yusong652/itasca-mcp/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)

`itasca>model new ;now, with LLM.`

**itasca-mcp** 通过 [Model Context Protocol](https://modelcontextprotocol.io/) 将 AI 智能体连接到 [ITASCA](https://www.itascacg.com/) 的数值模拟软件 —— PFC、FLAC、3DEC、MPoint、MassFlow。通过自然语言对话即可浏览文档、运行仿真和执行代码。

`itasca>model solve ;LLM solves.`

![itasca-mcp demo](https://raw.githubusercontent.com/yusong652/itasca-mcp/assets/itasca-mcp.gif)

## 工具（10）

**5 个文档工具** — 浏览和搜索所选引擎的命令、Python API 及参考文档。无需 bridge。

**5 个执行工具** — 交互式 REPL、任务提交、进度监控、中断和历史浏览。需要 bridge。

## 首次启动配置

### 前置条件

- 已安装一个 **ITASCA 引擎** —— PFC、FLAC、3DEC、MPoint 或 MassFlow。推荐 9.0 及以上版本；也支持 PFC 6.0 / 7.0 与 FLAC 7.0。
- 已安装 **[uv](https://docs.astral.sh/uv/getting-started/installation/)**（用于 `uvx`）
- 一个 **AI 智能体** —— Claude Code、Codex CLI、Gemini CLI 或其他任意 MCP 客户端

### 智能体自动配置（推荐）

将以下文本复制给你的 AI 智能体，让它自动完成配置：

```text
请全程用中文与我交流。然后获取并完整按照这份引导指南执行（指南为英文，照其步骤操作即可）：
https://raw.githubusercontent.com/yusong652/itasca-mcp/main/docs/agentic/itasca-mcp-bootstrap.md
```

### 手动配置

**1. 向你的智能体注册 MCP 服务。**

大多数智能体一条命令即可添加：

```bash
# Claude Code
claude mcp add itasca-mcp -- uvx itasca-mcp

# Codex / Codex-cli
codex mcp add itasca-mcp -- uvx itasca-mcp

# Gemini CLI
gemini mcp add itasca-mcp uvx itasca-mcp
```

或者手动填写MCP配置文件：

```json
{
  "mcpServers": {
    "itasca-mcp": {
      "command": "uvx",
      "args": ["itasca-mcp"]
    }
  }
}
```

**2. 在 ITASCA 引擎中启动 bridge：**

下载 [`addon.py`](addon.py)，然后在引擎 GUI（PFC、FLAC、3DEC……）中任选一种方式执行：

- 把这个文件的内容复制到引擎的 IPython 控制台里运行
- 或者先把这个文件下载到本地，再在引擎 GUI 里执行它

<img src="https://raw.githubusercontent.com/yusong652/itasca-mcp/assets/addon.gif" alt="addon.py 演示" width="60%">

### 验证

重启你的 AI 智能体，让它调用 `itasca_execute_code` 来验证连接是否正常。

## 日常启动

完成首次配置之后，每次启动引擎只需要在 IPython 控制台里运行下面两行，bridge 起来后就可以继续用了：

```python
import itasca_mcp_bridge
itasca_mcp_bridge.start()
```

`start()` 会先检查 PyPI 上是否有新版 bridge，有则自动升级再启动。MCP 客户端配置会一直保留。

## 功能亮点

- **多引擎语料** — 覆盖 PFC、FLAC、3DEC、MPoint、MassFlow 的命令、Python API 与参考文档，通过必填的 `software` 参数选择
- **多版本支持** — 通过 `version` 参数查阅各引擎不同版本（PFC：6.0/7.0/9.0，FLAC：7.0/9.0）的命令文档
- **层级式文档浏览** — 智能体沿着引擎命令树自主发现能力与边界，减少幻觉命令
- **增强的 plot 文档** — 在官方文档基础上补充了 plot items 参考文档
- **任务运行时 REPL 依然可用** — 仿真运行中也能执行代码，随时查看模型状态和中间结果，无需停止任务；也适合在写完整脚本前快速迭代
- **任务全生命周期管理** — 提交长时仿真、监控进度、中止运行中的任务、浏览历史任务
- **多客户端兼容** — 支持 Claude Code、Codex CLI、Gemini CLI、GitHub Copilot CLI、OpenCode、toyoura-nagisa 等 MCP 客户端

## 故障排查

详见 bootstrap 指南中的[故障排查章节](docs/agentic/itasca-mcp-bootstrap.md#troubleshooting)。

## 开发

详见 [开发者指南：从源码安装与运行](docs/development/source-install.zh-CN.md)。

<a href="https://glama.ai/mcp/servers/yusong652/itasca-mcp">
  <img width="200" height="105" src="https://glama.ai/mcp/servers/yusong652/itasca-mcp/badge" alt="itasca-mcp MCP server" />
</a>

## 贡献

欢迎提交 PR 和 Issue！参见[开发者指南](docs/development/source-install.zh-CN.md)了解如何开始。

## 许可证

MIT，详见 [LICENSE](LICENSE)。
