# -*- coding: utf-8 -*-
"""대교협 「2028학년도 권역별 대학별 권장과목(반영과목)」 xlsx → univ_recommend_2028.json

입력:  2028_권역별_대학별_권장과목_대교협.xlsx (Sheet1)
       - 어디가 대입정보자료실 prtlBbsId=26634 첨부. 2025-09-30 각 대학 발표를 대교협이 정리.
       - "필수 이수 기준이 아닌 참고자료"로 명시됨 → UI에서 반드시 병기.
출력:  univ_recommend_2028.json
       {
         "meta": {...},
         "entries": [{univ, area, region, college, unit, core[], core_raw, rec[], rec_raw, note}],
         "by_major": {정규화학과명: [entry_idx...]},   # recommender.norm_major 기준
         "by_subject": {정규화과목명: {"name": 표시명, "core": n, "rec": n}}
       }
과목 정규화: recommender._norm_subject + vocab(154) 대조 — 어휘에 없는 토큰은 raw로만 보존.
실행: python build_univ_recommend.py
"""
import json
import re
import sys

import pandas as pd

sys.path.insert(0, ".")
import recommender as R  # noqa: E402  (_norm_subject·norm_major·VOCAB_META 재사용)

SRC = "2028_권역별_대학별_권장과목_대교협.xlsx"
OUT = "univ_recommend_2028.json"

# 과목 리스트 구분자: 콤마·줄바꿈·'또는'. '/'는 과목명 일부(제2외국어/한문)라 분리 금지.
SPLIT = re.compile(r"[,\n]|또는")
# 자유서술(과목 아님) 판정 보조: '이수/선택/고려' 등이 든 긴 문장
FREE_HINT = re.compile(r"이수|고려|선택하여|자율적|상관없이|구분 없이")


def _clean(s):
    return re.sub(r"\s+", " ", str(s)).strip()


def parse_subjects(raw):
    """셀 텍스트 → (vocab 매칭 과목 리스트, 원문). '-'·NaN·자유서술은 과목 0개."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return [], ""
    text = str(raw).strip()
    if not text or text == "-":
        return [], ""
    subs = []
    for tok in SPLIT.split(text):
        tok = _clean(tok)
        tok = re.sub(r"\[.*?\]|\(.*?\)", "", tok).strip()  # 괄호 주석 제거
        if not tok or len(tok) > 25:
            continue
        key = R.norm_subject(tok)
        meta = R.VOCAB_META.get(key)
        if meta:
            subs.append(meta["name"])  # vocab 표기로 통일
    # 중복 제거(순서 유지)
    return list(dict.fromkeys(subs)), _clean(text)


def main():
    df = pd.read_excel(SRC, sheet_name="Sheet1", header=None, skiprows=4)
    df.columns = ["권역", "지역", "대학명", "모집단위", "학과", "핵심과목", "권장과목", "비고"]
    # 병합 셀 복원: 권역·지역·대학명·모집단위(단과대)는 아래로 채움
    df[["권역", "지역", "대학명", "모집단위"]] = df[["권역", "지역", "대학명", "모집단위"]].ffill()
    df = df.dropna(subset=["대학명"])

    entries, by_major, by_subject = [], {}, {}
    for _, r in df.iterrows():
        univ = _clean(r["대학명"])
        college = _clean(r["모집단위"]) if pd.notna(r["모집단위"]) else ""
        unit = _clean(r["학과"]) if pd.notna(r["학과"]) else college
        if not unit:
            continue
        core, core_raw = parse_subjects(r["핵심과목"])
        rec, rec_raw = parse_subjects(r["권장과목"])
        if not core_raw and not rec_raw:
            continue
        idx = len(entries)
        entries.append({
            "univ": univ, "area": _clean(r["권역"]), "region": _clean(r["지역"]),
            "college": college if college != unit else "",
            "unit": unit, "core": core, "core_raw": core_raw,
            "rec": rec, "rec_raw": rec_raw,
            "note": _clean(r["비고"]) if pd.notna(r["비고"]) and _clean(r["비고"]) != "-" else "",
        })
        # 학과명 역인덱스 — 학과 셀과 단과대 셀 둘 다 등록(조회 히트율↑)
        for name in {unit, college} - {""}:
            key = R.norm_major(name)
            if key:
                by_major.setdefault(key, []).append(idx)
        for s in core:
            d = by_subject.setdefault(R.norm_subject(s), {"name": s, "core": 0, "rec": 0})
            d["core"] += 1
        for s in rec:
            d = by_subject.setdefault(R.norm_subject(s), {"name": s, "core": 0, "rec": 0})
            d["rec"] += 1

    out = {
        "meta": {
            "source": "대교협 「2028학년도 권역별 대학별 권장과목(반영과목)」 (대입정보포털 어디가, prtlBbsId=26634)",
            "basis": "2025-09-30 각 대학 발표 자료를 대교협이 요약·정리 — 필수 이수 기준이 아닌 참고자료",
            "n_univs": len({e["univ"] for e in entries}),
            "n_entries": len(entries),
            "n_major_keys": len(by_major),
        },
        "entries": entries,
        "by_major": by_major,
        "by_subject": by_subject,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"OK: {OUT} — 대학 {out['meta']['n_univs']}개, 항목 {len(entries)}행, "
          f"학과키 {len(by_major)}개, 과목 {len(by_subject)}개")


if __name__ == "__main__":
    main()
