import uuid
from qdrant_client import QdrantClient, models
import os, json
from FlagEmbedding import BGEM3FlagModel
model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(root, "data", "chunks.jsonl"), encoding="utf-8") as f:
    chunk = [json.loads(l) for l in f.readlines()]
client = QdrantClient(path=os.path.join(root, "data", "qdrant"))
if client.collection_exists("docs"):
    client.delete_collection("docs")
client.recreate_collection(
    collection_name="docs",vectors_config={"dense":models.VectorParams(size=1024, distance=models.Distance.COSINE)}, sparse_vectors_config={"sparse": models.SparseVectorParams()})
B = 16
for i in range(0, len(chunk), B):
    batch = chunk[i:i+B]
    out = model.encode([f"{c['path']}\n{c['content']}" for c in batch], max_length=1024, batch_size=B, return_dense=True, return_sparse=True)
    points= [models.PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL, c["id"])),vector = {"dense": d.tolist(), "sparse": models.SparseVector(indices=[int(k)for k in s], values=[float(v) for v in s.values()])}, payload=c) for c, d, s in zip(batch, out["dense_vecs"], out["lexical_weights"])]
    client.upsert(collection_name="docs", points=points)
    print(f"{i}-{i+len(batch)}", client.count("docs").count)

print(len(chunk), client.count("docs").count)