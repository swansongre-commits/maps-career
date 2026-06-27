# -*- coding: utf-8 -*-
"""원천 커리어넷 JSON(datacrawling/raw) → content.db (정규화 콘텐츠 DB).

설계: DB_SCHEMA_재구조화.md. schools.db는 건드리지 않는다(고교 개설과목은 그대로 사용).
핵심: major_job 관계를 학과측 relateJob.relate_SEQ(직업 ID)로 정확 적재 → 퍼지매칭 0.

입력: datacrawling/raw/{major,job}/*.json, vocab_2022.json, achievement_standards.json
출력: content.db (+ 콘솔 무결성/커버리지 리포트, meta 테이블 기록)
실행: python build_content_db.py
"""
import glob
import json
import os
import re
import sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, "datacrawling", "raw")
OUT = os.path.join(BASE, "content.db")

_ROMAN = {"Ⅰ": "I", "Ⅱ": "II", "Ⅲ": "III", "Ⅳ": "IV", "Ⅴ": "V"}


def subj_norm(s):
    """과목 정규화 — recommender._norm_subject와 동일(로마숫자→영문, 공백 제거)."""
    s = str(s or "").strip()
    for a, b in _ROMAN.items():
        s = s.replace(a, b)
    return re.sub(r"\s+", "", s)


def name_norm(s):
    return re.sub(r"\s+", "", str(s or "").strip())


# ── 직업 이모지/한줄(주니어 카드용) — build_junior_data.py 규칙 이식 ──
EMOJI_RULES = [
    ("수의", "🐶"), ("동물", "🐾"), ("반려", "🐶"), ("축산", "🐄"),
    ("우주", "🚀"), ("항공", "✈️"), ("천문", "🔭"), ("비행", "✈️"), ("조종", "🛩️"),
    ("디자인", "🎨"), ("미술", "🎨"), ("화가", "🖼️"), ("그림", "🎨"), ("일러스트", "🖌️"),
    ("게임", "🎮"), ("웹툰", "🖍️"), ("애니메이", "🎞️"),
    ("로봇", "🤖"), ("인공지능", "🤖"),
    ("프로그", "💻"), ("소프트웨어", "💻"), ("개발자", "💻"), ("컴퓨터", "💻"), ("데이터", "📊"),
    ("의사", "🩺"), ("간호", "💉"), ("약사", "💊"), ("의료", "🩺"), ("치과", "🦷"), ("한의", "🌿"),
    ("운동", "⚽"), ("스포츠", "🏅"), ("체육", "🤸"), ("선수", "🏆"), ("트레이너", "💪"),
    ("요리", "🍳"), ("조리", "🍳"), ("제빵", "🥐"), ("제과", "🧁"), ("바리스타", "☕"), ("음식", "🍽️"),
    ("음악", "🎵"), ("작곡", "🎼"), ("가수", "🎤"), ("연주", "🎻"), ("성악", "🎶"),
    ("법", "⚖️"), ("변호", "⚖️"), ("판사", "⚖️"), ("검사", "⚖️"), ("경찰", "🚓"), ("소방", "🚒"),
    ("교사", "👩‍🏫"), ("교수", "🎓"), ("교육", "📚"), ("유치원", "🧸"),
    ("과학", "🔬"), ("연구", "🔬"), ("화학", "🧪"), ("물리", "🧲"), ("생명", "🧬"), ("실험", "⚗️"),
    ("식물", "🌱"), ("농업", "🌾"), ("원예", "🪴"), ("산림", "🌳"), ("환경", "♻️"),
    ("바다", "🌊"), ("해양", "🌊"), ("수산", "🐟"), ("어업", "🎣"), ("항해", "⛵"), ("선박", "🚢"),
    ("건축", "🏗️"), ("건설", "🏗️"), ("토목", "🏗️"), ("인테리어", "🛋️"),
    ("작가", "✍️"), ("기자", "📰"), ("번역", "🌍"), ("통역", "🌍"), ("편집", "📝"), ("사서", "📖"),
    ("영화", "🎬"), ("방송", "📺"), ("배우", "🎭"), ("연기", "🎭"), ("아나운서", "🎙️"),
    ("사진", "📷"), ("무용", "💃"), ("연극", "🎭"),
    ("금융", "💰"), ("은행", "🏦"), ("회계", "🧮"), ("경제", "💵"), ("증권", "📈"),
    ("자동차", "🚗"), ("기계", "⚙️"), ("전기", "⚡"), ("전자", "🔌"), ("에너지", "🔋"),
    ("패션", "👗"), ("의류", "🧵"), ("메이크업", "💄"), ("미용", "💇"), ("뷰티", "💅"),
    ("군", "🎖️"), ("물류", "📦"), ("여행", "🧳"), ("호텔", "🏨"), ("승무원", "🛫"),
    ("복지", "🤝"), ("상담", "💬"), ("심리", "🧠"), ("요양", "🧓"), ("드론", "🚁"),
]


