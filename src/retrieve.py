import os, re, json, unicodedata
import numpy as np
from rank_bm25 import BM25Okapi          # pip install rank-bm25
from qdrant_client import QdrantClient
from FlagEmbedding import BGEM3FlagModel

model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
client = QdrantClient(path=os.path.join(root, "data", "qdrant"))
CH = [json.loads(l) for l in open(os.path.join(root, "data", "chunks.jsonl"), encoding="utf-8")]
BY = {c["id"]: c for c in CH}

def tok(t):
    w = re.findall(r"\w+", unicodedata.normalize("NFC", t).lower())
    return w + [a + "_" + b for a, b in zip(w, w[1:])]    # unigram + bigram

bm = BM25Okapi([tok(f"{c['path']}\n{c['content']}") for c in CH])

def bm25(q, k):
    s = bm.get_scores(tok(q)); i = np.argsort(-s)[:k]
    return [(float(s[j]), CH[j]) for j in i if s[j] > 0]

def dense(q, k):
    d = model.encode([q], return_dense=True)["dense_vecs"][0].tolist()
    r = client.query_points("docs", query=d, using="dense", limit=k).points
    return [(x.score, BY.get(x.payload["id"], x.payload)) for x in r]

def search(q, mode="dense", k=5):
    if mode == "dense": return dense(q, k)
    if mode == "sparse": return bm25(q, k)
    sc, by = {}, {}
    for lst in (dense(q, 20), bm25(q, 20)):                 # RRF
        for r, (_, p) in enumerate(lst):
            sc[p["id"]] = sc.get(p["id"], 0) + 1 / (61 + r); by[p["id"]] = p
    return [(s, by[i]) for i, s in sorted(sc.items(), key=lambda x: -x[1])[:k]]