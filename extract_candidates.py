# -*- coding: utf-8 -*-
"""
[Pass 1 보조] 불용어·합성어 후보 통계 추출
원본 CSV → kiwi 명사 → 명사 DF(불용어 후보) + 어절내 연속명사(합성어 후보)
사전(stopwords/compounds)을 보강하고 싶을 때 실행해 후보를 점검한다.

실행:  python extract_candidates.py
출력:  noun_df.json, comp_freq.json, comp_items.json
"""
import json
from collections import Counter, defaultdict
import pandas as pd
from kiwipiepy import Kiwi

kiwi = Kiwi(); NOUN = {"NNG", "NNP", "SL", "SH"}
JOB_TEXT = ["직업명", "관련직업명", "하는일", "핵심능력", "적성 및 흥미_적성",
            "적성 및 흥미_흥미", "태그", "직업탐색_진로 탐색 활동",
            "준비방법_정규교육과정", "준비방법_직업훈련", "준비방법_입직 및 취업방법"]
MAJ_TEXT = ["학과명", "학과개요_학과개요", "학과개요_학과특성", "학과개요_흥미와 적성",
            "학과개요_진로 탐색 활동", "학과개요_대학 주요 교과목",
            "학과개요_졸업 후 진출 분야", "학과개요_관련 직업"]

def build(path, idc, nc, cols, typ):
    df = pd.read_csv(path, encoding="utf-8-sig"); us = []
    for _, r in df.iterrows():
        parts = [str(r[c]).strip() for c in cols if isinstance(r.get(c), str) and r.get(c).strip()]
        us.append({"type": typ, "name": str(r[nc]), "text": "  ".join(parts)})
    return us

def analyze(w, cache):
    if w in cache: return cache[w]
    run, out = [], []
    for tk in kiwi.tokenize(w):
        if tk.tag in NOUN: run.append(tk.form)
        else:
            if run: out.append(run); run = []
    if run: out.append(run)
    nouns = [f for r in out for f in r]
    comps = ["".join(r) for r in out if len(r) >= 2]   # 어절내 2+명사 = 합성어 후보
    cache[w] = (nouns, comps); return cache[w]

def main():
    units = build("job_info.csv", "job_id", "직업명", JOB_TEXT, "직업") + \
            build("major_info.csv", "major_id", "학과명", MAJ_TEXT, "학과")
    cache = {}
    noun_df = defaultdict(set); comp_freq = Counter()
    comp_items = defaultdict(lambda: defaultdict(set))
    for u in units:
        for w in u["text"].split():
            nouns, comps = analyze(w, cache)
            for n in nouns: noun_df[n].add(u["name"])
            for c in comps:
                comp_freq[c] += 1; comp_items[c][u["type"]].add(u["name"])
    N = len(units)
    json.dump({n: len(s) for n, s in sorted(noun_df.items(), key=lambda x: -len(x[1]))},
              open("noun_df.json", "w"), ensure_ascii=False)
    json.dump(dict(comp_freq.most_common()), open("comp_freq.json", "w"), ensure_ascii=False)
    json.dump({c: {t: sorted(v)[:3] for t, v in d.items()} for c, d in comp_items.items()},
              open("comp_items.json", "w"), ensure_ascii=False)
    print(f"문서 {N} / 명사 {len(noun_df):,} / 합성어 후보 {len(comp_freq):,}")
    print("불용어 후보(DF상위):", [n for n, _ in sorted(noun_df.items(), key=lambda x: -len(x[1]))[:15]])
    print("합성어 후보(빈도상위):", [c for c, _ in comp_freq.most_common(15)])

if __name__ == "__main__":
    main()
