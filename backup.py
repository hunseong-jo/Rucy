# -*- coding: utf-8 -*-
"""
기억 백업 — 루시의 정체성(기억·교훈·지식·열쇠·설정)은 전부 이 PC 한 대에 있습니다.
디스크가 죽으면 루시가 통째로 사라지므로, 주 1회 새벽에 zip 하나로 묶어
구글 드라이브 동기화 폴더에 둡니다. setup_check.py의 이식성(폴더만 복사하면
다른 PC에서 이어 씀)이 그대로 복구 절차가 됩니다: zip을 새 my-agent에 풀면 끝.

- 같은 날 다시 돌면 같은 이름에 덮어씁니다(하루 한 개).
- 최근 keep개(기본 4)만 남기고 오래된 것은 지웁니다 — 드라이브를 무한정 먹지 않게.
- 드라이브가 안 보이면(동기화 앱 꺼짐 등) 조용히 건너뜁니다. 백업은 없는 것보다
  늦는 게 낫지만, 배경 일과가 오류 창을 띄우면 그게 더 사고입니다.
"""
import datetime
import os
import zipfile

_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DEST = r"G:\내 드라이브\루시백업"
TARGETS = ["memory", "knowledge", "keys", "config.json"]   # 루시를 되살리는 데 필요한 전부
KEEP = 4


def run(config=None, notify=print):
    """백업 zip을 만들고 경로를 돌려줍니다. 드라이브가 없으면 None."""
    import portable
    conf = (config or {}).get("daily", {}).get("backup", {})
    dest = portable.expand(conf.get("dest", DEFAULT_DEST))   # ~·환경변수 지원(다른 PC 대비)
    if not os.path.isdir(os.path.dirname(dest) or dest):
        notify(f"  백업: 드라이브 폴더가 안 보여 건너뜁니다 — {dest}")
        return None
    os.makedirs(dest, exist_ok=True)

    name = f"lucy_backup_{datetime.date.today().strftime('%Y%m%d')}.zip"
    path = os.path.join(dest, name)
    tmp = path + ".tmp"
    count = 0
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for target in conf.get("targets", TARGETS):
            full = os.path.join(_DIR, target)
            if os.path.isfile(full):
                z.write(full, target)
                count += 1
            elif os.path.isdir(full):
                for root, _dirs, files in os.walk(full):
                    for fn in files:
                        p = os.path.join(root, fn)
                        z.write(p, os.path.relpath(p, _DIR))
                        count += 1
    os.replace(tmp, path)                     # 쓰다 죽어도 반쪽짜리 zip이 남지 않게

    keep = int(conf.get("keep", KEEP))
    olds = sorted(fn for fn in os.listdir(dest)
                  if fn.startswith("lucy_backup_") and fn.endswith(".zip"))
    for fn in olds[:-keep] if keep > 0 else []:
        try:
            os.remove(os.path.join(dest, fn))
        except OSError:
            pass

    size = os.path.getsize(path)
    notify(f"  백업: 파일 {count}개 → {path} ({size // 1024:,}KB)")
    return path
