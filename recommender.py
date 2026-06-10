# -*- coding: utf-8 -*-
"""
학과·직업 추천 엔진 (과목추천 제외 버전)

파이프라인:
  학생 발화 ─tokenize→ 토큰 ─매칭(공시키워드 + 쉬운말 동의어)→ 순위 점수합
            → 학과/직업 Top-N (설명가능) → 학과↔직업 연계 페어

핵심 데이터:
  - majors_keywords.json / jobs_keywords.json
      [{id, name, keywords:[{rank, official, easy:[...]}]}]
      · official = 커리어넷 공시 키워드(어려운 말)
      · easy     = 어린이/학생 수준 쉬운말 동의어 (rank별 쌍)
  - mapping_major.csv / mapping_job.csv  (설치대학·관련학과 등 부가정보)

UI(app.py)와 분리되어 있어 추후 FastAPI 엔드포인트로도 재사용 가능.
"""
import os
import re
import json
import csv

from tokenizer import tokenize

# ──────────────────────────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_RANK = 20  # 문서당 키워드 수(고정)

# 순위별 점수: 1위=20 … 20위=1 (높은 순위일수록 가중)
def rank_score(rank: int) -> int:
    return MAX_RANK + 1 - rank

# 부정 표현 단서 (해당 어절 이후 같은 절의 토큰을 추천에서 제외)
NEG_MARKERS = ("싫", "별로", "안좋", "안 좋", "흥미없", "흥미 없",
               "관심없", "관심 없", "재미없", "하기싫", "하기 싫",
               "말고", "빼고", "제외", "아니")
# 절 분리 기준
CLAUSE_SPLIT = re.compile(r"[,.!?\n·]|그리고|하지만|그런데|근데|다만|대신")


# ──────────────────────────────────────────────────────────────────
# 데이터 로드
# ──────────────────────────────────────────────────────────────────
def _path(name):
    return os.path.join(BASE_DIR, name)


