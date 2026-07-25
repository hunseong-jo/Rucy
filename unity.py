# -*- coding: utf-8 -*-
"""
유니티 배치모드 훅 — 루시가 Unity 에디터를 **창 없이** 돌려 스크립트 컴파일 점검·
테스트 실행·특정 메서드 실행을 시키고 로그를 읽습니다.

코딩 작업실(coding.py)은 파이썬·순수 C#만 실행합니다. 하지만 유니티 스크립트는
UnityEngine을 참조하므로 엔진 밖에선 컴파일이 의미가 없습니다 — 유니티 자신을
배치모드로 띄워야 진짜 컴파일·테스트가 됩니다. 그 다리가 이 모듈입니다.

    Unity.exe -batchmode -nographics -projectPath <P> -logFile <L> [-quit | -runTests ...]

이걸로 루시는 "C# 고쳤는데 컴파일 되나? 테스트 통과하나?"를 스스로 확인할 수 있습니다
(전에는 눈감고 .cs를 쓰기만 했음). 무겁고(수 분) 위험하므로(사용자 프로젝트를 건드림)
실행은 tools.py에서 확인을 받고, 에디터가 이미 열려 있으면 잠금 때문에 실패합니다.
"""
import json
import os
import re
import subprocess
import tempfile
import time
from xml.etree import ElementTree

# config에 unity 블록이 없을 때의 기본값(이 PC 실측: Unity 6000.4.5f1).
DEFAULT_EXE = r"D:\6000.4.5f1\Editor\Unity.exe"


def _cfg(config):
    return (config or {}).get("unity", {}) or {}


def exe_path(config, version=None):
    """유니티 에디터 실행파일. config에 적어두면 최우선(그 자리에 있을 때), 없으면 자동
    탐지(Unity Hub·흔한 위치). version(예: 6000.4.5f1)을 주면 그 버전을 우선으로 찾습니다."""
    import portable
    raw = _cfg(config).get("exe")
    exe = portable.expand(raw) if raw else None
    if exe and os.path.isfile(exe):
        return exe
    return portable.find_unity(version) or exe or DEFAULT_EXE


def editor_log_path(config):
    """실행 중인(또는 마지막) 유니티 에디터의 로그 위치."""
    p = _cfg(config).get("editor_log")
    if p:
        return p
    return os.path.join(os.environ.get("LOCALAPPDATA", ""), "Unity", "Editor", "Editor.log")


def read_status(config, tail_kb=160):
    """에디터를 닫지 않고 Editor.log를 읽어 '마지막 컴파일'에 에러가 있었는지 봅니다.
    배치모드(unity_run)는 에디터가 열려 있으면 잠금으로 실패하지만, 이건 로그만 읽으므로
    에디터를 켜둔 채로도 됩니다. 다만 '에디터가 마지막으로 컴파일한 시점' 기준입니다."""
    path = editor_log_path(config)
    if not os.path.isfile(path):
        return f"오류: Editor.log를 찾지 못했습니다: {path} (config unity.editor_log로 지정 가능)"
    size = os.path.getsize(path)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        if size > tail_kb * 1024:
            f.seek(size - tail_kb * 1024)
        text = f.read()
    # 로그는 append-only라 옛 에러가 그대로 쌓입니다 — '가장 최근 컴파일' 구간만 봅니다.
    anchors = ("- Starting script compilation", "Begin MonoManager ReloadAssembly",
               "Refresh completed", "AssetDatabase: Starting")
    cut = max((text.rfind(a) for a in anchors), default=-1)
    region = text[cut:] if cut >= 0 else text
    errors, warnings = _parse_compile(region)
    import datetime
    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%m-%d %H:%M")

    head = f"[Editor.log · 마지막 갱신 {mtime}]\n"
    low = region.lower()
    if errors:
        body = f"현재 컴파일 에러 {len(errors)}개:\n" + "\n".join("  ✗ " + e for e in errors[:30])
    elif "compilation failed" in low or "scripts have compiler errors" in low:
        body = ("컴파일 에러가 있는 것 같은데 상세를 못 뽑았습니다(로그가 잘렸을 수 있음) — "
                "unity_run으로 정밀 확인하세요.")
    else:
        body = "최근 컴파일에 에러 없음 ✅"
    if warnings:
        body += f"\n경고 {len(warnings)}개 (예: {warnings[0]})"
    return (head + body + "\n(에디터의 '마지막 컴파일' 상태입니다 — 방금 코드를 고쳤으면 "
            "에디터가 한 번 다시 컴파일한 뒤라야 반영됩니다. 확실한 검증은 unity_run.)")


def build(config, project=None, method=None, kind=None, timeout=1800):
    """빌드용 정적 메서드를 executeMethod로 돌립니다(unity_run과 같은 배치모드 경로).
    method를 직접 주거나, config의 build_methods에서 kind(apk·aab·dev)로 고릅니다."""
    if not method:
        methods = _cfg(config).get("build_methods", {}).get(
            str(project or "").strip().lower(), {})
        if kind:
            method = methods.get(str(kind).strip().lower())
        elif len(methods) == 1:
            method = next(iter(methods.values()))
        if not method:
            avail = "; ".join(f"{k}: {', '.join(v)}"
                              for k, v in _cfg(config).get("build_methods", {}).items()) or "없음"
            return ("오류: 빌드 메서드를 정하지 못했습니다. method='Class.Method'를 직접 주거나 "
                    f"kind(apk·aab·dev 등)로 고르세요. 등록된 빌드: {avail}")
    return run_batch(config, project=project, method=method, timeout=timeout)


def resolve_project(config, project):
    """이름(config unity.projects의 별칭) 또는 전체 경로를 실제 프로젝트 폴더로.
    경로의 ~·환경변수·다른 사용자 이름은 portable.expand가 지금 PC에 맞게 풉니다."""
    import portable
    projects = _cfg(config).get("projects", {}) or {}
    if not project:
        # 등록된 프로젝트가 하나뿐이면 그것을 기본으로.
        vals = list(dict.fromkeys(projects.values()))
        return portable.expand(vals[0]) if len(vals) == 1 else None
    key = str(project).strip().lower()
    if key in projects:
        return portable.expand(projects[key])
    p = os.path.abspath(portable.expand(str(project).strip().strip('"\'')))
    return p if os.path.isdir(p) else None


def _read_log(log_path):
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def _log_tail(text, limit=8000):
    return ("…(앞부분 생략)\n" + text[-limit:]) if len(text) > limit else text


# 유니티 배치 로그의 컴파일 진단 줄:
#   Assets/Scripts/Foo.cs(12,34): error CS0103: The name 'bar' does not exist ...
_DIAG_RE = re.compile(
    r"^(.+?\.cs)\((\d+),(\d+)\):\s+(error|warning)\s+(CS\d+):\s+(.*)$", re.M)


def _parse_compile(text):
    """로그에서 컴파일 에러·경고를 뽑아 (에러목록, 경고목록)으로. 중복은 지웁니다."""
    seen = set()
    errors, warnings = [], []
    for m in _DIAG_RE.finditer(text):
        path, ln, col, kind, code, msg = m.groups()
        path = path.replace("\\", "/")
        i = path.lower().rfind("assets/")          # Assets 이하만 남겨 짧게
        short = path[i:] if i >= 0 else path
        msg = msg.strip()
        key = (short, ln, code, msg)
        if key in seen:
            continue
        seen.add(key)
        line = f"{short}({ln},{col}) {code}: {msg}"
        (errors if kind == "error" else warnings).append(line)
    return errors, warnings


def _test_summary(xml_path):
    """NUnit3 결과 xml의 test-run 요소에서 합계를 뽑습니다."""
    try:
        a = ElementTree.parse(xml_path).getroot().attrib
        return (f"테스트 결과: 총 {a.get('total', '?')} · 통과 {a.get('passed', '?')} · "
                f"실패 {a.get('failed', '?')} · 건너뜀 {a.get('skipped', '?')}\n")
    except Exception:
        return ""


def run_batch(config, project=None, method=None, tests=None, timeout=600, return_log=False,
              graphics=False, burst=True):
    """유니티를 배치모드로 한 번 돌리고 결과(종료코드+로그 꼬리)를 문자열로 돌려줍니다.
    return_log=True면 (요약문, 전체로그) 튜플 — scene_smoke처럼 로그에서 마커를 뽑는 쪽용.
    graphics=True면 -nographics를 뺍니다 — 씬을 실제로 렌더(unity_shot)할 때 필수(세션58 실측).
    burst=False면 -burst-disable-compilation — 플레이모드 배치에서 Burst가 임시 테스트
    어셈블리 잡 재컴파일에 걸려 20분 넘게 매달리는 것 실측(세션63 6부), 검증엔 불필요."""
    proj = resolve_project(config, project)
    if not proj or not os.path.isdir(proj):
        return (f"오류: 유니티 프로젝트를 찾지 못했습니다: {project!r}. "
                "이름(config unity.projects의 별칭)이나 폴더 전체 경로를 주세요.")
    if not os.path.isdir(os.path.join(proj, "Assets")):
        return f"오류: 유니티 프로젝트가 아닌 것 같습니다(Assets 폴더 없음): {proj}"
    # 에디터가 이 프로젝트를 열고 있으면 배치모드는 잠금으로 실패합니다 — 헛부팅(수십 초)을
    # 하기 전에 미리 막습니다. 잠금 표식은 프로젝트의 Temp/UnityLockfile.
    if os.path.exists(os.path.join(proj, "Temp", "UnityLockfile")):
        return ("⚠유니티 에디터가 이 프로젝트를 열고 있는 것 같습니다(Temp/UnityLockfile) — "
                "배치모드는 잠금 충돌로 실패합니다. 에디터를 닫고 다시 시도하거나, 컴파일 상태만 "
                "볼 거면 unity_status(에디터 켠 채 됨)를 쓰세요. (에디터가 꺼졌는데도 이 메시지면 "
                "그 파일이 남은 것이니 지워도 됩니다.)")
    # 프로젝트 버전에 맞는 에디터를 우선 고릅니다(다른 PC로 옮겨도 알맞은 유니티를 찾게).
    import portable
    exe = exe_path(config, version=portable.project_unity_version(proj))
    if not os.path.isfile(exe):
        return (f"오류: Unity 에디터 실행파일을 찾을 수 없습니다: {exe} "
                "(Unity Hub로 설치했거나, config unity.exe에 경로를 적어 주세요)")

    log = tempfile.NamedTemporaryFile(suffix="_unity.log", delete=False).name
    results_xml = None
    cmd = [exe, "-batchmode", "-projectPath", proj, "-logFile", log]
    if not graphics:
        cmd.insert(2, "-nographics")
    if not burst:
        cmd.insert(2, "-burst-disable-compilation")
    if tests:
        platform = "PlayMode" if str(tests).lower().startswith("play") else "EditMode"
        results_xml = log + ".results.xml"
        # -runTests 는 끝나면 스스로 종료하므로 -quit 를 넣지 않습니다(넣으면 테스트 전에 꺼짐).
        cmd += ["-runTests", "-testPlatform", platform, "-testResults", results_xml]
        did = f"{platform} 테스트"
    else:
        cmd += ["-quit"]
        if method:
            cmd += ["-executeMethod", method]
            did = f"메서드 {method}"
        else:
            did = "컴파일 점검(열고 닫기)"

    def _sweep_lock():
        """이 배치가 남긴 잠금 청소 — 프리플라이트를 통과하고 부팅했으니 에디터 잠금일 수 없고,
        비정상 종료(컴파일 에러 exit 1·타임아웃 강제 종료)는 UnityLockfile을 안 지우고 감(실측)."""
        try:
            os.remove(os.path.join(proj, "Temp", "UnityLockfile"))
        except OSError:
            pass

    t0 = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              encoding="utf-8", errors="replace")
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        _sweep_lock()
        return (f"{timeout}초를 넘겨 중단했습니다. 첫 실행이나 에셋 임포트가 오래 걸릴 수 "
                "있습니다 — timeout을 늘려 다시 시도하세요.\n" + _log_tail(_read_log(log), 3000))
    _sweep_lock()
    dur = int(time.time() - t0)

    full = _read_log(log)
    # executeMethod(빌드 등) 로그는 사본을 남깁니다 — unity_build_report가 용량 분석에 씀.
    if method:
        try:
            import shutil
            shutil.copyfile(log, os.path.join(_mem_dir(), f"unity_lastbuild_{_proj_key(proj)}.log"))
        except OSError:
            pass
    errors, warnings = _parse_compile(full)
    summary = _test_summary(results_xml) if results_xml else ""
    # 임시 로그·결과 파일은 치웁니다(핵심은 이미 요약해 돌려주므로).
    for f in (log, results_xml):
        if f and os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass

    ok = "성공" if rc == 0 else "실패"
    low = full.lower()
    hint = ""
    if rc != 0 and "another unity instance" in low:
        hint = "  ⚠에디터가 이미 열려 있어 프로젝트가 잠긴 것 같습니다 — 닫고 다시 시도하세요.\n"
    elif rc != 0 and ("no valid unity editor license" in low or "returned an error" in low
                      and "licens" in low):
        hint = "  ⚠유니티 라이선스 문제 같습니다 — Unity Hub에서 로그인/라이선스를 확인하세요.\n"

    # 컴파일 진단을 맨 앞에 깔끔히 (작은 두뇌가 노이즈 로그에서 헤매지 않게)
    parsed = ""
    if errors:
        parsed += f"컴파일 에러 {len(errors)}개:\n" + "\n".join("  ✗ " + e for e in errors[:30])
        if len(errors) > 30:
            parsed += f"\n  …외 {len(errors) - 30}개"
        parsed += "\n"
    if warnings:
        parsed += f"경고 {len(warnings)}개" + (" (예: " + warnings[0] + ")" if warnings else "") + "\n"
    if not errors and not tests and not method:
        parsed += "컴파일 에러 없음 ✅\n"

    # 성공이면 로그 원문은 군더더기 — 진단만. 실패면 맥락 위해 로그 꼬리도 붙임.
    body = summary + parsed
    if rc != 0 or (tests and not summary):
        body += "\n--- 로그 꼬리 ---\n" + _log_tail(full)
    text = f"[유니티 {did} {ok} · 종료코드 {rc} · {dur}초]\n{hint}{body}"
    return (text, full) if return_log else text


# ── 스크립트 스캐폴딩 (컴파일 되는 골격 생성) ──────────────────────
# 작은 두뇌가 MonoBehaviour 뼈대를 손으로 쓰면 base 클래스·using·구조를 자주 틀립니다.
# 종류별로 '반드시 컴파일 되는' 골격을 깔아 주고, 내용은 edit_document로 채우게 합니다.
def _template(kind, name):
    if kind == "scriptable":
        return (f'using UnityEngine;\n\n'
                f'[CreateAssetMenu(fileName = "{name}", menuName = "ScriptableObjects/{name}")]\n'
                f'public class {name} : ScriptableObject\n{{\n}}\n')
    if kind == "editor":
        return (f'using UnityEngine;\nusing UnityEditor;\n\n'
                f'public class {name} : EditorWindow\n{{\n'
                f'    [MenuItem("Tools/{name}")]\n'
                f'    static void Open() => GetWindow<{name}>("{name}");\n\n'
                f'    void OnGUI()\n    {{\n    }}\n}}\n')
    if kind == "test":
        return (f'using NUnit.Framework;\n\n'
                f'public class {name}\n{{\n'
                f'    [Test]\n'
                f'    public void {name}_Passes()\n    {{\n'
                f'        Assert.AreEqual(4, 2 + 2);\n'
                f'    }}\n}}\n')
    if kind == "plain":
        return f'public class {name}\n{{\n}}\n'
    return (f'using UnityEngine;\n\n'          # 기본 = MonoBehaviour
            f'public class {name} : MonoBehaviour\n{{\n'
            f'    void Start()\n    {{\n    }}\n\n'
            f'    void Update()\n    {{\n    }}\n}}\n')


def _ensure_test_asmdef(folder):
    """EditMode 테스트는 테스트 어셈블리(.asmdef)가 있어야 컴파일·수집됩니다."""
    for f in os.listdir(folder):
        if f.endswith(".asmdef"):
            return ""
    asmdef = {
        "name": "LucyEditModeTests",
        "references": ["UnityEngine.TestRunner", "UnityEditor.TestRunner"],
        "includePlatforms": ["Editor"],
        "excludePlatforms": [],
        "overrideReferences": True,
        "precompiledReferences": ["nunit.framework.dll"],
        "autoReferenced": False,
        "defineConstraints": ["UNITY_INCLUDE_TESTS"],
        "versionDefines": [],
        "noEngineReferences": False,
    }
    with open(os.path.join(folder, "LucyEditModeTests.asmdef"), "w", encoding="utf-8") as f:
        json.dump(asmdef, f, indent=4)
    return "  · 테스트 어셈블리(LucyEditModeTests.asmdef)도 함께 만듦.\n"


def _under(child, parent):
    c, p = os.path.normcase(os.path.abspath(child)), os.path.normcase(os.path.abspath(parent))
    return c == p or c.startswith(p + os.sep)


