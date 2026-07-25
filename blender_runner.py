# -*- coding: utf-8 -*-
"""블렌더 안에서 도는 고정 러너 — blender3d.py가 부릅니다(직접 실행 금지).

    blender --background 파일.blend --python blender_runner.py -- 인자.json

두뇌(모델)는 bpy 코드를 짓지 않습니다 — 인자 json(action·경로·옵션)만 만들고,
실제 bpy 호출은 전부 이 파일의 고정 코드입니다(edit_video의 주입 차단 원칙).
결과는 stdout 한 줄 'B3D_RESULT {json}'로 돌려줍니다.
"""
import json
import math
import os
import sys

import bpy

args = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
action = args["action"]
out = {"action": action}

def scene_bbox():
    """보이는 메시 전체의 (중심, 최대 치수). 카메라를 알아서 놓을 때 씁니다."""
    lo = [1e9] * 3
    hi = [-1e9] * 3
    for o in bpy.context.scene.objects:
        if o.type != 'MESH' or o.hide_render:
            continue
        for corner in o.bound_box:
            w = o.matrix_world @ __import__("mathutils").Vector(corner)
            for i in range(3):
                lo[i] = min(lo[i], w[i])
                hi[i] = max(hi[i], w[i])
    if lo[0] > hi[0]:
        return (0, 0, 0), 2.0
    center = [(lo[i] + hi[i]) / 2 for i in range(3)]
    size = max(hi[i] - lo[i] for i in range(3))
    return center, max(size, 0.1)


def scene_extents():
    """보이는 메시 전체의 (lo[x,y,z], hi[x,y,z]) — 본 배치처럼 축별 치수가 필요할 때."""
    from mathutils import Vector
    lo = [1e9] * 3
    hi = [-1e9] * 3
    for o in bpy.context.scene.objects:
        if o.type != 'MESH' or o.hide_render:
            continue
        for corner in o.bound_box:
            w = o.matrix_world @ Vector(corner)
            for i in range(3):
                lo[i] = min(lo[i], w[i])
                hi[i] = max(hi[i], w[i])
    if lo[0] > hi[0]:
        return [0, 0, 0], [1, 1, 1]
    return lo, hi


def sel_only(objs):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    if objs:
        bpy.context.view_layer.objects.active = objs[0]


def safe_fbx_import(filepath):
    """FBX 임포트 — 헤드리스 블렌더 5.0.1은 FBX 안에 라이트가 있으면 blen_read_light에서
    죽습니다(세션59 실측). 라이트 읽기만 감싸서 실패하면 껍데기 라이트로 대체합니다."""
    try:
        import io_scene_fbx.import_fbx as _ifbx
        if hasattr(_ifbx, "blen_read_light") and not getattr(_ifbx, "_b3d_patched", False):
            _orig = _ifbx.blen_read_light

            def _tolerant(*a, **k):
                try:
                    return _orig(*a, **k)
                except Exception:
                    return bpy.data.lights.new("FBX_Light", 'POINT')
            _ifbx.blen_read_light = _tolerant
            _ifbx._b3d_patched = True
    except Exception:
        pass
    bpy.ops.import_scene.fbx(filepath=filepath)


def act_fcurves_of(a):
    """블렌더 4.4+ 레이어·슬롯 액션과 구형 양쪽에서 f-커브 목록 — anim_edit의 다리 재사용."""
    if hasattr(a, "fcurves") and len(getattr(a, "fcurves", [])):
        return list(a.fcurves)
    fcs = []
    for layer in getattr(a, "layers", []):
        for strip in layer.strips:
            for cb in getattr(strip, "channelbags", []):
                fcs.extend(cb.fcurves)
    return fcs


def import_any(src):
    """fbx·obj·glb·gltf·stl을 형식 보고 불러옵니다(공용)."""
    ext = os.path.splitext(src)[1].lower()
    if ext == ".fbx":
        safe_fbx_import(src)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=src)
    elif ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=src)
    elif ext == ".stl":
        bpy.ops.wm.stl_import(filepath=src)
    else:
        raise RuntimeError(f"불러올 수 없는 형식: {ext}")


def make_camera(center, size, deg=40):
    """중심을 바라보는 카메라(+태양·월드가 없으면 채움). 새 동작들의 공용 뷰 설정."""
    from mathutils import Vector
    scene = bpy.context.scene
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    scene.camera = cam
    tgt = bpy.data.objects.new("B3D_VT", None)
    scene.collection.objects.link(tgt)
    tgt.location = Vector(center)
    tr = cam.constraints.new('TRACK_TO')
    tr.target = tgt
    tr.track_axis = 'TRACK_NEGATIVE_Z'
    tr.up_axis = 'UP_Y'
    a = math.radians(deg)
    dist = size * 2.1
    cam.location = (center[0] + math.sin(a) * dist, center[1] - math.cos(a) * dist,
                    center[2] + size * 0.35)
    if not any(o.type == 'LIGHT' for o in scene.objects):
        bpy.ops.object.light_add(type='SUN', location=(center[0] + size,
                                                       center[1] - size * 1.5,
                                                       center[2] + size * 2))
        bpy.context.object.data.energy = 3.0
        bpy.context.object.rotation_euler = (math.radians(45), math.radians(8), math.radians(25))
    if not scene.world:
        scene.world = bpy.data.worlds.new("B3D_W")
        scene.world.use_nodes = True
    scene.render.engine = 'BLENDER_EEVEE'
    scene.view_settings.view_transform = 'Standard'
    return cam


def preview_shots(out_dir, stem, angles=2, size=512):
    """front·quarter 미리보기 몇 장 — build/assemble이 결과를 눈으로 보여줄 때."""
    scene = bpy.context.scene
    center, sz = scene_bbox()
    cam = make_camera(center, sz)
    scene.render.resolution_x = scene.render.resolution_y = int(size)
    scene.eevee.taa_render_samples = 16
    dist = sz * 2.1
    files = []
    for label, deg in (("front", 0), ("quarter", 40), ("side", 90), ("back", 180))[:max(1, min(int(angles), 4))]:
        a = math.radians(deg)
        cam.location = (center[0] + math.sin(a) * dist, center[1] - math.cos(a) * dist,
                        center[2] + sz * 0.35)
        fp = os.path.join(out_dir, f"{stem}_{label}.png")
        scene.render.filepath = fp
        bpy.ops.render.render(write_still=True)
        files.append(fp)
def build_chair_preset(args):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    seat_w = float(args.get("seat_w", 0.5))
    seat_d = float(args.get("seat_d", 0.5))
    seat_th = float(args.get("seat_th", 0.05))
    leg_h = float(args.get("leg_h", 0.45))
    leg_w = float(args.get("leg_w", 0.04))
    back_h = float(args.get("back_h", 0.45))
    back_th = float(args.get("back_th", 0.04))

    made = []
    x_off = (seat_w - leg_w) / 2.0
    y_off = (seat_d - leg_w) / 2.0
    leg_z = leg_h / 2.0

    for idx, (sign_x, sign_y) in enumerate([(1, 1), (-1, 1), (1, -1), (-1, -1)]):
        bpy.ops.mesh.primitive_cube_add()
        leg = bpy.context.object
        leg.name = f"Leg_{idx+1}"
        leg.dimensions = [leg_w, leg_w, leg_h]
        leg.location = [sign_x * x_off, sign_y * y_off, leg_z]
        made.append(leg)

    bpy.ops.mesh.primitive_cube_add()
    seat = bpy.context.object
    seat.name = "Seat"
    seat.dimensions = [seat_w, seat_d, seat_th]
    seat.location = [0.0, 0.0, leg_h + seat_th / 2.0]
    made.append(seat)

    bpy.ops.mesh.primitive_cube_add()
    back = bpy.context.object
    back.name = "Backrest"
    back.dimensions = [seat_w, back_th, back_h]
    back.location = [0.0, (seat_d - back_th) / 2.0, leg_h + seat_th + back_h / 2.0]
    made.append(back)

    bpy.context.view_layer.update()
    sel_only(made)
    bpy.context.view_layer.objects.active = seat
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.join()
    final_chair = bpy.context.object
    final_chair.name = "Chair"
    return [final_chair]


def build_table_preset(args):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    top_w = float(args.get("top_w", 1.2))
    top_d = float(args.get("top_d", 0.7))
    top_th = float(args.get("top_th", 0.05))
    leg_h = float(args.get("leg_h", 0.7))
    leg_w = float(args.get("leg_w", 0.06))

    made = []
    x_off = (top_w - leg_w * 2.0) / 2.0
    y_off = (top_d - leg_w * 2.0) / 2.0
    leg_z = leg_h / 2.0

    for idx, (sign_x, sign_y) in enumerate([(1, 1), (-1, 1), (1, -1), (-1, -1)]):
        bpy.ops.mesh.primitive_cube_add()
        leg = bpy.context.object
        leg.name = f"Leg_{idx+1}"
        leg.dimensions = [leg_w, leg_w, leg_h]
        leg.location = [sign_x * x_off, sign_y * y_off, leg_z]
        made.append(leg)

    bpy.ops.mesh.primitive_cube_add()
    top = bpy.context.object
    top.name = "TableTop"
    top.dimensions = [top_w, top_d, top_th]
    top.location = [0.0, 0.0, leg_h + top_th / 2.0]
    made.append(top)

    bpy.context.view_layer.update()
    sel_only(made)
    bpy.context.view_layer.objects.active = top
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.join()
    final_table = bpy.context.object
    final_table.name = "Table"
    return [final_table]


def build_hex_nut_preset(args):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    radius = float(args.get("radius", 0.5))
    height = float(args.get("height", 0.4))
    dome = bool(args.get("dome", True))
    dome_h = float(args.get("dome_height", 0.3))

    bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=radius, depth=height, location=[0, 0, height / 2.0])
    nut = bpy.context.object
    nut.name = "HexNut"

    if dome:
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type='FACE')
        bpy.ops.mesh.select_all(action='DESELECT')

        import bmesh
        bm = bmesh.from_edit_mesh(nut.data)
        bm.faces.ensure_lookup_table()
        for f in bm.faces:
            if f.normal.z > 0.8:
                f.select = True
        bmesh.update_edit_mesh(nut.data)

        bpy.ops.mesh.extrude_region_move()
        bpy.ops.transform.resize(value=(0.75, 0.75, 1.0))
        bpy.ops.transform.translate(value=(0, 0, dome_h * 0.7))

        bpy.ops.mesh.extrude_region_move()
        bpy.ops.transform.resize(value=(0.7, 0.7, 1.0))
        bpy.ops.transform.translate(value=(0, 0, dome_h * 0.3))

        bpy.ops.object.mode_set(mode='OBJECT')

    bpy.ops.mesh.primitive_cone_add(vertices=64, radius1=radius * 1.5, radius2=0.0, depth=radius * 1.2, location=[0, 0, height + radius * 0.4])
    cutter = bpy.context.object
    cutter.name = "ConicalCutter"
    cutter.rotation_euler[0] = math.radians(180)

    bpy.context.view_layer.update()
    sel_only([nut])
    bpy.context.view_layer.objects.active = nut

    mod_bool = nut.modifiers.new("cone_cut", 'BOOLEAN')
    mod_bool.operation = 'DIFFERENCE'
    mod_bool.object = cutter
    try:
        bpy.ops.object.modifier_apply(modifier="cone_cut")
    except Exception:
        pass

    bpy.data.objects.remove(cutter, do_unlink=True)

    bpy.context.view_layer.update()
    sel_only([nut])
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    try:
        bpy.ops.object.shade_auto_smooth(angle=math.radians(35))
    except AttributeError:
        bpy.ops.object.shade_smooth()

    mod = nut.modifiers.new("nut_bevel", 'BEVEL')
    mod.limit_method = 'ANGLE'
    mod.angle_limit = math.radians(20)
    mod.width = radius * 0.04
    mod.segments = 3
    try:
        bpy.ops.object.modifier_apply(modifier="nut_bevel")
    except Exception:
        pass

    return [nut]


if action == "info":
    objs = []
    total = 0
    total_tris = 0                                # 유니티·모바일 예산은 삼각형 기준이라 정확히 셉니다
    no_uv = []
    bones = 0
    for o in bpy.context.scene.objects:
        row = {"name": o.name, "type": o.type}
        if o.type == 'MESH':
            row["polys"] = len(o.data.polygons)
            row["tris"] = sum(len(p.vertices) - 2 for p in o.data.polygons)
            total += row["polys"]
            total_tris += row["tris"]
            if not o.data.uv_layers:
                no_uv.append(o.name)
            s = o.scale
            if any(abs(v - 1.0) > 1e-4 for v in s):
                row["scale_unapplied"] = [round(v, 3) for v in s]
        elif o.type == 'ARMATURE':
            bones += len(o.data.bones)
        objs.append(row)
    center, size = scene_bbox()
    out.update({
        "objects": objs,
        "total_polys": total,
        "total_tris": total_tris,
        "bones": bones,
        "materials": [m.name for m in bpy.data.materials if m.users],
        "max_dimension": round(size, 3),
        "cameras": sum(1 for o in bpy.context.scene.objects if o.type == 'CAMERA'),
        "lights": sum(1 for o in bpy.context.scene.objects if o.type == 'LIGHT'),
        "no_uv": no_uv,
        "actions": [a.name for a in bpy.data.actions],
    })

elif action == "render":
    scene = bpy.context.scene
    center, size = scene_bbox()
    # 파일에 카메라·조명이 없으면 만들어 줍니다 — 작업 중 blend는 대개 둘 다 없습니다.
    cam = next((o for o in scene.objects if o.type == 'CAMERA'), None)
    made_cam = cam is None
    if made_cam:
        bpy.ops.object.camera_add()
        cam = bpy.context.object
        tgt = bpy.data.objects.new("B3D_Target", None)
        scene.collection.objects.link(tgt)
        tgt.location = center
        tr = cam.constraints.new('TRACK_TO')
        tr.target = tgt
        tr.track_axis = 'TRACK_NEGATIVE_Z'
        tr.up_axis = 'UP_Y'
    scene.camera = cam
    if not any(o.type == 'LIGHT' for o in scene.objects):
        bpy.ops.object.light_add(type='SUN', location=(center[0] + size, center[1] - size * 1.5,
                                                       center[2] + size * 2))
        bpy.context.object.data.energy = 3.0
        bpy.context.object.rotation_euler = (math.radians(45), math.radians(8), math.radians(25))
    if not scene.world:
        scene.world = bpy.data.worlds.new("B3D_W")
        scene.world.use_nodes = True

    scene.render.engine = 'BLENDER_EEVEE'       # 미리보기 목적 — 빠른 엔진으로 통일
    scene.render.resolution_x = scene.render.resolution_y = int(args.get("size", 512))
    scene.eevee.taa_render_samples = 16
    scene.view_settings.view_transform = 'Standard'    # AgX가 채도 높은 색을 물빠지게 함(실측)

    dist = size * 2.1
    files = []
    for label, deg in (("front", 0), ("quarter", 40), ("side", 90), ("back", 180))[: int(args.get("angles", 4))]:
        if made_cam:
            a = math.radians(deg)
            cam.location = (center[0] + math.sin(a) * dist,
                            center[1] - math.cos(a) * dist,
                            center[2] + size * 0.35)
        fp = os.path.join(args["out_dir"], f"{args['stem']}_{label}.png")
        scene.render.filepath = fp
        bpy.ops.render.render(write_still=True)
        files.append(fp)
        if not made_cam:
            break                               # 파일에 카메라가 있으면 그 시점 한 장만
    out["renders"] = files

elif action == "export":
    fmt = args.get("format", "fbx")
    dest = args["dest"]
    for o in bpy.context.scene.objects:         # 메시+아마추어+부착점(Empty) — 조명·카메라는 불필요
        o.select_set(o.type in ('MESH', 'ARMATURE')
                     or (o.type == 'EMPTY' and not o.name.startswith("B3D_")))
    if fmt == "glb":
        bpy.ops.export_scene.gltf(filepath=dest, use_selection=True)
    else:
        bpy.ops.export_scene.fbx(filepath=dest, use_selection=True,
                                 add_leaf_bones=False, apply_scale_options='FBX_SCALE_ALL',
                                 axis_forward='-Z', axis_up='Y',
                                 primary_bone_axis='Y', secondary_bone_axis='X')
    out["exported"] = dest