def _load_mapping(fname, key_cols):
    """csv → {id: {col:value}}, {name: {col:value}} 둘 다 반환(조인 유연성)."""
    by_id, by_name = {}, {}
    p = _path(fname)
    if not os.path.exists(p):
        return by_id, by_name
    with open(p, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            row = {k: (v or "").strip() for k, v in row.items()}
            info = {c: row.get(c, "") for c in key_cols}
            if row.get("id"):
                by_id[str(row["id"])] = info
            if row.get("name"):
                by_name[row["name"]] = info
    return by_id, by_name


def _build_index(docs):
    """문서별 매칭 인덱스.
    official_terms: {공시키워드: rank}            (토큰 정확매칭)
    easy_terms:     {쉬운말: (rank, official)}    (토큰 매칭 + 부분문자열 매칭)
    officials:      set(공시키워드)               (연계페어 교집합용)
    """
    idx = []
    for d in docs:
        official_terms, easy_terms, officials = {}, {}, []
        for k in d.get("keywords", []):
            r = k["rank"]
            off = k["official"]
            officials.append(off)
            if off not in official_terms or r < official_terms[off]:
                official_terms[off] = r
            for e in k.get("easy", []):
                if not e or e == off:
                    continue
                if e not in easy_terms or r < easy_terms[e][0]:
                    easy_terms[e] = (r, off)
        idx.append({
            "id": str(d.get("id", "")),
            "name": d["name"],
            "official_terms": official_terms,
            "easy_terms": easy_terms,
            "officials": set(officials),
        })
    return idx


MAJORS = json.load(open(_path("majors_keywords.json"), encoding="utf-8"))
JOBS = json.load(open(_path("jobs_keywords.json"), encoding="utf-8"))
MAJOR_IDX = _build_index(MAJORS)
JOB_IDX = _build_index(JOBS)

MAJOR_MAP_ID, MAJOR_MAP_NAME = _load_mapping(
    "mapping_major.csv", ["개설대학", "선택과목2022", "관련직업", "관련자격"])
JOB_MAP_ID, JOB_MAP_NAME = _load_mapping(
    "mapping_job.csv", ["관련학과", "관련자격"])


# 설치대학 매핑(설치모집단위 리스트.xlsx → build_univ_mapping.py 산출물)
def _load_univ_mapping():
    p = _path("mapping_univ.json")
    if not os.path.exists(p):
        return {}
    return json.load(open(p, encoding="utf-8"))


UNIV_MAP = _load_univ_mapping()


# ──────────────────────────────────────────────────────────────────
# 고교 개설과목 (schools.db — 학교알리미 2025·2026 병합 SQLite, 폴백: 병합 JSON)
#   학생 고교(shl_idf_cd) × 추천 학과의 2022 선택과목 → 개설여부 판정
# ──────────────────────────────────────────────────────────────────
_ROMAN = {"Ⅰ": "I", "Ⅱ": "II", "Ⅲ": "III", "Ⅳ": "IV", "Ⅴ": "V"}


def _norm_subject(s: str) -> str:
    """과목명 정규화: 로마숫자→영문, 공백 제거. 어휘·DB·학과 3측 일관 매칭용."""
    s = str(s).strip()
    for a, b in _ROMAN.items():
        s = s.replace(a, b)
    return re.sub(r"\s+", "", s)


def _load_school_subjects_sqlite():
    """schools.db(SQLite) → (db {shl_idf_cd:{school,sido,gugun,subjects:{type:[...]},n_subj}},
                              offered {shl_idf_cd: 정규화 개설과목 set}).
    2025∪2026 병합본 기준. 개설과목 보유 학교(has_curriculum=1)만 노출."""
    import sqlite3
    p = _path("schools.db")
    if not os.path.exists(p):
        return None
    con = sqlite3.connect(p)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    db, offered = {}, {}
    # 개설과목 보유 학교만
    for r in cur.execute(
            "SELECT shl_idf_cd, school_name, sido, gugun, n_subj, years "
            "FROM schools WHERE has_curriculum=1"):
        sid = r["shl_idf_cd"]
        db[sid] = {"school": r["school_name"] or "", "sido": r["sido"] or "",
                   "gugun": r["gugun"] or "", "n_subj": r["n_subj"] or 0,
                   "years": r["years"] or "", "subjects": {"일반": [], "진로": [], "융합": []}}
        offered[sid] = set()
    for r in cur.execute("SELECT shl_idf_cd, type, subject FROM school_subjects"):
        sid = r["shl_idf_cd"]
        if sid not in db:
            continue
        typ = r["type"] if r["type"] in db[sid]["subjects"] else None
        if typ:
            db[sid]["subjects"][typ].append(r["subject"])
        offered[sid].add(_norm_subject(r["subject"]))
    con.close()
    return db, offered


def _load_school_subjects_json():
    """폴백: subjects_by_school_merged.json → subjects_by_school.json 순으로 로드."""
    for fname in ("subjects_by_school_merged.json", "subjects_by_school.json"):
        p = _path(fname)
        if not os.path.exists(p):
            continue
        db = json.load(open(p, encoding="utf-8"))
        offered = {}
        for sid, r in db.items():
            s = set()
            for subs in r.get("subjects", {}).values():
                s.update(_norm_subject(x) for x in subs)
            offered[sid] = s
            r.setdefault("n_subj", sum(len(v) for v in r.get("subjects", {}).values()))
        return db, offered
    return {}, {}


def _load_school_subjects():
    """schools.db 우선, 없으면 병합 JSON 폴백."""
    res = _load_school_subjects_sqlite()
    if res is not None:
        return res
    return _load_school_subjects_json()


def _load_vocab_canon():
    """과목 어휘 정규형 집합. schools.db의 vocab 테이블 우선, 없으면 vocab_2022.json."""
    p = _path("schools.db")
    if os.path.exists(p):
        try:
            import sqlite3
            con = sqlite3.connect(p)
            rows = con.execute("SELECT subject FROM vocab").fetchall()
            con.close()
            if rows:
                return {_norm_subject(r[0]) for r in rows}
        except Exception:
            pass
    pj = _path("vocab_2022.json")
    if os.path.exists(pj):
        v = json.load(open(pj, encoding="utf-8"))
        return {_norm_subject(k) for k in v}
    return set()


SCHOOL_DB, SCHOOL_OFFERED = _load_school_subjects()
_SUBJ_CANON = _load_vocab_canon()


def school_sidos():
    """개설과목 데이터가 있는 학교의 시도 목록."""
    return sorted({r.get("sido", "") for r in SCHOOL_DB.values() if r.get("sido")})


def school_guguns(sido):
    """해당 시도의 시군구 목록(개설과목 데이터 보유 학교 기준)."""
    return sorted({r.get("gugun", "") for r in SCHOOL_DB.values()
                   if r.get("sido") == sido and r.get("gugun")})


def school_options(sido=None, gugun=None):
    """UI용 학교 목록(개설과목 데이터 보유 학교만). [{shl_idf_cd, school, sido, gugun}]."""
    rows = [{"shl_idf_cd": sid, "school": r.get("school", ""),
             "sido": r.get("sido", ""), "gugun": r.get("gugun", ""),
             "n_subj": r.get("n_subj", 0)}
            for sid, r in SCHOOL_DB.items()]
    if sido:
        rows = [x for x in rows if x["sido"] == sido]
    if gugun:
        rows = [x for x in rows if x["gugun"] == gugun]
    rows.sort(key=lambda x: (x["gugun"], x["school"]))
    return rows


def subjects_of_major(rec):
    """추천 학과의 2022 선택과목(mapping_major.csv) → {일반/진로/융합: [과목...]}.
    어휘(vocab_2022) 정규형에 든 항목만 채택해 '등'·잡음 제거."""
    info = MAJOR_MAP_ID.get(rec.get("id")) or MAJOR_MAP_NAME.get(rec.get("name")) or {}
    raw = info.get("선택과목2022", "")
    out = {"일반": [], "진로": [], "융합": []}
    if not raw.strip():
        return out
    for sec in raw.split("|"):
        sec = sec.strip()
        if ":" not in sec:
            continue
        head, body = sec.split(":", 1)
        typ = ("일반" if "일반" in head else "진로" if "진로" in head
               else "융합" if "융합" in head else None)
        if not typ:
            continue
        for item in body.split(","):
            item = item.strip()
            if item.endswith("등"):
                item = item[:-1].strip()
            if item and _norm_subject(item) in _SUBJ_CANON and item not in out[typ]:
                out[typ].append(item)
    return out


def subject_availability(rec, shl_idf_cd):
    """학과 2022 선택과목 × 학생 고교 개설여부.
    반환: {by_type:{일반/진로/융합:[{subject, offered}]}, n_total, n_offered, have_school}."""
    by_major = subjects_of_major(rec)
    offered = SCHOOL_OFFERED.get(shl_idf_cd)
    have = offered is not None
    by_type = {"일반": [], "진로": [], "융합": []}
    n_total = n_off = 0
    for typ, subs in by_major.items():
        for s in subs:
            ok = bool(have and _norm_subject(s) in offered)
            by_type[typ].append({"subject": s, "offered": ok})
            n_total += 1
            n_off += int(ok)
    return {"by_type": by_type, "n_total": n_total,
            "n_offered": n_off, "have_school": have}


# ──────────────────────────────────────────────────────────────────
# 역방향 인덱스 (과목 → 학과) · 어휘 목록 · 학교별 개설과목 조회
#   탭2(학교별 설치과목)·탭3(학과별 정보)에서 사용
# ──────────────────────────────────────────────────────────────────
def _build_subject_major_index():
    """{정규화과목: set(학과명)} 역인덱스 + {학과명: score} 키워드 점수.
    학과 score는 그 학과 문서의 official rank_score 합(추천 점수와 동일 척도)."""
    subj2major = {}
    major_kw_score = {}
    for d, idx in zip(MAJORS, MAJOR_IDX):
        name = d["name"]
        # 학과 키워드 점수(고정): official rank_score 합
        sc = sum(rank_score(r) for r in idx["official_terms"].values())
        if name not in major_kw_score or sc > major_kw_score[name]:
            major_kw_score[name] = sc
        by = subjects_of_major({"id": d.get("id", ""), "name": name})
        for subs in by.values():
            for s in subs:
                subj2major.setdefault(_norm_subject(s), set()).add(name)
    return subj2major, major_kw_score


SUBJ2MAJOR, _MAJOR_KW_SCORE = _build_subject_major_index()

# 과목 어휘 메타({정규화: {원문표시명, type, freq}}): schools.db vocab 우선
def _build_vocab_meta():
    meta = {}
    p = _path("schools.db")
    if os.path.exists(p):
        try:
            import sqlite3
            con = sqlite3.connect(p)
            for sub, typ, freq in con.execute(
                    "SELECT subject, type, freq FROM vocab"):
                meta[_norm_subject(sub)] = {"name": sub, "type": typ or "",
                                            "freq": freq or 0}
            con.close()
            if meta:
                return meta
        except Exception:
            pass
    pj = _path("vocab_2022.json")
    if os.path.exists(pj):
        for k, v in json.load(open(pj, encoding="utf-8")).items():
            meta[_norm_subject(k)] = {"name": k, "type": v.get("type", ""),
                                      "freq": v.get("freq", 0)}
    return meta


VOCAB_META = _build_vocab_meta()


def subject_list():
    """탭2 '과목으로 찾기'용 과목 목록. [{key, name, type, freq, n_major}] freq순."""
    out = []
    for key, m in VOCAB_META.items():
        out.append({"key": key, "name": m["name"], "type": m["type"],
                    "freq": m["freq"], "n_major": len(SUBJ2MAJOR.get(key, set()))})
    out.sort(key=lambda x: (-x["freq"], x["name"]))
    return out


def majors_for_subject(subject_name, sort_by_score=True):
    """과목 → 그 과목을 권장 선택과목으로 두는 학과 목록.
    sort_by_score=True면 학과 키워드 점수 내림차순, False면 가나다순.
    반환: [{name, score}]."""
    key = _norm_subject(subject_name)
    names = SUBJ2MAJOR.get(key, set())
    rows = [{"name": n, "score": _MAJOR_KW_SCORE.get(n, 0)} for n in names]
    if sort_by_score:
        rows.sort(key=lambda x: (-x["score"], x["name"]))
    else:
        rows.sort(key=lambda x: x["name"])
    return rows


def school_subjects(shl_idf_cd):
    """학교 → 개설과목(어휘 154 기준) {일반/진로/융합:[과목명...]} + n_subj."""
    r = SCHOOL_DB.get(shl_idf_cd)
    if not r:
        return {"by_type": {"일반": [], "진로": [], "융합": []}, "n_subj": 0,
                "school": "", "sido": "", "gugun": ""}
    by = {t: sorted(set(v)) for t, v in r.get("subjects", {}).items()}
    for t in ("일반", "진로", "융합"):
        by.setdefault(t, [])
    n = sum(len(v) for v in by.values())
    return {"by_type": by, "n_subj": n, "school": r.get("school", ""),
            "sido": r.get("sido", ""), "gugun": r.get("gugun", "")}


def major_names():
    """탭3 학과 목록(중복 제거, 가나다순)."""
    return sorted({d["name"] for d in MAJORS})


def major_by_name(name):
    """학과명 → 추천 row 형태({id, name, score, officials, reasons}) 1건(최고 점수)."""
    best = None
    for d, idx in zip(MAJORS, MAJOR_IDX):
        if d["name"] != name:
            continue
        reasons = sorted(
            ({"official": off, "rank": r, "term": off, "via": "공시",
              "points": rank_score(r)}
             for off, r in idx["official_terms"].items()),
            key=lambda x: x["rank"])
        sc = sum(x["points"] for x in reasons)
        row = {"id": d.get("id", ""), "name": name, "score": sc,
               "officials": idx["officials"], "reasons": reasons}
        if best is None or sc > best["score"]:
            best = row
    return best


def schools_offering(subject_name, sido=None, gugun=None, limit=None):
    """과목 → 그 과목을 개설한 학교 목록. [{shl_idf_cd, school, sido, gugun}]."""
    key = _norm_subject(subject_name)
    rows = []
    for sid, off in SCHOOL_OFFERED.items():
        if key in off:
            r = SCHOOL_DB.get(sid, {})
            if sido and r.get("sido") != sido:
                continue
            if gugun and r.get("gugun") != gugun:
                continue
            rows.append({"shl_idf_cd": sid, "school": r.get("school", ""),
                         "sido": r.get("sido", ""), "gugun": r.get("gugun", "")})
    rows.sort(key=lambda x: (x["sido"], x["gugun"], x["school"]))
    return rows[:limit] if limit else rows


# 설치대학 학과명 정규화: build_univ_mapping.norm_major 와 동일 규칙 유지
_U_SUFFIX = re.compile(r"(학과|학부|학전공|전공|과|학)$")
_U_PAREN = re.compile(r"[\(\（].*?[\)\）]")
_U_NONWORD = re.compile(r"[^가-힣A-Za-z0-9]")


def norm_major(s: str) -> str:
    s = str(s).strip()
    s = _U_PAREN.sub("", s)
    s = _U_NONWORD.sub("", s)
    prev = None
    while prev != s:
        prev = s
        s = _U_SUFFIX.sub("", s)
        if len(s) <= 1:
            return prev
    return s or prev


# ──────────────────────────────────────────────────────────────────
# 키워드 추출 (발화 → 토큰; 부정절 토큰 제외)
# ──────────────────────────────────────────────────────────────────
def extract_terms_rule(speech: str):
    """[규칙 기반] 발화 → (긍정 토큰 set, 정규화 문자열, 제외 토큰 set).

    부정 단서가 들어간 절의 토큰은 제외한다.
    부분문자열 매칭(쉬운말)을 위해 부정절을 제거한 정규화 문자열도 만든다.
    """
    pos_tokens, neg_tokens = set(), set()
    pos_chunks = []
    for clause in CLAUSE_SPLIT.split(str(speech)):
        clause = clause.strip()
        if not clause:
            continue
        toks = set(tokenize(clause))
        if any(m in clause for m in NEG_MARKERS):
            neg_tokens |= toks
        else:
            pos_tokens |= toks
            pos_chunks.append(clause)
    pos_tokens -= neg_tokens
    norm = re.sub(r"\s+", "", " ".join(pos_chunks))
    return pos_tokens, norm, neg_tokens


def extract_terms(speech: str, use_llm: bool = False):
    """발화 → (긍정 토큰 set, 정규화 문자열, 제외 토큰 set, meta).

    use_llm=True 이고 OPENAI_API_KEY 가 있으면 LLM로 표준 키워드를 뽑고,
    실패/키없음이면 규칙 기반으로 자동 폴백한다. meta로 사용 경로를 알린다.
    LLM 키워드는 그 자체를 토큰으로 쓰고, 쉬운말 부분문자열 매칭을 위해
    키워드들을 이어붙인 문자열도 norm 으로 함께 넘긴다.
    """
    meta = {"mode": "rule", "rationale": "", "note": ""}
    if use_llm:
        try:
            import llm_extract
        except Exception as e:
            llm_extract = None
            meta["note"] = f"llm 모듈 로드 실패: {e}"
        if llm_extract is not None and llm_extract.available():
            res = llm_extract.extract(speech)
            if res and not res.get("error") and res.get("pos"):
                pos = set(res["pos"])
                neg = set(res.get("neg", []))
                pos -= neg
                norm = "".join(sorted(pos))
                meta.update(mode="llm", rationale=res.get("rationale", ""))
                return pos, norm, neg, meta
            if res and res.get("error"):
                meta["note"] = f"llm 호출 실패→규칙 폴백: {res['error']}"
            else:
                meta["note"] = "llm 결과 없음→규칙 폴백"
        elif not meta["note"]:
            meta["note"] = "OPENAI_API_KEY 없음→규칙 폴백"
    pos, norm, neg = extract_terms_rule(speech)
    return pos, norm, neg, meta


# ──────────────────────────────────────────────────────────────────
# 단일 코퍼스 추천 (순위 점수합, 설명가능)
# ──────────────────────────────────────────────────────────────────
def _score_doc(doc, tokens, norm):
    """문서 1건 점수 + 매칭 근거. 같은 공시키워드는 최고순위 1회만 인정."""
    matched = {}  # official -> (rank, matched_term, via)
    for off, r in doc["official_terms"].items():
        if off in tokens:
            cur = matched.get(off)
            if cur is None or r < cur[0]:
                matched[off] = (r, off, "공시")
    for term, (r, off) in doc["easy_terms"].items():
        hit = (term in tokens) or (len(term) >= 2 and term in norm)
        if hit:
            cur = matched.get(off)
            if cur is None or r < cur[0]:
                matched[off] = (r, term, "쉬운말")
    score = sum(rank_score(r) for r, _, _ in matched.values())
    return score, matched


def _recommend_corpus(idx, tokens, norm, top_n):
    best = {}  # name -> row (커리어넷 동일 명칭 중복 id는 최고점 1건만)
    for doc in idx:
        score, matched = _score_doc(doc, tokens, norm)
        if score <= 0:
            continue
        reasons = sorted(
            ({"official": off, "rank": r, "term": term, "via": via,
              "points": rank_score(r)}
             for off, (r, term, via) in matched.items()),
            key=lambda x: x["rank"])
        row = {
            "id": doc["id"], "name": doc["name"], "score": score,
            "officials": doc["officials"], "reasons": reasons,
        }
        cur = best.get(doc["name"])
        if cur is None or score > cur["score"]:
            best[doc["name"]] = row
    rows = sorted(best.values(), key=lambda x: (-x["score"], x["name"]))
    return rows[:top_n]


# ──────────────────────────────────────────────────────────────────
# 학과 × 직업 연계 페어 (공시키워드 교집합)
# ──────────────────────────────────────────────────────────────────
def link_pairs(top_majors, top_jobs, top_k=9):
    pairs = []
    for m in top_majors:
        for j in top_jobs:
            overlap = m["officials"] & j["officials"]
            pairs.append({
                "major": m["name"], "major_score": m["score"],
                "job": j["name"], "job_score": j["score"],
                "overlap": sorted(overlap),
                "overlap_n": len(overlap),
            })
    pairs.sort(key=lambda x: (-x["overlap_n"],
                              -(x["major_score"] + x["job_score"])))
    return pairs[:top_k]


# ──────────────────────────────────────────────────────────────────
# 부가정보 조인
# ──────────────────────────────────────────────────────────────────
def universities_for(name):
    """학과명 → 설치대학 구조화 목록.

    설치모집단위 리스트(mapping_univ.json) 우선 조회.
    반환: {"source": "univ"|"none", "univ_count": N,
           "by_region": {지역: [{대학명, 전형:[...], 인원, 분류}]}}
    매칭 실패(전문대·교양학부 등)면 univ_count=0 → 호출부가 개설대학 폴백 처리.
    """
    key = norm_major(name)
    entry = UNIV_MAP.get(key)
    if not entry:
        return {"source": "none", "univ_count": 0, "by_region": {}}
    by_region = {}
    for u in entry.get("univs", []):
        by_region.setdefault(u["지역"], []).append({
            "대학명": u["대학명"],
            "전형": u.get("전형", []),
            "인원": u.get("인원", 0),
            "분류": u.get("분류", ""),
        })
    return {"source": "univ", "univ_count": entry.get("univ_count", 0),
            "by_region": by_region}


def major_extra(rec):
    info = MAJOR_MAP_ID.get(rec["id"]) or MAJOR_MAP_NAME.get(rec["name"]) or {}
    return {"개설대학": info.get("개설대학", ""),
            "관련직업": info.get("관련직업", ""),
            "관련자격": info.get("관련자격", ""),
            "설치대학": universities_for(rec["name"])}


def job_extra(rec):
    info = JOB_MAP_ID.get(rec["id"]) or JOB_MAP_NAME.get(rec["name"]) or {}
    return {"관련학과": info.get("관련학과", ""),
            "관련자격": info.get("관련자격", "")}


# ──────────────────────────────────────────────────────────────────
# 구분자 없이 붙어버린 관련학과/관련직업 문자열 분절(최장일치 + 접미사 폴백)
# ──────────────────────────────────────────────────────────────────
_MAJOR_NAMES = sorted({d["name"] for d in MAJORS}, key=len, reverse=True)
_JOB_NAMES = sorted({d["name"] for d in JOBS}, key=len, reverse=True)
_MAJOR_SET = set(_MAJOR_NAMES)
_JOB_SET = set(_JOB_NAMES)
_MAJOR_MAXLEN = max((len(n) for n in _MAJOR_NAMES), default=0)
_JOB_MAXLEN = max((len(n) for n in _JOB_NAMES), default=0)
_DELIMS = re.compile(r"[,·/|;、ㆍ]")
_MAJOR_SUFFIX = re.compile(r".+?(공학과|학과|학부|전공|과)")


def _split_known(s, name_set, maxlen, suffix_re=None):
    """붙어있는 이름 문자열을 알려진 이름으로 최장일치 분절. 실패분은 접미사/통째 처리."""
    s = str(s).strip()
    if not s:
        return []
    if _DELIMS.search(s):  # 이미 구분자 있으면 그대로 분리
        return [x.strip() for x in _DELIMS.split(s) if x.strip()]
    out, i, n = [], 0, len(s)
    while i < n:
        matched = None
        for L in range(min(maxlen, n - i), 1, -1):
            if s[i:i + L] in name_set:
                matched = s[i:i + L]
                break
        if matched:
            out.append(matched)
            i += len(matched)
        elif suffix_re:
            m = suffix_re.match(s[i:])
            if m:
                out.append(m.group(0))
                i += m.end()
            else:
                out.append(s[i:])
                break
        else:
            out.append(s[i:])
            break
    return out


def split_related_majors(s):
    return _split_known(s, _MAJOR_SET, _MAJOR_MAXLEN, _MAJOR_SUFFIX)


def split_related_jobs(s):
    return _split_known(s, _JOB_SET, _JOB_MAXLEN)


# ──────────────────────────────────────────────────────────────────
# 통합 추천
# ──────────────────────────────────────────────────────────────────
def recommend(speech: str, top_n: int = 5, pair_k: int = 5, use_llm: bool = False):
    tokens, norm, excluded, meta = extract_terms(speech, use_llm=use_llm)
    majors = _recommend_corpus(MAJOR_IDX, tokens, norm, top_n)
    jobs = _recommend_corpus(JOB_IDX, tokens, norm, top_n)
    pairs = link_pairs(majors[:3], jobs[:3], top_k=pair_k)
    return {
        "tokens": sorted(tokens),
        "excluded": sorted(excluded),
        "majors": majors,
        "jobs": jobs,
        "pairs": pairs,
        "meta": meta,
    }


if __name__ == "__main__":
    demo = "나는 로봇이랑 똑똑한 기계가 좋아요. 그림 그리는 건 별로예요."
    out = recommend(demo, top_n=5)
    print("발화:", demo)
    print("토큰:", out["tokens"])
    print("제외:", out["excluded"])
    print("\n[학과]")
    for r in out["majors"]:
        terms = ", ".join(f'{x["term"]}({x["rank"]}위·{x["via"]})'
                          for x in r["reasons"][:6])
        print(f'  {r["name"]:20s} {r["score"]:>3}  ← {terms}')
    print("\n[직업]")
    for r in out["jobs"]:
        terms = ", ".join(f'{x["term"]}({x["rank"]}위·{x["via"]})'
                          for x in r["reasons"][:6])
        print(f'  {r["name"]:20s} {r["score"]:>3}  ← {terms}')
    print("\n[연계 페어]")
    for p in out["pairs"]:
        print(f'  {p["major"]} → {p["job"]}  공통 {p["overlap_n"]}: {", ".join(p["overlap"])}')
