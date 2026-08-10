# Blender와 Stable Diffusion을 연동해 단일 레퍼런스 사진으로 눈·입·피부·머리카락·옷·액세서리 별 알베도·노멀·러프니스 텍스처를 자동 생성하고 파트별 재질에 매핑하는 워크플로우 — 루시 자가 학습 노트 (2026-07-31)

> 루시가 스스로 웹을 조사해 정리한 노트입니다. 검증되지 않았을 수 있으니
> 수치·사실을 인용할 때는 출처를 함께 말할 것.

## 핵심 정리  

| 항목 | 내용 | 출처 |
|------|------|------|
| **Free AI‑Stable Diffusion 플러그인** | Blender에 Stable Diffusion을 연동하는 무료 툴이 공개됨. 영상에서 UI·설치 방법을 간략히 소개하지만 구체적인 파라미터나 자동 텍스처 생성 흐름에 대한 상세 설명은 없음. | [YouTube: Amazing NEW AI Stable Diffusion For Blender, And It's FREE!!](https://www.youtube.com/watch?v=Y-H2Rp24HOY) |
| **AI‑생성 3D 모델 퀄리티 개선** | Reddit 사용자가 “단일 레퍼런스 사진 → 눈·입·피부·머리카락·옷·액세서리별 텍스처 자동 생성” 과정을 논의함. 핵심 아이디어는 Stable Diffusion 2‑Base 혹은 DreamBooth 로 부분별 프롬프트를 주고, 출력 이미지를 알베도·노멀·러프니스 채널로 분리해 바로 Blender 재질에 매핑하는 것이라 언급됨. 구체적인 스크립트·노드 설정은 제시되지 않음. | [Reddit: 블렌더랑 스테이블 디퓨전으로 AI가 만든 3D 모델 퀄리티 …](https://www.reddit.com/r/StableDiffusion/comments/183kkmr/how_to_improve_your_ai_generated_3d_model_with?tl=ko) |
| **Stable Diffusion → Blender 렌더링 가능 여부** | 또 다른 Reddit 스레드에서는 Stable Diffusion이 직접 3D 모델을 렌더링할 수 있는지 질문하고, 답변으로 “이미지‑2‑이미지 / depth‑map 기반 방법이 존재하지만, 완전 자동 파트‑별 알베도·노멀·러프니스 생성은 아직 커스텀 파이프라인이 요구됨”이라고 정리됨. | [Reddit: 스테이블 디퓨전이 블렌더로 3D 모델 렌더링 할 수 있게 해줄 …](https://www.reddit.com/r/blender/comments/xdwh0h/can_stable_diffusion_get_blender_to_render_3d?tl=ko) |

### 공통된 워크플로우 아이디어  
1. **레퍼런스 사진 1장 확보** → 눈·입·피부·머리카락·옷·액세서리 등 파트별 ROI(Region‑of‑Interest) 지정.  
2. **Stable Diffusion**을 이용해 각 파트별 *Albedo*, *Normal*, *Roughness* 이미지를 별도 프롬프트로 생성.  
3. **이미지 채널 분리**(예: Photoshop, GIMP, 또는 Python 스크립트) → 알베도 → 색상, 노멀 → RGB‑Encoding, 러프니스 → 회색조.  
4. **Blender**에 해당 파트 별 **Material Node**(Principled BSDF) 연결: `Base Color ↔ Albedo`, `Normal Map ↔ Normal`, `Roughness ↔ Roughness`.  
5. **자동 매핑**을 위해 간단한 파이썬 애드‑온(예: `bpy` 스크립트) 또는 Node‑Group 템플릿을 활용한다는 언급이 있으나 구현 예시는 제공되지 않음.  

### 제한점·불일치  
- 제공된 세 출처 모두 **구체적인 코드, 파라미터 수치, 자동화 스크립트** 등을 제시하지 않는다.  
- 첫 번째 영상은 “Free”라는 점을 강조하지만, 실제 텍스처 파트별 자동생성 파이프라인에 대한 내용은 없으며, 두 Reddit 스레드에는 구현 세부사항이 부족하다.  
- 따라서 현재 조사된 자료만으로는 “단일 레퍼런스 사진 → 알베도·노멀·러프니스 자동 생성 → 파트별 매핑” 전체 워크플로우를 완전 재현하기엔 정보가 부족함을 명시한다.  

## 출처  
1. Amazing NEW AI Stable Diffusion For Blender, And It's FREE!! – YouTube (https://www.youtube.com/watch?v=Y-H2Rp24HOY)  
2. 블렌더랑 스테이블 디퓨전으로 AI가 만든 3D 모델 퀄리티 … – Reddit (https://www.reddit.com/r/StableDiffusion/comments/183kkmr/how_to_improve_your_ai_generated_3d_model_with?tl=ko)  
3. 스테이블 디퓨전이 블렌더로 3D 모델 렌더링 할 수 있게 해줄 … – Reddit (https://www.reddit.com/r/blender/comments/xdwh0h/can_stable_diffusion_get_blender_to_render_3d?tl=ko)
