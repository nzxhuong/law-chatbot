import os, re, json, itertools
from datetime import date, datetime
from collections import defaultdict

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = os.path.join(root, "data", "chunks.jsonl")

SEP = r"\s*(?:,|và|hoặc)\s*"
RE_REF = re.compile(
    r"(?:(?:các\s+)?điểm\s+(?P<diems>[a-zđ](?:" + SEP + r"(?:điểm\s+)?[a-zđ])*)\s+)?"
    r"(?:(?:các\s+)?khoản\s+(?P<khoans>\d+[a-zđ]?(?:" + SEP + r"(?:khoản\s+)?\d+[a-zđ]?)*)\s+)?"
    r"Điều\s+(?P<dieu>\d+[a-zđ]?|này)\b", re.I)
RE_SELF = re.compile(r"^\s*(?:của\s+)?(?:Bộ luật|Luật|Nghị định|Thông tư|Pháp lệnh|Nghị quyết|Quyết định)\s+này", re.I)
RE_OTHER = re.compile(r"^\s*(?:của\s+)?(?:Bộ luật|Luật|Nghị định|Thông tư|Pháp lệnh)\b(?:(?!\b(?:Điều|khoản|điểm)\b)[^,.;:()\n]){0,90}", re.I)
RE_SO = re.compile(r"\d+/\d{4}/[A-ZĐ0-9-]+")
RE_QUOTED = re.compile(r"[“\"«][^”\"»]*[”\"»]|[“«].*$", re.S)   # đoạn trích nguyên văn
RE_ART = re.compile(r":D(\d+[a-zđ]?)")
RE_AMEND = re.compile(r"^\s*(?:\d+\.|[a-zđ]\))?\s*(Sửa đổi, bổ sung|Sửa đổi|Bổ sung|Bãi bỏ|Hủy bỏ|Thay thế)\b", re.I)
ALIAS = {"bộ luật lao động": "45-2019-QH14"}   # chỉ dùng cho ref tên-không-số-hiệu trong extract()
MAX_AMENDERS = 3   # mỗi chunk giữ tối đa 3 văn bản sửa đổi, mới nhất trước


