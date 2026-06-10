# 학과·직업 추천 서비스 (전체 산출물)

커리어넷 원문 → 키워드 추출 → 학과·직업 추천 파일럿.
**Claude Code로 이어서 작업하려면 먼저 `CLAUDE.md`를 읽으세요.**

## 빠른 실행
```bash
pip install -r requirements.txt
streamlit run app.py          # 파일럿 (localhost:8501)
```

## 스크립트
- `build_keywords.py`     사전 수정 후 키워드 재생성 (Pass 2)
- `extract_candidates.py` 불용어/합성어 후보 재점검 (Pass 1 보조)

## 파일 안내
- 코드: app.py, tokenizer.py, build_keywords.py, extract_candidates.py
- 원본: job_info.csv, major_info.csv
- 추천 입력: doc_keyword_weights.json
- 사전: stopwords.json, compounds.json, compound_rules.json, broken_split.json
- 매핑: mapping_major.csv(개설대학·2022선택과목), mapping_job.csv(관련학과)
- 보조: keywords_top20.csv, vectorizer_meta.json, comp_freq/comp_items/noun_df.json

자세한 구조·방법론·다음 작업은 CLAUDE.md 참고.
