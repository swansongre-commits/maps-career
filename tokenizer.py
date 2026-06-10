# -*- coding: utf-8 -*-
"""
학과·직업 추천기 공용 토크나이저 (최종본)
- 문서 키워드 추출과 '학생 발화' 처리에 반드시 동일하게 사용 (매칭 일관성)
- kiwipiepy 기준. Okt로 교체 시 _nouns_in_eojeol()의 명사 추출부만 바꾸면 됨.
- 같은 폴더에 stopwords.json, compounds.json 필요.
"""
import json
from kiwipiepy import Kiwi

kiwi = Kiwi()
NOUN = {"NNG", "NNP", "SL", "SH"}

STOP = set(json.load(open("stopwords.json", encoding="utf-8")))
COMP = list(json.load(open("compounds.json", encoding="utf-8")).keys())

for _w in COMP:
    kiwi.add_user_word(_w, "NNP")
for _w in ["메카트로닉스", "빅데이터", "데이터사이언스", "사물인터넷", "메타버스", "블록체인"]:
    kiwi.add_user_word(_w, "NNP")

SPLIT_MAP = {
    "논리력공간지각": ["논리력", "공간지각"],
    "예술시각능력창의력": ["예술시각능력", "창의력"],
    "자연과학계열": ["자연과학"],
    "수리논리력공간지각력": ["수리논리력", "공간지각력"],
}
INST_SUF = ("연구원", "개발원", "진흥원", "평가원", "연구소",
            "위원회", "공단", "공사", "협회", "학회", "재단", "연맹", "정보원")
JOSA = ("으로서", "으로써", "으로", "에서", "에게", "까지", "부터", "이나", "라도",
        "과의", "와의", "로서", "로써",
        "을", "를", "이", "가", "은", "는", "의", "에", "도", "만", "와", "과", "나", "랑", "로")

_cache = {}

def _strip_josa(t):
    for j in JOSA:
        if t.endswith(j) and len(t) - len(j) >= 2:
            return t[:-len(j)]
    return t

def _strip_suffix(t):
    for suf in ["공학과", "공학부", "공학전공", "공학계열", "공학대학"]:
        if t.endswith(suf) and len(t) - len(suf) >= 1:
            return t[:-len(suf)] + "공학"
    for s in ["학과", "학부", "전공", "대학교", "대학", "학교", "계열"]:
        if t.endswith(s) and len(t) - len(s) >= 2:
            return t[:-len(s)]
    return t

def _nouns_in_eojeol(w):
    if w in _cache:
        return _cache[w]
    run, out = [], []
    for tk in kiwi.tokenize(w):
        if tk.tag in NOUN:
            run.append(tk.form)
        else:
            if run:
                out.append("".join(run)); run = []
    if run:
        out.append("".join(run))
    _cache[w] = [_strip_suffix(_strip_josa(t)) for t in out]
    return _cache[w]

def _is_inst(t):
    return t.startswith(("한국", "국립", "대한", "전국", "서울")) and len(t) >= 6 and t.endswith(INST_SUF)

def tokenize(text):
    res = []
    for w in str(text).split():
        for t in _nouns_in_eojeol(w):
            res.extend(SPLIT_MAP.get(t, [t]))
    return [t for t in res if len(t) >= 2 and t not in STOP and not _is_inst(t)]


if __name__ == "__main__":
    print(tokenize("로봇과 인공지능에 관심있고 메카트로닉스를 공부하고 싶어요"))
