# -*- coding: utf-8 -*-
"""
스키마 검증 및 자가 치유(Self-Healing) 래퍼 (schema_validator.py)
"""

TOOL_SCHEMAS = {
    "read_file": {"required": ["path"], "types": {"path": str}},
    "write_file": {"required": ["path", "content"], "types": {"path": str, "content": str}},
    "calc": {"required": ["expression"], "types": {"expression": str}},
    "web_search": {"required": ["query"], "types": {"query": str}},
    "research": {"required": ["question"], "types": {"question": str, "depth": int}},
    "remember": {"required": ["fact"], "types": {"fact": str}},
    "forget": {"required": ["about"], "types": {"about": str}},
    "run_python": {"required": ["code"], "types": {"code": str}},
    "run_powershell": {"required": ["command"], "types": {"command": str}},
}


def validate_args(tool_name, args):
    """도구 인자의 필수 키 및 타입을 검증하고 자동 타입 보정을 수행합니다.
    (is_valid, corrected_args, error_message) 반환.
    """
    if not isinstance(args, dict):
        return False, {}, "인자는 dict 객체이어야 합니다."

    schema = TOOL_SCHEMAS.get(tool_name)
    if not schema:
        return True, dict(args), "등록된 스키마 없음(통과)"

    corrected = dict(args)
    missing = []
    for key in schema.get("required", []):
        if key not in corrected or corrected[key] is None:
            missing.append(key)
    
    if missing:
        return False, corrected, f"필수 인자가 누락되었습니다: {', '.join(missing)}"

    # 타입 보정 및 검증
    types = schema.get("types", {})
    for key, expected_type in types.items():
        if key in corrected and corrected[key] is not None:
            val = corrected[key]
            if not isinstance(val, expected_type):
                try:
                    corrected[key] = expected_type(val)
                except (ValueError, TypeError):
                    return False, corrected, f"'{key}' 매개변수의 타입({type(val).__name__})이 {expected_type.__name__}(으)로 변환될 수 없습니다."

    return True, corrected, "정상"


def self_heal_execute(func, args, tool_name=None):
    """
    도구를 실행하되 KeyError 또는 TypeError 발생 시 1회 자가치유 보정 후 재시도합니다.
    """
    if not isinstance(args, dict):
        args = {}

    name = tool_name or getattr(func, "__name__", "unknown")
    is_valid, corrected, err_msg = validate_args(name, args)

    try:
        return func(corrected)
    except (KeyError, TypeError) as e:
        # 1회 자가치유 시도: 빈 키보정
        healed_args = dict(corrected)
        schema = TOOL_SCHEMAS.get(name, {})
        for req in schema.get("required", []):
            if req not in healed_args or healed_args[req] is None:
                healed_args[req] = "" if schema.get("types", {}).get(req) == str else 0
        try:
            return func(healed_args)
        except Exception as retry_e:
            return f"자가치유 실행 실패 ({type(retry_e).__name__}): {retry_e}"
