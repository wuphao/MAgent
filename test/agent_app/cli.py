from __future__ import annotations

from agent_app.service import ChatService
from agent_app.settings import load_config


HELP_TEXT = """Commands:
  /add <file>      Add a UTF-8 text file to the local RAG store
  /search <query>  Search the local RAG store without calling the chat model
  /remember <text> Save a long-term memory
  /memories        List active long-term memories
  /forget <id>     Delete a long-term memory
  /status          Show RAG and memory status
  /eval <jsonl>    Evaluate retrieval Recall@K, MRR, and keyword recall
  /help            Show this help
  /quit            Exit
"""


def run_console() -> None:
    config = load_config()
    if not config.deepseek.api_key:
        print("DeepSeek API key is empty. Fill config.toml or set DEEPSEEK_API_KEY.")
        return

    service = ChatService(config)

    print(f"DeepSeek chat started: {config.deepseek.chat_model}")
    print("Type /help for commands. Press Ctrl+C or Ctrl+Z then Enter to exit.")

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return

        if not user_input:
            continue

        if user_input.startswith("/"):
            if _handle_command(service, user_input):
                return
            continue

        try:
            answer = service.chat(user_input)
        except Exception as error:
            print(f"Error: {error}")
            continue

        print(f"Assistant: {answer}")


def _handle_command(service: ChatService, command_line: str) -> bool:
    command, _, argument = command_line.partition(" ")
    argument = argument.strip()

    if command in {"/quit", "/exit"}:
        print("Bye.")
        return True
    if command == "/help":
        print(HELP_TEXT)
    elif command == "/status":
        print(f"RAG: {service.rag_status()}")
        print(f"Memory: {service.memory_status()}")
    elif command == "/add":
        if not argument:
            print("Usage: /add <file>")
        else:
            try:
                chunks = service.add_document(argument)
                print(f"Added {chunks} chunks to RAG.")
            except Exception as error:
                print(f"Add failed: {error}")
    elif command == "/search":
        if not argument:
            print("Usage: /search <query>")
        else:
            results = service.search(argument)
            if not results:
                print("No results.")
            for index, result in enumerate(results, start=1):
                metadata = result["metadata"]
                print(
                    f"\n[{index}] source={metadata.get('source', 'unknown')} "
                    f"page={metadata.get('page') or '-'} "
                    f"section={metadata.get('section') or '-'} "
                    f"score={result.get('score', 0)}"
                )
                print(str(result["content"])[:500])
    elif command == "/eval":
        if not argument:
            print("Usage: /eval <jsonl>")
        else:
            try:
                summary = service.evaluate(argument)
                print(
                    f"questions={summary.questions} "
                    f"recall@k={summary.recall_at_k:.3f} "
                    f"mrr={summary.mean_reciprocal_rank:.3f} "
                    f"keyword_recall={summary.keyword_recall:.3f}"
                )
            except Exception as error:
                print(f"Evaluation failed: {error}")
    elif command == "/remember":
        if not argument:
            print("Usage: /remember <text>")
        else:
            try:
                memory = service.remember(argument)
                print(f"Remembered {memory.id}.")
            except Exception as error:
                print(f"Remember failed: {error}")
    elif command == "/memories":
        memories = service.memories()
        if not memories:
            print("No active memories.")
        for memory in memories:
            print(f"{memory.id} [{memory.kind}] {memory.content}")
    elif command == "/forget":
        if not argument:
            print("Usage: /forget <id>")
        elif service.forget(argument):
            print(f"Forgot {argument}.")
        else:
            print(f"Memory not found: {argument}")
    else:
        print(f"Unknown command: {command}. Type /help for commands.")
    return False
