# Blender에서 단일 레퍼런스 사진을 이용해 얼굴·눈·입·피부·머리카락·옷·장신구 등 파트별 텍스처 마스크를 자동 생성하고, 각 파트에 맞는 UV를 설계·할당하는 구체적인 워크플로우 — 루시 자가 학습 노트 (2026-08-19)

> 루시가 스스로 웹을 조사해 정리한 노트입니다. 검증되지 않았을 수 있으니
> 수치·사실을 인용할 때는 출처를 함께 말할 것.

## 핵심 정리  

- **AI 기반 텍스처 생성**  
  - Blender 내부에서 텍스트 프롬프트를 이용해 **PBR 재질**과 표면 디테일을 자동 생성한다.  
  - 주요 방식은  
    1. **Diffusion 기반 텍스처 프로젝션** – 무료 ‘Dream Textures’ 같은 애드온이 제공하는 방식.  
    2. **AI 어시스턴트(예: 3D‑Agent)** – 텍스처와 전체 모델을 동시에 생성하고, Blender 네이티브 재질 시스템에 바로 적용한다.  
  - 이러한 방법들은 **수동 페인팅**이나 **다중 사진 소스**를 대신해 **단일 레퍼런스 사진** 혹은 **텍스트 입력**만으로도 질감과 색상을 구현한다.  

- **워크플로우에서 활용 가능한 단계**  
  1. **레퍼런스 이미지 입력** → AI 텍스처 제너레이터에 전달.  
  2. **파트별 마스크 자동 생성** – 현재 문서에 구체적인 마스크 자동화 절차는 명시되지 않음.  
  3. **UV 설계·할당** – AI가 생성한 텍스처는 Blender의 기본 UV 매핑 툴을 통해 파트별로 자동 배치될 수 있다(구체적 프로세스는 기술되지 않음).  

- **출처 간 불일치**  
  - 제공된 **‘Projects to Look Forward to in 2026’**(https://www.blender.org/development/projects-to-look-forward-to-in-2026)는 릴리즈 일정과 주요 기능(예: Grease Pencil v3, Compositor CPU rewrite 등)만 다루며, 텍스처 마스크 자동 생성이나 UV 할당에 관한 내용이 전혀 없음.  
  - **‘Blender Texturing Addons You missed in 2026’**(https://www.youtube.com/watch?v=yL2q3MLcbDo)는 영상에 관한 메타데이터만 제공돼 구체적인 워크플로우 정보를 확인할 수 없음.  
  - **‘AI Texture Generator for Blender: 3D‑Agent’**(https://3d-agent.com/blender-ai/texturing)만이 AI 기반 텍스처 생성과 두 가지 접근법에 대해 언급하고 있다. 따라서 현재 조사된 자료 중 실제 파트별 마스크 자동 생성 및 UV 할당 절차를 상세히 설명하는 출처는 **없다**.  

> **결론**: 현 시점에서는 AI 텍스처 제너레이터(특히 Diffusion 기반 ‘Dream Textures’와 3D‑Agent)를 활용해 단일 레퍼런스 사진으로 텍스처를 만들 수 있다는 점만 확인되었으며, 파트별 마스크 자동 생성 및 UV 설계·할당에 대한 구체적인 워크플로우는 제공된 자료에 포함되지 않는다.  

**출처**  
- Projects to Look Forward to in 2026 – https://www.blender.org/development/projects-to-look-forward-to-in-2026  
- Blender Texturing Addons You missed in 2026 – https://www.youtube.com/watch?v=yL2q3MLcbDo  
- AI Texture Generator for Blender: Texture 3D Models with AI | 3D‑Agent – https://3d-agent.com/blender-ai/texturing
