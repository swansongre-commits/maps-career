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
import streamlit.components.v1 as components

st.set_page_config(page_title="진로 추천", page_icon="🎓", layout="wide")

# 페이지 언어를 한국어로 명시 → 브라우저 자동 번역 제안 제거
# (Streamlit 기본 <html lang="en">이라 한국어 내용에 번역 팝업이 뜸)
components.html(
    "<script>try{window.parent.document.documentElement.lang='ko';"
    "var m=window.parent.document.querySelector('meta[name=google]')||"
    "window.parent.document.createElement('meta');"
    "m.name='google';m.content='notranslate';"
    "window.parent.document.head.appendChild(m);}catch(e){}</script>",
    height=0,
)


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


def school_table_html(sch):
    """학교 목록 → 한 테이블(헤더 1개). 시도/시군구 행병합 + 시도경계 굵은선,
    학교명은 한 행에 2개씩 배치(가로 공간 활용)."""
    if not sch:
        return ""
    from math import ceil
    # (시도, 시군구) 순서 보존 그룹
    groups = []
    for o in sch:
        if groups and groups[-1][0] == o["sido"] and groups[-1][1] == o["gugun"]:
            groups[-1][2].append(o["school"])
        else:
            groups.append((o["sido"], o["gugun"], [o["school"]]))
    # 시도별 총 행수(각 시군구의 ceil(학교수/2) 합)
    sido_rows = {}
    for sido, gugun, schools in groups:
        sido_rows[sido] = sido_rows.get(sido, 0) + ceil(len(schools) / 2)
    trs = []
    sido_emitted = set()
    for sido, gugun, schools in groups:
        gug_rows = ceil(len(schools) / 2)
        for ri in range(gug_rows):
            pair = schools[ri * 2:ri * 2 + 2]
            cells = ""
            new_sido = sido not in sido_emitted and ri == 0
            if new_sido:
                cells += f"<td class='grp' rowspan='{sido_rows[sido]}'>{sido}</td>"
                sido_emitted.add(sido)
            if ri == 0:
                cells += f"<td class='grp' rowspan='{gug_rows}'>{gugun}</td>"
            s1 = f"<td><b>{pair[0]}</b></td>"
            s2 = f"<td><b>{pair[1]}</b></td>" if len(pair) > 1 else "<td></td>"
            cls = " class='grp-start'" if new_sido else ""
            trs.append(f"<tr{cls}>{cells}{s1}{s2}</tr>")
    return ("<table class='univ-tb'><thead><tr><th>시도</th><th>시군구</th>"
            "<th colspan='2'>학교명</th></tr></thead><tbody>"
            + "".join(trs) + "</tbody></table>")


def pair_card_html(p):
    """연계 진로 1건 → 등식 카드 HTML (📚학과 + 💼직업 = 🧭진로 · 공통 키워드)."""
    strong = " cp-strong" if p["overlap_n"] >= 3 else ""
    if p["overlap"]:
        chips = "".join(f'<span class="cp-chip">{k}</span>' for k in p["overlap"])
        kws = f'공통 키워드 <b>{p["overlap_n"]}</b>개 &nbsp; {chips}'
    else:
        kws = '공통 키워드 없음 (느슨한 연결)'
    return (
        f'<div class="cp-card{strong}">'
        f'<div class="cp-eq">'
        f'<span class="cp-tag cp-tag-major">학과</span>'
        f'<span class="cp-name">{p["major"]}</span>'
        f'<span class="cp-gt">›</span>'
        f'<span class="cp-tag cp-tag-job">직업</span>'
        f'<span class="cp-name">{p["job"]}</span>'
        f'</div>'
        f'<div class="cp-kws">{kws}</div>'
        f'</div>'
    )


