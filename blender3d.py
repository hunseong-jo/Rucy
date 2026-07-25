# -*- coding: utf-8 -*-
"""블렌더 연결 — 루시가 .blend 파일을 열어보지 않고도 확인(info)·미리보기(render)·
유니티용 내보내기(export)를 해 줍니다.

사상은 멜로 목소리·ffmpeg(edit_video)와 같습니다: 무거운 프로그램은 루시 밖에 있고,
루시는 안전한 명령만 만들어 넘깁니다. 두뇌(모델)는 bpy 코드를 짓지 않습니다 —
재료(경로·형식·장수)만 주면 고정 러너(blender_runner.py)가 수행합니다(주입 차단).
세 동작 전부 **원본 .blend를 절대 고치지 않습니다**(읽고, 옆에 새 파일만 만듦).
"""
import json
import os
import re
import shutil
import subprocess
import time
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.join(BASE_DIR, "blender_runner.py")

# '수술'(모델을 실제로 바꾸는) 동작들 — 러너가 save_mainfile로 저장하므로 **반드시 사본** 위에서만.
# auto_weight는 리깅의 '기계적 절반'(살 붙이기만 자동), bone_template은 그 앞 단계(표준 뼈대를
# 몸 크기에 맞춰 배치 — 출발점일 뿐 정밀 조정은 사람 몫). tex_resize는 큰 텍스처 줄이기.
SURGERY = ("apply", "origin", "scale_to", "cleanup", "uv", "decimate", "join", "auto_weight",
           "bone_template", "tex_resize",
           # 세션59 2부: 조형·배치(mirror·array·scatter)/유니티(collider·materials·split)/
           # 애니·리깅(anim_edit·weight_transfer) — 전부 사본 위 수술.
           "mirror", "array", "scatter", "collider", "materials", "split",
           "anim_edit", "weight_transfer",
           # 세션61: 수리(repair)/CSG(boolean)/경로(curve_path)/부착점(sockets)/
           # 아틀라스(uv_atlas)/PBR 배선(material_pbr) — 역시 사본 위 수술.
           "repair", "boolean", "curve_path", "sockets", "uv_atlas", "material_pbr",
           # 세션63: 마감(bevel·solidify·shade)/유니티(lightmap_uv·rename·normals)/
           # 배치(align)/청소(purge)/애니·물리(pose_apply·physics_bake).
           "bevel", "solidify", "shade", "lightmap_uv", "rename", "normals",
           "align", "purge", "pose_apply", "physics_bake",
           # 세션67: 절차적 유기 디테일 — 브러시 스컬프의 헤드리스 대체(표면만, 형태 창작 아님).
           "sculpt_displace",
           # 도형 정밀 편집 수술 4종 (taper, extrude_face, inset_face, deform_mesh)
           "taper", "extrude_face", "inset_face", "deform_mesh")


