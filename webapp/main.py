# -*- coding: utf-8 -*-
"""
과목선택 내비게이터 — FastAPI 백엔드 (자체 서비스, v1.1 화면설계 기준)

원칙:
  - recommender.py를 그대로 재사용(♻️). 추천 로직·데이터 파일은 절대 수정하지 않는다.
  - 신규 데이터 수집 없음. 서버측 개인정보 저장 없음(계정·DB write 전무) — 학생 상태는
    브라우저(localStorage)와 공유 링크(URL 직렬화, S7)에만 존재한다.
  - 고3 미지원(코호트 불일치, v1.1 §0). 학년은 고1·고2만 노출.
"""
import os
import sys
import re

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import recommender as rec  # noqa: E402  (ROOT를 sys.path에 넣은 뒤 import)

try:
    import content_db
except Exception:
    content_db = None

app = FastAPI(title="과목선택 내비게이터 API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# ──────────────────────────────────────────────────────────────────
# 대분류(갈래) 이모지 — mapping_category.json의 8개 대분류 고정 매핑
# ──────────────────────────────────────────────────────────────────
DAE_EMOJI = {
    "공학": "⚙️", "자연": "🧪", "의학": "🏥", "사회": "⚖️",
    "인문": "📚", "교육": "🍎", "예체능": "🎨", "공통": "🧭",
}


def _major_to_dae_index():
    """학과명 -> set(대분류명) 역인덱스 (mapping_category.tree 기반)."""
    idx = {}
    for dae, jungs in rec.CATEGORY_TREE.items():
        for jung, sos in jungs.items():
            for so, names in sos.items():
                for name in names:
                    idx.setdefault(name, set()).add(dae)
    return idx


MAJOR_TO_DAE = _major_to_dae_index()


def _reason_sentence(reasons, chip_mode=False):
    """매칭 근거 1건 -> 근거 문장. 쉬운말 경로 우선(학생 친화)."""
    if not reasons:
        return ""
    best = next((r for r in reasons if r.get("via") == "쉬운말"), reasons[0])
    term = best.get("term", "")
    if chip_mode:
        return f"'{term}' 칩을 골라서"
    return f"네가 '{term}'이라고 해서"


def _major_summary(name):
    if content_db is None:
        return ""
    try:
        info = content_db.major_intro(name)
        return (info or {}).get("summary", "") or ""
    except Exception:
        return ""


def _job_card_meta(name):
    if content_db is None:
        return {"emoji": "💼", "blurb": ""}
    try:
        meta = content_db.junior_job_meta().get(name)
        if meta:
            return {"emoji": meta.get("emoji", "💼"), "blurb": meta.get("blurb", "")}
    except Exception:
        pass
    return {"emoji": "💼", "blurb": ""}


# ──────────────────────────────────────────────────────────────────
# S0 — 학교 선택
# ──────────────────────────────────────────────────────────────────
@app.get("/api/sidos")
def api_sidos():
    return {"sidos": rec.school_sidos()}


@app.get("/api/guguns")
def api_guguns(sido: str = Query(...)):
    return {"guguns": rec.school_guguns(sido)}


@app.get("/api/schools")
def api_schools(sido: str = "", gugun: str = "", q: str = ""):
    rows = rec.school_options(sido or None, gugun or None)
    if q:
        qn = q.strip()
        rows = [r for r in rows if qn in r["school"]]
    return {"schools": rows[:200]}


# ──────────────────────────────────────────────────────────────────
# S1→S2 — 관심 입력 → 추천 (갈래 그룹핑 + 근거문장)
# ──────────────────────────────────────────────────────────────────
class RecommendIn(BaseModel):
    speech: str = ""
    chips: list[str] = []
    use_llm: bool = False


@app.post("/api/recommend")
def api_recommend(body: RecommendIn):
    chip_text = " ".join(body.chips or [])
    speech = f"{body.speech or ''} {chip_text}".strip()
    if not speech:
        raise HTTPException(400, "발화 또는 칩 중 하나는 필요해요")
    chip_only = not (body.speech or "").strip() and bool(body.chips)

    out = rec.recommend(speech, top_n=8, pair_k=5, use_llm=body.use_llm)

    # 학과 카드: 대분류별 그룹핑, 최대 3갈래
    dae_groups = {}  # dae -> list of major rows (already score-sorted)
    for m in out["majors"]:
        for dae in (MAJOR_TO_DAE.get(m["name"]) or {"기타"}):
            dae_groups.setdefault(dae, []).append(m)

    ordered_daes = sorted(
        dae_groups.keys(),
        key=lambda d: -max(m["score"] for m in dae_groups[d]),
    )[:3]

    categories = []
    for dae in ordered_daes:
        majors = dae_groups[dae][:3]
        categories.append({
            "dae": dae,
            "emoji": DAE_EMOJI.get(dae, "🧭"),
            "majors": [
                {
                    "name": m["name"],
                    "summary": _major_summary(m["name"]),
                    "reason": _reason_sentence(m["reasons"], chip_mode=chip_only),
                }
                for m in majors
            ],
        })

    jobs = [
        {
            "name": j["name"],
            **_job_card_meta(j["name"]),
            "reason": _reason_sentence(j["reasons"], chip_mode=chip_only),
        }
        for j in out["jobs"][:6]
    ]

    return {
        "tokens": out["tokens"],
        "excluded": out["excluded"],
        "categories": categories,
        "jobs": jobs,
        "pairs": out["pairs"],
        "meta": out["meta"],
        "empty": len(out["majors"]) == 0 and len(out["jobs"]) == 0,
    }


# ──────────────────────────────────────────────────────────────────
# S3 — 학과 상세: 권장과목·성취기준·설치대학
# ──────────────────────────────────────────────────────────────────
@app.get("/api/major/{name}")
def api_major_detail(name: str):
    row = rec.major_by_name(name)
    if not row:
        raise HTTPException(404, "학과를 찾을 수 없어요")
    subjects = rec.subjects_of_major(row)
    extra = rec.major_extra(row)
    return {
        "name": name,
        "summary": _major_summary(name),
        "subjects": subjects,
        "universities": extra["설치대학"],
        "related_jobs": rec.split_related_jobs(extra.get("관련직업", "")),
    }


@app.get("/api/major/{name}/achievement")
def api_achievement(name: str, subject: str = Query(...)):
    ach = rec.achievements_for_subject(subject)
    if not ach:
        return {"subject": subject, "items": []}
    items = (ach.get("items") or [])[:3]
    return {"subject": subject, "gwa": ach.get("gwa", ""),
            "items": [{"text": it.get("text", "")} for it in items]}


# ──────────────────────────────────────────────────────────────────
# S3.5 — 이수체크 시트: 과목 검색 폴백(전학생·미매칭 대비)
# ──────────────────────────────────────────────────────────────────
@app.get("/api/subjects/search")
def api_subject_search(q: str = ""):
    rows = rec.subject_list()
    if q:
        rows = [r for r in rows if q.strip() in r["name"]]
    return {"subjects": [{"name": r["name"], "type": r["type"]} for r in rows[:30]]}


# ──────────────────────────────────────────────────────────────────
# S4 — 우리 학교 개설여부
# ──────────────────────────────────────────────────────────────────
@app.get("/api/availability")
def api_availability(major: str = Query(...), school: str = Query(...)):
    row = rec.major_by_name(major)
    if not row:
        raise HTTPException(404, "학과를 찾을 수 없어요")
    avail = rec.subject_availability(row, school)
    return avail


# ──────────────────────────────────────────────────────────────────
# 정적 프론트엔드 서빙 (SPA — 모든 비-API 경로는 index.html)
# ──────────────────────────────────────────────────────────────────
app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


@app.get("/{full_path:path}")
def spa(full_path: str):
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