# 추천 처리 동안 노출할 전체화면 로딩 오버레이(회전 스피너)
LOADING_HTML = """
<div class="maps-loading">
  <div class="maps-spinner"></div>
  <div class="maps-loading-text">관심사를 분석해 학과·직업을 찾는 중…</div>
</div>
<style>
.maps-loading {
  position: fixed; inset: 0; z-index: 99999;
  background: rgba(255,255,255,0.78); backdrop-filter: blur(2px);
  display: flex; flex-direction: column; align-items: center; justify-content: center;
}
.maps-spinner {
  width: 58px; height: 58px; border-radius: 50%;
  border: 6px solid #FFE0CF; border-top-color: #FF6A2C;
  animation: maps-spin 0.8s linear infinite;
}
.maps-loading-text { margin-top: 16px; color: #1E2530; font-weight: 700; font-size: 1.0rem; }
@keyframes maps-spin { to { transform: rotate(360deg); } }
</style>
"""

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

/* 코드/키워드 칩 — Streamlit 기본 초록 스타일을 강제 덮어씀 */
code, .stMarkdown code {{ background: #FFE7D6 !important; color: #B5350D !important;
    font-weight: 600 !important; border: 1px solid #F7C6A4; border-radius: 6px;
    padding: 2px 8px !important; }}
hr {{ border-color: {FABRIK['border']}; }}

/* 설치대학 테이블(지역|대학명) — 공간 절약 */
table.univ-tb {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; margin-top: 4px; }}
table.univ-tb th, table.univ-tb td {{
    border: 1px solid {FABRIK['border']}; padding: 5px 10px;
    text-align: left; vertical-align: top;
}}
table.univ-tb th {{ background: {FABRIK['surface']}; font-weight: 700; }}
table.univ-tb td.rg {{ white-space: nowrap; font-weight: 700; width: 78px;
    color: {FABRIK['navy']}; background: {FABRIK['surface']}; }}
table.univ-tb td.nw {{ white-space: nowrap; color: {FABRIK['muted']}; font-weight: 600; }}
table.univ-tb td a {{ color: {FABRIK['cta_dim']}; }}
/* 설치학교 그룹 병합 셀(시도/시군구) + 시도 경계 굵은선 */
table.univ-tb td.grp {{ white-space: nowrap; font-weight: 700; color: {FABRIK['navy']};
    background: {FABRIK['surface']}; vertical-align: middle; text-align: center; }}
table.univ-tb tr.grp-start > td {{ border-top: 2px solid {FABRIK['navy']}; }}

/* 연계 진로 등식 카드(학과 + 직업 = 진로) */
.cp-card {{ border: 1px solid {FABRIK['border']}; border-radius: 12px;
    padding: 12px 16px; margin-bottom: 10px; background: {FABRIK['surface2']}; }}
