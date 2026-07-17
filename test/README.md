# Agent Demo

这是一个本地 Agent Demo，当前包含：

- `POST /api/chat`：流式问答接口，支持会话记忆
- `POST /api/upload`：上传文件并加入本地知识库
- `GET /health`：健康检查

## 启动

先确保本地 Ollama 已运行，并且可访问：

- `http://localhost:11434`

然后执行：

```bash
python main.py
```

默认监听：

- `http://0.0.0.0:8050`

## 目录结构

- `main.py`：启动入口
- `agent_app/server.py`：HTTP 接口
- `agent_app/service.py`：Agent 运行时和会话逻辑
- `agent_app/knowledge_base.py`：本地知识库、向量索引、上传入库
- `agent_app/tools.py`：工具定义
- `agent_app/text_utils.py`：文本处理、流式解析、计算器
- `agent_app/settings.py`：路径和环境变量配置
- `agent_app/prompts.py`：系统提示词和种子文档
- `agent_app/mcp_registry.py`：MCP 预留扩展位

## 问答接口

`POST /api/chat`

请求体示例：

```json
{
  "session_id": "user_001",
  "message": "刘慈欣出生年份加上《三体》出版年份，再除以 3，结果是多少？",
  "stream": true
}
```

`stream=true` 时返回 SSE 流。

## 上传接口

`POST /api/upload`

使用 `multipart/form-data`，字段名支持：

- `file`
- `files`

上传后的文件会写入本地 `data/uploads/`，并进入知识库索引。

## 记忆

记忆按 `session_id` 隔离，同一个会话可以继续追问。

## MCP

已经预留 `mcp_status` 和 `mcp_call` 工具入口。当前默认不连真实 MCP 服务，但后续可以通过环境变量扩展。
