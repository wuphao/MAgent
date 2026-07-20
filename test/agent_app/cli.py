from __future__ import annotations

from pathlib import Path

from agent_app.service import AgentService
from agent_app.settings import load_config


HELP_TEXT = """命令：
  /add <文件路径>  添加 UTF-8 文本文件到 RAG 知识库
  /status           查看 RAG 和 MCP 状态
  /help             查看帮助
  /quit             退出
"""

EXIT_COMMANDS = {"/quit", "/exit"}


def run_console() -> None:
    """启动交互式控制台。"""
    config = load_config()
    print(f"正在连接 Ollama：{config.ollama.chat_model} ({config.ollama.base_url})")
    service = AgentService(config)
    print("本地 Agent 已启动。输入 /help 查看命令。")

    while True:
        user_input = _read_input()
        if user_input is None:
            print("再见！")
            return
        if not user_input:
            continue
        if user_input.startswith("/"):
            if _handle_command(service, user_input):
                return
            continue

        _answer_question(service, user_input)


def _read_input() -> str | None:
    try:
        return input("\n你：").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def _handle_command(service: AgentService, command_line: str) -> bool:
    """执行控制台命令；返回 True 表示应该退出程序。"""
    command, _, argument = command_line.partition(" ")

    if command in EXIT_COMMANDS:
        print("再见！")
        return True
    if command == "/help":
        print(HELP_TEXT)
    elif command == "/status":
        status = service.status()
        print("RAG：", status["rag"])
        print("MCP：", status["mcp"])
    elif command == "/add":
        _add_document(service, argument.strip())
    else:
        print(f"未知命令：{command}。输入 /help 查看帮助。")
    return False


def _add_document(service: AgentService, file_name: str) -> None:
    if not file_name:
        print("用法：/add <文件路径>")
        return

    path = Path(file_name).expanduser().resolve()
    if not path.is_file():
        print(f"文件不存在：{path}")
        return

    try:
        service.add_document(path)
        print(f"已加入知识库：{path}")
    except (OSError, UnicodeError, ValueError) as error:
        print(f"添加失败：{error}")


def _answer_question(service: AgentService, question: str) -> None:
    try:
        answer = service.chat(question)
        print(f"助手：{answer}")
    except Exception as error:
        print(f"调用失败：{error}")
