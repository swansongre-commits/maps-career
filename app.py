# -*- coding: utf-8 -*-
"""
진로 발화 → 학과·직업 추천 웹서비스 (Streamlit)

흐름:  ① 관심사 발화(어린이~고교생) → 키워드 추출(쉬운말 매칭) →
       ② 추천 결과(학과 | 직업) — 항목 클릭 시 모달로 상세(설치대학·선택과목 아코디언)
       · 학교별 개설과목 보기(옵션): 체크박스 → 모달로 시도>시군구>학교 선택(3depth)

디자인: GMK Fabrik 컬러웨이(다크 블루 베이스 + 화이트 레전드 + 러스티 오렌지 액센트).

실행:  streamlit run app.py
필요 파일: recommender.py, tokenizer.py, llm_extract.py,
          majors_keywords.json, jobs_keywords.json, mapping_major.csv, mapping_job.csv,
          mapping_univ.json, schools.db(고교 개설과목 2025·2026 병합), vocab_2022.json,
          stopwords.json, compounds.json
"""
import streamlit as st

st.set_page_config(page_title="진로 추천", page_icon="🎓", layout="wide")


@st.cache_resource
def load_engine():
    import recommender
    return recommender


R = load_engine()

import re
from urllib.parse import quote

VIA_BADGE = {"공시": "🟦", "쉬운말": "🟩"}

# 대학명 클릭 → EBSi 대학 검색(새창). 괄호 캠퍼스 표기는 검색어에서 제거.
EBSI_BASE = ("https://www.ebsi.co.kr/ebs/ent/entNgf/retrieveEntNgfUnivList.ebs"
             "?srchUnivNm=")


def _ebsi_url(name):
    base = re.sub(r"\(.*?\)", "", str(name)).strip() or str(name)
    return EBSI_BASE + quote(base)


def univ_link(name):
    return f'<a href="{_ebsi_url(name)}" target="_blank">{name}</a>'

# ── 화이트 베이스 팔레트 · 강한 CTA(비비드 오렌지) ──
FABRIK = {
    "bg": "#FFFFFF",        # 페이지 배경(흰색)
    "surface": "#F4F6F8",   # 카드/사이드바 표면(연한 그레이)
    "surface2": "#FFFFFF",  # 버튼/행 표면(흰색)
    "border": "#DCE1E7",    # 보더(연한 그레이)
    "cta": "#FF6A2C",       # 강한 CTA(비비드 오렌지)
    "cta_dim": "#E25419",
    "cta_soft": "#FFF1E9",  # CTA 연한 배경
    "navy": "#2B3D6B",      # 활성 탭 글자(네이비)
    "tabbg": "#F5F6F8",     # 비활성 탭 배경
    "text": "#1E2530",      # 본문 텍스트(니어 블랙)
    "muted": "#8A929C",     # 보조/비활성 텍스트
}