elif action == "convert":
    # 다른 형식(fbx·obj·glb·stl)을 불러와 원하는 형식으로 — 에셋 파일 호환용.
    bpy.ops.object.select_all(action='SELECT')   # 빈 시작의 기본 큐브·카메라·조명 제거
    bpy.ops.object.delete()
    src = args["src"]
    ext = os.path.splitext(src)[1].lower()
    if ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=src)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=src)
    elif ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=src)
    elif ext == ".stl":
        bpy.ops.wm.stl_import(filepath=src)
    else:
        raise RuntimeError(f"불러올 수 없는 형식: {ext}")
    fmt = args.get("format", "fbx")
    dest = args["dest"]
    for o in bpy.context.scene.objects:
        o.select_set(o.type in ('MESH', 'ARMATURE'))
    if fmt == "glb":
        bpy.ops.export_scene.gltf(filepath=dest, use_selection=True)
    elif fmt == "obj":
        bpy.ops.wm.obj_export(filepath=dest, export_selected_objects=True)
    else:
        bpy.ops.export_scene.fbx(filepath=dest, use_selection=True,
                                 add_leaf_bones=False, apply_scale_options='FBX_SCALE_ALL')
    out["exported"] = dest
    out["objects"] = sum(1 for o in bpy.context.scene.objects if o.type == 'MESH')

elif action == "check":                          # 유니티 반입 린트 — 읽기만, 안 고침·저장 안 함
    import bmesh
    from mathutils import Vector
    scene = bpy.context.scene
    meshes = [o for o in scene.objects if o.type == 'MESH']
    unapplied = [o.name for o in meshes if any(abs(s - 1.0) > 1e-4 for s in o.scale)]
    ngons = sum(1 for o in meshes for p in o.data.polygons if len(p.vertices) > 4)
    tris = sum(1 for o in meshes for p in o.data.polygons if len(p.vertices) == 3)
    no_uv = [o.name for o in meshes if not o.data.uv_layers]
    nonmanifold = loose = 0
    for o in meshes:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        nonmanifold += sum(1 for e in bm.edges if not e.is_manifold)
        loose += sum(1 for v in bm.verts if not v.link_faces)
        bm.free()
    mats = sorted({m.name for o in meshes for m in o.data.materials if m})
    lo_z = min((o.matrix_world @ Vector(c)).z
               for o in meshes for c in o.bound_box) if meshes else 0.0
    center, _ = scene_bbox()
    out["check"] = {
        "meshes": len(meshes), "polys": sum(len(o.data.polygons) for o in meshes),
        "ngons": ngons, "tris": tris, "unapplied_scale": unapplied, "no_uv": no_uv,
        "nonmanifold_edges": nonmanifold, "loose_verts": loose, "materials": mats,
        "bottom_z": round(lo_z, 4), "center_xy": [round(center[0], 4), round(center[1], 4)],
    }

elif action == "anim_frames":
    # 애니메이션(또는 정지 모델의 턴테이블)을 프레임 그림들로 — GIF 조립은 밖(ffmpeg)에서.
    # 읽기만 — 저장 안 함. 눈 없는 루시 대신 사람이 움직임을 확인하는 통로입니다.
    scene = bpy.context.scene
    n = max(4, min(int(args.get("frames", 12)), 24))
    size = int(args.get("size", 384))
    mode = str(args.get("mode", "")).lower()
    if mode not in ("anim", "turntable"):
        mode = "anim" if bpy.data.actions else "turntable"
    if mode == "anim" and not bpy.data.actions:
        mode = "turntable"                       # 애니가 없으면 정직하게 돌려보기로

    center, sz = scene_bbox()
    cam = make_camera(center, sz)
    scene.render.resolution_x = scene.render.resolution_y = size
    scene.eevee.taa_render_samples = 16
    dist = sz * 2.1
    files = []
    if mode == "anim":
        fs = int(min(a.frame_range[0] for a in bpy.data.actions))
        fe = int(max(a.frame_range[1] for a in bpy.data.actions))
        if fe <= fs:
            fs, fe = scene.frame_start, max(scene.frame_end, scene.frame_start + 1)
        for i in range(n):
            scene.frame_set(round(fs + (fe - fs) * i / (n - 1)))
            fp = os.path.join(args["out_dir"], f"{args['stem']}_f{i:02d}.png")
            scene.render.filepath = fp
            bpy.ops.render.render(write_still=True)
            files.append(fp)
        out["frame_range"] = [fs, fe]
        out["actions"] = [a.name for a in bpy.data.actions]
    else:                                        # 턴테이블 — 카메라가 360° 돌며 찍음
        for i in range(n):
            a = math.radians(360.0 * i / n)
            cam.location = (center[0] + math.sin(a) * dist, center[1] - math.cos(a) * dist,
                            center[2] + sz * 0.35)
            fp = os.path.join(args["out_dir"], f"{args['stem']}_f{i:02d}.png")
            scene.render.filepath = fp
            bpy.ops.render.render(write_still=True)
            files.append(fp)
    out["mode"] = mode
    out["frames"] = files

elif action == "lod":
    # LOD 0/1/2를 유니티 자동 인식 이름(메시명_LODn)으로 한 FBX에 — 원본 저장 안 함.
    scene = bpy.context.scene
    meshes = [o for o in scene.objects if o.type == 'MESH']
    if not meshes:
        raise RuntimeError("LOD를 만들 메시가 없습니다.")
    ratios = args.get("lods") or [1.0, 0.5, 0.25]
    ratios = [min(max(float(r), 0.02), 1.0) for r in ratios][:4]
    levels = []
    all_objs = []
    for li, ratio in enumerate(ratios):
        objs = []
        for src_o in meshes:
            if li == 0:
                o = src_o
            else:
                o = src_o.copy()
                o.data = src_o.data.copy()
                scene.collection.objects.link(o)
            o.name = f"{src_o.name.split('_LOD')[0]}_LOD{li}"
            if li > 0 and ratio < 0.999:
                sel_only([o])
                mod = o.modifiers.new("dec", 'DECIMATE')
                mod.ratio = ratio
                bpy.ops.object.modifier_apply(modifier="dec")
            objs.append(o)
        levels.append({"level": li, "ratio": ratio,
                       "polys": sum(len(o.data.polygons) for o in objs)})
        all_objs += objs
    dest = args["dest"]
    sel_only(all_objs + [o for o in scene.objects if o.type == 'ARMATURE'])
    bpy.ops.export_scene.fbx(filepath=dest, use_selection=True,
                             add_leaf_bones=False, apply_scale_options='FBX_SCALE_ALL')
    # 자가검증 — 내보낸 FBX를 빈 씬에 다시 불러 LOD 이름이 실제로 붙었는지 실측
    verify = {}
    try:
        bpy.ops.wm.read_homefile(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=dest)
        names = [o.name for o in bpy.context.scene.objects if o.type == 'MESH']
        verify = {"meshes": len(names),
                  "lod_named": sum(1 for x in names if "_LOD" in x),
                  "ok": len(names) > 0 and all("_LOD" in x for x in names)}
    except Exception as e:
        verify = {"error": str(e)}
elif action == "build":
    subject = str(args.get("subject") or args.get("preset") or "").lower()
    shape_param = str(args.get("shape") or "").lower()
    parts = args.get("parts") or []

    parts_text = " ".join([str(p.get("shape", "")) + " " + str(p.get("name", "")) for p in parts if isinstance(p, dict)]).lower()
    all_target_text = f"{subject} {shape_param} {parts_text}"

    def _matches_any(keywords, text):
        return any(kw in text for kw in keywords)

    if _matches_any(("chair", "의자"), all_target_text):
        made = build_chair_preset(args)
    elif _matches_any(("table", "desk", "책상", "테이블"), all_target_text):
        made = build_table_preset(args)
    elif _matches_any(("hex_nut", "hexagon", "너트", "볼트", "nut", "acorn_nut"), all_target_text):
        made = build_hex_nut_preset(args)
    else:
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()
        scene = bpy.context.scene
        _SHAPES = {"cube": lambda: bpy.ops.mesh.primitive_cube_add(),
                   "cylinder": lambda: bpy.ops.mesh.primitive_cylinder_add(vertices=32),
                   "hexagon": lambda: bpy.ops.mesh.primitive_cylinder_add(vertices=6),
                   "sphere": lambda: bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16),
                   "cone": lambda: bpy.ops.mesh.primitive_cone_add(vertices=32),
                   "torus": lambda: bpy.ops.mesh.primitive_torus_add(),
                   "plane": lambda: bpy.ops.mesh.primitive_plane_add()}
        if not (1 <= len(parts) <= 64):
            raise RuntimeError("parts는 1~64개여야 합니다.")
        mats = {}

        def _mat(color):
            key = tuple(round(min(max(float(c), 0.0), 1.0), 3) for c in (list(color) + [0.8, 0.8, 0.8])[:3])
            if key not in mats:
                m = bpy.data.materials.new("mat_" + "_".join(str(int(c * 255)) for c in key))
                m.use_nodes = True
                b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
                b.inputs["Base Color"].default_value = (*key, 1.0)
                mats[key] = m
            return mats[key]

        made = []
        for i, p in enumerate(parts):
            shape = str(p.get("shape", "cube")).lower()
            if shape not in _SHAPES:
                raise RuntimeError(f"모르는 shape '{shape}' — " + "·".join(_SHAPES) + " 중 하나로.")
            _SHAPES[shape]()
            o = bpy.context.object
            o.name = str(p.get("name") or f"{shape}_{i+1}")[:60]
            size = [max(float(v), 0.001) for v in (list(p.get("size") or [1, 1, 1]) + [1, 1, 1])[:3]]
            if shape == "plane":
                o.dimensions[0], o.dimensions[1] = size[0], size[1]
            else:
                o.dimensions = size
            rot = [float(v) for v in (list(p.get("rot_deg") or [0, 0, 0]) + [0, 0, 0])[:3]]
            o.rotation_euler = [math.radians(v) for v in rot]
            o.location = [float(v) for v in (list(p.get("pos") or [0, 0, 0]) + [0, 0, 0])[:3]]
            if p.get("color"):
                o.data.materials.append(_mat(p["color"]))
            made.append(o)

    bpy.context.view_layer.update()
    sel_only(made)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)   # 유니티 대비 스케일 1
    dest = args.get("dest") or args.get("path") or os.path.join(os.path.expanduser("~"), "Desktop", "built_model.blend")
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=dest)
    out["dest"] = dest
    out["parts"] = [o.name for o in made]
    out["polys"] = sum(len(o.data.polygons) for o in made)
    if args.get("preview_dir"):
        out["previews"] = preview_shots(args["preview_dir"], args["stem"], angles=2)

elif action == "text3d":
    # 3D 글자(간판·로고) — 빈 시작에서 새 .blend. 한글은 맑은고딕으로.
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    scene = bpy.context.scene
    text = str(args.get("text") or "").strip()
    if not text:
        raise RuntimeError("text3d는 text(새길 글)가 필요합니다.")
    bpy.ops.object.text_add()
    ob = bpy.context.object
    ob.name = "Text_" + text[:20]
    ob.data.body = text[:200]
    size = max(float(args.get("size", 1.0)), 0.01)
    ob.data.size = size
    ob.data.extrude = max(float(args.get("depth", size * 0.15)), 0.001)
    ob.data.bevel_depth = max(float(args.get("bevel", size * 0.02)), 0.0)
    ob.data.bevel_resolution = int(args.get("bevel_res", 4))
    ob.data.resolution_u = int(args.get("resolution_u", 12))
    ob.data.align_x = 'CENTER'
    font_path = args.get("font") or r"C:\Windows\Fonts\malgunbd.ttf"
    if not os.path.isfile(font_path):
        font_path = r"C:\Windows\Fonts\malgun.ttf"
    try:
        ob.data.font = bpy.data.fonts.load(font_path)
    except Exception:
        pass                                     # 폰트 실패 시 기본 폰트(영문만) — 정직하게 결과로 보임
    ob.rotation_euler.x = math.radians(90)       # 세워서 앞(-Y)을 보게
    bpy.ops.object.convert(target='MESH')        # 유니티로 나갈 수 있게 메시로
    ob = bpy.context.object
    try:
        for p in ob.data.polygons:
            p.use_smooth = True
    except Exception:
        pass
    if args.get("color"):
        m = bpy.data.materials.new("text_mat")
        m.use_nodes = True
        b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        c = [min(max(float(v), 0.0), 1.0) for v in (list(args["color"]) + [0.8, 0.8, 0.8])[:3]]
        b.inputs["Base Color"].default_value = (*c, 1.0)
        ob.data.materials.append(m)
    bpy.context.view_layer.update()
    lo, hi = scene_extents()                     # 바닥 중앙을 원점에
    ob.location.x -= (lo[0] + hi[0]) / 2
    ob.location.y -= (lo[1] + hi[1]) / 2
    ob.location.z -= lo[2]
    dest = args["dest"]
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=dest)
    out["dest"] = dest
    out["text"] = text
    out["polys"] = len(ob.data.polygons)
    if args.get("preview_dir"):
        out["previews"] = preview_shots(args["preview_dir"], args["stem"], angles=1)

elif action == "assemble":
    # 씬 조립 — 여러 3D 파일을 좌표대로 한 씬에 배치(키트배시). 원본들은 읽기만.
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    scene = bpy.context.scene
    items = args.get("items") or []
    if not (1 <= len(items) <= 32):
        raise RuntimeError("items는 1~32개여야 합니다.")
    placed = []
    for i, it in enumerate(items):
        src = it["file"]
        ext = os.path.splitext(src)[1].lower()
        before = set(scene.objects)
        if ext == ".blend":
            with bpy.data.libraries.load(src) as (df, dt):
                dt.objects = df.objects
            for o in dt.objects:
                if o and o.type in ('MESH', 'ARMATURE', 'EMPTY'):
                    scene.collection.objects.link(o)
        elif ext == ".fbx":
            bpy.ops.import_scene.fbx(filepath=src)
        elif ext == ".obj":
            bpy.ops.wm.obj_import(filepath=src)
        elif ext in (".glb", ".gltf"):
            bpy.ops.import_scene.gltf(filepath=src)
        elif ext == ".stl":
            bpy.ops.wm.stl_import(filepath=src)
        else:
            raise RuntimeError(f"불러올 수 없는 형식: {ext}")
        new = [o for o in scene.objects if o not in before]
        grp = bpy.data.objects.new(str(it.get("name") or f"item_{i+1}")[:60], None)
        scene.collection.objects.link(grp)
        for r in [o for o in new if o.parent is None or o.parent not in new]:
            r.parent = grp
        grp.location = [float(v) for v in (list(it.get("pos") or [0, 0, 0]) + [0, 0, 0])[:3]]
        rot = [float(v) for v in (list(it.get("rot_deg") or [0, 0, 0]) + [0, 0, 0])[:3]]
        grp.rotation_euler = [math.radians(v) for v in rot]
        s = float(it.get("scale") or 1.0)
        grp.scale = (s, s, s)
        placed.append({"name": grp.name, "objects": len(new),
                       "file": os.path.basename(src)})
    dest = args["dest"]
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=dest)
    out["dest"] = dest
    out["placed"] = placed
    if args.get("export"):
        exp = args["export_dest"]
        sel_only([o for o in scene.objects if o.type in ('MESH', 'ARMATURE')])
        if args["export"] == "glb":
            bpy.ops.export_scene.gltf(filepath=exp, use_selection=True, export_format='GLB')
        else:
            bpy.ops.export_scene.fbx(filepath=exp, use_selection=True,
                                     add_leaf_bones=False, apply_scale_options='FBX_SCALE_ALL')
        out["exported"] = exp
    if args.get("preview_dir"):
        out["previews"] = preview_shots(args["preview_dir"], args["stem"], angles=2)

