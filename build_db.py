"""
학교별 개설과목 → SQLite DB화 (schools.db)
입력 우선순위: subjects_by_school_merged.json > subjects_by_school.json
school_list.csv로 전체 고교 로스터 + 메타 결합.

테이블
  schools(shl_idf_cd PK, school_name, sido, gugun, crse_cd, has_curriculum, n_subj, years)
  school_subjects(shl_idf_cd, type, subject, years)   -- idx: shl_idf_cd, subject
  vocab(subject PK, type, freq)
  meta(key PK, value)
"""
import sys, os, json, csv, sqlite3, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent
DB = ROOT / "schools.db"


def pick_subjects_json():
    for n in ("subjects_by_school_merged.json", "subjects_by_school.json"):
        p = ROOT / n
        if p.exists():
            return p
    raise SystemExit("subjects JSON 없음 — 먼저 parse_curriculum.py 실행 필요")


def main(build_date=None):
    src = pick_subjects_json()
    data = json.loads(src.read_text(encoding="utf-8"))
    vocab = json.loads((ROOT / "vocab_2022.json").read_text(encoding="utf-8"))

    # 전체 고교 로스터(school_list.csv)
    roster = {}
    with open(ROOT / "school_list.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            roster[r["shl_idf_cd"]] = r

    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    c = con.cursor()
    c.executescript("""
    CREATE TABLE schools(
        shl_idf_cd TEXT PRIMARY KEY, school_name TEXT, sido TEXT, gugun TEXT,
        crse_cd TEXT, has_curriculum INTEGER, n_subj INTEGER, years TEXT);
    CREATE TABLE school_subjects(
        shl_idf_cd TEXT, type TEXT, subject TEXT, years TEXT);
    CREATE TABLE vocab(subject TEXT PRIMARY KEY, type TEXT, freq INTEGER);
    CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
    """)

    # vocab
    c.executemany("INSERT INTO vocab VALUES(?,?,?)",
                  [(s, v["type"], v["freq"]) for s, v in vocab.items()])

    # schools + subjects
    have = set()
    sub_rows = []
    for idf, rec in data.items():
        have.add(idf)
        years = "+".join(rec.get("years", [])) or rec.get("year", "")
        c.execute("INSERT OR REPLACE INTO schools VALUES(?,?,?,?,?,?,?,?)", (
            idf, rec.get("school"), rec.get("sido"), rec.get("gugun", ""),
            roster.get(idf, {}).get("crse_cd", ""), 1, rec.get("n_subj", 0), years))
        for typ, lst in rec.get("subjects", {}).items():
            for s in lst:
                sub_rows.append((idf, typ, s, years))
    c.executemany("INSERT INTO school_subjects VALUES(?,?,?,?)", sub_rows)

    # 데이터 없는 나머지 학교도 로스터에 포함(UI 전체목록·커버리지 파악용)
    for idf, r in roster.items():
        if idf in have:
            continue
        c.execute("INSERT OR IGNORE INTO schools VALUES(?,?,?,?,?,?,?,?)", (
            idf, r["school_name"], r["sido"], r["gugun"], r["crse_cd"], 0, 0, ""))

    c.executescript("""
    CREATE INDEX idx_ss_idf ON school_subjects(shl_idf_cd);
    CREATE INDEX idx_ss_subj ON school_subjects(subject);
    CREATE INDEX idx_sc_sido ON schools(sido);
    """)

    meta = {
        "build_date": build_date or time.strftime("%Y-%m-%d %H:%M"),
        "source_json": src.name,
        "n_schools_total": str(len(roster)),
        "n_schools_with_curriculum": str(len(have)),
        "n_subject_rows": str(len(sub_rows)),
        "n_vocab": str(len(vocab)),
    }
    c.executemany("INSERT INTO meta VALUES(?,?)", list(meta.items()))
    con.commit()

    # 요약 출력
    print("== schools.db 생성 ==")
    for k, v in meta.items():
        print(f"  {k}: {v}")
    print("\n[검증] 양재고 개설과목 수:",
          c.execute("SELECT n_subj FROM schools WHERE shl_idf_cd=?",
                    ("9dfe0125-996c-4ba6-8400-08e1ff1759ec",)).fetchone())
    print("[검증] 시도별 데이터보유 학교수:")
    for row in c.execute("""SELECT sido, SUM(has_curriculum), COUNT(*)
                            FROM schools GROUP BY sido
                            ORDER BY SUM(has_curriculum) DESC LIMIT 6"""):
        print(f"   {row[0]}: {row[1]}/{row[2]}")
    print("[검증] 최다 개설과목 TOP5:")
    for row in c.execute("""SELECT subject, COUNT(DISTINCT shl_idf_cd) n
                            FROM school_subjects GROUP BY subject
                            ORDER BY n DESC LIMIT 5"""):
        print(f"   {row[0]}: {row[1]}교")
    con.close()
    print("\n저장:", DB)


if __name__ == "__main__":
    main()
