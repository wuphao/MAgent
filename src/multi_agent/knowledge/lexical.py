from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from multi_agent.knowledge.documents import KnowledgeChunk


TOKEN_RE = re.compile(r"[A-Za-z]+(?:-[A-Za-z0-9]+)?|\d+(?:\.\d+)?|[\u4e00-\u9fff]")


@dataclass(frozen=True)
class LexicalSearchResult:
    chunk: KnowledgeChunk
    score: float
    rank: int
    matched_terms: list[str]


def tokenize(text: str) -> list[str]:
    raw = [item.group(0).lower().replace("_", "-") for item in TOKEN_RE.finditer(text)]
    tokens: list[str] = []
    cjk_run: list[str] = []
    for item in raw:
        if len(item) == 1 and "\u4e00" <= item <= "\u9fff":
            cjk_run.append(item)
            tokens.append(item)
            continue
        tokens.extend(_flush_cjk_run(cjk_run))
        cjk_run = []
        tokens.append(item)
    tokens.extend(_flush_cjk_run(cjk_run))
    return [item for item in tokens if item.strip()]


class BM25LexicalIndex:
    def __init__(self, chunks: list[KnowledgeChunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.documents = [tokenize(chunk.text + " " + " ".join(chunk.keywords)) for chunk in chunks]
        self.term_counts = [Counter(document) for document in self.documents]
        self.lengths = [len(document) for document in self.documents]
        self.average_length = sum(self.lengths) / len(self.lengths) if self.lengths else 0.0
        doc_frequency: Counter[str] = Counter()
        for document in self.documents:
            doc_frequency.update(set(document))
        self.idf = {
            term: math.log(1 + (len(self.documents) - frequency + 0.5) / (frequency + 0.5))
            for term, frequency in doc_frequency.items()
        }

    def search(self, query: str, limit: int = 30) -> list[LexicalSearchResult]:
        query_terms = tokenize(query)
        if not query_terms or not self.chunks:
            return []
        unique_query_terms = sorted(set(query_terms))
        scored: list[tuple[float, KnowledgeChunk, list[str]]] = []
        for index, chunk in enumerate(self.chunks):
            score = 0.0
            matched_terms: list[str] = []
            length = self.lengths[index] or 1
            for term in unique_query_terms:
                frequency = self.term_counts[index].get(term, 0)
                if not frequency:
                    continue
                matched_terms.append(term)
                numerator = frequency * (self.k1 + 1)
                denominator = frequency + self.k1 * (1 - self.b + self.b * length / (self.average_length or 1))
                score += self.idf.get(term, 0.0) * numerator / denominator
            if score > 0:
                scored.append((score, chunk, matched_terms))
        scored.sort(key=lambda item: (-item[0], item[1].document_id, item[1].locator))
        return [
            LexicalSearchResult(chunk=chunk, score=score, rank=rank, matched_terms=matched_terms)
            for rank, (score, chunk, matched_terms) in enumerate(scored[:limit], start=1)
        ]


def _flush_cjk_run(run: list[str]) -> list[str]:
    if not run:
        return []
    if len(run) == 1:
        return []
    joined = "".join(run)
    bigrams = [joined[index : index + 2] for index in range(len(joined) - 1)]
    trigrams = [joined[index : index + 3] for index in range(len(joined) - 2)]
    return bigrams + trigrams
