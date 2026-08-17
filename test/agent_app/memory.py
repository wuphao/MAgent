from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from agent_app.settings import MemoryConfig


TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
CHINESE_PATTERN = re.compile(r"[\u4e00-\u9fff]+")


@dataclass(frozen=True)
class Memory:
    id: str
    kind: str
    content: str
    created_at: str
    updated_at: str
    status: str = "active"
    usage_count: int = 0


class MemoryStore:
    def __init__(self, config: MemoryConfig) -> None:
        self._config = config
        self._path = config.path

    def add(self, content: str, kind: str = "fact") -> Memory:
        cleaned = content.strip()
        if not cleaned:
            raise ValueError("Memory content is empty.")

        memories = self._load()
        duplicate = self._find_duplicate(memories, cleaned)
        now = _utc_now()
        if duplicate is not None:
            updated = Memory(
                id=duplicate.id,
                kind=kind or duplicate.kind,
                content=cleaned,
                created_at=duplicate.created_at,
                updated_at=now,
                status="active",
                usage_count=duplicate.usage_count,
            )
            self._save([updated if item.id == duplicate.id else item for item in memories])
            return updated

        memory = Memory(
            id=f"mem_{uuid.uuid4().hex[:12]}",
            kind=kind,
            content=cleaned,
            created_at=now,
            updated_at=now,
        )
        memories.append(memory)
        self._save(memories)
        return memory

    def list(self, include_inactive: bool = False) -> list[Memory]:
        memories = self._load()
        if include_inactive:
            return memories
        return [memory for memory in memories if memory.status == "active"]

    def forget(self, memory_id: str) -> bool:
        memories = self._load()
        found = False
        now = _utc_now()
        updated_memories: list[Memory] = []
        for memory in memories:
            if memory.id == memory_id and memory.status == "active":
                found = True
                updated_memories.append(
                    Memory(
                        id=memory.id,
                        kind=memory.kind,
                        content=memory.content,
                        created_at=memory.created_at,
                        updated_at=now,
                        status="deleted",
                        usage_count=memory.usage_count,
                    )
                )
            else:
                updated_memories.append(memory)
        if found:
            self._save(updated_memories)
        return found

    def search(self, query: str) -> list[Memory]:
        query_tokens = set(_tokens(query))
        if not query_tokens:
            return []

        scored: list[tuple[float, Memory]] = []
        for memory in self.list():
            memory_tokens = set(_tokens(memory.content))
            if not memory_tokens:
                continue
            overlap = len(query_tokens & memory_tokens)
            if overlap == 0:
                continue
            scored.append((overlap / len(query_tokens | memory_tokens), memory))

        scored.sort(key=lambda item: item[0], reverse=True)
        selected = [memory for _, memory in scored[: self._config.top_k]]
        if selected:
            self._mark_used([memory.id for memory in selected])
        return selected

    def status(self) -> dict[str, object]:
        memories = self._load()
        active = [memory for memory in memories if memory.status == "active"]
        return {
            "enabled": self._config.enabled,
            "active": len(active),
            "total": len(memories),
            "path": str(self._path),
        }

    def _load(self) -> list[Memory]:
        if not self._path.exists():
            return []
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        return [Memory(**item) for item in raw]

    def _save(self, memories: list[Memory]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        records = [asdict(memory) for memory in memories]
        self._path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _find_duplicate(self, memories: list[Memory], content: str) -> Memory | None:
        normalized = _normalize(content)
        for memory in memories:
            if memory.status == "active" and _normalize(memory.content) == normalized:
                return memory
        return None

    def _mark_used(self, memory_ids: list[str]) -> None:
        memory_id_set = set(memory_ids)
        memories = [
            Memory(
                id=memory.id,
                kind=memory.kind,
                content=memory.content,
                created_at=memory.created_at,
                updated_at=memory.updated_at,
                status=memory.status,
                usage_count=memory.usage_count + 1,
            )
            if memory.id in memory_id_set
            else memory
            for memory in self._load()
        ]
        self._save(memories)


def _tokens(text: str) -> list[str]:
    normalized = text.lower()
    tokens = TOKEN_PATTERN.findall(normalized)
    for chinese_text in CHINESE_PATTERN.findall(normalized):
        tokens.extend(
            chinese_text[index : index + 2] for index in range(len(chinese_text) - 1)
        )
    return tokens


def _normalize(text: str) -> str:
    return " ".join(_tokens(text))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