elif action == "anim_merge":
    # 애니 FBX 여러 개(Mixamo류)를 캐릭터 하나의 FBX로 합본 — 유니티에서 클립 여러 개로 뜸.
    # 캐릭터 .blend는 저장하지 않고(메모리에서만) FBX만 내보냅니다. 본 이름이 안 맞으면 정직 거절.
    import re as _re
    scene = bpy.context.scene
    arm = next((o for o in scene.objects if o.type == 'ARMATURE'), None)
    if not arm:
        raise RuntimeError("캐릭터 파일에 아마추어(뼈대)가 없습니다 — 리깅된 캐릭터에만 "
                           "애니메이션을 합본할 수 있습니다.")
    my_bones = {b.name for b in arm.data.bones}

    def bones_in(a):
        names = set()
        for fc in act_fcurves_of(a):
            m = _re.match(r'pose\.bones\["(.+?)"\]', fc.data_path or "")
            if m:
                names.add(m.group(1))
        return names

    def ascii_stem(p):
        s = _re.sub(r"[^A-Za-z0-9_-]", "_", os.path.splitext(os.path.basename(p))[0])
        return _re.sub(r"_+", "_", s).strip("._-") or "clip"

    merged, skipped = [], []
    base_acts = list(bpy.data.actions)           # 캐릭터가 원래 갖고 있던 액션도 같이 나감
    for src in args.get("anims", []):
        before_a = set(bpy.data.actions)
        before_o = set(scene.objects)
        try:
            safe_fbx_import(src)
        except Exception as e:
            skipped.append({"file": os.path.basename(src), "reason": f"임포트 실패: {e}"[:120]})
            continue
        new_acts = [a for a in bpy.data.actions if a not in before_a]
        new_objs = [o for o in scene.objects if o not in before_o]
        stem = ascii_stem(src)
        got = 0
        for a in new_acts:
            ab = bones_in(a)
            if not ab:
                bpy.data.actions.remove(a)       # 본 커브가 없는 액션(오브젝트 이동 등)은 제외
                continue
            hit = ab & my_bones
            if len(hit) < max(1, len(ab) // 2):  # 절반도 안 맞으면 다른 뼈대 — 정직 거절
                skipped.append({"file": os.path.basename(src), "reason": "본 이름 불일치",
                                "their_bones": sorted(ab)[:6]})
                bpy.data.actions.remove(a)
                continue
            got += 1
            a.name = stem if got == 1 else f"{stem}_{got}"
            a.use_fake_user = True
            merged.append({"clip": a.name, "bones_matched": f"{len(hit)}/{len(ab)}"})
        for o in new_objs:                        # 임포트된 껍데기(메시·아마추어)는 지움 — 액션만 취함
            try:
                bpy.data.objects.remove(o, do_unlink=True)
            except Exception:
                pass
        if not got and not any(s["file"] == os.path.basename(src) for s in skipped):
            skipped.append({"file": os.path.basename(src), "reason": "본 애니메이션 없음"})
    if not merged:
        raise RuntimeError("합본할 애니메이션이 하나도 없습니다: "
                           + "; ".join(f"{s['file']}({s['reason']})" for s in skipped[:5]))

    # 전 액션을 NLA 스트립으로 깔아 내보냄 — '모든 액션' 옵션보다 슬롯 액션(5.0)에서 확실.
    if arm.animation_data is None:
        arm.animation_data_create()
    for tr in list(arm.animation_data.nla_tracks):
        arm.animation_data.nla_tracks.remove(tr)
    for a in bpy.data.actions:
        if not bones_in(a):
            continue
        tr = arm.animation_data.nla_tracks.new()
        tr.name = a.name
        tr.strips.new(a.name, 1, a)
    arm.animation_data.action = None

    dest = args["dest"]
    for o in scene.objects:
        o.select_set(o.type in ('MESH', 'ARMATURE', 'EMPTY'))
    bpy.ops.export_scene.fbx(filepath=dest, use_selection=True, add_leaf_bones=False,
                             apply_scale_options='FBX_SCALE_ALL', bake_anim=True,
                             bake_anim_use_all_actions=False, bake_anim_use_nla_strips=True,
                             bake_anim_use_all_bones=True)
    verify = {}
    try:                                          # 내보낸 FBX를 빈 씬에 다시 불러 클립 수·이름 실측
        bpy.ops.wm.read_homefile(use_empty=True)
        safe_fbx_import(dest)
        names = [a.name for a in bpy.data.actions]
        want = [m["clip"] for m in merged]
        verify = {"clips": len(names), "names": names[:12],
                  "ok": all(any(w in n for n in names) for w in want)}
    except Exception as e:
        verify = {"error": str(e)}
    out.update({"dest": dest, "merged": merged, "skipped": skipped,
                "base_actions": [a.name for a in base_acts], "verify": verify})

elif action == "bake":
    # 하이폴리→로우폴리 노멀/AO 베이킹(Cycles 헤드리스) — decimate·lod와 세트로 '폴리↓ 디테일 보존'.
    # .blend는 저장하지 않고 PNG만 남깁니다(ASCII 이름·외부 파일 방식 — 유니티 자동 바인딩용).
    scene = bpy.context.scene
    meshes = [o for o in scene.objects if o.type == 'MESH']
    if len(meshes) < 2:
        raise RuntimeError("bake는 하이폴리·로우폴리 메시 2개가 필요합니다"
                           f"(지금 {len(meshes)}개) — decimate로 로우폴리를 먼저 만드세요.")

    def pick(name, fallback):
        if name:
            o = bpy.data.objects.get(str(name))
            if not o or o.type != 'MESH':
                raise RuntimeError(f"메시 '{name}'가 없습니다. 있는 메시: "
                                   + ", ".join(m.name for m in meshes[:10]))
            return o
        return fallback

    by_poly = sorted(meshes, key=lambda o: len(o.data.polygons))
    high = pick(args.get("high"), by_poly[-1])
    low = pick(args.get("low"), by_poly[0])
    if high is low:
        raise RuntimeError("high와 low가 같은 메시입니다.")
    maps = [m for m in (args.get("maps") or ["normal", "ao"]) if m in ("normal", "ao")]
    size = min(max(int(args.get("size", 1024)), 128), 4096)

    if not low.data.uv_layers:                    # 베이크는 로우폴리의 UV에 굽습니다
        sel_only([low])
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
        bpy.ops.object.mode_set(mode='OBJECT')
        out["uv_added"] = True
    if not low.data.materials:
        m = bpy.data.materials.new("bake_mat")
        m.use_nodes = True
        low.data.materials.append(m)

    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    _, sz = scene_bbox()
    extr = float(args.get("extrusion", sz * 0.02))
    baked = []
    for map_kind in maps:
        img = bpy.data.images.new(f"bake_{map_kind}", size, size, alpha=False)
        img.colorspace_settings.name = 'Non-Color'
        nodes_added = []
        for slot in low.material_slots:           # 로우폴리 모든 재질에서 이 이미지가 활성 타깃
            m = slot.material
            if not m:
                continue
            if not m.use_nodes:
                m.use_nodes = True
            n = m.node_tree.nodes.new('ShaderNodeTexImage')
            n.image = img
            m.node_tree.nodes.active = n
            nodes_added.append((m, n))
        scene.cycles.samples = 8 if map_kind == "normal" else int(args.get("samples", 32))
        sel_only([high, low])
        bpy.context.view_layer.objects.active = low
        bpy.ops.object.bake(type='NORMAL' if map_kind == "normal" else 'AO',
                            use_selected_to_active=True, cage_extrusion=extr,
                            use_clear=True)
        fp = os.path.join(args["out_dir"], f"{args['stem']}_{map_kind}.png")
        img.filepath_raw = fp
        img.file_format = 'PNG'
        img.save()
        baked.append({"map": map_kind, "file": fp, "size": size})
        for m, n in nodes_added:
            m.node_tree.nodes.remove(n)
    out.update({"high": high.name, "high_polys": len(high.data.polygons),
                "low": low.name, "low_polys": len(low.data.polygons),
                "extrusion": round(extr, 4), "baked": baked})

elif action == "beauty_render":
    # 기획서용 렌더 — 3점 조명+바닥 그림자(섀도 캐처)+투명 배경 PNG. 읽기만, 저장 안 함.
    from mathutils import Vector
    scene = bpy.context.scene
    center, sz = scene_bbox()
    meshes = [o for o in scene.objects if o.type == 'MESH']
    if not meshes:
        raise RuntimeError("렌더할 메시가 없습니다.")
    for o in scene.objects:                       # 파일에 있던 조명은 끄고 3점 조명으로 통일
        if o.type == 'LIGHT':
            o.hide_render = True

    def area_light(name, loc, energy, light_size, color=None):
        bpy.ops.object.light_add(type='AREA', location=loc)
        L = bpy.context.object
        L.name = name
        L.data.energy = energy
        L.data.size = light_size
        if color:
            L.data.color = color
        tr = L.constraints.new('TRACK_TO')
        tgt = bpy.data.objects.new("B3D_LT_" + name, None)
        scene.collection.objects.link(tgt)
        tgt.location = Vector(center)
        tr.target = tgt
        tr.track_axis = 'TRACK_NEGATIVE_Z'
        tr.up_axis = 'UP_Y'
        return L

    base_e = 250.0 * max(sz, 0.5) ** 2            # 몸집에 비례한 광량(실측 감)
    preset = str(args.get("preset", "3point")).lower()

    if preset == "studio":
        area_light("KeyLeft", (center[0] - sz * 2.0, center[1] - sz * 1.5, center[2] + sz * 1.5), base_e * 0.8, sz * 2.0)
        area_light("KeyRight", (center[0] + sz * 2.0, center[1] - sz * 1.5, center[2] + sz * 1.5), base_e * 0.8, sz * 2.0)
        area_light("TopFill", (center[0], center[1], center[2] + sz * 3.0), base_e * 0.4, sz * 2.5)
        area_light("Rim", (center[0], center[1] + sz * 2.5, center[2] + sz * 2.0), base_e * 0.7, sz * 1.0)
    elif preset == "sunset":
        area_light("KeySun", (center[0] - sz * 2.5, center[1] - sz * 2.0, center[2] + sz * 1.2), base_e * 1.4, sz * 1.0, color=(1.0, 0.7, 0.4))
        area_light("SkyFill", (center[0] + sz * 2.0, center[1] - sz * 1.0, center[2] + sz * 2.0), base_e * 0.3, sz * 2.0, color=(0.4, 0.6, 1.0))
        area_light("Rim", (center[0] + sz * 0.5, center[1] + sz * 2.2, center[2] + sz * 1.8), base_e * 0.8, sz * 0.8, color=(1.0, 0.5, 0.3))
    elif preset == "cyberpunk":
        area_light("CyanKey", (center[0] - sz * 1.8, center[1] - sz * 1.5, center[2] + sz * 1.5), base_e * 1.2, sz * 1.2, color=(0.0, 0.8, 1.0))
        area_light("MagentaRim", (center[0] + sz * 1.8, center[1] + sz * 1.8, center[2] + sz * 1.8), base_e * 1.0, sz * 1.0, color=(1.0, 0.0, 0.8))
        area_light("Fill", (center[0], center[1] - sz * 2.0, center[2] + sz * 0.5), base_e * 0.2, sz * 2.0)
    else: # 3point (기본)
        area_light("Key", (center[0] - sz * 1.6, center[1] - sz * 1.8, center[2] + sz * 1.6), base_e, sz * 1.2)
        area_light("Fill", (center[0] + sz * 2.0, center[1] - sz * 1.2, center[2] + sz * 0.6), base_e * 0.35, sz * 1.8)
        area_light("Rim", (center[0] + sz * 0.4, center[1] + sz * 2.0, center[2] + sz * 2.0), base_e * 0.6, sz * 0.8)

    lo_z = min((o.matrix_world @ Vector(c)).z for o in meshes for c in o.bound_box)
    bpy.ops.mesh.primitive_plane_add(size=sz * 12,
                                     location=(center[0], center[1], lo_z - 0.001))
    floor = bpy.context.object
    floor.name = "B3D_ShadowFloor"
    floor.is_shadow_catcher = True                # Cycles 전용 — 그림자만 받는 투명 바닥

    cam = make_camera(center, sz, deg=float(args.get("angle", 35)))
    cam.location.z = center[2] + sz * 0.55
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = min(max(int(args.get("samples", 64)), 16), 512)
    scene.cycles.use_denoising = True
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.resolution_x = min(max(int(args.get("width", args.get("size", 1024))), 256), 4096)
    scene.render.resolution_y = min(max(int(args.get("height", args.get("size", 1024))), 256), 4096)
    scene.view_settings.view_transform = 'Standard'
    fp = args["dest"]
    scene.render.filepath = fp
    bpy.ops.render.render(write_still=True)
    out.update({"dest": fp, "samples": scene.cycles.samples,
                "resolution": [scene.render.resolution_x, scene.render.resolution_y]})

elif action == "shot":
    # 임의 3D 파일(fbx·obj·glb·stl) 한 컷 — contact_sheet(폴더 몽타주)의 재료.
    bpy.ops.object.select_all(action='SELECT')    # 빈 시작의 기본 큐브·카메라·조명 제거
    bpy.ops.object.delete()
    import_any(args["src"])
    scene = bpy.context.scene
    center, sz = scene_bbox()
    cam = make_camera(center, sz)
    scene.render.resolution_x = scene.render.resolution_y = int(args.get("size", 384))
    scene.eevee.taa_render_samples = 16
    fp = args["dest"]
    scene.render.filepath = fp
    bpy.ops.render.render(write_still=True)
    out["shot"] = fp
    out["polys"] = sum(len(o.data.polygons) for o in scene.objects if o.type == 'MESH')

# ── 여기부터는 '수술' — blender3d.py가 만든 **사본** 위에서만 돕니다 ──
elif action in ("apply", "origin", "scale_to", "cleanup", "uv", "decimate", "join",
                "auto_weight", "bone_template", "tex_resize", "mirror", "array", "scatter",
                "collider", "materials", "split", "anim_edit", "weight_transfer",
                "repair", "boolean", "curve_path", "sockets", "uv_atlas", "material_pbr",
                # 세션63: 마감(bevel·solidify·shade)/유니티(lightmap_uv·rename·normals)/
                # 배치(align)/청소(purge)/애니·물리(pose_apply·physics_bake) — 전부 사본 위 수술.
                "bevel", "solidify", "shade", "lightmap_uv", "rename", "normals",
                "align", "purge", "pose_apply", "physics_bake",
                # 세션67: 절차적 유기 디테일(sculpt_displace) — 브러시 스컬프의 헤드리스 대체.
                "sculpt_displace",
                "prep_unity", "chain"):
    scene = bpy.context.scene
    meshes = [o for o in scene.objects if o.type == 'MESH']

    def select_only(objs):
        bpy.ops.object.select_all(action='DESELECT')
        for o in objs:
            o.select_set(True)
        if objs:
            bpy.context.view_layer.objects.active = objs[0]

    if action == "apply":                        # 스케일·회전 적용(Ctrl+A) — 유니티 크기 어긋남의 주범
        select_only(meshes)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        out["applied"] = [o.name for o in meshes]

    elif action == "origin":                     # 바닥 중심을 월드 원점으로 — 발이 (0,0,0)에 닿게
        center, size = scene_bbox()
        lo_z = 1e9
        from mathutils import Vector
        for o in meshes:
            for c in o.bound_box:
                lo_z = min(lo_z, (o.matrix_world @ Vector(c)).z)
        dx, dy, dz = -center[0], -center[1], -lo_z
        roots = [o for o in scene.objects if o.parent is None and o.type != 'CAMERA'
                 and o.type != 'LIGHT']
        for o in roots:
            o.location.x += dx
            o.location.y += dy
            o.location.z += dz
        out["moved_by"] = [round(v, 4) for v in (dx, dy, dz)]

    elif action == "scale_to":                   # 전체 키(Z)를 지정 미터로
        center, size = scene_bbox()
        from mathutils import Vector
        lo_z, hi_z = 1e9, -1e9
        for o in meshes:
            for c in o.bound_box:
                z = (o.matrix_world @ Vector(c)).z
                lo_z, hi_z = min(lo_z, z), max(hi_z, z)
        cur = max(hi_z - lo_z, 1e-6)
        f = float(args["height"]) / cur
        roots = [o for o in scene.objects if o.parent is None
                 and o.type not in ('CAMERA', 'LIGHT')]
        for o in roots:
            o.location *= f
            o.scale *= f
        select_only([o for o in roots if o.type in ('MESH', 'ARMATURE')] +
                    [m for m in meshes if m.parent is None])
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        out["height_before"] = round(cur, 3)
        out["height_after"] = float(args["height"])

    elif action == "cleanup":                    # 중복 정점 합치기 + 법선 바깥으로 + 부스러기 제거
        import bmesh
        removed = 0
        for o in meshes:
            before = len(o.data.vertices)
            bm = bmesh.new()
            bm.from_mesh(o.data)
            bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0001)
            loose = [v for v in bm.verts if not v.link_faces]
            bmesh.ops.delete(bm, geom=loose, context='VERTS')
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
            bm.to_mesh(o.data)
            bm.free()
            removed += before - len(o.data.vertices)
        out["removed_verts"] = removed

    elif action == "uv":                         # UV 없는 메시에 자동 UV(텍스처 입힐 준비)
        targets = [o for o in meshes if not o.data.uv_layers]
        if args.get("force"):
            targets = meshes
        for o in targets:
            select_only([o])
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
            bpy.ops.object.mode_set(mode='OBJECT')
        out["uv_added"] = [o.name for o in targets]

    elif action == "decimate":                   # 폴리 줄이기 — 모바일 최적화
        ratio = min(max(float(args.get("ratio", 0.5)), 0.05), 0.95)
        before = sum(len(o.data.polygons) for o in meshes)
        for o in meshes:
            select_only([o])
            mod = o.modifiers.new("dec", 'DECIMATE')
            mod.ratio = ratio
            bpy.ops.object.modifier_apply(modifier="dec")
        out["polys_before"] = before
        out["polys_after"] = sum(len(o.data.polygons) for o in meshes)

    elif action == "join":                       # 메시 전부 한 덩어리로(드로우콜 절약)
        if len(meshes) < 2:
            raise RuntimeError("합칠 메시가 2개 미만입니다.")
        select_only(meshes)
        bpy.ops.object.join()
        out["joined"] = len(meshes)
        out["result"] = bpy.context.object.name

    elif action == "auto_weight":                # 리깅의 기계적 절반: 기존 뼈대에 자동으로 살 붙이기
        arm = next((o for o in scene.objects if o.type == 'ARMATURE'), None)
        if not arm:
            raise RuntimeError("아마추어(뼈대)가 없습니다 — 본이 놓인 리그 파일에만 "
                               "자동 웨이트를 씌울 수 있습니다(본 배치는 사람 몫).")
        if not meshes:
            raise RuntimeError("살을 붙일 메시가 없습니다.")
        bpy.ops.object.select_all(action='DESELECT')
        for m in meshes:                          # 겹겹 방지: 기존 아마추어 모디파이어 제거 후 새로 바인딩
            for mod in [x for x in m.modifiers if x.type == 'ARMATURE']:
                m.modifiers.remove(mod)
            m.select_set(True)
        arm.select_set(True)
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')   # 히트맵 자동 웨이트(안 되는 본은 엔벌로프 폴백)
        # 정밀 웨이트 정리: 0.001 이하 미세 웨이트 감쇄 및 가비지 핑거핑거 방지
        clean_count = 0
        for m in meshes:
            if m.type == 'MESH':
                for v in m.data.vertices:
                    for g in v.groups:
                        if g.weight < 0.001:
                            g.weight = 0.0
                            clean_count += 1
        out["armature"] = arm.name
        out["bones"] = len(arm.data.bones)
        out["bound_meshes"] = [m.name for m in meshes]
        out["pruned_tiny_weights"] = clean_count

    elif action == "bone_template":              # 표준 뼈대 자동 배치 — 리깅의 나머지 절반의 출발점
        # 크기를 재서 휴머노이드(17본)/사족(15본) 표준 리그를 몸에 맞춰 놓습니다.
        # 어디까지나 '출발점' — 정밀한 관절 위치는 블렌더에서 사람이 다듬는 게 맞습니다.
        if not meshes:
            raise RuntimeError("뼈대를 놓을 메시가 없습니다.")
        if any(o.type == 'ARMATURE' for o in scene.objects):
            raise RuntimeError("이미 아마추어(뼈대)가 있습니다 — 겹으로 놓으면 자동 웨이트가 "
                               "엉킵니다. 기존 뼈대를 쓰려면 auto_weight를 부르세요.")
        kind = str(args.get("kind", "humanoid")).lower()
        if kind not in ("humanoid", "quadruped"):
            raise RuntimeError("kind는 humanoid(두발)·quadruped(네발) 중 하나입니다.")
        lo, hi = scene_extents()
        H = max(hi[2] - lo[2], 0.01)
        W = max(hi[0] - lo[0], 0.01)
        D = max(hi[1] - lo[1], 0.01)
        cx, cy, z0 = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]

        arm_data = bpy.data.armatures.new("Rig")
        arm = bpy.data.objects.new("Rig", arm_data)
        scene.collection.objects.link(arm)
        sel_only([arm])
        bpy.ops.object.mode_set(mode='EDIT')
        eb = arm_data.edit_bones

        def bone(name, head, tail, parent=None, connect=False):
            b = eb.new(name)
            b.head, b.tail = head, tail
            if parent is not None:
                b.parent = parent
                b.use_connect = connect
            return b

        Z = lambda f: z0 + f * H
        if kind == "humanoid":
            hips = bone("hips", (cx, cy, Z(.50)), (cx, cy, Z(.58)))
            spine = bone("spine", (cx, cy, Z(.58)), (cx, cy, Z(.68)), hips, True)
            chest = bone("chest", (cx, cy, Z(.68)), (cx, cy, Z(.78)), spine, True)
            neck = bone("neck", (cx, cy, Z(.78)), (cx, cy, Z(.84)), chest, True)
            bone("head", (cx, cy, Z(.84)), (cx, cy, Z(.97)), neck, True)
            for suf, s in ((".L", 1), (".R", -1)):
                sh = bone("shoulder" + suf, (cx + s * 0.06 * W, cy, Z(.76)),
                          (cx + s * 0.17 * W, cy, Z(.75)), chest)
                ua = bone("upper_arm" + suf, (cx + s * 0.17 * W, cy, Z(.75)),
                          (cx + s * 0.38 * W, cy, Z(.65)), sh, True)
                fa = bone("forearm" + suf, (cx + s * 0.38 * W, cy, Z(.65)),
                          (cx + s * 0.48 * W, cy, Z(.56)), ua, True)
                bone("hand" + suf, (cx + s * 0.48 * W, cy, Z(.56)),
                     (cx + s * 0.53 * W, cy, Z(.51)), fa, True)
                hx = cx + s * max(0.12 * W, 0.02)
                th = bone("thigh" + suf, (hx, cy, Z(.50)), (hx, cy, Z(.27)), hips)
                sn = bone("shin" + suf, (hx, cy, Z(.27)), (hx, cy, Z(.05)), th, True)
                bone("foot" + suf, (hx, cy, Z(.05)),
                     (hx, cy - max(0.35 * D, 0.06 * H), Z(.02)), sn, True)
        else:                                    # quadruped — 앞이 -Y(렌더 front와 같은 방향)
            hips = bone("hips", (cx, cy + 0.30 * D, Z(.60)), (cx, cy + 0.10 * D, Z(.62)))
            spine = bone("spine", (cx, cy + 0.10 * D, Z(.62)), (cx, cy - 0.15 * D, Z(.62)),
                         hips, True)
            neck = bone("neck", (cx, cy - 0.15 * D, Z(.62)), (cx, cy - 0.32 * D, Z(.75)),
                        spine, True)
            bone("head", (cx, cy - 0.32 * D, Z(.75)), (cx, cy - 0.46 * D, Z(.80)), neck, True)
            bone("tail", (cx, cy + 0.30 * D, Z(.60)), (cx, cy + 0.48 * D, Z(.55)), hips)
            for suf, s in ((".L", 1), (".R", -1)):
                xo = cx + s * 0.30 * W
                for part, yy, par in (("front_leg", cy - 0.22 * D, spine),
                                      ("hind_leg", cy + 0.26 * D, hips)):
                    up = bone(f"{part}_upper{suf}", (xo, yy, Z(.55)), (xo, yy, Z(.28)), par)
                    bone(f"{part}_lower{suf}", (xo, yy, Z(.28)), (xo, yy, Z(.02)), up, True)
        bpy.ops.object.mode_set(mode='OBJECT')
        out["kind"] = kind
        out["bones"] = len(arm_data.bones)
        out["armature"] = arm.name
        if args.get("bind"):                     # 원하면 그 자리에서 자동 웨이트까지
            bpy.ops.object.select_all(action='DESELECT')
            for m in meshes:
                for mod in [x for x in m.modifiers if x.type == 'ARMATURE']:
                    m.modifiers.remove(mod)
                m.select_set(True)
            arm.select_set(True)
            bpy.context.view_layer.objects.active = arm
            bpy.ops.object.parent_set(type='ARMATURE_AUTO')
            out["bound_meshes"] = [m.name for m in meshes]

    elif action == "tex_resize":                 # 큰 텍스처를 줄여 .blend·FBX 몸집을 빼기
        max_px = min(max(int(args.get("max_px", 1024)), 64), 4096)
        try:
            bpy.ops.file.pack_all()              # 원본 이미지 파일은 안 건드리고 사본 안에서만
        except Exception:
            pass
        resized = []
        for img in bpy.data.images:
            if img.name in ("Render Result", "Viewer Node"):
                continue
            w, h = img.size
            if w <= max_px and h <= max_px or w == 0 or h == 0:
                continue
            f = max_px / float(max(w, h))
            nw, nh = max(int(w * f), 1), max(int(h * f), 1)
            img.scale(nw, nh)
            try:
                img.pack()                       # 줄인 픽셀을 사본에 다시 담음
            except Exception:
                pass
            resized.append({"name": img.name, "from": [w, h], "to": [nw, nh]})
        out["resized"] = resized
        out["max_px"] = max_px

    elif action == "mirror":                     # 반쪽만 만든 모델을 대칭으로 완성(원점 기준)
        axis = str(args.get("axis", "x")).lower()
        idx = {"x": 0, "y": 1, "z": 2}.get(axis)
        if idx is None:
            raise RuntimeError("axis는 x·y·z 중 하나입니다.")
        before = sum(len(o.data.polygons) for o in meshes)
        for o in meshes:
            select_only([o])
            mod = o.modifiers.new("mir", 'MIRROR')
            mod.use_axis = (idx == 0, idx == 1, idx == 2)
            mod.use_clip = True
            mod.merge_threshold = 0.001
            bpy.ops.object.modifier_apply(modifier="mir")
        out["axis"] = axis
        out["polys_before"] = before
        out["polys_after"] = sum(len(o.data.polygons) for o in meshes)

    elif action in ("array", "scatter"):         # 배열 복제 / 영역 랜덤 뿌리기(둘 다 링크 복제=가벼움)
        import random
        from mathutils import Vector

        roots = [o for o in scene.objects if o.parent is None
                 and o.type in ('MESH', 'EMPTY', 'ARMATURE')]
        if not roots:
            raise RuntimeError("복제할 오브젝트가 없습니다.")

        def dup_tree(root):
            """계층 통째 링크 복제(메시 데이터 공유) — 부모 관계도 사본끼리 다시 맺음."""
            def rec(o, par):
                c = o.copy()                     # data는 공유 — 파일이 안 불어남
                scene.collection.objects.link(c)
                c.parent = par
                if par is not None:
                    c.matrix_parent_inverse = o.matrix_parent_inverse.copy()
                for ch in o.children:
                    rec(ch, c)
                return c
            return rec(root, None)

        made = 0
        if action == "array":
            mode = str(args.get("mode", "linear")).lower()
            count = min(max(int(args.get("count", 4)), 2), 50)
            if mode == "radial":
                radius = float(args.get("radius", 0))
                if radius <= 0:
                    raise RuntimeError("radial 배열은 radius(원 반지름, 미터)가 필요합니다.")
                cx, cy = [float(v) for v in (list(args.get("center") or [0, 0]) + [0, 0])[:2]]
                # 부품 여러 개짜리 모델도 '대형 그대로' 돌려 놓아야 함 — 절대좌표로 찍으면
                # 모든 부품이 원둘레 한 점에 겹침(실측 눈검수에서 잡은 함정).
                for k in range(count):
                    a = 2 * math.pi * k / count
                    ca, sa = math.cos(a), math.sin(a)
                    for r in roots:
                        c = dup_tree(r) if k else r
                        rx, ry = r.location.x - cx, r.location.y - cy
                        c.location.x = cx + (rx * ca - ry * sa) + ca * radius
                        c.location.y = cy + (rx * sa + ry * ca) + sa * radius
                        c.rotation_euler.rotate_axis('Z', a)
                        if k:
                            made += 1
            else:
                lo, hi = scene_extents()
                off = args.get("offset") or [round((hi[0] - lo[0]) * 1.2, 3) or 1.0, 0, 0]
                off = Vector([float(v) for v in (list(off) + [0, 0, 0])[:3]])
                for k in range(1, count):
                    for r in roots:
                        c = dup_tree(r)
                        c.location = Vector(r.location) + off * k
                        made += 1
            out["mode"] = mode
            out["count"] = count
        else:                                    # scatter — 시드 고정=같은 씨앗이면 같은 배치
            count = min(max(int(args.get("count", 20)), 2), 200)
            w, d = [max(float(v), 0.1) for v in (list(args.get("area") or [10, 10]) + [10, 10])[:2]]
            seed = int(args.get("seed", 0))
            jitter = min(max(float(args.get("jitter", 0.2)), 0.0), 0.5)
            rng = random.Random(seed)
            protos = [r for r in roots if r.type == 'MESH' or
                      any(ch.type == 'MESH' for ch in r.children_recursive)]
            if not protos:
                raise RuntimeError("뿌릴 메시가 없습니다.")
            for _ in range(count):
                c = dup_tree(rng.choice(protos))
                c.location.x = rng.uniform(-w / 2, w / 2)
                c.location.y = rng.uniform(-d / 2, d / 2)
                c.rotation_euler.z = rng.uniform(0, 2 * math.pi)
                s = 1.0 + rng.uniform(-jitter, jitter)
                c.scale = (c.scale[0] * s, c.scale[1] * s, c.scale[2] * s)
                made += 1
            out["count"] = count
            out["area"] = [w, d]
            out["seed"] = seed
        out["copies"] = made

    elif action == "collider":                   # 유니티 콜라이더용 저폴리 콘벡스 헐 생성
        import bmesh
        max_tris = min(max(int(args.get("max_tris", 255)), 12), 2000)

        def make_hull(name, verts_co, matrix=None):
            bm = bmesh.new()
            for co in verts_co:
                bm.verts.new(co)
            res = bmesh.ops.convex_hull(bm, input=bm.verts[:])
            junk = [g for g in (res.get("geom_interior", []) + res.get("geom_unused", []))
                    if isinstance(g, bmesh.types.BMVert)]
            if junk:
                bmesh.ops.delete(bm, geom=junk, context='VERTS')
            me = bpy.data.meshes.new(name)
            bm.to_mesh(me)
            bm.free()
            ob = bpy.data.objects.new(name, me)
            scene.collection.objects.link(ob)
            if matrix is not None:
                ob.matrix_world = matrix.copy()
            ob.display_type = 'WIRE'             # 본체를 안 가리게 철사 표시
            tris = sum(max(len(p.vertices) - 2, 0) for p in me.polygons)
            if tris > max_tris:
                select_only([ob])
                mod = ob.modifiers.new("dec", 'DECIMATE')
                mod.ratio = max_tris / float(tris)
                bpy.ops.object.modifier_apply(modifier="dec")
                tris = sum(max(len(p.vertices) - 2, 0) for p in ob.data.polygons)
            return ob, tris

        made = []
        if args.get("combined"):
            allco = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
            if not allco:
                raise RuntimeError("헐을 만들 정점이 없습니다.")
            ob, tris = make_hull("Combined_collider", allco)
            made.append({"name": ob.name, "tris": tris})
        else:
            for o in meshes:
                if o.name.endswith("_collider") or not o.data.vertices:
                    continue
                ob, tris = make_hull(o.name + "_collider", [v.co for v in o.data.vertices],
                                     o.matrix_world)
                made.append({"name": ob.name, "tris": tris})
        if not made:
            raise RuntimeError("콜라이더를 만들 메시가 없습니다.")
        out["colliders"] = made

    elif action == "materials":                  # 재질 정리 — .001 중복 병합·(선택)ASCII화·색 변경
        import re as _re
        eps = 0.03
        mats = [m for m in bpy.data.materials if m.users]

        def base_color(m):
            if m.use_nodes:
                b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
                if b:
                    return list(b.inputs["Base Color"].default_value)[:3]
            return list(m.diffuse_color)[:3]

        merged = {}
        if args.get("dedupe", True):
            groups = {}
            for m in sorted(mats, key=lambda x: x.name):
                groups.setdefault(_re.sub(r"\.\d{3}$", "", m.name), []).append(m)
            remap = {}
            for base, ms in groups.items():
                canon = ms[0]
                for m in ms[1:]:
                    if all(abs(a - b) < eps for a, b in zip(base_color(canon), base_color(m))):
                        remap[m] = canon
                        merged[m.name] = canon.name
            for o in meshes:
                for slot in o.material_slots:
                    if slot.material in remap:
                        slot.material = remap[slot.material]
        renamed = {}
        if args.get("ascii"):
            for m in [m for m in bpy.data.materials if m.users]:
                if m.name.isascii():
                    continue
                new = _re.sub(r"[^A-Za-z0-9_-]", "_", m.name)
                new = _re.sub(r"_+", "_", new).strip("._-") or "mat"
                old = m.name
                m.name = new                     # 충돌 시 블렌더가 .001을 붙임(그래도 ASCII)
                renamed[old] = m.name
        recolored = []
        for name, col in (args.get("colors") or {}).items():
            for m in bpy.data.materials:
                if m.users and name in m.name and m.use_nodes:
                    b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
                    if b:
                        c = [min(max(float(v), 0.0), 1.0) for v in (list(col) + [0.8] * 3)[:3]]
                        b.inputs["Base Color"].default_value = (*c, 1.0)
                        recolored.append(m.name)
        for m in list(bpy.data.materials):       # 병합으로 임자 잃은 재질 청소
            if m.users == 0:
                bpy.data.materials.remove(m)
        out["merged"] = merged
        out["renamed"] = renamed
        out["recolored"] = recolored
        out["materials_left"] = sum(1 for m in bpy.data.materials if m.users)

    elif action == "split":                      # join의 역 — 느슨한 조각/재질별로 분리
        mode = str(args.get("mode", "loose")).lower()
        kind = {"loose": 'LOOSE', "material": 'MATERIAL'}.get(mode)
        if not kind:
            raise RuntimeError("mode는 loose(떨어진 조각)·material(재질별) 중 하나입니다.")
        before = len(meshes)
        for o in list(meshes):
            select_only([o])
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            try:
                bpy.ops.mesh.separate(type=kind)
            except RuntimeError:
                pass                             # 조각이 하나뿐이면 분리할 게 없음 — 그대로 둠
            bpy.ops.object.mode_set(mode='OBJECT')
        after = [o for o in scene.objects if o.type == 'MESH']
        out["mode"] = mode
        out["before"] = before
        out["after"] = len(after)
        out["names"] = [o.name for o in after[:12]]

    elif action == "anim_edit":                  # 액션 이름변경·구간 트림·루프화(첫=끝 값 복사)
        acts = list(bpy.data.actions)
        if not acts:
            raise RuntimeError("이 파일에는 애니메이션(액션)이 없습니다.")
        name = str(args.get("name") or "").strip()
        if name:
            act = next((a for a in acts if a.name == name), None)
            if not act:
                raise RuntimeError("그 이름의 액션이 없습니다. 있는 것: "
                                   + ", ".join(a.name for a in acts[:10]))
        elif len(acts) == 1:
            act = acts[0]
        else:
            raise RuntimeError("액션이 여러 개라 name이 필요합니다: "
                               + ", ".join(a.name for a in acts[:10]))
        # 블렌더 4.4+에서 액션이 레이어·슬롯 구조가 되며 5.0에서 Action.fcurves가 사라짐 —
        # 신구 양쪽에서 f-커브를 모아 주는 다리.
        def act_fcurves(a):
            if hasattr(a, "fcurves"):
                return list(a.fcurves)
            fcs = []
            for layer in a.layers:
                for strip in layer.strips:
                    for cb in getattr(strip, "channelbags", []):
                        fcs.extend(cb.fcurves)
            return fcs

        out["range_before"] = [round(v, 1) for v in act.frame_range]
        did = []
        trim = args.get("trim")
        if trim and len(list(trim)) == 2:
            s, e = sorted(float(v) for v in list(trim)[:2])
            for fc in act_fcurves(act):
                for kp in reversed(fc.keyframe_points.values()):
                    if kp.co.x < s - 1e-6 or kp.co.x > e + 1e-6:
                        fc.keyframe_points.remove(kp)
                if args.get("shift", True):      # 잘라낸 구간이 1프레임부터 시작하게 밀기
                    for kp in fc.keyframe_points:
                        kp.co.x -= (s - 1)
                        kp.handle_left.x -= (s - 1)
                        kp.handle_right.x -= (s - 1)
                fc.update()
            did.append(f"트림 {s:g}~{e:g}")
        if args.get("loop"):
            end = act.frame_range[1]
            for fc in act_fcurves(act):
                if not len(fc.keyframe_points):
                    continue
                first = fc.keyframe_points[0]
                kp = fc.keyframe_points.insert(end, first.co.y, options={'REPLACE'})
                kp.interpolation = first.interpolation
                fc.update()
            did.append("루프화(끝=첫 프레임 값)")
        if args.get("new_name"):
            old = act.name
            act.name = str(args["new_name"])[:60]
            did.append(f"이름 {old}→{act.name}")
        if not did:
            raise RuntimeError("할 일이 없습니다 — new_name·trim=[시작,끝]·loop=true 중 하나를 주세요.")
        out["action_name"] = act.name
        out["range_after"] = [round(v, 1) for v in act.frame_range]
        out["did"] = did

    elif action == "weight_transfer":            # 본체 웨이트를 옷·장비 메시에 근접 전사
        src_name = str(args.get("source") or "").strip()
        if src_name:
            src = next((o for o in meshes if o.name == src_name), None)
            if not src:
                raise RuntimeError(f"source 메시 '{src_name}'가 없습니다.")
        else:
            weighted = [o for o in meshes if o.vertex_groups]
            if not weighted:
                raise RuntimeError("웨이트를 가진 메시가 없습니다 — auto_weight를 먼저 하세요.")
            src = max(weighted, key=lambda o: len(o.vertex_groups))
        arm = next((m.object for m in src.modifiers if m.type == 'ARMATURE' and m.object),
                   next((o for o in scene.objects if o.type == 'ARMATURE'), None))
        want = args.get("targets")
        if want:
            targets = [o for o in meshes if o.name in list(want) and o is not src]
            missing = [n for n in list(want) if not any(o.name == n for o in meshes)]
            if missing:
                raise RuntimeError("targets에 없는 메시: " + ", ".join(missing))
        else:
            targets = [o for o in meshes if o is not src and not o.vertex_groups]
        if not targets:
            raise RuntimeError("전사할 대상 메시가 없습니다(이미 전부 웨이트가 있음 — "
                               "targets로 콕 집어 주세요).")
        for t in targets:
            for vg in src.vertex_groups:         # 같은 이름의 그룹을 먼저 만들어야 전사가 붙음
                if vg.name not in t.vertex_groups:
                    t.vertex_groups.new(name=vg.name)
            select_only([t])
            mod = t.modifiers.new("dt", 'DATA_TRANSFER')
            mod.object = src
            mod.use_vert_data = True
            mod.data_types_verts = {'VGROUP_WEIGHTS'}
            mod.vert_mapping = 'POLYINTERP_NEAREST'
            mod.layers_vgroup_select_src = 'ALL'
            bpy.ops.object.modifier_apply(modifier="dt")
            if arm:
                for old in [x for x in t.modifiers if x.type == 'ARMATURE']:
                    t.modifiers.remove(old)
                am = t.modifiers.new("Armature", 'ARMATURE')
                am.object = arm
                if t.parent is None:
                    t.parent = arm
                    t.matrix_parent_inverse = arm.matrix_world.inverted()
        out["source"] = src.name
        out["targets"] = [t.name for t in targets]
        out["groups"] = len(src.vertex_groups)
        out["armature"] = arm.name if arm else None

    elif action == "repair":                     # check의 수리 짝: 구멍·퇴화면·비매니폴드 단계 수리
        import bmesh

        def diag(o):
            bm = bmesh.new()
            bm.from_mesh(o.data)
            d = {"nonmanifold": sum(1 for e in bm.edges if not e.is_manifold),
                 "boundary": sum(1 for e in bm.edges if len(e.link_faces) == 1),
                 "loose": sum(1 for v in bm.verts if not v.link_faces),
                 "verts": len(bm.verts), "faces": len(bm.faces)}
            bm.free()
            return d

        report = []
        for o in meshes:
            before = diag(o)
            bm = bmesh.new()
            bm.from_mesh(o.data)
            bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0001)
            bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=0.0001)
            bmesh.ops.holes_fill(bm, edges=bm.edges[:], sides=int(args.get("sides", 32)))
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces],
                             context='VERTS')
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
            bm.to_mesh(o.data)
            bm.free()
            after = diag(o)
            if args.get("remesh") and after["nonmanifold"]:   # 심하면 마지막 수단: 복셀 리메시
                dim = max(o.dimensions) or 1.0                # (형상은 유지, UV·재질 배치는 날아감)
                mod = o.modifiers.new("rm", 'REMESH')
                mod.mode = 'VOXEL'
                mod.voxel_size = max(dim / 120.0, 0.001)
                select_only([o])
                bpy.ops.object.modifier_apply(modifier="rm")
                after = diag(o)
                after["remeshed"] = True
            report.append({"name": o.name, "before": before, "after": after})
        out["repair"] = report

    elif action == "boolean":                    # 스펙 CSG — 그레이박스에 창문 뚫기·구멍 내기
        items = args.get("items") or []
        if not items:
            raise RuntimeError("boolean은 items=[{target,tool,mode}] 목록이 필요합니다. "
                               "있는 메시: " + ", ".join(o.name for o in meshes[:10]))
        _MODES = {"union": 'UNION', "difference": 'DIFFERENCE', "intersect": 'INTERSECT'}
        done = []
        tools_used = set()
        for op in items:
            tname, wname = str(op.get("target") or ""), str(op.get("tool") or "")
            target = bpy.data.objects.get(tname)
            tool = bpy.data.objects.get(wname)
            if not target or target.type != 'MESH':
                raise RuntimeError(f"target 메시 '{tname}'가 없습니다. 있는 메시: "
                                   + ", ".join(o.name for o in meshes[:10]))
            if not tool or tool.type != 'MESH':
                raise RuntimeError(f"tool 메시 '{wname}'가 없습니다. 있는 메시: "
                                   + ", ".join(o.name for o in meshes[:10]))
            mode = _MODES.get(str(op.get("mode", "difference")).lower())
            if not mode:
                raise RuntimeError("mode는 union·difference·intersect 중 하나입니다.")
            select_only([target])
            mod = target.modifiers.new("bool", 'BOOLEAN')
            mod.object = tool
            mod.operation = mode
            mod.solver = 'EXACT'
            bpy.ops.object.modifier_apply(modifier="bool")
            tools_used.add(wname)
            done.append(f"{tname} {mode.lower()} {wname}")
        if not args.get("keep_tools"):            # 칼(tool)은 기본으로 치움 — 남기려면 keep_tools
            for wname in tools_used:
                t = bpy.data.objects.get(wname)
                if t:
                    bpy.data.objects.remove(t, do_unlink=True)
        out["ops_done"] = done
        out["polys"] = sum(len(o.data.polygons)
                           for o in scene.objects if o.type == 'MESH')

    elif action == "curve_path":                 # 좌표 경로 → 파이프/리본, 또는 커브 따라 배열
        from mathutils import Vector
        pts = args.get("points") or []
        if len(pts) < 2:
            raise RuntimeError("curve_path는 points=[[x,y,z]…] 2개 이상이 필요합니다.")
        mode = str(args.get("mode", "pipe")).lower()
        if mode not in ("pipe", "ribbon", "array"):
            raise RuntimeError("mode는 pipe(관)·ribbon(띠)·array(커브 따라 배열) 중 하나입니다.")
        cu = bpy.data.curves.new("B3D_Path", 'CURVE')
        cu.dimensions = '3D'
        smooth = bool(args.get("smooth", True))
        sp = cu.splines.new('BEZIER' if smooth else 'POLY')
        if smooth:
            sp.bezier_points.add(len(pts) - 1)
            for i, p in enumerate(pts):
                bp = sp.bezier_points[i]
                bp.co = [float(v) for v in (list(p) + [0, 0, 0])[:3]]
                bp.handle_left_type = bp.handle_right_type = 'AUTO'
        else:
            sp.points.add(len(pts) - 1)
            for i, p in enumerate(pts):
                x, y, z = [float(v) for v in (list(p) + [0, 0, 0])[:3]]
                sp.points[i].co = (x, y, z, 1.0)
        sp.use_cyclic_u = bool(args.get("cyclic"))
        curve = bpy.data.objects.new(str(args.get("name") or "Path")[:60], cu)
        scene.collection.objects.link(curve)
        if mode in ("pipe", "ribbon"):
            if mode == "pipe":
                cu.bevel_depth = max(float(args.get("radius", 0.05)), 0.001)
                cu.bevel_resolution = 4
            else:
                cu.extrude = max(float(args.get("width", 0.5)), 0.01) / 2
            select_only([curve])
            bpy.ops.object.convert(target='MESH')   # 유니티로 나갈 수 있게 메시로
            ob = bpy.context.object
            out["result"] = ob.name
            out["polys"] = len(ob.data.polygons)
        else:                                     # array — 기존 오브젝트를 커브 길이만큼 반복 배열
            src = bpy.data.objects.get(str(args.get("object") or "")) \
                or (meshes[0] if meshes else None)
            if not src or src.type != 'MESH':
                raise RuntimeError("array 모드는 object(배열할 메시 이름)가 필요합니다. 있는 메시: "
                                   + ", ".join(o.name for o in meshes[:10]))
            arr = src.modifiers.new("arr", 'ARRAY')
            arr.fit_type = 'FIT_CURVE'
            arr.curve = curve
            crv = src.modifiers.new("crv", 'CURVE')
            crv.object = curve
            select_only([src])
            bpy.ops.object.modifier_apply(modifier="arr")
            bpy.ops.object.modifier_apply(modifier="crv")
            bpy.data.objects.remove(curve, do_unlink=True)
            out["result"] = src.name
            out["polys"] = len(src.data.polygons)
        out["mode"] = mode
        out["points"] = len(pts)

    elif action == "sockets":                    # 부착점 Empty 심기 — 유니티 장착 포인트(손·총구)
        import re as _re
        items = args.get("items") or []
        if not items:
            raise RuntimeError('sockets는 items=[{"name":"Socket_Muzzle","pos":[x,y,z],'
                               '"rot_deg":[0,0,0],"parent":"메시이름"}] 목록이 필요합니다.')
        made = []
        for it in items:
            name = _re.sub(r"[^A-Za-z0-9_.-]", "_", str(it.get("name") or "Socket"))[:60]
            name = name.strip("._-") or "Socket"  # 유니티가 이름으로 찾으므로 ASCII 강제
            e = bpy.data.objects.new(name, None)
            e.empty_display_type = 'PLAIN_AXES'
            e.empty_display_size = max(float(it.get("size", 0.1)), 0.01)
            scene.collection.objects.link(e)
            pname = str(it.get("parent") or "")
            parent = bpy.data.objects.get(pname) if pname else \
                (meshes[0] if len(meshes) == 1 else None)
            if pname and not parent:
                raise RuntimeError(f"parent '{pname}'가 없습니다. 있는 오브젝트: "
                                   + ", ".join(o.name for o in scene.objects[:10]))
            if parent:
                e.parent = parent
                e.matrix_parent_inverse = parent.matrix_world.inverted()
            e.location = [float(v) for v in (list(it.get("pos") or [0, 0, 0]) + [0, 0, 0])[:3]]
            e.rotation_euler = [math.radians(float(v))
                                for v in (list(it.get("rot_deg") or [0, 0, 0]) + [0, 0, 0])[:3]]
            made.append({"name": e.name, "parent": parent.name if parent else None})
        out["sockets"] = made

    elif action == "uv_atlas":                   # 여러 오브젝트 재질을 아틀라스 한 장으로(드로우콜↓)
        if not meshes:
            raise RuntimeError("아틀라스로 묶을 메시가 없습니다.")
        size = min(max(int(args.get("size", 2048)), 256), 4096)
        mats_before = {m.name for o in meshes for m in o.data.materials if m}
        for o in meshes:                          # 재질 없는 메시도 구울 수 있게 기본 재질
            if not o.data.materials:
                m = bpy.data.materials.new("mat_plain")
                m.use_nodes = True
                o.data.materials.append(m)
        for o in meshes:                          # 원래 UV는 읽기용(active_render), 아틀라스는 굽기용
            orig = o.data.uv_layers[0] if o.data.uv_layers else None
            if "AtlasUV" not in o.data.uv_layers:
                o.data.uv_layers.new(name="AtlasUV")
            o.data.uv_layers.active = o.data.uv_layers["AtlasUV"]
            if orig is not None:
                orig.active_render = True
        select_only(meshes)
        bpy.ops.object.mode_set(mode='EDIT')      # 여러 오브젝트 동시 편집 → 한 0~1 안에 같이 패킹
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
        bpy.ops.object.mode_set(mode='OBJECT')
        atlas = bpy.data.images.new("atlas", size, size, alpha=False)
        seen = set()
        for o in meshes:
            for slot in o.material_slots:
                m = slot.material
                if not m or m.name in seen:
                    continue
                seen.add(m.name)
                if not m.use_nodes:
                    m.use_nodes = True
                n = m.node_tree.nodes.new('ShaderNodeTexImage')
                n.image = atlas
                m.node_tree.nodes.active = n
        scene.render.engine = 'CYCLES'
        scene.cycles.device = 'CPU'
        scene.cycles.samples = min(max(int(args.get("samples", 16)), 4), 128)
        scene.render.bake.margin = 4
        select_only(meshes)
        bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'},
                            use_selected_to_active=False, use_clear=True)
        png = args["png_dest"]
        atlas.filepath_raw = png
        atlas.file_format = 'PNG'
        atlas.save()                              # 외부 파일 — FBX 옆에 두면 유니티가 자동 바인딩
        newm = bpy.data.materials.new("Atlas")
        newm.use_nodes = True
        bsdf = next(n for n in newm.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        tex = newm.node_tree.nodes.new('ShaderNodeTexImage')
        tex.image = atlas
        newm.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
        for o in meshes:
            o.data.materials.clear()
            o.data.materials.append(newm)
            for uv in [u for u in o.data.uv_layers if u.name != "AtlasUV"]:
                o.data.uv_layers.remove(uv)       # 아틀라스 UV만 남김 — 유니티에서 헷갈릴 일 없게
        for m in list(bpy.data.materials):
            if m.users == 0:
                bpy.data.materials.remove(m)
        try:
            atlas.pack()                          # 사본 .blend 안에도 픽셀을 품게
        except Exception:
            pass
        out.update({"materials_before": len(mats_before), "materials_after": 1,
                    "atlas": png, "size": size,
                    "meshes": [o.name for o in meshes]})

    elif action == "material_pbr":               # 텍스처 폴더 → Principled 자동 배선('갈색 덩어리' 예방)
        import re as _re
        tex_dir = str(args.get("tex_dir") or "")
        if not os.path.isdir(tex_dir):
            raise RuntimeError("material_pbr는 tex_dir(텍스처가 든 폴더)가 필요합니다.")
        _IMG = (".png", ".jpg", ".jpeg", ".tga", ".bmp", ".tif", ".tiff")
        files = sorted(f for f in os.listdir(tex_dir) if f.lower().endswith(_IMG))
        # 관용 명명은 접미사(Gun_Albedo·T_Gun_N) — 'metal_albedo.png'의 metal처럼 앞에 붙는
        # 재질 이름에 속지 않게 **마지막 토큰 우선**, 그 다음에야 아무 토큰으로 폴백.
        _KEYS = (("albedo", ("albedo", "basecolor", "diffuse", "color", "col", "alb", "d", "c")),
                 ("normal", ("normal", "nrm", "nor", "norm", "n")),
                 ("rough", ("roughness", "rough", "rgh", "r")),
                 ("metal", ("metallic", "metal", "met", "m")),
                 ("ao", ("ambientocclusion", "occlusion", "ao")))

        def _toks(f):
            return [t for t in _re.split(r"[^a-z0-9]+",
                                         os.path.splitext(f)[0].lower()) if t]

        def _hit(tok, keys):                      # 한 글자 키(_N 등)는 정확히 일치할 때만
            return tok in keys or any(len(k) >= 3 and tok.startswith(k) for k in keys)

        found = {}
        used = set()
        for last_only in (True, False):
            for ch, keys in _KEYS:
                if ch in found:
                    continue
                for f in files:
                    if f in used:
                        continue
                    tt = _toks(f)
                    cand = tt[-1:] if last_only else tt
                    if any(_hit(t, keys) for t in cand):
                        found[ch] = os.path.join(tex_dir, f)
                        used.add(f)
                        break
        if not found:
            raise RuntimeError("폴더에서 albedo/normal/rough/metal/ao 규칙으로 매칭되는 "
                               "텍스처를 못 찾았습니다. 파일: " + ", ".join(files[:8]))
        if not meshes:
            raise RuntimeError("재질을 입힐 메시가 없습니다.")
        mat = bpy.data.materials.new(str(args.get("name") or "PBR_mat")[:60])
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')

        def tex_node(path, noncolor, y):
            img = bpy.data.images.load(path)
            base = _re.sub(r"[^A-Za-z0-9_.-]", "_", os.path.basename(path))
            img.name = base.strip("._-") or "tex"  # ASCII 개명 — 유니티 임포트 경로 안 깨지게
            if noncolor:
                img.colorspace_settings.name = 'Non-Color'
            n = nt.nodes.new('ShaderNodeTexImage')
            n.image = img
            n.location = (-560, y)
            return n

        wired = {}
        if "albedo" in found:
            alb = tex_node(found["albedo"], False, 360)
            if "ao" in found:                     # AO는 albedo에 곱해 넣음
                ao = tex_node(found["ao"], True, 120)
                mix = nt.nodes.new('ShaderNodeMix')
                mix.data_type = 'RGBA'
                mix.blend_type = 'MULTIPLY'
                mix.location = (-260, 300)
                mix.inputs["Factor"].default_value = 1.0
                in_a = next(s for s in mix.inputs if s.name == "A" and s.type == 'RGBA')
                in_b = next(s for s in mix.inputs if s.name == "B" and s.type == 'RGBA')
                out_c = next(s for s in mix.outputs if s.type == 'RGBA')
                nt.links.new(alb.outputs['Color'], in_a)
                nt.links.new(ao.outputs['Color'], in_b)
                nt.links.new(out_c, bsdf.inputs['Base Color'])
                wired["ao"] = os.path.basename(found["ao"])
            else:
                nt.links.new(alb.outputs['Color'], bsdf.inputs['Base Color'])
            wired["albedo"] = os.path.basename(found["albedo"])
        if "rough" in found:
            n = tex_node(found["rough"], True, -120)
            nt.links.new(n.outputs['Color'], bsdf.inputs['Roughness'])
            wired["rough"] = os.path.basename(found["rough"])
        if "metal" in found:
            n = tex_node(found["metal"], True, -360)
            nt.links.new(n.outputs['Color'], bsdf.inputs['Metallic'])
            wired["metal"] = os.path.basename(found["metal"])
        if "normal" in found:
            n = tex_node(found["normal"], True, -600)
            nm = nt.nodes.new('ShaderNodeNormalMap')
            nm.location = (-260, -520)
            nt.links.new(n.outputs['Color'], nm.inputs['Color'])
            nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
            wired["normal"] = os.path.basename(found["normal"])
        want = args.get("targets")
        targets = [o for o in meshes if o.name in list(want)] if want else meshes
        if not targets:
            raise RuntimeError("targets에 해당하는 메시가 없습니다. 있는 메시: "
                               + ", ".join(o.name for o in meshes[:10]))
        no_uv = []
        for o in targets:
            if not o.data.uv_layers:              # 텍스처는 UV가 있어야 붙음
                select_only([o])
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
                bpy.ops.object.mode_set(mode='OBJECT')
                no_uv.append(o.name)
            o.data.materials.clear()
            o.data.materials.append(mat)
        try:
            bpy.ops.file.pack_all()               # 사본 .blend가 픽셀을 품게(원본 텍스처 불가침)
        except Exception:
            pass
        out.update({"material": mat.name, "channels": wired,
                    "targets": [o.name for o in targets], "uv_added": no_uv})

    elif action == "bevel":                      # 모서리 챔퍼 — 각도 제한이라 평평한 면은 안 건드림
        width = float(args.get("width", 0.02))
        segments = max(1, min(int(args.get("segments", 2)), 6))
        angle = float(args.get("angle", 30))
        before = sum(len(o.data.polygons) for o in meshes)
        for o in meshes:
            select_only([o])
            mod = o.modifiers.new("bv", 'BEVEL')
            mod.width = width
            mod.segments = segments
            mod.limit_method = 'ANGLE'
            mod.angle_limit = math.radians(angle)
            bpy.ops.object.modifier_apply(modifier="bv")
        out.update({"beveled": [o.name for o in meshes], "width": width,
                    "segments": segments, "polys_before": before,
                    "polys_after": sum(len(o.data.polygons) for o in meshes)})

    elif action == "solidify":                   # 두께 입히기 — 종이장 벽·컵에 진짜 두께(안쪽 뻥 뚫림 방지)
        thick = float(args.get("thickness", 0.02))
        want = args.get("targets")
        targets = [o for o in meshes if o.name in list(want)] if want else meshes
        if not targets:
            raise RuntimeError("targets에 해당하는 메시가 없습니다. 있는 메시: "
                               + ", ".join(o.name for o in meshes[:10]))
        before = sum(len(o.data.polygons) for o in targets)
        for o in targets:
            select_only([o])
            mod = o.modifiers.new("so", 'SOLIDIFY')
            mod.thickness = thick
            mod.offset = float(args.get("offset", -1.0))   # -1=안쪽으로 두께(겉모습 유지)
            mod.use_even_offset = True
            bpy.ops.object.modifier_apply(modifier="so")
        out.update({"solidified": [o.name for o in targets], "thickness": thick,
                    "polys_before": before,
                    "polys_after": sum(len(o.data.polygons) for o in targets)})

    elif action == "shade":                      # 셰이딩: smooth·flat·auto(각도 기준 자동 스무스)
        mode = str(args.get("mode", "auto")).lower()
        angle = float(args.get("angle", 30))
        if not meshes:
            raise RuntimeError("셰이딩을 바꿀 메시가 없습니다.")
        select_only(meshes)
        if mode == "flat":
            bpy.ops.object.shade_flat()
        elif mode == "smooth":
            bpy.ops.object.shade_smooth()
        else:                                     # auto — 급한 모서리는 각지게, 완만한 면은 부드럽게
            try:                                  # 4.1+에서 자동 스무스가 별도 op로 바뀜
                bpy.ops.object.shade_auto_smooth(angle=math.radians(angle))
            except AttributeError:
                bpy.ops.object.shade_smooth()
        out.update({"mode": mode, "angle": angle, "shaded": [o.name for o in meshes]})

    elif action == "lightmap_uv":                # 유니티 라이트맵용 두 번째 UV(UV2) 깔기
        margin = float(args.get("margin", 0.05))
        done, skipped = [], []
        for o in meshes:
            uvs = o.data.uv_layers
            if any(u.name == "Lightmap" for u in uvs):
                skipped.append(o.name)
                continue
            if not uvs:                           # UV0조차 없으면 먼저 깔아줌
                select_only([o])
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
                bpy.ops.object.mode_set(mode='OBJECT')
            lm = uvs.new(name="Lightmap")
            uvs.active = lm                       # 펼침 대상 레이어로 지정 후 펼침
            select_only([o])
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=margin)
            bpy.ops.object.mode_set(mode='OBJECT')
            uvs.active = uvs[0]                   # 기본 UV로 복귀(uv_atlas의 active 교훈)
            uvs[0].active_render = True
            done.append(o.name)
        if not done and not skipped:
            raise RuntimeError("라이트맵 UV를 깔 메시가 없습니다.")
        out.update({"lightmap_added": done, "already": skipped, "margin": margin})

    elif action == "rename":                     # 오브젝트·재질 ASCII 일괄 개명 — 유니티 위생
        import re as _re
        prefix = str(args.get("prefix") or "")

        def _ascii_nm(name, used):
            base = _re.sub(r"[^A-Za-z0-9_.-]", "_", name)
            base = _re.sub(r"_+", "_", base).strip("._-") or "Item"
            base = prefix + base
            cand, n = base, 2
            while cand in used:
                cand = f"{base}_{n}"
                n += 1
            return cand

        ren_obj, ren_mat = {}, {}
        for o in list(scene.objects):
            if o.type in ('CAMERA', 'LIGHT'):
                continue
            new = _ascii_nm(o.name, {x.name for x in scene.objects} - {o.name})
            if new != o.name:
                ren_obj[o.name] = new
                o.name = new
            if o.data is not None and getattr(o.data, "users", 0) == 1:
                o.data.name = o.name              # 데이터 이름도 따라가게(내보내기 목록 깔끔히)
        for m in bpy.data.materials:
            new = _ascii_nm(_re.sub(r"\.\d{3}$", "", m.name),
                            {x.name for x in bpy.data.materials} - {m.name})
            if new != m.name:
                ren_mat[m.name] = new
                m.name = new
        # 본(뼈)은 애니·웨이트가 이름으로 묶여 있어 일부러 안 건드립니다.
        out.update({"objects": ren_obj, "materials": ren_mat})

    elif action == "normals":                    # 법선 전수진단+수리 — '안쪽이 비쳐 보임' 근절(세션61 노하우)
        import bmesh
        report = []
        for o in meshes:
            bm = bmesh.new()
            bm.from_mesh(o.data)
            vol_before = bm.calc_volume(signed=True) if bm.faces else 0.0
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])   # 바깥 방향으로 재계산
            vol_after = bm.calc_volume(signed=True) if bm.faces else 0.0
            if vol_after < 0:                     # 재계산 뒤에도 음수면 통째 뒤집힘 — 전부 플립
                for f in bm.faces:
                    f.normal_flip()
                vol_after = bm.calc_volume(signed=True)
            bm.to_mesh(o.data)
            bm.free()
            report.append({"name": o.name, "vol_before": round(vol_before, 6),
                           "vol_after": round(vol_after, 6),
                           "fixed": vol_before < 0 <= vol_after})
        out["normals"] = report
        out["fixed"] = [x["name"] for x in report if x["fixed"]]

    elif action == "align":                      # 기계적 정렬: ground(바닥 스냅)·row(일렬)·grid(격자)
        from mathutils import Vector
        mode = str(args.get("mode", "ground")).lower()
        gap = float(args.get("gap", 0.2))
        axis = {"x": 0, "y": 1}.get(str(args.get("axis", "x")).lower(), 0)
        roots = sorted((o for o in scene.objects
                        if o.parent is None and o.type not in ('CAMERA', 'LIGHT', 'EMPTY')),
                       key=lambda o: o.name)
        if not roots:
            raise RuntimeError("정렬할 오브젝트가 없습니다.")

        def _bbox_w(o):
            pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
            for ch in getattr(o, "children_recursive", []):   # 조립품은 자식까지 통으로 재야 맞음
                if ch.type == 'MESH':
                    pts += [ch.matrix_world @ Vector(c) for c in ch.bound_box]
            return ([min(p[i] for p in pts) for i in range(3)],
                    [max(p[i] for p in pts) for i in range(3)])

        placed = []
        if mode == "ground":
            for o in roots:
                lo, hi = _bbox_w(o)
                o.location.z -= lo[2]
                placed.append({"name": o.name, "moved_z": round(-lo[2], 4)})
        elif mode in ("row", "grid"):
            other = 1 - axis
            cols = (max(1, int(args.get("cols", math.ceil(math.sqrt(len(roots))))))
                    if mode == "grid" else len(roots))
            cursor, row_pos, row_depth = 0.0, 0.0, 0.0
            for i, o in enumerate(roots):
                lo, hi = _bbox_w(o)
                if mode == "grid" and i and i % cols == 0:
                    cursor = 0.0
                    row_pos += row_depth + gap
                    row_depth = 0.0
                o.location[axis] += cursor - lo[axis]
                if mode == "grid":
                    o.location[other] += row_pos - lo[other]
                o.location.z -= lo[2]             # 바닥도 같이 스냅
                cursor += (hi[axis] - lo[axis]) + gap
                row_depth = max(row_depth, hi[other] - lo[other])
                placed.append({"name": o.name,
                               "pos": [round(v, 3) for v in o.location]})
        else:
            raise RuntimeError("align의 mode는 ground·row·grid 중 하나입니다.")
        out.update({"mode": mode, "aligned": placed})

    elif action == "purge":                      # 미사용(고아) 데이터 청소 — 파일 다이어트
        # 0-user 데이터는 저장 때 어차피 버려짐 — 실파일에서 살아남는 고아는 대부분
        # fake user(방패 F)만 잡고 있는 것(임포트 찌꺼기 액션 등). 기본은 보고만,
        # include_fake=true일 때만 방패를 벗겨 지웁니다(원하는 예비 액션까지 지울 수 있어서).
        kinds = ("meshes", "materials", "images", "actions", "armatures", "textures",
                 "node_groups", "curves", "cameras", "lights", "worlds", "collections")
        before = {k: len(getattr(bpy.data, k, [])) for k in kinds}
        removed = 0
        include_fake = bool(args.get("include_fake"))
        for _ in range(4):                        # 재질→텍스처→이미지처럼 얽힌 고아는 몇 바퀴 돌며 비움
            n = 0
            for k in kinds:
                coll = getattr(bpy.data, k, None)
                if coll is None:
                    continue
                for d in list(coll):
                    dead = d.users == 0 and not d.use_fake_user
                    fake_only = d.use_fake_user and d.users == 1
                    if dead or (include_fake and fake_only):
                        try:
                            if fake_only:
                                d.use_fake_user = False
                            coll.remove(d)
                            n += 1
                        except Exception:
                            pass
            removed += n
            if n == 0:
                break
        fake_left = [f"{k}:{d.name}" for k in kinds for d in getattr(bpy.data, k, [])
                     if d.use_fake_user and d.users == 1][:10]
        out.update({"purged": removed,
                    "detail": {k: before[k] - len(getattr(bpy.data, k, []))
                               for k in kinds if before[k] != len(getattr(bpy.data, k, []))},
                    "fake_only_left": fake_left})

    elif action == "pose_apply":                 # 포즈 JSON → 키프레임(설계는 클로드·적용은 루시 분업)
        arm = next((o for o in scene.objects if o.type == 'ARMATURE'), None)
        if not arm:
            raise RuntimeError("아마추어(뼈대)가 없습니다 — bone_template로 뼈대를 먼저 놓거나 "
                               "리깅된 파일에 쓰세요.")
        poses = args.get("poses") or []
        select_only([arm])
        bpy.ops.object.mode_set(mode='POSE')
        bone_names = {b.name for b in arm.pose.bones}
        missing, keyed, frames = set(), set(), []
        for p in poses:
            f = int(p.get("frame", 1))
            frames.append(f)
            for bname, spec in (p.get("bones") or {}).items():
                pb = arm.pose.bones.get(bname)
                if not pb:
                    missing.add(bname)
                    continue
                pb.rotation_mode = 'XYZ'
                if spec.get("rot_deg") is not None:
                    pb.rotation_euler = tuple(math.radians(float(v)) for v in spec["rot_deg"])
                    pb.keyframe_insert("rotation_euler", frame=f)
                if spec.get("loc") is not None:
                    pb.location = tuple(float(v) for v in spec["loc"])
                    pb.keyframe_insert("location", frame=f)
                keyed.add(bname)
        bpy.ops.object.mode_set(mode='OBJECT')
        if not keyed:
            raise RuntimeError("포즈의 본 이름이 하나도 안 맞습니다. 있는 본: "
                               + ", ".join(sorted(bone_names)[:15]))
        scene.frame_start = min(frames)
        scene.frame_end = max(frames)
        if args.get("name") and arm.animation_data and arm.animation_data.action:
            arm.animation_data.action.name = str(args["name"])
        scene.frame_set(max(frames))              # 미리보기가 마지막 포즈를 찍게
        out.update({"frames": sorted(set(frames)), "keyed_bones": sorted(keyed),
                    "missing_bones": sorted(missing),
                    "action": (arm.animation_data.action.name
                               if arm.animation_data and arm.animation_data.action else None)})

    elif action == "physics_bake":               # 물리 굽기 — rigid(떨어뜨려 안착)·cloth(드리워 고정)
        mode = str(args.get("mode", "rigid")).lower()
        frames = max(10, min(int(args.get("frames", 60)), 250))
        scene.frame_start = 1
        scene.frame_end = frames
        if mode == "rigid":
            if not meshes:
                raise RuntimeError("떨어뜨릴 메시가 없습니다.")
            if not scene.rigidbody_world:
                bpy.ops.rigidbody.world_add()
            scene.rigidbody_world.point_cache.frame_end = frames
            ground = None
            if args.get("ground", True):          # 바닥이 없으면 임시로 깔고 굽기 뒤 치움
                center, size = scene_bbox()
                bpy.ops.mesh.primitive_plane_add(size=max(size * 4, 4),
                                                 location=(center[0], center[1], 0))
                ground = bpy.context.object
                ground.name = "B3D_Ground"
                select_only([ground])
                bpy.ops.rigidbody.object_add(type='PASSIVE')
            for o in meshes:
                select_only([o])
                bpy.ops.rigidbody.object_add(type='ACTIVE')
            # ⚠bake_to_keyframes는 내부의 keyframe op가 헤드리스 컨텍스트에서 죽음(실측) →
            # 프레임을 차례로 밟으며 평가된 행렬을 기록하고, 시뮬을 걷어낸 뒤
            # 데이터 API(keyframe_insert)로 직접 굽습니다 — 컨텍스트 무관.
            deps = bpy.context.evaluated_depsgraph_get()
            rec = {o.name: [] for o in meshes}
            for f in range(1, frames + 1):
                scene.frame_set(f)
                for o in meshes:
                    ev = o.evaluated_get(deps)
                    loc, rot, _ = ev.matrix_world.decompose()
                    rec[o.name].append((f, tuple(loc), tuple(rot.to_euler())))
            if ground:
                bpy.data.objects.remove(ground, do_unlink=True)
            try:
                bpy.ops.rigidbody.world_remove()  # 시뮬을 걷어내야 키프레임이 움직임을 몰게 됨
            except Exception:
                pass
            for o in meshes:
                o.rotation_mode = 'XYZ'
                for f, loc, rot in rec[o.name]:
                    o.location = loc
                    o.rotation_euler = rot
                    o.keyframe_insert("location", frame=f)
                    o.keyframe_insert("rotation_euler", frame=f)
            scene.frame_set(frames)
            out.update({"mode": "rigid", "frames": frames,
                        "settled": [{"name": o.name,
                                     "z": round(rec[o.name][-1][1][2], 3)}
                                    for o in meshes]})
        elif mode == "cloth":
            if len(meshes) < 1:
                raise RuntimeError("천으로 삼을 메시가 없습니다.")
            tgt_name = args.get("target")
            tgt = next((o for o in meshes if o.name == tgt_name), None)
            if tgt_name and not tgt:
                raise RuntimeError(f"target '{tgt_name}' 메시가 없습니다. 있는 메시: "
                                   + ", ".join(o.name for o in meshes[:10]))
            if not tgt:                           # 지정 없으면 가장 높이 있는 메시를 천으로(테이블보 관례)
                tgt = max(meshes, key=lambda o: o.matrix_world.translation.z)
            others = [o for o in meshes if o is not tgt]
            cl = tgt.modifiers.new("cl", 'CLOTH')
            cl.settings.quality = 5
            for o in others:
                o.modifiers.new("col", 'COLLISION')
            z0 = max((tgt.matrix_world @ v.co).z for v in tgt.data.vertices)
            for f in range(1, frames + 1):        # 헤드리스는 프레임을 차례로 밟아야 시뮬이 굴러감
                scene.frame_set(f)
            select_only([tgt])
            bpy.ops.object.modifier_apply(modifier="cl")   # 마지막 프레임 모양을 실메시로 고정
            for o in others:
                for m in [x for x in o.modifiers if x.type == 'COLLISION']:
                    o.modifiers.remove(m)
            z1 = max((tgt.matrix_world @ v.co).z for v in tgt.data.vertices)
            out.update({"mode": "cloth", "target": tgt.name, "frames": frames,
                        "top_z_before": round(z0, 4), "top_z_after": round(z1, 4)})
        else:
            raise RuntimeError("physics_bake의 mode는 rigid·cloth 중 하나입니다.")

    elif action == "sculpt_displace":            # 절차적 유기 디테일 — 브러시 스컬프의 헤드리스 대체
        # 헤드리스에는 '손'이 없어 브러시 스컬프가 불가능합니다. 대신 면을 잘게 나눈 뒤
        # 절차적 텍스처로 표면을 밀어 유기적 요철(빵 골결·주름·돌기)을 만듭니다 —
        # 버거·스테이크(steak_v4)를 만든 기법과 같은 것을 도구로 굳힌 것입니다.
        # ⚠️형태를 '창작'하지 않습니다. 이미 대략 맞는 덩어리의 **표면**만 거칠게 합니다.
        PATTERNS = {                              # 이름 → (레거시 텍스처 타입, 기본 크기배수)
            "bumpy":   ('CLOUDS', 1.0),           # 뭉실한 요철 — 빵·반죽 표면
            "wrinkle": ('DISTORTED_NOISE', 0.6),  # 불규칙 주름 — 토마토·채소
            "groove":  ('WOOD', 1.0),             # 결·골 — 빵 골결, 고기 결
            "cell":    ('VORONOI', 0.8),          # 오돌토돌 알갱이 — 참깨·치즈 구멍
            "rough":   ('STUCCI', 0.5),           # 미세 거칠기 — 마감용
        }
        pattern = str(args.get("pattern", "bumpy")).lower()
        if pattern not in PATTERNS:
            raise RuntimeError("pattern은 " + ", ".join(PATTERNS) + " 중 하나입니다.")
        tex_type, scale_mul = PATTERNS[pattern]

        want = args.get("targets")
        targets = [o for o in meshes if o.name in list(want)] if want else meshes
        if not targets:
            raise RuntimeError("targets에 해당하는 메시가 없습니다. 있는 메시: "
                               + ", ".join(o.name for o in meshes[:10]))

        _, scene_sz = scene_bbox()
        # strength=요철 깊이(m), feature=무늬 한 칸 크기(m). 안 주면 모델 크기에 비례해 잡습니다.
        strength = float(args.get("strength", scene_sz * 0.03))
        feature = float(args.get("feature", scene_sz * 0.15)) * scale_mul
        if feature <= 0:
            raise RuntimeError("feature(무늬 크기)는 0보다 커야 합니다.")
        subdiv = max(0, min(int(args.get("subdiv", 2)), 4))
        seed = int(args.get("seed", 0))

        # ⭐폭주 방지: SIMPLE 서브디비전은 레벨당 면 4배 — 예산을 넘길 것 같으면 미리 막습니다.
        cap = int(args.get("max_tris", 300000))
        before = sum(len(o.data.polygons) for o in targets)
        projected = before * (4 ** subdiv)
        if projected > cap:
            raise RuntimeError(
                f"면이 {before:,}→약 {projected:,}개로 늘어 상한({cap:,})을 넘습니다. "
                f"subdiv를 {subdiv}보다 낮추거나 max_tris를 올리세요.")

        tex = bpy.data.textures.new(f"sd_{pattern}", type=tex_type)
        for attr, val in (("noise_scale", feature), ("noise_depth", 2)):
            try:                                  # 텍스처 종류마다 있는 속성이 달라 있는 것만
                setattr(tex, attr, val)
            except (AttributeError, TypeError):
                pass
        if seed:                                  # 같은 seed=같은 무늬(재현 가능)
            try:
                tex.noise_basis = ('BLENDER_ORIGINAL', 'ORIGINAL_PERLIN', 'IMPROVED_PERLIN',
                                   'VORONOI_F1', 'CELL_NOISE')[seed % 5]
            except (AttributeError, TypeError):
                pass

        done = []
        for o in targets:
            select_only([o])
            if subdiv:                            # 요철을 담을 면 밀도 확보
                sub = o.modifiers.new("sd_sub", 'SUBSURF')
                sub.subdivision_type = 'SIMPLE'   # ⭐SIMPLE — 실루엣을 안 줄임(CATMULL은 오므라듦)
                sub.levels = sub.render_levels = subdiv
                bpy.ops.object.modifier_apply(modifier="sd_sub")
            mod = o.modifiers.new("sd_disp", 'DISPLACE')
            mod.texture = tex
            mod.texture_coords = 'LOCAL'          # 오브젝트에 무늬가 붙어 다님(움직여도 안 헤엄침)
            mod.strength = strength
            mod.mid_level = 0.5                   # 0.5=안팎 양방향(부피 유지) / 0=바깥으로만 부풂
            bpy.ops.object.modifier_apply(modifier="sd_disp")
            done.append(o.name)
        if args.get("smooth", True):              # 요철은 부드럽게 셰이딩해야 유기적으로 보임
            select_only(targets)
            try:
                bpy.ops.object.shade_auto_smooth(angle=math.radians(40))
            except AttributeError:
                bpy.ops.object.shade_smooth()
        after = sum(len(o.data.polygons) for o in targets)
        out.update({"pattern": pattern, "displaced": done, "strength": round(strength, 4),
                    "feature": round(feature, 4), "subdiv": subdiv,
                    "polys_before": before, "polys_after": after})

    elif action == "taper":
        top_factor = float(args.get("top_factor", 0.5))
        bottom_factor = float(args.get("bottom_factor", 1.0))
        axis_str = str(args.get("axis", "z")).lower()
        axis_idx = {"x": 0, "y": 1, "z": 2}.get(axis_str, 2)
        other_axes = [i for i in range(3) if i != axis_idx]

        want = args.get("targets")
        targets = [o for o in meshes if o.name in list(want)] if want else meshes
        if not targets:
            raise RuntimeError("targets에 해당하는 메시가 없습니다.")

        done = []
        for o in targets:
            import bmesh
            bm = bmesh.new()
            bm.from_mesh(o.data)
            coords = [v.co[axis_idx] for v in bm.verts]
            if not coords:
                bm.free()
                continue
            min_v, max_v = min(coords), max(coords)
            rng = (max_v - min_v) if (max_v - min_v) > 1e-6 else 1.0
            for v in bm.verts:
                t = (v.co[axis_idx] - min_v) / rng
                factor = bottom_factor * (1.0 - t) + top_factor * t
                for oa in other_axes:
                    v.co[oa] *= factor
            bm.to_mesh(o.data)
            bm.free()
            o.data.update()
            done.append(o.name)

        out.update({"tapered": done, "top_factor": top_factor, "bottom_factor": bottom_factor, "axis": axis_str})

    elif action == "extrude_face":
        face_dir = str(args.get("face", "top")).lower()
        distance = float(args.get("distance", 0.5))
        scale = float(args.get("scale", 1.0))

        dir_vectors = {
            "top": (0, 0, 1),
            "bottom": (0, 0, -1),
            "front": (0, -1, 0),
            "back": (0, 1, 0),
            "left": (-1, 0, 0),
            "right": (1, 0, 0),
        }
        target_vec = dir_vectors.get(face_dir, (0, 0, 1))

        want = args.get("targets")
        targets = [o for o in meshes if o.name in list(want)] if want else meshes
        if not targets:
            raise RuntimeError("targets에 해당하는 메시가 없습니다.")

        done = []
        for o in targets:
            import bmesh
            from mathutils import Vector
            bm = bmesh.new()
            bm.from_mesh(o.data)
            bm.faces.ensure_lookup_table()

            t_vec = Vector(target_vec).normalized()
            best_faces = []
            for f in bm.faces:
                dot = f.normal.dot(t_vec)
                if dot > 0.5:
                    best_faces.append((dot, f))

            if best_faces:
                best_faces.sort(key=lambda x: x[0], reverse=True)
                sel_faces = [f for dot, f in best_faces if dot >= best_faces[0][0] - 0.1]
                res = bmesh.ops.extrude_face_region(bm, faces=sel_faces)
                extruded_verts = [v for v in res["geom"] if isinstance(v, bmesh.types.BMVert)]

                move_vec = t_vec * distance
                for v in extruded_verts:
                    v.co += move_vec

                if scale != 1.0 and extruded_verts:
                    center = Vector((0, 0, 0))
                    for v in extruded_verts:
                        center += v.co
                    center /= len(extruded_verts)
                    for v in extruded_verts:
                        v.co = center + (v.co - center) * scale

                bm.to_mesh(o.data)
                done.append(o.name)
            bm.free()
            o.data.update()

        out.update({"extruded": done, "face": face_dir, "distance": distance, "scale": scale})

    elif action == "inset_face":
        face_dir = str(args.get("face", "top")).lower()
        thickness = float(args.get("thickness", 0.1))
        depth = float(args.get("depth", -0.1))

        dir_vectors = {
            "top": (0, 0, 1),
            "bottom": (0, 0, -1),
            "front": (0, -1, 0),
            "back": (0, 1, 0),
            "left": (-1, 0, 0),
            "right": (1, 0, 0),
        }
        target_vec = dir_vectors.get(face_dir, (0, 0, 1))

        want = args.get("targets")
        targets = [o for o in meshes if o.name in list(want)] if want else meshes
        if not targets:
            raise RuntimeError("targets에 해당하는 메시가 없습니다.")

        done = []
        for o in targets:
            import bmesh
            from mathutils import Vector
            bm = bmesh.new()
            bm.from_mesh(o.data)
            bm.faces.ensure_lookup_table()

            t_vec = Vector(target_vec).normalized()
            best_faces = [f for f in bm.faces if f.normal.dot(t_vec) > 0.5]
            if best_faces:
                res = bmesh.ops.inset_individual(bm, faces=best_faces, thickness=thickness, depth=0.0)
                inset_faces = [f for f in res["faces"]]
                if depth != 0.0:
                    for f in inset_faces:
                        move_vec = f.normal * depth
                        for v in f.verts:
                            v.co += move_vec

                bm.to_mesh(o.data)
                done.append(o.name)
            bm.free()
            o.data.update()

        out.update({"inset": done, "face": face_dir, "thickness": thickness, "depth": depth})

    elif action == "deform_mesh":
        mode_str = str(args.get("mode", "bend")).upper()
        if mode_str not in ("BEND", "TWIST", "TAPER", "STRETCH"):
            mode_str = "BEND"
        angle_deg = float(args.get("angle_deg", 45.0))
        axis_str = str(args.get("axis", "z")).upper()

        want = args.get("targets")
        targets = [o for o in meshes if o.name in list(want)] if want else meshes
        if not targets:
            raise RuntimeError("targets에 해당하는 메시가 없습니다.")

        done = []
        for o in targets:
            select_only([o])
            mod = o.modifiers.new("def_mod", 'SIMPLE_DEFORM')
            mod.deform_method = mode_str
            mod.deform_axis = axis_str
            mod.angle = math.radians(angle_deg)
            try:
                bpy.ops.object.modifier_apply(modifier="def_mod")
                done.append(o.name)
            except Exception as e:
                o.modifiers.remove(mod)

        out.update({"deformed": done, "mode": mode_str.lower(), "angle_deg": angle_deg, "axis": axis_str.lower()})

    elif action == "prep_unity":                 # 유니티용 한 방: 적용+바닥원점+정리+FBX+검증
        import bmesh
        from mathutils import Vector
        polys = sum(len(o.data.polygons) for o in meshes)
        # 1) 스케일·회전 적용 (유니티 크기 어긋남 방지)
        select_only(meshes)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        # 2) 바닥 중심을 월드 원점으로
        center, _ = scene_bbox()
        lo_z = 1e9
        for o in meshes:
            for c in o.bound_box:
                lo_z = min(lo_z, (o.matrix_world @ Vector(c)).z)
        dx, dy, dz = -center[0], -center[1], -lo_z
        for o in [m for m in scene.objects if m.parent is None
                  and m.type not in ('CAMERA', 'LIGHT')]:
            o.location.x += dx
            o.location.y += dy
            o.location.z += dz
        # 3) 정리 — 중복 정점·부스러기·법선
        removed = 0
        for o in meshes:
            before = len(o.data.vertices)
            bm = bmesh.new()
            bm.from_mesh(o.data)
            bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0001)
            loose = [v for v in bm.verts if not v.link_faces]
            bmesh.ops.delete(bm, geom=loose, context='VERTS')
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
            bm.to_mesh(o.data)
            bm.free()
            removed += before - len(o.data.vertices)
        # 4) 스스로 검증 — 스케일이 정말 1인가
        bad = [o.name for o in meshes if any(abs(s - 1.0) > 1e-4 for s in o.scale)]
        # 5) FBX 내보내기 (부착점 Empty가 있으면 같이 — 유니티 장착 포인트)
        dest = args["fbx_dest"]
        select_only(meshes + [o for o in scene.objects
                              if o.type == 'EMPTY' and not o.name.startswith("B3D_")])
        bpy.ops.export_scene.fbx(filepath=dest, use_selection=True,
                                 add_leaf_bones=False, apply_scale_options='FBX_SCALE_ALL')
        out["applied"] = len(meshes)
        out["moved_by"] = [round(v, 4) for v in (dx, dy, dz)]
        out["removed_verts"] = removed
        out["polys"] = polys
        out["scale_ok"] = (len(bad) == 0)
        out["bad_scale"] = bad
        out["exported"] = dest

    elif action == "chain":                      # 여러 작업을 한 세션에(콜드부팅 세금 절약)
        import bmesh
        from mathutils import Vector
        for op in args.get("ops", []):
            if op == "apply":
                select_only(meshes)
                bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            elif op == "cleanup":
                for o in meshes:
                    bm = bmesh.new()
                    bm.from_mesh(o.data)
                    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0001)
                    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces],
                                     context='VERTS')
                    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
                    bm.to_mesh(o.data)
                    bm.free()
            elif op == "decimate":
                ratio = min(max(float(args.get("ratio", 0.5)), 0.05), 0.95)
                for o in meshes:
                    select_only([o])
                    mod = o.modifiers.new("dec", 'DECIMATE')
                    mod.ratio = ratio
                    bpy.ops.object.modifier_apply(modifier="dec")
            elif op == "uv":
                for o in [m for m in meshes if not m.data.uv_layers]:
                    select_only([o])
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.select_all(action='SELECT')
                    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
                    bpy.ops.object.mode_set(mode='OBJECT')
            elif op == "origin":
                center, _ = scene_bbox()
                lo_z = min((o.matrix_world @ Vector(c)).z for o in meshes for c in o.bound_box)
                for o in [m for m in scene.objects if m.parent is None
                          and m.type not in ('CAMERA', 'LIGHT')]:
                    o.location.x -= center[0]
                    o.location.y -= center[1]
                    o.location.z -= lo_z
            elif op == "join":
                if len(meshes) >= 2:
                    select_only(meshes)
                    bpy.ops.object.join()
            meshes = [o for o in scene.objects if o.type == 'MESH']   # join 등 뒤 갱신
        out["chain"] = list(args.get("ops", []))
        if args.get("export"):
            dest = args["export_dest"]
            select_only(meshes)
            if args["export"] == "glb":
                bpy.ops.export_scene.gltf(filepath=dest, use_selection=True, export_format='GLB')
            else:
                bpy.ops.export_scene.fbx(filepath=dest, use_selection=True,
                                         add_leaf_bones=False, apply_scale_options='FBX_SCALE_ALL')
            out["exported"] = dest

    bpy.context.preferences.filepaths.save_version = 0   # .blend1 백업 안 남김(사본 폴더 깔끔히)
    bpy.ops.wm.save_mainfile()                   # 사본을 저장 — 원본은 여기 없습니다

    # 수술 결과를 눈으로 — 미리보기 한 장을 옆에 찍어 줍니다.
    # ⚠uv_atlas는 제외: Cycles 베이크 뒤 같은 부팅에서 EEVEE 렌더를 하면 블렌더 5.0.1이
    # ACCESS_VIOLATION으로 죽습니다(실측·결정적). 미리보기는 밖(tools)이 새 부팅으로 찍습니다.
    if args.get("preview_dir") and action != "uv_atlas":
        center, size = scene_bbox()
        bpy.ops.object.camera_add()
        cam = bpy.context.object
        bpy.context.scene.camera = cam
        a = math.radians(40)
        dist = size * 2.1
        # 배치류(정렬·배열·뿌리기)는 낮은 앵글이면 앞뒤 물체가 겹쳐 보여 눈검수가 오판함(실측)
        # → 부감(높은 앵글)으로 찍어 배치가 한눈에 보이게.
        cam_z = center[2] + (dist * 0.85 if action in ("align", "array", "scatter")
                             else size * 0.35)
        cam.location = (center[0] + math.sin(a) * dist, center[1] - math.cos(a) * dist,
                        cam_z)
        tgt = bpy.data.objects.new("B3D_T", None)
        bpy.context.scene.collection.objects.link(tgt)
        from mathutils import Vector
        tgt.location = Vector(center)
        tr = cam.constraints.new('TRACK_TO')
        tr.target = tgt
        tr.track_axis = 'TRACK_NEGATIVE_Z'
        tr.up_axis = 'UP_Y'
        if not any(o.type == 'LIGHT' for o in bpy.context.scene.objects):
            bpy.ops.object.light_add(type='SUN', location=(center[0] + size,
                                                           center[1] - size * 1.5,
                                                           center[2] + size * 2))
            bpy.context.object.data.energy = 3.0
            # 회전 없는 태양=수직 낙사로 옆면이 새까매짐(전/후 비교에서 실측) — 렌더 액션과 통일.
            bpy.context.object.rotation_euler = (math.radians(45), math.radians(8),
                                                 math.radians(25))
        if not bpy.context.scene.world:
            bpy.context.scene.world = bpy.data.worlds.new("B3D_W")
            bpy.context.scene.world.use_nodes = True
        bpy.context.scene.render.engine = 'BLENDER_EEVEE'
        bpy.context.scene.render.resolution_x = bpy.context.scene.render.resolution_y = 512
        bpy.context.scene.view_settings.view_transform = 'Standard'
        fp = os.path.join(args["preview_dir"], args["stem"] + "_미리보기.png")
        bpy.context.scene.render.filepath = fp
        bpy.ops.render.render(write_still=True)
        out["preview"] = fp

