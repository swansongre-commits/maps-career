# -*- coding: utf-8 -*-
"""M.A.P.S 과목선택 내비게이터 (자체 서비스 프로토타입) — Streamlit 재구현.

설계 문서: MAPS_자체서비스_화면설계_v1.md(v1.1, 상급자 리뷰 반영).
디자인: 기존 M.A.P.S(views/highschool.py) FABRIK 팔레트 그대로 계승
        (무채색·흰 배경·검정 CTA·8px/999px 라운드) — 신규 컬러 도입 없음.

흐름: S0 학교·학년 → S1 관심 입력 → S2 갈래·후보 → S3 학과 상세(권장과목·성취기준)
     → S3.5 이수체크(S3 안 인라인) → S4 개설여부 → S5 상의할 목록(결승선)
     → S6 미개설 대안. S7(공유 링크)은 쿼리파라미터로 읽기전용 뷰.

전제: 고1·고2만 지원(2022 개정 교육과정 코호트, 고3 제외 — v1.1 §0 차단조건).
서버 세션 상태만 사용(st.session_state) — 계정·DB 저장 없음. 공유는 URL 쿼리파라미터.
"""
import base64
import json

import streamlit as st

# set_page_config는 라우터(app.py)에서 1회만 호출 — 페이지 스크립트에서는 호출 금지.


@st.cache_resource
def load_engine():
    import recommender
    return recommender


@st.cache_resource
def load_content_db():
    try:
        import content_db
        return content_db if content_db.available() else None
    except Exception:
        return None


R = load_engine()
CDB = load_content_db()

# ──────────────────────────────────────────────────────────────────
# 디자인 — highschool.py FABRIK 팔레트 계승(무채색 에디토리얼)
# ──────────────────────────────────────────────────────────────────
FABRIK = {
    "bg": "#F5F5F5", "surface": "#FFFFFF", "surface_soft": "#F0F0F0",
    "border": "#E4E4E4", "line_strong": "#C9C9C9",
    "cta": "#141414", "cta_soft": "#EDEDED",
    "text": "#141414", "ink_mid": "#3F3F3F", "muted": "#6B6B6B",
}

