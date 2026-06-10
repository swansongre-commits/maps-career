"""
전체 파이프라인 드라이버: 크롤(2026) → 파싱 → 병합(2025∪2026) → SQLite DB화.
각 단계를 subprocess로 순차 실행하고 진행을 pipeline.log에 남긴다.
크롤은 collection_status.csv 체크포인트로 재개되므로, 중간에 끊겨 재실행해도 이어짐.
"""
import sys, subprocess, time, ctypes
from pathlib import Path
ROOT = Path(__file__).parent
PY = sys.executable
LOG = ROOT / "pipeline.log"


def keep_awake():
    """실행 동안 OS 절전/디스플레이 끔 방지(caffeinate 상당). Windows 전용."""
    try:
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ES_AWAYMODE_REQUIRED = 0x00000040
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED)
        print("[keep_awake] OS 절전 방지 ON", flush=True)
    except Exception as e:
        print("[keep_awake] 실패:", e, flush=True)


def release_awake():
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)  # ES_CONTINUOUS만
    except Exception:
        pass


def run(step, args):
    msg = f"\n===== [{time.strftime('%m-%d %H:%M:%S')}] {step}: {' '.join(args)} =====\n"
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg)
    print(msg.strip(), flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        r = subprocess.run([PY] + args, stdout=f, stderr=subprocess.STDOUT,
                           cwd=str(ROOT))
    print(f"  -> exit {r.returncode}", flush=True)
    if r.returncode != 0:
        raise SystemExit(f"{step} 실패(exit {r.returncode}) — pipeline.log 확인")


def main():
    t0 = time.time()
    keep_awake()
    try:
        run("1.크롤(2026)", ["crawl_curriculum.py", "--year", "2026", "--pause", "0.2"])
        run("2.파싱", ["parse_curriculum.py"])
        run("3.병합", ["merge_years.py"])
        run("4.DB화", ["build_db.py"])
    finally:
        release_awake()
    mins = round((time.time() - t0) / 60, 1)
    print(f"\n##### 파이프라인 완료 ({mins}분) #####", flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"\n##### DONE {mins}min @ {time.strftime('%m-%d %H:%M')} #####\n")


if __name__ == "__main__":
    main()