def pick_emoji(name, tag):
    hay = (str(name) + " " + str(tag or "")).lower()
    for kw, em in EMOJI_RULES:
        if kw.lower() in hay:
            return em
    return "💼"


def kidify(text):
    if not text:
        return ""
    seg = re.split(r"[.,]\s|\.$|\n", str(text).strip())[0].strip().rstrip(" .,")
    seg = re.sub(r"합니다$", "해요", seg)
    seg = re.sub(r"됩니다$", "돼요", seg)
    seg = re.sub(r"입니다$", "이에요", seg)
    if len(seg) > 48:
        seg = seg[:46].rstrip() + "…"
    return seg


def flat_text(v):
    """리스트/문자열/딕트 혼재 필드 → ' ' 결합 문자열."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, list):
        parts = []
        for it in v:
            if isinstance(it, str):
                parts.append(it.strip())
            elif isinstance(it, dict):
                parts.append(str(it.get("name") or it.get("text") or "").strip())
        return " ".join(p for p in parts if p)
    return str(v)


AREA_2022 = {"일반 선택": "일반", "진로 선택": "진로", "융합 선택": "융합"}
AREA_2015 = {"공통과목": "공통", "일반선택과목": "일반", "진로선택과목": "진로",
             "전문교과Ⅰ": "전문", "전문교과Ⅱ": "전문", "전문교과": "전문"}


def parse_subject_groups(items, area_map):
    """relateSubject2022/2015 → [(과목명, area)] 리스트.
    구조: [area헤더][내용행][area헤더][내용행]…[출처 footer].
    헤더당 '바로 다음 내용행 1개'만 소비하고, 출처('[…' / '출처') 행은 스킵."""
    out, expect = [], None
    for it in items:
        desc = (it.get("subject_DESCRIPTION") or "").strip()
        if not desc:
            continue
        if desc in area_map:
            expect = area_map[desc]
            continue
        if desc.startswith("[") or "출처" in desc:   # footer
            expect = None
            continue
        if expect is None:
            continue
        for tok in desc.split(","):
            t = tok.strip().rstrip("등").strip().strip(" []")
            if ":" in t:                      # 2015 "예술교과 : 미술"
                t = t.split(":")[-1].strip()
            if any(ch in t for ch in "[]()") or "출처" in t:
                continue
            if t and len(t) <= 20:
                out.append((t, expect))
        expect = None                          # 한 area = 한 내용행
    return out


def main():
    if os.path.exists(OUT):
        os.remove(OUT)
    con = sqlite3.connect(OUT)
    c = con.cursor()
    c.executescript("""
    CREATE TABLE major(major_id TEXT PRIMARY KEY, name TEXT, name_norm TEXT,
      summary TEXT, features TEXT, aptitude TEXT, explore_act TEXT,
      univ_courses TEXT, career_field TEXT, category TEXT,
      salary_code TEXT, read_cnt INTEGER, like_cnt INTEGER);
    CREATE TABLE job(job_id TEXT PRIMARY KEY, name TEXT, name_norm TEXT,
      duties TEXT, core_skill TEXT, aptitude TEXT, interest TEXT,
      std_job_nm TEXT, std_job_cd TEXT, tags TEXT, read_cnt INTEGER);
    CREATE TABLE job_card(job_id TEXT PRIMARY KEY, emoji TEXT, blurb TEXT,
      salary TEXT, wage_level TEXT, satisfaction TEXT);
    CREATE TABLE university(univ_id TEXT PRIMARY KEY, name TEXT, region TEXT);
    CREATE TABLE subject(subject_id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT, name_norm TEXT UNIQUE, is_target INTEGER DEFAULT 0);
    CREATE TABLE certification(cert_id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT UNIQUE, url TEXT);
    CREATE TABLE major_job(major_id TEXT, job_id TEXT, via_major INTEGER DEFAULT 0,
      via_job INTEGER DEFAULT 0, PRIMARY KEY(major_id, job_id));
    CREATE TABLE major_subject(major_id TEXT, subject_id INTEGER, curriculum TEXT,
      area TEXT, PRIMARY KEY(major_id, subject_id, curriculum, area));
    CREATE TABLE major_university(major_id TEXT, univ_id TEXT, campus TEXT,
      PRIMARY KEY(major_id, univ_id));
    CREATE TABLE major_certification(major_id TEXT, cert_id INTEGER,
      PRIMARY KEY(major_id, cert_id));
    CREATE TABLE job_certification(job_id TEXT, cert_id INTEGER,
      PRIMARY KEY(job_id, cert_id));
    CREATE TABLE subject_achievement(subject_id INTEGER, code TEXT, text TEXT);
    CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
    """)

    # ── 과목/자격 마스터 헬퍼 ──
    subj_cache = {}     # name_norm -> subject_id
    target_norms = set()
    voc = json.load(open(os.path.join(BASE, "vocab_2022.json"), encoding="utf-8"))
    for sname in voc:
        target_norms.add(subj_norm(sname))

    def get_subject(name):
        nn = subj_norm(name)
        if not nn:
            return None
        if nn in subj_cache:
            return subj_cache[nn]
        is_t = 1 if nn in target_norms else 0
        c.execute("INSERT OR IGNORE INTO subject(name,name_norm,is_target) VALUES(?,?,?)",
                  (name, nn, is_t))
        sid = c.execute("SELECT subject_id FROM subject WHERE name_norm=?", (nn,)).fetchone()[0]
        subj_cache[nn] = sid
        return sid

    cert_cache = {}

    def get_cert(name, url=None):
        nm = str(name or "").strip()
        if not nm:
            return None
        if nm in cert_cache:
            return cert_cache[nm]
        c.execute("INSERT OR IGNORE INTO certification(name,url) VALUES(?,?)", (nm, url))
        cid = c.execute("SELECT cert_id FROM certification WHERE name=?", (nm,)).fetchone()[0]
        cert_cache[nm] = cid
        return cid

    # 어휘 과목 선적재(is_target=1 보장)
    for sname in voc:
        get_subject(sname)

    # ── JOB 적재 ──
    job_ids = set()
    for fp in glob.glob(os.path.join(RAW, "job", "*.json")):
        d = json.load(open(fp, encoding="utf-8"))
        jid = str(d.get("seq"))
        job_ids.add(jid)
        duties = flat_text(d.get("jobWorkList"))
        c.execute("INSERT OR REPLACE INTO job VALUES(?,?,?,?,?,?,?,?,?,?,?)", (
            jid, d.get("job_nm"), name_norm(d.get("job_nm")),
            duties, flat_text(d.get("jobAbilityList")),
            flat_text(d.get("jobAptitudeList")), flat_text(d.get("jobInterestList")),
            d.get("std_job_nm"), str(d.get("std_job_cd") or ""), d.get("tag"),
            int(d.get("views") or 0)))
        c.execute("INSERT OR REPLACE INTO job_card VALUES(?,?,?,?,?,?)", (
            jid, pick_emoji(d.get("job_nm"), d.get("tag")), kidify(duties),
            d.get("wage"), d.get("wage_level"), d.get("satisfication")))
        for it in d.get("jobCertiList") or []:
            cid = get_cert(it.get("name"), it.get("detail"))
            if cid:
                c.execute("INSERT OR IGNORE INTO job_certification VALUES(?,?)", (jid, cid))

    # ── MAJOR 적재 ──
    major_ids = set()
    rel_targets = []            # relateJob 대상 직업 seq (커버리지 측정용)
    for fp in glob.glob(os.path.join(RAW, "major", "*.json")):
        d = json.load(open(fp, encoding="utf-8"))
        mid = str(d.get("seq"))
        major_ids.add(mid)
        univ_courses = " | ".join(
            f"{s.get('subject_NAME')}: {s.get('subject_DESCRIPTION')}"
            for s in (d.get("subject") or []) if s.get("subject_NAME"))
        career_field = " | ".join(
            f"{g.get('graduate_AFTER_NAME')}: {g.get('graduate_AFTER_DESCRIPTION')}"
            for g in (d.get("graduateAfter") or []) if g.get("graduate_AFTER_NAME"))
        c.execute("INSERT OR REPLACE INTO major VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            mid, d.get("major_NM"), name_norm(d.get("major_NM")),
            d.get("major_SUMRY"), d.get("characteristics"), d.get("interest"),
            d.get("career_ACT"), univ_courses, career_field, d.get("major_CLNM"),
            str(d.get("salary_CODE") or ""), int(d.get("rdcnt") or 0),
            int(d.get("likecnt") or 0)))

        # major_job (★ 학과측 ID 정본)
        for it in d.get("relateJob") or []:
            rj = it.get("relate_SEQ")
            if rj:
                rel_targets.append(str(rj))
                c.execute("INSERT OR IGNORE INTO major_job(major_id,job_id,via_major) "
                          "VALUES(?,?,1)", (mid, str(rj)))
        # major_subject (2022 + 2015)
        for items, cur, amap in (
                (d.get("relateSubject2022") or [], "2022", AREA_2022),
                (d.get("relateSubject2015") or [], "2015", AREA_2015)):
            for sname, area in parse_subject_groups(items, amap):
                sid = get_subject(sname)
                if sid:
                    c.execute("INSERT OR IGNORE INTO major_subject VALUES(?,?,?,?)",
                              (mid, sid, cur, area))
        # major_certification
        for it in d.get("relateQualf") or []:
            cid = get_cert(it.get("qualf_NAME"), it.get("relate_URL"))
            if cid:
                c.execute("INSERT OR IGNORE INTO major_certification VALUES(?,?)", (mid, cid))
        # major_university (schl[] — univ_SEQ ID)
        for u in d.get("schl") or []:
            uid = str(u.get("univ_SEQ") or "").strip()
            if not uid:
                continue
            c.execute("INSERT OR IGNORE INTO university VALUES(?,?,?)",
                      (uid, u.get("univ_NM"), u.get("area_NAME")))
            c.execute("INSERT OR IGNORE INTO major_university VALUES(?,?,?)",
                      (mid, uid, u.get("campus_NM")))

    # ── 성취기준 ──
    ach = json.load(open(os.path.join(BASE, "achievement_standards.json"), encoding="utf-8"))
    ach_subj = 0
    for key, v in ach.items():
        sname = v.get("subject", key)
        sid = get_subject(sname)
        ach_subj += 1
        for it in v.get("items", []):
            c.execute("INSERT INTO subject_achievement VALUES(?,?,?)",
                      (sid, it.get("code"), it.get("text")))

    con.commit()

    # ── 무결성/커버리지 리포트 ──
    def n(q):
        return c.execute(q).fetchone()[0]
    rel_in = sum(1 for t in rel_targets if t in job_ids)
    mj_in = n("SELECT COUNT(*) FROM major_job WHERE job_id IN (SELECT job_id FROM job)")
    mj_total = n("SELECT COUNT(*) FROM major_job")
    report = {
        "majors": n("SELECT COUNT(*) FROM major"),
        "jobs": n("SELECT COUNT(*) FROM job"),
        "universities": n("SELECT COUNT(*) FROM university"),
        "subjects": n("SELECT COUNT(*) FROM subject"),
        "subjects_target": n("SELECT COUNT(*) FROM subject WHERE is_target=1"),
        "certifications": n("SELECT COUNT(*) FROM certification"),
        "major_job": mj_total,
        "major_job_orphan(job미수집)": mj_total - mj_in,
        "major_subject": n("SELECT COUNT(*) FROM major_subject"),
        "major_university": n("SELECT COUNT(*) FROM major_university"),
        "major_certification": n("SELECT COUNT(*) FROM major_certification"),
        "job_certification": n("SELECT COUNT(*) FROM job_certification"),
        "subject_achievement": n("SELECT COUNT(*) FROM subject_achievement"),
        "majors_with_job": n("SELECT COUNT(DISTINCT major_id) FROM major_job"),
        "majors_with_univ": n("SELECT COUNT(DISTINCT major_id) FROM major_university"),
        "majors_with_subject": n("SELECT COUNT(DISTINCT major_id) FROM major_subject"),
    }
    for k, v in report.items():
        c.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (k, str(v)))
    con.commit()

    print("=" * 56)
    print("content.db 생성 완료:", OUT)
    print("=" * 56)
    for k, v in report.items():
        print(f"  {k:32s}: {v}")
    print(f"\n  relateJob 대상 중 수집직업(468) 포함: {rel_in}/{len(rel_targets)} "
          f"({100*rel_in/max(len(rel_targets),1):.1f}%)")
    con.close()


if __name__ == "__main__":
    main()
