# 학과·직업 추천 서비스 — 프로젝트 가이드

> 이 문서는 Claude Code가 프로젝트를 이어받아 작업할 수 있도록 전체 맥락·구조·다음 단계를 정리한 핸드오프 문서입니다.

## 1. 목표
커리어넷 원문(학과 504 / 직업 549)을 가공해, **학생의 관심사 발화 → 키워드 → 학과·직업 추천 → 설치대학·2022 권장 선택과목 → (예정) 고교 개설여부**로 이어지는 추천 서비스를 만든다. 현재 Streamlit 파일럿까지 완성됨.

## 2. 전체 데이터 흐름
```
원본 CSV ─┬─(키워드 컬럼만 선별)─> 합본 텍스트 ─tokenize─> TF-IDF ─> doc_keyword_weights.json
          └─(매핑 컬럼)──────────> mapping_*.csv (설치대학·2022선택과목·관련학과)

학생 발화 ─tokenize(동일)─> 키워드 ─매칭·가중치 합산─> 학과/직업 순위 ─> mapping으로 설치대학·선택과목 표시
```
핵심 원칙: **문서와 발화를 같은 `tokenize()`로 처리**해야 매칭이 맞는다.

## 3. 파일 구조
| 파일 | 역할 |
|---|---|
| `app.py` | **Streamlit 웹서비스** (발화 → 쉬운말 매칭 추천 → 설명·연계페어·설치대학). `recommender.py` 사용 |
| `recommender.py` | **추천 엔진**(UI 분리). 발화→키워드(부정절 제외)→순위 점수합 매칭(공시+쉬운말)→학과/직업 Top-N→연계페어. FastAPI 재사용 가능 |
| `llm_extract.py` | **선택적 LLM 발화 이해(A단계)**. `OPENAI_API_KEY` 있을 때만 GPT로 긍정/부정 키워드 추출. 없거나 실패 시 규칙 기반 자동 폴백. 추상 발화 보강용 |
| `majors_keywords.json` `jobs_keywords.json` | **추천엔진 입력.** 학과 504·직업 549. 각 문서 keywords:[{rank, official(공시), easy[쉬운말 동의어]}] rank별 쌍, 20개 고정 |
| `synonyms_merged.json` | 전체 고유키워드 5,464개 → 쉬운말 동의어 사전(병합본). `syn_batches/batch_*.json`(수기 생성)을 합친 결과 |
| `tokenizer.py` | **발화·문서 공용 토크나이저** (사전·규칙 적용). 모든 곳에서 import |
| `build_keywords.py` | [Pass2] 원본+사전 → TF-IDF → 키워드 산출물 재생성 |
| `extract_candidates.py` | [Pass1보조] 원본 → 불용어/합성어 후보 통계 (사전 보강용) |
| `job_info.csv` `major_info.csv` | 커리어넷 원문 (raw, 형태소분석 전) |
| `doc_keyword_weights.json` | **추천엔진 입력.** {학과·직업명: {키워드: tfidf가중치}} |
| `keywords_top20.csv` | 학과·직업별 상위 20 키워드 (사람 검수용) |
| `vectorizer_meta.json` | vocab + idf (발화를 코사인용으로 벡터화할 때) |
| `stopwords.json` | 불용어 (순수 기능어만) |
| `compounds.json` | 특화 합성어 (빈도·등장항목 예시 포함) |
| `compound_rules.json` | 접미사 결합 규칙(학과/전공/학부/공학…) |
| `broken_split.json` | 원문 정제 오류로 붙은 토큰 분리 목록 |
| `mapping_major.csv` | 학과 → 개설대학(구 데이터, 폴백) / 2022선택과목 / 2015교과목 / 관련자격 / 관련직업 |
| `mapping_job.csv` | 직업 → 관련학과 / 관련자격 |
| `build_univ_mapping.py` | `설치모집단위 리스트.xlsx`(sheet=univ_major) → `mapping_univ.json` 생성. `norm_major`로 학과명 정규화 후 (지역·대학명·전형·인원·분류) 집계 |
| `mapping_univ.json` | **설치대학 매핑(4년제 모집단위 기준).** {정규화학과명: {names, univ_count, univs:[{지역,대학명,전형:[...],인원,분류}]}}. 커버리지 70.6%(298/422). 미매칭(전문대·교양학부)은 `mapping_major.csv` 개설대학으로 폴백 |
| **고교 개설과목 (학교알리미)** | ↓ 수집·파싱 상세는 **`HANDOFF_고교개설과목.md`** 참조 |
| `school_list.csv` | 전국 고교 2,536교 시드(school_name, shl_idf_cd, sido, gugun…) |
| **`schools.db`** | **추천엔진 입력(개설여부, 현행).** SQLite. `recommender._load_school_subjects_sqlite()`가 schools(2,536)·school_subjects(139,648행)·vocab(154)·meta 테이블에서 has_curriculum=1 학교(**2,287교**, 2025∪2026 병합)를 로드. 없으면 `subjects_by_school_merged.json`→`subjects_by_school.json` 폴백 |
| `subjects_by_school_merged.{json,csv}` | schools.db 빌드 전 병합 산출물(폴백 입력). {shl_idf_cd:{school,sido,gugun,subjects:{일반/진로/융합:[...]},n_subj}} |
| `vocab_2022.json` | 154개 타깃 과목 사전(`선택과목2022`에서 추출). 학과·DB·학교 매칭 어휘 |
| `crawl_curriculum.py` `parse_curriculum.py` `build_vocab.py` | [1차]다운로드 / [2차]파싱 / 어휘생성 스크립트 (상세 HANDOFF) |
| **고교 개설과목 (2026-05 신규)** | ↓ 학교알리미 수집·파싱 파이프라인. 상세는 **`HANDOFF_고교개설과목.md`** 참조 |
| `school_list.csv` | 전국 고교 2,536교 시드(SHL_IDF_CD 포함). curl로 생성(검색 API는 Python WAF에 막힘) |
| `crawl_curriculum.py` | **[1차]** 학교알리미 항목05(교육과정 편성) 첨부 형식무관 다운로드 + 엑셀현황. 재개 가능 |
| `collection_status.xlsx`/`.csv` | 1차 수집현황(확인여부Y/총파일수/교육과정파일수). `curriculum_files/<시도>/<학교>/`에 원본 |
| `build_vocab.py` → `vocab_2022.json` | mapping_major의 `선택과목2022`→154개 타깃과목 사전(추천엔진과 정렬) |
| `parse_curriculum.py` | **[2차]** 형식별 텍스트추출(XLSX/PDF/HWP/HWPX)→어휘 경계매칭→학교별 과목셋 |
| `subjects_by_school.json` | 2차 파싱 결과(연도단독). {shl_idf_cd:{school,sido,subjects:{일반/진로/융합},n_subj}} |
| `merge_years.py` → `subjects_by_school_merged.{json,csv}` | 2025∪2026 병합(어느 해든 개설=개설). 2,287교 |
| `build_db.py` → **`schools.db`** | **최종 SQLite DB(추천엔진 입력).** 테이블: schools(2,536)·school_subjects(139,648행)·vocab(154)·meta. idf/subject 인덱스 |
| `run_pipeline.py` | 크롤→파싱→병합→DB 순차 드라이버(절전금지 내장, 재개 가능). `python run_pipeline.py` |
| `parse_status.xlsx` | 2차 파싱현황(매칭과목수/미파싱사유) |
| `fetch_curriculum.py` | 단일학교 데모/엔드포인트 검증용(참고) |

## 4. 사전 구축 방법론 (중요)
- **불용어**: "어느 학과·직업에서도 변별력 없는 순수 기능어"만 넣는다(`관련·필요·적합·방법…`).
  도메인 의미가 조금이라도 있는 단어(`봉사활동`은 사회복지/간호에 핵심)는 **넣지 않고** TF-IDF의 IDF + `max_df`에 위임한다.
- **합성어**: 원문 띄어쓰기가 곧 단어 경계. "한 어절인데 분석기가 2+명사로 쪼갠 것"이 합성어.
  - `OO학과/전공/학부/공학` 등 접미사 패턴(6,500여종)은 사전에 안 넣고 `tokenizer._strip_suffix()` **규칙**으로 처리.
  - 불규칙 특화어(`인공지능·시각디자인·스포츠재활…`)만 `compounds.json` + kiwi 사용자사전 등록.
- **접미사 절단**: `시각디자인학과→시각디자인`, 단 `기계공학과→기계공학`(공학 보존) 특례 있음.

## 5. tokenize() 파이프라인 (tokenizer.py)
1. 합성어를 kiwi 사용자사전 등록 (보호 + 조사 정확분리)
2. 어절별 연속명사 결합 (원문 띄어쓰기 = 경계)
3. 조사 절단(`_strip_josa`) → 접미사 절단(`_strip_suffix`)
4. 깨진토큰 분리(`SPLIT_MAP`) → 불용어/기관명 제거
- **Okt로 교체 시**: `_nouns_in_eojeol()`의 kiwi 부분만 Okt 명사추출로 바꾸면 됨. 사전·규칙은 그대로.

