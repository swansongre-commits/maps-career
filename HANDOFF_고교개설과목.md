# 고교 개설과목 수집·파싱 — 핸드오프 (2026-05-29 작업분, 2026-05-30 추천엔진 연결 완료)

> 목적: "추천 학과의 2022 선택과목이 **학생이 다니는 고교에 개설되어 있는지**" 판정 데이터 구축.
> 학교알리미(schoolinfo.go.kr)에서 전국 고교 교육과정 문서를 수집→파싱해 학교별 개설과목 셋을 만든다.
> CLAUDE.md TODO의 "고교 개설여부 연결" 작업. **1차(다운로드)·2차(파싱)·추천엔진 연결 모두 완료.**

---

## 0. 현재 상태 (한 줄)
전국 고교 2,478개 중 **1,050개교의 개설과목 추출 완료** → `subjects_by_school.json`.
**추천엔진 연결 완료(2026-05-30)**: `recommender.subjects_of_major()`/`subject_availability()`/`school_options()` + `app.py` 사이드바 학교선택 → 학과카드에 선택과목 개설 ✅/⬜ 표시. 남은 건 **2026 데이터 보강·커버리지 향상**(아래 §7-2,3).

---

## 1. 데이터 흐름 (신규 파이프라인)
```
[시드] curl로 전국 고교목록 ──> school_list.csv (2,536교, SHL_IDF_CD 포함)
          │
[1차] crawl_curriculum.py  ──> 각 학교 항목05(교육과정 편성) 첨부 형식무관 다운로드
          │                     curriculum_files/<시도>/<학교>/<원본파일>
          │                     collection_status.{csv,xlsx} (확인여부Y/총파일수/교육과정파일수)
          │
[어휘] build_vocab.py       ──> vocab_2022.json (154개 타깃과목, mapping_major의 '선택과목2022'에서 추출)
          │
[2차] parse_curriculum.py  ──> 형식별 텍스트추출(XLSX/PDF/HWP/HWPX) → 어휘매칭
                               subjects_by_school.{json,csv} + parse_status.xlsx
```

---

## 2. 학교알리미 크롤링 — 검증된 사실 (중요)

### 2-1. 학교 목록 (검색)
- 엔드포인트: `POST https://www.schoolinfo.go.kr/ei/ss/pneiss_a04_s0/getSchoolList.do`  body `SEARCH_WORD=고등학교`
- **`SEARCH_WORD=고등학교` 한 번에 전국 고교 2,536건** 반환(JSON, SHL_IDF_CD/SIDO_CODE/GUGUN_CODE 등 포함). `SHL_CRSE_SC_CD=04`가 일반 고교(2,478), `05`는 기타(58).
- **⚠ WAF 함정**: 이 검색은 **curl은 되지만 Python(requests/urllib)은 빈 배열([]) 반환**. (TLS/HTTP 스택 지문 차이로 추정, UA·쿠키 무관. 같은 IP에서도 그러함.)
  → 그래서 목록은 **curl로 받아 `school_list.csv` 시드로 저장**해 쓴다. `crawl_curriculum.py --refresh-list`가 내부적으로 curl 호출로 갱신.

### 2-2. 파일 다운로드 (Python 정상 동작)
- 엔드포인트: `GET https://www.schoolinfo.go.kr/servlets/EiFileDownLoad.do`
- 파라미터(교육과정 편성 항목):
  `SHL_IDF_CD=<uuid>` `JG_BURYU_CD=JG020` `JG_HANGMOK_CD=05` `JG_GUBUN=1` `JG_YEAR=2025` `JG_CHASU=1` `USE_YN=Y` `FILE_SEQ=<1..N>`
