# law-chatbot

[**Demo: rag-legal on Hugging Face Spaces**](https://huggingface.co/spaces/NZUONG/rag-legal)


A retrieval-augmented chatbot for Vietnamese labor and social-insurance law. It answers questions in Vietnamese, cites the exact provision (Điều / Khoản / Điểm) behind each statement, follows cross-references and later amendments, and refuses when the retrieved text is not enough to answer.

> This is a research/baseline project, not legal advice.

## What it does

- **Provision-level chunks.** One chunk per Khoản (long Khoản are split per Điểm), each prefixed with its path: `law number + title > Chương > Điều`.
- **Hybrid retrieval.** Dense (`BAAI/bge-m3`) and BM25 (Vietnamese unigram + bigram), fused with reciprocal rank fusion.
- **Reranking.** `BAAI/bge-reranker-v2-m3` over the top 20 hybrid candidates.
- **Cross-reference expansion.** Chunks that a hit refers to ("theo quy định tại khoản 2 Điều này", exceptions) are pulled in as extra context.
- **Amendment awareness.** Each chunk records which later provisions amend it (`amended_by`) and which it amends (`amends`). Amending text is placed right under the original in the prompt, so the answer can say what changed (not yet tested).
- **Citation checking.** Every claim must end with a chunk id in brackets. Ids that don't exist, uncited lines, and numbers that don't appear in the cited text are flagged.
- **Refusal.** If the best reranked chunk scores below a threshold, the bot says it found no sufficient basis instead of answering.

## Corpus

Built from the [`th1nhng0/vietnamese-legal-documents`](https://huggingface.co/datasets/th1nhng0/vietnamese-legal-documents) dataset (content, metadata and relationships tables). Currently three documents (`TARGETS` in `src/html_parser.py`):

| Law | Note |
|---|---|
| 45/2019/QH14 | Bộ luật Lao động 2019 |
| 41/2024/QH15 | Luật Bảo hiểm xã hội 2024 |
| 71/2025/QH15 | Luật Công nghiệp công nghệ số |

## Pipeline

```
html_parser.py  ->  chunk.py  ->  refs.py  ->  index.py  ->  retrieve.py / rerank.py  ->  generate.py
 (parse HTML,      (chunks.jsonl) (refs, amends,  (Qdrant,     (hybrid search, rerank)     (rewrite, context,
  doc graph)                       amended_by)     dense+sparse)                              answer, verify)
```
## Chunk format

```json
{
  "id": "41-2024-QH15:D2.K1.a",
  "doc": "41-2024-QH15",
  "so_ky_hieu": "41/2024/QH15",
  "title": "Luật Bảo hiểm xã hội",
  "path": "41/2024/QH15 Luật Bảo hiểm xã hội > Chương I ... > Điều 2. ...",
  "content": "1. Người lao động ... bao gồm:\na) ...",
  "units": [{"id": "41-2024-QH15:D2.K1", "text": "..."}, {"id": "41-2024-QH15:D2.K1.a", "text": "..."}],
  "refs": [], "unresolved_refs": [], "amends": [], "amended_by": [],
  "loai_van_ban": "Luật", "tinh_trang_hieu_luc": "...", "ngay_ban_hanh": "...", "ngay_co_hieu_luc": "..."
}
```

Ids follow `<doc>:D<điều>[.K<khoản>][.<điểm>]`. A repeated id gets a `~2`, `~3` suffix.

## Configuration

| Setting | Value | Where |
|---|---|---|
| Khoản split threshold | 800 chars (longer Khoản are split per Điểm) | `chunk.py` `SPLIT` |
| Max chunk for Điều without Khoản | 1800 chars | `chunk.py` `MAX` |
| Embedding | `BAAI/bge-m3`, dense 1024-d + sparse | `index.py`, `retrieve.py` |
| BM25 | unigram + bigram over `path + content` | `retrieve.py` `tok` |
| Fusion | RRF, k = 61, 20 candidates from each side | `retrieve.py` |
| Reranker | `BAAI/bge-reranker-v2-m3`, pool 20, final k = 5 | `rerank.py` |
| Refusal threshold | top rerank score < 0.3 | `generate.py` `THRESH` |
| Expansion | 3 seeds, cap 6, depth 2 | `expand.py` |
| Max amenders per chunk | 3 | `refs.py` |
| Generator | `gemini-3.5-flash-lite` | `generate.py` `MODEL` |

## Evaluation

[There Are Only 6 RAG Evals](https://jxnl.co/writing/2025/05/19/there-are-only-6-rag-evals/): Tier 1 retrieval metrics (recall@k, MRR) and Tier 2 LLM-judged relationships (context relevance, faithfulness, answer relevance). Tier 3 is not run.

Results, method and caveats are in [`EVAL_REPORT.md`](eval/EVAL_REPORT.md).

## Known limitations

- Tiny corpus (three laws). Retrieval numbers will drop as the corpus grows.
- Amendments are only as complete as the dataset's relationships table and the pattern matching in `refs.py`.
- Long first-person scenarios retrieve worse than short, direct questions (see the eval report).

## TODO
[ ] Eval
[ ] Graph rag?

## Resources & References
- Jason Liu’s [There Are Only 6 RAG Evals](https://jxnl.co/writing/2025/05/19/there-are-only-6-rag-evals/)
- [`th1nhng0/vietnamese-legal-documents`](https://huggingface.co/datasets/th1nhng0/vietnamese-legal-documents) dataset 