elif action == "unity_export":
    # 유니티 안전 익스포트 — 텍스처가 유니티에서 사라져 '갈색 덩어리'로 뜨는 문제를 뿌리째 막습니다.
    #   ① 텍스처 이름을 ASCII로(한글·공백은 유니티 임포트 경로를 깨뜨려 텍스처가 통째로 사라짐)
    #   ② 리소스를 pack(원본 파일 없어도 픽셀을 품고 감)
    #   ③ (선택) 투명 데칼을 색 위에 '구워' 불투명화 — 유니티에서 Transparent 설정을 안 해도 로고가 보임
    #   ④ FBX에 텍스처를 박아(embed) 내보냄 → 파일 하나만 넘기면 끝
    #   ⑤ 내보낸 FBX를 **빈 씬에 다시 불러 검증**(이름이 ASCII인지·픽셀이 박혔는지 실측)
    # 원본 .blend는 저장하지 않습니다(메모리에서만 고치고 FBX만 내보냄) — 원본 보존.
    import re as _re
    import numpy as np

    scene = bpy.context.scene
    dest = args["dest"]
    folder = os.path.dirname(dest)

    _IMG_EXTS = (".png", ".jpg", ".jpeg", ".tga", ".bmp", ".tif", ".tiff")

    def _ascii_tex_name(name):
        name = _re.sub(r"\.\d{3}$", "", name)           # 블렌더 중복표시(.001/.002) 제거
        base, ext = os.path.splitext(name)
        if ext.lower() not in _IMG_EXTS:                # .002 등이 확장자로 오인되면 png로
            base, ext = name, ".png"
        base = _re.sub(r"[^A-Za-z0-9_-]", "_", base)    # 한글·공백·중간점 등 → _
        base = _re.sub(r"_+", "_", base).strip("._-") or "tex"
        return base + ext

    # 실제로 쓰이는 텍스처만 대상
    used = []
    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue
        for n in mat.node_tree.nodes:
            if n.type == "TEX_IMAGE" and n.image and n.image not in used:
                used.append(n.image)

    # ① 먼저 pack — 이래야 이름을 바꿔도 픽셀이 메모리에 남아 embed 됩니다(reload 불필요).
    #    백그라운드에선 이미지가 지연 로딩이라 has_data가 못 믿을 값 → pack 뒤에 판정해야 정확합니다.
    try:
        bpy.ops.file.pack_all()
    except Exception:
        pass
    # 파일이 진짜 없는(깨진 링크) 텍스처만 골라냅니다 — pack 뒤에도 안 담긴 것.
    missing = [img.name for img in used if not img.packed_file]

    # ② 텍스처 이름·경로를 ASCII로
    renamed = []
    for img in used:
        if img.name in missing:
            continue
        newn = _ascii_tex_name(img.name)
        img.name = newn                      # 충돌 시 블렌더가 .001을 붙여도 전부 ASCII라 안전
        img.filepath = "//" + img.name
        renamed.append(img.name)

    # ③ (선택) 투명 데칼을 색 위에 구워 불투명화
    import tempfile, shutil
    baked = []
    alpha_left = []
    _bake_dirs = []          # 구운 png를 담아둔 임시폴더들 — FBX embed 뒤 finally에서 지움
    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue
        nt = mat.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if not bsdf:
            continue
        bc = bsdf.inputs["Base Color"]
        alpha_in = bsdf.inputs["Alpha"]
        uses_alpha = alpha_in.is_linked or mat.blend_method != "OPAQUE"
        tex = bc.links[0].from_node if bc.is_linked else None
        is_img = tex is not None and tex.type == "TEX_IMAGE" and tex.image is not None
        if not (uses_alpha and is_img):
            continue
        if not args.get("bake_decal"):
            alpha_left.append(mat.name)      # 안 구우면: 유니티에서 Transparent로 바꿔야 함(경고용)
            continue
        img = tex.image
        w, h = img.size
        if w == 0 or h == 0 or not img.has_data:
            alpha_left.append(mat.name)
            continue
        buf = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(buf)
        px = buf.reshape(h, w, 4)
        bg = args.get("bg")
        if not bg:
            bg = list(bc.default_value)[:3]  # 재질 자체의 기본 색을 배경으로(대개 본체 색과 맞음)
        bg = np.array(bg[:3], dtype=np.float32)
        a = px[:, :, 3:4]
        px[:, :, :3] = px[:, :, :3] * a + bg[None, None, :] * (1.0 - a)   # 알파 위에 색 합성
        px[:, :, 3] = 1.0                    # 완전 불투명
        nimg = bpy.data.images.new(os.path.splitext(img.name)[0] + "_baked.png", w, h, alpha=False)
        nimg.pixels.foreach_set(px.reshape(-1))
        # 구운 텍스처는 FBX에 박히므로 디스크엔 남길 필요가 없습니다 → OS 임시폴더에만 씀(사용자 폴더 깨끗).
        _bake_tmp = tempfile.mkdtemp(prefix="b3d_bake_")
        _bake_dirs.append(_bake_tmp)
        nimg.filepath_raw = os.path.join(_bake_tmp, _ascii_tex_name(nimg.name))
        nimg.file_format = "PNG"
        nimg.save()                          # embed가 이 파일을 담음
        tex.image = nimg
        for l in list(nt.links):             # 알파 연결 끊고 불투명으로
            if l.to_socket is alpha_in:
                nt.links.remove(l)
        alpha_in.default_value = 1.0
        mat.blend_method = "OPAQUE"
        baked.append(mat.name)

    # ④ FBX에 텍스처를 박아 내보냄 (embed가 임시 png를 담고 나면 그 폴더는 반드시 지움)
    for o in scene.objects:
        o.select_set(o.type in ("MESH", "ARMATURE")
                     or (o.type == "EMPTY" and not o.name.startswith("B3D_")))
    try:
        bpy.ops.export_scene.fbx(
            filepath=dest, use_selection=True, add_leaf_bones=False,
            path_mode="COPY", embed_textures=True,
            apply_scale_options="FBX_SCALE_ALL", mesh_smooth_type="FACE")
    finally:
        for _d in _bake_dirs:
            shutil.rmtree(_d, ignore_errors=True)

    # ⑤ 검증 — 내보낸 FBX를 빈 씬에 다시 불러 텍스처가 ASCII 이름으로 박혔는지 실측
    verify = {}
    try:
        bpy.ops.wm.read_homefile(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=dest)
        imgs = [im for im in bpy.data.images if (im.packed_file or im.source == "FILE") and im.name != "Render Result"]
        verify = {
            "images": [{"name": im.name, "packed": im.packed_file is not None,
                        "size": list(im.size)} for im in imgs],
            "all_ascii": all(im.name.isascii() for im in imgs),
            "all_packed": all(im.packed_file is not None for im in imgs) if imgs else False,
            "count": len(imgs),
        }
    except Exception as e:
        verify = {"error": str(e)}

    out.update({
        "dest": dest,
        "renamed_textures": renamed,
        "baked_materials": baked,
        "alpha_materials": alpha_left,       # 안 구운 투명 재질(유니티에서 Transparent 필요)
        "missing_images": missing,
        "verify": verify,
    })

print("B3D_RESULT " + json.dumps(out, ensure_ascii=False))