# ── 기능 목록(유일 원본) — action=help가 이걸 그대로 보여 줍니다. ─────────────────
# ⭐왜 있나(세션67): 도구 설명이 4,000자를 넘어 작은 두뇌가 **자기가 가진 기능을 회상하지
#   못했습니다** — bake·uv_atlas·uv가 멀쩡히 있는데 "없으니 추가해 달라"고 답한 실측이 있음.
#   회상은 못 믿으니 **조회**하게 만듭니다. 새 action을 더하면 여기도 반드시 한 줄 추가할 것.
CATALOG = [
    ("확인(읽기만·확인 불필요)", [
        ("info", "구성·폴리·재질·UV 확인"),
        ("check", "유니티 반입 점검(진단만)"),
        ("compare", "두 .blend 차이표(path2)"),
        ("render", "점검용 미리보기 PNG"),
        ("anim_preview", "움직임을 GIF로"),
        ("beauty_render", "기획서용 렌더(3점 조명·투명 배경)"),
    ]),
    ("만들기", [
        ("build", "치수 스펙으로 프리미티브 조립(각진 소품·그레이박스 수준)"),
        ("text3d", "3D 글자 간판(한글 됨)"),
        ("assemble", "여러 3D 파일을 좌표대로 한 씬에"),
    ]),
    ("표면 디테일·마감", [
        ("sculpt_displace", "⭐유기적 요철 — 빵 골결·주름·돌기·알갱이(pattern=bumpy/wrinkle/groove/cell/rough)"),
        ("bevel", "모서리 챔퍼(각진 티 제거)"),
        ("solidify", "두께 입히기"),
        ("shade", "부드럽게/각지게 셰이딩"),
        ("normals", "뒤집힌 면 진단+수리"),
        ("repair", "구멍·퇴화면·비매니폴드 수리"),
    ]),
    ("텍스처·재질·UV", [
        ("uv", "UV 자동 펼침(smart project)"),
        ("bake", "⭐하이폴리 디테일을 로우폴리 normal/AO PNG로 굽기"),
        ("uv_atlas", "⭐여러 재질을 아틀라스 한 장으로 통합(드로우콜↓)"),
        ("materials", "중복 재질 병합·영문화·색 변경"),
        ("material_pbr", "텍스처 폴더 → Principled 자동 배선"),
        ("lightmap_uv", "유니티 라이트맵용 UV2"),
        ("tex_resize", "큰 텍스처 축소"),
    ]),
    ("형태 편집", [
        ("boolean", "CSG 뚫기/합치기"), ("mirror", "대칭 완성"),
        ("array", "복제 배열"), ("scatter", "영역에 랜덤 배치"),
        ("curve_path", "경로 → 관/띠/배열"), ("align", "바닥 스냅·일렬·격자 정렬"),
        ("join", "한 덩어리로"), ("split", "조각·재질별 분리"),
        ("decimate", "폴리 줄이기"), ("lod", "LOD0/1/2 한 FBX로"),
        ("taper", "상/하단 경사 변형(top_factor, bottom_factor)"),
        ("extrude_face", "지정 방향 면 돌출(face, distance, scale)"),
        ("inset_face", "지정 방향 면 인셋/음각(face, thickness, depth)"),
        ("deform_mesh", "변형 모디파이어(mode=bend/twist/taper/stretch, angle_deg, axis)"),
    ]),
    ("리깅·애니", [
        ("bone_template", "표준 뼈대 배치"), ("auto_weight", "자동 웨이트"),
        ("weight_transfer", "웨이트 근접 전사(옷·장비)"),
        ("pose_apply", "포즈 JSON → 키프레임"), ("anim_edit", "개명·트림·루프화"),
        ("anim_merge", "애니 FBX 여러 개를 클립으로 합본"),
        ("physics_bake", "낙하 안착·천 드리움 굽기"),
    ]),
    ("유니티 내보내기·정리", [
        ("prep_unity", "원클릭 정리+FBX"), ("unity_export", "텍스처 갈색 사고 방지 내보내기"),
        ("export", "FBX/GLB"), ("convert", "fbx·obj·glb·stl 형식변환"),
        ("collider", "저폴리 콘벡스 헐"), ("sockets", "부착점 Empty"),
        ("apply", "스케일·회전 적용"), ("origin", "바닥중심을 원점으로"),
        ("scale_to", "키를 m로"), ("cleanup", "중복정점·법선 정리"),
        ("rename", "ASCII 일괄 개명"), ("purge", "고아 데이터 청소"),
        ("chain", "여러 수술 한 번에"),
    ]),
]

# 도구가 **못 하는 것** — 없는 기능을 있다고 하거나, 있는 기능을 없다고 하는 것 둘 다 막습니다.
CANNOT = ("브러시 스컬프(사람 손 전제)·리토폴로지·헤어/파티클·텍스처 페인팅은 없습니다. "
          "유기적 '형태'를 창작하지는 못합니다 — build로 덩어리를 잡고 sculpt_displace로 "
          "표면만 유기적으로 만드는 것까지가 한계입니다. "
          "⭐형태 설계(무엇이 어떻게 생겼는가)는 도구가 아니라 설계자 몫입니다.")


def catalog_text():
    """action=help가 돌려줄 기능 목록 — 블렌더를 켜지 않고 즉시 답합니다(공짜·빠름)."""
    L = ["블렌더 도구가 지금 할 수 있는 일 전부(회상하지 말고 이 목록을 보세요):"]
    for group, items in CATALOG:
        L.append(f"\n■ {group}")
        for name, desc in items:
            L.append(f"  · {name} — {desc}")
    L.append("\n■ 못 하는 것\n  " + CANNOT)
    L.append("\n자세한 인자는 도구 설명에 있습니다. 수술은 원본을 복사한 사본에만 반영됩니다.")
    return "\n".join(L)