def new_script(config, project, name, kind="mono", folder=None):
    proj = resolve_project(config, project)
    if not proj or not os.path.isdir(proj):
        return f"오류: 유니티 프로젝트를 찾지 못했습니다: {project!r}"
    name = re.sub(r"\W", "", str(name or "").strip())
    if not name or name[0].isdigit():
        return "오류: 올바른 C# 클래스 이름을 name에 주세요(영문·숫자, 숫자로 시작 불가)."
    kind = (kind or "mono").strip().lower()
    if kind not in ("mono", "scriptable", "editor", "test", "plain"):
        return f"오류: kind는 mono·scriptable·editor·test·plain 중 하나입니다(받음: {kind})."
    if not folder:
        folder = {"test": "Assets/Tests", "editor": "Assets/Editor"}.get(kind, "Assets/Scripts")
    target_dir = os.path.abspath(os.path.join(proj, folder))
    if not _under(target_dir, os.path.join(proj, "Assets")):
        return "오류: 스크립트는 프로젝트의 Assets 폴더 안에만 만들 수 있습니다."
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, name + ".cs")
    if os.path.exists(path):
        rel = os.path.relpath(path, proj).replace(os.sep, "/")
        return f"오류: 이미 있습니다: {rel} — 새로 만들지 말고 edit_document/read_document로 고치세요."
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(_template(kind, name))
    extra = _ensure_test_asmdef(target_dir) if kind == "test" else ""
    rel = os.path.relpath(path, proj).replace(os.sep, "/")
    verify = ("unity_run(tests='EditMode')로 테스트 실행" if kind == "test"
              else "unity_run으로 컴파일 확인")
    return (f"만듦: {rel} ({kind} 골격)\n{extra}"
            f"내용은 edit_document로 채우고, {verify}하세요.")


# ── 프로젝트 코드 검색 (기존 코드 파악 → 환각 감소) ────────────────
def audit(config, project=None):
    """프로젝트를 파일 스캔으로 감사합니다(유니티 안 띄움·읽기전용·빠름):
    깨진 스크립트 참조·큰 텍스처·.meta 누락. 리팩터·머지 뒤 '왜 깨졌지'를 눈 없이 잡는 층."""
    proj = resolve_project(config, project)
    if not proj or not os.path.isdir(proj):
        return f"오류: 유니티 프로젝트를 찾지 못했습니다: {project!r}"
    assets = os.path.join(proj, "Assets")
    if not os.path.isdir(assets):
        return f"오류: Assets 폴더가 없습니다: {proj}"
    big_mb = float(_cfg(config).get("audit_texture_mb", 2))
    big_bytes = int(big_mb * 1024 * 1024)
    broken, big_tex, missing_meta = [], [], []
    n_cs = n_scene = n_prefab = 0
    for dp, _dirs, files in os.walk(assets):
        for fn in files:
            fp = os.path.join(dp, fn)
            ext = os.path.splitext(fn)[1].lower()
            rel = os.path.relpath(fp, proj).replace(os.sep, "/")
            if ext == ".cs":
                n_cs += 1
            elif ext == ".unity":
                n_scene += 1
            elif ext == ".prefab":
                n_prefab += 1
            if ext in (".prefab", ".unity", ".asset"):
                try:
                    with open(fp, "r", encoding="utf-8", errors="replace") as f:
                        if "m_Script: {fileID: 0}" in f.read():
                            broken.append(rel)
                except OSError:
                    pass
            if ext in (".png", ".jpg", ".jpeg", ".tga", ".psd", ".exr"):
                try:
                    sz = os.path.getsize(fp)
                    if sz > big_bytes:
                        big_tex.append((rel, sz))
                except OSError:
                    pass
            # 유니티 밖에서 복사하면 .meta가 빠져 참조가 깨집니다(주요 에셋만 확인).
            if ext in (".cs", ".prefab", ".unity", ".asset", ".png", ".mat") \
                    and not os.path.exists(fp + ".meta"):
                missing_meta.append(rel)

    L = [f"[{os.path.basename(proj)}] 에셋 감사 — 스크립트 {n_cs}·씬 {n_scene}·프리팹 {n_prefab}"]
    if broken:
        L.append(f"  ⚠ 깨진 스크립트 참조 {len(broken)}개 (누락된 컴포넌트 — 프리팹/씬이 깨짐):")
        L += [f"      {b}" for b in broken[:15]]
        if len(broken) > 15:
            L.append(f"      …외 {len(broken) - 15}개")
    else:
        L.append("  ✅ 깨진 스크립트 참조 없음")
    if big_tex:
        L.append(f"  ⚠ 큰 텍스처 {len(big_tex)}개 (빌드 용량·메모리 — 임포트 설정 낮추기 검토):")
        L += [f"      {p} ({sz / 1048576:.1f}MB)" for p, sz in sorted(big_tex, key=lambda x: -x[1])[:10]]
    else:
        L.append(f"  ✅ {big_mb:.0f}MB↑ 텍스처 없음")
    if missing_meta:
        L.append(f"  ⚠ .meta 없는 파일 {len(missing_meta)}개 (유니티 밖에서 복사됨?): "
                 + ", ".join(m.rsplit("/", 1)[-1] for m in missing_meta[:8]))
    warns = len(broken) + len(big_tex) + (1 if missing_meta else 0)
    L.append(f"  → 문제 {warns}건" if warns else "  → 깨끗 ✅")
    return "\n".join(L)


# ── 씬/프리팹 구조 읽기 (유니티 안 띄움·읽기전용) ──────────────────
# 씬(.unity)·프리팹(.prefab)은 텍스트 YAML이라 파싱만으로 계층·컴포넌트가 나옵니다.
# 눈 없는 루시가 "씬에 뭐가 있는지"를 알고 스크립트를 짜게 하는 층입니다.
_DOC_RE = re.compile(r"^--- !u!(\d+) &(-?\d+)( stripped)?")
_GUID_RE = re.compile(r"guid:\s*([0-9a-f]{32})")
_FILEID_RE = re.compile(r"fileID:\s*(-?\d+)")

# 유니티 내장 컴포넌트의 클래스 ID → 이름(자주 나오는 것만; 모르면 C<번호>로 표기).
_CID_NAMES = {
    20: "Camera", 23: "MeshRenderer", 33: "MeshFilter", 50: "Rigidbody2D",
    54: "Rigidbody", 58: "CircleCollider2D", 60: "PolygonCollider2D",
    61: "BoxCollider2D", 64: "MeshCollider", 65: "BoxCollider",
    68: "EdgeCollider2D", 70: "CapsuleCollider2D", 81: "AudioListener",
    82: "AudioSource", 95: "Animator", 96: "TrailRenderer", 102: "TextMesh",
    108: "Light", 111: "Animation", 120: "LineRenderer", 135: "SphereCollider",
    136: "CapsuleCollider", 137: "SkinnedMeshRenderer", 143: "CharacterController",
    146: "WheelCollider", 154: "TerrainCollider", 198: "ParticleSystem",
    199: "ParticleSystemRenderer", 205: "LODGroup", 212: "SpriteRenderer",
    218: "Terrain", 223: "Canvas", 225: "CanvasGroup", 320: "PlayableDirector",
    329: "VideoPlayer",
}
_CID_SKIP = {4, 224, 222}        # Transform·RectTransform·CanvasRenderer — 전부 있어서 소음

_pkg_guid_cache = {}             # proj → {guid: 클래스이름} (패키지 캐시는 프로세스당 1회만 스캔)


def _meta_guid(meta_path):
    try:
        with open(meta_path, "r", encoding="utf-8", errors="replace") as f:
            head = f.read(600)
        m = re.search(r"^guid: ([0-9a-f]{32})", head, re.M)
        return m.group(1) if m else None
    except OSError:
        return None


def _script_guid_map(proj):
    """guid → C# 클래스 이름. Assets는 매번 새로 훑고(방금 만든 스크립트도 잡게),
    패키지 캐시(uGUI·TMP 등)는 크고 안 변하니 프로세스당 한 번만 훑습니다."""
    cached = _pkg_guid_cache.get(proj)
    if cached is None:
        cached = {}
        pkg = os.path.join(proj, "Library", "PackageCache")
        if os.path.isdir(pkg):
            for dp, _dirs, files in os.walk(pkg):
                for fn in files:
                    if fn.endswith(".cs.meta"):
                        g = _meta_guid(os.path.join(dp, fn))
                        if g:
                            cached[g] = fn[:-8]
        _pkg_guid_cache[proj] = cached
    out = dict(cached)
    for dp, _dirs, files in os.walk(os.path.join(proj, "Assets")):
        for fn in files:
            if fn.endswith(".cs.meta"):
                g = _meta_guid(os.path.join(dp, fn))
                if g:
                    out[g] = fn[:-8]
    return out


def _asset_guid_index(proj):
    """Assets의 모든 .meta에서 guid → 에셋 상대경로."""
    out = {}
    for dp, _dirs, files in os.walk(os.path.join(proj, "Assets")):
        for fn in files:
            if fn.endswith(".meta"):
                g = _meta_guid(os.path.join(dp, fn))
                if g:
                    out[g] = os.path.relpath(os.path.join(dp, fn[:-5]), proj).replace(os.sep, "/")
    return out


def _find_asset(proj, path, exts=None):
    """상대경로·파일명·이름만으로 프로젝트 안 에셋 파일 하나를 찾습니다 → (전체경로, 오류문)."""
    p = str(path or "").strip().strip('"\'')
    if not p:
        return None, "오류: 파일 경로(path)가 필요합니다."
    for cand in (os.path.join(proj, p), p):
        if os.path.isfile(cand):
            return cand, None
    low = p.lower().replace("\\", "/").lstrip("/")
    stem = os.path.splitext(os.path.basename(low))[0]
    hits = []
    for dp, _dirs, files in os.walk(os.path.join(proj, "Assets")):
        for fn in files:
            if fn.endswith(".meta"):
                continue
            fl = fn.lower()
            if exts and not fl.endswith(exts):
                continue
            rel = os.path.relpath(os.path.join(dp, fn), proj).replace(os.sep, "/")
            if rel.lower().endswith(low) or os.path.splitext(fn)[0].lower() == stem:
                hits.append(rel)
    if len(hits) == 1:
        return os.path.join(proj, hits[0]), None
    if not hits:
        return None, f"오류: '{p}'를 프로젝트에서 못 찾았습니다."
    return None, ("여러 개가 걸립니다 — path를 더 구체적으로 주세요:\n"
                  + "\n".join("  " + h for h in hits[:15]))