## 6. 추천 로직 (recommender.py — 과목추천 제외 현행)
1. **발화→키워드**: `tokenize()` + 부정절 제외. 절을 구분자(`, . 그리고 하지만 다만…`)로 쪼개 부정 단서(`싫·별로·말고·빼고…`)가 든 절의 토큰은 제외.
2. **매칭(쉬운말 포함)**: 각 문서의 rank별 [공시 official + 쉬운말 easy]에 대해 — 공시는 토큰 정확매칭, 쉬운말은 토큰매칭 OR 발화 부분문자열매칭. → 어린이 어휘가 공시 키워드로 연결됨.
3. **순위 점수합**: 1위=20 … 20위=1점(`rank_score`). 같은 공시키워드는 최고순위 1회만 인정 → 합산이 문서 점수. 학과/직업 각각 Top-N(동일 명칭 중복 id는 최고점 1건만).
4. **설명가능**: 매칭된 term·순위·점수·경로(공시/쉬운말)를 근거로 함께 반환·표시.
5. **연계페어**: 상위 학과×직업의 **공시키워드 교집합** 크기로 정렬.
- 부가정보: **설치대학**은 `mapping_univ.json`(`recommender.universities_for(name)` → 지역·대학명·전형·인원 구조화)을 우선 사용하고, 미매칭 학과는 `mapping_major.csv` 개설대학으로 폴백. `mapping_job.csv`(관련학과).
- **고교 선택과목 개설여부(D) — 연결 완료**: 사이드바에서 학생 고교(시도→학교) 선택 시, 추천 학과의 `선택과목2022`가 그 고교에 개설됐는지 ✅/⬜ 표시. `recommender.subjects_of_major(rec)`(vocab 정규형 필터로 {일반/진로/융합} 파싱) + `subject_availability(rec, shl_idf_cd)`(과목별 개설여부+요약), `school_options(sido, gugun)`(데이터 보유 **2,287교**, 시도→시군구→학교 3depth). 입력은 **`schools.db`**(SQLite) 우선·병합 JSON 폴백. 정규화 `_norm_subject()`(로마숫자·공백)로 어휘/DB/학과 3측 일관 매칭. 미개설 과목은 공동교육과정·교실온닷 안내. (학교알리미 2025·2026 공시 병합 기준.)
- 대안: vectorizer_meta로 코사인 유사도, LLM(`career_recommender.py`의 긍정/부정 추출)로 발화이해 고도화.

