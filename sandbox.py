# -*- coding: utf-8 -*-
"""
명령어 및 코드 실행 샌드박스 (sandbox.py)
"""
import ast
import re
import subprocess
import sys
import tempfile
import os

DANGEROUS_PATTERNS = [
    re.compile(r"\brmdir\s+/[sS]", re.I),
    re.compile(r"\bdel\s+/[fFsS]", re.I),
    re.compile(r"\bformat\b", re.I),
    re.compile(r"\bRemove-Item\b.*-Recurse", re.I),
    re.compile(r"\bRemove-Item\b.*-Force", re.I),
    re.compile(r"\bdrop\s+database\b", re.I),
]

FORBIDDEN_AST_CALLS = {
    "shutil.rmtree",
    "os.system",
}


def validate_command(cmd):
    """파괴적 명령어가 포함되어 있는지 검사합니다. (is_safe, message) 리턴"""
    if not cmd or not str(cmd).strip():
        return False, "명령어가 비어 있습니다."
    
    cmd_str = str(cmd)
    for pattern in DANGEROUS_PATTERNS:
        if pattern.search(cmd_str):
            return False, f"파괴적인 위험 명령어가 포함되어 실행이 차단되었습니다: {pattern.pattern}"
    
    return True, "안전함"


def run_code_isolated(code, timeout=60):
    """파이썬 코드를 AST 파싱 후 격리 실행합니다. (is_success, output) 리턴"""
    if not code or not str(code).strip():
        return False, "코드가 비어 있습니다."
    
    try:
        parsed = ast.parse(code)
    except SyntaxError as e:
        return False, f"구문 오류: {e}"

    # AST 검사
    for node in ast.walk(parsed):
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    func_name = f"{node.func.value.id}.{node.func.attr}"
            if func_name in FORBIDDEN_AST_CALLS:
                return False, f"안전상 금지된 함수 호출이 감지되었습니다: {func_name}"

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        temp_path = f.name

    try:
        proc = subprocess.run([sys.executable, temp_path], capture_output=True, text=True,
                              timeout=timeout, encoding="utf-8", errors="replace")
        out = (proc.stdout or "") + (proc.stderr or "")
        return True, out[:10000]
    except subprocess.TimeoutExpired:
        return False, "실행 시간이 초과되었습니다."
    finally:
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass
