# -*- coding: utf-8 -*-
"""성취기준.xlsx → achievement_standards.json
교과-과목별 2022 개정 성취기준(코드+내용)을 정규화 과목키로 묶는다.
키: loose_norm(과목)  값: {subject(대표 원형명), gwa(교과), items:[{code, text}]}
추천엔진 recommender.achievements_for_subject()가 조회(정확+오타허용 매칭)."""
import json
import re
import openpyxl

SRC = "성취기준.xlsx"
OUT = "achievement_standards.json"

_ROMAN = {"Ⅰ": "I", "Ⅱ": "II", "Ⅲ": "III", "Ⅳ": "IV"}


def loose_norm(s):
    """공백·중점·괄호 등 제거 + 로마숫자 정규화 → 과목명 매칭 키."""
    s = str(s or "")
    for a, b in _ROMAN.items():
        s = s.replace(a, b)
    return re.sub(r"[^가-힣A-Za-z0-9]", "", s)


def main():
    wb = openpyxl.load_workbook(SRC, read_only=True, data_only=True)
    ws = wb["Sheet1"]
    out = {}
    n = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or not row[1]:
            continue
        gwa, subject, code, text = row[0], row[1], row[2], row[3]
        text = (str(text).strip() if text else "")
        code = (str(code).strip().strip("[]") if code else "")
        if not text:
            continue
        key = loose_norm(subject)
        if key not in out:
            out[key] = {"subject": str(subject).strip(),
                        "gwa": str(gwa).strip() if gwa else "", "items": []}
        out[key]["items"].append({"code": code, "text": text})
        n += 1
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    cnt = sorted((len(v["items"]) for v in out.values()))
    print(f"과목 {len(out)}개 · 성취기준 {n}개 → {OUT}")
    print(f"과목당 성취기준수  min/median/max: "
          f"{cnt[0]}/{cnt[len(cnt)//2]}/{cnt[-1]}")


if __name__ == "__main__":
    main()
