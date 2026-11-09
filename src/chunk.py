import os, re, json

S = re.compile(r'^(#{1,6})\s+(.+)$')
ART = re.compile(r'^Điều\s+(\d+[a-zđ]?)', re.I)
KHOAN = re.compile(r'^(\d+[a-zđ]?)\.\s')
DIEM = re.compile(r'^([a-zđ])\)')
MAX = 1800    # Điều không có Khoản: cắt theo độ dài
SPLIT = 800   # Khoản dài hơn mức này thì tách từng Điểm; 0 = luôn tách

def label(aid, blocks):
    """gán mã cho từng đoạn: D35 / D35.K2 / D35.K2.b"""
    out, k, seen = [], None, {}
    for b in blocks:
        if m := KHOAN.match(b):
            k = m[1]; out.append([f"{aid}.K{k}", b, k])
        elif m := DIEM.match(b):
            out.append([f"{aid}.K{k}.{m[1]}" if k else f"{aid}.{m[1]}", b, k])
        elif out:
            out[-1][1] += "\n" + b
        else:
            out.append([aid, b, None])
    for u in out:  # mã trùng -> thêm ~2, ~3
        seen[u[0]] = seen.get(u[0], 0) + 1
        if seen[u[0]] > 1:
            u[0] += f"~{seen[u[0]]}"
    return out

def pack(units):
    """-> [(chunk_id, [units])]"""
    groups = []
    for u in units: 
        if not groups or KHOAN.match(u[1]):
            groups.append([u])
        else:
            groups[-1].append(u)
    if len(groups) > 1 and not any(KHOAN.match(u[1]) for u in groups[0]):
        intro = groups.pop(0)      
        groups[0][:0] = intro

    out = []
    for g in groups:
        ki = next((i for i, u in enumerate(g) if KHOAN.match(u[1])), -1)
        rest = g[ki + 1:] if ki >= 0 else []
        if ki >= 0 and (sum(len(u[1]) for u in g) <= SPLIT or not rest):
            out.append((g[ki][0], g))                 # cả Khoản = 1 chunk
        elif ki >= 0:
            lead = g[:ki + 1]                      
            for u in rest:
                out.append((u[0], lead + [u]))        # mỗi Điểm = 1 chunk + dòng dẫn
        else:                                         # không có Khoản: cắt theo độ dài
            cur, n = [], 0
            for u in g:
                if cur and n + len(u[1]) > MAX:
                    out.append((cur[0][0], cur)); cur, n = [], 0
                cur.append(u); n += len(u[1])
            out.append((cur[0][0], cur))
    return out

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
in_dir = os.path.join(root, "data", "parsed")

with open(os.path.join(root, "data", "chunks.jsonl"), "w", encoding="utf-8") as out:
    for file in sorted(os.listdir(in_dir)):
        if not file.endswith(".md"):
            continue
        doc = file[:-3]
        mp = os.path.join(in_dir, doc + ".json")
        meta = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else {}
        with open(os.path.join(in_dir, file), encoding="utf-8") as f:
            md = f.read()

        secs, path, buf = [], [], []
        for l in md.splitlines():
            m = S.match(l)
            if m:
                secs.append((path, buf))
                buf = []
                lv = len(m[1])
                path = [x for x in path if x[0] < lv] + [(lv, m[2].strip())]
            else:
                buf.append(l)
        secs.append((path, buf))

        arts = {}
        for path, buf in secs:
            if not path or path[-1][0] != 6 or not (m := ART.match(path[-1][1])):
                continue
            blocks = [b.strip() for b in re.split(r'\n\s*\n', "\n".join(buf)) if b.strip()]
            if not blocks:
                continue
            aid = f"{doc}:D{m[1]}"
            arts[aid] = arts.get(aid, 0) + 1
            if arts[aid] > 1:           # Điều trùng số (vd văn bản đính kèm)
                aid += f"~{arts[aid]}"
            p = " > ".join(t for _, t in path)
            for cid, piece in pack(label(aid, blocks)):
                body = "\n".join(u[1] for u in piece)
                out.write(json.dumps({
                    **meta,
                    "id": cid, "doc": doc, "path": p, "content": body,
                    "text": f"{p}\n{body}",
                    "units": [{"id": u[0], "text": u[1]} for u in piece],
                }, ensure_ascii=False) + "\n")