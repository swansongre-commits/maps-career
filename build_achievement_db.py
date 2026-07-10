# -*- coding: utf-8 -*-
"""학교알리미 「교과별(과목별) 학업성취 사항」 수집 CSV → achievement.db (SQLite)

입력:  achievement_data/achievement_all_2026_r1.csv (Codex 수집, 2026년 1차 공시)
       - 2,418교 × 과목별 학기 평균·성취도(A~E) 분포. shl_idf_cd는 schools.db와 동일 체계.
출력:  achievement.db
       - school_achievement(shl_idf_cd, academic_year, grade, semester,
                            subject_name, units, average, a~e_pct, subj_base)
       - meta(key, value)

정규화: subj_base = _norm_subject 후 꼬리 로마숫자·숫자 제거.
  → 2022개정('미적분Ⅰ')과 2015개정('미적분') 실적을 같은 계열로 묶어 조회하되,
    화면에는 공시 과목명을 그대로 표기(참고용임을 병기)한다.
용량 관리: 서비스 어휘(vocab 154 + 공통과목)와 베이스가 겹치는 행만 적재.
실행: python build_achievement_db.py
"""
import os
import re
import sqlite3
import sys
from datetime import datetime

import pandas as pd

sys.path.insert(0, ".")
import recommender as R  # noqa: E402

SRC = "achievement_data/achievement_all_2026_r1.csv"
OUT = "achievement.db"

_TAIL = re.compile(r"[IVX0-9]+$")


def subj_base(name):
    """정규형에서 꼬리 로마숫자·숫자 제거 — 교육과정 개정판 간 계열 매칭용."""
    return _TAIL.sub("", R.norm_subject(str(name)))


def main():
    df = pd.read_csv(SRC)
    n_raw = len(df)
    df = df.drop_duplicates(
        subset=["shl_idf_cd", "academic_year", "grade", "semester",
                "subject_code", "track", "category"])
    df = df[df["has_data"] == True]  # noqa: E712

    # 서비스 어휘와 계열이 겹치는 행만 적재(전문교과 등 미사용 행 제외 → DB 경량화)
    vocab_bases = {subj_base(m["name"]) for m in R.VOCAB_META.values()}
    common_bases = {subj_base(s) for s in
                    ("공통국어", "공통수학", "공통영어", "통합사회", "통합과학",
                     "한국사", "과학탐구실험")}
    keep_bases = {b for b in (vocab_bases | common_bases) if b}
    df["subj_base"] = df["subject_name"].map(subj_base)
    df = df[df["subj_base"].isin(keep_bases)]

    cols = ["shl_idf_cd", "academic_year", "grade", "semester", "subject_name",
            "units", "average", "a_pct", "b_pct", "c_pct", "d_pct", "e_pct",
            "subj_base"]
    out = df[cols].copy()

    if os.path.exists(OUT):
        os.remove(OUT)
    con = sqlite3.connect(OUT)
    out.to_sql("school_achievement", con, index=False)
    con.execute("CREATE INDEX idx_sch_subj ON school_achievement(shl_idf_cd, subj_base)")
    con.execute("CREATE TABLE meta (key TEXT, value TEXT)")
    con.executemany("INSERT INTO meta VALUES (?, ?)", [
        ("source", "학교알리미 교과별(과목별) 학업성취 사항 — 2026년 1차 공시"),
        ("built", datetime.now().strftime("%Y-%m-%d %H:%M")),
        ("n_rows_raw", str(n_raw)),
        ("n_rows_kept", str(len(out))),
        ("n_schools", str(out["shl_idf_cd"].nunique())),
    ])
    con.commit()
    con.close()
    size_mb = os.path.getsize(OUT) / 1024 / 1024
    print(f"OK: {OUT} — {len(out):,}행(원본 {n_raw:,}), "
          f"학교 {out['shl_idf_cd'].nunique():,}교, {size_mb:.1f}MB")


if __name__ == "__main__":
    main()
