# M.A.P.S 데이터 재구조화 — DB 스키마 설계

> 흩어진 산출물(JSON·CSV)을 **신규 `content.db`** 로 정규화 통합. **기존 `schools.db`(고교·개설과목)는 그대로 유지**하고 `name_norm`으로 연계한다.
> 목표: ① 학과/직업 **카드 설명 데이터** 1급 컬럼화, ② **연관직업↔연관학과** 등 관계를 명시적 조인 테이블로, ③ 화면/엔진이 일관된 소스를 본다.
>
> **확정(검토 결과):** content.db 신규 + schools.db 유지 · 추천 키워드는 당분간 **JSON 병행**(엔진은 JSON 로드 유지) · **본 문서는 스키마 확정까지**이며 ETL 빌드는 승인 후 별도 진행.

---

## 0. 현재 소스 → 타깃 테이블 매핑

| 현재 파일 | 내용 | → 타깃 테이블 |
|---|---|---|
| `major_info.csv` (504, 23컬럼) | 학과 개요·특성·흥미적성·진출분야·전망 | `major`, `major_stat` |
| `job_info.csv` (549, 31컬럼) | 직업 하는일·핵심능력·적성·흥미·태그·연봉 | `job`, `job_card` |
| `majors_keywords.json` / `jobs_keywords.json` | rank별 공시+쉬운말 키워드 | `doc_keyword`, `doc_keyword_synonym` |
| `junior_jobs.json` (468) | 직업 이모지·한줄·관련학과 | `job_card` |
| `mapping_major.csv` | 학과→개설대학/선택과목2022/교과2015/관련자격/관련직업 | `major_subject`, `major_certification`, `major_job` |
| `mapping_job.csv` | 직업→관련학과/관련자격 | `major_job`, `job_certification` |
| `mapping_univ.json` (2,414 정규명) | 설치대학 지역·대학·전형·인원·분류 | `university`, `major_university`, `major_university_track` |
| `vocab_2022.json` (154) | 타깃 선택과목 사전 | `subject` (is_target=1) |
| `achievement_standards.json` (239과목/3,261항목) | 과목별 성취기준 | `subject_achievement` |
| `schools.db` (schools 2,536 / school_subjects 139,648) | 고교·개설과목 | **유지(이관 안 함).** content.db `subject`와 `name_norm` 연계 |

---

## 1. 엔터티 개요 (ERD 요약)

```
            ┌─────────┐   doc_keyword(+synonym)   ┌─────────┐
            │  major  │◀───────────────┬─────────▶│   job   │
            │ (504)   │                │           │ (549)   │
            └────┬────┘                │           └────┬────┘
   major_stat ───┤        ┌────────────┴───────────┐    ├─── job_card
                 │        │   ⭐ major_job (관계)   │    │
  major_subject  │        │  via_major / via_job   │    │  job_certification
        │        │        └────────────────────────┘    │
        ▼        │                                       ▼
   ┌─────────┐   │ major_university(+track)         ┌──────────────┐
   │ subject │   ├────────────────▶ ┌──────────┐    │ certification │
   │ (154+)  │   │                  │university│    └──────────────┘
   └────┬────┘   │                  │          │           ▲
        │        │                  └──────────┘   major_certification
        │ school_subject                                   │
        ▼                                          major_related_major(자기참조)
   ┌─────────┐   subject_achievement
   │ school  │◀──(school_subject)
   │ (2,536) │
   └─────────┘
```

핵심 설계 원칙
- **과목의 유형(일반/진로/융합)은 과목 자체가 아니라 "관계"에 둔다** — 학과별·학교별로 같은 과목이 다른 유형일 수 있으므로 `major_subject.area` / `school_subject.type`에 위치.
- **자유텍스트 관계는 id 해소 + 미해소 스테이징** — 원문 이름을 버리지 않고 `*_unresolved`에 남겨 재현·보강.
- **원문 통계/긴 서술은 분리 테이블**(`major_stat`, `job_card`)로 빼서 핵심 `major`/`job`을 가볍게.

---

## 2. DDL (SQLite)

### 2.1 차원(Dimension)

