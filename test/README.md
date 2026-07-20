# 本地控制台 Agent

这是一个只在控制台运行的本地 Agent，保留了以下能力：

- 使用本地 Ollama 对话模型
- 多轮会话记忆
- 本地 RAG 知识库
- 安全计算器工具
- MCP 配置与扩展入口

## 准备环境

安装并启动 Ollama，然后下载配置文件中使用的模型：

```powershell
ollama pull qwen3:8b
ollama pull nomic-embed-text
pip install -r requirements.txt
```

模型名、Ollama 地址、RAG 参数和 MCP 参数都在 `config.toml` 中修改。

## 运行

```powershell
python main.py
```

控制台命令：

- `/add <文件路径>`：把 UTF-8 文本文件加入 RAG 知识库
- `/status`：查看 RAG 和 MCP 状态
- `/help`：查看帮助
- `/quit`：退出

知识库记录保存在 `data/documents.json`。程序启动时会调用 Ollama 的嵌入模型重建内存向量索引。

## MCP 说明

MCP 默认关闭。启用 Streamable HTTP 服务：

```toml
[mcp]
enabled = true
server_name = "local-mcp"
transport = "streamable_http"
server_url = "http://localhost:8000/mcp"
command = ""
args = []
```

也可以把 `transport` 改为 `stdio`，并填写 `command` 和 `args`。启动时加载到的 MCP 工具会和 RAG、计算器工具一起直接交给 Agent 使用。
