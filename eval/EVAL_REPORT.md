# Baseline Evaluation Report: law-chatbot

Date: 2026-11-19
Scope: baseline measurement of the current pipeline. Nothing was tuned or changed to improve the numbers.

## 1. Summary

- **Retrieval (Tier 1).** On the scenario-style set (`blld_1`, 106 questions), a correct provision is in the top 10 for about 90% of questions (R@10 0.896 to 0.915 depending on mode). Reranking mainly improves ranking: R@1 goes from 0.642 (dense) to 0.726 and MRR from 0.727 to 0.795. Dense, sparse and hybrid are statistically indistinguishable.
- **Generation (Tier 2, `blld_1`).** 7.5% of questions were refused (about 8 of 106). Faithfulness measured 0.997, but that judge has not been validated (section 6). At least one directly relevant chunk was retrieved for 94.9% of answered questions, which is about 0.88 end to end once refusals are counted.
- **Weak spot.** Long first-person scenarios that mix several legal issues. Seven questions failed in every retrieval mode, and refusals are expected to overlap with them (not yet cross-checked).
- **Easy set.** `blld_2` (46 questions) is near ceiling and mostly serves as a regression check.

## 2. Framework

Metrics follow Jason Liu's [There Are Only 6 RAG Evals](https://jxnl.co/writing/2025/05/19/there-are-only-6-rag-evals/): a RAG system has a question (Q), retrieved context (C) and an answer (A), and every failure is one of six relationships between them.

| Tier | Relationship | Status |
|---|---|---|
| 1 | Retrieval recall / MRR against labeled provisions | Done |
| 2 | Context relevance (C\|Q) | Done (`blld_1`) |
| 2 | Faithfulness (A\|C) | Done (`blld_1`), judge not validated |
| 2 | Answer relevance (A\|Q) | Done (`blld_1`) |
| 3 | Context support coverage (C\|A), question answerability (Q\|C), self-containment (Q\|A) | Not run |

## 3. System under test

| Component | Setting |
|---|---|
| Corpus | 3 documents: 45/2019/QH14, 41/2024/QH15, 71/2025/QH15 |
| Chunking | per Khoản; Khoản over 800 chars split per Điểm; Điều without Khoản capped at 1800 chars |
| Dense | `BAAI/bge-m3`, input `path + content` |
| Sparse | BM25, Vietnamese unigram + bigram |
| Hybrid | reciprocal rank fusion, k = 61, 20 candidates per side |
| Reranker | `BAAI/bge-reranker-v2-m3`, pool 20 |
| Answering | query rewrite, rerank top 5, reference expansion, amender text in context, `gemini-3.5-flash-lite`, refusal below rerank score 0.3 |

Tier 1 runs `search()` / `rerank()` directly on the raw question. Tier 2 runs the full `answer()` function, which rewrites the question first and keeps the top 5 chunks, so the two tiers do not measure retrieval under identical conditions.

## 4. Evaluation data