```sql
-- 학과 (504) — 카드 핵심 설명
CREATE TABLE major (
  major_id     TEXT PRIMARY KEY,   -- 커리어넷 학과 id (예: '309')
  name         TEXT NOT NULL,      -- 표준 학과명 (시각디자인학과)
  name_norm    TEXT NOT NULL,      -- 정규화명 (설치대학/매칭 조인 키)
  summary      TEXT,               -- 학과개요_학과개요
  features     TEXT,               -- 학과개요_학과특성
  aptitude     TEXT,               -- 학과개요_흥미와 적성
  explore_act  TEXT,               -- 학과개요_진로 탐색 활동
  univ_courses TEXT,               -- 학과개요_대학 주요 교과목
  career_field TEXT,               -- 학과개요_졸업 후 진출 분야
  category     TEXT                -- 계열/분류 (있으면)
);
CREATE INDEX idx_major_name ON major(name);
CREATE INDEX idx_major_norm ON major(name_norm);

-- 학과 통계(선택적, 카드 보조)
CREATE TABLE major_stat (
  major_id     TEXT PRIMARY KEY REFERENCES major(major_id),
  applicants   INTEGER,            -- 지원자
  enrolled     INTEGER,            -- 입학자
  ratio_male   REAL, ratio_female REAL,
  advance_rate REAL,               -- 진학률(%)
  employ_rate  REAL,               -- 취업률(%)
  wage_band    TEXT,               -- 첫 직장 임금 분포(원문 보존)
  satisfaction TEXT                -- 첫 직장 만족도(원문)
);

-- 직업 (549) — 카드 핵심 설명
CREATE TABLE job (
  job_id     TEXT PRIMARY KEY,     -- 커리어넷 직업 id (예: '10113')
  name       TEXT NOT NULL,
  name_norm  TEXT NOT NULL,
  duties     TEXT,                 -- 하는일
  core_skill TEXT,                 -- 핵심능력
  aptitude   TEXT,                 -- 적성
  interest   TEXT,                 -- 흥미
  tags       TEXT,                 -- 태그
  category   TEXT                  -- 표준직업분류
);
CREATE INDEX idx_job_name ON job(name);

-- 직업 카드(주니어 이모지/한줄 + 고교 연봉/전망)
CREATE TABLE job_card (
  job_id  TEXT PRIMARY KEY REFERENCES job(job_id),
  emoji   TEXT,                    -- 초중 카드 이모지
  blurb   TEXT,                    -- 어린이용 한 줄
  salary  TEXT,                    -- 연봉(원문)
  outlook TEXT                     -- 직업전망(원문)
);

-- 대학
CREATE TABLE university (
  univ_id INTEGER PRIMARY KEY,
  name    TEXT NOT NULL,           -- 대학명(캠퍼스 표기 포함)
  region  TEXT,                    -- 지역(시도)
  UNIQUE(name, region)
);

-- 과목 마스터(정규화) — 선택과목154 + 학과/학교에서 등장하는 과목
CREATE TABLE subject (
  subject_id INTEGER PRIMARY KEY,
  name       TEXT NOT NULL,        -- 표시명
  name_norm  TEXT NOT NULL UNIQUE, -- 정규화(로마숫자·공백 제거)
  is_target  INTEGER DEFAULT 0     -- vocab_2022(154) 타깃 여부
);

-- 자격증
CREATE TABLE certification (
  cert_id INTEGER PRIMARY KEY,
  name    TEXT NOT NULL UNIQUE
);

-- 고교(school)·개설과목(school_subject)은 content.db에 만들지 않는다.
-- → 기존 schools.db(schools / school_subjects / vocab)를 그대로 사용하고,
--   content.subject.name_norm ↔ schools.vocab/ school_subjects.subject(정규형)로 연계.
```

### 2.2 관계(Junction)