## 7. 실행
```bash
pip install -r requirements.txt
streamlit run app.py            # 웹서비스 실행 (localhost:8501)
python recommender.py           # 엔진 단독 데모(콘솔)
python build_keywords.py        # 사전 수정 후 키워드 재생성
python extract_candidates.py    # 불용어/합성어 후보 재점검
```
> 키워드 산출물 갱신 시: `syn_batches/*.json` 병합 → `synonyms_merged.json` → `keywords_top20.csv`와 rank 정렬 결합 → `majors_keywords.json`/`jobs_keywords.json` 재생성.

### LLM 발화 이해(선택) · 배포
- LLM 켜기: 환경변수 `OPENAI_API_KEY` 설정 → 사이드바 "LLM 발화 이해 사용" 체크. 미설정이면 비활성+규칙 폴백.
- **비밀키 커밋 금지**: 로컬은 환경변수, Streamlit Cloud는 *Secrets* 에 `OPENAI_API_KEY` 추가(자동으로 env 노출). `.gitignore`에 `secrets.toml` 제외 설정됨.
- Streamlit Cloud 배포: GitHub 푸시 후 앱 연결, main 파일 `app.py`. system 패키지 불필요(kiwipiepy 순수 wheel). 설정은 `.streamlit/config.toml`.

## 8. 다음 작업 (TODO)
- [x] **고교 개설여부 연결** (완료, 상세 `HANDOFF_고교개설과목.md`):
  - [x] **1차 수집**: `crawl_curriculum.py`로 전국 고교 항목05 첨부 다운로드(1,780/2,478교 파일보유, 1.5GB). `collection_status.xlsx`.
  - [x] **2차 파싱**: `parse_curriculum.py`로 형식별(XLSX/PDF/HWP/HWPX) 텍스트추출→`vocab_2022.json`(154과목) 매칭 → `subjects_by_school.json`(**1,050교 개설과목 추출**).
  - [x] **추천엔진 연결**: `recommender.subjects_of_major()`/`subject_availability()`/`school_options()` + `app.py` 사이드바 학교선택 → 학과카드 선택과목 개설 ✅/⬜. 미개설은 공동교육과정·교실온닷 안내.
  - [x] **2026 보강 + FILE_SEQ 버그수정(완료, 06-22)**: `crawl_curriculum.py --year 2026` 재수집 + `FILE_SEQ`를 0부터 열거하도록 수정(no_file 대거 회수) → `parse_curriculum.py` 재파싱 → `merge_years.py`로 2025∪2026 병합 → `build_db.py`로 **`schools.db`** 재생성. 커버리지 1,050→1,578→**2,287교(90%)**. `run_pipeline.py` 드라이버로 일괄 실행.
- [ ] **합성어 꼬리 보강**: `extract_candidates.py`의 comp_freq 중·하위 구간에서 저빈도 특화어를 `compounds.json`에 추가 → `build_keywords.py` 재실행.
- [x] **설치대학 파싱 고도화**: `설치모집단위 리스트.xlsx` → `build_univ_mapping.py` → `mapping_univ.json`(지역·대학·전형·인원). `recommender.universities_for()`로 조회, app.py에서 지역별 렌더. 미매칭은 구 개설대학 폴백.
- [ ] **Okt 전환**(부장님 기존 환경과 통일 시) — tokenizer.py 명사추출부만 교체 후 build_keywords 재실행.
- [ ] **FastAPI화**: 추천 로직을 엔드포인트로 분리 → EBSi 등 연동, 정식 프론트(React) 연결.
- [ ] 코사인 유사도 추천 옵션 추가(vectorizer_meta 활용), 학과↔직업 연계 페어 표시.

## 9. 주의
- 문서·발화 토큰화는 **반드시 동일** (tokenizer.py 공용).
- 사전 변경 시 반드시 `build_keywords.py` 재실행해야 키워드에 반영됨.
- 형태소 분석기는 kiwipiepy 기준(JVM 불필요, 순수 파이썬).
