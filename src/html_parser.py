from datasets import load_dataset
from bs4 import BeautifulSoup
import re, os

TARGETS = ["45/2019/QH14"]
HEAD = {"prov-part": 2, "prov-chapter": 3, "prov-section": 4, "prov-subsection": 5, "prov-article": 6}
NUM_ONLY = re.compile(r"^(Phần|Chương|Mục|Tiểu\s+mục)\s+(thứ\s+\S+|[IVXLC]+|\d+)\.?\s*$", re.I)
GUESS = [
    (re.compile(r"^Phần\s+(thứ\s+\S+|[IVXLC]+)\b", re.I), "prov-part"),
    (re.compile(r"^Chương\s+[IVXLC]+\b", re.I), "prov-chapter"),
    (re.compile(r"^Mục\s+\d+\b", re.I), "prov-section"),
    (re.compile(r"^Tiểu\s+mục\s+\d+\b", re.I), "prov-subsection"),
    (re.compile(r"^Điều\s+\d+[a-zđ]?\s*\.", re.I), "prov-article"),
]

ds = load_dataset("th1nhng0/vietnamese-legal-documents", "content")['data']
meta = load_dataset("th1nhng0/vietnamese-legal-documents", "metadata")['data']

def prov_class(p):
    for i in p.get('class') or []:
        if i.startswith('prov-'):
            return i
    return None

def guess_class(t):
    for rx, c in GUESS:
        if rx.match(t):
            return c
    return "prov-content"

def head_class(lines):
    m = re.match(r"^(#+)\s", lines[-1])
    return {v: k for k, v in HEAD.items()}.get(len(m.group(1))) if m else None

found = {}
for r in meta:
    s = r['so_ky_hieu']
    if s in TARGETS and s not in found and not re.search(r'[a-z]+', r['id']):
        found[s] = r
ids = {r['id']: s for s, r in found.items()}
print("missing:", set(TARGETS) - set(found))

os.makedirs("data/parsed", exist_ok=True)
for row in ds.filter(lambda x: x['id'] in ids):
    s = ids[row['id']]
    lines = [f"# {s} {found[s]['title']}"]
    last_num_only = False
    stats = {"paragraphs": 0, "kept": 0, "skipped_no_class": 0, "articles": 0, "mode": ""}

    ps = BeautifulSoup(row['content_html'], 'html.parser').find_all('p')
    use_guess = not any(prov_class(p) for p in ps)
    stats["mode"] = "guess" if use_guess else "prov"

    for p in ps:
        stats["paragraphs"] += 1
        t = p.get_text(" ", strip=True)
        if not t:
            continue
        c = guess_class(t) if use_guess else prov_class(p)
        if not c:
            stats["skipped_no_class"] += 1
            continue
        stats["kept"] += 1
        is_head = c in HEAD

        if last_num_only and (not is_head or c == head_class(lines)) and c != "prov-article":
            lines[-1] += f". {t}"
            last_num_only = False
            continue

        if is_head:
            lines.append('#' * HEAD[c] + ' ' + t)
            last_num_only = c != "prov-article" and bool(NUM_ONLY.match(t))
            stats["articles"] += c == "prov-article"
        else:
            lines.append(t)
            last_num_only = False

    with open(f"data/parsed/{s.replace('/', '-')}.md", "w", encoding="utf-8") as f:
        f.write('\n\n'.join(lines))
    print(s, stats)