```sql
-- ⭐ 학과 ↔ 직업 (연관) : 양방향 출처를 한 행으로 병합
CREATE TABLE major_job (
  major_id   TEXT REFERENCES major(major_id),
  job_id     TEXT REFERENCES job(job_id),
  via_major  INTEGER DEFAULT 0,    -- major_info.관련직업 출처(1)
  via_job    INTEGER DEFAULT 0,    -- job_info.관련학과 출처(1)
  confidence REAL DEFAULT 1.0,     -- 이름→id 매칭 신뢰도(1=정확, <1=퍼지)
  PRIMARY KEY (major_id, job_id)
);
CREATE INDEX idx_mj_job ON major_job(job_id);

-- 자유텍스트 미해소 보관(재현·보강용)
CREATE TABLE major_job_unresolved (
  src_type TEXT,   -- 'major' | 'job'
  src_id   TEXT,   -- 출처 id
  raw_name TEXT,   -- 매칭 실패한 상대 이름 원문
  reason   TEXT
);

-- 학과 ↔ 권장 선택과목 (유형·교육과정 버전은 관계에)
CREATE TABLE major_subject (
  major_id   TEXT REFERENCES major(major_id),
  subject_id INTEGER REFERENCES subject(subject_id),
  curriculum TEXT,   -- '2022' | '2015'
  area       TEXT,   -- 일반 | 진로 | 융합 | 공통 | 전문
  PRIMARY KEY (major_id, subject_id, curriculum, area)
);

-- 고교 ↔ 개설 과목: content.db에 두지 않음.
--   기존 schools.db.school_subjects(shl_idf_cd, type, subject, years)를 그대로 사용.
--   학과 권장과목 개설여부 조회는 content.major_subject(name_norm) ↔ schools.school_subjects(정규형) 교차로 수행.

-- 과목 ↔ 성취기준
CREATE TABLE subject_achievement (
  subject_id INTEGER REFERENCES subject(subject_id),
  seq        INTEGER,
  code       TEXT,    -- 성취기준코드(있으면)
  text       TEXT
);

-- 학과 ↔ 대학(설치)
CREATE TABLE major_university (
  major_id TEXT REFERENCES major(major_id),
  univ_id  INTEGER REFERENCES university(univ_id),
  quota    INTEGER,   -- 모집인원
  field    TEXT,      -- 분류(모집단위 계열)
  PRIMARY KEY (major_id, univ_id)
);
-- 설치 전형(한 단계 더 정규화)
CREATE TABLE major_university_track (
  major_id TEXT, univ_id INTEGER, track TEXT,   -- 전형명
  PRIMARY KEY (major_id, univ_id, track)
);

-- 학과/직업 ↔ 자격
CREATE TABLE major_certification (major_id TEXT, cert_id INTEGER, PRIMARY KEY(major_id,cert_id));
CREATE TABLE job_certification   (job_id   TEXT, cert_id INTEGER, PRIMARY KEY(job_id,cert_id));

-- 학과 ↔ 관련 세부학과(자기참조)
CREATE TABLE major_related_major (
  major_id   TEXT REFERENCES major(major_id),
  related_id TEXT REFERENCES major(major_id),  -- 매칭되면 id, 아니면 NULL
  raw_name   TEXT,                             -- 원문 세부학과명
  PRIMARY KEY (major_id, raw_name)
);
```

### 2.3 추천엔진 키워드 + 메타

> **병행 정책(확정):** 추천엔진은 당분간 `majors_keywords.json`/`jobs_keywords.json`을 그대로 로드한다.
> 아래 두 테이블은 **동기화 보관용(선택 적재)** 이며, 엔진 DB 단일화는 추후 단계.

```sql
-- 공시 키워드(rank별) — major/job 통합
CREATE TABLE doc_keyword (
  doc_type TEXT,   -- 'major' | 'job'
  doc_id   TEXT,
  rank     INTEGER,
  official TEXT,
  PRIMARY KEY (doc_type, doc_id, rank)
);
-- 쉬운말 동의어(어린이 어휘 매칭)
CREATE TABLE doc_keyword_synonym (
  doc_type TEXT, doc_id TEXT, rank INTEGER, easy TEXT,
  PRIMARY KEY (doc_type, doc_id, rank, easy)
);
CREATE INDEX idx_kw_official ON doc_keyword(official);
CREATE INDEX idx_kw_syn ON doc_keyword_synonym(easy);

CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
```

---

## 3. 편의 뷰 (화면/엔진용)

```sql
-- 주니어 직업 카드 한 방 조회
CREATE VIEW v_job_card AS
SELECT j.job_id, j.name, c.emoji, c.blurb,
       (SELECT m.name FROM major_job mj JOIN major m ON m.major_id=mj.major_id
        WHERE mj.job_id=j.job_id ORDER BY mj.confidence DESC LIMIT 1) AS top_major
FROM job j LEFT JOIN job_card c ON c.job_id=j.job_id;

-- 학과 상세 카드(고교)
CREATE VIEW v_major_card AS
SELECT m.*, s.employ_rate, s.advance_rate
FROM major m LEFT JOIN major_stat s ON s.major_id=m.major_id;
```

