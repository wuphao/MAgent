# RAG Exact Retrieval Baseline

Generated from `evaluation/rag/run_a0_baseline.py` using the current `ExactRetriever`.

## Summary

- Cases: 12
- Answerable Hit@10: 6/9 (0.6667)
- Answerable MRR@10: 0.6111
- Correct no-answer: 1/3 (0.3333)
- Status counts: `{"correct_no_answer": 1, "false_positive": 2, "hit": 6, "miss": 3}`

## Case Results

| Case | Status | First gold rank | Top hit |
|---|---|---:|---|
| rag_a0_001 | hit | 1 | xx_v1_dictionary 2026-09-07 paragraph:1 score=2 |
| rag_a0_002 | hit | 1 | xx_v1_dictionary 2026-09-07 paragraph:1 score=2 |
| rag_a0_003 | hit | 1 | xx_v1_dictionary 2026-09-07 paragraph:1 score=1 |
| rag_a0_004 | hit | 1 | xx_v1_dictionary 2026-09-07 paragraph:2 score=1 |
| rag_a0_005 | miss |  | None |
| rag_a0_006 | miss |  | None |
| rag_a0_007 | hit | 1 | xx_v1_dictionary 2026-09-07 paragraph:1 score=2 |
| rag_a0_008 | hit | 2 | xx_v1_dictionary 2026-09-07 paragraph:0 score=1 |
| rag_a0_009 | false_positive |  | xx_v1_dictionary 2026-09-07 paragraph:1 score=2 |
| rag_a0_010 | false_positive |  | xx_v1_dictionary 2026-09-07 paragraph:1 score=1 |
| rag_a0_011 | miss |  | None |
| rag_a0_012 | correct_no_answer |  | None |
