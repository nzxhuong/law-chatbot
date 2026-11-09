import os, re
from google import genai
from rerank import rerank, client

gemini = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL = "gemini-3.5-flash-lite"
THRESH = 0.3
REFUSE = "Không tìm thấy căn cứ đủ để trả lời."
_UNIT = re.compile(r":(?:PL(\d+)\.)?D(\w+?)(?:\.K(\w+?))?(?:\.(\w+?))?(?:~\d+)?$")
DIACRITIC_PROMPT = ("Thêm dấu tiếng Việt cho câu hỏi pháp luật sau. Giữ nguyên nghĩa và thứ tự từ. "
                    "Chỉ trả về đúng một dòng là câu đã thêm dấu.")
SYS = (f"""Bạn là trợ lý tra cứu pháp luật Việt Nam. Chỉ trả lời dựa trên phần NGỮ CẢNH.

Quy tắc bắt buộc:
1. Không dùng kiến thức ngoài ngữ cảnh. Không tự thêm con số, thời hạn, mức phạt.
2. Không viết mã nào không xuất hiện trong ngữ cảnh.
4. Nếu ngữ cảnh không đủ để trả lời, nói rõ "{REFUSE}" và nêu phần còn thiếu.
5. Trả lời ngắn gọn bằng tiếng Việt, gạch đầu dòng. Không lặp lại nguyên văn điều luật dài.
6. Mỗi ý khẳng định phải kết thúc bằng mã trích dẫn dạng [mã], sao chép NGUYÊN VĂN từ ngữ cảnh,
   ví dụ [45-2019-QH14:D35.K1.a]. Chọn mã cụ thể nhất có thể (Điểm > Khoản > Điều)""")

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

def answer(q, history):
    sq = rewrite(q, history)
    hits = rerank(sq, k=5)
    if not hits or hits[0][0] < THRESH:
        return REFUSE, hits
    ctx = "\n\n".join(f'[{i}] ({p["doc"]} | {p["path"]})\n{p["content"]}'
                      for i, (_, p) in enumerate(hits, 1))
    msgs = [{"role": "system", "content": SYS}] + history[-6:] + [
        {"role": "user", "content": f"Sources:\n{ctx}\n\nQuestion: {q}"}]
    return llm(msgs), hits
def unit_label(unit_id: str) -> str:
    """45-2019-QH14:D35.K2.b."""
    m = _UNIT.search(unit_id)
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
    return " ".join(parts)

if __name__ == "__main__":
    history = []
    try:
        while True:
            q = input("\nq> ").strip()
            if not q:
                break
            a, hits = answer(q, history)
            print("\n" + a)
            for i, (s, p) in enumerate(hits, 1):
                print(f'  [{i}] {unit_label(p["id"])}')
            history += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
    finally:
        client.close()