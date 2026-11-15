# Chuẩn hoá nhãn quan hệ của bảng relationships -> {văn bản sửa: [văn bản bị sửa]} (cấp văn bản).
# Lấy từ virag-legal parse/relations.py (bỏ các nhãn không dùng).
LABELS = {  # nhãn -> (loại cạnh, True nếu doc_id là tác nhân)
    "Sửa đổi, bổ sung": ("AMENDS", True),
    "Văn bản sửa đổi": ("AMENDS", False),
    "Văn bản được sửa đổi": ("AMENDS", True),
    "Văn bản bổ sung": ("AMENDS", False),
    "Văn bản được bổ sung": ("AMENDS", True),
    "Văn bản quy định hết hiệu lực 1 phần": ("AMENDS", False),
    "Văn bản bị hết hiệu lực 1 phần": ("AMENDS", True),
    "Thay thế": ("REPLACES", True),
    "Bãi bỏ": ("REPEALS", True),
    "Văn bản quy định hết hiệu lực": ("REPEALS", False),
    "Văn bản hết hiệu lực": ("REPEALS", True),
}


def build_doc_graph(rows, id_to_doc):
    """rows: bảng relationships (doc_id, other_doc_id, relationship); id_to_doc: vbpl id -> doc id (45-2019-QH14).
    -> {amender_doc: [amended_doc, ...]} chỉ gồm văn bản có trong corpus."""
    g = {}
    for r in rows:
        spec = LABELS.get(r["relationship"])
        if not spec:
            continue
        x, y = str(r["doc_id"]), str(r["other_doc_id"])
        a, b = (x, y) if spec[1] else (y, x)
        if a in id_to_doc and b in id_to_doc and a != b:
            g.setdefault(id_to_doc[a], [])
            if id_to_doc[b] not in g[id_to_doc[a]]:
                g[id_to_doc[a]].append(id_to_doc[b])
    return g
