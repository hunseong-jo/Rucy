# -*- coding: utf-8 -*-
"""
코딩 작업실 — 루시가 여러 파일짜리 프로그램을 짓고·돌려보고·고쳐가며 완성합니다.

run_python은 임시파일 하나를 한 번 돌리고 버립니다(계산용). 그래서 여러 파일로 된
프로그램을 만들거나, 에러를 읽고 한 줄 고쳐 다시 돌리는 '진짜 코딩'은 못 했습니다.
이 모듈은 전용 폴더(workspace/)를 두고 그 안에서만 파일을 만들고 실행하게 합니다.

    code_write → code_run → (에러) → code_edit → code_run → … → 완성

**격리**가 핵심입니다. 코딩 도구는 workspace/ **밖을 절대 못 건드립니다**(경로 탈출 차단).
사용자의 진짜 파일(바탕화면·문서)은 여기서 안전합니다 — 실수로 지어본 프로그램이
엉뚱한 파일을 덮어쓸 길이 없습니다. 실행(code_run)만 위험하므로 거기서만 확인을 받습니다.

이 파일은 확인(허락받기)을 하지 않는 순수 로직입니다 — 확인 정책은 tools.py가 가집니다
(터미널은 물어보고, 웹·배경은 실행을 거부하는 그 규칙을 코딩도 똑같이 따르게).
"""
import os
import shutil
import subprocess
import sys

WORKSPACE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workspace")

# C# 파일 하나만으론 dotnet이 못 돌립니다 — 폴더에 최소 콘솔 프로젝트(.csproj)가 있어야
# 합니다. 없으면 이걸 자동으로 깔아 줍니다(ImplicitUsings=켜서 using 안 써도 Console 됨).
_CSPROJ = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net9.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>disable</Nullable>
    <InvariantGlobalization>true</InvariantGlobalization>
  </PropertyGroup>
