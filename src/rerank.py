from .retrieve import search, client
from FlagEmbedding import FlagReranker
reranker = FlagReranker("BAAI/bge-reranker-v2-m3", use_fp16=True)

def rerank(q, k=5, pool=20):
    cands = [p for _, p in search(q, "hybrid", k=pool)]
    pairs = [[q, f'{c["path"]}\n{c["content"]}'] for c in cands]
    scores = reranker.compute_score(pairs, normalize=True, max_length=1024)
    if not isinstance(scores, list):
        scores = [scores]
    return sorted(zip(scores, cands), key=lambda x: -x[0])[:k]

def retrieve_multi(q, subs, k=5, k_sub=2, extra=4):
    base = rerank(q, k=k)
    seen = {p["id"] for _, p in base}
    lists = [rerank(s, k=k_sub) for s in subs]
    out = list(base)
    added = 0
    for rank in range(k_sub):
        for lst in lists:
            if added < extra and rank < len(lst) and lst[rank][1]["id"] not in seen:
                seen.add(lst[rank][1]["id"]); out.append(lst[rank]); added += 1
    return out

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