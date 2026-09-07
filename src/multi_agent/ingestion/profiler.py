from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from typing import Any

from multi_agent.domain.mapping import ParsedDocument, SourceProfile


class Profiler:
    def profile(self, document: ParsedDocument, sample_size: int = 20) -> SourceProfile:
        fields: dict[str, dict[str, Any]] = {}
        counters: dict[str, Counter[str]] = defaultdict(Counter)
        missing: Counter[str] = Counter()
        present: Counter[str] = Counter()
        for record in document.records:
            for field, value in record.data.items():
                present[field] += 1
                if value in (None, ""):
                    missing[field] += 1
                elif len(counters[field]) < sample_size:
                    counters[field][str(value)] += 1
        for field in sorted(present):
            fields[field] = {
                "present_count": present[field],
                "missing_count": missing[field],
                "sample_values": list(counters[field].keys())[:sample_size],
            }
        top_level_paths = sorted(document.root.keys()) if isinstance(document.root, dict) else []
        structure_payload = {
            "layout": document.layout,
            "fields": sorted(fields),
            "top_level_paths": top_level_paths,
        }
        semantic_payload = {
            "sample_enums": {field: fields[field]["sample_values"] for field in fields},
        }
        return SourceProfile(
            parser_version=document.parser_version,
            layout=document.layout,
            record_count=len(document.records),
            fields=fields,
            top_level_paths=top_level_paths,
            structure_fingerprint=_digest(structure_payload),
            semantic_metadata_fingerprint=_digest(semantic_payload),
            facts_from_full_scan=["record_count", "field_presence", "missing_count"],
            facts_from_sample=["sample_values"],
        )


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
