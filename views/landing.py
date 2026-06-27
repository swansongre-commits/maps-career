# -*- coding: utf-8 -*-
"""M.A.P.S 랜딩 — 대상(초중 / 고교) 선택 화면.

라우팅 메모: st.navigation에서 '기본 페이지'는 루트('/')에서만 서비스되고
자기 url_path로는 라우팅되지 않는다(예: 기본 페이지에 url_path='1'을 줘도 '/1'은 404→루트 폴백).
그래서 주니어/고교를 둘 다 '비-기본'으로 두고 이 랜딩을 기본으로 삼아 '/1','/2'를 깨끗이 노출한다.
"""
import streamlit as st

st.markdown("""
<style>
.lp-hero{text-align:center;margin:2.2rem 0 .4rem;font-size:2.0rem;font-weight:800;color:#141414}
.lp-sub{text-align:center;color:#6B6B6B;margin-bottom:2.0rem}
.lp-card{border:1.5px solid #E4E4E4;border-radius:18px;padding:26px 22px 10px;background:#fff;
  text-align:center;min-height:210px}
.lp-emoji{font-size:3rem;margin:.2rem 0}
.lp-title{font-size:1.3rem;font-weight:800;color:#141414;margin:.2rem 0}
.lp-desc{color:#6B6B6B;font-size:.95rem;line-height:1.5;margin:.4rem 0 .8rem}
div[data-testid="stButton"] > button{border-radius:999px;padding:.6rem 0;font-weight:700;font-size:1.05rem}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="lp-hero">🎓 M.A.P.S</div>', unsafe_allow_html=True)
st.markdown('<div class="lp-sub">Major · Aptitude · Path System — 누구를 위한 진로 찾기인가요?</div>',
            unsafe_allow_html=True)

c1, c2 = st.columns(2, gap="large")
with c1:
    st.markdown(
        '<div class="lp-card"><div class="lp-emoji">🧭</div>'
        '<div class="lp-title">주니어 · 초·중</div>'
        '<div class="lp-desc">좋아하는 걸 말하면 직업 카드가 펼쳐지는<br>'
        '가벼운 진로 도감. 점수·입시 없이 흥미 탐색.</div></div>',
        unsafe_allow_html=True)
    if st.button("초·중학생용 시작하기", key="go_jr", use_container_width=True, type="primary"):
        st.switch_page("views/junior.py")
with c2:
    st.markdown(
        '<div class="lp-card"><div class="lp-emoji">🎓</div>'
        '<div class="lp-title">고교 · 선택과목</div>'
        '<div class="lp-desc">관심사 → 학과·직업 → 2022 권장 선택과목 →<br>'
        '우리 학교 개설여부까지. 고교학점제 결정 도우미.</div></div>',
        unsafe_allow_html=True)
    if st.button("고등학생용 시작하기", key="go_hs", use_container_width=True):
        st.switch_page("views/highschool.py")

st.caption("　")
st.caption("바로가기:  초·중용 → 주소 끝에 **/1**　·　고교용 → **/2**")
