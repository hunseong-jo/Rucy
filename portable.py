# -*- coding: utf-8 -*-
"""
이식성 도우미 — 이 폴더를 다른 PC로 옮겨도 경로가 알아서 맞게 합니다.

두 가지를 해결합니다:
  1) 경로 안의 사용자 이름·드라이브 차이  → expand(): ~·환경변수를 풀고, 다른 사용자
     이름이 박힌 경로(C:\\Users\\옛이름\\…)는 지금 사용자로 자동 교정(원경로가 없을 때만).
  2) 블렌더·유니티가 어디 깔렸는지            → find_blender()/find_unity(): PATH·Unity Hub·
     흔한 설치 위치를 훑어 자동으로 찾음. config에 적어두면 그게 최우선.

config에 절대경로를 박아두는 대신 이걸 쓰면, "폴더 복사 → 파이썬 설치"만으로 대부분
맞아 들어갑니다. (스케줄러 재등록·외부 프로그램 설치는 setup_check가 안내)
"""
import glob
import os
import re
import shutil
import string

import sys

_cache = {}


def expand(path):
    """~·환경변수를 풀고, 다른 사용자 이름이 박힌 경로면 현재 사용자로 교정합니다.
    교정은 **바꾼 경로가 실제로 존재할 때만** 합니다(엉뚱하게 바꾸지 않게)."""
    if not path:
        return path
    p = os.path.normpath(os.path.expanduser(os.path.expandvars(str(path))))
    if os.path.exists(p):
        return p
    m_win = re.match(r"(?i)^([A-Za-z]:[\\/]+Users[\\/]+)([^\\/]+)([\\/].*)?$", p)
    if m_win:
        rest = m_win.group(3) or ""
        cand = os.path.normpath(os.path.join(os.path.expanduser("~"), rest.lstrip("\\/")))
        if os.path.exists(cand):
            return cand
    m_linux = re.match(r"^(/home/)([^/]+)(/.*)?$", p)
    if m_linux:
        rest = m_linux.group(3) or ""
        cand = os.path.normpath(os.path.join(os.path.expanduser("~"), rest.lstrip("/")))
        if os.path.exists(cand):
            return cand
    return p


def _drives():
    if sys.platform != "win32":
        return ["/"]
    return [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]


def find_blender():
    """블렌더 실행파일을 흔한 위치에서 찾습니다(못 찾으면 None)."""
    if "blender" in _cache and (_cache["blender"] is None or os.path.isfile(_cache["blender"])):
        return _cache["blender"]
    hit = shutil.which("blender")
    if not hit:
        pats = []
        if sys.platform != "win32":
            pats = ["/usr/bin/blender", "/usr/local/bin/blender", "/snap/bin/blender"]
        else:
            for d in _drives():
                pats += [
                    os.path.join(d, "Program Files", "Blender Foundation", "Blender*", "blender.exe"),
                    os.path.join(d, "Program Files (x86)", "Blender Foundation", "Blender*", "blender.exe"),
                    os.path.join(d, "blander", "blender.exe"),      # 이 사용자 자리(폴더명 오타 포함)
                    os.path.join(d, "Blender*", "blender.exe"),
                    os.path.join(d, "*", "Steam", "steamapps", "common", "Blender", "blender.exe"),
                ]
        for pat in pats:
            cands = sorted((p for p in glob.glob(pat) if os.path.isfile(p)), reverse=True)
            if cands:
                hit = cands[0]                                   # 최신 버전 우선
                break
    _cache["blender"] = hit
    return hit


def find_unity(version=None):
    """유니티 에디터를 Unity Hub·흔한 위치에서 찾습니다. version(예: 6000.4.5f1)을 주면 우선."""
    key = f"unity:{version}"
    if key in _cache and (_cache[key] is None or os.path.isfile(_cache[key])):
        return _cache[key]
    hit = shutil.which("unity") or shutil.which("Unity")
    if hit:
        _cache[key] = hit
        return hit
    found = []
    if sys.platform != "win32":
        home = os.path.expanduser("~")
        pats = [
            os.path.join(home, "Unity", "Hub", "Editor", "*", "Editor", "Unity"),
            os.path.join("/opt", "Unity", "Hub", "Editor", "*", "Editor", "Unity"),
        ]
        for pat in pats:
            found += glob.glob(pat)
    else:
        for d in _drives():
            found += glob.glob(os.path.join(d, "Program Files", "Unity", "Hub", "Editor",
                                            "*", "Editor", "Unity.exe"))
            found += glob.glob(os.path.join(d, "Unity", "Hub", "Editor", "*", "Editor", "Unity.exe"))
            found += glob.glob(os.path.join(d, "*", "Editor", "Unity.exe"))   # Hub 밖(D:\6000.4.5f1\…)
    found = [p for p in dict.fromkeys(found) if os.path.isfile(p)]
    hit = None
    if version:
        hit = next((p for p in found if version in p.replace("\\", "/")), None)
    if not hit:
        hit = sorted(found, reverse=True)[0] if found else None
    _cache[key] = hit
    return hit


def project_unity_version(project_dir):
    """유니티 프로젝트의 ProjectVersion.txt에서 에디터 버전을 읽습니다(없으면 None)."""
    pv = os.path.join(project_dir, "ProjectSettings", "ProjectVersion.txt")
    try:
        with open(pv, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("m_EditorVersion:"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return None
