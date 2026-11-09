from retrieve import search, client
from FlagEmbedding import FlagReranker
import re
reranker = FlagReranker("BAAI/bge-reranker-v2-m3", use_fp16=True)

def rerank(q, k=5, pool=20):
    cands = [p for _, p in search(q, "hybrid", k=pool)]
    pairs = [[q, f'{c["path"]}\n{c["content"]}'] for c in cands]
    scores = reranker.compute_score(pairs, normalize=True, max_length=1024)
    if not isinstance(scores, list):
        scores = [scores]
    return sorted(zip(scores, cands), key=lambda x: -x[0])[:k]
if __name__ == "__main__":
    try:
        while True:
            q = input("\nq> ").strip()
            if not q:
                break
            for sc, p in rerank(q):
                print(f'{sc:.3f}  {p["id"]}  |  {p["doc"]} | {p["path"]} | {p["content"][:100]!r}')
    finally:
        client.close()