def load_graph():
    p = os.path.join(root, "data", "doc_graph.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def _date(s):
    for f in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime((s or "").strip()[:10], f).date()
        except ValueError:
            pass
    return date.min
CAP_UNIT = 5   # tối đa chunk cho 1 ref Khoản/Điểm (Khoản tách nhiều Điểm)
CAP_ART = 3    # tối đa chunk cho 1 ref cả Điều


def build_maps(chunks):
    unit_chunks, art_chunks = defaultdict(list), defaultdict(list)
    for c in chunks:
        if "~" in c["id"]:          # Điều/mã trùng (văn bản đính kèm): không làm đích
            continue
        if m := re.match(r"^(.*?:D\d+[a-zđ]?)", c["id"]):
            art_chunks[m[1]].append(c["id"])
        for u in c["units"]:
            if "~" not in u["id"] and c["id"] not in unit_chunks[u["id"]]:
                unit_chunks[u["id"]].append(c["id"])
    return unit_chunks, art_chunks


def targets(doc, dieu, khoans, diems, unit_chunks, art_chunks):
    """(Điều, [khoản], [điểm]) -> [(unit_id, [chunk_id])]; ids rỗng = đích không có trong corpus."""
    base = f"{doc}:D{dieu}"
    ks = re.findall(r"\d+[a-zđ]?", (khoans or "").lower()) or [None]
    ds = re.findall(r"\b[a-zđ]\b", (diems or "").lower()) or [None]
    out = []
    for khoan, diem in list(itertools.product(ks, ds))[:12]:
        if not khoan and not diem:                   # ref cả Điều -> lấy từ đầu Điều
            uid, ids = base, art_chunks.get(base, [])[:CAP_ART]
        else:
            cands = [x for x in (khoan and diem and f"{base}.K{khoan}.{diem}",
                                 khoan and f"{base}.K{khoan}",
                                 diem and not khoan and f"{base}.{diem}") if x]
            uid = next((x for x in cands if x in unit_chunks), None)
            if uid:
                ids = unit_chunks[uid][:CAP_UNIT]
            else:                                    # không thấy Khoản/Điểm -> lùi về Điều
                uid, ids = base, art_chunks.get(base, [])[:CAP_ART]
        out.append((uid, ids))
    return out


def extract(c, docs, unit_chunks, art_chunks, graph):
    art = RE_ART.search(c["id"])
    title = re.sub(r"^\s*Điều\s+\w+\.\s*", "", c["path"].rsplit(">", 1)[-1])
    in_amending = bool(RE_AMEND.match(title))      # Điều "Sửa đổi, bổ sung ... các luật khác"
    refs, unres = {}, []
    for u in c["units"]:
        if c["doc"] in graph and RE_AMEND.match(u["text"]):   # câu sửa đổi luật khác: extract_amends xử lý
            continue
        foreign = in_amending or "~" in u["id"]    # nội dung trích của luật khác: "Luật này"/"Điều N" không phải doc hiện tại
        text = RE_QUOTED.sub(" ", u["text"])
        for m in RE_REF.finditer(text):
            dieu = m["dieu"]
            if dieu.lower() == "này":
                if not art:
                    continue
                dieu = art[1]
            doc, after = c["doc"], text[m.end():]
            if RE_SELF.match(after):
                if foreign:
                    continue
            elif mo := RE_OTHER.match(after):
                so = RE_SO.search(mo[0])
                d2 = (so[0].replace("/", "-").upper() if so
                      else next((d for n, d in ALIAS.items() if n in mo[0].lower()), None))
                if d2 not in docs:
                    unres.append(f"{m[0].strip()} {mo[0].strip()}")
                    continue
                doc = d2
            elif foreign:
                continue
            seg = text[:m.start()].rsplit(".", 1)[-1].rsplit(";", 1)[-1]
            rel = "exception" if re.search(r"\btrừ\b", seg, re.I) else "ref"
            for uid, ids in targets(doc, dieu, m["khoans"], m["diems"], unit_chunks, art_chunks):
                if not ids:                          # đích không có trong corpus
                    unres.append(m[0].strip())
                    continue
                ids = [i for i in ids if i != c["id"]]   # bỏ tự trỏ vào chính chunk
                if ids and ((uid not in refs) or rel == "exception"):
                    refs[uid] = {"unit": uid, "chunks": ids, "rel": rel}
    return list(refs.values()), list(dict.fromkeys(unres))


def amend_doc(c, u, docs, graph):
    """Văn bản bị sửa: số hiệu nêu ở câu -> câu cha (K1.a -> K1) -> tiêu đề Điều;
    không nêu thì lấy văn bản duy nhất mà văn bản này sửa (theo bảng quan hệ)."""
    by_id = {x["id"]: x["text"] for x in c["units"]}
    uid, cands = u["id"], [u["text"]]
    while "." in uid.split(":")[-1]:
        uid = uid.rsplit(".", 1)[0]
        if uid in by_id:
            cands.append(by_id[uid])
    cands.append(c["path"].rsplit(">", 1)[-1])
    for t in cands:
        t = re.split(r"\s+đã được\b|\s+như sau\b", t.split("\n")[0])[0]   # bỏ phần "đã được sửa đổi bởi..."
        if so := RE_SO.search(t):
            return so[0].replace("/", "-").upper()
    amended = [d for d in graph.get(c["doc"], []) if d in docs]
    return amended[0] if len(amended) == 1 else None


RE_ANCHOR = re.compile(r"\bvào\s+(?:sau|trước)\s+(?P<seg>.+)$", re.I)


def amend_targets(op, head):
    """[(điều, khoản, điểm, text)]. Bổ sung 'vào sau/trước X' -> gắn vào X (đơn vị đã có), không phải đơn vị mới."""
    if op == "add" and (ma := RE_ANCHOR.search(head)):
        seg = ma["seg"]
        if d := re.search(r"Điều\s+(\d+[a-zđ]?)", seg, re.I):
            k = re.search(r"khoản\s+(\d+[a-zđ]?)", seg, re.I)    # mỏ neo đầu tiên ("sau ...")
            p = re.search(r"điểm\s+([a-zđ])\b", seg, re.I)
            return [(d[1], k and k[1], p and p[1], ma[0][:60])]
    return [(m["dieu"], m["khoans"], m["diems"], m[0]) for m in RE_REF.finditer(head)
            if m["dieu"].lower() != "này"]


def extract_amends(c, docs, unit_chunks, art_chunks, graph):
    out, unres = {}, []
    if c["doc"] not in graph:          # cổng văn bản: chỉ văn bản có quan hệ sửa/bãi bỏ/thay thế mới có câu sửa đổi
        return [], []
    for u in c["units"]:
        m0 = RE_AMEND.match(u["text"])
        if not m0:
            continue
        head = re.split(r"\s+như sau\b|\n", u["text"])[0]
        w = m0[1].lower()
        op = "repeal" if w in ("bãi bỏ", "hủy bỏ") else "add" if w == "bổ sung" else "modify"
        tg = amend_targets(op, head)
        scope = "article" if op == "add" and re.search(r"Bổ sung\s+(?:các\s+)?(?:khoản|điểm)\b", head, re.I) else "unit"
        if not tg:                         # câu dẫn ("Sửa đổi, bổ sung một số điều của ..."): chỉ làm ngữ cảnh
            continue
        doc = amend_doc(c, u, docs, graph)
        if doc not in docs:                # không rõ văn bản đích / ngoài corpus
            unres.append(f"[amend→{doc}] {head[:100]}")
            continue
        for dieu, khoans, diems, txt in tg:
            for uid, ids in targets(doc, dieu, khoans, diems, unit_chunks, art_chunks):
                if ids:
                    out[(u["id"], uid)] = {"src_unit": u["id"], "unit": uid, "chunks": ids, "op": op, "scope": scope}
                else:
                    unres.append(f"[amend] {txt.strip()}")
    return list(out.values()), list(dict.fromkeys(unres))


if __name__ == "__main__":
    with open(path, encoding="utf-8") as f:
        chunks = [json.loads(l) for l in f]
    docs = {c["doc"] for c in chunks}
    graph = load_graph()
    unit_chunks, art_chunks = build_maps(chunks)
    by_id = {c["id"]: c for c in chunks}
    for c in chunks:
        c["refs"], c["unresolved_refs"] = extract(c, docs, unit_chunks, art_chunks, graph)
        c["amends"], un = extract_amends(c, docs, unit_chunks, art_chunks, graph)
        c["unresolved_refs"] += un
        c["amended_by"] = []
    for c in chunks:                       # đảo chiều: chunk bị sửa biết ai sửa nó
        for e in c["amends"]:
            tids = list(e["chunks"])
            if e.get("scope") == "article" and (m := re.match(r"^(.*?:D\d+[a-zđ]?)", e["unit"])):
                tids += art_chunks.get(m[1], [])[:12]      # thêm mục vào danh sách: cả Điều đều cần biết
            for tid in dict.fromkeys(tids):
                a = {"chunk": c["id"], "doc": c["doc"], "src_unit": e["src_unit"], "unit": e["unit"], "op": e["op"]}
                if a not in by_id[tid]["amended_by"]:
                    by_id[tid]["amended_by"].append(a)
    for c in chunks:                       # mới nhất trước, tối đa MAX_AMENDERS
        c["amended_by"].sort(key=lambda a: (_date(by_id[a["chunk"]].get("ngay_ban_hanh")), a["chunk"]), reverse=True)
        c["amended_by"] = c["amended_by"][:MAX_AMENDERS]
    with open(path + ".tmp", "w", encoding="utf-8") as out:
        for c in chunks:
            out.write(json.dumps(c, ensure_ascii=False) + "\n")
    os.replace(path + ".tmp", path)
    print(f"{sum(bool(c['refs']) for c in chunks)} chunk có refs, "
          f"{sum(bool(c['amends']) for c in chunks)} chunk sửa đổi, "
          f"{sum(bool(c['amended_by']) for c in chunks)} chunk bị sửa, "
          f"{sum(len(c['unresolved_refs']) for c in chunks)} ref chưa resolve")
