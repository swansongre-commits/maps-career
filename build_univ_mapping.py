# -*- coding: utf-8 -*-
"""
설치대학 매핑 생성기
입력 : 설치모집단위 리스트.xlsx (sheet=univ_major)
출력 : mapping_univ.json

각 (정규화된 학과명) → 그 학과를 설치한 대학 목록.
대학별로 (지역·대학명·전형목록·모집인원합·전공분류)을 집계한다.

추천기(recommender.major_extra)는 careernet 학과명을 같은 방식으로 정규화해
이 사전을 조회한다. 4년제 모집단위 기준이라 전문대·교양학부는 매칭 안 될 수 있음
(그 경우 mapping_major.csv 개설대학으로 폴백).

실행: python build_univ_mapping.py
"""
import re
import json
import pandas as pd

SRC = "설치모집단위 리스트.xlsx"
OUT = "mapping_univ.json"

COLS = ["연번", "서비스구분", "지역", "대학명", "대학코드", "세부전형",
        "전형구분", "전형중심", "전형요소", "계열", "대분류", "중분류",
        "소분류", "모집단위", "전공", "인원"]

# 학과명 정규화: 흔한 접미사 절단(질의/색인 동일 적용으로 일관 매칭)
_SUFFIX = re.compile(r"(학과|학부|학전공|전공|과|학)$")
_PAREN = re.compile(r"[\(\（].*?[\)\）]")
_NONWORD = re.compile(r"[^가-힣A-Za-z0-9]")


def norm_major(s: str) -> str:
    s = str(s).strip()
    s = _PAREN.sub("", s)          # 괄호주석 제거: 간호학과(야간)→간호학과
    s = _NONWORD.sub("", s)        # 공백·기호 제거
    prev = None
    while prev != s:               # 접미사 반복 절단: 공학전공→공학→...
        prev = s
        s = _SUFFIX.sub("", s)
        if len(s) <= 1:            # 과도 절단 방지
            return prev
    return s or prev


def to_int(x):
    try:
        return int(float(str(x).replace(",", "").strip()))
    except Exception:
        return 0


def main():
    df = pd.read_excel(SRC, sheet_name="univ_major")
    df = df.iloc[1:].copy()        # 중복 헤더행 제거
    df.columns = COLS
    df = df.dropna(subset=["대학명", "모집단위"])

    # 정규화 키
    df["_key"] = df["모집단위"].map(norm_major)

    index = {}
    for key, g in df.groupby("_key"):
        if not key:
            continue
        univs = {}
        names = set()
        for _, r in g.iterrows():
            names.add(str(r["모집단위"]))
            region = str(r["지역"]).strip()
            uni = str(r["대학명"]).strip()
            uk = (region, uni)
            slot = univs.setdefault(uk, {"지역": region, "대학명": uni,
                                          "전형": set(), "인원": 0, "분류": ""})
            jh = str(r["세부전형"]).strip()
            if jh and jh != "nan":
                slot["전형"].add(jh)
            slot["인원"] += to_int(r["인원"])
            if not slot["분류"]:
                cat = "/".join(str(r[c]).strip() for c in ["대분류", "중분류", "소분류"]
                               if str(r[c]).strip() and str(r[c]).strip() != "nan")
                slot["분류"] = cat
        uni_list = []
        for slot in univs.values():
            slot["전형"] = sorted(slot["전형"])
            uni_list.append(slot)
        # 지역→대학명 순 정렬
        uni_list.sort(key=lambda x: (x["지역"], x["대학명"]))
        index[key] = {
            "names": sorted(names),
            "univ_count": len(uni_list),
            "univs": uni_list,
        }

    json.dump(index, open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    total_univ = sum(v["univ_count"] for v in index.values())
    print(f"keys={len(index)}  univ_slots={total_univ}  -> {OUT}")


if __name__ == "__main__":
    main()