def scene_outline(config, project=None, path=None, limit=150):
    """씬·프리팹의 게임오브젝트 계층과 컴포넌트를 YAML 파싱으로 봅니다(유니티 안 띄움).
    path가 없으면 프로젝트의 씬·프리팹 목록을 돌려줍니다."""
    proj = resolve_project(config, project)
    if not proj or not os.path.isdir(proj):
        return f"오류: 유니티 프로젝트를 찾지 못했습니다: {project!r}"
    if not path:
        scenes, prefabs = [], []
        for dp, _dirs, files in os.walk(os.path.join(proj, "Assets")):
            for fn in files:
                rel = os.path.relpath(os.path.join(dp, fn), proj).replace(os.sep, "/")
                if fn.endswith(".unity"):
                    scenes.append(rel)
                elif fn.endswith(".prefab"):
                    prefabs.append(rel)
        L = [f"[{os.path.basename(proj)}] 씬 {len(scenes)}개 · 프리팹 {len(prefabs)}개"]
        L += ["  씬:"] + [f"    {s}" for s in sorted(scenes)[:30]]
        L += ["  프리팹:"] + [f"    {p}" for p in sorted(prefabs)[:40]]
        if len(prefabs) > 40:
            L.append(f"    …외 {len(prefabs) - 40}개")
        L.append("  (구조를 보려면 path에 씬/프리팹 경로를 주세요)")
        return "\n".join(L)

    full, err = _find_asset(proj, path, (".unity", ".prefab"))
    if err:
        return err
    rel = os.path.relpath(full, proj).replace(os.sep, "/")

    # 문서 단위로 필요한 필드만 줄 훑기로 뽑습니다(유니티 YAML은 태그 때문에 일반 파서가 못 읽음).
    docs, cur = [], None
    with open(full, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = _DOC_RE.match(line)
            if m:
                cur = {"cls": int(m.group(1)), "fid": m.group(2),
                       "stripped": bool(m.group(3))}
                docs.append(cur)
                continue
            if cur is None:
                continue
            s = line.strip()
            if "name" not in cur and s.startswith("m_Name:"):
                cur["name"] = s[7:].strip()
            elif "go" not in cur and s.startswith("m_GameObject:"):
                mm = _FILEID_RE.search(s)
                if mm:
                    cur["go"] = mm.group(1)
            elif "father" not in cur and (s.startswith("m_Father:")
                                          or s.startswith("m_TransformParent:")):
                mm = _FILEID_RE.search(s)
                if mm:
                    cur["father"] = mm.group(1)
            elif "guid" not in cur and (s.startswith("m_Script:")
                                        or s.startswith("m_SourcePrefab:")):
                mm = _GUID_RE.search(s)
                if mm:
                    cur["guid"] = mm.group(1)
            elif s == "propertyPath: m_Name":
                cur["_wait_name"] = True
            elif cur.pop("_wait_name", False) and s.startswith("value:"):
                cur.setdefault("mod_name", s[6:].strip())

    scripts = _script_guid_map(proj)
    gname, comps, tr, prefs = {}, {}, {}, []
    for d in docs:
        if d.get("stripped"):
            continue
        cls = d["cls"]
        if cls == 1:
            gname[d["fid"]] = d.get("name") or "(이름없음)"
        elif cls in (4, 224):
            if d.get("go"):
                tr[d["fid"]] = (d["go"], d.get("father", "0"))
        elif cls == 1001:
            prefs.append(d)
        elif d.get("go"):
            if cls == 114:
                label = scripts.get(d.get("guid"), "Script?")
            else:
                label = _CID_NAMES.get(cls, f"C{cls}")
            if cls not in _CID_SKIP:
                comps.setdefault(d["go"], []).append(label)

    guid_idx = None
    children = {}
    for fid, (go, father) in tr.items():
        children.setdefault(father, []).append(("t", fid))
    for d in prefs:
        nm = d.get("mod_name")
        if not nm:
            if guid_idx is None:
                guid_idx = _asset_guid_index(proj)
            src = guid_idx.get(d.get("guid"), "")
            nm = os.path.splitext(os.path.basename(src))[0] or "(프리팹)"
        children.setdefault(d.get("father", "0"), []).append(("p", nm))

    lines = []

    def _walk(key, depth):
        if len(lines) > limit:
            return
        for kind, v in children.get(key, []):
            if kind == "p":
                lines.append("  " * depth + f"{v}  (프리팹 인스턴스)")
                continue
            go, _f = tr[v]
            cs = comps.get(go, [])
            tag = ("  [" + ", ".join(cs[:8]) + ("…" if len(cs) > 8 else "") + "]") if cs else ""
            lines.append("  " * depth + gname.get(go, "?") + tag)
            _walk(v, depth + 1)

    _walk("0", 1)
    head = f"[{rel}] 게임오브젝트 {len(gname)}개" + (f" · 프리팹 인스턴스 {len(prefs)}개" if prefs else "")
    if len(lines) > limit:
        lines = lines[:limit] + [f"  …(길어서 {limit}줄에서 자름 — limit을 늘리면 더 봄)"]
    return head + "\n" + "\n".join(lines) if lines else head + "\n  (계층을 못 읽었습니다 — 바이너리 직렬화면 에디터에서 Force Text로 바꿔야 합니다)"


# ── 에셋 참조 추적 / 미사용 에셋 (guid 스캔·읽기전용) ───────────────
_SCAN_EXTS = (".unity", ".prefab", ".asset", ".mat", ".anim", ".controller",
              ".overridecontroller", ".physicmaterial", ".guiskin", ".fontsettings",
              ".playable", ".spriteatlas", ".asmdef", ".terrainlayer", ".mixer",
              ".preset", ".mask", ".shadergraph", ".vfx")
_UNUSED_EXTS = (".png", ".jpg", ".jpeg", ".tga", ".psd", ".exr", ".gif", ".bmp",
                ".wav", ".mp3", ".ogg", ".aif", ".aiff",
                ".fbx", ".obj", ".blend",
                ".mat", ".prefab", ".anim", ".controller", ".shader", ".physicmaterial")
_UNUSED_SKIP_DIRS = {"editor", "resources", "streamingassets", "plugins", "gizmos"}


def _scan_files(proj):
    """참조(guid)가 적혀 있을 수 있는 텍스트 에셋 파일들의 전체 경로."""
    out = []
    for dp, _dirs, files in os.walk(os.path.join(proj, "Assets")):
        for fn in files:
            if fn.lower().endswith(_SCAN_EXTS):
                out.append(os.path.join(dp, fn))
    ps = os.path.join(proj, "ProjectSettings")
    if os.path.isdir(ps):
        out += [os.path.join(ps, f) for f in os.listdir(ps) if f.endswith(".asset")]
    return out


def find_refs(config, project=None, asset=None):
    """asset을 주면 그 에셋(스크립트·텍스처·프리팹…)을 참조하는 씬·프리팹·머티리얼을 찾고,
    비우면 어디서도 참조 안 되는 '미사용 에셋 후보'를 보고합니다. 전부 읽기만 합니다."""
    proj = resolve_project(config, project)
    if not proj or not os.path.isdir(proj):
        return f"오류: 유니티 프로젝트를 찾지 못했습니다: {project!r}"

    if asset:
        full, err = _find_asset(proj, asset)
        if err:
            return err
        rel = os.path.relpath(full, proj).replace(os.sep, "/")
        guid = _meta_guid(full + ".meta")
        if not guid:
            return f"오류: {rel}의 .meta를 못 읽어 guid를 모릅니다(유니티가 아직 임포트 안 했을 수 있음)."
        hits = []
        own_meta = os.path.normcase(full + ".meta")
        targets = _scan_files(proj)
        for dp, _dirs, files in os.walk(os.path.join(proj, "Assets")):
            targets += [os.path.join(dp, f) for f in files if f.endswith(".meta")]
        for fp in targets:
            if os.path.normcase(fp) == own_meta or os.path.normcase(fp) == os.path.normcase(full):
                continue
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    if guid in f.read():
                        r = os.path.relpath(fp, proj).replace(os.sep, "/")
                        hits.append(r[:-5] if r.endswith(".meta") else r)
            except OSError:
                pass
        hits = sorted(set(hits))
        if not hits:
            return (f"[{rel}] 참조하는 곳을 못 찾았습니다(guid {guid[:8]}…).\n"
                    "⚠️코드에서 경로/이름으로 로드(Resources.Load 등)하는 건 못 잡습니다 — "
                    "지우기 전에 unity_find로 이름 검색도 해보세요.")
        L = [f"[{rel}] 참조하는 곳 {len(hits)}개:"] + [f"  {h}" for h in hits[:40]]
        if len(hits) > 40:
            L.append(f"  …외 {len(hits) - 40}개")
        return "\n".join(L)

    # 미사용 에셋 후보 — 텍스트 에셋·메타에 적힌 모든 guid를 모아 '참조된 집합'을 만들고 비교.
    referenced = set()
    for fp in _scan_files(proj):
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                referenced.update(_GUID_RE.findall(f.read()))
        except OSError:
            pass
    for dp, _dirs, files in os.walk(os.path.join(proj, "Assets")):
        for fn in files:
            if not fn.endswith(".meta"):
                continue
            try:
                with open(os.path.join(dp, fn), "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError:
                continue
            own = re.search(r"^guid: ([0-9a-f]{32})", text, re.M)
            own = own.group(1) if own else None
            referenced.update(g for g in _GUID_RE.findall(text) if g != own)

    unused, n_checked = [], 0
    for dp, _dirs, files in os.walk(os.path.join(proj, "Assets")):
        parts = {p.lower() for p in os.path.relpath(dp, proj).split(os.sep)}
        if parts & _UNUSED_SKIP_DIRS:
            continue
        for fn in files:
            if not fn.lower().endswith(_UNUSED_EXTS):
                continue
            fp = os.path.join(dp, fn)
            g = _meta_guid(fp + ".meta")
            if not g:
                continue
            n_checked += 1
            if g not in referenced:
                try:
                    unused.append((os.path.relpath(fp, proj).replace(os.sep, "/"),
                                   os.path.getsize(fp)))
                except OSError:
                    pass
    if not unused:
        return (f"[{os.path.basename(proj)}] 검사한 에셋 {n_checked}개 — 미사용 후보 없음 ✅ "
                "(Editor·Resources·StreamingAssets·Plugins는 제외)")
    unused.sort(key=lambda x: -x[1])
    total = sum(sz for _p, sz in unused)
    L = [f"[{os.path.basename(proj)}] 미사용 에셋 후보 {len(unused)}개 · 합계 {total / 1048576:.1f}MB "
         f"(검사 {n_checked}개):"]
    L += [f"  {p} ({sz / 1024:.0f}KB)" for p, sz in unused[:30]]
    if len(unused) > 30:
        L.append(f"  …외 {len(unused) - 30}개")
    L.append("⚠️'후보'입니다 — 코드에서 이름/경로로 로드하는 것(Resources.Load·Addressables)은 "
             "참조로 안 잡힙니다. 지우기 전 unity_find로 파일명을 검색해 확인하세요.")
    return "\n".join(L)


# ── 프로젝트 설정 요약 (읽기전용) ───────────────────────────────────
def _ps_text(proj):
    p = os.path.join(proj, "ProjectSettings", "ProjectSettings.asset")
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def settings_summary(config, project=None):
    """제품명·버전·번들ID·에디터 버전·빌드 씬·define 심볼·패키지를 한눈에(읽기전용)."""
    proj = resolve_project(config, project)
    if not proj or not os.path.isdir(proj):
        return f"오류: 유니티 프로젝트를 찾지 못했습니다: {project!r}"
    import portable
    L = [f"[{os.path.basename(proj)}] 프로젝트 설정"]
    ver = portable.project_unity_version(proj)
    if ver:
        L.append(f"  에디터 버전: {ver}")
    ps = _ps_text(proj)
    if "productName" not in ps:
        L.append("  ⚠ ProjectSettings.asset이 텍스트가 아니라(바이너리 직렬화) 상세를 못 읽습니다.")
    else:
        def g(key):
            m = re.search(rf"^\s*{key}: (.*)$", ps, re.M)
            return m.group(1).strip() or "(비어 있음)" if m else "?"
        L.append(f"  제품: {g('productName')} (회사: {g('companyName')})")
        L.append(f"  버전: {g('bundleVersion')} · 안드로이드 버전코드 {g('AndroidBundleVersionCode')}")
        m = re.search(r"applicationIdentifier:\n((?:\s+\w+: \S+\n)+)", ps)
        if m:
            ids = ", ".join(x.strip() for x in m.group(1).strip().splitlines())
            L.append(f"  번들 ID: {ids}")
        m = re.search(r"scriptingDefineSymbols:\n((?:\s+\w+: .*\n)+)", ps)
        if m:
            syms = [x.strip() for x in m.group(1).strip().splitlines() if x.split(":", 1)[1].strip()]
            if syms:
                L.append("  define 심볼: " + " · ".join(syms[:6]))
    ebs = os.path.join(proj, "ProjectSettings", "EditorBuildSettings.asset")
    try:
        with open(ebs, "r", encoding="utf-8", errors="replace") as f:
            pairs = re.findall(r"- enabled: (\d)\s*\n\s*path: (.+)", f.read())
        if pairs:
            L.append(f"  빌드 씬 {sum(1 for e, _p in pairs if e == '1')}개 켜짐 / 목록 {len(pairs)}개:")
            L += [f"    {'✅' if e == '1' else '⬜'} {p.strip()}" for e, p in pairs[:20]]
    except OSError:
        pass
    mf = os.path.join(proj, "Packages", "manifest.json")
    try:
        with open(mf, "r", encoding="utf-8") as f:
            deps = (json.load(f).get("dependencies") or {})
        keep = [f"{k.replace('com.unity.', 'u.')} {v}" for k, v in sorted(deps.items())
                if not str(v).startswith("file:")][:12]
        L.append(f"  패키지 {len(deps)}개: " + ", ".join(keep) + ("…" if len(deps) > 12 else ""))
    except (OSError, ValueError):
        pass
    return "\n".join(L)


# ── 런타임 예외 로그 분석 (읽기전용) ────────────────────────────────
# unity_status는 '컴파일' 에러만 봅니다. 이건 게임을 돌리다 난 **런타임 예외**
# (NullReference 등)를 Editor.log(에디터 플레이)나 Player.log(빌드된 게임)에서 집계합니다.
_EXC_RE = re.compile(r"^[A-Za-z_][\w.`]*Exception(?:: .*)?$")
_FRAME_RE = re.compile(r"^[\w`.+<>\[\],]+(?:\.[\w`.+<>\[\],]+)+\s*\(")


def game_log(config, project=None, source="editor", tail_kb=512):
    src = (source or "editor").strip().lower()
    if src.startswith("p"):
        proj = resolve_project(config, project)
        if not proj:
            return "오류: player 로그를 보려면 project(별칭·경로)가 필요합니다(회사·제품명을 설정에서 읽음)."
        ps = _ps_text(proj)
        comp = re.search(r"^\s*companyName: (.*)$", ps, re.M)
        prod = re.search(r"^\s*productName: (.*)$", ps, re.M)
        if not (comp and prod):
            return "오류: ProjectSettings에서 회사·제품명을 못 읽어 Player.log 위치를 모릅니다."
        base = os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "LocalLow",
                            comp.group(1).strip(), prod.group(1).strip())
        path = next((os.path.join(base, f) for f in ("Player.log", "Player-prev.log")
                     if os.path.isfile(os.path.join(base, f))), None)
        if not path:
            return f"Player.log가 없습니다: {base} — 이 PC에서 빌드된 게임을 돌린 적이 있어야 생깁니다."
        label = "Player.log(빌드된 게임)"
    else:
        path = editor_log_path(config)
        if not os.path.isfile(path):
            return f"오류: Editor.log를 찾지 못했습니다: {path}"
        label = "Editor.log(에디터)"

    size = os.path.getsize(path)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        if size > tail_kb * 1024:
            f.seek(size - tail_kb * 1024)
        lines = f.read().splitlines()

    groups = {}                                   # 메시지 → {"n": 횟수, "frames": [스택]}
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        if _EXC_RE.match(ln) or ln.startswith("Assertion failed"):
            frames = []
            j = i + 1
            while j < len(lines) and len(frames) < 25:
                fl = lines[j].rstrip()
                if " (at " in fl or fl.startswith("  at ") or _FRAME_RE.match(fl.strip()):
                    frames.append(fl.strip())
                    j += 1
                else:
                    break
            g = groups.setdefault(ln, {"n": 0, "frames": frames})
            g["n"] += 1
            if not g["frames"]:
                g["frames"] = frames
            i = j
        else:
            i += 1

    import datetime
    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%m-%d %H:%M")
    head = f"[{label} · 마지막 갱신 {mtime} · 꼬리 {min(size, tail_kb * 1024) // 1024}KB]"
    if not groups:
        return head + "\n런타임 예외 없음 ✅ (컴파일 에러는 unity_status/unity_run이 따로 봅니다)"
    total = sum(g["n"] for g in groups.values())
    L = [head, f"런타임 예외 {len(groups)}종 · 총 {total}회:"]
    for msg, g in sorted(groups.items(), key=lambda kv: -kv[1]["n"])[:10]:
        L.append(f"  ✗ {g['n']}회 · {msg[:160]}")
        best = [f for f in g["frames"] if "Assets/" in f.replace("\\", "/")] or g["frames"]
        for fr in best[:2]:
            L.append(f"      ↳ {fr[:150]}")
    if len(groups) > 10:
        L.append(f"  …외 {len(groups) - 10}종")
    L.append("(줄번호가 있는 Assets/ 스택 프레임부터 고치면 됩니다 — unity_find로 그 지점을 확인하세요)")
    return "\n".join(L)


# ── C# 구조 개요 (읽기전용) ─────────────────────────────────────────
# unity_find는 '낱말 검색'(grep), 이건 '뼈대 보기' — 파일의 클래스·메서드·직렬화 필드를
# 개요로 뽑아, 작은 두뇌가 파일 전체를 안 읽고도 코드 구조를 파악하게 합니다.
_TYPE_RE = re.compile(
    r"^(?:(?:public|private|protected|internal|static|abstract|sealed|partial)\s+)*"
    r"(class|struct|interface|enum)\s+(\w+)(?:\s*:\s*([^{/]+?))?\s*(?:\{|$)")
_KW = {"if", "for", "foreach", "while", "switch", "catch", "using", "lock",
       "return", "new", "else", "throw", "await", "yield", "base", "this", "in", "out", "var"}
_METH_RE = re.compile(
    r"^((?:(?:public|private|protected|internal|static|override|virtual|abstract|"
    r"async|sealed|new|partial|extern|unsafe)\s+)*)"
    r"([\w.<>\[\],? ]+?)\s+(\w+)\s*\(([^)]*)\)\s*(?:\{|=>|$|where )")
_FIELD_RE = re.compile(
    r"^(?:\[SerializeField\]\s*)?(?:public|(?:\[SerializeField\]\s*)?private|protected|internal)"
    r"[\w.<>\[\],? ]*?\s+(\w+)\s*(?:=[^;]*)?;")


def _outline_file(full):
    """한 .cs 파일의 (타입들, 메서드들, 직렬화필드들)."""
    types, meths, fields = [], [], []
    prev_attr = False
    try:
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                s = raw.strip()
                if not s or s.startswith("//") or s.startswith("*") or s.startswith("/*"):
                    continue
                m = _TYPE_RE.match(s)
                if m:
                    kind, name, base = m.group(1), m.group(2), (m.group(3) or "").strip()
                    types.append(f"{kind} {name}" + (f" : {base}" if base else ""))
                    prev_attr = False
                    continue
                m = _METH_RE.match(s)
                if m and m.group(3) not in _KW and m.group(2).split()[-1] not in _KW \
                        and not s.endswith(";"):
                    args = " ".join(m.group(4).split())
                    meths.append(f"{m.group(3)}({args[:60] + ('…' if len(args) > 60 else '')})")
                    prev_attr = False
                    continue
                if "(" not in s and (s.startswith("public ") or "[SerializeField]" in s or prev_attr):
                    fm = _FIELD_RE.match(s) or (re.match(r"^[\w.<>\[\],? ]+?\s+(\w+)\s*(?:=[^;]*)?;", s)
                                                if prev_attr else None)
                    if fm and fm.group(1) not in _KW:
                        fields.append(fm.group(1))
                prev_attr = s == "[SerializeField]"
    except OSError:
        pass
    return types, meths, fields


def code_outline(config, project=None, path=None, limit=150):
    """path를 주면 그 .cs의 클래스·메서드·직렬화 필드 개요, 없으면 프로젝트 전체 파일별 요약."""
    proj = resolve_project(config, project)
    if not proj or not os.path.isdir(proj):
        return f"오류: 유니티 프로젝트를 찾지 못했습니다: {project!r}"
    if path:
        full, err = _find_asset(proj, path, (".cs",))
        if err:
            return err
        rel = os.path.relpath(full, proj).replace(os.sep, "/")
        types, meths, fields = _outline_file(full)
        L = [f"[{rel}]"]
        L += [f"  {t}" for t in types] or ["  (타입 선언을 못 찾음)"]
        if fields:
            L.append("    직렬화/공개 필드: " + ", ".join(dict.fromkeys(fields))[:300])
        if meths:
            L.append("    메서드 " + str(len(meths)) + "개: " + ", ".join(meths[:40]))
        L.append("(개요입니다 — 본문은 read_document로, 낱말 위치는 unity_find로 보세요)")
        return "\n".join(L)

    rows, n = [], 0
    for dp, _dirs, files in os.walk(os.path.join(proj, "Assets")):
        for fn in sorted(files):
            if not fn.endswith(".cs"):
                continue
            n += 1
            if len(rows) >= limit:
                continue
            fullp = os.path.join(dp, fn)
            types, meths, fields = _outline_file(fullp)
            rel = os.path.relpath(fullp, proj).replace(os.sep, "/")
            tdesc = "; ".join(types[:2]) or "(타입 없음)"
            rows.append(f"  {rel} — {tdesc} (메서드 {len(meths)}·필드 {len(fields)})")
    head = f"[{os.path.basename(proj)}] C# {n}개 파일 개요:"
    if n > len(rows):
        rows.append(f"  …외 {n - len(rows)}개 (limit을 늘리거나 path로 하나씩 보세요)")
    return head + "\n" + "\n".join(rows)


# ── 공용: 루시 메모리 폴더 (스냅샷·빌드 기록 저장소) ────────────────
def _mem_dir(*sub):
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory", *sub)
    os.makedirs(d, exist_ok=True)
    return d


def _proj_key(proj):
    return os.path.basename(os.path.normpath(proj)).lower()


# ── 작업 대상 프로젝트 건강 감시 (새벽 일과 + 아침 브리핑 한 줄) ────
# doctor 9종은 전부 '루시 자기 인프라'만 봅니다. 정작 사용자가 작업 중인 유니티 프로젝트가
# 컴파일도 안 되는 상태는 아무도 안 봤습니다(세션63: saladfarm의 MCP 패키지가 CS0115로 깨져
# 배치 작업이 전멸했는데 루시는 몰랐음). 그래서 새벽에 프로젝트마다 한 번씩 확인해 둡니다.
#
# 확인 방법은 두 겹입니다:
#   ① 정밀 — 배치모드로 열고 닫기(run_batch, method 없음). 진짜 컴파일 결과라 확실합니다.
#   ② 정적 — 에디터가 그 프로젝트를 열고 있어 ①이 불가능할 때(Temp/UnityLockfile).
#      최신 .cs mtime vs Library/ScriptAssemblies의 최신 .dll mtime을 견줍니다. 코드가 더
#      새것이면 '컴파일 결과가 코드보다 오래됨'(에러이거나 아직 컴파일 전)으로 봅니다.
# ⚠️Editor.log(read_status)는 쓰지 않습니다 — PC에 하나뿐인 전역 로그라 어느 프로젝트의
#   상태인지 알 수 없습니다(실측: 로그가 D:\test\My project 것이었음).
HEALTH_FILE = "unity_health.json"


def _newest(root, exts, skip=("Library", "Temp", "Obj", "Build", "Logs", ".git")):
    """root 아래에서 가장 최근에 바뀐 파일의 (mtime, 상대경로). 없으면 (0, "")."""
    best, best_path = 0.0, ""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for name in filenames:
            if not name.lower().endswith(exts):
                continue
            full = os.path.join(dirpath, name)
            try:
                m = os.path.getmtime(full)
            except OSError:
                continue
            if m > best:
                best, best_path = m, os.path.relpath(full, root)
    return best, best_path


def _health_static(proj):
    """에디터가 열려 있어 배치를 못 돌릴 때의 대타 — 컴파일 결과가 코드보다 오래됐는지만."""
    asm = os.path.join(proj, "Library", "ScriptAssemblies")
    if not os.path.isdir(asm):
        return "unknown", "아직 한 번도 컴파일된 적이 없는 것 같습니다(ScriptAssemblies 없음)."
    cs_m, cs_path = _newest(os.path.join(proj, "Assets"), (".cs",))
    pkg = os.path.join(proj, "Packages")
    if os.path.isdir(pkg):                       # 로컬 패키지 코드도 컴파일 대상입니다
        p_m, p_path = _newest(pkg, (".cs",))
        if p_m > cs_m:
            cs_m, cs_path = p_m, os.path.join("Packages", p_path)
    dll_m, _ = _newest(asm, (".dll",), skip=())
    if not cs_m:
        return "unknown", "C# 파일을 찾지 못했습니다."
    if cs_m > dll_m + 5:                         # 5초는 같은 컴파일 안에서의 시각 흔들림 여유
        import datetime as _dt
        when = _dt.datetime.fromtimestamp(cs_m).strftime("%m-%d %H:%M")
        return "stale", (f"코드가 마지막 컴파일 결과보다 새것입니다({cs_path}, {when}) — "
                         "컴파일 에러이거나 아직 컴파일 전일 수 있습니다.")
    return "ok", "컴파일 결과가 코드보다 새것입니다(정적 점검 통과)."


def health(config, projects=None, timeout=900, notify=None, save=True):
    """등록된 유니티 프로젝트들이 지금 컴파일 되는 상태인지 확인합니다.
    돌려주는 값: (사람이 읽을 요약문, 프로젝트별 결과 리스트)."""
    say = notify or (lambda _m: None)
    reg = _cfg(config).get("projects", {}) or {}
    if projects:
        wanted = [(str(p), resolve_project(config, p)) for p in projects]
    else:
        # 같은 폴더를 가리키는 별칭(saladfarm·dietcreature)은 한 번만 봅니다.
        # health_skip에 적힌 프로젝트는 자동 감시에서 뺍니다 — 더 개발하지 않는 프로젝트의
        # 컴파일 에러를 매일 아침 브리핑에서 읊으면 경보만 무뎌집니다(사용자 결정으로 뺌).
        # ⚠️별칭 자체는 config에 남아 있어 "샐러드팜 점검해줘"라고 직접 시키면 그대로 됩니다.
        skip = {str(s).strip().lower() for s in (_cfg(config).get("health_skip") or [])}
        seen, wanted = {}, []
        for name, raw in reg.items():
            import portable
            if name.strip().lower() in skip:
                continue
            path = portable.expand(raw)
            key = os.path.normcase(os.path.normpath(path or ""))
            if not path or key in seen:
                continue
            seen[key] = name
            wanted.append((name, path))
    if not wanted:
        return "등록된 유니티 프로젝트가 없습니다(config unity.projects).", []

    results = []
    for name, proj in wanted:
        if not proj or not os.path.isdir(os.path.join(proj or "", "Assets")):
            results.append({"name": name, "path": proj or "", "state": "unknown",
                            "detail": "프로젝트 폴더를 찾지 못했습니다.", "errors": []})
            continue
        if os.path.exists(os.path.join(proj, "Temp", "UnityLockfile")):
            state, detail = _health_static(proj)
            detail = "에디터가 열려 있어 정적 점검만 했습니다. " + detail
            results.append({"name": name, "path": proj, "state": state,
                            "detail": detail, "errors": []})
            say(f"  [{name}] 에디터 열림 → 정적 점검: {state}")
            continue
        say(f"  [{name}] 배치모드 컴파일 점검…")
        text = run_batch(config, project=proj, timeout=timeout)
        errors, _warnings = _parse_compile(text)
        if "컴파일 에러 없음" in text:
            state, detail = "ok", "컴파일 에러 없음."
        elif errors:
            state, detail = "error", f"컴파일 에러 {len(errors)}개."
        else:
            state, detail = "unknown", text.splitlines()[0] if text else "결과를 읽지 못했습니다."
        results.append({"name": name, "path": proj, "state": state,
                        "detail": detail, "errors": errors[:10]})
        say(f"  [{name}] {state}: {detail}")

    if save:
        import datetime as _dt
        import json as _json
        try:
            with open(os.path.join(_mem_dir(), HEALTH_FILE), "w", encoding="utf-8") as f:
                _json.dump({"at": _dt.datetime.now().isoformat(timespec="seconds"),
                            "projects": results}, f, ensure_ascii=False, indent=1)
        except OSError:
            pass

    mark = {"ok": "✅", "error": "✗", "stale": "⚠", "unknown": "?"}
    lines = [f"{mark.get(r['state'], '?')} {r['name']}: {r['detail']}" for r in results]
    for r in results:
        for e in r["errors"][:5]:
            lines.append(f"    ✗ {e}")
    return "[작업 프로젝트 건강 점검]\n" + "\n".join(lines), results


def health_line(max_age_hours=36):
    """아침 브리핑용 한 줄 — 새벽에 적어둔 결과를 읽습니다(브리핑이 유니티를 켜지 않게).
    결과가 없거나 오래됐으면 빈 문자열(브리핑은 그 줄을 통째로 건너뜁니다)."""
    import datetime as _dt
    import json as _json
    path = os.path.join(_mem_dir(), HEALTH_FILE)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = _json.load(f)
        at = _dt.datetime.fromisoformat(data["at"])
    except (OSError, ValueError, KeyError):
        return ""
    if (_dt.datetime.now() - at).total_seconds() > max_age_hours * 3600:
        return ""
    bad = [p for p in data.get("projects", []) if p.get("state") in ("error", "stale")]
    if not bad:
        names = ", ".join(p["name"] for p in data.get("projects", []))
        return f"{names}: 컴파일 문제 없음" if names else ""
    return " / ".join(f"{p['name']}: {p.get('detail', '문제 있음')}" for p in bad)


# ── 빌드 용량 리포트 (읽기전용) ─────────────────────────────────────
# 유니티는 빌드 끝에 로그로 '카테고리별 크기 + 큰 에셋 순위'를 남깁니다.
# unity_build(run_batch의 method 실행)가 로그 사본을 memory/에 남기므로 그걸 파싱하고,
# 에디터 GUI 빌드는 Editor.log에서 찾습니다(에디터 재시작 시 지워지는 한계는 안내).
_CAT_RE = re.compile(r"^([A-Za-z][\w /&.-]*?)\s+([\d.]+\s*[kmg]b)\s+([\d.]+)%", re.M)
_TOPASSET_RE = re.compile(r"^\s*([\d.]+\s*[kmg]b)\s+([\d.]+)%\s+(.+?)\s*$")
_SIZE_RE = re.compile(r"([\d.]+)\s*([kmg]b)", re.I)


def _mb(txt):
    m = _SIZE_RE.search(str(txt))
    if not m:
        return 0.0
    v, u = float(m.group(1)), m.group(2).lower()
    return v / 1024 if u == "kb" else v * 1024 if u == "gb" else v


def _parse_build_report(text):
    """로그에서 마지막 빌드 리포트를 뽑아 dict로. 없으면 None."""
    idx = text.rfind("Uncompressed usage by category")
    if idx < 0:
        return None
    seg = text[idx:idx + 40000]
    cats = {}
    for line in seg.splitlines()[1:]:
        if not line.strip() or line.strip().startswith("---"):
            if cats:
                break
            continue
        m = _CAT_RE.match(line)
        if m:
            name = m.group(1).strip()
            if not name.lower().startswith("total"):   # 합계줄은 카테고리가 아님
                cats[name] = _mb(m.group(2))
        elif "Complete build size" in line or "sorted by" in line:
            break
    m = re.search(r"Complete build size\s+([\d.]+\s*[kmg]b)", seg)
    total = _mb(m.group(1)) if m else None
    top = []
    p = seg.find("sorted by uncompressed size")
    if p >= 0:
        for line in seg[p:].splitlines()[1:250]:
            if line.strip().startswith("---"):
                break
            m = _TOPASSET_RE.match(line)
            if m and "%" not in m.group(3):
                top.append((_mb(m.group(1)), m.group(3)))
    return {"cats": cats, "total": total, "top": top}


def build_report(config, project=None):
    proj = resolve_project(config, project)
    if not proj or not os.path.isdir(proj):
        return f"오류: 유니티 프로젝트를 찾지 못했습니다: {project!r}"
    key = _proj_key(proj)
    cand = [os.path.join(_mem_dir(), f"unity_lastbuild_{key}.log"),
            editor_log_path(config),
            editor_log_path(config).replace("Editor.log", "Editor-prev.log")]
    best = None                                    # (mtime, 경로, 리포트)
    for p in cand:
        if not os.path.isfile(p):
            continue
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                rep = _parse_build_report(f.read())
        except OSError:
            continue
        if rep and (best is None or os.path.getmtime(p) > best[0]):
            best = (os.path.getmtime(p), p, rep)
    if not best:
        return ("빌드 리포트를 못 찾았습니다 — 아직 이 PC에서 빌드 기록이 없거나 에디터를 재시작해 "
                "Editor.log가 지워졌습니다. unity_build로 빌드하면 리포트가 자동 저장돼 다음부터는 "
                "언제든 볼 수 있습니다.")
    mtime, src, rep = best
    import datetime
    when = datetime.datetime.fromtimestamp(mtime).strftime("%m-%d %H:%M")

    # 이력에 쌓아 직전 빌드와 비교(같은 빌드를 다시 읽으면 중복 저장 안 함).
    hist_path = os.path.join(_mem_dir(), "unity_build_history.json")
    try:
        with open(hist_path, "r", encoding="utf-8") as f:
            hist = json.load(f)
    except (OSError, ValueError):
        hist = {}
    runs = hist.setdefault(key, [])
    entry = {"ts": round(mtime), "total": rep["total"], "cats": rep["cats"]}
    prev = None
    if runs and runs[-1].get("ts") == entry["ts"]:
        prev = runs[-2] if len(runs) > 1 else None
    else:
        prev = runs[-1] if runs else None
        runs.append(entry)
        hist[key] = runs[-10:]
        try:
            with open(hist_path, "w", encoding="utf-8") as f:
                json.dump(hist, f, ensure_ascii=False)
        except OSError:
            pass

    L = [f"[{key} 빌드 리포트 · {when} · 출처 {os.path.basename(src)}]"]
    if rep["total"] is not None:
        d = ""
        if prev and prev.get("total") is not None:
            diff = rep["total"] - prev["total"]
            d = f" ({'+' if diff >= 0 else ''}{diff:.1f}MB, 직전 빌드 대비)"
        L.append(f"  전체 크기: {rep['total']:.1f}MB{d}")
        # 판단력 2층: 크기를 예산과 대조(기준 근거는 knowledge/unity_모바일_기준표.md,
        # 변경은 config unity.budgets.apk_mb — 기본 150=플레이스토어 한도 전 여유선).
        cap = int((config.get("unity", {}).get("budgets", {}) or {}).get("apk_mb", 150))
        if rep["total"] > cap:
            L.append(f"  📏 빌드 {rep['total']:.0f}MB — 모바일 기준({cap}MB) 초과: "
                     "큰 에셋 상위부터 unity_tex_fix/unity_audit로 다이어트 권장")
    if rep["cats"]:
        L.append("  카테고리별(비압축):")
        for name, mb in sorted(rep["cats"].items(), key=lambda x: -x[1])[:10]:
            d = ""
            if prev and name in (prev.get("cats") or {}):
                dv = mb - prev["cats"][name]
                if abs(dv) >= 0.1:
                    d = f"  ({'+' if dv >= 0 else ''}{dv:.1f}MB)"
            L.append(f"    {name:<22} {mb:8.1f}MB{d}")
    if rep["top"]:
        L.append("  큰 에셋 상위:")
        L += [f"    {mb:7.1f}MB  {p}" for mb, p in rep["top"][:12]]
    if len(runs) >= 2:
        L.append(f"  (이력 {len(runs)}회 저장 — 빌드할 때마다 증감을 추적합니다)")
    return "\n".join(L)


# ── 씬/프리팹/에셋 기계적 수정 (자동 백업 + 확인) ───────────────────
_EDIT_EXTS = (".unity", ".prefab", ".asset", ".mat", ".anim", ".controller",
              ".asmdef", ".json", ".txt")


def yaml_edit(config, project, path, find, replace, replace_all=False):
    """유니티 텍스트 에셋에서 find→replace. 원본은 memory/unity_snapshots/<proj>/edits/에
    백업한 뒤에만 손댑니다. (확인은 tools.py 래퍼에서 받음)"""
    proj = resolve_project(config, project)
    if not proj or not os.path.isdir(proj):
        return f"오류: 유니티 프로젝트를 찾지 못했습니다: {project!r}"
    full, err = _find_asset(proj, path, _EDIT_EXTS)
    if err:
        return err
    rel = os.path.relpath(full, proj).replace(os.sep, "/")
    if os.path.getsize(full) > 20 * 1024 * 1024:
        return f"오류: {rel}은 20MB가 넘어 이 도구로 안 고칩니다."
    find, replace = str(find or ""), str(replace or "")
    if not find:
        return "오류: 찾을 문구(find)가 필요합니다."
    with open(full, "rb") as f:
        text = f.read().decode("utf-8", "surrogateescape")
    n = text.count(find)
    if n == 0:
        return (f"'{find[:60]}'을(를) {rel}에서 못 찾았습니다 — 파일에 실제로 있는 그대로 넣어야 "
                "합니다. read_file로 원문을 확인하세요.")
    if n > 1 and not replace_all:
        return (f"'{find[:60]}'이(가) {rel}에 {n}곳 있습니다 — 앞뒤를 더 붙여 한 곳으로 좁히거나, "
                "전부 바꿀 거면 all=true를 주세요.")
    ts = time.strftime("%Y%m%d_%H%M%S")
    bdir = _mem_dir("unity_snapshots", _proj_key(proj), "edits", ts)
    bpath = os.path.join(bdir, rel.replace("/", "_"))
    import shutil
    shutil.copyfile(full, bpath)
    with open(full, "wb") as f:
        f.write(text.replace(find, replace).encode("utf-8", "surrogateescape"))
    return (f"{rel}에서 {n}곳 바꿨습니다(원본 백업: memory/unity_snapshots/…/edits/{ts}).\n"
            "⚠️에디터가 이 씬/에셋을 열고 있었다면 에디터 쪽 저장이 이 수정을 덮어쓸 수 있습니다 — "
            "에디터에서 다시 열어 확인하세요. 검증은 unity_scene/unity_run.")


# ── 스냅샷 찍기/목록/복원 ───────────────────────────────────────────
_SNAP_EXTS = (".unity", ".prefab", ".asset", ".mat", ".anim", ".controller")
_TS_RE = re.compile(r"^\d{8}_\d{6}(_\d+)?$")


def _snap_take(proj, root):
    # 같은 초에 두 번 찍혀도(복원 직전 자동 백업 등) 기존 스냅샷을 덮치지 않게 유일한 폴더명.
    ts = time.strftime("%Y%m%d_%H%M%S")
    dst_root = os.path.join(root, ts)
    i = 1
    while os.path.exists(dst_root):
        i += 1
        dst_root = os.path.join(root, f"{ts}_{i}")
    ts = os.path.basename(dst_root)
    import shutil
    n = size = skipped = 0
    files = []
    for dp, _dirs, fns in os.walk(os.path.join(proj, "Assets")):
        for fn in fns:
            if fn.lower().endswith(_SNAP_EXTS):
                fp = os.path.join(dp, fn)
                files.append(fp)
                if os.path.isfile(fp + ".meta"):
                    files.append(fp + ".meta")
    ps = os.path.join(proj, "ProjectSettings")
    if os.path.isdir(ps):
        files += [os.path.join(ps, f) for f in os.listdir(ps)
                  if f.endswith(".asset") or f == "ProjectVersion.txt"]
    mf = os.path.join(proj, "Packages", "manifest.json")
    if os.path.isfile(mf):
        files.append(mf)
    for fp in files:
        try:
            sz = os.path.getsize(fp)
            if sz > 10 * 1024 * 1024:              # 라이트맵 데이터 같은 거대 .asset은 건너뜀
                skipped += 1
                continue
            rel = os.path.relpath(fp, proj)
            dst = os.path.join(dst_root, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(fp, dst)
            n += 1
            size += sz
        except OSError:
            skipped += 1
    # 오래된 스냅샷 정리(최근 15개만; edits 폴더는 안 건드림).
    snaps = sorted(d for d in os.listdir(root) if _TS_RE.match(d))
    for old in snaps[:-15]:
        try:
            shutil.rmtree(os.path.join(root, old))
        except OSError:
            pass
    return ts, n, size, skipped


def _snap_pick(root, snap_id):
    snaps = sorted((d for d in os.listdir(root) if _TS_RE.match(d)), reverse=True)
    if not snaps:
        return None, "스냅샷이 없습니다 — 먼저 unity_snapshot(action=take)으로 찍으세요."
    if not snap_id or str(snap_id).strip() in ("최신", "latest"):
        return snaps[0], None
    sid = str(snap_id).strip()
    hit = [s for s in snaps if s == sid] or [s for s in snaps if s.startswith(sid)]
    if len(hit) == 1:
        return hit[0], None
    return None, (f"스냅샷 '{sid}'을 못 고르겠습니다. 있는 것: " + ", ".join(snaps[:10]))


def snapshot(config, project=None, action="take", snap_id=None, file=None):
    proj = resolve_project(config, project)
    if not proj or not os.path.isdir(proj):
        return f"오류: 유니티 프로젝트를 찾지 못했습니다: {project!r}"
    root = _mem_dir("unity_snapshots", _proj_key(proj))
    act = (action or "take").strip().lower()

    if act == "take":
        ts, n, size, skipped = _snap_take(proj, root)
        return (f"스냅샷 {ts} 저장: 씬·프리팹·에셋·설정 {n}개 파일 · {size / 1048576:.1f}MB"
                + (f" (10MB 초과 등 {skipped}개 건너뜀)" if skipped else "")
                + "\n되돌리기: unity_snapshot(action=restore, id=최신 또는 시각)")

    if act == "list":
        snaps = sorted((d for d in os.listdir(root) if _TS_RE.match(d)), reverse=True)
        if not snaps:
            return "스냅샷이 없습니다 — unity_snapshot(action=take)으로 찍으세요."
        L = [f"[{_proj_key(proj)}] 스냅샷 {len(snaps)}개(최신순):"]
        for s in snaps[:15]:
            n = size = 0
            for dp, _d, fns in os.walk(os.path.join(root, s)):
                for fn in fns:
                    n += 1
                    try:
                        size += os.path.getsize(os.path.join(dp, fn))
                    except OSError:
                        pass
            L.append(f"  {s} — 파일 {n}개 · {size / 1048576:.1f}MB")
        return "\n".join(L)

    if act == "restore":
        sid, err = _snap_pick(root, snap_id)
        if err:
            return err
        # 복원도 사고일 수 있으니, 되돌리기 전 현재 상태부터 자동 백업.
        safety, _n, _s, _k = _snap_take(proj, root)
        src_root = os.path.join(root, sid)
        import shutil
        n = 0
        flt = str(file or "").strip().lower().replace("\\", "/")
        for dp, _dirs, fns in os.walk(src_root):
            for fn in fns:
                sp = os.path.join(dp, fn)
                rel = os.path.relpath(sp, src_root)
                if flt and flt not in rel.replace(os.sep, "/").lower():
                    continue
                dst = os.path.join(proj, rel)
                try:
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copyfile(sp, dst)
                    n += 1
                except OSError:
                    pass
        what = f"'{file}' 관련 {n}개" if flt else f"{n}개"
        return (f"스냅샷 {sid}에서 파일 {what}를 되돌렸습니다"
                f"(복원 직전 상태는 {safety}에 자동 백업 — 후회하면 그걸로 다시 복원).\n"
                "⚠️스냅샷 이후 '새로 만든' 파일은 지우지 않으며, 에디터가 켜져 있었다면 "
                "에디터에서 프로젝트를 다시 열어야 반영됩니다.")

    return "오류: action은 take(찍기)·list(목록)·restore(복원) 중 하나입니다."


# ── 씬/프리팹 차이 비교 (읽기전용) ──────────────────────────────────
def _parse_docs(path):
    docs = {}
    cur_key, cur = None, None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = _DOC_RE.match(line)
            if m:
                cur_key = m.group(2)
                cur = {"cls": int(m.group(1)), "lines": []}
                docs[cur_key] = cur
                continue
            if cur is not None and len(cur["lines"]) < 5000:
                cur["lines"].append(line.rstrip("\n"))
    return docs


def _doc_label(d, scripts):
    cls = d["cls"]
    name = next((ln.strip()[8:] for ln in d["lines"] if ln.strip().startswith("m_Name: ")), "")
    if cls == 1:
        return f"GameObject '{name or '(이름없음)'}'"
    if cls == 114:
        g = next((_GUID_RE.search(ln).group(1) for ln in d["lines"]
                  if ln.strip().startswith("m_Script:") and _GUID_RE.search(ln)), None)
        base = scripts.get(g, "MonoBehaviour")
    else:
        extra = {4: "Transform", 224: "RectTransform", 222: "CanvasRenderer",
                 1001: "PrefabInstance"}
        base = _CID_NAMES.get(cls) or extra.get(cls) or f"C{cls}"
    return base + (f" '{name}'" if name else "")


def diff_assets(config, project, path, path2=None, snap_id=None):
    proj = resolve_project(config, project)
    if not proj or not os.path.isdir(proj):
        return f"오류: 유니티 프로젝트를 찾지 못했습니다: {project!r}"
    full, err = _find_asset(proj, path, _SNAP_EXTS)
    if err:
        return err
    rel = os.path.relpath(full, proj).replace(os.sep, "/")
    if path2:
        other, err = _find_asset(proj, path2, _SNAP_EXTS)
        if err:
            return err
        label_b = os.path.relpath(other, proj).replace(os.sep, "/")
        note = "(주의: 서로 다른 두 파일은 내부 ID가 달라 대부분 추가/삭제로 보입니다)"
    else:
        root = _mem_dir("unity_snapshots", _proj_key(proj))
        sid, err = _snap_pick(root, snap_id)
        if err:
            return err
        other = os.path.join(root, sid, rel.replace("/", os.sep))
        if not os.path.isfile(other):
            return f"스냅샷 {sid}에는 {rel}이 없습니다(그 뒤에 만든 파일?)."
        label_b, note = f"스냅샷 {sid}", ""

    now, old = _parse_docs(full), _parse_docs(other)
    scripts = _script_guid_map(proj)
    added = [k for k in now if k not in old]
    removed = [k for k in old if k not in now]
    changed = [k for k in now if k in old and now[k]["lines"] != old[k]["lines"]]
    if not (added or removed or changed):
        return f"[{rel} ↔ {label_b}] 차이 없음 ✅"
    L = [f"[{rel} ↔ {label_b}] 추가 {len(added)} · 삭제 {len(removed)} · 변경 {len(changed)} {note}"]
    for k in added[:10]:
        L.append(f"  + {_doc_label(now[k], scripts)}")
    for k in removed[:10]:
        L.append(f"  - {_doc_label(old[k], scripts)}")
    for k in changed[:15]:
        L.append(f"  ~ {_doc_label(now[k], scripts)}:")
        a_set, b_set = set(now[k]["lines"]), set(old[k]["lines"])
        for ln in [x for x in old[k]["lines"] if x not in a_set][:4]:
            L.append(f"      - {ln.strip()[:110]}")
        for ln in [x for x in now[k]["lines"] if x not in b_set][:4]:
            L.append(f"      + {ln.strip()[:110]}")
    hidden = max(0, len(added) - 10) + max(0, len(removed) - 10) + max(0, len(changed) - 15)
    if hidden:
        L.append(f"  …외 {hidden}건")
    return "\n".join(L)


# ── 스프라이트/텍스처 임포트 감사 (읽기전용) ────────────────────────
# 도트 게임 규칙: 같은 폴더의 스프라이트는 크기·PPU가 통일돼야 프레임 전환 시
# 크기가 널뛰지 않습니다(샐러드팜 500px 사고). 그 규칙 위반을 기계적으로 잡습니다.
def _png_dims(path):
    try:
        with open(path, "rb") as f:
            h = f.read(26)
        if h[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        import struct
        return struct.unpack(">II", h[16:24])
    except (OSError, ValueError):
        return None


def sprites_audit(config, project=None, folder=None):
    proj = resolve_project(config, project)
    if not proj or not os.path.isdir(proj):
        return f"오류: 유니티 프로젝트를 찾지 못했습니다: {project!r}"
    base = os.path.join(proj, "Assets")
    if folder:
        cand = os.path.join(proj, str(folder).strip().strip('"\'').replace("/", os.sep))
        if not os.path.isdir(cand):
            cand = os.path.join(base, str(folder).strip())
        if not os.path.isdir(cand):
            return f"오류: 폴더를 못 찾았습니다: {folder}"
        base = cand

    per_dir = {}
    mip_on, oversize = [], []
    n_img = 0
    for dp, _dirs, files in os.walk(base):
        for fn in files:
            if not fn.lower().endswith((".png", ".jpg", ".jpeg")):
                continue
            fp = os.path.join(dp, fn)
            n_img += 1
            rel = os.path.relpath(fp, proj).replace(os.sep, "/")
            dims = _png_dims(fp) if fn.lower().endswith(".png") else None
            ppu = ttype = mip = maxsz = None
            try:
                with open(fp + ".meta", "r", encoding="utf-8", errors="replace") as f:
                    meta = f.read()
                m = re.search(r"spritePixelsToUnits: (\d+)", meta)
                ppu = int(m.group(1)) if m else None
                m = re.search(r"textureType: (-?\d+)", meta)
                ttype = int(m.group(1)) if m else None
                m = re.search(r"enableMipMap: (\d)", meta)
                mip = m.group(1) == "1" if m else None
                m = re.search(r"maxTextureSize: (\d+)", meta)
                maxsz = int(m.group(1)) if m else None
            except OSError:
                pass
            if ttype == 8:                          # 8 = Sprite
                per_dir.setdefault(os.path.dirname(rel), []).append((fn, dims, ppu))
                if mip:
                    mip_on.append(rel)
            if dims and maxsz and max(dims) > maxsz:
                oversize.append(f"{rel} ({dims[0]}×{dims[1]} > maxTextureSize {maxsz} — 임포트에서 축소됨)")

    size_mix, ppu_mix = [], []
    for d, items in per_dir.items():
        if len(items) < 4:
            continue
        sizes = {}
        for fn, dims, _p in items:
            if dims:
                sizes.setdefault(dims, []).append(fn)
        # '통일된 무리(3장 이상)'가 있는데 몇 개가 이탈한 경우만 문제 — 원래 잡다한 폴더는 놔둠.
        major = max(sizes, key=lambda k: len(sizes[k])) if sizes else None
        if len(sizes) > 1 and len(sizes[major]) >= 3:
            odd = [(k, v) for k, v in sizes.items() if k != major]
            desc = ", ".join(f"{k[0]}×{k[1]}: " + ", ".join(v[:4]) + ("…" if len(v) > 4 else "")
                             for k, v in odd[:3])
            size_mix.append(f"{d} — 다수 {major[0]}×{major[1]}({len(sizes[major])}장)인데 이탈: {desc}")
        ppus = {p for _f, _d, p in items if p}
        if len(ppus) > 1:
            ppu_mix.append(f"{d} — PPU 섞임: {sorted(ppus)}")

    L = [f"[{os.path.basename(proj)}] 스프라이트 임포트 감사 — 이미지 {n_img}개"
         + (f" (범위: {folder})" if folder else "")]
    L.append(f"  {'⚠ 같은 폴더에 크기 제각각 ' + str(len(size_mix)) + '곳:' if size_mix else '✅ 폴더별 스프라이트 크기 통일'}")
    L += [f"    {s}" for s in size_mix[:8]]
    L.append(f"  {'⚠ PPU 불일치 ' + str(len(ppu_mix)) + '곳:' if ppu_mix else '✅ 폴더별 PPU 통일'}")
    L += [f"    {s}" for s in ppu_mix[:8]]
    L.append(f"  {'⚠ 스프라이트에 밉맵 켜짐 ' + str(len(mip_on)) + '개(2D에선 메모리 낭비): ' + ', '.join(m.rsplit('/', 1)[-1] for m in mip_on[:6]) if mip_on else '✅ 스프라이트 밉맵 꺼짐'}")
    L.append(f"  {'⚠ 원본이 maxTextureSize 초과 ' + str(len(oversize)) + '개:' if oversize else '✅ maxTextureSize 초과 없음'}")
    L += [f"    {s}" for s in oversize[:8]]
    warns = len(size_mix) + len(ppu_mix) + len(mip_on) + len(oversize)
    L.append(f"  → 문제 {warns}건" if warns else "  → 깨끗 ✅")
    return "\n".join(L)


def find_in_code(config, project, query, limit=40):
    """프로젝트 Assets의 .cs를 지금 이 순간 훑어 낱말/이름을 파일:줄로 찾습니다(색인 안 씀)."""
    proj = resolve_project(config, project)
    if not proj or not os.path.isdir(proj):
        return f"오류: 유니티 프로젝트를 찾지 못했습니다: {project!r}"
    assets = os.path.join(proj, "Assets")
    if not os.path.isdir(assets):
        return f"오류: Assets 폴더가 없습니다: {proj}"
    q = str(query or "").strip()
    if not q:
        return "오류: 찾을 낱말(query)이 필요합니다."
    ql = q.lower()
    hits, scanned = [], 0
    for dp, dirs, files in os.walk(assets):
        for fn in files:
            if not fn.endswith(".cs"):
                continue
            scanned += 1
            fp = os.path.join(dp, fn)
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    for i, ln in enumerate(f, 1):
                        if ql in ln.lower():
                            rel = os.path.relpath(fp, proj).replace(os.sep, "/")
                            hits.append(f"  {rel}:{i}: {ln.strip()[:120]}")
                            if len(hits) >= limit:
                                return (f"'{q}' 검색 ({limit}개 이상, 상한):\n" + "\n".join(hits))
            except OSError:
                pass
    if not hits:
        return f"'{q}'를 {scanned}개 .cs에서 못 찾았습니다."
    return f"'{q}' 검색 ({len(hits)}곳, .cs {scanned}개 훑음):\n" + "\n".join(hits)


# ── 텍스처 임포트 설정 자동 하향 (감사→수리 짝, 쓰기·백업) ──────────
# unity_audit·unity_sprites가 '큰 텍스처'를 잡기만 하던 것의 수리 짝입니다.
# .meta의 maxTextureSize(기본+플랫폼 오버라이드 전부)를 목표치로 낮춥니다.
# 원본 픽셀이 목표보다 작은 텍스처는 건드려도 효과가 없으니 건너뜁니다.
_TEX_EXTS = (".png", ".jpg", ".jpeg", ".tga", ".psd", ".exr", ".tif", ".tiff")
_MAXSZ_RE = re.compile(r"(maxTextureSize:\s*)(\d+)")


def _scope_dir(proj, folder):
    """folder 인자를 프로젝트 안 실제 폴더로(절대·Assets 상대 둘 다 허용) → (경로, 오류문)."""
    base = os.path.join(proj, "Assets")
    if not folder:
        return base, None
    cand = os.path.join(proj, str(folder).strip().strip('"\'').replace("/", os.sep))
    if not os.path.isdir(cand):
        cand = os.path.join(base, str(folder).strip())
    if not os.path.isdir(cand):
        return None, f"오류: 폴더를 못 찾았습니다: {folder}"
    return cand, None


def tex_fix_candidates(config, project=None, folder=None, max_px=1024):
    """낮출 대상 목록만 스캔(쓰기 없음) → (proj, [(rel, dims, [현재값들])], 오류문)."""
    proj = resolve_project(config, project)
    if not proj or not os.path.isdir(proj):
        return None, [], f"오류: 유니티 프로젝트를 찾지 못했습니다: {project!r}"
    base, err = _scope_dir(proj, folder)
    if err:
        return None, [], err
    max_px = int(max_px)
    hits = []
    for dp, _dirs, files in os.walk(base):
        for fn in files:
            if not fn.lower().endswith(_TEX_EXTS):
                continue
            fp = os.path.join(dp, fn)
            meta = fp + ".meta"
            if not os.path.isfile(meta):
                continue
            try:
                with open(meta, "r", encoding="utf-8", errors="replace") as f:
                    mtext = f.read()
            except OSError:
                continue
            sizes = [int(v) for _pre, v in _MAXSZ_RE.findall(mtext)]
            if not sizes or max(sizes) <= max_px:
                continue
            dims = _png_dims(fp) if fn.lower().endswith(".png") else None
            if dims and max(dims) <= max_px:
                continue                          # 원본이 이미 작음 — 낮춰도 효과 0
            rel = os.path.relpath(fp, proj).replace(os.sep, "/")
            hits.append((rel, dims, sorted(set(s for s in sizes if s > max_px), reverse=True)))
    return proj, hits, None


def tex_fix_apply(config, project=None, folder=None, max_px=1024):
    """후보의 .meta에서 max_px 초과 maxTextureSize를 전부 max_px로. 원본 .meta는
    memory/unity_snapshots/<proj>/edits/<ts>/에 백업. 에디터가 열려 있으면 거절
    (에디터가 meta를 도로 덮어써 수정이 조용히 증발하는 사고 방지)."""
    proj, hits, err = tex_fix_candidates(config, project, folder, max_px)
    if err:
        return err
    if os.path.exists(os.path.join(proj, "Temp", "UnityLockfile")):
        return ("⚠에디터가 이 프로젝트를 열고 있습니다(Temp/UnityLockfile) — .meta를 고쳐도 "
                "에디터가 도로 덮어쓸 수 있어 중단합니다. 에디터를 닫고 다시 불러 주세요.")
    if not hits:
        return f"maxTextureSize {max_px} 초과 텍스처가 없습니다 — 고칠 게 없어요."
    import shutil
    ts = time.strftime("%Y%m%d_%H%M%S")
    bdir = _mem_dir("unity_snapshots", _proj_key(proj), "edits", ts)
    max_px = int(max_px)
    done = []
    for rel, dims, olds in hits:
        meta = os.path.join(proj, rel.replace("/", os.sep)) + ".meta"
        shutil.copyfile(meta, os.path.join(bdir, rel.replace("/", "_") + ".meta"))
        with open(meta, "rb") as f:
            text = f.read().decode("utf-8", "surrogateescape")
        text = _MAXSZ_RE.sub(
            lambda m: m.group(1) + (str(max_px) if int(m.group(2)) > max_px else m.group(2)),
            text)
        with open(meta, "wb") as f:
            f.write(text.encode("utf-8", "surrogateescape"))
        d = f"{dims[0]}x{dims[1]}" if dims else "?"
        done.append(f"  V {rel} (원본 {d}) — maxTextureSize {'/'.join(map(str, olds))} → {max_px}")
    L = [f"[{os.path.basename(proj)}] 텍스처 임포트 하향 — {len(done)}개 .meta 수정"
         f" (백업: memory/unity_snapshots/…/edits/{ts})"]
    L += done[:20]
    if len(done) > 20:
        L.append(f"  …외 {len(done) - 20}개")
    L.append("→ 다음에 에디터를 열면 유니티가 자동 재임포트합니다. 빌드 용량 변화는 "
             "unity_build 후 unity_build_report로 확인하세요.")
    return "\n".join(L)


# ── 3D 모델(FBX 등) 임포트 감사 (읽기전용) ─────────────────────────
# 스프라이트 감사(unity_sprites)의 3D판 — 블렌더에서 쏟아지는 FBX를 받는 쪽 검문소.
_MODEL_EXTS = (".fbx", ".obj", ".blend", ".glb", ".gltf", ".dae", ".3ds")


def models_audit(config, project=None, folder=None):
    proj = resolve_project(config, project)
    if not proj or not os.path.isdir(proj):
        return f"오류: 유니티 프로젝트를 찾지 못했습니다: {project!r}"
    base, err = _scope_dir(proj, folder)
    if err:
        return err

    n = 0
    readable, scaled, cam_light, legacy, no_meta, big = [], [], [], [], [], []
    compress_off = 0
    for dp, _dirs, files in os.walk(base):
        for fn in files:
            if not fn.lower().endswith(_MODEL_EXTS):
                continue
            fp = os.path.join(dp, fn)
            rel = os.path.relpath(fp, proj).replace(os.sep, "/")
            n += 1
            try:
                mb = os.path.getsize(fp) / 1048576
                if mb > 5:
                    big.append(f"{rel} ({mb:.1f}MB)")
            except OSError:
                pass
            meta = fp + ".meta"
            if not os.path.isfile(meta):
                no_meta.append(rel)               # 유니티 밖에서 복사 — 아직 임포트 안 됨
                continue
            try:
                with open(meta, "r", encoding="utf-8", errors="replace") as f:
                    mt = f.read()
            except OSError:
                continue

            def g(key, default=None):
                m = re.search(rf"^\s*{key}: (-?[\d.]+)$", mt, re.M)
                return float(m.group(1)) if m else default

            if g("isReadable") == 1:
                readable.append(rel)              # Read/Write=메모리 2배(CPU 사본 유지)
            gs = g("globalScale")
            ufs = g("useFileScale")
            if (gs is not None and abs(gs - 1.0) > 1e-6) or ufs == 0:
                scaled.append(f"{rel} (globalScale {gs:g}"
                              + (", 파일 스케일 무시" if ufs == 0 else "") + ")")
            if g("importCameras") == 1 or g("importLights") == 1:
                cam_light.append(rel)             # 게임에 카메라·조명이 따라 들어옴
            if g("animationType") == 1:
                legacy.append(rel)                # Legacy 애니 — 현행 Animator와 안 섞임
            if g("meshCompression") == 0:
                compress_off += 1

    L = [f"[{os.path.basename(proj)}] 3D 모델 임포트 감사 — 모델 {n}개"
         + (f" (범위: {folder})" if folder else "")]
    if n == 0:
        return L[0] + "\n  (fbx·obj·blend·glb 파일이 없습니다)"
    L.append(("  ⚠ Read/Write 켜짐 " + str(len(readable))
              + "개 (메모리 2배 — 코드로 메시를 안 만지면 꺼도 됨):") if readable
             else "  ✅ Read/Write 전부 꺼짐")
    L += [f"    {s}" for s in readable[:8]]
    L.append(("  ⚠ 스케일 조정된 모델 " + str(len(scaled))
              + "개 (블렌더에서 apply가 안 된 신호 — prep_unity 권장):") if scaled
             else "  ✅ 스케일 팩터 전부 1(원본 그대로)")
    L += [f"    {s}" for s in scaled[:8]]
    L.append(("  ⚠ 카메라/조명 임포트 켜짐 " + str(len(cam_light)) + "개: "
              + ", ".join(x.rsplit("/", 1)[-1] for x in cam_light[:6])) if cam_light
             else "  ✅ 카메라/조명 임포트 꺼짐")
    if legacy:
        L.append(f"  ⚠ Legacy 애니메이션 {len(legacy)}개 (Animator와 호환 안 됨): "
                 + ", ".join(x.rsplit("/", 1)[-1] for x in legacy[:6]))
    L.append(("  ⚠ .meta 없는 모델 " + str(len(no_meta)) + "개 (아직 유니티가 임포트 안 함): "
              + ", ".join(x.rsplit("/", 1)[-1] for x in no_meta[:6])) if no_meta
             else "  ✅ .meta 전부 있음")
    if big:
        L.append(f"  ⚠ 5MB↑ 모델 {len(big)}개 (원본 최적화 검토 — blender_3d decimate/lod):")
        L += [f"    {s}" for s in big[:6]]
    if compress_off and n >= 3:
        L.append(f"  ℹ 메시 압축 꺼진 모델 {compress_off}/{n}개 — 모바일 용량이 아쉬우면 Low 검토")
    warns = len(readable) + len(scaled) + len(cam_light) + len(legacy) + len(no_meta) + len(big)
    L.append(f"  → 문제 {warns}건" if warns else "  → 깨끗 ✅")
    return "\n".join(L)


# ── 씬 성능 린트 (읽기전용) ─────────────────────────────────────────
# unity_audit=파일 무결성, unity_scene=구조 보기, 이건 **모바일 성능 관점** 집계.
def _enabled_scenes(proj):
    ebs = os.path.join(proj, "ProjectSettings", "EditorBuildSettings.asset")
    try:
        with open(ebs, "r", encoding="utf-8", errors="replace") as f:
            pairs = re.findall(r"- enabled: (\d)\s*\n\s*path: (.+)", f.read())
        return [p.strip() for e, p in pairs if e == "1"]
    except OSError:
        return []


def scene_lint(config, project=None, path=None):
    proj = resolve_project(config, project)
    if not proj or not os.path.isdir(proj):
        return f"오류: 유니티 프로젝트를 찾지 못했습니다: {project!r}"
    if path:
        full, err = _find_asset(proj, path, (".unity",))
        if err:
            return err
        scenes = [os.path.relpath(full, proj).replace(os.sep, "/")]
    else:
        scenes = _enabled_scenes(proj)
        if not scenes:                            # 빌드 씬 등록이 없으면 Assets의 씬 전부(상한)
            scenes = []
            for dp, _dirs, files in os.walk(os.path.join(proj, "Assets")):
                scenes += [os.path.relpath(os.path.join(dp, f), proj).replace(os.sep, "/")
                           for f in files if f.endswith(".unity")]
            scenes = sorted(scenes)[:20]
    if not scenes:
        return f"[{os.path.basename(proj)}] 검사할 씬이 없습니다."

    L = [f"[{os.path.basename(proj)}] 씬 성능 린트 — {len(scenes)}개 씬 (모바일 기준)"]
    total_warn = 0
    for rel in scenes:
        fp = os.path.join(proj, rel.replace("/", os.sep))
        if not os.path.isfile(fp):
            L.append(f"  ✗ {rel} — 파일 없음(빌드 목록이 낡음?)")
            total_warn += 1
            continue
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                t = f.read()
        except OSError:
            continue
        docs = len(re.findall(r"^--- !u!", t, re.M))
        cams = len(re.findall(r"^--- !u!20 ", t, re.M))
        listeners = len(re.findall(r"^--- !u!81 ", t, re.M))
        lights = len(re.findall(r"^--- !u!108 ", t, re.M))
        shadows = len(re.findall(r"m_Shadows:\s*\n\s*m_Type: [12]", t))
        particles = len(re.findall(r"^--- !u!198 ", t, re.M))
        canvases = len(re.findall(r"^--- !u!223 ", t, re.M))
        missing = t.count("m_Script: {fileID: 0}")
        warns = []
        if cams > 1:
            warns.append(f"카메라 {cams}대(대개 1대면 충분 — 겹치면 그만큼 더 그림)")
        if listeners > 1:
            warns.append(f"AudioListener {listeners}개(1개여야 함 — 경고 도배)")
        if shadows:
            warns.append(f"실시간 그림자 조명 {shadows}개(모바일 큰 비용 — 꼭 필요한지)")
        if lights > 4:
            warns.append(f"조명 {lights}개(모바일엔 많음)")
        missing_shader = t.count("Hidden/InternalErrorShader") + t.count("m_Shader: {fileID: 0}")
        if missing_shader:
            warns.append(f"💡 [분홍색/Magenta 셰이더 감지] 유실되거나 손상된 셰이더 {missing_shader}개 — Materials의 Shader를 Standard 또는 Universal Render Pipeline/Lit으로 재지정하세요.")
        if missing:
            warns.append(f"💡 [깨진 스크립트 감지] missing script 참조 {missing}개 — 메타 유실 또는 C# 스크립트 클래스명과 파일명이 일치하는지 확인하세요.")
        if canvases > 3:
            warns.append(f"Canvas {canvases}개(리빌드 단위 — 통합 검토)")
        if docs > 4000:
            warns.append(f"오브젝트 문서 {docs:,}개(무거운 씬)")
        L.append(f"  {'⚠' if warns else '✅'} {rel} — 문서 {docs:,}·카메라 {cams}"
                 f"·조명 {lights}·파티클 {particles}·Canvas {canvases}")
        L += [f"      · {w}" for w in warns]
        total_warn += len(warns)
    L.append(f"  → 경고 {total_warn}건" if total_warn else "  → 전 씬 깨끗 ✅")
    L.append("(구조 상세는 unity_scene, 깨진 참조의 실행 검증은 unity_scene_smoke)")
    return "\n".join(L)


# ── 씬 로드 스모크 테스트 (배치모드 실행 검증) ──────────────────────
# 컴파일 통과 != 씬이 멀쩡함. 빌드 씬을 배치모드로 하나씩 실제 로드해
# 누락 스크립트·**끊긴 참조(있던 에셋이 삭제돼 None이 된 필드)**·로드 중 예외를 잡습니다.
_SMOKE_CS = r'''using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class LucySmokeTemp
{
    public static void Run()
    {
        foreach (var s in EditorBuildSettings.scenes)
        {
            if (!s.enabled) continue;
            int objs = 0, missScript = 0, missRef = 0;
            var notes = new StringBuilder();
            try
            {
                var scene = EditorSceneManager.OpenScene(s.path, OpenSceneMode.Single);
                foreach (var root in scene.GetRootGameObjects())
                foreach (var tr in root.GetComponentsInChildren<Transform>(true))
                {
                    objs++;
                    var go = tr.gameObject;
                    foreach (var c in go.GetComponents<Component>())
                    {
                        if (c == null)
                        {
                            missScript++;
                            if (missScript <= 8) notes.Append("SCRIPT@" + go.name + "; ");
                            continue;
                        }
                        var so = new SerializedObject(c);
                        var sp = so.GetIterator();
                        while (sp.NextVisible(true))
                        {
                            if (sp.propertyType == SerializedPropertyType.ObjectReference
                                && sp.objectReferenceValue == null
                                && sp.objectReferenceInstanceIDValue != 0)
                            {
                                missRef++;
                                if (missRef <= 8)
                                    notes.Append("REF@" + go.name + "." + c.GetType().Name
                                                 + "." + sp.name + "; ");
                            }
                        }
                    }
                }
                Debug.Log("LUCY_SMOKE|OK|" + s.path + "|" + objs + "|" + missScript
                          + "|" + missRef + "|" + notes);
            }
            catch (System.Exception e)
            {
                Debug.Log("LUCY_SMOKE|ERR|" + s.path + "|" + e.GetType().Name + ": " + e.Message);
            }
        }
        EditorApplication.Exit(0);
    }
}
'''


def scene_smoke(config, project=None, timeout=900):
    proj = resolve_project(config, project)
    if not proj or not os.path.isdir(proj):
        return f"오류: 유니티 프로젝트를 찾지 못했습니다: {project!r}"
    if not _enabled_scenes(proj):
        return (f"[{os.path.basename(proj)}] 빌드 씬이 하나도 등록·활성화돼 있지 않습니다 "
                "(File - Build Settings). 스모크는 빌드 씬을 대상으로 합니다.")
    # 임시 에디터 스크립트를 심고(배치 부팅이 컴파일해 줌) 끝나면 흔적 없이 지웁니다.
    ed_dir = os.path.join(proj, "Assets", "Editor")
    os.makedirs(ed_dir, exist_ok=True)
    cs = os.path.join(ed_dir, "LucySmokeTemp.cs")
    with open(cs, "w", encoding="utf-8") as f:
        f.write(_SMOKE_CS)
    try:
        r = run_batch(config, project=project, method="LucySmokeTemp.Run",
                      timeout=timeout, return_log=True)
    finally:
        for p in (cs, cs + ".meta"):
            try:
                os.remove(p)
            except OSError:
                pass
    if isinstance(r, str):                        # 잠금·타임아웃 등 초기 실패는 문자열로 옴
        return r
    summary, full = r
    rows = [ln.split("|") for ln in full.splitlines() if ln.startswith("LUCY_SMOKE|")]
    if not rows:
        return ("스모크 마커가 로그에 없습니다 — 프로젝트에 컴파일 에러가 있으면 스크립트가 "
                "못 돌아갑니다. unity_run으로 컴파일부터 확인하세요.\n" + summary)
    L = [f"[{os.path.basename(proj)}] 씬 로드 스모크 — 빌드 씬 {len(rows)}개 실제 로드"]
    bad = 0
    for row in rows:
        if row[1] == "ERR":
            L.append(f"  ✗ {row[2]} — 로드 중 예외: {'|'.join(row[3:])[:150]}")
            bad += 1
            continue
        _tag, _ok, spath, objs, mscript, mref = row[:6]
        notes = row[6] if len(row) > 6 else ""
        issues = []
        if int(mscript):
            issues.append(f"누락 스크립트 {mscript}개")
        if int(mref):
            issues.append(f"끊긴 참조 {mref}개(있던 에셋이 지워져 None)")
        mark = "⚠" if issues else "✅"
        L.append(f"  {mark} {spath} — 오브젝트 {int(objs):,}개"
                 + (" · " + " · ".join(issues) if issues else ""))
        if issues and notes.strip():
            L.append(f"      → {notes.strip()[:220]}")
        bad += 1 if issues else 0
    exc = len(re.findall(r"^\w[\w.]*Exception", full, re.M))
    if exc:
        L.append(f"  ℹ 로드 과정 로그에 예외 표기 {exc}건 — 상세는 unity_log로")
    L.append(f"  → 문제 씬 {bad}개" if bad else "  → 전 씬 통과 ✅ (로드 수준 — 플레이 로직은 별개)")
    return "\n".join(L)


# ── 씬 스크린샷 (배치모드 실제 렌더 — 루시의 유니티 눈) ─────────────
# 세션58 배치 렌더 함정 3종을 코드에 박음: ①비동기 셰이더 컴파일=검정 플레이스홀더
# → allowAsyncCompilation=false+예열 렌더 ②-nographics면 렌더 불가 → graphics=True
# ③Screen Space Overlay UI는 카메라 렌더에 안 찍힘 → 렌더 동안만 카메라에 붙임(씬 저장 안 하므로 무해).
_SHOT_CS = r'''using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class LucyShotTemp
{
    public static void Run()
    {
        var outDir = @"__OUT__";
        int w = __W__, h = __H__;
        ShaderUtil.allowAsyncCompilation = false;
        foreach (var s in EditorBuildSettings.scenes)
        {
            if (!s.enabled) continue;
            var stem = Path.GetFileNameWithoutExtension(s.path);
            if ("__ONLY__" != "" && !stem.ToLower().Contains("__ONLY__")) continue;
            try
            {
                var scene = EditorSceneManager.OpenScene(s.path, OpenSceneMode.Single);
                Camera cam = Camera.main;
                if (cam == null)
                    foreach (var c in Object.FindObjectsByType<Camera>())
                    { cam = c; break; }
                if (cam == null) { Debug.Log("LUCY_SHOT|NOCAM|" + s.path); continue; }
                foreach (var cv in Object.FindObjectsByType<Canvas>())
                    if (cv.renderMode == RenderMode.ScreenSpaceOverlay)
                    {
                        cv.renderMode = RenderMode.ScreenSpaceCamera;   // 씬은 저장 안 하므로 원복 불필요
                        cv.worldCamera = cam;
                        cv.planeDistance = cam.nearClipPlane + 0.1f;
                    }
                var rt = new RenderTexture(w, h, 24);
                cam.targetTexture = rt;
                for (int i = 0; i < 3; i++) cam.Render();
                RenderTexture.active = rt;
                var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
                tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
                tex.Apply();
                cam.targetTexture = null;
                RenderTexture.active = null;
                var png = Path.Combine(outDir, stem + ".png");
                File.WriteAllBytes(png, tex.EncodeToPNG());
                Debug.Log("LUCY_SHOT|OK|" + s.path + "|" + png);
            }
            catch (System.Exception e)
            {
                Debug.Log("LUCY_SHOT|ERR|" + s.path + "|" + e.GetType().Name + ": " + e.Message);
            }
        }
        EditorApplication.Exit(0);
    }
}
'''


def _pixel_stats(png):
    """(마젠타 비율, 단색 비율). 마젠타=재질/셰이더 실종 신호, 단색≈1.0=정적 콘텐츠 없는 씬
    (UI를 런타임에 만드는 씬이면 정상 — 눈 두뇌에 보낼 것도 없으니 기계 판별로 끝냄).
    PIL 없거나 실패하면 (None, None) — 판정을 지어내지 않음.
    ⭐실제 계산은 vision.pixel_stats 하나뿐입니다(블렌더·유니티가 같은 자를 쓰도록)."""
    import vision
    s = vision.pixel_stats(png)
    return (s["magenta"], s["flat"]) if s else (None, None)


def scene_shot(config, project=None, scene=None, width=720, height=1280, timeout=900):
    """빌드 씬들을 배치모드로 실제 렌더해 PNG로 — (요약문, [(씬, png, 마젠타비율)…]) 반환.
    초기 실패(잠금 등)는 문자열."""
    proj = resolve_project(config, project)
    if not proj or not os.path.isdir(proj):
        return f"오류: 유니티 프로젝트를 찾지 못했습니다: {project!r}"
    if not _enabled_scenes(proj):
        return (f"[{os.path.basename(proj)}] 빌드 씬이 하나도 등록·활성화돼 있지 않습니다 "
                "(File - Build Settings).")
    out_dir = os.path.join(_mem_dir(), "unity_shots", _proj_key(proj),
                           time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(out_dir, exist_ok=True)
    src = (_SHOT_CS.replace("__OUT__", out_dir.replace("\\", "/"))
                   .replace("__W__", str(int(width))).replace("__H__", str(int(height)))
                   .replace("__ONLY__", (scene or "").strip().lower().replace('"', "")))
    ed_dir = os.path.join(proj, "Assets", "Editor")
    os.makedirs(ed_dir, exist_ok=True)
    cs = os.path.join(ed_dir, "LucyShotTemp.cs")
    with open(cs, "w", encoding="utf-8") as f:
        f.write(src)
    try:
        r = run_batch(config, project=project, method="LucyShotTemp.Run",
                      timeout=timeout, return_log=True, graphics=True)
    finally:
        for p in (cs, cs + ".meta"):
            try:
                os.remove(p)
            except OSError:
                pass
    if isinstance(r, str):
        return r
    summary, full = r
    rows = [ln.split("|") for ln in full.splitlines() if ln.startswith("LUCY_SHOT|")]
    if not rows:
        return ("샷 마커가 로그에 없습니다 — 컴파일 에러가 있으면 스크립트가 못 돌아갑니다. "
                "unity_run으로 컴파일부터 확인하세요.\n" + summary)
    shots = []
    for row in rows:
        if row[1] == "OK" and len(row) > 3 and os.path.isfile(row[3]):
            magenta, flat = _pixel_stats(row[3])
            shots.append((row[2], row[3], magenta, flat))
        else:
            shots.append((row[2], None, row[1] if row[1] != "OK" else "파일 없음", None))
    return f"[{os.path.basename(proj)}]", shots


def prev_shot_diff(png):
    """같은 씬의 직전 샷과의 픽셀 차이 비율(0~1)과 그 샷의 폴더명 — 리그레션 감시.
    직전 샷이 없거나 비교 실패면 (None, None). 에디트/플레이 샷은 서로 안 섞습니다."""
    cur_dir = os.path.dirname(png)
    parent = os.path.dirname(cur_dir)
    is_play = os.path.basename(cur_dir).endswith("_play")
    base = os.path.basename(png)
    try:
        cur_name = os.path.basename(cur_dir)
        sibs = sorted(d for d in os.listdir(parent)
                      if os.path.isdir(os.path.join(parent, d)) and d < cur_name
                      and d.endswith("_play") == is_play)   # 과거 것만(폴더명=타임스탬프)
    except OSError:
        return None, None
    for d in reversed(sibs):                      # 가장 최근 것부터
        old = os.path.join(parent, d, base)
        if not os.path.isfile(old):
            continue
        try:
            from PIL import Image, ImageChops
            a = Image.open(old).convert("RGB").resize((180, 320))
            b = Image.open(png).convert("RGB").resize((180, 320))
            px = list(ImageChops.difference(a, b).getdata())
            ratio = sum(r + g + bl for r, g, bl in px) / (3 * 255.0 * len(px))
            return ratio, d
        except Exception:
            return None, None
    return None, None


# ── 플레이모드 씬 캡처 (런타임 상태 — 에디트 모드가 못 보는 것) ─────
# 에디트 샷의 한계=런타임 생성물(데이터 UI·스폰)이 안 보임 → 플레이모드 테스트로 씬을
# **실제로 굴리고 2초 기다린 뒤** 카메라 렌더. 오버레이 UI 부착 트릭 동일(저장 없음=무해).
_PSHOT_CS = r'''using System.Collections;
using System.IO;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

public class LucyPlayShotTemp
{
    [UnityTest]
    public IEnumerator Shots()
    {
        var outDir = @"__OUT__";
        var only = "__ONLY__";
        int w = __W__, h = __H__;
        int n = SceneManager.sceneCountInBuildSettings;
        for (int i = 0; i < n; i++)
        {
            var path = SceneUtility.GetScenePathByBuildIndex(i);
            var stem = Path.GetFileNameWithoutExtension(path);
            if (stem.StartsWith("InitTestScene")) continue;   // 테스트 프레임워크 부트 씬은 제외
            if (only != "" && !stem.ToLower().Contains(only)) continue;
            var load = SceneManager.LoadSceneAsync(i, LoadSceneMode.Single);
            float t0 = Time.realtimeSinceStartup;
            while (load != null && !load.isDone && Time.realtimeSinceStartup - t0 < 20)
                yield return null;
            float settle = Time.realtimeSinceStartup;      // 런타임 초기화(스폰·UI 구성)가 돌 시간
            while (Time.realtimeSinceStartup - settle < 2f) yield return null;
            Camera cam = Camera.main;
            if (cam == null)
                foreach (var c in Object.FindObjectsByType<Camera>())
                { cam = c; break; }
            if (cam == null) { Debug.Log("LUCY_PSHOT|NOCAM|" + path); continue; }
            foreach (var cv in Object.FindObjectsByType<Canvas>())
                if (cv.renderMode == RenderMode.ScreenSpaceOverlay)
                {
                    cv.renderMode = RenderMode.ScreenSpaceCamera;
                    cv.worldCamera = cam;
                    cv.planeDistance = cam.nearClipPlane + 0.1f;
                }
            var rt = new RenderTexture(w, h, 24);
            cam.targetTexture = rt;
            for (int k = 0; k < 3; k++) cam.Render();
            RenderTexture.active = rt;
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
            tex.Apply();
            cam.targetTexture = null;
            RenderTexture.active = null;
            var png = Path.Combine(outDir, stem + ".png");
            File.WriteAllBytes(png, tex.EncodeToPNG());
            Debug.Log("LUCY_PSHOT|OK|" + path + "|" + png);
            yield return null;                              // 캡처 직후 바로 다음 로드 금지(비동기 함정)
        }
        Assert.Pass();
    }
}
'''

_PSHOT_ASMDEF = {
    "name": "LucyPlayShotTests",
    "references": ["UnityEngine.TestRunner", "UnityEditor.TestRunner"],
    "includePlatforms": [],
    "excludePlatforms": [],
    "overrideReferences": True,
    "precompiledReferences": ["nunit.framework.dll"],
    "autoReferenced": False,
    "defineConstraints": ["UNITY_INCLUDE_TESTS"],
    "versionDefines": [],
    "noEngineReferences": False,
}


def play_shot(config, project=None, scene=None, width=720, height=1280, timeout=1200):
    """씬을 플레이모드로 실제 굴려 캡처 — (요약문, [(씬, png, 마젠타, 단색)…]) 또는 오류 문자열.
    런타임 스크립트가 도는 만큼 예외가 날 수 있음 — 로그의 예외 수를 요약문에 담습니다."""
    proj = resolve_project(config, project)
    if not proj or not os.path.isdir(proj):
        return f"오류: 유니티 프로젝트를 찾지 못했습니다: {project!r}"
    if not _enabled_scenes(proj):
        return (f"[{os.path.basename(proj)}] 빌드 씬이 하나도 등록·활성화돼 있지 않습니다 "
                "(File - Build Settings).")
    out_dir = os.path.join(_mem_dir(), "unity_shots", _proj_key(proj),
                           time.strftime("%Y%m%d_%H%M%S") + "_play")
    os.makedirs(out_dir, exist_ok=True)
    ps_dir = os.path.join(proj, "Assets", "_LucyPlayShot")
    os.makedirs(ps_dir, exist_ok=True)
    import shutil
    try:
        src = (_PSHOT_CS.replace("__OUT__", out_dir.replace("\\", "/"))
                        .replace("__W__", str(int(width))).replace("__H__", str(int(height)))
                        .replace("__ONLY__", (scene or "").strip().lower().replace('"', "")))
        with open(os.path.join(ps_dir, "LucyPlayShotTemp.cs"), "w", encoding="utf-8") as f:
            f.write(src)
        with open(os.path.join(ps_dir, "LucyPlayShotTests.asmdef"), "w", encoding="utf-8") as f:
            json.dump(_PSHOT_ASMDEF, f, indent=4)
        r = run_batch(config, project=project, tests="playmode",
                      timeout=timeout, return_log=True, graphics=True, burst=False)
    finally:
        shutil.rmtree(ps_dir, ignore_errors=True)
        try:
            os.remove(ps_dir + ".meta")
        except OSError:
            pass
    if isinstance(r, str):
        return r
    summary, full = r
    rows = [ln.split("|") for ln in full.splitlines() if ln.startswith("LUCY_PSHOT|")]
    if not rows:
        return ("플레이모드 샷 마커가 로그에 없습니다 — 컴파일 에러(unity_run으로 확인)거나 "
                "플레이모드 자체가 못 돌았습니다.\n" + summary)
    shots = []
    for row in rows:
        if row[1] == "OK" and len(row) > 3 and os.path.isfile(row[3]):
            magenta, flat = _pixel_stats(row[3])
            shots.append((row[2], row[3], magenta, flat))
        else:
            shots.append((row[2], None, row[1] if row[1] != "OK" else "파일 없음", None))
    exc = len(re.findall(r"^\w[\w.]*Exception", full, re.M))
    head = f"[{os.path.basename(proj)}] 플레이모드" + (f" · 런타임 예외 로그 {exc}건" if exc else "")
    return head, shots


# ── FBX 왕복 검증 (블렌더 납품물을 진짜 유니티에서) ─────────────────
# 세션58~61 사고 클래스(갈색 덩어리·통째 투명·노멀 뒤집힘)는 전부 **유니티에 넣어봐야**
# 드러났음 — 블렌더 자체검증(재임포트)은 통과했는데 유니티선 _BaseMap=NULL이던 실측.
# FBX+옆의 텍스처를 검증 프로젝트에 심고 배치 임포트→재질 바인딩 실측→렌더까지.
_FBXV_CS = r'''using System.IO;
using UnityEditor;
using UnityEngine;

public static class LucyFbxVerifyTemp
{
    public static void Run()
    {
        ShaderUtil.allowAsyncCompilation = false;
        var outPng = @"__OUT__";
        var guids = AssetDatabase.FindAssets("t:Model", new[] { "Assets/_LucyVerify" });
        if (guids.Length == 0) { Debug.Log("LUCY_FBXV|ERR|모델 없음"); EditorApplication.Exit(0); return; }
        var path = AssetDatabase.GUIDToAssetPath(guids[0]);
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
        if (prefab == null) { Debug.Log("LUCY_FBXV|ERR|로드 실패 " + path); EditorApplication.Exit(0); return; }
        var go = Object.Instantiate(prefab);
        int bound = 0, unbound = 0;
        foreach (var r in go.GetComponentsInChildren<Renderer>(true))
            foreach (var m in r.sharedMaterials)
            {
                if (m == null) { Debug.Log("LUCY_FBXV|MAT|(널 재질)|NULL"); unbound++; continue; }
                var t = m.mainTexture;
                Debug.Log("LUCY_FBXV|MAT|" + m.name + "|" + (t ? t.name : "NULL"));
                if (t) bound++; else unbound++;
            }
        var b = new Bounds(go.transform.position, Vector3.one * 0.1f);
        foreach (var r in go.GetComponentsInChildren<Renderer>(true)) b.Encapsulate(r.bounds);
        var lightGo = new GameObject("LucyL");
        var light = lightGo.AddComponent<Light>();
        light.type = LightType.Directional;
        light.transform.rotation = Quaternion.Euler(45, 30, 0);
        light.intensity = 1.2f;
        var camGo = new GameObject("LucyC");
        var cam = camGo.AddComponent<Camera>();
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = new Color(0.24f, 0.32f, 0.40f);
        float size = Mathf.Max(b.size.x, Mathf.Max(b.size.y, b.size.z), 0.1f);
        cam.transform.position = b.center + new Vector3(0.7f, 0.5f, -1.6f).normalized * size * 2.2f;
        cam.transform.LookAt(b.center);
        var rt = new RenderTexture(768, 768, 24);
        cam.targetTexture = rt;
        for (int i = 0; i < 3; i++) cam.Render();
        RenderTexture.active = rt;
        var tex = new Texture2D(768, 768, TextureFormat.RGB24, false);
        tex.ReadPixels(new Rect(0, 0, 768, 768), 0, 0);
        tex.Apply();
        File.WriteAllBytes(outPng, tex.EncodeToPNG());
        Debug.Log("LUCY_FBXV|SHOT|" + outPng);
        Debug.Log("LUCY_FBXV|SUM|" + bound + "|" + unbound);
        EditorApplication.Exit(0);
    }
}
'''

_TEX_SIBLINGS = (".png", ".jpg", ".jpeg", ".tga")


def fbx_verify(config, fbx_path, project=None, timeout=900):
    """FBX(+같은 폴더 텍스처)를 검증용 유니티 프로젝트에 심고 배치 임포트해
    재질 바인딩(mainTexture) 실측 + 렌더 PNG. (재질표, png, 로그요약) 또는 오류 문자열.
    검증 프로젝트는 config unity.verify_project(기본 onlyuprat) — 흔적은 끝나면 지움."""
    if not os.path.isfile(fbx_path) or not fbx_path.lower().endswith(".fbx"):
        return f"오류: FBX 파일이 아닙니다: {fbx_path}"
    alias = project or (config.get("unity", {}) or {}).get("verify_project", "onlyuprat")
    proj = resolve_project(config, alias)
    if not proj or not os.path.isdir(proj):
        return f"오류: 검증용 유니티 프로젝트를 찾지 못했습니다: {alias!r}"
    ver_dir = os.path.join(proj, "Assets", "_LucyVerify")
    ed_dir = os.path.join(ver_dir, "Editor")
    out_png = os.path.join(_mem_dir(), "unity_shots",
                           f"fbxverify_{time.strftime('%H%M%S')}.png")
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    import shutil
    os.makedirs(ed_dir, exist_ok=True)
    try:
        shutil.copy2(fbx_path, os.path.join(ver_dir, os.path.basename(fbx_path)))
        folder = os.path.dirname(fbx_path)
        for f in os.listdir(folder):                 # 외부 파일 방식: 옆의 텍스처도 같이(세션58 교훈)
            if f.lower().endswith(_TEX_SIBLINGS):
                shutil.copy2(os.path.join(folder, f), os.path.join(ver_dir, f))
        with open(os.path.join(ed_dir, "LucyFbxVerifyTemp.cs"), "w", encoding="utf-8") as f:
            f.write(_FBXV_CS.replace("__OUT__", out_png.replace("\\", "/")))
        r = run_batch(config, project=alias, method="LucyFbxVerifyTemp.Run",
                      timeout=timeout, return_log=True, graphics=True)
    finally:
        shutil.rmtree(ver_dir, ignore_errors=True)   # 검증 프로젝트에 흔적을 남기지 않음
        for m in (ver_dir + ".meta",):
            try:
                os.remove(m)
            except OSError:
                pass
    if isinstance(r, str):
        return r
    summary, full = r
    rows = [ln.split("|") for ln in full.splitlines() if ln.startswith("LUCY_FBXV|")]
    if not rows:
        return ("검증 마커가 로그에 없습니다 — 검증 프로젝트에 컴파일 에러가 있으면 스크립트가 "
                "못 돌아갑니다. unity_run으로 확인하세요.\n" + summary)
    mats = [(x[2], x[3]) for x in rows if x[1] == "MAT"]
    shot = next((x[2] for x in rows if x[1] == "SHOT" and os.path.isfile(x[2])), None)
    err = next(("|".join(x[2:]) for x in rows if x[1] == "ERR"), None)
    return {"materials": mats, "shot": shot, "error": err, "project": alias}


# ── C# 위생 린트 (읽기전용) ─────────────────────────────────────────
# unity_find=검색, unity_outline=구조, 이건 **나쁜 패턴 탐지** — 모바일 성능 함정 위주.
_UPDATE_RE = re.compile(r"\bvoid\s+(Update|LateUpdate|FixedUpdate)\s*\(\s*\)")
_HOT_PATS = (
    (re.compile(r"GameObject\.Find(?:WithTag)?\s*\("), "GameObject.Find(매 프레임 전체 검색)"),
    (re.compile(r"\bFindObjectOfType\s*<"), "FindObjectOfType(매 프레임 전체 검색)"),
    (re.compile(r"\bGetComponent(?:s|InChildren|InParent)?\s*<"), "GetComponent(캐시 권장)"),
    (re.compile(r"\bCamera\.main\b"), "Camera.main(내부적으로 Find)"),
    (re.compile(r"\bInstantiate\s*\("), "Instantiate(풀링 검토)"),
)


def code_lint(config, project=None, folder=None):
    proj = resolve_project(config, project)
    if not proj or not os.path.isdir(proj):
        return f"오류: 유니티 프로젝트를 찾지 못했습니다: {project!r}"
    base, err = _scope_dir(proj, folder)
    if err:
        return err

    empty_update, hot, empty_catch, sendmsg = [], [], [], []
    n_files = debug_logs = 0
    for dp, _dirs, files in os.walk(base):
        if os.sep + "Editor" in dp:               # 에디터 코드는 런타임 성능과 무관
            continue
        for fn in files:
            if not fn.endswith(".cs"):
                continue
            fp = os.path.join(dp, fn)
            rel = os.path.relpath(fp, proj).replace(os.sep, "/")
            n_files += 1
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError:
                continue
            debug_logs += len(re.findall(r"^\s*Debug\.Log", text, re.M))
            for m in re.finditer(r"catch\s*(?:\([^)]*\))?\s*\{\s*\}", text):
                empty_catch.append(f"{rel}:{text[:m.start()].count(chr(10)) + 1}")
            for m in re.finditer(r"\bSendMessage\s*\(", text):
                sendmsg.append(f"{rel}:{text[:m.start()].count(chr(10)) + 1}")
            # Update류 본문만 중괄호 짝으로 오려내 '매 프레임 비용' 패턴을 그 안에서만 봅니다.
            for m in _UPDATE_RE.finditer(text):
                name = m.group(1)
                i = text.find("{", m.end())
                if i < 0:
                    continue
                depth = 0
                j = i
                while j < len(text):
                    if text[j] == "{":
                        depth += 1
                    elif text[j] == "}":
                        depth -= 1
                        if depth == 0:
                            break
                    j += 1
                body = text[i + 1:j]
                if not body.strip():
                    empty_update.append(f"{rel} — 빈 {name}()(호출 비용만 냄, 지우면 됨)")
                    continue
                for pat, label in _HOT_PATS:
                    for hm in pat.finditer(body):
                        ls = body.rfind("\n", 0, hm.start()) + 1
                        le = body.find("\n", hm.start())
                        line_txt = body[ls:le if le > 0 else len(body)]
                        if line_txt.lstrip().startswith("//"):
                            continue              # 주석 줄은 제외
                        # 오탐 억제 2종(FarmTouch.cs 실사례): ①null 복구 가드(캐시가 비었을
                        # 때만 도는 줄) ②입력 게이트 뒤(클릭·키 프레임에만 도는 코드).
                        if "== null" in line_txt:
                            continue
                        gated = ("wasPressedThisFrame", "wasReleasedThisFrame",
                                 "GetMouseButtonDown", "GetMouseButtonUp", "GetKeyDown",
                                 "GetKeyUp", "GetButtonDown", "touchCount")
                        if any(g in body[:hm.start()] for g in gated):
                            continue
                        ln = text[:i + 1 + hm.start()].count("\n") + 1
                        hot.append(f"{rel}:{ln} — {name}() 안 {label}")
                        break                     # 패턴당 파일 1건이면 신호는 충분

    L = [f"[{os.path.basename(proj)}] C# 위생 린트 — 런타임 .cs {n_files}개"
         + (f" (범위: {folder})" if folder else "") + " (Editor 폴더 제외)"]
    L.append(("  ⚠ 매 프레임 비용 패턴 " + str(len(hot)) + "건 (Update류 본문 안):") if hot
             else "  ✅ Update 안 검색·할당 패턴 없음")
    L += [f"    {s}" for s in hot[:12]]
    if len(hot) > 12:
        L.append(f"    …외 {len(hot) - 12}건")
    L.append(("  ⚠ 빈 Update류 " + str(len(empty_update)) + "개:") if empty_update
             else "  ✅ 빈 Update 없음")
    L += [f"    {s}" for s in empty_update[:8]]
    L.append(("  ⚠ 빈 catch " + str(len(empty_catch)) + "곳 (예외를 삼켜 버그를 숨김): "
              + ", ".join(empty_catch[:6])) if empty_catch else "  ✅ 빈 catch 없음")
    if sendmsg:
        L.append(f"  ⚠ SendMessage {len(sendmsg)}곳 (문자열 호출 — 느리고 오타에 약함): "
                 + ", ".join(sendmsg[:6]))
    if debug_logs:
        L.append(f"  ℹ Debug.Log {debug_logs}곳 — 릴리스 전 정리 검토(로그도 비용·정보 노출)")
    warns = len(hot) + len(empty_update) + len(empty_catch) + len(sendmsg)
    L.append(f"  → 경고 {warns}건" if warns else "  → 깨끗 ✅")
    L.append("(위치는 unity_find로 열어 확인 — 매 프레임 패턴은 Start에서 캐시하는 게 정석)")
    return "\n".join(L)


# ── 초고속 C# 컴파일 검사 (dotnet + 유니티 DLL 참조, 유니티 안 띄움) ──
# unity_run은 유니티를 부팅해 6~21초+에디터 잠금이 걸립니다. 이건 dotnet(csc)로
# **그 파일 하나만** 유니티 DLL·게임 어셈블리를 참조해 컴파일 — 몇 초 만에 문법·타입
# 오류를 잡고, 에디터가 열려 있어도 됩니다. 정밀 최종 검증은 여전히 unity_run.
def _unity_refs(config, proj):
    """참조 DLL 목록: 에디터 Managed(UnityEngine·UnityEditor+모듈) + 게임 ScriptAssemblies."""
    import portable
    exe = exe_path(config, version=portable.project_unity_version(proj))
    refs = []
    if exe and os.path.isfile(exe):
        managed = os.path.join(os.path.dirname(exe), "Data", "Managed")
        for cand in ("UnityEngine.dll", "UnityEditor.dll"):
            p = os.path.join(managed, cand)
            if os.path.isfile(p):
                refs.append(p)
        mdir = os.path.join(managed, "UnityEngine")
        if os.path.isdir(mdir):
            refs += [os.path.join(mdir, f) for f in sorted(os.listdir(mdir))
                     if f.endswith(".dll")]
    sa = os.path.join(proj, "Library", "ScriptAssemblies")
    if os.path.isdir(sa):
        refs += [os.path.join(sa, f) for f in sorted(os.listdir(sa)) if f.endswith(".dll")]
    return refs


_CSPROJ_TMPL = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>netstandard2.1</TargetFramework>
    <LangVersion>9.0</LangVersion>
    <Nullable>disable</Nullable>
    <AllowUnsafeBlocks>true</AllowUnsafeBlocks>
    <EnableDefaultCompileItems>false</EnableDefaultCompileItems>
    <NoWarn>0436;1701;1702;0169;0649</NoWarn>
    <OutputType>Library</OutputType>
    <AssemblyName>LucyCsCheck</AssemblyName>
    <AppendTargetFrameworkToOutputPath>false</AppendTargetFrameworkToOutputPath>
    <CopyLocalLockFileAssemblies>false</CopyLocalLockFileAssemblies>
  </PropertyGroup>
  <ItemGroup>
{items}
  </ItemGroup>
</Project>
"""


def cs_check(config, project=None, path=None):
    """한 .cs 파일을 dotnet로 몇 초 만에 컴파일 검사(유니티 부팅 없음·에디터 켠 채 OK).
    ⚠검사 대상 파일만 새로 컴파일하고 나머지 게임 코드는 마지막 유니티 컴파일 산출물
    (ScriptAssemblies)을 참조하므로, '남의 파일까지 얽힌' 변경의 최종 확인은 unity_run."""
    proj = resolve_project(config, project)
    if not proj or not os.path.isdir(proj):
        return f"오류: 유니티 프로젝트를 찾지 못했습니다: {project!r}"
    full, err = _find_asset(proj, path, (".cs",))
    if err:
        return err
    rel = os.path.relpath(full, proj).replace(os.sep, "/")
    refs = _unity_refs(config, proj)
    if not any("UnityEngine" in r for r in refs):
        return ("오류: 유니티 에디터 DLL을 찾지 못했습니다(config unity.exe 확인) — "
                "이 검사는 유니티 설치가 필요합니다.")
    if not any(os.sep + "ScriptAssemblies" + os.sep in r for r in refs):
        # 게임 어셈블리가 없으면 게임 클래스 참조를 못 풀어 오탐이 납니다 — 정직하게 안내.
        note = ("\n  ℹ Library/ScriptAssemblies가 없어(유니티가 이 프로젝트를 아직 컴파일 안 함) "
                "게임 클래스 참조는 못 풉니다 — 에디터를 한 번 열거나 unity_run을 먼저.")
    else:
        note = ""

    work = _mem_dir("unity_cscheck", _proj_key(proj))
    items = [f'    <Compile Include="{full}" />']
    items += [f'    <Reference Include="{os.path.splitext(os.path.basename(r))[0]}">'
              f"<HintPath>{r}</HintPath><Private>false</Private></Reference>" for r in refs]
    with open(os.path.join(work, "check.csproj"), "w", encoding="utf-8") as f:
        f.write(_CSPROJ_TMPL.format(items="\n".join(items)))

    t0 = time.time()
    try:
        proc = subprocess.run(
            ["dotnet", "build", os.path.join(work, "check.csproj"), "-nologo", "-v:q",
             "--nologo"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=180, cwd=work,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except FileNotFoundError:
        return "오류: dotnet SDK가 없습니다(코딩 작업실 C#과 같은 전제) — winget install Microsoft.DotNet.SDK.9"
    except subprocess.TimeoutExpired:
        return "컴파일 검사가 3분을 넘겨 중단했습니다 — dotnet 첫 실행 캐시 문제일 수 있으니 다시 시도하세요."
    dur = time.time() - t0
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    errors, warnings = _parse_compile(out)
    if proc.returncode == 0 and not errors:
        return (f"[{rel}] 빠른 컴파일 검사 통과 ✅ ({dur:.1f}초, 유니티 안 띄움)" + note
                + "\n(문법·타입 수준 — 최종 확인은 unity_run. 에디터가 열려 있어도 되는 검사입니다.)")
    L = [f"[{rel}] 빠른 컴파일 검사 — 에러 {len(errors)}개 ({dur:.1f}초)"]
    L += ["  ✗ " + re.sub(r"\s*\[[^\]]*\.csproj\]\s*$", "", e) for e in errors[:20]]
    if len(errors) > 20:
        L.append(f"  …외 {len(errors) - 20}개")
    if not errors:                                # rc!=0인데 CS 진단이 없으면 빌드 자체 문제
        tail = [l for l in out.splitlines() if l.strip()][-5:]
        L += ["  (CS 진단 없이 실패 — 빌드 출력 꼬리)"] + ["  " + l for l in tail]
    L.append("(고친 뒤 다시 unity_cs_check — 몇 초면 됩니다)" + note)
    return "\n".join(L)


# ── 프로젝트 C# 쓰기/수정 (백업 + 저장 직후 자동 컴파일 검사) ────────
def _assets_cs_path(proj, path):
    """path를 Assets 안 .cs 절대경로로 정규화(탈출 차단) → (절대경로, 오류문)."""
    p = str(path or "").strip().strip('"\'').replace("\\", "/")
    if not p:
        return None, "오류: 파일 경로(path)가 필요합니다."
    if not p.lower().endswith(".cs"):
        p += ".cs"
    if not p.lower().startswith("assets/"):
        p = "Assets/Scripts/" + p.lstrip("/")
    full = os.path.abspath(os.path.join(proj, p.replace("/", os.sep)))
    assets_root = os.path.abspath(os.path.join(proj, "Assets"))
    if not full.startswith(assets_root + os.sep):
        return None, "오류: Assets 밖 경로는 안 됩니다(.. 탈출 차단)."
    return full, None


def cs_write(config, project, path, content):
    """프로젝트 Assets에 .cs를 만들거나 통째로 교체(기존 파일은 edits/에 백업) 후
    곧바로 cs_check — '쓰고 나서 컴파일 되는지'까지 한 번에. (확인은 tools 래퍼가 받음)"""
    proj = resolve_project(config, project)
    if not proj or not os.path.isdir(proj):
        return f"오류: 유니티 프로젝트를 찾지 못했습니다: {project!r}"
    full, err = _assets_cs_path(proj, path)
    if err:
        return err
    rel = os.path.relpath(full, proj).replace(os.sep, "/")
    content = str(content or "")
    if not content.strip():
        return "오류: content(파일 내용)가 비어 있습니다."
    existed = os.path.isfile(full)
    if existed:
        import shutil
        ts = time.strftime("%Y%m%d_%H%M%S")
        bdir = _mem_dir("unity_snapshots", _proj_key(proj), "edits", ts)
        shutil.copyfile(full, os.path.join(bdir, rel.replace("/", "_")))
        bnote = f"(이전 내용 백업: edits/{ts}) "
    else:
        os.makedirs(os.path.dirname(full), exist_ok=True)
        bnote = "(새 파일) "
    with open(full, "w", encoding="utf-8") as f:
        f.write(content if content.endswith("\n") else content + "\n")
    head = f"{rel} 저장 {bnote}— 이어서 빠른 컴파일 검사:\n"
    return head + cs_check(config, project, rel)


def cs_edit(config, project, path, find, replace, replace_all=False):
    """프로젝트 .cs에서 find→replace(백업) 후 곧바로 cs_check. 코딩 작업실 code_edit의
    유니티판 — 에러 한두 줄 고치고 몇 초 안에 컴파일 확인까지."""
    proj = resolve_project(config, project)
    if not proj or not os.path.isdir(proj):
        return f"오류: 유니티 프로젝트를 찾지 못했습니다: {project!r}"
    full, err = _find_asset(proj, path, (".cs",))
    if err:
        return err
    rel = os.path.relpath(full, proj).replace(os.sep, "/")
    find = str(find or "")
    if not find:
        return "오류: 찾을 문구(find)가 필요합니다."
    with open(full, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    n = text.count(find)
    if n == 0:
        return (f"'{find[:60]}'을(를) {rel}에서 못 찾았습니다 — unity_find나 read_file로 "
                "실제 원문을 확인해 그대로 넣어야 합니다.")
    if n > 1 and not replace_all:
        return (f"'{find[:60]}'이(가) {rel}에 {n}곳 있습니다 — 앞뒤를 더 붙여 좁히거나 "
                "all=true로 전부 바꾸세요.")
    import shutil
    ts = time.strftime("%Y%m%d_%H%M%S")
    bdir = _mem_dir("unity_snapshots", _proj_key(proj), "edits", ts)
    shutil.copyfile(full, os.path.join(bdir, rel.replace("/", "_")))
    with open(full, "w", encoding="utf-8") as f:
        f.write(text.replace(find, str(replace or "")))
    head = f"{rel}에서 {n}곳 바꿈(백업: edits/{ts}) — 이어서 빠른 컴파일 검사:\n"
    return head + cs_check(config, project, rel)


# ── 관련 코드 맥락 팩 (읽기전용) — 코드 짜기 전 한 방에 맥락 수집 ────
def context_pack(config, project=None, query=None, limit=15):
    """클래스·주제 하나에 대한 맥락 묶음: ①정의 파일의 전체 개요 ②그걸 쓰는 곳들
    ③파일의 네임스페이스·using 관례. 눈 없는 두뇌가 코드를 짜기 전에 이걸 한 번 보면
    없는 메서드를 지어내는(환각) 일이 크게 줄어듭니다."""
    proj = resolve_project(config, project)
    if not proj or not os.path.isdir(proj):
        return f"오류: 유니티 프로젝트를 찾지 못했습니다: {project!r}"
    q = str(query or "").strip()
    if not q:
        return "오류: query(클래스·타입·주제 이름)가 필요합니다."
    assets = os.path.join(proj, "Assets")
    def_re = re.compile(rf"\b(class|struct|interface|enum)\s+{re.escape(q)}\b")
    defs, users = [], []
    usings, namespaces = {}, {}
    for dp, _dirs, files in os.walk(assets):
        for fn in files:
            if not fn.endswith(".cs"):
                continue
            fp = os.path.join(dp, fn)
            rel = os.path.relpath(fp, proj).replace(os.sep, "/")
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError:
                continue
            for m in re.finditer(r"^\s*using\s+([\w.]+);", text, re.M):
                usings[m.group(1)] = usings.get(m.group(1), 0) + 1
            nm = re.search(r"^\s*namespace\s+([\w.]+)", text, re.M)
            if nm:
                namespaces[nm.group(1)] = namespaces.get(nm.group(1), 0) + 1
            if def_re.search(text):
                defs.append((rel, fp))
            elif re.search(rf"\b{re.escape(q)}\b", text):
                for i, ln in enumerate(text.splitlines(), 1):
                    if re.search(rf"\b{re.escape(q)}\b", ln) and not ln.strip().startswith("//"):
                        users.append(f"  {rel}:{i}: {ln.strip()[:110]}")
                        break                     # 파일당 대표 1줄

    L = [f"[{os.path.basename(proj)}] '{q}' 맥락 팩"]
    if defs:
        for rel, fp in defs[:3]:
            types, meths, fields = _outline_file(fp)
            L.append(f"◆ 정의: {rel}")
            L += [f"    {t}" for t in types]
            if fields:
                L.append("    직렬화/공개 필드: " + ", ".join(dict.fromkeys(fields))[:250])
            if meths:
                L.append("    메서드: " + ", ".join(meths[:30])[:600])
    else:
        L.append(f"◆ 정의 없음 — '{q}'라는 타입은 프로젝트에 없습니다(새로 만드는 이름이면 정상, "
                 "오타면 unity_find로 비슷한 이름을 찾아보세요).")
    if users:
        L.append(f"◆ 쓰는 곳 {len(users)}파일 (파일당 대표 1줄):")
        L += users[:limit]
        if len(users) > limit:
            L.append(f"  …외 {len(users) - limit}파일")
    elif defs:
        L.append("◆ 쓰는 곳 없음 — 아직 아무도 참조 안 함")
    top_ns = sorted(namespaces.items(), key=lambda kv: -kv[1])[:3]
    top_us = sorted(usings.items(), key=lambda kv: -kv[1])[:8]
    if top_ns:
        L.append("◆ 프로젝트 관례: namespace " + ", ".join(f"{n}({c})" for n, c in top_ns)
                 + " · 자주 쓰는 using: " + ", ".join(u for u, _c in top_us))
    L.append("(개요 수준 — 본문이 필요하면 read_document, 짠 뒤에는 unity_cs_check로 몇 초 검증)")
    return "\n".join(L)