CSS = f"""
<style>
.stApp {{ background: {FABRIK['bg']}; color: {FABRIK['text']}; }}
.cn-sub {{ color: {FABRIK['muted']}; font-size: 0.92rem; margin: -0.3rem 0 1rem; }}
.cn-banner {{ background: {FABRIK['surface_soft']}; border: 1px solid {FABRIK['border']};
    border-radius: 8px; padding: 10px 14px; font-size: 0.86rem; color: {FABRIK['muted']};
    margin-bottom: 14px; }}
.cn-banner.warn {{ border-color: #E0A94F; color: #8A6320; background: #FFF8EC; }}
.cn-card {{ background: {FABRIK['surface']}; border: 1px solid {FABRIK['border']};
    border-radius: 8px; padding: 14px 16px; margin-bottom: 12px; }}
.cn-major {{ background: {FABRIK['surface_soft']}; border-radius: 8px; padding: 10px 12px;
    margin-bottom: 8px; }}
.cn-major .name {{ font-weight: 800; font-size: 1.0rem; }}
.cn-major .summary {{ color: {FABRIK['muted']}; font-size: 0.86rem; margin: 4px 0; }}
.cn-major .reason {{ color: #1D4ED8; font-size: 0.82rem; }}
.cn-cathead {{ font-weight: 800; font-size: 1.02rem; margin-bottom: 8px; }}
.cn-summary {{ font-size: 0.92rem; color: {FABRIK['muted']}; margin-bottom: 12px; line-height: 1.7; }}
.cn-summary b {{ color: {FABRIK['text']}; }}
.cn-chip-grid div[data-testid="stButton"] > button {{ min-height: 56px; font-size: 0.86rem; }}
/* 관심 칩 — 좁은 화면에서도 4열 유지가 과하니 2열 그리드로 고정(Streamlit 기본 컬럼 세로쌓임 방지) */
[class*="cn_chip_grid"] div[data-testid="stHorizontalBlock"] {{ flex-wrap: wrap; gap: 8px; }}
[class*="cn_chip_grid"] div[data-testid="stColumn"] {{
    flex: 0 1 calc(50% - 4px) !important;
    min-width: calc(50% - 4px) !important; width: calc(50% - 4px) !important; }}
.cn-badge {{ display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 0.74rem;
    font-weight: 800; margin-left: 6px; }}
.cn-badge.ok {{ background: #EFF6FF; color: #1D4ED8; border: 1px solid #93C5FD; }}
.cn-badge.done {{ background: #E9F7EF; color: #1E7A46; border: 1px solid #A3E0BE; }}
.cn-badge.applied {{ background: #FFF3D6; color: #8A6320; border: 1px solid #E9C77E; }}
.cn-badge.q {{ background: {FABRIK['surface_soft']}; color: {FABRIK['muted']}; border: 1px solid {FABRIK['border']}; }}
.cn-pill {{ display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 0.76rem;
    font-weight: 800; white-space: nowrap; }}
.cn-pill.il {{ background: #FCE7E9; color: #B23A48; }}
.cn-pill.jr {{ background: #E3F5E9; color: #1F8A54; }}
.cn-pill.yh {{ background: #E5EEFB; color: #2A5DB0; }}
.cn-row {{ display: flex; align-items: center; gap: 8px; min-height: 38px; }}
div[data-testid="stCheckbox"] {{ display: flex; justify-content: flex-end; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────
# 관심 칩 (수기 큐레이션 24개 — S1)
# ──────────────────────────────────────────────────────────────────
CHIPS = [
    ("동물", "🐾"), ("실험", "🧪"), ("그림", "🎨"), ("코딩", "💻"),
    ("돌봄", "🏥"), ("정의", "⚖️"), ("무대", "🎤"), ("여행", "✈️"),
    ("탐구", "🔬"), ("건축", "🏗️"), ("경영", "📈"), ("요리", "🍳"),
    ("운동", "⚽"), ("영상", "🎬"), ("환경", "🌱"), ("수리", "🧮"),
    ("글쓰기", "📖"), ("로봇", "🤖"), ("음악", "🎼"), ("설득", "🗣️"),
    ("가르침", "🧑‍🏫"), ("세계", "🌏"), ("손재주", "🧵"), ("우주", "🛰️"),
]

DAE_EMOJI = {
    "공학": "⚙️", "자연": "🧪", "의학": "🏥", "사회": "⚖️",
    "인문": "📚", "교육": "🍎", "예체능": "🎨", "공통": "🧭", "기타": "🧭",
}


@st.cache_resource
def _major_to_dae_index():
    idx = {}
    for dae, jungs in R.CATEGORY_TREE.items():
        for jung, sos in jungs.items():
            for so, names in sos.items():
                for name in names:
                    idx.setdefault(name, set()).add(dae)
    return idx


MAJOR_TO_DAE = _major_to_dae_index()


def _major_summary(name):
    if not CDB:
        return ""
    try:
        info = CDB.major_intro(name)
        return (info or {}).get("summary", "") or ""
    except Exception:
        return ""


def _job_meta(name):
    if not CDB:
        return {"emoji": "💼", "blurb": ""}
    try:
        meta = CDB.junior_job_meta().get(name)
        if meta:
            return {"emoji": meta.get("emoji", "💼"), "blurb": meta.get("blurb", "")}
    except Exception:
        pass
    return {"emoji": "💼", "blurb": ""}


def _reason_sentence(reasons, chip_mode):
    if not reasons:
        return ""
    best = next((r for r in reasons if r.get("via") == "쉬운말"), reasons[0])
    term = best.get("term", "")
    return f"'{term}' 칩을 골라서" if chip_mode else f"네가 '{term}'이라고 해서"


# ──────────────────────────────────────────────────────────────────
# 상태 초기화
# ──────────────────────────────────────────────────────────────────
def _init_state():
    ss = st.session_state
    ss.setdefault("cn_step", "s0")
    ss.setdefault("cn_profile", {"sido": "", "gugun": "", "school_id": "",
                                  "school_name": "", "grade": "고1", "semester": 1})
    ss.setdefault("cn_taken", [])        # [{subject, status: 이수함|신청함}]
    ss.setdefault("cn_interests", {"utterance": "", "chips": []})
    ss.setdefault("cn_candidates", None)
    ss.setdefault("cn_current_major", None)
    ss.setdefault("cn_plan", [])         # [{subject, from_major}]
    ss.setdefault("cn_alt_subject", "")
    ss.setdefault("cn_seen_sheet_for", [])
    ss.setdefault("cn_first_visit_modal_shown", False)
    ss.setdefault("cn_history", [])   # 뒤로가기용 방문 이력 스택


def _go(step):
    """다음 화면으로 이동 — 현재 화면을 이력 스택에 쌓는다(뒤로가기가 실제 방문 순서를 따라가도록)."""
    cur = st.session_state["cn_step"]
    if cur != step:
        st.session_state["cn_history"].append(cur)
    st.session_state["cn_step"] = step
    st.rerun()


def _back():
    """뒤로가기 — 이력 스택에서 바로 직전 화면으로. 스택이 비었으면 처음 화면으로."""
    hist = st.session_state["cn_history"]
    st.session_state["cn_step"] = hist.pop() if hist else "s0"
    st.rerun()


def _taken_status(subject):
    for t in st.session_state["cn_taken"]:
        if t["subject"] == subject:
            return t["status"]
    return None


def _taken_type(subject):
    for t in st.session_state["cn_taken"]:
        if t["subject"] == subject:
            return t.get("type", "")
    return ""


def _set_taken(subject, status, typ=""):
    taken = st.session_state["cn_taken"]
    for t in taken:
        if t["subject"] == subject:
            if t["status"] == status:
                taken.remove(t)
            else:
                t["status"] = status
                t["type"] = typ or t.get("type", "")
            return
    taken.append({"subject": subject, "status": status, "type": typ})


def _sub_label(typ, subject):
    """과목명 목록에 유형(일반/진로/융합) 접두를 붙인 표시용 라벨(순수 텍스트 —
    st.expander 라벨처럼 HTML을 못 쓰는 자리용)."""
    return f"{typ} · {subject}" if typ else subject


PILL_CODE = {"일반": "il", "진로": "jr", "융합": "yh"}


def _pill_html(typ):
    code = PILL_CODE.get(typ)
    return f'<span class="cn-pill {code}">{typ}</span>' if code else ""


def _sub_row_html(typ, subject, bullet="•"):
    """유형 필(pill) + 불릿 + 과목명 — HTML 렌더 가능한 자리(st.markdown unsafe_allow_html)용."""
    pill = _pill_html(typ)
    mid = f" {bullet} " if bullet else " "
    return f"{pill}{mid}{subject}" if pill else f"{bullet} {subject}".strip()


def _plan_subjects():
    return {p["subject"] for p in st.session_state["cn_plan"]}


# ──────────────────────────────────────────────────────────────────
# S0 — 학교·학년
# ──────────────────────────────────────────────────────────────────
def render_s0():
    st.markdown("## 과목선택 내비게이터")
    st.markdown('<p class="cn-sub">네 학교에서 실제로 신청할 수 있는 과목으로 알려줄게</p>',
                unsafe_allow_html=True)

    p = st.session_state["cn_profile"]
    sidos = R.school_sidos()
    c1, c2, c3 = st.columns(3)
    with c1:
        sido = st.selectbox("시도", ["(선택)"] + sidos, key="cn_sido")
    guguns = R.school_guguns(sido) if sido != "(선택)" else []
    with c2:
        gugun = st.selectbox("시군구", ["(선택)"] + guguns, key="cn_gugun",
                              disabled=not guguns)
    schools = R.school_options(sido, gugun) if (guguns and gugun != "(선택)") else []
    labels = [f'{o["school"]}  ·  {o["n_subj"]}과목' for o in schools]
    with c3:
        pick = st.selectbox("학교", ["(선택)"] + labels, key="cn_school",
                             disabled=not labels)

    if labels and pick != "(선택)":
        o = schools[labels.index(pick)]
        p["sido"], p["gugun"] = sido, gugun
        p["school_id"], p["school_name"] = o["shl_idf_cd"], o["school"]
        st.success(f"✓ {o['school']} 선택됨")
    else:
        p["school_id"], p["school_name"] = "", ""

    st.markdown("**학년**")
    grade = st.radio("학년", ["고1", "고2"], key="cn_grade_radio",
                      horizontal=True, label_visibility="collapsed")
    p["grade"] = grade
    if grade == "고1":
        sem = st.radio("학기", ["1학기", "2학기"], key="cn_sem_radio",
                        horizontal=True, label_visibility="collapsed")
        p["semester"] = 1 if sem == "1학기" else 2

    st.markdown(
        '<div class="cn-banner">지금은 2025년 이후 입학생(2022 개정 교육과정, 고1·고2)만 '
        '도와줄 수 있어요.</div>', unsafe_allow_html=True)

    if st.button("시작하기 →", type="primary", use_container_width=True,
                 disabled=not p["school_id"]):
        _go("s1")
    st.caption("학교 과목 정보: 학교알리미 2025·2026 공시 기준")


# ──────────────────────────────────────────────────────────────────
# S1 — 관심 입력
# ──────────────────────────────────────────────────────────────────
def render_s1():
    p = st.session_state["cn_profile"]
    if st.button("← 뒤로"):
        _back()
    st.caption(f'{p["school_name"]} · {p["grade"]}')
    st.markdown("### 요즘 뭐가 제일 끌려?")
    st.markdown('<p class="cn-sub">한 마디면 충분해</p>', unsafe_allow_html=True)

    utterance = st.text_input("발화", key="cn_speech_input",
                               placeholder="예: 동물 돌보는 일이 좋아요",
                               label_visibility="collapsed")

    st.markdown("아니면 골라봐 (2~3개)")
    chips = st.session_state["cn_interests"]["chips"]
    with st.container(key="cn_chip_grid"):
        for row_start in range(0, len(CHIPS), 4):
            cols = st.columns(4)
            for c, (label, emoji) in zip(cols, CHIPS[row_start:row_start + 4]):
                sel = label in chips
                with c:
                    if st.button(f"{emoji}\n{label}", key=f"cn_chip_{label}",
                                 use_container_width=True,
                                 type="primary" if sel else "secondary"):
                        if sel:
                            chips.remove(label)
                        elif len(chips) < 3:
                            chips.append(label)
                        st.rerun()

    if st.button("말한 걸로 찾기", type="primary", use_container_width=True):
        st.session_state["cn_interests"]["utterance"] = utterance
        if not utterance.strip() and not chips:
            st.warning("한 마디만 말해주거나 칩을 하나 골라줘.")
        else:
            chip_only = not utterance.strip() and bool(chips)
            speech = f"{utterance} {' '.join(chips)}".strip()
            with st.spinner("관심사를 분석해 학과·직업을 찾는 중…"):
                out = R.recommend(speech, top_n=8, pair_k=5)
            dae_groups = {}
            for m in out["majors"]:
                for dae in (MAJOR_TO_DAE.get(m["name"]) or {"기타"}):
                    dae_groups.setdefault(dae, []).append(m)
            ordered = sorted(dae_groups, key=lambda d: -max(x["score"] for x in dae_groups[d]))[:3]
            categories = [{
                "dae": d, "emoji": DAE_EMOJI.get(d, "🧭"),
                "majors": [{
                    "name": m["name"], "summary": _major_summary(m["name"]),
                    "reason": _reason_sentence(m["reasons"], chip_only),
                } for m in dae_groups[d][:3]],
            } for d in ordered]
            jobs = [{
                "name": j["name"], **_job_meta(j["name"]),
                "reason": _reason_sentence(j["reasons"], chip_only),
            } for j in out["jobs"][:6]]
            st.session_state["cn_candidates"] = {
                "empty": not out["majors"] and not out["jobs"],
                "categories": categories, "jobs": jobs,
            }
            _go("s2")


# ──────────────────────────────────────────────────────────────────
# S2 — 갈래 → 후보 카드
# ──────────────────────────────────────────────────────────────────
def render_s2():
    c = st.session_state["cn_candidates"]
    if not c:
        _go("s1")
        return
    if st.button("← 뒤로"):
        _back()
    st.markdown("### 이런 갈래로 이어져")

    if c["empty"]:
        st.info("맞는 걸 못 찾았어. 이렇게 말해볼래?\n\n"
                 "\"동물 돌보는 일\" · \"그림 그리는 거\" · \"사람들 앞에서 말하는 거\"")
        if st.button("다시 입력하기"):
            _go("s1")
        return

    st.markdown('<p class="cn-sub">점수·순위는 없어. 근거만 보여줄게</p>', unsafe_allow_html=True)
    for cat in c["categories"]:
        with st.container(key=f"cn_cat_{cat['dae']}"):
            st.markdown(f'<div class="cn-card"><div class="cn-cathead">'
                        f'{cat["emoji"]} {cat["dae"]}</div>', unsafe_allow_html=True)
            for m in cat["majors"]:
                st.markdown(
                    f'<div class="cn-major"><div class="name">{m["name"]}</div>'
                    + (f'<div class="summary">{m["summary"]}</div>' if m["summary"] else "")
                    + f'<div class="reason">근거: {m["reason"]}</div></div>',
                    unsafe_allow_html=True)
                if st.button(f"{m['name']} 선택", key=f"cn_pick_{cat['dae']}_{m['name']}",
                             use_container_width=True):
                    st.session_state["cn_current_major"] = m["name"]
                    _go("s3")
            st.markdown("</div>", unsafe_allow_html=True)

    if st.button("다른 갈래 볼래"):
        _go("s1")


# ──────────────────────────────────────────────────────────────────
# S3 — 학과 상세 + S3.5 이수체크(인라인)
# ──────────────────────────────────────────────────────────────────
def render_s3():
    name = st.session_state["cn_current_major"]
    if not name:
        _go("s2")
        return
    if st.button("← 뒤로"):
        _back()
    st.markdown(f"### {name}")
    st.markdown("2·3학년 때 이런 과목이 도움 돼")
    st.caption("커리어넷 학과정보 기준")

    rec = R.major_by_name(name)
    subjects = R.subjects_of_major(rec)
    # (유형, 과목) 쌍으로 유지 — 같은 과목명이 일반/진로 등 유형에 걸쳐 중복 등장하는
    # 학과가 실제로 있어(예: 컴퓨터시스템과의 '인공지능 수학'), 위젯 key에 유형을 반드시 섞는다.
    all_subs = [(typ, s) for typ in ("일반", "진로", "융합") for s in subjects.get(typ, [])]

    for typ in ("일반", "진로", "융합"):
        subs = subjects.get(typ, [])
        if not subs:
            continue
        st.markdown(f"**{typ}선택**")
        for s in subs:
            st_status = _taken_status(s)
            badge = ""
            if st_status == "이수함":
                badge = ' <span class="cn-badge done">✓ 하는 중</span>'
            elif st_status == "신청함":
                badge = ' <span class="cn-badge applied">📝 신청함</span>'
            with st.expander(_sub_label(typ, s) + ("" if not badge else "  " + ("✓" if st_status == "이수함" else "📝")),
                              expanded=False, key=f"cn_exp_{typ}_{s}"):
                ach = R.achievements_for_subject(s)
                items = ach.get("items") if ach else []
                if not items:
                    st.caption("성취기준 정보가 아직 없어.")
                else:
                    show_all_key = f"cn_ach_all_{typ}_{s}"
                    show_all = st.session_state.get(show_all_key, False)
                    shown = items if show_all else items[:3]
                    for it in shown:
                        st.markdown(f"- \"{it['text']}\"")
                    if len(items) > 3:
                        if show_all:
                            if st.button("접기", key=f"cn_ach_less_{typ}_{s}"):
                                st.session_state[show_all_key] = False
                                st.rerun()
                        else:
                            if st.button(f"성취기준 전체보기 ({len(items)}개)",
                                         key=f"cn_ach_more_{typ}_{s}"):
                                st.session_state[show_all_key] = True
                                st.rerun()

    extra = R.major_extra(rec)
    univ = extra.get("설치대학", {})
    with st.expander("설치대학 더 보기"):
        by_region = univ.get("by_region", {})
        if by_region:
            for region, unis in by_region.items():
                names = ", ".join(u["대학명"] for u in unis[:8])
                st.markdown(f"- **{region}**: {names}")
        else:
            st.caption("설치대학 정보가 아직 없어.")

    st.divider()
    seen = name in st.session_state["cn_seen_sheet_for"]
    if not seen:
        st.markdown("#### 확인 전에 하나만!")
        st.caption("이 중에 벌써 듣고 있는 게 있어? (없으면 건너뛰어도 돼)")
        st.markdown(
            '<div class="cn-banner">1학년 공통과목(국어·수학·통합과학 등)은 체크 안 해도 돼</div>',
            unsafe_allow_html=True)
        for typ, s in all_subs:
            cur = _taken_status(s)
            cols = st.columns([3, 1, 1])
            cols[0].markdown(_sub_row_html(typ, s), unsafe_allow_html=True)
            if cols[1].button("들었어", key=f"cn_take_{typ}_{s}",
                               type="primary" if cur == "이수함" else "secondary"):
                _set_taken(s, "이수함", typ)
                st.rerun()
            if cols[2].button("신청해뒀어", key=f"cn_apply_{typ}_{s}",
                               type="primary" if cur == "신청함" else "secondary"):
                _set_taken(s, "신청함", typ)
                st.rerun()
        c1, c2 = st.columns(2)
        if c1.button("건너뛰기", use_container_width=True):
            st.session_state["cn_seen_sheet_for"].append(name)
            _go("s4")
        if c2.button("확인하러 가기", type="primary", use_container_width=True):
            st.session_state["cn_seen_sheet_for"].append(name)
            _go("s4")
    else:
        if st.button("우리 학교에 있는지 확인 →", type="primary", use_container_width=True):
            _go("s4")


# ──────────────────────────────────────────────────────────────────
# S4 — 우리 학교 개설여부 × 내 이수 현황
# ──────────────────────────────────────────────────────────────────
@st.dialog("과목 선택이 합불을 정하지 않아요")
def _first_visit_modal():
    st.write("어떤 과목을 골랐는지가 대학 합격을 결정하지 않아. "
             "참고만 하고, 진짜 결정은 담임선생님과 함께해줘.")
    if st.button("알겠어", type="primary", use_container_width=True):
        st.session_state["cn_first_visit_modal_shown"] = True
        st.rerun()


def render_s4():
    name = st.session_state["cn_current_major"]
    p = st.session_state["cn_profile"]
    if st.button("← 뒤로"):
        _back()

    if not st.session_state["cn_first_visit_modal_shown"]:
        _first_visit_modal()

    st.markdown(f"### {p['school_name']} 개설 현황")
    st.caption("2025·2026 공시 기준")

    rec = R.major_by_name(name)
    avail = R.subject_availability(rec, p["school_id"])
    plan_set = _plan_subjects()

    rows = []
    c_have = c_can = c_no = c_q = 0
    for typ in ("일반", "진로", "융합"):
        for item in avail["by_type"].get(typ, []):
            subj = item["subject"]
            st_status = _taken_status(subj)
            if not avail["have_school"]:
                kind = "q"; c_q += 1
            elif st_status == "이수함":
                kind = "done"; c_have += 1
            elif st_status == "신청함":
                kind = "applied"; c_have += 1
            elif item["offered"]:
                kind = "ok"; c_can += 1
            else:
                kind = "no"; c_no += 1
            rows.append((typ, subj, kind))

    st.markdown(
        f'<div class="cn-summary"><b>{name}</b> 권장 {len(rows)}과목 중<br>'
        f'이미 하는 중 <b>{c_have}</b> · 담을 수 있어 <b>{c_can}</b> · '
        f'우리 학교엔 없어 <b>{c_no}</b> · 확인 필요 <b>{c_q}</b></div>',
        unsafe_allow_html=True)

    if not avail["have_school"]:
        st.markdown('<div class="cn-banner warn">이 학교 과목 정보가 아직 없어 — '
                    '담임선생님께 확인해줘.</div>', unsafe_allow_html=True)

    # 같은 과목명이 일반/진로 등 유형에 걸쳐 중복 등장할 수 있어(예: '인공지능 수학')
    # 과목명 기준으로 한 번만 담되, 처음 만난 유형을 표시용으로 남긴다.
    seen_subj = set()
    selectable = []
    for typ, subj, kind in rows:
        if kind == "ok" and subj not in plan_set and subj not in seen_subj:
            seen_subj.add(subj)
            selectable.append((typ, subj))
    sel_key = lambda typ, subj: f"cn_sel_{name}_{typ}_{subj}"  # noqa: E731

    def _toggle_select_all():
        val = st.session_state[f"cn_selall_{name}"]
        for typ, subj in selectable:
            st.session_state[sel_key(typ, subj)] = val

    if selectable:
        hc1, hc2 = st.columns([3, 2])
        with hc1:
            st.checkbox(f"전체선택 ({len(selectable)}과목)", key=f"cn_selall_{name}",
                        on_change=_toggle_select_all)
        with hc2:
            if st.button("체크한 항목 담기", key="cn_add_checked",
                         type="primary", use_container_width=True):
                to_add = [(typ, subj) for typ, subj in selectable
                          if st.session_state.get(sel_key(typ, subj))]
                if not to_add:
                    st.warning("체크한 과목이 없어.")
                else:
                    for typ, subj in to_add:
                        st.session_state["cn_plan"].append(
                            {"subject": subj, "from_major": name, "type": typ})
                        st.session_state[sel_key(typ, subj)] = False
                    st.session_state[f"cn_selall_{name}"] = False
                    st.rerun()

    hcols = st.columns([1.1, 3, 1.6, 0.6])
    hcols[0].caption("구분")
    hcols[1].caption("과목")
    hcols[3].caption("선택")

    for typ, subj, kind in rows:
        bullet = "⬜" if kind == "no" else "❓" if kind == "q" else "•"
        cols = st.columns([1.1, 3, 1.6, 0.6])
        with cols[0]:
            st.markdown(_pill_html(typ), unsafe_allow_html=True)
        cols[1].markdown(f"{bullet} {subj}")
        with cols[2]:
            if kind == "done":
                st.markdown('<span class="cn-badge done">✓ 하는 중</span>', unsafe_allow_html=True)
            elif kind == "applied":
                if st.button("신청해뒀네 →", key=f"cn_appl_{typ}_{subj}", use_container_width=True):
                    if subj not in plan_set:
                        st.session_state["cn_plan"].append(
                            {"subject": subj, "from_major": name, "type": typ})
                    st.toast("목록에 담아뒀어. 마음이 바뀌면 목록에서 뺄 수 있어.")
                    st.rerun()
            elif kind == "ok":
                if subj in plan_set:
                    st.markdown('<span class="cn-badge done">담음</span>', unsafe_allow_html=True)
                elif st.button("목록에 담기", key=f"cn_add_{typ}_{subj}", use_container_width=True):
                    st.session_state["cn_plan"].append(
                        {"subject": subj, "from_major": name, "type": typ})
                    st.rerun()
            elif kind == "no":
                if st.button("대안 보기 →", key=f"cn_alt_{typ}_{subj}", use_container_width=True):
                    st.session_state["cn_alt_subject"] = subj
                    st.session_state["cn_alt_type"] = typ
                    _go("s6")
            else:
                st.markdown('<span class="cn-badge q">담임 확인</span>', unsafe_allow_html=True)
        with cols[3]:
            if kind == "ok" and subj not in plan_set:
                st.checkbox("선택", key=sel_key(typ, subj), label_visibility="collapsed")

    st.markdown('<div class="cn-banner">ⓘ 신청 전 담임선생님과 꼭 확인해줘</div>',
                unsafe_allow_html=True)
    if st.button("내 목록 보기 →", type="primary", use_container_width=True):
        _go("s5")


# ──────────────────────────────────────────────────────────────────
# 공유 링크 (URL 쿼리파라미터 직렬화 — 서버 저장 없음)
# ──────────────────────────────────────────────────────────────────
def _encode_share():
    payload = {
        "profile": st.session_state["cn_profile"],
        "taken": st.session_state["cn_taken"],
        "plan": st.session_state["cn_plan"],
        "interests": st.session_state["cn_interests"],
    }
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_share(token):
    pad = "=" * (-len(token) % 4)
    raw = base64.urlsafe_b64decode(token + pad)
    return json.loads(raw.decode("utf-8"))


# ──────────────────────────────────────────────────────────────────
# S5 — 담임쌤과 상의할 목록 (결승선)
# ──────────────────────────────────────────────────────────────────
def render_s5():
    p = st.session_state["cn_profile"]
    if st.button("← 뒤로"):
        _back()
    st.markdown("### 담임쌤과 상의할 목록")
    st.markdown(
        '<div class="cn-banner">실제 개설 학년·학기와 신청 가능 개수는 학교 편제표에 따라 '
        '달라 — 그래서 담임쌤과 상의가 필요해</div>', unsafe_allow_html=True)

    plan = st.session_state["cn_plan"]
    if not plan:
        st.info("아직 담은 게 없어.")
        if st.button("추천으로 돌아갈래?"):
            _go("s2")
        return

    st.markdown("**상의할 과목**")
    for i, item in enumerate(list(plan)):
        cols = st.columns([4, 1])
        tag = " 📝" if _taken_status(item["subject"]) == "신청함" else ""
        cols[0].markdown(_sub_row_html(item.get("type", ""), item["subject"]) + tag,
                          unsafe_allow_html=True)
        if cols[1].button("빼기", key=f"cn_rm_{i}"):
            plan.pop(i)
            st.rerun()

    taken = st.session_state["cn_taken"]
    if taken:
        st.markdown("**이미 듣고 있거나 신청한 과목**")
        for t in taken:
            mark = "✓" if t["status"] == "이수함" else "📝"
            st.markdown(mark + " " + _sub_row_html(t.get("type", ""), t["subject"]),
                        unsafe_allow_html=True)

    majors = sorted({item["from_major"] for item in plan})
    st.markdown(f'<div class="cn-sub">이 목록이 이어주는 진로: <b>{" · ".join(majors)}</b></div>',
                unsafe_allow_html=True)

    if st.button("공유 링크 만들기", type="primary", use_container_width=True):
        st.query_params["share"] = _encode_share()
        st.success("주소창의 링크를 복사해서 담임선생님께 보내줘.")
    st.caption(f"학교: {p['school_name']} · {p['grade']}"
               + (f" {p['semester']}학기" if p["grade"] == "고1" else ""))


# ──────────────────────────────────────────────────────────────────
# S6 — 미개설 대안
# ──────────────────────────────────────────────────────────────────
def render_s6():
    subj = st.session_state["cn_alt_subject"] or ""
    typ = st.session_state.get("cn_alt_type", "")
    if st.button("← 뒤로"):
        _back()
    st.markdown(f"### '{_sub_row_html(typ, subj, bullet='')}'이 우리 학교에 없을 때",
                unsafe_allow_html=True)
    st.markdown('<p class="cn-sub">안 열렸다고 길이 닫힌 건 아니야</p>', unsafe_allow_html=True)

    st.markdown(
        '<div class="cn-card"><div class="cn-cathead">① 학교 밖에서 듣는 길</div>'
        '· 학교 간 공동교육과정<br>· 시도 온라인학교 / 교실온닷<br>'
        '(담임선생님·교육과정부장님께 문의해줘)</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="cn-banner">ⓘ 개설 신청이 많으면 학교가 열기도 해 — '
        '수요조사에 꼭 적어봐</div>', unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────
# S7 — 공유 링크 읽기전용 뷰
# ──────────────────────────────────────────────────────────────────
def render_s7_read(data):
    st.markdown("### 학생 플랜 요약")
    prof = data.get("profile", {})
    st.markdown(f"**{prof.get('school_name','')} · {prof.get('grade','')}**")
    interests = data.get("interests", {})
    st.caption(f"관심: {interests.get('utterance') or ', '.join(interests.get('chips', [])) or '-'}")

    st.markdown("**상의할 과목**")
    plan = data.get("plan", [])
    if plan:
        for item in plan:
            st.markdown(_sub_row_html(item.get("type", ""), item["subject"]),
                        unsafe_allow_html=True)
    else:
        st.caption("아직 없음")

    st.markdown("**이수 체크**")
    taken = data.get("taken", [])
    if taken:
        for t in taken:
            mark = "✓" if t["status"] == "이수함" else "📝"
            st.markdown(mark + " " + _sub_row_html(t.get("type", ""), t["subject"]),
                        unsafe_allow_html=True)
    else:
        st.caption("아직 없음")

    st.caption("데이터: 학교알리미 2025·2026 공시 기준 · 학생 셀프체크 기반(참고용)")
    if st.button("나도 해보기", type="primary"):
        st.query_params.clear()
        st.rerun()


# ──────────────────────────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────────────────────────
if "share" in st.query_params:
    try:
        render_s7_read(_decode_share(st.query_params["share"]))
    except Exception:
        st.error("공유 링크를 읽을 수 없어.")
else:
    _init_state()
    STEP_RENDER = {
        "s0": render_s0, "s1": render_s1, "s2": render_s2, "s3": render_s3,
        "s4": render_s4, "s5": render_s5, "s6": render_s6,
    }
    STEP_RENDER.get(st.session_state["cn_step"], render_s0)()