CSS = f"""
<style>
.stApp {{ background: {FABRIK['bg']}; color: {FABRIK['text']}; }}
h1, h2, h3, h4, h5, h6 {{ color: {FABRIK['text']}; letter-spacing: -0.2px; }}
section[data-testid="stSidebar"] {{ background: {FABRIK['surface']}; border-right: 1px solid {FABRIK['border']}; }}

/* 결과 칼럼(테두리 컨테이너) */
div[data-testid="stVerticalBlockBorderWrapper"] {{
    background: {FABRIK['surface']};
    border: 1px solid {FABRIK['border']} !important;
    border-radius: 14px;
}}

/* ── 탭 헤더: 셀형(EBSi 스타일) · 활성=흰배경 네이비 굵게 / 비활성=회색 ── */
div[data-baseweb="tab-list"] {{
    gap: 0;
    border-bottom: 1px solid {FABRIK['border']};
}}
button[data-baseweb="tab"] {{
    flex: 1 1 0;
    justify-content: center;
    text-align: center;
    color: {FABRIK['muted']};
    background: {FABRIK['tabbg']};
    border: 1px solid {FABRIK['border']};
    border-right: none;
    border-radius: 0;
    padding: 0.75rem 0;
    font-weight: 600;
    margin-bottom: -1px;
}}
button[data-baseweb="tab"]:last-child {{ border-right: 1px solid {FABRIK['border']}; }}
button[data-baseweb="tab"]:hover {{ color: {FABRIK['navy']}; background: #ECEFF3; }}
/* 활성 탭 — 흰 배경 + 네이비 굵은 글자 + 하단 라인 제거(본문과 연결) */
button[data-baseweb="tab"][aria-selected="true"] {{
    color: {FABRIK['navy']};
    background: {FABRIK['bg']};
    border-bottom: 1px solid {FABRIK['bg']};
    font-weight: 800;
}}
button[data-baseweb="tab"][aria-selected="true"] p {{ font-weight: 800; color: {FABRIK['navy']}; font-size: 1.02rem; }}
div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] {{ background-color: transparent; }}

/* 추천 항목 버튼 = 한 줄 리스트 행 */
div[data-testid="stButton"] > button {{
    width: 100%;
    text-align: left;
    background: {FABRIK['surface2']};
    color: {FABRIK['text']};
    border: 1px solid {FABRIK['border']};
    border-radius: 10px;
    padding: 0.55rem 0.85rem;
    font-weight: 600;
    transition: all .12s ease;
}}
div[data-testid="stButton"] > button p {{ text-align: left; margin: 0; }}
div[data-testid="stButton"] > button:hover {{
    border-color: {FABRIK['cta']};
    background: {FABRIK['cta_soft']};
    transform: translateY(-1px);
}}

/* 기본(primary) 버튼 = 강한 CTA */
div[data-testid="stButton"] > button[kind="primary"] {{
    background: {FABRIK['cta']};
    color: #FFFFFF;
    border: 1px solid {FABRIK['cta']};
    text-align: center;
    box-shadow: 0 2px 12px {FABRIK['cta']}40;
}}
div[data-testid="stButton"] > button[kind="primary"] p {{ text-align: center; color: #FFFFFF; }}
div[data-testid="stButton"] > button[kind="primary"]:hover {{ background: {FABRIK['cta_dim']}; }}

/* 모달(dialog) — 흰 배경 위에서 떠 보이게 그림자·CTA 라인 */
div[role="dialog"], div[data-testid="stDialog"] > div > div {{
    border: 1px solid {FABRIK['border']} !important;
    border-top: 4px solid {FABRIK['cta']} !important;
    border-radius: 14px !important;
    box-shadow: 0 18px 50px rgba(30,37,48,0.28) !important;
}}
div[data-testid="stDialogOverlay"] {{ background: rgba(30,37,48,0.45) !important; }}

/* 아코디언 */
details {{ border-radius: 10px !important; border: 1px solid {FABRIK['border']} !important;
          background: {FABRIK['surface2']}; }}

/* 코드/키워드 칩 */
code {{ background: {FABRIK['cta']}1A; color: {FABRIK['cta_dim']}; border-radius: 6px; padding: 1px 6px; }}
hr {{ border-color: {FABRIK['border']}; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def reason_line(reasons, limit=8):
    parts = []
    for x in reasons[:limit]:
        b = VIA_BADGE.get(x["via"], "")
        parts.append(f'{b} `{x["term"]}` ({x["rank"]}위·{x["points"]}점)')
    return "  ".join(parts)


def parse_universities_legacy(raw):
    """구(舊) mapping_major.csv '개설대학' 문자열 폴백 파서('지역_대학' 형태)."""
    items = [x.strip() for x in raw.split(",") if x.strip()]
    by_region = {}
    for it in items:
        parts = it.split("_")
        region = parts[0] if parts else "기타"
        uni = parts[1] if len(parts) > 1 else it
        by_region.setdefault(region, []).append(uni)
    return by_region, len(items)


# %% [공용 헬퍼 · 모달 · 상세 렌더]
def _safe_select(label, options, key, disabled=False):
    """저장된 값이 현재 옵션에 없으면 위젯 생성 전에 제거(계단식 변경 시 오류 방지)."""
    if key in st.session_state and st.session_state[key] not in options:
        del st.session_state[key]
    return st.selectbox(label, options, key=key, disabled=disabled)


def _render_major_detail(r):
    extra = R.major_extra(r)
    univ = extra.get("설치대학", {})
    if univ.get("univ_count", 0) > 0:
        with st.expander(f"🏛️ 설치대학 ({univ['univ_count']}곳) · 지역·전형·인원  ·  대학명 클릭 시 EBSi"):
            for region, unis in univ["by_region"].items():
                st.markdown(f"**{region}** ({len(unis)}곳)")
                for u in unis:
                    jh = ", ".join(u["전형"][:4]) if u["전형"] else "전형정보 없음"
                    cap = f" · 모집 {u['인원']}명" if u.get("인원") else ""
                    st.markdown(f"- {univ_link(u['대학명'])} — {jh}{cap}",
                                unsafe_allow_html=True)
    else:
        uni = extra.get("개설대학", "")
        if uni:
            by_region, total = parse_universities_legacy(uni)
            with st.expander(f"🏛️ 개설대학 ({total}곳)  ·  대학명 클릭 시 EBSi"):
                for region, unis in list(by_region.items())[:8]:
                    links = ", ".join(univ_link(u) for u in sorted(set(unis))[:6])
                    st.markdown(f"- **{region}**: {links}", unsafe_allow_html=True)

    subj = R.subjects_of_major(r)
    n_subj = sum(len(v) for v in subj.values())
    if n_subj:
        with st.expander(f"📘 2022 선택과목 ({n_subj}개)"):
            for typ in ("일반", "진로", "융합"):
                items = subj[typ]
                if items:
                    st.markdown(f"**{typ} 선택**: {', '.join(items)}")
            st.caption("‘학교별 설치과목’ 탭에서 특정 고교의 개설 과목을 확인할 수 있어요.")

    rel = extra.get("관련직업", "")
    if rel:
        jobs = R.split_related_jobs(rel)
        with st.expander(f"💼 관련 직업 ({len(jobs)})"):
            st.markdown(", ".join(jobs))


def _render_school_detail(r):
    """학교 상세 — 개설과목(유형별), 각 과목 클릭 시 연관 학과 모달."""
    info = R.school_subjects(r["shl_idf_cd"])
    st.markdown(f"### 🏫 {info['school']}  ·  {info['sido']} {info['gugun']}")
    st.caption(f"개설 과목 {info['n_subj']}개 (학교알리미 2025·2026 병합 기준). "
               "과목을 누르면 그 과목과 연관된 학과를 보여줍니다.")
    for typ in ("일반", "진로", "융합"):
        subs = info["by_type"][typ]
        if not subs:
            continue
        st.markdown(f"**{typ} 선택 ({len(subs)})**")
        cols = st.columns(3)
        for k, s in enumerate(subs):
            with cols[k % 3]:
                if st.button(s, key=f"schsub_{r['shl_idf_cd']}_{typ}_{s}",
                             use_container_width=True):
                    subject_majors_modal(s)


def _render_job_detail(r):
    extra = R.job_extra(r)
    rel = extra.get("관련학과", "")
    if rel:
        majors = R.split_related_majors(rel)
        with st.expander(f"📚 관련 학과 ({len(majors)})", expanded=True):
            st.markdown(", ".join(majors))
    cert = extra.get("관련자격", "")
    if cert:
        certs = [c.strip() for c in cert.replace("·", ",").split(",") if c.strip()]
        with st.expander(f"📜 관련 자격 ({len(certs)})"):
            st.markdown(", ".join(certs))


@st.dialog("상세 정보", width="large")
def detail_modal(kind, r):
    icon = "📚" if kind == "major" else "💼"
    st.markdown(f"### {icon} {r['name']}  ·  점수 {r['score']}")
    st.markdown("**추천 근거** — " + reason_line(r["reasons"]))
    st.markdown("---")
    if kind == "major":
        _render_major_detail(r)
    else:
        _render_job_detail(r)


@st.dialog("과목 연관 학과", width="large")
def subject_majors_modal(subject_name):
    st.markdown(f"### 📘 {subject_name}")
    sort_score = st.toggle("키워드 점수순 정렬", value=True, key="sm_sort",
                           help="끄면 가나다순으로 봅니다.")
    majors = R.majors_for_subject(subject_name, sort_by_score=sort_score)
    st.caption(f"이 과목을 2022 권장 선택과목으로 두는 학과 {len(majors)}개")
    if not majors:
        st.info("연관 학과가 없어요.")
        return
    for m in majors:
        st.markdown(f"- **{m['name']}**"
                    + (f"  ·  {m['score']}점" if sort_score else ""))


# %% [헤더 · 사이드바]
st.title("🎓 진로 추천")
st.caption("관심사 발화로 **학과·직업**을 추천받고, **학교별 개설과목**과 **학과 정보**를 함께 탐색하세요.")

with st.sidebar:
    st.subheader("설정")
    topn = st.slider("추천 개수", 3, 10, 5)
    pair_k = st.slider("연계 페어 개수", 3, 9, 5)
    import llm_extract
    llm_ready = llm_extract.available()
    use_llm = st.checkbox(
        "LLM 발화 이해 사용", value=llm_ready, disabled=not llm_ready,
        help=("OPENAI_API_KEY 가 설정되어 있어야 켤 수 있습니다. "
              "추상적인 발화(예: '남 도와주는 일')도 표준 키워드로 변환합니다. "
              "실패 시 규칙 기반으로 자동 전환됩니다."))
    if not llm_ready:
        st.caption("🔒 OPENAI_API_KEY 미설정 — 규칙 기반으로 동작")
    st.markdown("---")
    st.caption("범례")
    st.markdown("🟦 공시 키워드(원문)  ·  🟩 쉬운말로 매칭")

TAB_REC, TAB_SCHOOL, TAB_MAJOR = st.tabs(
    ["🎯 학과·직업 추천", "🏫 학교별 설치과목", "📚 학과별 정보"])


# %% [탭1 — 학과·직업 추천]
with TAB_REC:
    examples = [
        "나는 로봇이랑 똑똑한 기계가 좋아요. 그림 그리는 건 별로예요.",
        "그림 그리고 꾸미는 거 좋아하고 영상 만드는 것도 재밌어요.",
        "컴퓨터로 게임 만들고 프로그램 짜는 게 좋아요.",
        "동물이랑 식물이 좋고 자연에서 관찰하는 걸 좋아해요.",
        "우주랑 별이 신기하고 과학실험 하는 게 재밌어요.",
    ]
    ex = st.radio("예시 — 클릭하면 입력창에 채워집니다", ["(직접 입력)"] + examples,
                  index=0, horizontal=False)
    default_text = "" if ex == "(직접 입력)" else ex
    speech = st.text_area("관심사·하고 싶은 일을 적어주세요", value=default_text, height=120,
                          placeholder="예) 나는 로봇이랑 우주가 좋아요. 만들고 조립하는 것도 재밌어요.")
    go = st.button("추천 받기", type="primary")

    if go:
        if not speech.strip():
            st.warning("진로 추천에 바탕이 될 내용을 입력해 주세요.")
        else:
            st.session_state["result"] = R.recommend(
                speech, top_n=topn, pair_k=pair_k, use_llm=use_llm)

    out = st.session_state.get("result")
    if not out:
        st.info("관심사를 입력하고 **추천 받기**를 누르면 결과가 여기에 표시됩니다.")
    else:
        meta = out.get("meta", {})
        st.markdown("#### 🔑 뽑아낸 키워드")
        mode_label = "🤖 LLM 발화 이해" if meta.get("mode") == "llm" else "🔧 규칙 기반"
        st.caption(f"추출 방식: {mode_label}"
                   + (f"  ·  {meta['rationale']}" if meta.get("rationale") else ""))
        if meta.get("note"):
            st.caption("ℹ️ " + meta["note"])
        if out["tokens"]:
            st.write(" ".join(f"`{t}`" for t in out["tokens"]))
        else:
            st.warning("키워드를 뽑지 못했어요. 조금 더 자세히 적어보세요.")
        if out["excluded"]:
            st.caption("제외(싫다고 한 것): "
                       + ", ".join(f"~~{t}~~" for t in out["excluded"]))

        st.markdown("#### 🎯 추천 결과  ·  항목을 누르면 상세가 모달로 열립니다")
        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                st.subheader("📚 추천 학과")
                if not out["majors"]:
                    st.info("매칭되는 학과가 없어요.")
                for i, r in enumerate(out["majors"], 1):
                    if st.button(f"{i}.  {r['name']}　·　{r['score']}점",
                                 key=f"maj_{i}", use_container_width=True):
                        detail_modal("major", r)
        with col2:
            with st.container(border=True):
                st.subheader("💼 추천 직업")
                if not out["jobs"]:
                    st.info("매칭되는 직업이 없어요.")
                for i, r in enumerate(out["jobs"], 1):
                    if st.button(f"{i}.  {r['name']}　·　{r['score']}점",
                                 key=f"job_{i}", use_container_width=True):
                        detail_modal("job", r)

        st.markdown("---")
        st.subheader("🔗 학과 ↔ 직업 연계 진로")
        st.caption("추천 상위 학과·직업이 공유하는 키워드가 많을수록 연결이 강합니다.")
        if not out["pairs"]:
            st.info("연계 페어를 만들 수 없어요.")
        for p in out["pairs"]:
            strong = "✅" if p["overlap_n"] >= 3 else ("•" if p["overlap_n"] else "·")
            kws = ", ".join(p["overlap"]) if p["overlap"] else "(공통 키워드 없음)"
            st.markdown(f"{strong} **{p['major']}**  →  **{p['job']}**  "
                        f"· 공통 {p['overlap_n']}개: {kws}")


# %% [탭2 — 학교별 설치과목: 과목으로 찾기 / 학교로 찾기]
with TAB_SCHOOL:
    st.caption(f"학교알리미 2025·2026 공시 병합 · 데이터 보유 전국 {len(R.SCHOOL_DB):,}개교")
    mode = st.radio("찾는 방법", ["과목으로 찾기", "학교로 찾기"], horizontal=True,
                    key="school_tab_mode")

    if mode == "과목으로 찾기":
        st.markdown("##### 📘 과목으로 찾기 — 유형 → 과목을 고르면 "
                    "연관 학과·설치대학·설치학교를 보여줍니다")
        subs = R.subject_list()
        type_opts = ["일반", "진로", "융합"]
        fc1, fc2 = st.columns([1, 2])
        with fc1:
            ftype = st.selectbox("① 과목 유형(카테고리)", type_opts, key="subj_ftype")
        cands = [s for s in subs if s["type"] == ftype]
        labels = [f'{s["name"]}  ·  연관 학과 {s["n_major"]}개' for s in cands]
        with fc2:
            pick = _safe_select("② 과목 선택", ["(선택)"] + labels, "subj_pick")
        if pick == "(선택)":
            st.info("과목 유형을 고른 뒤 과목을 선택하면 결과가 아래에 표시됩니다.")
        else:
            s = cands[labels.index(pick)]
            subject_name = s["name"]
            st.markdown("---")
            st.markdown(f"### 📘 {subject_name}  ·  {ftype} 선택")

            # ── 연관 학과 (정렬 토글) ──
            sort_score = st.toggle("학과 키워드 점수순 정렬", value=False,
                                   key="subj_sort", help="끄면 가나다순")
            majors = R.majors_for_subject(subject_name, sort_by_score=sort_score)
            st.markdown(f"#### 🎓 연관 학과 ({len(majors)})")
            st.caption("이 과목을 2022 권장 선택과목으로 두는 학과")
            if len(majors) > 8:
                show_n = st.slider("표시할 학과 수", 4, min(30, len(majors)),
                                   8, key="subj_majn")
            else:
                show_n = len(majors)
            for m in majors[:show_n]:
                with st.expander(f"**{m['name']}**"
                                 + (f"  ·  {m['score']}점" if sort_score else "")):
                    # 연관 학과의 설치대학
                    uinfo = R.universities_for(m["name"])
                    if uinfo.get("univ_count", 0) > 0:
                        st.markdown(f"**🏛️ 설치대학 {uinfo['univ_count']}곳** "
                                    "· 대학명 클릭 시 EBSi")
                        for region, unis in list(uinfo["by_region"].items()):
                            names_u = ", ".join(univ_link(u["대학명"]) for u in unis[:10])
                            more = f" 외 {len(unis)-10}곳" if len(unis) > 10 else ""
                            st.markdown(f"- **{region}** ({len(unis)}): {names_u}{more}",
                                        unsafe_allow_html=True)
                    else:
                        st.caption("🏛️ 설치대학 정보 없음(전문대·교양학부 등)")

            # ── 이 과목을 개설한 고교 (지역 필터) ──
            st.markdown("#### 🏫 이 과목 설치학교")
            offered_all = R.schools_offering(subject_name)
            st.caption(f"전국 {len(offered_all):,}개교에서 개설")
            sc1, sc2 = st.columns(2)
            with sc1:
                f_sido = _safe_select("시도 필터", ["전체"] + R.school_sidos(),
                                      "subj_sch_sido")
            guguns2 = (R.school_guguns(f_sido) if f_sido != "전체" else [])
            with sc2:
                f_gugun = _safe_select("시군구 필터", ["전체"] + guguns2,
                                       "subj_sch_gugun", disabled=not guguns2)
            offered = R.schools_offering(
                subject_name,
                sido=None if f_sido == "전체" else f_sido,
                gugun=None if f_gugun == "전체" else f_gugun)
            st.caption(f"{len(offered):,}개교")
            for o in offered[:60]:
                st.markdown(f"- {o['sido']} {o['gugun']} · **{o['school']}**")
            if len(offered) > 60:
                st.caption(f"… 외 {len(offered) - 60:,}개교. 지역 필터로 좁혀보세요.")

    else:  # 학교로 찾기
        st.markdown("##### 🏫 학교로 찾기 — 학교를 고르면 개설과목을 보여줍니다")
        sidos = R.school_sidos()
        c1, c2, c3 = st.columns(3)
        with c1:
            sido = _safe_select("시도", ["(선택)"] + sidos, "st_sido")
        guguns = R.school_guguns(sido) if sido != "(선택)" else []
        with c2:
            gugun = _safe_select("시군구", ["(선택)"] + guguns, "st_gugun",
                                 disabled=not guguns)
        schools = (R.school_options(sido, gugun)
                   if (guguns and gugun != "(선택)") else [])
        labels = [f'{o["school"]}  ·  {o["n_subj"]}과목' for o in schools]
        with c3:
            pick = _safe_select("학교", ["(선택)"] + labels, "st_school",
                                disabled=not labels)
        if labels and pick != "(선택)":
            o = schools[labels.index(pick)]
            _render_school_detail({"shl_idf_cd": o["shl_idf_cd"]})
        else:
            st.info("시도 → 시군구 → 학교를 차례로 선택하세요.")


# %% [탭3 — 학과별 정보: 검색+목록 → 상세(설치 고교 보기 포함)]
with TAB_MAJOR:
    st.markdown("##### 📚 학과별 정보 — 학과를 고르면 키워드·설치대학·선택과목을 보여줍니다")
    names = R.major_names()
    mq = st.text_input("학과명 검색", key="major_q", placeholder="예) 시각디자인, 기계, 간호")
    flt = [n for n in names if not mq.strip() or mq.strip() in n]
    st.caption(f"{len(flt)}개 학과")
    sel = st.selectbox("학과 선택", ["(선택)"] + flt, key="major_sel")
    if sel != "(선택)":
        r = R.major_by_name(sel)
        if r:
            st.markdown(f"### 📚 {r['name']}  ·  키워드 점수 {r['score']}")
            st.markdown("**대표 키워드** — " + reason_line(r["reasons"], limit=10))
            st.markdown("---")
            _render_major_detail(r)
            # 설치 고교 보기 — 이 학과 선택과목별 개설 고교 수
            with st.expander("🏫 설치 고교 보기 (선택과목 개설 학교)"):
                subj = R.subjects_of_major(r)
                flat = [s for v in subj.values() for s in v]
                st.caption("이 학과의 권장 선택과목이 전국 몇 개 고교에 개설돼 있는지")
                for s in flat:
                    n = len(R.schools_offering(s))
                    st.markdown(f"- **{s}** — {n:,}개교 개설")
    else:
        st.info("학과를 검색·선택하면 상세 정보가 표시됩니다.")
