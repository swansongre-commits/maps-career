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

st.set_page_config(page_title="M.A.P.S", page_icon="🎓", layout="wide")

# 참고: 크롬 자동 번역 팝업은 Streamlit Cloud에서 코드로 막기 어렵다(최초 HTML의
# <html lang>을 제어할 수 없고, JS 주입은 컴포넌트 iframe 제약·타이밍으로 늦음).
# 자체 호스팅으로 옮기면 <head>에 lang="ko"를 박아 영구 해결 가능. 기능엔 무관.


@st.cache_resource
def load_engine():
    import recommender
    return recommender


R = load_engine()

import re
from urllib.parse import quote

VIA_BADGE = {"공시": "🟦", "쉬운말": "🟩"}

# 과목 유형 → 위젯키용 ASCII 코드(버튼 키에 인코딩 → CSS ::before 뱃지 매칭)
SUBJ_TYPE_CODE = {"일반": "il", "진로": "jr", "융합": "yh"}


def via_badge_html(via):
    """매칭 경로(공시/쉬운말) 뱃지 — 무채색(.badge 톤). 색이 아니라 채움으로 구분:
    공시=잉크 반전(채움), 쉬운말=외곽선."""
    cls = "vb-off" if via == "공시" else "vb-easy"
    return f"<span class='vbadge {cls}'>{via}</span>"

# 대학명 클릭 → EBSi 대학 검색(새창). 괄호 캠퍼스 표기는 검색어에서 제거.
EBSI_BASE = ("https://www.ebsi.co.kr/ebs/ent/entNgf/retrieveEntNgfUnivList.ebs"
             "?srchUnivNm=")


def _ebsi_url(name):
    base = re.sub(r"\(.*?\)", "", str(name)).strip() or str(name)
    return EBSI_BASE + quote(base)


def univ_link(name):
    return f'<a href="{_ebsi_url(name)}" target="_blank">{name}</a>'