def work_copy(blend_path, suffix="_수정"):
    """수술용 사본을 원본 옆에 만들어 그 경로를 돌려줍니다. 원본은 절대 열지 않습니다."""
    folder = os.path.dirname(blend_path)
    stem = os.path.splitext(os.path.basename(blend_path))[0]
    dest = os.path.join(folder, f"{stem}{suffix}.blend")
    n = 2
    while os.path.exists(dest):
        dest = os.path.join(folder, f"{stem}{suffix}{n}.blend")
        n += 1
    shutil.copy2(blend_path, dest)
    return dest

# 사용자 PC의 실제 설치 자리(폴더명 오타까지 실측 그대로). 다른 PC면 config blender.exe로.
def find_exe(config=None):
    """블렌더 실행파일을 찾습니다. config에 적어두면 최우선, 없으면 자동 탐지(portable)."""
    import portable
    conf = (config or {}).get("blender", {})
    exe = portable.expand(conf.get("exe")) if conf.get("exe") else None
    if exe and os.path.isfile(exe):
        return exe
    return portable.find_blender()          # PATH·Unity Hub 밖·흔한 설치 위치 자동 탐지


INSTALL_GUIDE = ("블렌더가 안 보여 3D 파일을 다룰 수 없습니다. 설치: "
                 "winget install -e --id BlenderFoundation.Blender "
                 "(설치돼 있다면 config의 blender.exe에 경로를 적어 주세요)")


def run(action, blend_path, config=None, timeout=300, **opts):
    """러너를 돌리고 결과 dict를 돌려줍니다. 실패는 RuntimeError(마지막 출력 몇 줄 포함)."""
    exe = find_exe(config)
    if not exe:
        raise RuntimeError(INSTALL_GUIDE)
    if blend_path and not os.path.isfile(blend_path):
        raise RuntimeError(f"파일이 없습니다: {blend_path}")

    payload = dict(opts)
    payload["action"] = action
    args_file = os.path.join(BASE_DIR, "memory", f"_b3d_{uuid.uuid4().hex[:8]}.json")
    os.makedirs(os.path.dirname(args_file), exist_ok=True)
    with open(args_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    cmd = [exe, "--background"]
    cmd += [blend_path] if blend_path else ["--factory-startup"]   # convert는 파일 없이 빈 시작
    cmd += ["--python", RUNNER, "--", args_file]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        text = (proc.stdout or b"").decode("utf-8", "replace")
        m = re.search(r"B3D_RESULT (\{.*\})", text)
        if not m:
            tail = [l for l in (text + (proc.stderr or b"").decode("utf-8", "replace")).splitlines()
                    if l.strip()][-4:]
            raise RuntimeError("블렌더 실행 실패: " + " / ".join(tail))
        return json.loads(m.group(1))
    finally:
        try:
            os.remove(args_file)
        except OSError:
            pass


def summarize_info(r):
    """info 결과를 사람이 읽을 요약으로 — 두뇌가 이걸 보고 답합니다."""
    lines = [f"오브젝트 {len(r['objects'])}개 · 총 폴리곤 {r['total_polys']:,}"
             + (f"(삼각형 {r['total_tris']:,})" if r.get("total_tris") else "") + " · "
             f"최대 크기 {r['max_dimension']}m · 재질 {len(r['materials'])}종 · "
             + (f"본 {r['bones']}개 · " if r.get("bones") else "")
             + f"카메라 {r['cameras']}·조명 {r['lights']} · 애니메이션 {len(r['actions'])}개"]
    for o in r["objects"][:20]:
        row = f"  - {o['name']} ({o['type']}"
        if "polys" in o:
            row += f", {o['polys']:,}폴리"
        row += ")"
        if o.get("scale_unapplied"):
            row += f" ⚠스케일 미적용 {o['scale_unapplied']}"
        lines.append(row)
    if len(r["objects"]) > 20:
        lines.append(f"  …외 {len(r['objects']) - 20}개")
    if r["materials"]:
        lines.append("  재질: " + ", ".join(r["materials"][:10]))
    if r["no_uv"]:
        lines.append(f"  ⚠UV 없는 메시: {', '.join(r['no_uv'][:8])} — 텍스처를 입히려면 UV 필요")
    if r["actions"]:
        lines.append("  애니메이션: " + ", ".join(r["actions"][:8]))
    return "\n".join(lines)
