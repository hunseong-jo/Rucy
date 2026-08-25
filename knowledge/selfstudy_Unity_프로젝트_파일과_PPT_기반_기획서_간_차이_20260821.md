# Unity 프로젝트 파일과 PPT 기반 기획서 간 차이점 자동 추출 및 동기화 워크플로우 설계 — 루시 자가 학습 노트 (2026-08-21)

> 루시가 스스로 웹을 조사해 정리한 노트입니다. 검증되지 않았을 수 있으니
> 수치·사실을 인용할 때는 출처를 함께 말할 것.

## 핵심 내용 요약  

### Unity 파이프라인 자동화(UPA)  
- **목적**: 실시간 3D 제작·라이브 작업에 필요한 연산 집약적 파이프라인을 클라우드에서 자동화·조정(출처 3)  
- **핵심 기능**  
  - Unity 서비스와 타사 도구를 하나의 클라우드 기반 파이프라인에 연결 가능  
  - 커스텀 매개 변수화 워크플로 설계 지원  
  - 무거운 처리 작업을 클라우드로 이관해 로컬 하드웨어 부담 감소 및 개발·릴리스 주기 가속화(출처 3)  
- **주요 사용 사례**  
  - CAD 데이터 전환  
  - 자동화된 에셋 처리·검증  
  - 알림·통합 파이프라인 구축(출처 3)  

### Unity 파이프라인 자동화 FAQ  
- Unity Cloud 서비스가 제공하는 자동화 툴을 통해 대용량 3D 데이터 워크플로를 **자동화**할 수 있음(출처 1)  

### Git‑Unity 워크플로우 팁 (Reddit)  
- **버전 관리**: Unity 프로젝트 전체를 Git 레포지토리로 관리·커밋 시 메타데이터(.meta) 파일을 반드시 포함(출처 2)  
- **충돌 방지**: 씬 파일·프리팹은 텍스트(Force Text) 포맷으로 변환해 병합 충돌 최소화(출처 2)  
- **CI/CD**: Unity Cloud Build와 연계해 커밋 → 자동 빌드 → 테스트·배포 파이프라인 구축 가능(출처 2)  

### PPT 기반 기획서와의 차이점 자동 추출·동기화  
- 제공된 자료(출처 1‑3)에는 **PPT와 Unity 프로젝트 파일 간 차이점 자동 추출 또는 동기화**에 관한 구체적인 내용이 **없음**.  

## 적용 방안 (자료 기반)  
1. **UPA 활용**: 에셋 변환·검증 파이프라인을 자동화하여 Unity 프로젝트 최신 상태 유지(출처 3).  
2. **Git 연동**: 프로젝트 파일 변경을 버전 관리하고, CI 파이프라인에서 자동 빌드·테스트 수행(출처 2).  
3. **추가 도구 필요**: PPT와 Unity 간 차이점 추출·동기화를 구현하려면 별도 스크립트·플러그인(예: PowerPoint API와 Unity Editor 스크립트) 개발이 필요하나, 이는 현재 자료에 포함되지 않음.  

## 출처  
- Unity 파이프라인 자동화를 사용하여 3D 데이터 워크플로우 자동화 FAQ: https://unity.com/kr/resources/automating-3d-data-workflows-with-pipeline-automation-faqs-faq  
- Reddit – “What are your tips for a good workflow when using Git & Unity?”: https://www.reddit.com/r/Unity3D/comments/154tx2x/what_are_your_tips_for_a_good_workflow_when?tl=ko  
- Unity 파이프라인 자동화란 무엇인가요? (Unity Square): https://unitysquare.co.kr/growwith/unityblog/webinarView?id=777
