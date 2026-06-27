# -*- coding: utf-8 -*-
"""커리어넷 내부 JSON API 재수집 — 원천 JSON 보관용.

기존 Selenium 크롤은 렌더된 DOM에서 '이름 텍스트'만 떠서 관계 ID를 버렸다.
내부 API는 관계를 ID로 준다:
  · 학과: https://www.career.go.kr/cloud/api/major/uView?seq=N
      relateJob[].relate_SEQ = 직업 ID (★ major_job 정본),
      relateSubject2022[]/relateSubject2015[] = 과목 seq + subject_DESCRIPTION(일반/진로/융합),
      relateQualf[] = 자격 seq, major_SUMRY/characteristics/interest/career_ACT = 카드설명
  · 직업: https://www.career.go.kr/cloud/api/job/view?seq=N
      jobWorkList(하는일)/jobAbilityList/jobAptitudeList/jobInterestList/wage,
      jobDepartList(관련학과: seq=null, 이름만), jobCertiList(+q-net URL)

원천 JSON을 raw/{major|job}/{seq}.json 으로 저장(파싱은 별도 단계). 재개·재시도 내장.
사용: python crawl_careernet_api.py [limit]   (limit=각 타입 앞 N개만, 테스트용)
"""
import csv
import json
import os
import sys
import time

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, "raw")

ENDPOINTS = {
    "major": "https://www.career.go.kr/cloud/api/major/uView?seq={}",
    "job":   "https://www.career.go.kr/cloud/api/job/view?seq={}",
}
SEQ_FILES = {"major": "major_seq_list.csv", "job": "job_seq_list.csv"}
# 응답이 정상 상세인지 최소 검증(에러 응답은 timestamp/status/error 만 옴)
KEYCHECK = {
    "major": lambda d: isinstance(d, dict) and "seq" in d and ("relateJob" in d or "major_NM" in d),
    "job":   lambda d: isinstance(d, dict) and ("job_nm" in d or "jobWorkList" in d),
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://www.career.go.kr/",
    "Accept": "application/json, text/plain, */*",
}
DELAY = 0.4          # 요청 간 간격(예의)
TRIES = 3


def load_seqs(kind):
    with open(os.path.join(BASE, SEQ_FILES[kind]), encoding="utf-8-sig") as f:
        r = csv.reader(f)
        next(r, None)  # header
        return [row[0].strip() for row in r if row and row[0].strip()]


def fetch(kind, seq, session):
    url = ENDPOINTS[kind].format(seq)
    err = "?"
    for t in range(TRIES):
        try:
            r = session.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                d = r.json()
                if KEYCHECK[kind](d):
                    return d, None
                return None, "badkey:" + ",".join(list(d)[:3])
            err = "http%s" % r.status_code
        except Exception as e:
            err = type(e).__name__
        time.sleep(1.5 * (t + 1))
    return None, err


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    session = requests.Session()
    status = []
    for kind in ("major", "job"):
        outdir = os.path.join(RAW, kind)
        os.makedirs(outdir, exist_ok=True)
        seqs = load_seqs(kind)
        if limit:
            seqs = seqs[:limit]
        total = len(seqs)
        print("[%s] %d건 시작" % (kind, total))
        for i, seq in enumerate(seqs, 1):
            fp = os.path.join(outdir, "%s.json" % seq)
            if os.path.exists(fp) and os.path.getsize(fp) > 200:
                status.append((kind, seq, "skip"))
                continue
            d, err = fetch(kind, seq, session)
            if d is not None:
                json.dump(d, open(fp, "w", encoding="utf-8"), ensure_ascii=False)
                status.append((kind, seq, "ok"))
            else:
                status.append((kind, seq, "FAIL:" + str(err)))
                print("  FAIL %s seq=%s (%s)" % (kind, seq, err))
            time.sleep(DELAY)
            if i % 50 == 0:
                print("  %s %d/%d" % (kind, i, total))

    with open(os.path.join(BASE, "collection_status_api.csv"), "w",
              encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["type", "seq", "status"])
        w.writerows(status)
    ok = sum(1 for s in status if s[2] in ("ok", "skip"))
    fail = [s for s in status if s[2].startswith("FAIL")]
    print("완료: %d/%d 성공, 실패 %d" % (ok, len(status), len(fail)))


if __name__ == "__main__":
    main()
