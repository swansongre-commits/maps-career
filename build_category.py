# -*- coding: utf-8 -*-
"""
학과 카테고리 트리 생성기
입력 : 설치모집단위 리스트.xlsx (sheet=univ_major) — K~M열 대분류/중분류/소분류 + 모집단위
       majors_keywords.json — 우리가 보유한 학과명
출력 : mapping_category.json
       {"tree": {대분류: {중분류: {소분류: [우리 학과명...]}}},
        "stats": {...}}

매칭: norm_major(모집단위)  ==  norm_major(우리 학과명)  기준.
학과별 정보 탭의 대>중>소 캐스케이드 필터에 사용.
실행: python build_category.py
"""
import re
import json
import pandas as pd

SRC = "설치모집단위 리스트.xlsx"
OUT = "mapping_category.json"
COLS = ["연번", "서비스구분", "지역", "대학명", "대학코드", "세부전형",
        "전형구분", "전형중심", "전형요소", "계열", "대분류", "중분류",
        "소분류", "모집단위", "전공", "인원"]

_SUFFIX = re.compile(r"(학과|학부|학전공|전공|과|학)$")
_PAREN = re.compile(r"[\(\（].*?[\)\）]")
_NONWORD = re.compile(r"[^가-힣A-Za-z0-9]")


def norm_major(s):
    s = str(s).strip()
    s = _PAREN.sub("", s)
    s = _NONWORD.sub("", s)
    prev = None
    while prev != s:
        prev = s
        s = _SUFFIX.sub("", s)
        if len(s) <= 1:
            return prev
    return s or prev


def clean(x):
    x = str(x).strip()
    return "" if x in ("", "nan", "None") else x


def main():
    df = pd.read_excel(SRC, sheet_name="univ_major")
    df = df.iloc[1:].copy()
    df.columns = COLS
    df = df.dropna(subset=["모집단위"])

    # 우리 학과명 → 정규형 인덱스
    majors = json.load(open("majors_keywords.json", encoding="utf-8"))
    our_by_norm = {}
    for d in majors:
        our_by_norm.setdefault(norm_major(d["name"]), set()).add(d["name"])
    our_names = {d["name"] for d in majors}

    tree = {}
    matched_names = set()
    for _, r in df.iterrows():
        dae, jung, so = clean(r["대분류"]), clean(r["중분류"]), clean(r["소분류"])
        if not (dae and jung):
            continue
        so = so or "(기타)"
        key = norm_major(r["모집단위"])
        names = our_by_norm.get(key)
        if not names:
            continue
        for nm in names:
            tree.setdefault(dae, {}).setdefault(jung, {}).setdefault(so, set()).add(nm)
            matched_names.add(nm)

    # set → 정렬 리스트
    tree_out = {}
    for dae in sorted(tree):
        tree_out[dae] = {}
        for jung in sorted(tree[dae]):
            tree_out[dae][jung] = {so: sorted(tree[dae][jung][so])
                                   for so in sorted(tree[dae][jung])}

    stats = {
        "n_major_total": len(our_names),
        "n_major_matched": len(matched_names),
        "coverage": round(len(matched_names) / max(1, len(our_names)), 3),
        "n_dae": len(tree_out),
        "unmatched_sample": sorted(our_names - matched_names)[:30],
    }
    json.dump({"tree": tree_out, "stats": stats},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"대분류 {stats['n_dae']}개 | 매칭 학과 {stats['n_major_matched']}/"
          f"{stats['n_major_total']} ({stats['coverage']*100:.1f}%) -> {OUT}")
    print("미매칭 예시:", stats["unmatched_sample"][:12])


if __name__ == "__main__":
    main()
