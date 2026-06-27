# -*- coding: utf-8 -*-
"""M.A.P.S 주니어 (초·중용) — 가벼운 진로발견.

설계: 디자이너 시안(3안 카드 + 페이지 전체) 반영.
  · 미션: "좋아하는 걸 말하면 세상의 일들이 카드로 펼쳐지는 진로 도감."
  · 흐름: 관심사 타일 → 직업 카드(아이콘 타일+칩 모으기, 수집 시 초록) → 나의 진로도감.
재사용: recommender.recommend(). 대학·schools.db 모듈은 호출하지 않음.
"""
import json
import os
import streamlit as st

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@st.cache_resource
def _engine():
    import recommender
    return recommender


@st.cache_data
def _jobmeta():
    import content_db
    if content_db.available():
        meta = content_db.junior_job_meta()
        if meta:
            return meta
    p = os.path.join(BASE, "junior_jobs.json")
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    return {}


R = _engine()
JOBMETA = _jobmeta()

CHIPS = [
    ("동물", "🐶", "나는 동물이 좋아"),
    ("우주", "🚀", "나는 우주랑 별이 궁금해"),
    ("그림", "🎨", "나는 그림 그리는 게 좋아"),
    ("게임", "🎮", "나는 게임이 좋아"),
    ("운동", "⚽", "나는 운동하는 게 좋아"),
    ("요리", "🍳", "나는 요리하는 게 좋아"),
    ("음악", "🎵", "나는 음악이 좋아"),
    ("공룡", "🦕", "나는 공룡이랑 옛날 생물이 좋아"),
    ("로봇", "🤖", "나는 로봇이랑 기계가 좋아"),
    ("바다", "🌊", "나는 바다랑 물고기가 좋아"),
    ("식물", "🌱", "나는 식물이랑 꽃이 좋아"),
    ("책", "📚", "나는 책 읽고 글 쓰는 게 좋아"),
]

POOL = 16
PER_PAGE = 8

