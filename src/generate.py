import os, re
from dataclasses import dataclass
from google import genai
from rerank import rerank, client
from expand import expand, amenders, amender_units

gemini = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL = "gemini-3.5-flash-lite"
THRESH = 0.3
REFUSE = "Không tìm thấy căn cứ đủ để trả lời."
_UNIT = re.compile(r":(?:PL(\d+)\.)?D(\w+?)(?:\.K(\w+?))?(?:\.(\w+?))?(?:~\d+)?$")
REL = {"exception": "ngoại lệ", "ref": "dẫn chiếu", "amends": "điều khoản bị văn bản này sửa đổi"}
OP = {"add": "BỔ SUNG", "modify": "SỬA ĐỔI", "repeal": "BÃI BỎ"}
_BRACKET = re.compile(r"\[([^\[\]]+)\]")
_LIST_MARK = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s*")
DIACRITIC_PROMPT = ("Thêm dấu tiếng Việt cho câu hỏi pháp luật sau. Giữ nguyên nghĩa và thứ tự từ. "
                    "Chỉ trả về đúng một dòng là câu đã thêm dấu.")
SYS = (f"""Bạn là trợ lý tra cứu pháp luật Việt Nam. Chỉ trả lời dựa trên phần NGỮ CẢNH.

Quy tắc bắt buộc:
1. Không dùng kiến thức ngoài ngữ cảnh. Không tự thêm con số, thời hạn, mức phạt.
2. Không viết mã nào không xuất hiện trong ngữ cảnh.
3. Nếu ngữ cảnh không đủ để trả lời, nói rõ "{REFUSE}" và nêu phần còn thiếu.
4. Trả lời ngắn gọn bằng tiếng Việt, gạch đầu dòng. Không lặp lại nguyên văn điều luật dài.
5. Mỗi ý khẳng định phải kết thúc bằng mã trích dẫn dạng [mã], sao chép NGUYÊN VĂN từ ngữ cảnh,
   ví dụ [45-2019-QH14:D35.K1.a]. Chọn mã cụ thể nhất có thể (Điểm > Khoản > Điều)
6. Dòng "↳ ĐÃ BỊ ... bởi" ngay dưới một điều khoản là văn bản sửa đổi điều khoản đó. Nội dung MỚI (trong dấu “ ”) thay cho phần gốc tương ứng: nếu khác nhau, theo nội dung mới và nói rõ phần gốc đã được sửa.
   Nếu là BÃI BỎ thì phần gốc không còn hiệu lực; nếu là BỔ SUNG thì nội dung mới được thêm vào, không thay phần gốc.
7. Phần THAM CHIẾU (nếu có) là điều khoản được dẫn chiếu: chỉ dùng để bổ sung, không thay phần chính. NHÃN: ngoại lệ là trường hợp loại trừ của quy định chính: nêu khi liên quan.""")


@dataclass
class Verified:
    text: str
    sources: list[dict]
    invalid: list[str]
    uncited: list[str]
    number_warnings: list[dict]
    raw: str = ""


def llm(messages):
    system = "\n".join(m["content"] for m in messages if m["role"] == "system")
    rest = [m for m in messages if m["role"] != "system"]
    text = "\n\n".join(f'{m["role"]}: {m["content"]}' for m in rest)
    kw = {"system_instruction": system} if system else {}
    r = gemini.interactions.create(model=MODEL, input=text, **kw)
    return (r.output_text or "").strip()


def rewrite(q, history):
    if not history:
        return q
    h = "\n".join(f'{m["role"]}: {m["content"]}' for m in history[-6:])
    return llm([{"role": "user", "content":
        f"Chat history:\n{h}\n\n{DIACRITIC_PROMPT} "
        f"Output only the query.\nQuestion: {q}"}])


def unit_label(unit_id: str) -> str:
    """45-2019-QH14:D35.K2.b -> Điểm b Khoản 2 Điều 35 45/2019/QH14"""
    m = _UNIT.search(unit_id)
    doc = unit_id.split(":")[0].replace("-", "/")
    parts: list[str] = []
    if m:
        pl, dieu, khoan, diem = m.groups()
        if diem:
            parts.append(f"Điểm {diem}")
        if khoan:
            parts.append(f"Khoản {khoan}")
        parts.append(f"Điều {dieu}")
        if pl:
            parts.append("(văn bản ban hành kèm theo)")
    else:
        parts.append(unit_id)
    return " ".join(parts) + f" {doc}"


def _subtree_text(uid, units, sep=" "):
    return sep.join(u["text"] for k, u in units.items() if k == uid or k.startswith(uid + "."))


