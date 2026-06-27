# -*- coding: utf-8 -*-
"""M.A.P.S 주니어 (초·중용) — 가벼운 진로발견.

설계(보고서 기준):
  · 미션: "좋아하는 걸 말하면 세상의 일들이 카드로 펼쳐지는 진로 도감."
  · 대상: 초3~중3. 정답 1개가 아니라 카드 3장, 점수·순위·대학·입시·선택과목 비노출.
  · 흐름: 관심사 칩/직접쓰기 → 직업 카드 덱 → ⭐도감 수집 → 키워드로 인접 재탐색.
재사용: recommender.recommend()(발화→키워드→직업 순위). 대학·schools.db 모듈은 호출하지 않음.
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
    # content.db(재수집 정본) 우선, 없으면 junior_jobs.json 폴백
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

# 관심사 칩 (라벨, 이모지, 발화) — 무입력 진입용
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

POOL = 16       # 한 발화당 가져올 직업 후보 수
PER_PAGE = 8    # 4열 그리드에 한 번에 보여줄 카드 수(2행)

CSS = """
<style>
.jr-hero{font-size:1.55rem;font-weight:800;color:#141414;margin:.2rem 0 .1rem}
.jr-sub{color:#6B6B6B;margin:0 0 .8rem}
/* 관심사 칩 버튼 + 더보기/직접쓰기 영역의 버튼을 둥글고 큼직하게 */
div[data-testid="stButton"] > button{
  border-radius:999px;border:1.5px solid #E4E4E4;padding:.55rem .2rem;
  font-size:1.02rem;font-weight:600;background:#fff;transition:.12s;}
div[data-testid="stButton"] > button:hover{border-color:#141414;background:#FAFAFA;}
/* 관심사 칩: 정사각형 타일(가로=세로) 폭 고정 + 칼럼 중앙 정렬 — 너무 넓지 않게 */
.st-key-jr_chips div[data-testid="stButton"]{display:flex;justify-content:center;}
.st-key-jr_chips div[data-testid="stButton"] > button{
  width:132px;max-width:132px;aspect-ratio:1/1;padding:.3rem;
  border-radius:18px;font-size:1.06rem;font-weight:700;line-height:1.3;}
/* 직업 카드: 4열 그리드 · 세로가 긴 카드(이모지·제목 크게) */
/* 카드 비율 고정: 세로형 3:4 (폭에 상관없이 같은 비율), 폭 상한 210px */
.jr-card{border:1.5px solid #E4E4E4;border-radius:16px;padding:20px 14px 14px;
  background:#fff;text-align:center;width:100%;max-width:210px;margin:0 auto 6px;
  aspect-ratio:3/4;display:flex;flex-direction:column;align-items:center;overflow:hidden}
.jr-emoji{font-size:3.2rem;line-height:1.05;margin:.1rem 0 .25rem}
.jr-name{width:100%;font-size:1.16rem;font-weight:800;color:#141414;margin:.1rem 0 .4rem;
  line-height:1.25;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
  overflow:hidden}
.jr-blurb{width:100%;font-size:.85rem;color:#4B5563;line-height:1.45;margin:.1rem 0 0;
  text-align:left;display:-webkit-box;-webkit-line-clamp:6;-webkit-box-orient:vertical;
  overflow:hidden}
.jr-dex{display:inline-block;border:1.5px solid #E4E4E4;border-radius:999px;
  padding:.25rem .7rem;margin:.2rem .3rem .2rem 0;font-size:.95rem;background:#fff;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

ss = st.session_state
ss.setdefault("jr_query", "")
ss.setdefault("jr_offset", 0)
ss.setdefault("jr_dex", [])     # 수집한 직업명 리스트(순서 보존)


def _emoji(name):
    return JOBMETA.get(name, {}).get("emoji", "💼")


def set_query(q):
    ss["jr_query"] = q
    ss["jr_offset"] = 0


# ── 헤더 ──────────────────────────────────────────────
st.markdown('<div class="jr-hero">🧭 M.A.P.S 주니어</div>', unsafe_allow_html=True)
st.markdown('<div class="jr-sub">좋아하는 걸 말하면, 세상의 일들이 카드로 펼쳐져요!</div>',
            unsafe_allow_html=True)

# ── 관심사 칩 (무입력 진입) — 4열, 정방형에 가깝게 ────────
st.markdown("##### 무엇을 좋아해요?")
with st.container(key="jr_chips"):
    for row_start in range(0, len(CHIPS), 4):
        cols = st.columns(4)
        for c, (label, em, utter) in zip(cols, CHIPS[row_start:row_start + 4]):
            if c.button(f"{em} {label}", key=f"chip_{label}", use_container_width=True):
                set_query(utter)

# 직접 쓰기(보조)
with st.expander("✏️ 직접 쓰기"):
    typed = st.text_input("좋아하는 걸 자유롭게 적어줘",
                          key="jr_typed", placeholder="예) 나는 비행기랑 하늘이 좋아",
                          label_visibility="collapsed")
    if st.button("이걸로 찾기", key="jr_typed_go"):
        if typed.strip():
            set_query(typed.strip())

# ── 나의 진로도감 ─────────────────────────────────────
if ss["jr_dex"]:
    st.markdown(f"##### 🗂️ 나의 진로도감 &nbsp;({len(ss['jr_dex'])})")
    chips_html = "".join(
        f'<span class="jr-dex">{_emoji(n)} {n}</span>' for n in ss["jr_dex"])
    st.markdown(chips_html, unsafe_allow_html=True)
    if st.button("도감 비우기", key="jr_dex_clear"):
        ss["jr_dex"] = []
        st.rerun()

st.divider()

# ── 결과 카드 덱 ──────────────────────────────────────
q = ss["jr_query"]
if not q:
    st.info("위에서 좋아하는 걸 골라줘! 🐶🚀🎨")
    st.stop()

out = R.recommend(q, top_n=POOL, pair_k=0, use_llm=False)
jobs = out.get("jobs", [])

# 매칭된 쉬운말 키워드(인접 재탐색용)
kw_terms = []
for j in jobs[:6]:
    for rs in j.get("reasons", []):
        t = rs.get("term")
        if t and t not in kw_terms:
            kw_terms.append(t)

st.markdown(f"#### 💬 “{q}” 라고 말했어요")

if not jobs:
    # 막다른 길 금지 — 안전한 폴백
    st.warning("음… 그건 아직 잘 모르겠어! 대신 이런 건 어때? 🎲")
    fallback = ["수의사", "요리사", "프로그래머", "디자이너", "운동선수", "과학자"]
    jobs = [{"name": n, "reasons": []} for n in fallback]
    kw_terms = []

# 인접 재탐색 칩
if kw_terms:
    st.caption("🔖 이 말도 눌러서 더 찾아봐")
    kcols = st.columns(min(len(kw_terms), 6))
    for c, t in zip(kcols, kw_terms[:6]):
        if c.button(f"🔖 {t}", key=f"kw_{t}", use_container_width=True):
            set_query(t)
            st.rerun()

# 현재 페이지 윈도우(더보기로 순환)
total = len(jobs)
start = ss["jr_offset"] % total if total else 0
window = [jobs[(start + i) % total] for i in range(min(PER_PAGE, total))]

with st.container(key="jr_grid"):
    for row_start in range(0, len(window), 4):
        cols = st.columns(4)
        for col, j in zip(cols, window[row_start:row_start + 4]):
            name = j["name"]
            meta = JOBMETA.get(name, {})
            em = meta.get("emoji", "💼")
            blurb = meta.get("blurb", "")
            with col:
                st.markdown(
                    f'<div class="jr-card"><div class="jr-emoji">{em}</div>'
                    f'<div class="jr-name" title="{name}">{name}</div>'
                    + (f'<div class="jr-blurb">{blurb}</div>' if blurb else "")
                    + '</div>', unsafe_allow_html=True)
                already = name in ss["jr_dex"]
                if st.button("✅ 모았어요" if already else "⭐ 모으기",
                             key=f"add_{name}", use_container_width=True, disabled=already):
                    ss["jr_dex"].append(name)
                    st.rerun()

# 더보기
if total > PER_PAGE:
    if st.button("♻️ 다른 일 더 보기", key="jr_more"):
        ss["jr_offset"] += PER_PAGE
        st.rerun()

st.caption("※ 주니어는 흥미를 넓혀가는 도구예요. 점수·순위·대학·입시는 보여주지 않아요. "
           "고등학생이 되면 ‘고교 · 선택과목’ 메뉴에서 더 깊이 찾아볼 수 있어요.")
