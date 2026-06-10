"""
추천엔진 정렬용 '2022 선택과목 어휘' 사전 구축.
mapping_major.csv 의 '선택과목2022' 컬럼(일반/진로/융합 선택: ...)에서
과목명을 모아 vocab_2022.json 생성. 학교 교육과정 텍스트 매칭의 타깃 집합.
"""
import sys, re, csv, json, collections
sys.stdout.reconfigure(encoding='utf-8')

ROMAN = {"Ⅰ": "I", "Ⅱ": "II", "Ⅲ": "III", "Ⅳ": "IV"}


def normalize(s):
    s = s.strip()
    for k, v in ROMAN.items():
        s = s.replace(k, v)
    s = re.sub(r"\s+", " ", s)
    return s


def parse_cell(cell):
    """'일반 선택: a, b 등 | 진로 선택: c 등 | 융합 선택: d' -> {type:[subjects]}"""
    out = collections.defaultdict(list)
    if not cell:
        return out
    for seg in cell.split("|"):
        m = re.match(r"\s*(일반|진로|융합)\s*선택\s*[:：]\s*(.*)", seg)
        if not m:
            continue
        typ, body = m.group(1), m.group(2)
        body = re.sub(r"\s*등\s*$", "", body.strip())
        for tok in re.split(r"[,，]", body):
            t = normalize(tok)
            t = re.sub(r"\s*등$", "", t).strip()
            if t and re.search(r"[가-힣]", t) and 2 <= len(t) <= 25:
                out[typ].append(t)
    return out


def main():
    rows = list(csv.DictReader(open("mapping_major.csv", encoding="utf-8-sig")))
    vocab = collections.defaultdict(collections.Counter)  # subj -> {type:count}
    for r in rows:
        for typ, subs in parse_cell(r.get("선택과목2022", "")).items():
            for s in subs:
                vocab[s][typ] += 1

    # 정리: 명백한 노이즈/오타 토막 제거
    out = {}
    for subj, types in vocab.items():
        if re.search(r"^(또는|및|또|프|외)$", subj):
            continue
        out[subj] = {"type": types.most_common(1)[0][0],
                     "freq": sum(types.values())}
    out = dict(sorted(out.items(), key=lambda kv: -kv[1]["freq"]))
    json.dump(out, open("vocab_2022.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("vocab_2022.json:", len(out), "과목")
    bt = collections.Counter(v["type"] for v in out.values())
    print("유형분포:", dict(bt))
    print("\n상위 40 (빈도순):")
    for k in list(out)[:40]:
        print(f"  {k} [{out[k]['type']}] x{out[k]['freq']}")


if __name__ == "__main__":
    main()
