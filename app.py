# -*- coding: utf-8 -*-
"""M.A.P.S 라우터 — 멀티페이지 진입점.

서비스 분리:
  · /1 → 주니어(초·중용): 가벼운 진로발견. 좋아하는 걸 말하면 직업 카드가 펼쳐지는 도감.
         → views/junior.py
  · /2 → 고교용: 고교학점제 선택과목 결정 도우미(학과·직업·설치대학·선택과목·개설여부).
         → views/highschool.py
  · /rebuild → 과목선택 내비게이터(자체 서비스 프로토타입, v1.1 화면설계).
         → views/course_navigator.py

배포: 메인 파일은 app.py. 루트 URL은 기본 페이지(주니어)로 열리고, /1·/2·/rebuild로 직접 접근.
set_page_config는 라우터에서 1회만 호출한다(페이지 스크립트에서는 호출 금지).
"""
import streamlit as st

st.set_page_config(page_title="M.A.P.S", page_icon="🎓", layout="wide")

# 기본 페이지(랜딩)는 루트('/')에서 대상 선택. 주니어/고교는 비-기본 → '/1','/2' 라우팅.
pages = [
    st.Page("views/landing.py", title="홈", icon="🎓", default=True),
    st.Page("views/junior.py", title="주니어 · 초중", icon="🧭", url_path="1"),
    st.Page("views/highschool.py", title="고교 · 선택과목", icon="🎓", url_path="2"),
    st.Page("views/legacy.py", title="원본(분리 전 통합)", icon="🗂️", url_path="3"),
    st.Page("views/course_navigator.py", title="과목선택 내비게이터", icon="🧭", url_path="rebuild"),
]
st.navigation(pages).run()