def verify_citations(answer: str, units: dict[str, dict]) -> Verified:
    order: dict[str, int] = {}
    invalid: list[str] = []
    uncited: list[str] = []
    num_warn: list[dict] = []
    out_lines: list[str] = []

    for line in answer.splitlines():
        line_valid: list[str] = []

        def repl(m: re.Match) -> str:
            ids = [x.strip() for x in re.split(r"[;,]", m.group(1)) if x.strip()]
            nums = []
            for i in ids:
                if i in units:
                    order.setdefault(i, len(order) + 1)
                    line_valid.append(i)
                    if order[i] not in nums:
                        nums.append(order[i])
                else:
                    invalid.append(i)
            return "[" + ", ".join(map(str, nums)) + "]" if nums else ""

        new = re.sub(r"\s+$", "", _BRACKET.sub(repl, line))
        out_lines.append(new)
        plain = _LIST_MARK.sub("", _BRACKET.sub("", line)).strip()
        if len(plain) < 20 or plain.endswith(":"):
            continue
        if not line_valid:
            uncited.append(plain)
            continue
        support = " ".join(f"{units[c]['label']} {_subtree_text(c, units)}" for c in line_valid)
        have = set(re.findall(r"\d+", support))
        missing = sorted({n for n in re.findall(r"\d+", plain) if n not in have})
        if missing:
            num_warn.append({"line": plain, "numbers": missing})

    sources = [{"n": n, "id": uid, "label": units[uid]["label"],
                "text": _subtree_text(uid, units, "\n"),
                "tinh_trang": units[uid]["hit"].get("tinh_trang_hieu_luc"),
                "so_ky_hieu": units[uid]["hit"].get("so_ky_hieu")} for uid, n in order.items()]
    return Verified("\n".join(out_lines), sources, list(dict.fromkeys(invalid)),
                    uncited, num_warn, answer)


def _clip(t, n=1200):
    return t if len(t) <= n else t[:n] + " …"


def build_ctx(hits):
    """Mỗi hit kèm ngay dưới nó các văn bản sửa đổi (mỗi cặp chunk+đơn vị chỉ in 1 lần)."""
    shown, parts, au = set(), [], []
    for _, p in hits:
        s = f'({p["doc"]} | {p["path"]})\n' + "\n".join(f'[{u["id"]}] {u["text"]}' for u in p["units"])
        for a, ch in amenders(p):
            if (ch["id"], a["src_unit"]) in shown:
                continue
            shown.add((ch["id"], a["src_unit"]))
            us = amender_units(ch, a["src_unit"])
            s += f'\n↳ ĐÃ BỊ {OP.get(a["op"], a["op"])} bởi {unit_label(a["src_unit"])}:\n' + \
                 "\n".join(f'[{u["id"]}] {_clip(u["text"])}' for u in us)
            au += [(ch, u) for u in us]
        parts.append(s)
    return "\n\n".join(parts), au


def answer(q, history):
    sq = rewrite(q, history)
    hits = rerank(sq, k=5)
    if not hits or hits[0][0] < THRESH:
        return Verified(REFUSE, [], [], [], [], REFUSE), hits

    ctx, au = build_ctx(hits)
    extra = expand(hits)
    if extra:
        ctx += "\n\nTHAM CHIẾU:\n" + "\n\n".join(
            f'({p["doc"]} | {p["path"]}) | NHÃN: {REL.get(rel, rel)}\n'
            + "\n".join(f'[{u["id"]}] {u["text"]}' for u in p["units"])
            for p, rel, _ in extra)
    msgs = [{"role": "system", "content": SYS}] + history[-6:] + [
        {"role": "user", "content": f"Sources:\n{ctx}\n\nQuestion: {q}"}]
    raw = llm(msgs)

    units = {u["id"]: {"label": unit_label(u["id"]), "text": u["text"], "hit": p}
             for p in [p for p, _, _ in extra] + [p for _, p in hits] for u in p["units"]}
    for ch, u in au:                       # đơn vị văn bản sửa đổi cũng được phép trích dẫn
        units.setdefault(u["id"], {"label": unit_label(u["id"]), "text": u["text"], "hit": ch})
    return verify_citations(raw, units), hits


if __name__ == "__main__":
    history = []
    try:
        while True:
            q = input("\nq> ").strip()
            if not q:
                break
            v, hits = answer(q, history)
            print("\n" + v.text)
            for s in v.sources:
                print(f'  [{s["n"]}] {s["label"]}')
            if v.invalid:
                print("  invalid:", v.invalid)
            if v.uncited:
                print("  uncited:", v.uncited)
            if v.number_warnings:
                print("  numbers:", v.number_warnings)
            history += [{"role": "user", "content": q}, {"role": "assistant", "content": v.raw}]
    finally:
        client.close()