- 동작: 실제 첨부면 `Content-Type: application/octet-stream` + `Content-Disposition`에 파일명(`OOOO학년도 입학생 …`). 없으면 302.
- **FILE_SEQ는 중간 빈 번호 가능** → 끝까지(예: 1~12) 열거해야 함(끊으면 누락).
- `JG_HANGMOK_CD=05` = 공시항목 "2-가 학교교육과정 편성·운영·평가". **학교마다 여기에 올린 파일이 제각각**(배당표 XLSX, 편제표 PDF/HWP, 또는 학교교육계획·학사일정만). 형식·내용 표준화 안 됨.

### 2-3. 점검 윈도우
- 매년 5월말 연간 공시갱신 점검. **2026년 데이터는 2026-05-30 공개.** 점검 중엔 공시상세 목록페이지(`Pneipp_b14_s0p.do`)는 막히지만, **검색·다운로드 엔드포인트는 동작**했음.
- 이번 수집은 **2025 공시연도(JG_YEAR=2025)** 기준. 2026 공개 후 `--year 2026` 재수집 권장.

---

## 3. 생성된 파일 (산출물)

| 파일 | 내용 |
|---|---|
| `school_list.csv` | 전국 고교 2,536교 시드 (school_name, shl_idf_cd, crse_cd, sido, gugun, …) |
| `curriculum_files/<시도>/<학교>/…` | 다운로드 원본 3,034개·약 1.5GB (HWP1048·PDF986·XLSX605·HWPX386) |
| `collection_status.xlsx` / `.csv` | **1차 수집현황**: 확인여부Y·총파일수·교육과정파일수·파일목록 (재개 체크포인트) |
| `vocab_2022.json` | 154개 타깃 과목 사전 {과목:{type:일반/진로/융합, freq}} |
| `subjects_by_school.json` | **2차 결과(추천엔진 조회용).** `{shl_idf_cd: {school, sido, gugun, formats, n_files, used_files, subjects:{일반:[],진로:[],융합:[]}, n_subj}}` |
| `subjects_by_school.csv` | tidy: (shl_idf_cd, school, sido, gugun, type, subject) |
| `parse_status.xlsx` | **2차 파싱현황**: 후보/사용 파일수·매칭과목수·유형분포·미파싱사유 |

## 4. 생성된 스크립트

| 스크립트 | 역할 | 주요 실행 |
|---|---|---|
| `crawl_curriculum.py` | **1차 다운로드 전용** 크롤러(항목05 첨부 형식무관 수집)+엑셀현황. 재개 가능. | `python crawl_curriculum.py --year 2025 --pause 0.2` / `--refresh-list` / `--sido 서울특별시` / `--limit N` / `--build-xlsx` |
| `build_vocab.py` | mapping_major의 `선택과목2022` → `vocab_2022.json` | `python build_vocab.py` |
| `parse_curriculum.py` | **2차 파싱**: 형식별 텍스트추출→어휘매칭→학교별 과목셋 | `python parse_curriculum.py` (`--limit N`, `--include-all`) |
| `fetch_curriculum.py` | 단일학교 데모/엔드포인트 검증용(양재고 FILE_SEQ 발견 과정). 참고용. | `python fetch_curriculum.py` |

> 콘솔 한글 깨짐 방지: PowerShell에서 `$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"` 후 실행.
> 필요 패키지: `requests openpyxl pymupdf(fitz) olefile`. (PDF=fitz, HWP=olefile, HWPX=zipfile+xml, XLSX=openpyxl)

---