def pair_card_html(p):
    """연계 진로 1건 → 등식 카드 HTML (:material/menu_book:학과 + :material/work:직업 = :material/explore:진로 · 공통 키워드)."""
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
  border: 6px solid #E4E4E4; border-top-color: #141414;
  animation: maps-spin 0.8s linear infinite;
}
.maps-loading-text { margin-top: 16px; color: #141414; font-weight: 700; font-size: 1.0rem; }
@keyframes maps-spin { to { transform: rotate(360deg); } }
</style>
"""

# ── 무채색 에디토리얼 팔레트 — timeline DESIGN_GUIDE 토큰과 정렬 ──
# 원칙: 흰 배경·무채색·1px 라인·8px/999px 라운드·강조는 색이 아니라 잉크 반전.
FABRIK = {
    "bg": "#F5F5F5",            # 페이지 배경(연한 회색) = --bg
    "surface": "#FFFFFF",       # 카드/사이드바 표면 = --surface
    "surface2": "#FFFFFF",      # 버튼/행 표면(흰색)
    "surface_soft": "#F0F0F0",  # 칩·hover 약한 표면 = --surface-soft
    "border": "#E4E4E4",        # 기본 보더 = --line
    "line_strong": "#C9C9C9",   # 강한 보더(버튼·인풋) = --line-strong
    "cta": "#141414",           # 강조 = 잉크 = --ink/--accent
    "cta_dim": "#000000",
    "cta_soft": "#EDEDED",      # 활성 카드 배경 = --accent-soft
    "navy": "#141414",          # 선택/활성(검정) — 무채색 통일
    "tabbg": "#F0F0F0",         # 비활성 탭 배경 = --surface-soft
    "text": "#141414",          # 본문 텍스트(잉크) = --ink
    "ink_mid": "#3F3F3F",       # 중간 농도 텍스트(배지) = --ink-mid
    "muted": "#6B6B6B",         # 보조/라벨 텍스트 = --muted
    "soft": "#9A9A9A",          # 더 약한 텍스트/아이콘 = --soft
}

CSS = f"""
<style>
.stApp {{ background: {FABRIK['bg']}; color: {FABRIK['text']}; }}
h1, h2, h3, h4, h5, h6 {{ color: {FABRIK['text']}; letter-spacing: -0.2px; }}
/* 페이지 제목 — 과도하게 큰 기본 h1 축소(에디토리얼 톤) */
.stApp h1 {{ font-size: 1.85rem !important; font-weight: 800; }}
section[data-testid="stSidebar"] {{ background: {FABRIK['surface']}; border-right: 1px solid {FABRIK['border']}; }}

/* 결과 칼럼(테두리 컨테이너) — 8px 라운드 통일, 은은한 패널 그림자 */
div[data-testid="stVerticalBlockBorderWrapper"] {{
    background: {FABRIK['surface']};
    border: 1px solid {FABRIK['border']} !important;
    border-radius: 8px;
    box-shadow: 0 8px 26px rgba(28,35,31,0.05);
}}

/* ── 탭 = 세그먼트 컨트롤. 강조=반전: 활성 탭만 잉크 배경+흰 글씨 ── */
div[data-baseweb="tab-list"] {{
    gap: 0;
    border-bottom: 1px solid {FABRIK['border']};
}}
button[data-baseweb="tab"] {{
    flex: 1 1 0;
    justify-content: center;
    text-align: center;
    color: {FABRIK['muted']};
    background: {FABRIK['surface_soft']};
    border: 1px solid {FABRIK['line_strong']};
    border-right: none;
    border-radius: 0;
    padding: 0.75rem 0;
    font-weight: 700;
    margin-bottom: -1px;
}}
button[data-baseweb="tab"]:last-child {{ border-right: 1px solid {FABRIK['line_strong']}; }}
button[data-baseweb="tab"]:hover {{ color: {FABRIK['ink_mid']}; background: {FABRIK['surface_soft']}; }}
/* 활성 탭 — 잉크 반전(검정 배경 + 흰 글씨) */
button[data-baseweb="tab"][aria-selected="true"] {{
    color: #FFFFFF;
    background: {FABRIK['cta']};
    border-color: {FABRIK['cta']};
    font-weight: 800;
}}
button[data-baseweb="tab"][aria-selected="true"] p {{ font-weight: 800; color: #FFFFFF; font-size: 1.02rem; }}
div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] {{ background-color: transparent; }}

/* 버튼 = 외곽선 위계. 라운드 8px·강한 보더·hover 시 외곽 진해짐 */
div[data-testid="stButton"] > button {{
    width: 100%;
    min-height: 38px;
    text-align: left;
    background: {FABRIK['surface2']};
    color: {FABRIK['text']};
    border: 1px solid {FABRIK['line_strong']};
    border-radius: 8px;
    padding: 0.5rem 0.85rem;
    font-weight: 700;
    transition: all .12s ease;
}}
div[data-testid="stButton"] > button p {{ text-align: left; margin: 0; font-weight: 700; }}
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

/* 모달(dialog) — 8px 라운드 + 잉크 상단 라인 + 떠있는 표면 그림자 */
div[role="dialog"], div[data-testid="stDialog"] > div > div {{
    border: 1px solid {FABRIK['border']} !important;
    border-top: 4px solid {FABRIK['cta']} !important;
    border-radius: 8px !important;
    box-shadow: 0 18px 60px rgba(0,0,0,0.07) !important;
}}
div[data-testid="stDialogOverlay"] {{ background: rgba(20,24,22,0.34) !important; }}
/* 기본 닫기 X 숨김 — iOS식 자체 헤더(좌:뒤로 / 우:닫기)로 통일 */
div[data-testid="stDialog"] button[aria-label="Close"],
div[role="dialog"] button[aria-label="Close"] {{ display: none !important; }}
/* 기본 타이틀 바 숨김 — 버튼을 타이틀 위로 올려 자체 헤더로 렌더 */
div[role="dialog"] > div:first-child {{ display: none !important; }}

/* 아코디언 — 8px 통일 */
details {{ border-radius: 8px !important; border: 1px solid {FABRIK['border']} !important;
          background: {FABRIK['surface2']}; }}

/* 코드/키워드 칩 — 무채색 알약형(999px) */
code, .stMarkdown code {{ background: {FABRIK['surface_soft']} !important; color: {FABRIK['text']} !important;
    font-weight: 750 !important; border: 1px solid {FABRIK['border']}; border-radius: 999px;
    padding: 3px 10px !important; }}
hr {{ border-color: {FABRIK['border']}; }}

/* 입력/드롭다운 — 8px 라운드, focus 시 잉크 외곽 */
div[data-baseweb="input"], div[data-baseweb="select"] > div,
div[data-baseweb="textarea"], .stTextInput div[data-baseweb="base-input"] {{
    border-radius: 8px !important; }}
div[data-baseweb="input"]:focus-within, div[data-baseweb="select"] > div:focus-within,
div[data-baseweb="textarea"]:focus-within {{ border-color: {FABRIK['cta']} !important; }}

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
/* 대표 키워드 그리드(kw-grid): 데스크톱 4열·모바일 2열, 칸=순위·키워드·점수 */
.kw-grid {{ display: grid; grid-template-columns: repeat(4, 1fr);
    gap: 6px; margin: 4px 0 2px; }}
@media (max-width: 640px) {{ .kw-grid {{ grid-template-columns: repeat(2, 1fr); }} }}
.kw-cell {{ display: flex; align-items: center; gap: 6px;
    border: 1px solid {FABRIK['border']}; border-radius: 8px;
    background: {FABRIK['surface2']}; padding: 5px 9px; font-size: 0.84rem;
    overflow: hidden; }}
.kw-cell .kw-rank {{ color: {FABRIK['muted']}; font-weight: 700;
    font-size: 0.74rem; min-width: 26px; flex: none; }}
.kw-cell .kw-term {{ color: {FABRIK['text']}; font-weight: 750;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.kw-cell .kw-pts {{ margin-left: auto; color: {FABRIK['muted']};
    font-weight: 600; font-size: 0.76rem; flex: none; }}
/* 설치학교 그룹 병합 셀(시도/시군구) + 시도 경계 굵은선 */
table.univ-tb td.grp {{ white-space: nowrap; font-weight: 700; color: {FABRIK['navy']};
    background: {FABRIK['surface']}; vertical-align: middle; text-align: center; }}
table.univ-tb tr.grp-start > td {{ border-top: 2px solid {FABRIK['navy']}; }}

/* 연계 진로 등식 카드(학과 + 직업 = 진로) */
.cp-card {{ border: 1px solid {FABRIK['border']}; border-radius: 8px;
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
.cp-chip {{ display: inline-block; background: {FABRIK['surface_soft']}; color: {FABRIK['ink_mid']};
    border: 1px solid {FABRIK['border']}; border-radius: 999px; padding: 2px 9px;
    margin: 2px 3px 0 0; font-weight: 750; font-size: 0.78rem; }}

/* 분류(대/중/소)는 버튼 방식 — use_container_width로 폭 100% 보장.
   기본 버튼 스타일(흰 행) 상속, 선택 버튼은 _cat_buttons가 네이비로 동적 강조. */
[class*="st-key-cat_"] div[data-testid="stButton"] > button p {{ text-align: center; }}

/* 분류 영역 반응형: 화면 폭 기준으로 데스크톱 패널 / 모바일 아코디언 택1 */
[class*="st-key-catwrap_mobile"] {{ display: none; }}        /* 기본(데스크톱): 모바일판 숨김 */
@media (max-width: 640px) {{
    [class*="st-key-catwrap_desktop"] {{ display: none !important; }}  /* 모바일: 데스크톱판 숨김 */
    [class*="st-key-catwrap_mobile"] {{ display: block !important; }}
}}

/* 과목 설치고교(…schtbl) — 지역 그룹 헤더 + 학교 칩 버튼 그리드(컴팩트) */
[class*="schtbl"] div[data-testid="stVerticalBlock"] {{ gap: 6px !important; }}
[class*="schtbl"] div[data-testid="stHorizontalBlock"] {{ gap: 6px; }}
[class*="schtbl"] .rg-label {{ margin: 12px 0 2px; padding-left: 8px;
    font-size: 0.9rem; font-weight: 700; color: {FABRIK['navy']};
    border-left: 3px solid {FABRIK['navy']}; }}
[class*="schtbl"] .rg-label .gug {{ color: {FABRIK['muted']};
    font-weight: 600; font-size: 0.82rem; }}
[class*="schtbl"] div[data-testid="stButton"] > button {{
    background: {FABRIK['surface2']} !important;
    border: 1px solid {FABRIK['border']} !important; border-radius: 8px;
    min-height: 0; padding: 5px 10px; box-shadow: none; }}
[class*="schtbl"] div[data-testid="stButton"] > button:hover {{
    border-color: {FABRIK['cta']} !important;
    background: {FABRIK['cta_soft']} !important; transform: none; }}
[class*="schtbl"] div[data-testid="stButton"] > button p {{
    text-align: center; font-size: 0.86rem; color: {FABRIK['text']};
    font-weight: 600; white-space: normal; word-break: keep-all;
    line-height: 1.25; }}

/* 매칭 경로 뱃지(공시/쉬운말) — 무채색. 공시=잉크 채움, 쉬운말=외곽선 */
.vbadge {{ display: inline-block; margin-right: 5px; padding: 0 7px;
    border-radius: 999px; font-size: 0.62rem; font-weight: 800;
    line-height: 1.7; vertical-align: middle; white-space: nowrap;
    border: 1px solid {FABRIK['line_strong']}; }}
/* 공시=특수분류 파랑(타임라인 §2), 쉬운말=중립 회색 */
.vbadge.vb-off {{ background: #EFF6FF; color: #1D4ED8; border-color: #93C5FD; }}
.vbadge.vb-easy {{ background: {FABRIK['bg']}; color: {FABRIK['ink_mid']}; }}

/* 제외한 키워드 = 경고·삭제 빨강(타임라인 §2) */
.kw-excl {{ display: inline-block; padding: 2px 10px; margin: 2px 3px 0 0;
    border-radius: 999px; background: #FDF2F2; color: #C0392B;
    border: 1px solid #E0B4B4; font-weight: 750; font-size: 0.82rem; }}

/* 추천 적합도 지표 — 강도 막대 + 3단 라벨(무채색 농도로 구분, 색 분류 X) */
.strength {{ display: flex; flex-direction: column; justify-content: center;
    gap: 4px; min-height: 38px; }}
.strength .sbar {{ height: 6px; border-radius: 999px;
    background: {FABRIK['surface_soft']}; overflow: hidden; }}
.strength .sfill {{ height: 100%; border-radius: 999px; }}
.strength .sfill.s-hi {{ background: #1D4ED8; }}
.strength .sfill.s-mid {{ background: #3B82F6; }}
.strength .sfill.s-lo {{ background: #93C5FD; }}
.strength .smeta {{ display: flex; align-items: center; gap: 7px;
    font-size: 0.74rem; line-height: 1; }}
.strength .stier {{ font-weight: 800; color: {FABRIK['text']}; }}
.strength .smatch {{ color: {FABRIK['muted']}; font-weight: 600; }}

/* 선택과목 칩 그리드(…subjgrid): 데스크톱 4열·모바일 2열 (st.columns reflow) */
[class*="subjgrid"] div[data-testid="stHorizontalBlock"] {{ flex-wrap: wrap; gap: 6px; }}
[class*="subjgrid"] div[data-testid="stVerticalBlock"] {{ gap: 6px !important; }}
[class*="subjgrid"] div[data-testid="stButton"] > button {{
    display: flex; align-items: center; justify-content: flex-start; }}
[class*="subjgrid"] div[data-testid="stButton"] > button p {{
    white-space: normal; word-break: keep-all; line-height: 1.2;
    font-size: 0.86rem; text-align: left; }}
/* 학교 화면에서 '거쳐온 학과'의 권장과목 강조 — 특수분류 파랑(공시 배지와 동일) */
[class*="st-key-xschsub_hl_"] button {{
    border: 2px solid #1D4ED8 !important;
    background: #EFF6FF !important; }}
[class*="st-key-xschsub_hl_"] button p {{ font-weight: 800 !important; color: #1D4ED8 !important; }}

/* 과목 유형 뱃지 — 칩 앞 무채색 알약(.badge 톤). 버튼 키 코드로 매칭 */
[class*="st-key-xmajsub_il_"] button::before,
[class*="st-key-xmajsub_jr_"] button::before,
[class*="st-key-xmajsub_yh_"] button::before {{
    display: inline-block; margin-right: 6px; padding: 0 7px;
    border-radius: 999px; border: 1px solid {FABRIK['line_strong']};
    background: {FABRIK['bg']}; color: {FABRIK['ink_mid']};
    font-size: 0.64rem; font-weight: 800; line-height: 1.7;
    flex: none; white-space: nowrap; }}
[class*="st-key-xmajsub_il_"] button::before {{ content: "일반"; }}
[class*="st-key-xmajsub_jr_"] button::before {{ content: "진로"; }}
[class*="st-key-xmajsub_yh_"] button::before {{ content: "융합"; }}

/* ── 반응형: 태블릿·모바일에서 과대 폰트/여백 축소 ── */
@media (max-width: 1024px) {{
    .stApp h1 {{ font-size: 1.7rem !important; }}
    .stApp h2 {{ font-size: 1.35rem !important; }}
    .stApp h3 {{ font-size: 1.15rem !important; }}
    .stApp h4 {{ font-size: 1.02rem !important; }}
    .block-container {{ padding-left: 1.6rem !important; padding-right: 1.6rem !important; }}
}}
@media (max-width: 640px) {{
    .stApp h1 {{ font-size: 1.45rem !important; line-height: 1.2 !important; }}
    .stApp h2 {{ font-size: 1.2rem !important; }}
    .stApp h3 {{ font-size: 1.05rem !important; }}
    .stApp h4 {{ font-size: 0.98rem !important; }}
    .block-container {{ padding: 3rem 0.85rem 1.5rem !important; }}
    [data-testid="stMarkdownContainer"] p {{ font-size: 0.9rem; }}
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{ font-size: 0.76rem; }}
    /* 탭 라벨 — 좁은 폭에서 넘침/줄바꿈 방지 */
    button[data-baseweb="tab"] {{ padding: 0.55rem 0 !important; }}
    button[data-baseweb="tab"] p {{ font-size: 0.82rem !important; }}
    button[data-baseweb="tab"][aria-selected="true"] p {{ font-size: 0.84rem !important; }}
    /* 버튼 — 약간 컴팩트 */
    div[data-testid="stButton"] > button {{ min-height: 34px; }}
    div[data-testid="stButton"] > button p {{ font-size: 0.88rem; }}
    /* 키워드 그리드 칸 더 촘촘 */
    .kw-cell {{ font-size: 0.78rem; padding: 4px 7px; gap: 4px; }}
    .kw-cell .kw-rank {{ min-width: 22px; font-size: 0.68rem; }}
    .kw-cell .kw-pts {{ font-size: 0.7rem; }}
    /* 설치고교 칩 버튼 */
    [class*="schtbl"] div[data-testid="stButton"] > button p {{ font-size: 0.8rem; }}
    /* 연계 진로 카드 — 폰트·여백 축소 */
    .cp-name {{ font-size: 0.9rem; }}
    .cp-card {{ padding: 10px 12px; }}
    /* 선택과목 그리드 — 모바일 2열 강제 */
    [class*="subjgrid"] div[data-testid="stColumn"] {{
        flex: 0 1 calc(50% - 3px) !important;
        min-width: calc(50% - 3px) !important; width: calc(50% - 3px) !important; }}
    [class*="subjgrid"] div[data-testid="stButton"] > button p {{ font-size: 0.8rem; }}
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def reason_line(reasons, limit=8):
    parts = []
    for x in reasons[:limit]:
        b = VIA_BADGE.get(x["via"], "")
        parts.append(f'{b} `{x["term"]}` ({x["rank"]}위·{x["points"]}점)')
    return "  ".join(parts)


def reason_table_html(reasons, limit=20):
    """추천 근거(대표 키워드)를 4열 그리드로 압축(데스크톱 4열·모바일 2열).
    각 칸: 순위 · 경로(공시/쉬운말) 뱃지 + 키워드 · 점수. 20개면 4열×5행."""
    if not reasons:
        return "<p style='color:#6B6B6B'>매칭된 키워드가 없어요.</p>"
    cells = []
    for x in reasons[:limit]:
        cells.append(
            f"<div class='kw-cell'>"
            f"<span class='kw-rank'>{x['rank']}위</span>"
            f"<span class='kw-term'>{via_badge_html(x['via'])}{x['term']}</span>"
            f"<span class='kw-pts'>{x['points']}점</span>"
            f"</div>")
    return "<div class='kw-grid'>" + "".join(cells) + "</div>"


def strength_html(score, top, n_match=None):
    """사용자용 적합도 지표 — 원점수 대신 '상대 강도 막대 + 3단 라벨'.
    top(이 목록 1위 점수) 기준 상대화 → 만점이 자동으로 생긴다(1위=가득).
    원점수는 백엔드 정렬에만 쓰고 화면엔 노출하지 않는다."""
    rel = (score / top) if top else 0
    if rel >= 0.7:
        tier, cls = "매우 적합", "s-hi"
    elif rel >= 0.4:
        tier, cls = "적합", "s-mid"
    else:
        tier, cls = "관련 있음", "s-lo"
    pct = max(8, round(rel * 100))
    meta = f"<span class='stier'>{tier}</span>"
    if n_match:
        meta += f"<span class='smatch'>키워드 {n_match}개 일치</span>"
    return (f"<div class='strength' title='추천 강도(1위 기준 상대)'>"
            f"<div class='sbar'><div class='sfill {cls}' style='width:{pct}%'></div></div>"
            f"<div class='smeta'>{meta}</div></div>")


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
    """분류 선택(버튼, 행 전체폭). 선택값 session_state[sel_key], 선택 버튼은 네이비.
    반환: 선택된 값(없으면 None)."""
    for idx, it in enumerate(items):
        if st.button(it, key=f"{prefix}_{idx}", use_container_width=True):
            st.session_state[sel_key] = it
            for ck in clear_keys:
                st.session_state.pop(ck, None)
    cur = st.session_state.get(sel_key)
    if cur in items:
        i = items.index(cur)
        st.markdown(
            f"<style>"
            f"[class~='st-key-{prefix}_{i}'] button{{"
            f"background:{FABRIK['navy']} !important;border-color:{FABRIK['navy']} !important;}}"
            f"[class~='st-key-{prefix}_{i}'] button p{{color:#fff !important;font-weight:700;}}"
            f"</style>", unsafe_allow_html=True)
        return cur
    return None


def _cat_desktop_panels(daes, p):
    """데스크톱 3패널(대/중/소). prefix p로 위젯키 구분, 선택은 sel_* 공유."""
    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        st.markdown("**대분류**")
        with st.container(height=240):
            d = _cat_buttons(daes, f"{p}_dae", "sel_dae", clear_keys=("sel_jung", "sel_so"))
    with cc2:
        st.markdown("**중분류**")
        with st.container(height=240):
            jungs = R.category_jungs(d) if d else []
            if jungs:
                _cat_buttons(jungs, f"{p}_jung", "sel_jung", clear_keys=("sel_so",))
            else:
                st.caption("← 대분류를 먼저 선택")
    with cc3:
        st.markdown("**소분류**")
        with st.container(height=240):
            jn = st.session_state.get("sel_jung")
            sos = R.category_sos(d, jn) if (d and jn) else []
            if sos:
                _cat_buttons(["전체"] + sos, f"{p}_so", "sel_so")
            else:
                st.caption("← 중분류를 선택")


def _cat_mobile_accordion(daes, p):
    """모바일 아코디언(대→중→소). 세 단계 항상 표시, 선택은 sel_* 공유."""
    sd = st.session_state.get("sel_dae")
    sj = st.session_state.get("sel_jung")
    with st.expander("① 대분류" + (f" · {sd}" if sd else "  (선택)"), expanded=not sd):
        d = _cat_buttons(daes, f"{p}_dae", "sel_dae", clear_keys=("sel_jung", "sel_so"))
    jungs = R.category_jungs(d) if d else []
    with st.expander("② 중분류" + (f" · {sj}" if sj else "  (선택)"),
                     expanded=bool(d and not sj)):
        if jungs:
            _cat_buttons(jungs, f"{p}_jung", "sel_jung", clear_keys=("sel_so",))
        else:
            st.caption("← 대분류를 먼저 선택하세요")
    jn = st.session_state.get("sel_jung")
    sos = R.category_sos(d, jn) if (d and jn) else []
    with st.expander("③ 소분류  (선택)", expanded=False):
        if sos:
            _cat_buttons(["전체"] + sos, f"{p}_so", "sel_so")
        else:
            st.caption("← 중분류를 먼저 선택하세요")


def _category_picker():
    """대>중>소 분류 선택. 데스크톱 패널 + 모바일 아코디언을 둘 다 렌더하고
    CSS 미디어쿼리로 화면 폭에 따라 하나만 노출(선택 상태 sel_*는 공유). 반환 (대,중,소)."""
    daes = R.category_daes()
    with st.container(key="catwrap_desktop"):
        _cat_desktop_panels(daes, "cat")
    with st.container(key="catwrap_mobile"):
        _cat_mobile_accordion(daes, "catm")

    # 공유 선택값 정리(현재 트리에 유효한 것만)
    dae = st.session_state.get("sel_dae")
    if dae not in daes:
        dae = None
    jung = st.session_state.get("sel_jung")
    if not (dae and jung in R.category_jungs(dae)):
        jung = None
    so = st.session_state.get("sel_so")
    if not (dae and jung):
        so = None
    elif so == "전체" or so not in R.category_sos(dae, jung):
        so = None
    return dae, jung, so


def _render_major_detail(r):
    extra = R.major_extra(r)
    univ = extra.get("설치대학", {})
    if univ.get("univ_count", 0) > 0:
        with st.expander(f":material/account_balance: 설치대학 ({univ['univ_count']}곳)  ·  대학명 클릭 시 EBSi"):
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
            with st.expander(f":material/account_balance: 개설대학 ({total}곳)  ·  대학명 클릭 시 EBSi"):
                for region, unis in list(by_region.items())[:8]:
                    links = ", ".join(univ_link(u) for u in sorted(set(unis))[:6])
                    st.markdown(f"- **{region}**: {links}", unsafe_allow_html=True)

    subj = R.subjects_of_major(r)
    n_subj = sum(len(v) for v in subj.values())
    if n_subj:
        with st.expander(f":material/menu_book: 2022 선택과목 ({n_subj}개)"):
            for typ in ("일반", "진로", "융합"):
                items = subj[typ]
                if items:
                    st.markdown(f"**{typ} 선택**: {', '.join(items)}")
            st.caption("‘학교별 설치과목’ 탭에서 특정 고교의 개설 과목을 확인할 수 있어요.")

    rel = extra.get("관련직업", "")
    if rel:
        jobs = R.split_related_jobs(rel)
        with st.expander(f":material/work: 관련 직업 ({len(jobs)})"):
            st.markdown(", ".join(jobs))


def _render_univ_block(r):
    """설치대학 expander(대학명 EBSi 링크) — 상세·탐색기 공용."""
    extra = R.major_extra(r)
    univ = extra.get("설치대학", {})
    if univ.get("univ_count", 0) > 0:
        with st.expander(f":material/account_balance: 설치대학 ({univ['univ_count']}곳)  ·  대학명 클릭 시 EBSi"):
            rows = []
            for region, unis in univ["by_region"].items():
                links = ", ".join(univ_link(u["대학명"]) for u in unis)
                rows.append(f"<tr><td class='rg'>{region}</td><td>{links}</td></tr>")
            st.markdown("<table class='univ-tb'><thead><tr><th>지역</th><th>대학명</th>"
                        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>",
                        unsafe_allow_html=True)
    else:
        uni = extra.get("개설대학", "")
        if uni:
            by_region, total = parse_universities_legacy(uni)
            with st.expander(f":material/account_balance: 개설대학 ({total}곳)  ·  대학명 클릭 시 EBSi"):
                for region, unis in list(by_region.items())[:8]:
                    links = ", ".join(univ_link(u) for u in sorted(set(unis))[:6])
                    st.markdown(f"- **{region}**: {links}", unsafe_allow_html=True)


# ── 탐색기: 과목 ↔ 학교 ↔ 학과 무한 탐색 (단일 모달 + 네비 스택, reopen 패턴) ──
# xreopen: 네비게이션(열기/이동/뒤로) 때만 True로 켜서 하단 가드가 모달을 1회 재오픈.
# 내장 X·ESC·배경클릭으로 닫은 뒤 무관한 리런에서 모달이 되살아나는 것을 방지.
def _xopen(view):
    st.session_state["xstack"] = [view]
    st.session_state["xreopen"] = True
    st.rerun()


def _xgo(view):
    st.session_state["xstack"] = st.session_state.get("xstack", []) + [view]
    st.session_state["xreopen"] = True
    st.rerun()


def _xback():
    s = st.session_state.get("xstack", [])
    if len(s) > 1:
        s.pop()
    st.session_state["xstack"] = s
    st.session_state["xreopen"] = True
    st.rerun()


def _xclose():
    st.session_state["xstack"] = []
    st.session_state["xreopen"] = False
    st.rerun()


def _subject_school_table(subject, prefix):
    """과목 설치 고교 — 지역(시도·시군구)별로 묶고 학교는 칩 버튼 그리드로 표시.
    학교명 검색·지역 필터·더보기 지원. 버튼 클릭 시 그 학교 개설과목으로 이동."""
    schools = R.schools_offering(subject)
    st.caption(f"전국 {len(schools):,}개교 개설 — 학교명을 누르면 그 학교 개설과목을 봅니다")
    fc1, fc2, fc3 = st.columns([1, 1, 1.4])
    with fc1:
        sido = _safe_select("시도", ["전체"] + R.school_sidos(), f"{prefix}_sido")
    guguns = R.school_guguns(sido) if sido != "전체" else []
    with fc2:
        gugun = _safe_select("시군구", ["전체"] + guguns, f"{prefix}_gugun",
                             disabled=not guguns)
    with fc3:
        q = st.text_input("학교명 검색", key=f"{prefix}_q",
                          placeholder="학교명 일부 입력")
    qn = q.strip()
    fil = [o for o in schools
           if (sido == "전체" or o["sido"] == sido)
           and (not guguns or gugun == "전체" or o["gugun"] == gugun)
           and (not qn or qn in o["school"])]
    st.caption(f"검색·필터 결과 **{len(fil):,}개교**")
    if not fil:
        st.info("조건에 맞는 학교가 없어요. 검색어나 지역 필터를 바꿔보세요.")
        return

    show_key = f"{prefix}_show"
    show_n = st.session_state.get(show_key, 60)
    shown = fil[:show_n]
    # (시도, 시군구) 순서 보존 그룹 → 지역 헤더 + 학교 버튼 그리드
    groups = []
    for o in shown:
        if groups and groups[-1][0] == o["sido"] and groups[-1][1] == o["gugun"]:
            groups[-1][2].append(o)
        else:
            groups.append([o["sido"], o["gugun"], [o]])
    with st.container(key=f"{prefix}schtbl"):
        for sido_, gugun_, items in groups:
            st.markdown(
                f"<div class='rg-label'>{sido_}"
                f"<span class='gug'> · {gugun_} ({len(items)})</span></div>",
                unsafe_allow_html=True)
            cols = st.columns(4)
            for j, o in enumerate(items):
                with cols[j % 4]:
                    if st.button(o["school"],
                                 key=f"{prefix}_sch_{o['shl_idf_cd']}",
                                 use_container_width=True):
                        _xgo(("school", o["shl_idf_cd"], o["school"]))
    if len(fil) > show_n:
        if st.button(f"＋ 더 보기 (남은 {len(fil) - show_n:,}개교)",
                     key=f"{prefix}_more", use_container_width=True):
            st.session_state[show_key] = show_n + 60
            st.rerun()


def _xview_major(name):
    r = R.major_by_name(name)
    if not r:
        st.info("학과 정보를 찾을 수 없어요.")
        return
    st.markdown(f"### :material/menu_book: {r['name']}")
    st.markdown("**대표 키워드**")
    st.markdown(reason_table_html(r["reasons"]), unsafe_allow_html=True)
    _render_univ_block(r)
    subj = R.subjects_of_major(r)
    pairs = [(s, typ) for typ in ("일반", "진로", "융합") for s in subj[typ]]
    if pairs:
        # 과목 버튼 + 선택 과목의 설치 고교를 같은 박스 안에(하나의 영역)
        with st.container(border=True):
            st.markdown(f"**:material/menu_book: 2022 선택과목 ({len(pairs)})** — 과목을 누르면 바로 아래에 설치 "
                        "고교가 표시됩니다. 칩 앞 뱃지는 과목 유형(일반·진로·융합)이에요.")
            cur = st.session_state.get("xmaj_sub")
            cur_subj = cur[1] if (isinstance(cur, tuple) and cur[0] == r["name"]) else None
            with st.container(key="xmaj_subjgrid"):
                for start in range(0, len(pairs), 4):
                    cols = st.columns(4)
                    for j, (s, typ) in enumerate(pairs[start:start + 4]):
                        with cols[j]:
                            if st.button(s, key=f"xmajsub_{SUBJ_TYPE_CODE[typ]}_{start + j}",
                                         use_container_width=True):
                                # 같은 과목 재클릭 시 접기
                                st.session_state["xmaj_sub"] = (
                                    None if cur_subj == s else (r["name"], s))
            cur = st.session_state.get("xmaj_sub")
            cur_subj = cur[1] if (isinstance(cur, tuple) and cur[0] == r["name"]) else None
            sel = next(((SUBJ_TYPE_CODE[t], k) for k, (s, t) in enumerate(pairs)
                        if s == cur_subj), None)
            if sel is not None:
                code, sel_i = sel
                st.markdown(
                    f"<style>[class~='st-key-xmajsub_{code}_{sel_i}'] button{{"
                    f"background:{FABRIK['navy']} !important;border-color:{FABRIK['navy']} !important;}}"
                    f"[class~='st-key-xmajsub_{code}_{sel_i}'] button p{{color:#fff !important;font-weight:700;}}"
                    f"</style>", unsafe_allow_html=True)
                st.markdown(f"##### :material/menu_book: {cur_subj} · 설치 고교")
                _subject_school_table(cur_subj, "xmaj")

    # 이 학과 권장과목을 가장 많이 개설한 고교 Top-N (지역 필터 + 시도·시군구 표시)
    subj_chk = R.subjects_of_major(r)
    if any(subj_chk.values()):
        with st.container(border=True):
            st.markdown("**:material/trophy: 이 학과 권장과목을 가장 많이 개설한 고교**")
            tc1, tc2 = st.columns(2)
            with tc1:
                t_sido = _safe_select("시도", ["전국"] + R.school_sidos(), "xmajtop_sido")
            t_guguns = R.school_guguns(t_sido) if t_sido != "전국" else []
            with tc2:
                t_gugun = _safe_select("시군구", ["전체"] + t_guguns, "xmajtop_gugun",
                                       disabled=not t_guguns)
            top = R.top_schools_for_major(
                r, sido=None if t_sido == "전국" else t_sido,
                gugun=None if (not t_guguns or t_gugun == "전체") else t_gugun,
                top_n=5)
            if not top["schools"]:
                st.info("이 지역에 개설 학교가 없어요. 지역을 바꿔보세요.")
            else:
                scope = "전국" if t_sido == "전국" else (
                    f"{t_sido}" + ("" if (not t_guguns or t_gugun == "전체")
                                   else f" {t_gugun}"))
                st.caption(f"{scope} 기준 — 권장 {top['total']}과목 중 최다 "
                           f"{top['max_matched']}과목 개설 학교 {top['n_full']:,}곳. "
                           "학교를 누르면 개설과목을 봅니다.")
                for o in top["schools"]:
                    label = (f"{o['school']}　·　{o['sido']} {o['gugun']}"
                             f"　·　{o['matched']}/{top['total']}과목")
                    if st.button(label, key=f"xmajtop_{o['shl_idf_cd']}",
                                 use_container_width=True):
                        _xgo(("school", o["shl_idf_cd"], o["school"]))

    rel = R.major_extra(r).get("관련직업", "")
    if rel:
        with st.expander(":material/work: 관련 직업"):
            st.markdown(", ".join(R.split_related_jobs(rel)))


def _xview_subject(name):
    st.markdown(f"### :material/menu_book: {name}  ·  설치 고교")
    _subject_school_table(name, "xsub")


def _stack_recent_major():
    """현재 탐색 스택에서 가장 가까운 학과명(있으면) — 학교 화면에서 권장과목 강조용."""
    for v in reversed(st.session_state.get("xstack", [])):
        if v[0] == "major":
            return v[1]
    return None


def _xview_school(sid, name):
    info = R.school_subjects(sid)
    st.markdown(f"### :material/apartment: {info['school']}  ·  {info['sido']} {info['gugun']}")
    # 거쳐온 학과가 있으면 그 학과 권장과목을 강조(테두리+배경)
    hl_major = _stack_recent_major()
    hl_set = R.major_subject_norm_set(hl_major) if hl_major else set()
    if hl_set:
        st.caption(f"개설 과목 {info['n_subj']}개 — 과목을 누르면 그 과목 설치 고교를 봅니다. "
                   f"**강조된 과목**은 ‘{hl_major}’ 권장과목이에요.")
    else:
        st.caption(f"개설 과목 {info['n_subj']}개 — 과목을 누르면 그 과목 설치 고교를 봅니다.")
    gidx = 0
    with st.container(key="xsch_subjgrid"):
        for typ in ("일반", "진로", "융합"):
            subs = info["by_type"][typ]
            if not subs:
                continue
            n_hl = sum(1 for s in subs if R.norm_subject(s) in hl_set)
            head = f"**{typ} 선택 ({len(subs)})**"
            if hl_set and n_hl:
                head += f" · 권장 {n_hl}개"
            st.markdown(head)
            for start in range(0, len(subs), 4):
                cols = st.columns(4)
                for j, s in enumerate(subs[start:start + 4]):
                    hl = R.norm_subject(s) in hl_set
                    key = f"xschsub_hl_{gidx}" if hl else f"xschsub_{gidx}"
                    with cols[j]:
                        if st.button(s, key=key, use_container_width=True):
                            _xgo(("subject", s))
                    gidx += 1


def _xview_job(name):
    extra = R.job_extra({"id": "", "name": name})
    st.markdown(f"### :material/work: {name}")
    rel = extra.get("관련학과", "")
    if rel:
        majors = R.split_related_majors(rel)
        st.markdown(f"**:material/menu_book: 관련 학과 ({len(majors)})** — 학과를 누르면 상세를 봅니다")
        cols = st.columns(2)
        for i, m in enumerate(majors):
            with cols[i % 2]:
                if st.button(m, key=f"xjobmaj_{i}", use_container_width=True):
                    _xgo(("major", m))
    cert = extra.get("관련자격", "")
    if cert:
        certs = [c.strip() for c in cert.replace("·", ",").split(",") if c.strip()]
        with st.expander(f":material/description: 관련 자격 ({len(certs)})"):
            st.markdown(", ".join(certs))


def _xcrumb(v):
    return {"major": ":material/menu_book: ", "subject": ":material/menu_book: ", "school": ":material/apartment: ",
            "job": ":material/work: "}.get(v[0], "") + (v[2] if v[0] == "school" else v[1])


@st.dialog(":material/search: 탐색", width="large")
def explorer_dialog():
    """과목↔학교↔학과↔직업 탐색 — 단일 모달 + 네비 스택(reopen 패턴).
    어느 탭에서 항목을 클릭하든 이 모달로 상세가 뜬다. 깊이 이동은 _xgo가
    xstack에 push + rerun → 하단 가드가 모달을 다시 열어 새 화면을 그린다."""
    stack = st.session_state.get("xstack", [])
    if not stack:
        return
    # iOS 웹 스타일 헤더: 최상단 네비 바(좌:뒤로 / 우:닫기) → 그 아래 타이틀.
    # Streamlit 기본 타이틀 바·X는 CSS로 숨기고 여기서 직접 그린다.
    hc1, _, hc3 = st.columns([1.2, 3, 1.2])
    with hc1:
        if len(stack) > 1 and st.button("← 뒤로", use_container_width=True, key="x_back"):
            _xback()
    with hc3:
        if st.button("닫기 ✕", use_container_width=True, key="x_close"):
            _xclose()
    st.markdown("#### :material/search: 탐색")
    st.caption("경로: " + "  ›  ".join(_xcrumb(v) for v in stack))
    top = stack[-1]
    if top[0] == "major":
        _xview_major(top[1])
    elif top[0] == "subject":
        _xview_subject(top[1])
    elif top[0] == "school":
        _xview_school(top[1], top[2])
    elif top[0] == "job":
        _xview_job(top[1])


def _render_school_detail(r):
    """학교 상세 — 개설과목(유형별), 각 과목 클릭 시 연관 학과 모달."""
    info = R.school_subjects(r["shl_idf_cd"])
    st.markdown(f"### :material/apartment: {info['school']}  ·  {info['sido']} {info['gugun']}")
    st.caption(f"개설 과목 {info['n_subj']}개 (학교알리미 2025·2026 병합 기준). "
               "과목을 누르면 그 과목과 연관된 학과를 보여줍니다.")
    with st.container(key="schd_subjgrid"):
        for typ in ("일반", "진로", "융합"):
            subs = info["by_type"][typ]
            if not subs:
                continue
            st.markdown(f"**{typ} 선택 ({len(subs)})**")
            for start in range(0, len(subs), 4):
                cols = st.columns(4)
                for j, s in enumerate(subs[start:start + 4]):
                    with cols[j]:
                        if st.button(s, key=f"schsub_{r['shl_idf_cd']}_{typ}_{s}",
                                     use_container_width=True):
                            _xopen(("subject", s))


def _render_job_detail(r):
    extra = R.job_extra(r)
    rel = extra.get("관련학과", "")
    if rel:
        majors = R.split_related_majors(rel)
        with st.expander(f":material/menu_book: 관련 학과 ({len(majors)})", expanded=True):
            st.markdown(", ".join(majors))
    cert = extra.get("관련자격", "")
    if cert:
        certs = [c.strip() for c in cert.replace("·", ",").split(",") if c.strip()]
        with st.expander(f":material/description: 관련 자격 ({len(certs)})"):
            st.markdown(", ".join(certs))


@st.dialog("상세 정보", width="large")
def detail_modal(kind, r):
    icon = ":material/menu_book:" if kind == "major" else ":material/work:"
    st.markdown(f"### {icon} {r['name']}")
    st.markdown("**추천 근거**")
    st.markdown(reason_table_html(r["reasons"]), unsafe_allow_html=True)
    st.markdown("---")
    if kind == "major":
        _render_major_detail(r)
    else:
        _render_job_detail(r)


@st.dialog("과목 연관 학과", width="large")
def subject_majors_modal(subject_name):
    st.markdown(f"### :material/menu_book: {subject_name}")
    sort_score = st.toggle("키워드 점수순 정렬", value=True, key="sm_sort",
                           help="끄면 가나다순으로 봅니다.")
    majors = R.majors_for_subject(subject_name, sort_by_score=sort_score)
    st.caption(f"이 과목을 2022 권장 선택과목으로 두는 학과 {len(majors)}개")
    if not majors:
        st.info("연관 학과가 없어요.")
        return
    for m in majors:
        st.markdown(f"- **{m['name']}**")


@st.dialog("학과 상세", width="large")
def major_info_modal(name):
    r = R.major_by_name(name)
    if not r:
        st.info("학과 정보를 찾을 수 없어요.")
        return
    st.markdown(f"### :material/menu_book: {r['name']}")
    st.markdown("**대표 키워드**")
    st.markdown(reason_table_html(r["reasons"]), unsafe_allow_html=True)
    st.markdown("---")
    _render_major_detail(r)
    with st.expander(":material/apartment: 설치 고교 보기 (선택과목 개설 학교)"):
        subj = R.subjects_of_major(r)
        flat = [s for v in subj.values() for s in v]
        st.caption("이 학과의 권장 선택과목이 전국 몇 개 고교에 개설돼 있는지")
        for s in flat:
            n = len(R.schools_offering(s))
            st.markdown(f"- **{s}** — {n:,}개교 개설")


# %% [헤더 · 사이드바]
st.title(":material/school: M.A.P.S")
st.caption("Major · Aptitude · Path System  ·  학과 · 적성 · 진로 시스템")
st.caption("나의 관심사로부터 진로진학까지 한번에")

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
    st.markdown(f"{via_badge_html('공시')} 공시 키워드(원문)  &nbsp; "
                f"{via_badge_html('쉬운말')} 쉬운말로 매칭", unsafe_allow_html=True)

TAB_REC, TAB_SCHOOL, TAB_MAJOR = st.tabs(
    [":material/target: 학과·직업 추천", ":material/apartment: 학교별 설치과목", ":material/menu_book: 학과별 정보"])


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
        st.markdown("#### :material/key: 키워드")
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
                        + " ".join(f"<span class='kw-excl'>{t}</span>"
                                   for t in out["excluded"]),
                        unsafe_allow_html=True)
            st.caption("싫어하거나 어려워하는 것은 추천에서 제외했어요.")

        st.markdown("#### :material/target: 추천 결과")
        st.caption("추천 학과나 직업을 클릭하면 상세한 내용을 볼 수 있습니다.")
        col1, col2 = st.columns(2)
        top_m = out["majors"][0]["score"] if out["majors"] else 1
        top_j = out["jobs"][0]["score"] if out["jobs"] else 1
        with col1:
            with st.container(border=True):
                st.subheader(":material/menu_book: 추천 학과")
                if not out["majors"]:
                    st.info("매칭되는 학과가 없어요.")
                for i, r in enumerate(out["majors"], 1):
                    bc1, bc2 = st.columns([3, 2])
                    with bc1:
                        if st.button(f"{i}.  {r['name']}",
                                     key=f"maj_{i}", use_container_width=True):
                            _xopen(("major", r["name"]))
                    with bc2:
                        st.markdown(strength_html(r["score"], top_m, len(r["reasons"])),
                                    unsafe_allow_html=True)
        with col2:
            with st.container(border=True):
                st.subheader(":material/work: 추천 직업")
                if not out["jobs"]:
                    st.info("매칭되는 직업이 없어요.")
                for i, r in enumerate(out["jobs"], 1):
                    bc1, bc2 = st.columns([3, 2])
                    with bc1:
                        if st.button(f"{i}.  {r['name']}",
                                     key=f"job_{i}", use_container_width=True):
                            _xopen(("job", r["name"]))
                    with bc2:
                        st.markdown(strength_html(r["score"], top_j, len(r["reasons"])),
                                    unsafe_allow_html=True)

        st.markdown("---")
        st.subheader(":material/explore: 추천 진로")
        st.caption("추천 학과와 직업이 **공통 키워드**로 이어지는 진로 조합입니다. "
                   "공통 키워드가 많을수록(진하게 강조) 연결이 강합니다.")
        if not out["pairs"]:
            st.info("연계 진로를 만들 수 없어요.")
        else:
            st.markdown("".join(pair_card_html(p) for p in out["pairs"]),
                        unsafe_allow_html=True)


# %% [탭2 — 학교별 설치과목: 과목으로 찾기 / 학교로 찾기]
with TAB_SCHOOL:
    st.caption(f"학교알리미 2025·2026 공시 병합 · 데이터 보유 전국 {len(R.SCHOOL_DB):,}개교")
    mode = st.radio("찾는 방법", ["학교로 찾기", "과목으로 찾기"], horizontal=True,
                    key="school_tab_mode")

    if mode == "과목으로 찾기":
        st.markdown("##### :material/menu_book: 과목으로 찾기 — 유형 → 과목을 고르면 "
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
            st.markdown(f"### :material/menu_book: {subject_name}  ·  {ftype} 선택")

            # ── 연관 학과 (정렬 토글) ──
            sort_score = st.toggle("학과 키워드 점수순 정렬", value=False,
                                   key="subj_sort", help="끄면 가나다순")
            majors = R.majors_for_subject(subject_name, sort_by_score=sort_score)
            st.markdown(f"#### :material/school: 연관 학과 ({len(majors)})")
            st.caption("이 과목을 2022 권장 선택과목으로 두는 학과")
            if len(majors) > 8:
                show_n = st.slider("표시할 학과 수", 4, min(30, len(majors)),
                                   8, key="subj_majn")
            else:
                show_n = len(majors)
            for m in majors[:show_n]:
                with st.expander(f"**{m['name']}**"):
                    # 연관 학과의 설치대학
                    uinfo = R.universities_for(m["name"])
                    if uinfo.get("univ_count", 0) > 0:
                        st.markdown(f"**:material/account_balance: 설치대학 {uinfo['univ_count']}곳** "
                                    "· 대학명 클릭 시 EBSi")
                        for region, unis in list(uinfo["by_region"].items()):
                            names_u = ", ".join(univ_link(u["대학명"]) for u in unis[:10])
                            more = f" 외 {len(unis)-10}곳" if len(unis) > 10 else ""
                            st.markdown(f"- **{region}** ({len(unis)}): {names_u}{more}",
                                        unsafe_allow_html=True)
                    else:
                        st.caption(":material/account_balance: 설치대학 정보 없음(전문대·교양학부 등)")

            # ── 이 과목을 개설한 고교 — 탐색 패널과 동일한 지역그룹 칩 그리드 ──
            st.markdown("#### :material/apartment: 이 과목 설치학교")
            _subject_school_table(subject_name, "subjpage")

    else:  # 학교로 찾기
        st.markdown("##### :material/apartment: 학교로 찾기 — 학교를 고르면 개설과목을 보여줍니다")
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
@st.fragment
def render_major_info_tab():
    """분류 선택 시 이 영역만 재실행(전체 탭 리렌더 방지 → 반응 빠름)."""
    st.markdown("##### :material/menu_book: 학과별 정보 — 학과를 고르면 키워드·설치대학·선택과목을 보여줍니다")
    names = R.major_names()

    # ── 검색 ──
    qc1, qc2 = st.columns([5, 1])
    with qc1:
        mq = st.text_input("학과명 검색", key="major_q",
                           placeholder="예) 시각디자인, 기계, 간호",
                           label_visibility="collapsed")
    with qc2:
        st.button(":material/search: 검색", use_container_width=True, key="major_search_btn")

    # ── 분류로 찾기 (대 > 중 > 소) ──
    st.caption("분류로 찾기 — **대분류 → 중분류**까지 고르면 학과가 나타나고, 소분류를 고르면 더 좁혀집니다.")
    dae, jung, so = _category_picker()

    # ── 결과 목록 ──
    if dae and jung:
        so_sel = None if (not so or so == "전체") else so
        results = R.majors_in_category(dae, jung, so_sel)
        if mq.strip():
            results = [n for n in results if mq.strip() in n]
        loc = f"{dae} › {jung}" + (f" › {so_sel}" if so_sel else "")
        st.markdown(f"**:material/category: {loc}**  ·  {len(results)}개 학과")
    elif mq.strip():
        results = [n for n in names if mq.strip() in n]
        st.markdown(f"**:material/search: 검색 결과**  ·  {len(results)}개 학과")
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
                    _xopen(("major", nm))
        if len(results) > GRID_CAP:
            st.caption(f"… 외 {len(results) - GRID_CAP}개. 검색·소분류로 좁혀보세요.")


with TAB_MAJOR:
    render_major_info_tab()


# ── 탐색 모달(단일 dialog + reopen 패턴) — 네비게이션 시에만 1회 재오픈 ──
# 모달이 열려 있는 동안의 내부 위젯 조작은 Streamlit이 모달 본문을 자동 재실행한다.
# _xopen/_xgo/_xback가 켠 xreopen을 여기서 소비(1회) → 무관 리런 시 되살아나지 않음.
if st.session_state.get("xreopen"):
    st.session_state["xreopen"] = False
    explorer_dialog()
