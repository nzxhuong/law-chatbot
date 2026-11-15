import os, json

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(root, "data", "chunks.jsonl"), encoding="utf-8") as f:
    CH = {c["id"]: c for c in map(json.loads, f)}


def links(p):
    """Dẫn chiếu: ngoại lệ trước, rồi ref thường, rồi đích mà chunk này sửa. (Văn bản sửa đổi: xem amenders)"""
    out = []
    for r in sorted(p.get("refs", []), key=lambda r: r["rel"] != "exception"):
        out += [(cid, r["rel"]) for cid in r["chunks"]]
    for e in p.get("amends", []):
        out += [(cid, "amends") for cid in e["chunks"]]
    return out


def expand(hits, seeds=3, cap=6, depth=2):
    """hits: [(score, payload)] sau rerank -> [(payload, rel, depth)]."""
    seen = {p["id"] for _, p in hits}
    out, q = [], [(CH.get(p["id"], p), 0) for _, p in hits[:seeds]]
    while q and len(out) < cap:
        p, d = q.pop(0)
        for cid, rel in links(p):
            if cid in seen or cid not in CH or len(out) >= cap:
                continue
            seen.add(cid)
            out.append((CH[cid], rel, d + 1))
            if d + 1 < depth and rel in ("ref", "exception"):
                q.append((CH[cid], d + 1))
    return out


def amenders(p):
    """[(edge, chunk văn bản sửa)] - đã sắp xếp mới -> cũ và cắt top 3 lúc ingest."""
    p = CH.get(p["id"], p)
    return [(a, CH[a["chunk"]]) for a in p.get("amended_by", []) if a["chunk"] in CH]


def amender_units(ch, src_unit):
    """đơn vị sửa + câu dẫn của nó (K1.a -> K1 nêu văn bản bị sửa)"""
    return [u for u in ch["units"]
            if u["id"] == src_unit or u["id"].startswith(src_unit + ".") or src_unit.startswith(u["id"] + ".")]
