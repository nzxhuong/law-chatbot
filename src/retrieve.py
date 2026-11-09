
import os
from qdrant_client import QdrantClient, models
from FlagEmbedding import BGEM3FlagModel
model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
client = QdrantClient(path=os.path.join(root, "data", "qdrant"))

def search(q: str, mode: str = "dense", k: int = 5):
    e = model.encode([q], return_dense=True, return_sparse=True)
    d = e['dense_vecs'][0].tolist()
    s = e["lexical_weights"][0]
    sv = models.SparseVector(indices=[k for k in s], values=[v for v in s.values()])
    if mode == "dense":
        res = client.query_points('docs', query = d, using = "dense", limit=k)
    elif mode == "sparse":
        res = client.query_points('docs', query = sv, using = "sparse", limit=k)
    else:
        res = client.query_points('docs', prefetch=[models.Prefetch(query=d, using="dense",limit=20), models.Prefetch(query=sv, using="sparse",limit=20)], query = models.FusionQuery(fusion = models.Fusion.RRF), limit=k)
     
    return [(r.score, r.payload) for r in res.points]

if __name__ == "__main__":
    try:
        while True:
            q = input("Enter your query (or 'exit' to quit): ")
            if q.lower() == 'exit':
                break
            for mode in ["dense", "sparse", "hybrid"]:
                print(f"Results for mode '{mode}':")
                for s,p in search(q, mode):
                    print(f'{s:.3f}  {p["file"]} | {p["path"]} | {p["content"][:100]!r}')

    finally:
        client.close()