</Project>
"""


def ws_path(rel):
    """작업실 기준 상대경로를 실제 경로로. 작업실 밖(.. 탈출·절대경로)은 거부합니다."""
    rel = str(rel).strip().strip('"\'').replace("\\", "/").lstrip("/")
    full = os.path.abspath(os.path.join(WORKSPACE, rel))
    nc_full, nc_root = os.path.normcase(full), os.path.normcase(WORKSPACE)
    if nc_full != nc_root and not nc_full.startswith(nc_root + os.sep):
        raise PermissionError("작업실(workspace) 밖은 코딩 도구로 건드릴 수 없습니다.")
    return full


def write(rel, content):
    path = ws_path(rel)
    parent = os.path.dirname(path)
    if not parent or os.path.normcase(path) == os.path.normcase(WORKSPACE):
        return "오류: 파일 이름이 필요합니다(예: main.py 또는 앱/main.py)."
    os.makedirs(parent, exist_ok=True)
    existed = os.path.isfile(path)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content if content is not None else "")
    return f"{'덮어씀' if existed else '새로 만듦'}: {rel} ({len(content or '')}자)"


def read(rel):
    path = ws_path(rel)
    if not os.path.isfile(path):
        return f"오류: 작업실에 그런 파일이 없습니다: {rel} (code_list로 목록 확인)"
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    return text[:20000] + "\n…(생략)" if len(text) > 20000 else text


def edit(rel, find, replace, all_=False):
    """파일에서 find 부분만 replace로 바꿉니다. 통째로 다시 쓸 필요 없이 한 곳만 고칠 때."""
    path = ws_path(rel)
    if not os.path.isfile(path):
        return f"오류: 작업실에 그런 파일이 없습니다: {rel}"
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    n = text.count(find)
    if n == 0:
        return ("오류: 찾는 내용이 원문에 없어 못 바꿨습니다. "
                "code_read로 지금 코드를 확인하고 정확히 붙여 넣으세요.")
    if n > 1 and not all_:
        return (f"오류: 그 내용이 {n}군데 있어 어디를 바꿀지 모호합니다. "
                "앞뒤를 더 붙여 범위를 넓히거나, 전부 바꾸려면 all=true.")
    new = text.replace(find, replace) if all_ else text.replace(find, replace, 1)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new)
    return f"수정 완료: {rel} ({'전부' if all_ else '1곳'} 교체, {len(find)}자→{len(replace)}자)"


def list_tree(sub=None):
    root = ws_path(sub) if sub else WORKSPACE
    if not os.path.isdir(root):
        return "작업실이 비어 있습니다. code_write로 파일을 만들면 여기 쌓입니다."
    rows = []
    for dirpath, dirs, files in os.walk(root):
        dirs.sort()
        for fn in sorted(files):
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, WORKSPACE).replace(os.sep, "/")
            rows.append(f"  {rel}  ({os.path.getsize(full)}B)")
        if len(rows) >= 200:
            rows.append("  …(200개 넘어 생략)")
            break
    return "작업실 파일:\n" + "\n".join(rows) if rows else "작업실이 비어 있습니다."


def run(rel, args=None, timeout=None):
    """작업실 파일을 실행합니다. 확장자로 갈라집니다 — .py는 파이썬, .cs는 dotnet(C#).
    cwd는 그 파일이 있는 폴더(상대경로 읽기·프로젝트 단위 실행이 되게)."""
    path = ws_path(rel)
    if not os.path.isfile(path):
        return f"오류: 작업실에 그런 파일이 없습니다: {rel} (code_list로 목록 확인)"
    ext = os.path.splitext(path)[1].lower()
    if ext == ".cs":
        return _run_csharp(path, args, timeout)
    return _run_python(path, args, timeout)


import re


def parse_traceback(text):
    """트레이스백 및 예외 메시지를 파싱하여 자동 진단 및 복구 가이드를 생성합니다."""
    if not text:
        return ""
    
    hints = []
    
    # 1. ModuleNotFoundError / ImportError (pip auto-install guideline)
    mod_match = re.search(r"(?:ModuleNotFoundError|ImportError):\s+No module named\s+['\"]([^'\"]+)['\"]", text)
    if mod_match:
        missing_mod = mod_match.group(1).split(".")[0]
        hints.append(f"💡 [자동 진단] 누락된 패키지: '{missing_mod}'")
        hints.append(f"💡 [복구 가이드] code_install(package=\"{missing_mod}\") 도구를 실행해 패키지를 자동 설치한 후 다시 실행해 보세요.")
    
    # 2. 파이썬 트레이스백 파싱 (파일명, 줄 번호, 예외 종류)
    tb_matches = re.findall(r'File "([^"]+)", line (\d+), in (\S+)', text)
    err_line_match = re.search(r"^([A-Z]\w*(?:Error|Exception|Interrupt|Exit)): (.*)$", text, re.M)
    
    if err_line_match:
        err_type = err_line_match.group(1)
        err_msg = err_line_match.group(2).strip()
        loc = f" line {tb_matches[-1][1]}" if tb_matches else ""
        hints.append(f"💡 [자동 진단]{loc} {err_type}: {err_msg}")
        
        if err_type == "SyntaxError":
            hints.append("💡 [복구 가이드] 문법 오류입니다. 괄호, 따옴표, 들여쓰기를 확인하고 code_edit으로 수정하세요.")
        elif err_type in ("NameError", "AttributeError", "TypeError", "ValueError", "IndexError", "KeyError", "ZeroDivisionError"):
            hints.append(f"💡 [복구 가이드] {err_type}가 발생했습니다. 변수/함수 정의 및 인자 타입을 확인하고 code_edit으로 수정하세요.")
        elif err_type == "FileNotFoundError":
            hints.append("💡 [복구 가이드] 파일이 존재하지 않습니다. 경로를 재확인하거나 code_write로 파일을 새로 만드세요.")

    return "\n".join(hints)


def _fmt(returncode, out, empty_hint):
    if len(out) > 10000:
        out = "…(앞부분 생략)\n" + out[-10000:]      # 에러는 보통 끝에 있으므로 뒤를 남깁니다
    ok = "성공" if returncode == 0 else "실패"
    res = f"[{ok} · 종료코드 {returncode}]\n" + (out or empty_hint)
    diag = parse_traceback(out)
    if diag:
        res += f"\n\n{diag}"
    return res



def _run_python(path, args, timeout):
    to = timeout or 60
    cmd = [sys.executable, path] + [str(a) for a in (args or [])]
    # 자식이 한글을 찍다 cp949로 죽지 않게 UTF-8을 강제합니다(이 프로젝트의 오랜 함정).
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=to,
                              encoding="utf-8", errors="replace",
                              cwd=os.path.dirname(path), env=env)
    except subprocess.TimeoutExpired:
        return f"{to}초를 넘겨 중단했습니다(무한 루프·입력 대기·서버일 수 있습니다)."
    out = (proc.stdout or "") + (proc.stderr or "")
    return _fmt(proc.returncode, out, "(출력 없음 — print()로 찍어야 보입니다)")


def _ensure_csproj(proj_dir):
    """폴더에 .csproj가 없으면 최소 콘솔 프로젝트를 깔아 줍니다."""
    for f in os.listdir(proj_dir):
        if f.lower().endswith(".csproj"):
            return
    name = os.path.basename(proj_dir.rstrip("\\/")) or "app"
    with open(os.path.join(proj_dir, name + ".csproj"), "w", encoding="utf-8") as f:
        f.write(_CSPROJ)


def _run_csharp(path, args, timeout):
    if not shutil.which("dotnet"):
        return ("오류: dotnet SDK가 없어 C#을 실행할 수 없습니다. "
                "https://dotnet.microsoft.com/download 에서 설치 후 다시 시도하세요.")
    to = timeout or 180        # 첫 빌드는 복원·컴파일로 느립니다
    proj_dir = os.path.dirname(path)
    _ensure_csproj(proj_dir)
    # 폴더에 Main이 든 .cs가 여럿이면 dotnet이 에러를 냅니다 — 그건 C#의 정상 제약이라
    # 모델이 로그를 보고 정리하게 둡니다. 한글 출력이 깨지지 않게 UTF-8 콘솔을 유도합니다.
    env = dict(os.environ, DOTNET_NOLOGO="1", DOTNET_CLI_TELEMETRY_OPTOUT="1",
               DOTNET_CLI_UI_LANGUAGE="en")
    cmd = ["dotnet", "run", "--project", proj_dir]
    if args:
        cmd += ["--"] + [str(a) for a in args]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=to,
                              encoding="utf-8", errors="replace", cwd=proj_dir, env=env)
    except subprocess.TimeoutExpired:
        return (f"{to}초를 넘겨 중단했습니다. 첫 빌드는 오래 걸립니다 — "
                "timeout을 늘려(예: 300) 다시 실행해 보세요.")
    out = (proc.stdout or "") + (proc.stderr or "")
    return _fmt(proc.returncode, out, "(출력 없음 — Console.WriteLine으로 찍어야 보입니다)")


def pip_install(package, timeout=180):
    cmd = [sys.executable, "-m", "pip", "install"] + str(package).split()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return f"{timeout}초를 넘겨 설치를 중단했습니다."
    out = (proc.stdout or "") + (proc.stderr or "")
    tail = out[-4000:] if len(out) > 4000 else out
    return f"[pip 종료코드 {proc.returncode}]\n" + (tail or "(출력 없음)")
