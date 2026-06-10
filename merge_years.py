"""
2025·2026 파싱 결과 병합 → 최종 학교별 개설과목 데이터.
한 학교가 어느 해든 개설한 과목이면 '개설'로 본다(커버리지 극대화).
2026 공시가 아직 미업로드인 학교는 2025로 보완.

입력 : subjects_by_school_2025.json, subjects_by_school.json(=2026)
출력 : subjects_by_school_merged.json, subjects_by_school_merged.csv
       (recommender가 쓸 최종본. 필요시 이 파일을 subjects_by_school.json으로 채택)
"""
import sys, json, csv, collections
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent


def load(p):
    f = ROOT / p
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def main():
    y25 = load("subjects_by_school_2025.json")
    y26 = load("subjects_by_school.json")  # 2026 재파싱 결과
    keys = set(y25) | set(y26)
    merged = {}
    only25 = only26 = both = 0
    for k in keys:
        a, b = y25.get(k), y26.get(k)
        base = b or a                       # 최신(2026) 메타 우선
        subj = collections.defaultdict(set)
        years = set()
        for src, tag in ((a, "2025"), (b, "2026")):
            if not src:
                continue
            years.add(tag)
            for typ, lst in src.get("subjects", {}).items():
                subj[typ].update(lst)
        if a and b: both += 1
        elif b: only26 += 1
        else: only25 += 1
        merged[k] = {
            "shl_idf_cd": base.get("shl_idf_cd", k if "-" in k else ""),
            "school": base.get("school"), "sido": base.get("sido"),
            "gugun": base.get("gugun", ""),
            "years": sorted(years),
            "subjects": {t: sorted(v) for t, v in subj.items()},
            "n_subj": sum(len(v) for v in subj.values()),
        }
    (ROOT / "subjects_by_school_merged.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(ROOT / "subjects_by_school_merged.csv", "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["shl_idf_cd", "school", "sido", "gugun", "years", "type", "subject"])
        for k, v in merged.items():
            for t, lst in v["subjects"].items():
                for s in lst:
                    w.writerow([v["shl_idf_cd"], v["school"], v["sido"],
                                v["gugun"], "+".join(v["years"]), t, s])
    print(f"병합 학교수 {len(merged)}  (2025만 {only25} / 2026만 {only26} / 양년 {both})")
    cnts = sorted(v["n_subj"] for v in merged.values() if v["n_subj"])
    if cnts:
        print(f"과목수 중앙값 {cnts[len(cnts)//2]}  최대 {cnts[-1]}")
    print("저장: subjects_by_school_merged.json / .csv")


if __name__ == "__main__":
    main()