---

## 4. ETL / 적재 전략 (핵심: 이름→id 해소)

가장 어려운 부분은 **자유텍스트 관계의 id 매칭**이다. 단계:

1. **차원 먼저 적재**: `major`, `job`(+stat/card), `subject`(vocab+학과/학교 등장 과목 합집합), `university`, `certification`, `school`.
2. **major_job 해소**
   - `mapping_major.관련직업`(쉼표 분리) → 각 직업명 → `job.name` **정확매칭** → 실패 시 difflib **퍼지(≥0.85)** → `via_major=1`.
   - `mapping_job.관련학과`(구분자 없음, "기계공학과전자공학과…") → `학과/공학과/학부/전공` 경계로 **분절** → `major.name` 매칭 → `via_job=1`.
   - 두 출처를 (major_id,job_id)로 **UPSERT 병합**(via 플래그 OR). 매칭 실패는 `major_job_unresolved`.
3. **major_subject**: `선택과목2022`/`교과목2015` 파서 → `일반/진로/융합/공통/전문` 라벨별 과목 → `subject` 매칭(`_norm_subject`) → curriculum/area 부여.
4. **major_university**: `mapping_univ.json`을 `name_norm`으로 `major`에 연결 → univs[] 펼쳐 `university` UPSERT, `major_university`(인원·분류) + `major_university_track`(전형 펼침).
5. **고교 개설과목**: 이관/중복 적재 안 함. schools.db 그대로 두고, content.`subject.name_norm`을 schools.`vocab`/`school_subjects`의 정규형과 **정렬만** 맞춰 교차조회 가능하게.
6. **subject_achievement**: JSON 그대로 펼쳐 적재. (doc_keyword는 JSON 병행이므로 적재 선택)
7. **무결성 점검**: 고아 FK, 매칭 커버리지(설치대학 70.6%·major_job 해소율 등) 리포트를 `meta`에 기록.

> 빌드 산출물(예정): `build_content_db.py` → `content.db`. schools.db는 건드리지 않음. 교차조회는 `ATTACH DATABASE 'schools.db' AS sch;` 또는 파이썬에서 두 연결 조인.

---

## 5. 확정 사항 (검토 완료)

1. **통합 범위 ✅**: 신규 **`content.db`**(학과·직업·관계·대학·과목·자격·성취기준) + 기존 **`schools.db` 유지**. 교차조회는 `name_norm` / `ATTACH`.
2. **추천 키워드 ✅**: **JSON 병행** — 엔진은 기존 JSON 로드 유지, DB 키워드 테이블은 동기화 보관용(선택).
3. **진행 범위 ✅**: **스키마 확정까지**. ETL 빌드(`build_content_db.py`)는 승인 후 별도.

### 남은 빌드 옵션(빌드 착수 시 정함)
- 교육과정 버전: 2015·2022를 `major_subject.curriculum`으로 한 테이블에(권장) vs 2022만.
- 원문 보존: `major_stat`/`job_card` 긴 원문 TEXT 보존(권장) vs 추가 정규화.
- `major_job` 퍼지 매칭 컷(0.85?)과 미해소 허용 범위.

---

## 6. 적용 후 영향 (빌드 단계에서)

- **두 DB 연계**: 개설여부 조회는 `content.db`(major_subject) ↔ `schools.db`(school_subjects)를 `ATTACH DATABASE 'schools.db' AS sch;` 후 `name_norm` 정규형으로 조인. 키워드는 JSON 유지.
- `recommender.py`: `universities_for`, `subjects_of_major`, `achievements_for_subject` 등이 CSV/JSON 대신 `content.db` 조인으로 단순화. `subject_availability`만 schools.db 교차.
- `views/junior.py`: `junior_jobs.json` → `content.db`의 `job`+`job_card`+`major_job`(연관학과) 조회.
- `views/highschool.py`: 학과 카드에 `major.summary/aptitude/career_field`, 연관직업(`major_job`), 설치대학(`major_university`)을 일관 조회.
- 빌드 스크립트: **`build_content_db.py` 신규**(schools.db는 불변). 재현 가능.

> 다음 작업: 본 스키마 승인 후 `build_content_db.py` 작성 → `content.db` 생성 → 커버리지/무결성 리포트.
