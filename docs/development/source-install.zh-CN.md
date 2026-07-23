# 开发者指南：从源码安装与运行

这份指南面向需要直接使用本地源码进行开发、在发布到 PyPI 之前验证修改，或将 bridge 从本地源码安装到 PFC 内嵌 Python 环境中的贡献者。

## 运行时拆分

这个仓库实际上包含两个独立运行时：

- `itasca-mcp`
  位于 [`src/itasca_mcp`](../../src/itasca_mcp) 的 MCP 服务端包，运行在标准 Python `>=3.10`
- `itasca-mcp-bridge`
  位于 [`itasca-mcp-bridge`](../../itasca-mcp-bridge) 的 bridge 包，运行在 PFC 内嵌 Python 中。这个目录是一个 **git submodule**，指向独立仓库 [`yusong652/itasca-mcp-bridge`](https://github.com/yusong652/itasca-mcp-bridge)，有自己的发布周期。`itasca-mcp` 只记录使用哪一个 bridge commit，不保存 bridge 源码本身。

虽然它们在同一个工作树里，但安装和验证时应当视为两个独立目标。

## 1. 克隆仓库并安装开发依赖

带上 bridge submodule 一起克隆（第 3–7 步会用到）：

```bash
git clone --recurse-submodules https://github.com/yusong652/itasca-mcp.git
```

如果之前已经不带 `--recurse-submodules` 克隆过了，`itasca-mcp-bridge/` 会是空的，需要初始化：

```bash
git submodule update --init --recursive
```

然后在仓库根目录执行：

```bash
uv sync --group dev
```

运行测试：

```bash
uv run pytest tests
```

### 关于 bridge submodule 的日常操作

`itasca-mcp-bridge/` 是一个固定 commit 的指针（gitlink，mode `160000`），指向独立仓库 [`yusong652/itasca-mcp-bridge`](https://github.com/yusong652/itasca-mcp-bridge) 的某一个 SHA——`itasca-mcp` 跟踪的是这一个 SHA，不是 bridge 的源文件。实际工作中要注意：

- **拉了 `itasca-mcp` 之后**，submodule 工作树不会自动跟着移动，需要重新同步：

  ```bash
  git submodule update --init --recursive
  ```

- **要升级 bridge 版本**，先在 `itasca-mcp-bridge/` 里 checkout 目标 commit，然后在 `itasca-mcp` 里把这个指针 stage 出来：

  ```bash
  git add itasca-mcp-bridge && git commit -m "chore: bump itasca-mcp-bridge pin"
  ```

- **push 顺序很重要**：先 push bridge 仓库——pin 指向的 commit 必须先在公开 bridge repo 上存在，否则别人 clone 你的 `itasca-mcp` 时拉不到。
- `git status` 看到 `modified: itasca-mcp-bridge (untracked content)` 通常只是 submodule 工作树里多了些本地或未跟踪文件，并不代表 `itasca-mcp` 在跟踪 bridge 源码。除非你**确实要**升级 pin，否则不要 commit 这条 gitlink 变动。

## 2. 让 MCP 客户端指向本地源码

如果你希望 MCP 客户端使用本地 checkout 而不是 PyPI 发布版，可以用 `uv run --directory` 指向仓库：

```json
{
  "mcpServers": {
    "itasca-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/itasca-mcp", "itasca-mcp", "--bridge-url", "http://localhost:9001"]
    }
  }
}
```

`--bridge-url` 参数是可选的（默认 `http://localhost:9001`）。若 bridge 跑在非默认端口上，
直接用 `--bridge-port` 即可，无需写出整条 URL——例如 bridge 以
`itasca_mcp_bridge.start(port=9002)` 启动时，配置写
`"args": [..., "itasca-mcp", "--bridge-port", "9002"]`。

这是验证 MCP 侧改动最简单的方式，不需要先构建或发布包。

## 3. 直接从源码启动 Bridge

如果你只是想让 bridge 侧代码修改在 PFC 中生效，其实不需要先安装 bridge 包。在 PFC 的 IPython 控制台里执行：

```python
%run C:/path/to/itasca-mcp/itasca-mcp-bridge/start_bridge.py
```

注意：

- 路径请使用正斜杠
- `%run` 后面的路径不要加引号
- 修改 bridge 源码后需要重启 bridge

这是 bridge 开发时最快的工作流。

## 4. 将 Bridge 从本地源码安装到内嵌 Python

如果你要验证"包安装路径"本身，而不只是直接 `%run`，建议从终端调用 PFC 的内嵌 Python 解释器，把 `itasca-mcp-bridge` 从本地源码安装进去。

先根据 PFC 版本选择正确解释器：

- PFC `6.0` / `7.0`：`C:/Program Files/Itasca/.../exe64/python36/python.exe`
- PFC `9.0`：`C:/Program Files/Itasca/.../exe64/python310/python.exe`

示例命令：

```powershell
& "C:\Program Files\Itasca\PFC700\exe64\python36\python.exe" -m pip install --user -e C:\path\to\itasca-mcp\itasca-mcp-bridge
& "C:\Program Files\Itasca\ItascaSoftware900\exe64\python310\python.exe" -m pip install --user -e C:\path\to\itasca-mcp\itasca-mcp-bridge
```

为什么推荐在终端里直接调用内嵌解释器：

- 安装目标就是 PFC 实际使用的那个 Python 环境
- 不依赖在 PFC 控制台里通过 `subprocess` 再起一个解释器
- 对 editable install 来说最稳定

bridge 只依赖标准库（基于 `http.server` 的 HTTP + SSE），没有任何运行时第三方依赖。

## 5. 在 PFC IPython 中安装

如果你是在 PFC 控制台里直接安装 PyPI 版本，请使用仓库根目录的 `addon.py`——它会自动按 PFC 版本选择 `pip.main(...)`（PFC 6/7）或 `pip._internal.cli.main.main(...)`（PFC 9），并启动 bridge。

如果是"从源码安装"，更推荐使用上面第 4 步那种"终端 + 内嵌解释器"的方式，而不是在 PFC GUI 控制台里尝试驱动 editable install。

## 6. 验证环境

可以先在内嵌 Python 里检查 bridge 包：

```powershell
& "C:\Program Files\Itasca\ItascaSoftware900\exe64\python310\python.exe" -c "import itasca_mcp_bridge; print(itasca_mcp_bridge.__version__)"
```

然后在 PFC 中启动 bridge，并从 MCP 客户端验证：

1. 在 PFC 中执行 `itasca_mcp_bridge.start()` 或 `%run .../start_bridge.py`
2. 重启 MCP 客户端会话
3. 调用 `itasca_list_tasks`

## 7. 推荐开发循环

对于大多数日常开发，推荐这样做：

1. 执行 `uv sync --group dev`
2. 用 `uv run --directory` 让 MCP 客户端指向本地源码
3. 在 PFC 中用 `%run .../itasca-mcp-bridge/start_bridge.py` 启动 bridge
4. 执行 `uv run pytest tests`
5. 修改后按需重启 MCP 客户端和 bridge
