# Unity 프로젝트 메타데이터를 추출해 PowerPoint 기획서에 자동으로 적용하는 스크립트와 워크플로우 설계 — 루시 자가 학습 노트 (2026-08-29)

> 루시가 스스로 웹을 조사해 정리한 노트입니다. 검증되지 않았을 수 있으니
> 수치·사실을 인용할 때는 출처를 함께 말할 것.

## 핵심 사실·방법

### 1. Unity 파이프라인 자동화 활용
- **베타 기능**인 Unity Pipeline Automation을 사용해 ‘규칙 정의 → 백그라운드 자동 처리’ 흐름을 구축할 수 있다.  
- 한 번 정의한 규칙은 **CAD 파일을 프로젝트 표준에 맞게 자동 변환·최적화·통합**해 주며, 별도 수동 개입이 필요 없다.  
- 워크플로우는 **파이프라인(자산 처리 단계) → 이벤트 기반 자동화 연결 → 작업(job) 실행** 순서로 구성된다.  
  (출처 1)

### 2. 메타데이터 추출 방법
- Reddit 사용자들은 **소스 코드 주석이나 `<summary>` 태그**에 담긴 정보를 스크립트로 읽어오는 간단한 방식을 제안한다.  
- Unity 프로젝트 내 스크립트 파일을 파싱하거나 리플렉션을 이용해 이러한 주석을 **키‑값 형태의 메타데이터**로 변환할 수 있다.  
  (출처 2)

### 3. 에셋 워크플로우와 연계
- Unity 매뉴얼에서는 **에셋 임포트 → 생성 → 빌드 → 배포 → 로드** 순서의 전형적인 워크플로우를 정의한다.  
- 파이프라인 자동화는 **임포트 단계**에서 트리거될 수 있어, 이 시점에 메타데이터(예: 파일명, 타입, 커스텀 주석)를 추출하도록 스크립트를 삽입한다.  
  (출처 3)

### 4. 스크립트·파워포인트 연동 설계 개요
| 단계 | 내용 | 구현 포인트 |
|------|------|-------------|
| **1. 파이프라인 정의** | CAD·3D 모델 등 에셋을 자동 변환하도록 규칙 설정 | Unity Pipeline Automation (베타) 사용 |
| **2. 이벤트 연결** | 에셋 임포트 완료 시 커스텀 에디터 스크립트 호출 | `AssetPostprocessor.OnPostprocessAllAssets` 활용 가능(매뉴얼에 암시) |
| **3. 메타데이터 추출** | 스크립트가 주석/`<summary>`·파일 메타 정보를 파싱 | C# 리플렉션·텍스트 파싱 |
| **4. 데이터 포맷 변환** | 추출한 메타데이터를 표 형식(예: CSV, JSON)으로 변환 | Unity 내 파일 I/O 활용 |
| **5. 파워포인트 자동 적용** | 외부 툴(예: PowerPoint Open XML)로 변환 파일을 삽입 | Unity 외부 프로세스로 실행(스크립트에서 `Process.Start` 등) |

> **주의**: 현재 제공된 자료에는 PowerPoint 자동 생성 API에 대한 직접적인 언급이 없으며, 4‑5 단계의 구현은 별도 도구 연동이 필요함을 밝힌다.

## 출처
- Unity Pipeline Automation FAQ: <https://unity.com/kr/resources/automating-3d-data-workflows-with-pipeline-automation-faqs-faq>  
- Reddit – 메타데이터 추출 관련 질문: <https://www.reddit.com/r/gamedev/comments/11iua3l/for_a_unity_project_is_there_a_simple_way_to?tl=ko>  
- Unity 매뉴얼 – 에셋 워크플로: <https://docs.unity.cn/kr/2021.3/Manual/AssetWorkflow.html>