Both sets come from public Q&A booklets on the 2019 Labor Code. [blld_1](https://www.studocu.vn/vn/document/truong-dai-hoc-sai-gon/bo-luat-lao-dong/106-cau-hoi-dap-tinh-huong-phap-luat-ve-bo-luat-lao-dong-nam-2019/96392508?sid=2bac7925-7b2c-4297-a998-441f40123d5e1795082603) [blld_2](https://sotuphap.ninhbinh.gov.vn/uploads/images/2025/t12/t%C3%ACnh_hu%E1%BB%91ng_h%E1%BB%8Fi_%C4%91%C3%A1p_b%E1%BB%99_lu%E1%BA%ADt_lao_%C4%91%E1%BB%99ng.pdf). Only 45/2019/QH14 is labeled.

| Set | Questions | Style |
|---|---|---|
| `blld_1` | 106 | Mostly situation-based ("Chị S xin đi làm công nhân...") plus direct questions. Questions do not name the Điều. |
| `blld_2` | 46 | Mostly direct lookups ("Các trường hợp giấy phép lao động hết hiệu lực"). Many questions paraphrase the Điều title, which is also part of the indexed `path`, so this set is easy. |

Metrics:
- `R@k`: share of questions with at least one hit in the top k.
- `MRR`: mean reciprocal rank of the first hit, top 10.
- `cover@10`: average share of a question's labels found in the top 10 (stricter than R@10 for multi-label questions).
- `R@10 CI`: 95% bootstrap interval over questions.

Headline numbers use `blld_1` only. Pooled `ALL` rows are secondary because `blld_2` raises them.

## 5. Tier 1 results

### `blld_1` (n = 106)

| Mode | R@1 | R@5 | R@10 | MRR | cover@10 | R@10 95% CI |
|---|---|---|---|---|---|---|
| dense | 0.642 | 0.840 | 0.896 | 0.727 | 0.813 | 0.84 – 0.95 |
| sparse (BM25) | 0.642 | 0.858 | 0.896 | 0.728 | 0.798 | 0.84 – 0.95 |
| hybrid | 0.689 | 0.877 | 0.906 | 0.765 | 0.818 | 0.85 – 0.95 |
| rerank | 0.726 | 0.887 | 0.915 | 0.795 | 0.834 | 0.86 – 0.96 |

### `blld_2` (n = 46)

| Mode | R@1 | R@5 | R@10 | MRR | cover@10 |
|---|---|---|---|---|---|
| dense | 0.826 | 0.957 | 1.000 | 0.884 | 0.989 |
| sparse (BM25) | 0.739 | 0.957 | 0.978 | 0.820 | 0.957 |
| hybrid | 0.804 | 0.978 | 0.978 | 0.869 | 0.967 |
| rerank | 0.935 | 0.957 | 0.978 | 0.945 | 0.967 |

The R@10 interval for dense on this set came out as (1.0, 1.0). That is the bootstrap collapsing because every question hit, not real certainty.

### Pooled (`ALL`, n = 152), secondary

| Mode | R@1 | R@5 | R@10 | MRR | cover@10 |
|---|---|---|---|---|---|
| dense | 0.697 | 0.875 | 0.928 | 0.774 | 0.866 |
| sparse (BM25) | 0.671 | 0.888 | 0.921 | 0.756 | 0.846 |
| hybrid | 0.724 | 0.908 | 0.928 | 0.796 | 0.863 |
| rerank | 0.789 | 0.908 | 0.934 | 0.840 | 0.874 |

### Reading

- **Reranking helps ranking, not recall.** It is the only change that shows up on both sets: R@1 +8 points on `blld_1` over dense, +11 on `blld_2`, and higher MRR on both. R@10 barely moves.
- **Dense, sparse and hybrid are within noise.** With 106 questions the 95% interval is about ±5 points, so 0.896 vs 0.906 is not a difference.
- **Recall plateaus around 0.90 to 0.92 at R@10 in every mode.** The same questions seem to fail everywhere.
- **`cover@10` sits about 0.08 below R@10 on `blld_1`.** Questions that need several provisions often get only some of them.

## 6. Tier 2 results

`blld_1` only, over the full `answer()` pipeline. Context relevance is judged per retrieved chunk; faithfulness and answer relevance are judged per answer. Judging used an LLM; scores for the three metrics cover answered (non-refused) questions only.

| Metric | Value | Definition |
|---|---|---|
| refusal rate | 0.075 | share of questions where the bot declined (about 8 of 106; all questions are answerable from the corpus) |
| `ctx_rel` | 0.458 | mean relevance of the 5 retrieved chunks (0 / 1 / 2 scale, normalized) |
| `ctx_any` | 0.949 | share of answered questions where at least one chunk was judged directly relevant |
| `faith` | 0.997 | share of answer claims supported by the context |
| `ans_rel` | 0.872 | how directly the answer addresses the question (0 / 1 / 2 scale, normalized) |

End to end over all 106 questions: about 0.949 × 98 / 106 ≈ **0.88** of questions got an answer with at least one directly relevant chunk.

`blld_2` Tier 2 results were not recorded.

### Reading and caveats

- **`faith` = 0.997 is not yet trustworthy.** The generator and the judge are the same model family, the answers carry citations, and scenario answers apply a rule to the user's facts, which a lenient judge may accept. A negative control (inject an unsupported claim into ~20 answers and check that the judge flags it) and a comparison with the deterministic checks in `verify_citations` (`invalid`, `uncited`, `number_warnings`) have not been done.
- **`ctx_rel` = 0.458 is not low by itself.** It averages five chunks, and most questions have only one or two directly relevant ones, so the realistic ceiling is roughly 0.5 to 0.6.
- **Refusals are the largest cost.** Every question in the set is answerable, so each refusal is a false refusal, and the three scores above ignore them.
- **Tier 1 and Tier 2 are not directly comparable** because `answer()` rewrites the question before retrieval.

## 7. Limitations

- **Small sets.** 106 and 46 questions give roughly ±5 points of uncertainty at R@10. Differences between dense, sparse and hybrid cannot be read from this data.
- **Labels from booklets.** Labels follow what each booklet's answer cites. They may omit other provisions a lawyer would also consider relevant. The pipeline was not tuned on them.
- **One law labeled.** Only 45/2019/QH14 has ground truth. Cross-document retrieval and amendment handling (a newer law changing an older provision) are not tested.
- **Granularity.** Labels mix Điều, Khoản and Điểm level. Prefix matching avoids false misses from chunk splitting, but Điều-level labels are easier to hit than Điểm-level ones.
- **Overlap.** The two booklets cover the same law and some topics overlap, so the two sets are not fully independent.
- **Judge model.** All Tier 2 scores come from an LLM judge that has not been checked against human labels.

## 8. Not evaluated

- Tier 3 (context support coverage, question answerability, self-containment).
- Validation of the Tier 2 judges against hand labels.
- Retrieval over amended provisions and across laws.
- Tier 2 on `blld_2`.
