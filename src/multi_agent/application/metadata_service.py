from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from multi_agent.mapping.candidate import MetadataQuestion


@dataclass(frozen=True)
class MetadataRevision:
    revision_id: str
    question_id: str
    answer: str
    source: str
    idempotency_key: str


class MetadataService:
    def __init__(self, store_path: Path):
        self.store_path = store_path
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

    def list_questions(self, questions_path: Path) -> list[MetadataQuestion]:
        payload = json.loads(questions_path.read_text(encoding="utf-8"))
        return [MetadataQuestion.model_validate(item) for item in payload.get("questions", [])]

    def submit(
        self,
        question_id: str,
        answer: str,
        source: str,
        idempotency_key: str,
    ) -> MetadataRevision:
        data = self._read()
        if idempotency_key in data:
            return MetadataRevision(**data[idempotency_key])
        revision = MetadataRevision(
            revision_id=_stable_id("metadata", question_id, answer, source),
            question_id=question_id,
            answer=answer,
            source=source,
            idempotency_key=idempotency_key,
        )
        data[idempotency_key] = asdict(revision)
        self.store_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return revision

    def _read(self) -> dict:
        if not self.store_path.exists():
            return {}
        return json.loads(self.store_path.read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage stage03 supplemental metadata revisions.")
    parser.add_argument("--store", type=Path, default=Path("evaluation/stage-03/metadata_revisions.json"))
    subparsers = parser.add_subparsers(dest="command", required=True)
    questions = subparsers.add_parser("questions")
    questions.add_argument("questions_json", type=Path)
    submit = subparsers.add_parser("submit")
    submit.add_argument("--question-id", required=True)
    submit.add_argument("--answer", required=True)
    submit.add_argument("--source", required=True)
    submit.add_argument("--idempotency-key", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = MetadataService(args.store)
    if args.command == "questions":
        result = [item.model_dump(mode="json") for item in service.list_questions(args.questions_json)]
    else:
        result = asdict(
            service.submit(
                question_id=args.question_id,
                answer=args.answer,
                source=args.source,
                idempotency_key=args.idempotency_key,
            )
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


if __name__ == "__main__":
    raise SystemExit(main())
