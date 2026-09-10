# RAG Exact Retrieval Baseline

Generated from `evaluation/rag/run_a0_baseline.py` using the current `ExactRetriever`.

## Summary

- Cases: 40
- Answerable Hit@10: 22/28 (0.7857)
- Answerable MRR@10: 0.6726
- Correct no-answer: 1/12 (0.0833)
- Status counts: `{"correct_no_answer": 1, "false_positive": 11, "hit": 22, "miss": 6}`

## Case Results

| Case | Status | First gold rank | Top hit |
|---|---|---:|---|
| rag_a1_001 | hit | 1 | xx_v1_dictionary 2026-09-07 paragraph:1 score=2 |
| rag_a1_002 | hit | 1 | xx_v1_dictionary 2026-09-07 paragraph:1 score=2 |
| rag_a1_003 | hit | 2 | xx_v1_dictionary 2026-09-07 paragraph:0 score=1 |
| rag_a1_004 | hit | 2 | xx_v1_dictionary 2026-09-07 paragraph:0 score=1 |
| rag_a1_005 | hit | 2 | xx_v1_dictionary 2026-09-07 paragraph:0 score=1 |
| rag_a1_006 | hit | 1 | xx_v1_dictionary 2026-09-07 paragraph:1 score=1 |
| rag_a1_007 | hit | 1 | xx_v1_dictionary 2026-09-07 paragraph:1 score=1 |
| rag_a1_008 | hit | 1 | xx_v1_dictionary 2026-09-07 paragraph:1 score=2 |
| rag_a1_009 | hit | 1 | xx_v1_dictionary 2026-09-07 paragraph:1 score=1 |
| rag_a1_010 | hit | 1 | xx_v1_dictionary 2026-09-07 paragraph:1 score=1 |
| rag_a1_011 | hit | 1 | xx_v1_dictionary 2026-09-07 paragraph:2 score=1 |
| rag_a1_012 | miss |  | None |
| rag_a1_013 | hit | 1 | xx_v1_dictionary 2026-09-07 paragraph:2 score=1 |
| rag_a1_014 | miss |  | None |
| rag_a1_015 | hit | 1 | xx_v1_dictionary 2026-09-07 paragraph:2 score=2 |
| rag_a1_016 | miss |  | None |
| rag_a1_017 | hit | 1 | xx_v1_dictionary 2026-09-07 paragraph:2 score=1 |
| rag_a1_018 | hit | 3 | xx_v1_dictionary 2026-09-07 paragraph:0 score=1 |
| rag_a1_019 | miss |  | None |
| rag_a1_020 | miss |  | xx_v1_dictionary 2026-09-07 paragraph:0 score=1 |
| rag_a1_021 | hit | 1 | xx_v1_dictionary 2026-09-07 paragraph:1 score=2 |
| rag_a1_022 | hit | 2 | xx_v1_dictionary 2026-09-07 paragraph:0 score=1 |
| rag_a1_023 | hit | 1 | xx_v1_dictionary 2026-09-07 paragraph:1 score=1 |
| rag_a1_024 | miss |  | xx_v1_dictionary 2026-09-07 paragraph:0 score=1 |
| rag_a1_025 | hit | 1 | xx_v1_dictionary 2026-09-07 paragraph:2 score=3 |
| rag_a1_026 | hit | 1 | xx_v1_dictionary 2026-09-07 paragraph:2 score=1 |
| rag_a1_027 | hit | 2 | xx_v1_dictionary 2026-09-07 paragraph:0 score=1 |
| rag_a1_028 | hit | 1 | xx_v1_dictionary 2026-09-07 paragraph:1 score=2 |
| rag_a1_029 | false_positive |  | xx_v1_dictionary 2026-09-07 paragraph:1 score=2 |
| rag_a1_030 | false_positive |  | xx_v1_dictionary 2026-09-07 paragraph:0 score=1 |
| rag_a1_031 | false_positive |  | xx_v1_dictionary 2026-09-07 paragraph:1 score=1 |
| rag_a1_032 | false_positive |  | xx_v1_dictionary 2026-09-07 paragraph:0 score=1 |
| rag_a1_033 | false_positive |  | xx_v1_dictionary 2026-09-07 paragraph:0 score=1 |
| rag_a1_034 | false_positive |  | xx_v1_dictionary 2026-09-07 paragraph:0 score=1 |
| rag_a1_035 | false_positive |  | xx_v1_dictionary 2026-09-07 paragraph:1 score=2 |
| rag_a1_036 | false_positive |  | xx_v1_dictionary 2026-09-07 paragraph:0 score=1 |
| rag_a1_037 | correct_no_answer |  | None |
| rag_a1_038 | false_positive |  | xx_v1_dictionary 2026-09-07 paragraph:0 score=1 |
| rag_a1_039 | false_positive |  | xx_v1_dictionary 2026-09-07 paragraph:0 score=1 |
| rag_a1_040 | false_positive |  | xx_v1_dictionary 2026-09-07 paragraph:1 score=2 |