## 5. 2차 파싱 설계 (핵심 로직 — parse_curriculum.py)
1. **대상 파일 선별**: 학교폴더에서 파일명에 `배당/편제/편성/교육과정` 포함 & `학사일정/체험활동/평가결과/…` 제외(`is_curriculum`).
2. **형식별 텍스트 추출**: XLSX(openpyxl 전 셀), PDF(fitz), HWPX(zip의 Contents/*.xml 태그제거), HWP(olefile→BodyText 섹션 zlib해제→PARA_TEXT 레코드 tag 0x43 UTF-16LE).
3. **어휘 매칭(match_subjects)**: vocab_2022(154) 각 과목을 **한글/영문 경계 + 유연공백 정규식**으로 검색. 로마숫자 Ⅰ/Ⅱ→I/II 정규화.
   - 경계매칭으로 `연기`·`음악사`·`극 창작` 등 **부분문자열 오탐 제거**.
4. **XLSX 참조시트 제외(match_xlsx)**: 한 시트가 100개 이상 매칭하면 "전체 과목 메뉴/드롭다운 목록"으로 보고 제외(REF_SHEET_MAX). 양재 'Sheet1'(114) 제거, 데이터시트(66)만 채택.
5. **키잉**: 동명학교 충돌 방지 위해 `shl_idf_cd`(school_list.csv로 매핑).

검증: **양재고 66(단일 배당표 기준)~73(폴더 전체)과목**, 예술 전문교과 오탐 없음.

---

## 6. 커버리지·한계·주의
- **추출 성공 1,050 / 2,478 (약 42%).** 미추출: 첨부 없음 698교 + 편제표 아닌 narrative(계획서·학사일정)뿐 약 730교.
- 과목수: 중앙값 69, 최대 122. **일부 PDF/HWP가 "선택 가능 과목 전체 메뉴"를 실어 과대계상** 가능(편성됨 vs 선택가능 구분이 원문상 모호). 추천 용도엔 과소누락보다 안전한 편.
- 최다 개설: 정보94%·음악94%·미술91%·체육89%·문학86% (직관 일치 → 매칭 신뢰 OK).
- **어휘는 154개(추천엔진이 추천하는 과목)로 한정** — 전체 2022 과목 사전이 아님. mapping_major 갱신 시 build_vocab 재실행.

---

## 7. 다음 작업 (TODO)
1. **[완료 2026-05-30] 추천엔진 연결**: `recommender.py`에 로더·조회 함수 추가.
   - `_norm_subject()` 로마숫자(Ⅰ→I)·공백 정규화로 어휘/DB/학과 3측 일관 매칭.
   - `subjects_of_major(rec)` 학과 `선택과목2022` → vocab 정규형 필터 → {일반/진로/융합}.
   - `subject_availability(rec, shl_idf_cd)` 과목별 개설여부 O/X + 요약(n_offered/n_total).
   - `school_sidos()`/`school_options(sido)` UI용 학교목록(데이터 보유 1,050교).
   - `app.py` 사이드바: 시도→학교 선택. 학과카드: 학교 선택 시 ✅/⬜, 미선택 시 과목목록만. 미개설은 공동교육과정·교실온닷 안내.
2. **2026 데이터 보강**(05-30 이후): `crawl_curriculum.py --year 2026` 재수집 → `parse_curriculum.py` 재파싱 → 커버리지↑, 미보유교 회수.
3. **커버리지 향상 옵션**: 다른 공시항목 탐색(편제표가 05 외에 있는 학교), narrative 문서의 표 영역 파싱 강화, NEIS 고등학교시간표 OpenAPI(실제 편성 과목, 무료키) 병행.

---

## 8. 재현/이어가기 빠른 명령
```bash
# 목록 갱신(curl 필요)
python crawl_curriculum.py --refresh-list
# 1차 다운로드(전국, 재개 가능)
python crawl_curriculum.py --year 2025 --pause 0.2
# 어휘 재생성(mapping_major 변경 시)
python build_vocab.py
# 2차 파싱
python parse_curriculum.py
# 엑셀 현황만 재생성
python crawl_curriculum.py --build-xlsx
```
조회 예시(파이썬):
```python
import json
db = json.load(open("subjects_by_school.json", encoding="utf-8"))
rec = db["9dfe0125-996c-4ba6-8400-08e1ff1759ec"]  # 양재고
offered = {s for ss in rec["subjects"].values() for s in ss}
print("미적분II" in offered)  # 개설여부
```
