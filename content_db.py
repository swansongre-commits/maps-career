# -*- coding: utf-8 -*-
"""content.db 읽기 전용 접근자 — /1·/2 화면 '표시' 보강 전용.

원칙: 원래 추천 엔진(recommender.py·키워드 JSON 매칭)은 절대 변경하지 않는다.
이 모듈은 카드에 보여줄 보조 콘텐츠(학과 개요·연관직업·직업 이모지/한줄)만 제공한다.
content.db가 없으면 모든 함수가 안전하게 빈 값을 돌려준다(폴백).
"""
import functools
import os
import re
import sqlite3

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content.db")


def available():
    return os.path.exists(DB)


def _query(sql, args=()):
    if not available():
        return []
    con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def _norm(s):
    return re.sub(r"\s+", "", str(s or "").strip())


@functools.lru_cache(maxsize=1)
def junior_job_meta():
    """{job_name: {emoji, blurb, major}} — 주니어 카드용(content.db 정본)."""
    if not available():
        return {}
    out = {}
    for name, emoji, blurb in _query(
            "SELECT j.name, jc.emoji, jc.blurb FROM job j "
            "LEFT JOIN job_card jc ON jc.job_id=j.job_id"):
        out[name] = {"emoji": emoji or "💼", "blurb": blurb or "", "major": ""}
    # 대표 관련학과 1개(먼저 나온 것)
    for jname, mname in _query(
            "SELECT j.name, m.name FROM major_job mj "
            "JOIN job j ON j.job_id=mj.job_id JOIN major m ON m.major_id=mj.major_id"):
        if jname in out and not out[jname]["major"]:
            out[jname]["major"] = mname
    return out


@functools.lru_cache(maxsize=2048)
def major_intro(name):
    """학과명 → {summary, category, related_jobs:[...]} (고교 학과 상세 보강). 없으면 None."""
    if not available():
        return None
    row = _query("SELECT major_id, summary, category FROM major WHERE name=?", (name,))
    if not row:
        row = _query("SELECT major_id, summary, category FROM major WHERE name_norm=?", (_norm(name),))
    if not row:
        return None
    mid, summary, category = row[0]
    jobs = [r[0] for r in _query(
        "SELECT j.name FROM major_job mj JOIN job j ON j.job_id=mj.job_id "
        "WHERE mj.major_id=?", (mid,))]
    return {"summary": summary, "category": category, "related_jobs": jobs}