CSS = """
<style>
.jr-hero{text-align:center;font-size:1.85rem;font-weight:800;color:#141414;margin:.4rem 0 .15rem;letter-spacing:-.5px}
.jr-sub{text-align:center;color:#6B6B6B;font-size:.95rem;margin:0 0 1rem}
.jr-sec{font-size:1.18rem;font-weight:800;color:#141414;margin:1.5rem 0 .8rem}
.jr-dexsub{font-size:.86rem;color:#6B6B6B;margin:-.3rem 0 .7rem}
/* 공통 버튼(둥근 흰색) */
div[data-testid="stButton"] > button{border-radius:999px;border:1.5px solid #E4E4E4;
  padding:.5rem .2rem;font-size:1rem;font-weight:700;background:#fff;transition:.12s;}
div[data-testid="stButton"] > button:hover{border-color:#141414;background:#FAFAFA;}
/* 관심사 타일: 정사각형 + 큰 이모지(버튼 라벨=이모지), 라벨은 아래 */
.st-key-jr_chips div[data-testid="stButton"]{display:flex;justify-content:center;}
.st-key-jr_chips div[data-testid="stButton"] > button{
  width:100%;max-width:120px;aspect-ratio:1/1;margin:0 auto;padding:.2rem;border-radius:18px;}
.st-key-jr_chips div[data-testid="stButton"] > button p{font-size:2.7rem;line-height:1;margin:0}
.jr-tilelabel{text-align:center;font-size:.9rem;font-weight:700;color:#6B6B6B;margin:1px 0 4px}
/* 결과 박스 */
.st-key-jr_resultbox{background:#F5F5F5;border-radius:16px;padding:15px 17px;}
.jr-rtitle{font-size:1.06rem;font-weight:800;color:#141414}
.jr-rsub{font-size:.85rem;color:#6B6B6B;margin:.6rem 0 .1rem}
.st-key-jr_resultbox div[data-testid="stButton"] > button{
  width:auto;padding:.32rem .8rem;font-size:.85rem;border-radius:999px;}
/* 직업 카드(3안): 아이콘 타일 + 제목 + 설명 + 칩(자연 흐름, 폭 상한) */
[class*="st-key-jcard"]{border:1.5px solid #E4E4E4;border-radius:16px;background:#fff;
  padding:16px 15px 15px;max-width:208px;margin:0 auto 6px;box-sizing:border-box;}
.jr-ic{width:50px;height:50px;border-radius:13px;display:flex;align-items:center;
  justify-content:center;font-size:30px;margin-bottom:10px;}
.jr-nm{font-size:1rem;font-weight:800;color:#141414;line-height:1.25;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.jr-bl{margin-top:6px;font-size:.8rem;color:#6B6B6B;line-height:1.42;min-height:3.4em;
  display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
[class*="st-key-jcard"] div[data-testid="stButton"]{margin-top:10px;}
[class*="st-key-jcard"] div[data-testid="stButton"] > button{
  width:auto;border:1.5px solid #2563EB;color:#2563EB;background:#fff;
  font-size:.82rem;font-weight:700;padding:.34rem .9rem;border-radius:999px;}
[class*="st-key-jcard"] div[data-testid="stButton"] > button:disabled{opacity:1;}
/* 나의 진로도감 */
.jr-dexgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:.2rem 0 .7rem}
.jr-dexcard{border:2px solid #16A34A;background:#E7F6EC;border-radius:14px;padding:14px 6px;
  display:flex;flex-direction:column;align-items:center;gap:5px;text-align:center}
.jr-dexcard .e{font-size:2.2rem;line-height:1}
.jr-dexcard .n{font-size:.78rem;font-weight:700;color:#141414;line-height:1.2}
.jr-dexempty{border:1px dashed #D7D7D7;border-radius:14px;min-height:104px;display:flex;
  align-items:center;justify-content:center;color:#CFCFCF;font-size:1.9rem}
.jr-foot{margin-top:1.6rem;border-top:1px solid #E4E4E4;padding-top:1.1rem;text-align:center;
  font-size:.8rem;color:#6B6B6B;line-height:1.7}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

ss = st.session_state
ss.setdefault("jr_query", "")
ss.setdefault("jr_offset", 0)
ss.setdefault("jr_dex", [])


def _emoji(name):
    return JOBMETA.get(name, {}).get("emoji", "💼")


def set_query(q):
    ss["jr_query"] = q
    ss["jr_offset"] = 0


def render_dex():
    dex = ss["jr_dex"]
    st.markdown('<div class="jr-sec">🗂️ 나의 진로도감</div>', unsafe_allow_html=True)
    n = len(dex)
    if n:
        sub = (f"마음에 든 직업을 모아봐요. 지금까지 "
               f"<b style='color:#16A34A'>{n}개</b> 모았어요!")
    else:
        sub = "마음에 든 직업의 ‘모으기’를 누르면 여기에 모여요."
    st.markdown(f'<div class="jr-dexsub">{sub}</div>', unsafe_allow_html=True)
    empties = 4 if n == 0 else (4 - n % 4) % 4
    cells = [f'<div class="jr-dexcard"><span class="e">{_emoji(x)}</span>'
             f'<span class="n">{x}</span></div>' for x in dex]
    cells += ['<div class="jr-dexempty">＋</div>'] * empties
    st.markdown(f'<div class="jr-dexgrid">{"".join(cells)}</div>',
                unsafe_allow_html=True)
    if n:
        if st.button("도감 비우기", key="jr_dex_clear"):
            ss["jr_dex"] = []
            st.rerun()


# ── 헤더 ──────────────────────────────────────────────
st.markdown('<div class="jr-hero">M.A.P.S 주니어</div>', unsafe_allow_html=True)
st.markdown('<div class="jr-sub">좋아하는 걸 말하면, 세상의 일들이 카드로 펼쳐져요!</div>',
            unsafe_allow_html=True)

# ── 관심사 타일 ───────────────────────────────────────
st.markdown('<div class="jr-sec">무엇을 좋아해요?</div>', unsafe_allow_html=True)
with st.container(key="jr_chips"):
    for row_start in range(0, len(CHIPS), 4):
        cols = st.columns(4)
        for c, (label, em, utter) in zip(cols, CHIPS[row_start:row_start + 4]):
            with c:
                if st.button(em, key=f"chip_{label}", use_container_width=True):
                    set_query(utter)
                    st.rerun()
                st.markdown(f'<div class="jr-tilelabel">{label}</div>',
                            unsafe_allow_html=True)
                if ss["jr_query"] == utter:   # 선택된 타일 초록
                    st.markdown(
                        f"<style>.st-key-chip_{label} button{{"
                        f"border-color:#16A34A!important;background:#E7F6EC!important;}}"
                        f"</style>", unsafe_allow_html=True)

with st.expander("✏️ 직접 쓰기"):
    typed = st.text_input("좋아하는 걸 자유롭게 적어줘", key="jr_typed",
                          placeholder="예) 나는 비행기랑 하늘이 좋아",
                          label_visibility="collapsed")
    if st.button("이걸로 찾기", key="jr_typed_go"):
        if typed.strip():
            set_query(typed.strip())
            st.rerun()

# ── 결과 ──────────────────────────────────────────────
q = ss["jr_query"]
if q:
    out = R.recommend(q, top_n=POOL, pair_k=0, use_llm=False)
    jobs = out.get("jobs", [])
    kw_terms = []
    for j in jobs[:6]:
        for rs in j.get("reasons", []):
            t = rs.get("term")
            if t and t not in kw_terms:
                kw_terms.append(t)
    if not jobs:
        jobs = [{"name": n, "reasons": []} for n in
                ("수의사", "요리사", "프로그래머", "디자이너", "운동선수", "과학자")]
        kw_terms = []

    with st.container(key="jr_resultbox"):
        st.markdown(f'<div class="jr-rtitle">💬 “{q}” 라고 말했어요</div>',
                    unsafe_allow_html=True)
        if kw_terms:
            st.markdown('<div class="jr-rsub">이런 것도 좋아해요?</div>',
                        unsafe_allow_html=True)
            kcols = st.columns(min(len(kw_terms), 6))
            for c, t in zip(kcols, kw_terms[:6]):
                if c.button(f"🔖 {t}", key=f"kw_{t}", use_container_width=False):
                    set_query(t)
                    st.rerun()

    st.markdown('<div class="jr-sec">이런 일들이 있어요 ✨</div>', unsafe_allow_html=True)
    total = len(jobs)
    start = ss["jr_offset"] % total if total else 0
    window = [jobs[(start + i) % total] for i in range(min(PER_PAGE, total))]

    for row_start in range(0, len(window), 4):
        cols = st.columns(4)
        for ci, j in enumerate(window[row_start:row_start + 4]):
            idx = row_start + ci
            name = j["name"]
            meta = JOBMETA.get(name, {})
            em = meta.get("emoji", "💼")
            blurb = meta.get("blurb", "")
            collected = name in ss["jr_dex"]
            icbg = "#E7F6EC" if collected else "#F5F5F5"
            with cols[ci]:
                with st.container(key=f"jcard{idx}"):
                    st.markdown(
                        f'<div class="jr-ic" style="background:{icbg}">{em}</div>'
                        f'<div class="jr-nm" title="{name}">{name}</div>'
                        + (f'<div class="jr-bl">{blurb}</div>' if blurb else ""),
                        unsafe_allow_html=True)
                    if st.button("✓ 모았어요" if collected else "＋ 모으기",
                                 key=f"add_{name}", disabled=collected):
                        ss["jr_dex"].append(name)
                        st.rerun()
                if collected:
                    st.markdown(
                        f"<style>.st-key-jcard{idx}{{border-color:#16A34A!important;"
                        f"border-width:2px!important;}}"
                        f".st-key-jcard{idx} div[data-testid='stButton'] > button{{"
                        f"border-color:#16A34A!important;background:#16A34A!important;"
                        f"color:#fff!important;}}</style>", unsafe_allow_html=True)

    if total > PER_PAGE:
        if st.button("♻️ 다른 일 더 보기", key="jr_more"):
            ss["jr_offset"] += PER_PAGE
            st.rerun()
else:
    st.info("위에서 좋아하는 걸 골라줘! 🐶🚀🎨")

# ── 나의 진로도감 (항상 하단) ─────────────────────────
render_dex()

# ── 푸터 ──────────────────────────────────────────────
st.markdown(
    '<div class="jr-foot">🌈 여기서는 점수·순위·대학·입시를 보여주지 않아요.<br>'
    '좋아하는 마음을 따라 세상의 일들을 천천히 구경해요.</div>',
    unsafe_allow_html=True)
