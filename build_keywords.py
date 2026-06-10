# -*- coding: utf-8 -*-
"""
[Pass 2] 키워드 재추출 파이프라인
원본 CSV + 사전 → tokenize → TF-IDF → 산출물 생성

실행:  python build_keywords.py
입력:  job_info.csv, major_info.csv (원본)
       stopwords.json, compounds.json (사전, tokenizer.py가 로드)
출력:  doc_keyword_weights.json, keywords_top20.csv, vectorizer_meta.json
사전을 수정한 뒤 이 스크립트만 다시 돌리면 키워드가 갱신됩니다.
"""
import json
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from tokenizer import tokenize   # 사전·사용자사전·규칙 모두 포함

# 키워드 텍스트로 합칠 컬럼 (노이즈·매핑 컬럼 제외)
JOB_TEXT = ["직업명", "관련직업명", "하는일", "핵심능력", "적성 및 흥미_적성",
            "적성 및 흥미_흥미", "태그", "직업탐색_진로 탐색 활동",
            "준비방법_정규교육과정", "준비방법_직업훈련", "준비방법_입직 및 취업방법"]
MAJ_TEXT = ["학과명", "학과개요_학과개요", "학과개요_학과특성", "학과개요_흥미와 적성",
            "학과개요_진로 탐색 활동", "학과개요_대학 주요 교과목",
            "학과개요_졸업 후 진출 분야", "학과개요_관련 직업"]

MAX_DF, MIN_DF, TOPN = 0.5, 2, 20

def build_units(path, idc, nc, cols, typ):
    df = pd.read_csv(path, encoding="utf-8-sig")
    us = []
    for _, r in df.iterrows():
        parts = [str(r[c]).strip() for c in cols if isinstance(r.get(c), str) and r.get(c).strip()]
        us.append({"type": typ, "id": str(r[idc]), "name": str(r[nc]), "text": "  ".join(parts)})
    return us

def main():
    units = build_units("job_info.csv", "job_id", "직업명", JOB_TEXT, "직업") + \
            build_units("major_info.csv", "major_id", "학과명", MAJ_TEXT, "학과")
    corpus = [tokenize(u["text"]) for u in units]

    vec = TfidfVectorizer(analyzer=lambda x: x, max_df=MAX_DF, min_df=MIN_DF)
    X = vec.fit_transform(corpus)
    vocab = np.array(vec.get_feature_names_out())
    print(f"문서 {len(units)} (직업/학과) / 어휘 {len(vocab):,}")

    # 1) 문서별 전체 키워드:가중치
    Xc = X.tocsr(); weights = {}
    for k, u in enumerate(units):
        row = Xc[k]
        d = {vocab[j]: round(float(v), 4) for j, v in zip(row.indices, row.data)}
        d = dict(sorted(d.items(), key=lambda x: -x[1]))
        weights[u["name"]] = {"type": u["type"], "id": u["id"], "keywords": d}
    json.dump(weights, open("doc_keyword_weights.json", "w"), ensure_ascii=False)

    # 2) 상위 TOPN wide CSV
    rows = []
    for k, u in enumerate(units):
        row = X[k].toarray().ravel(); idx = row.argsort()[::-1][:TOPN]
        ks = [vocab[j] for j in idx if row[j] > 0]
        rows.append({"type": u["type"], "id": u["id"], "name": u["name"],
                     **{f"kw{i+1}": (ks[i] if i < len(ks) else "") for i in range(TOPN)}})
    pd.DataFrame(rows).to_csv("keywords_top20.csv", index=False, encoding="utf-8-sig")

    # 3) vocab + idf (발화 벡터화용)
    json.dump({"vocab": vocab.tolist(), "idf": vec.idf_.tolist()},
              open("vectorizer_meta.json", "w"), ensure_ascii=False)
    print("저장: doc_keyword_weights.json / keywords_top20.csv / vectorizer_meta.json")

if __name__ == "__main__":
    main()