.cp-card.cp-strong {{ border-left: 4px solid {FABRIK['cta']}; background: {FABRIK['cta_soft']}; }}
.cp-eq {{ display: flex; align-items: center; flex-wrap: wrap; gap: 7px; }}
/* 타원형 라벨 */
.cp-tag {{ padding: 3px 12px; border-radius: 999px; font-size: 0.76rem;
    font-weight: 700; color: #fff; white-space: nowrap; }}
.cp-tag-major {{ background: {FABRIK['navy']}; }}
.cp-tag-job {{ background: {FABRIK['cta']}; }}
.cp-name {{ font-weight: 700; color: {FABRIK['text']}; }}
.cp-gt {{ color: {FABRIK['muted']}; font-weight: 800; font-size: 1.1rem; margin: 0 5px; }}
.cp-kws {{ margin-top: 9px; color: {FABRIK['muted']}; font-size: 0.86rem; }}
.cp-chip {{ display: inline-block; background: {FABRIK['cta']}1A; color: {FABRIK['cta_dim']};
    border-radius: 6px; padding: 1px 8px; margin: 2px 3px 0 0; font-weight: 600; }}

/* 분류(대/중/소)는 버튼 방식 — 선택 강조는 동적 주입 CSS로 처리 */
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


def _safe_radio(label, options, key, **kw):
    """계단식 라디오 — 저장값이 현재 옵션에 없으면 제거 후 생성."""
    if key in st.session_state and st.session_state[key] not in options:
        del st.session_state[key]
    return st.radio(label, options, key=key, **kw)


def _cat_buttons(items, prefix, sel_key, clear_keys=()):
    """분류 버튼 리스트(행 전체 클릭). 선택값은 session_state[sel_key].
    선택된 버튼은 네이비로 강조(인덱스 기반 동적 CSS)."""
    for idx, it in enumerate(items):
        if st.button(it, key=f"{prefix}_{idx}", use_container_width=True):
            st.session_state[sel_key] = it
            for ck in clear_keys:
                st.session_state.pop(ck, None)
            st.rerun()
    cur = st.session_state.get(sel_key)
    if cur in items:
        i = items.index(cur)
        st.markdown(
            f"<style>[class~='st-key-{prefix}_{i}'] button{{"
            f"background:{FABRIK['navy']} !important;border-color:{FABRIK['navy']} !important;}}"
            f"[class~='st-key-{prefix}_{i}'] button p{{color:#fff !important;font-weight:800;}}"
            f"</style>", unsafe_allow_html=True)
        return cur
    return None


def _render_major_detail(r):
    extra = R.major_extra(r)
    univ = extra.get("설치대학", {})
    if univ.get("univ_count", 0) > 0:
        with st.expander(f"🏛️ 설치대학 ({univ['univ_count']}곳)  ·  대학명 클릭 시 EBSi"):
            rows = []
            for region, unis in univ["by_region"].items():
                links = ", ".join(univ_link(u["대학명"]) for u in unis)
                rows.append(f"<tr><td class='rg'>{region}</td><td>{links}</td></tr>")
            st.markdown(
                "<table class='univ-tb'><thead><tr><th>지역</th><th>대학명</th>"
                "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>",
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


@st.dialog("학과 상세", width="large")
def major_info_modal(name):
    r = R.major_by_name(name)
    if not r:
        st.info("학과 정보를 찾을 수 없어요.")
        return
    st.markdown(f"### 📚 {r['name']}  ·  키워드 점수 {r['score']}")
    st.markdown("**대표 키워드** — " + reason_line(r["reasons"], limit=10))
    st.markdown("---")
    _render_major_detail(r)
    with st.expander("🏫 설치 고교 보기 (선택과목 개설 학교)"):
        subj = R.subjects_of_major(r)
        flat = [s for v in subj.values() for s in v]
        st.caption("이 학과의 권장 선택과목이 전국 몇 개 고교에 개설돼 있는지")
        for s in flat:
            n = len(R.schools_offering(s))
            st.markdown(f"- **{s}** — {n:,}개교 개설")


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
    EXAMPLE = "나는 로봇이랑 똑똑한 기계가 좋은데, 글쓰기는 어려워하고, 운동은 잘 못해요."
    st.markdown("**좋아하거나 관심있고 재미있는 것**과 **싫어하거나 어려운 것**을 자유롭게 적어주세요.")
    st.caption(f"예) {EXAMPLE}")
    if st.button("예시로 채우기", key="fill_example"):
        st.session_state["speech_input"] = EXAMPLE
    speech = st.text_area("관심사·하고 싶은 일을 적어주세요", key="speech_input",
                          height=120, placeholder=f"예) {EXAMPLE}")
    go = st.button("추천 받기", type="primary")

    if go:
        if not speech.strip():
            st.warning("진로 추천에 바탕이 될 내용을 입력해 주세요.")
        else:
            loading = st.empty()
            loading.markdown(LOADING_HTML, unsafe_allow_html=True)
            try:
                st.session_state["result"] = R.recommend(
                    speech, top_n=topn, pair_k=pair_k, use_llm=use_llm)
            finally:
                loading.empty()

    out = st.session_state.get("result")
    if not out:
        st.info("관심사를 입력하고 **추천 받기**를 누르면 결과가 여기에 표시됩니다.")
    else:
        meta = out.get("meta", {})
        st.markdown("#### 🔑 키워드")
        mode_label = "🤖 LLM 발화 이해" if meta.get("mode") == "llm" else "🔧 규칙 기반"
        st.caption(f"추출 방식: {mode_label}"
                   + (f"  ·  {meta['rationale']}" if meta.get("rationale") else ""))
        if meta.get("note"):
            st.caption("ℹ️ " + meta["note"])
        if out["tokens"]:
            st.markdown("**추출한 키워드** &nbsp; "
                        + " ".join(f"`{t}`" for t in out["tokens"]))
        else:
            st.warning("키워드를 추출하지 못했어요. 조금 더 자세히 적어보세요.")
        if out["excluded"]:
            st.markdown("**제외한 키워드** &nbsp; "
                        + " ".join(f"`{t}`" for t in out["excluded"]))
            st.caption("싫어하거나 어려워하는 것은 추천에서 제외했어요.")

        st.markdown("#### 🎯 추천 결과")
        st.caption("추천 학과나 직업을 클릭하면 상세한 내용을 볼 수 있습니다.")
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
        st.subheader("🧭 추천 진로")
        st.caption("추천 학과와 직업이 **공통 키워드**로 이어지는 진로 조합입니다. "
                   "공통 키워드가 많을수록(주황 강조) 연결이 강합니다.")
        if not out["pairs"]:
            st.info("연계 진로를 만들 수 없어요.")
        else:
            st.markdown("".join(pair_card_html(p) for p in out["pairs"]),
                        unsafe_allow_html=True)


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
            CAP = 140
            st.markdown(school_table_html(offered[:CAP]), unsafe_allow_html=True)
            if len(offered) > CAP:
                st.caption(f"… 외 {len(offered) - CAP:,}개교. 지역 필터로 좁혀보세요.")

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

    # ── 검색 ──
    qc1, qc2 = st.columns([5, 1])
    with qc1:
        mq = st.text_input("학과명 검색", key="major_q",
                           placeholder="예) 시각디자인, 기계, 간호",
                           label_visibility="collapsed")
    with qc2:
        st.button("🔍 검색", use_container_width=True, key="major_search_btn")

    # ── 분류로 찾기 (대 > 중 > 소) ──
    st.caption("분류로 찾기 — **대분류 → 중분류**까지 고르면 학과가 나타나고, 소분류를 고르면 더 좁혀집니다.")
    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        st.markdown("**대분류**")
        with st.container(height=240):
            dae = _cat_buttons(R.category_daes(), "cat_dae", "sel_dae",
                               clear_keys=("sel_jung", "sel_so"))
    jungs = R.category_jungs(dae) if dae else []
    with cc2:
        st.markdown("**중분류**")
        with st.container(height=240):
            if jungs:
                jung = _cat_buttons(jungs, "cat_jung", "sel_jung",
                                    clear_keys=("sel_so",))
            else:
                jung = None
                st.caption("← 대분류를 먼저 선택")
    sos = R.category_sos(dae, jung) if (dae and jung) else []
    with cc3:
        st.markdown("**소분류**")
        with st.container(height=240):
            if sos:
                so = _cat_buttons(["전체"] + sos, "cat_so", "sel_so")
            else:
                so = None
                st.caption("← 중분류를 선택")

    # ── 결과 목록 ──
    if dae and jung:
        so_sel = None if (not so or so == "전체") else so
        results = R.majors_in_category(dae, jung, so_sel)
        if mq.strip():
            results = [n for n in results if mq.strip() in n]
        loc = f"{dae} › {jung}" + (f" › {so_sel}" if so_sel else "")
        st.markdown(f"**📂 {loc}**  ·  {len(results)}개 학과")
    elif mq.strip():
        results = [n for n in names if mq.strip() in n]
        st.markdown(f"**🔎 검색 결과**  ·  {len(results)}개 학과")
    else:
        results = None
        if dae and not jung:
            st.info("중분류까지 선택해주세요.")
        else:
            st.info("학과명을 검색하거나, 대분류 → 중분류를 선택하세요.")

    if results is not None:
        if not results:
            st.info("해당하는 학과가 없어요.")
        GRID_CAP = 60
        gcols = st.columns(2)
        for idx, nm in enumerate(results[:GRID_CAP]):
            with gcols[idx % 2]:
                if st.button(nm, key=f"majinfo_{nm}", use_container_width=True):
                    major_info_modal(nm)
        if len(results) > GRID_CAP:
            st.caption(f"… 외 {len(results) - GRID_CAP}개. 검색·소분류로 좁혀보세요.")
