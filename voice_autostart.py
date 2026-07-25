# -*- coding: utf-8 -*-
"""
로그온 자동시작 상주 발사대 — 작업 스케줄러 "Lucy 목소리"가 pythonw로 이걸 부릅니다.

왜 '상주'인가 (전부 실측):
  · pythonw로 서버를 직접 돌리면 tqdm 등이 sys.stderr(None)에 써서 죽습니다(결과 1).
  · 떼어서(DETACHED) 켜고 발사대가 끝나면, 작업 스케줄러의 잡 오브젝트가
    **발사대 종료와 함께 자식(서버)까지 거둬 갑니다.** CREATE_BREAKAWAY_FROM_JOB도
    이 스케줄러의 잡에서는 거부됩니다 — 2026-07-15 실측: 작업은 '성공(0)'으로 기록되는데
    10초 뒤 서버가 없음. 그래서 부팅마다 목소리가 조용히 구글로 내려가 있었습니다.
  → 해법: 발사대가 서버를 자식으로 안고 **서버가 사는 동안 함께 상주**합니다.
    잡이 비지 않으니 거둬갈 일이 없고, 서버가 죽으면 다시 켭니다(자가 치유).
    서버 출력은 memory/melo_server.log로 받습니다 — pythonw의 stderr 문제도 같이 풀리고,
    서버가 왜 죽었는지 처음으로 눈에 보이게 됩니다(em-dash 사망 사건의 교훈).
"""
import os
import subprocess
import time

import doctor

LOG = os.path.join(doctor.BASE_DIR, "memory", "melo_server.log")
MAX_LOG = 1_000_000          # 이걸 넘으면 .old로 밀어냅니다 — 로그가 디스크를 먹지 않게


def _log_handle():
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > MAX_LOG:
            os.replace(LOG, LOG + ".old")
    except OSError:
        pass
    return open(LOG, "a", encoding="utf-8", errors="replace")


def main():
    if not os.path.isfile(doctor.MELO_PY):
        return                           # D:\lucy-tts가 없는 PC — 조용히 물러납니다
    quick_deaths = 0
    while quick_deaths < 5:              # 켜자마자 5번 연속 죽으면 코드 문제 — 무한 재시도 금지
        if doctor._port_open(doctor.MELO_PORT):
            # 다른 인스턴스(start.bat 동반기동 등)가 이미 서비스 중 — 자리만 지킵니다.
            # 그쪽이 죽으면 다음 바퀴에 이 발사대가 이어받습니다.
            time.sleep(60)
            quick_deaths = 0
            continue
        with _log_handle() as log:
            log.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} 서버 시작 ---\n")
            log.flush()
            proc = subprocess.Popen(
                [doctor.MELO_PY, os.path.join(doctor.BASE_DIR, "tts_local_server.py")],
                cwd=doctor.BASE_DIR, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                # 부모(pythonw)는 콘솔이 없어서, 이게 없으면 자식(python.exe)이 검은 창을 띄웁니다
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
            )
            started = time.time()
            proc.wait()                  # 서버가 사는 동안 여기 머무릅니다 — 잡을 비우지 않는 핵심
        lived = time.time() - started
        quick_deaths = quick_deaths + 1 if lived < 120 else 0
        time.sleep(5)


if __name__ == "__main__":
    main()
