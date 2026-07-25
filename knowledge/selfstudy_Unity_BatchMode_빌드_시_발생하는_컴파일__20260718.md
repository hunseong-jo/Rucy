# Unity BatchMode 빌드 시 발생하는 컴파일 에러 분석 — 루시 자가 학습 노트 (2026-07-18)

> 루시가 스스로 웹을 조사해 정리한 노트입니다. 검증되지 않았을 수 있으니
> 수치·사실을 인용할 때는 출처를 함께 말할 것.

## Unity BatchMode 빌드 컴파일 에러 분석 노트

### 1. 빌드 오류 로그 분석 방법
*   **로그 확인**: UBA(Unity Build Automation) 오류 해결의 첫 단계입니다.
*   **로그 색상 구분**: 오류는 빨간색, 경고는 노란색으로 강조 표시됩니다.
*   **컴팩트 로그 vs 전체 로그**: 컴팩트 로그 탭은 경고와 오류를 쉽게 찾아주지만, 모든 오류가 기록되는 것은 아니므로 전체 로그를 확인하는 것이 유용합니다.
*   **로그 비교**: 오류 로그가 여러 개이고 이전 빌드가 성공한 경우, 성공한 로그와 비교하여 차이점을 파악합니다.

### 2. 배치 모드 및 명령줄 인자 설정
*   **기본 인자**: `-batchMode`, `-quit`, `-executeMethod`, `-logFile` 등이 사용됩니다.
*   **CI 환경 설정 (Jenkins 등)**: CI 툴을 통해 커맨드 라인으로 활성화할 때 macOS 터미널 사용 시 `-nographics` 플래그를 추가하여 WindowServer 오류를 방지해야 합니다.

### 3. 주요 발생 문제 및 에러 유형
*   **일반적인 문제**:
    *   빌드 즉시 실패 (프로젝트 오류를 인식하지 못하는 경우).
    *   Git 하위 모듈 사용 시 클론 지연.
    *   라이트맵 베이킹(Lightmap Baking) 관련 이슈.
    *   안드로이드 빌드 오류, iOS 공증(Notarization) 오류, Xcode 마이그레이션 오류 등 플랫폼별 이슈.
*   **컴파일 에러 특이 사례**:
    *   에디터에서는 잘 되지만 빌드 시 `using` 구문에서 컴파일 에러가 발생하는 경우 (예: `The type or namespace name 'PackageManager' does not exist`).

### 출처
*   [Unity Docs] Build Automation 오류 문제 해결: https://docs.unity.com/ko-kr/build-automation/check-build-results/troubleshoot-build-failures/overview
*   [Unity 매뉴얼] 커맨드 라인 인자: https://docs.unity3d.com/kr/2018.4/Manual/CommandLineArguments.html
*   [Tistory] [Unity 이슈] Editor에서는 잘 되지만 Build가 안되는 이슈: https://gus6615.tistory.com/140
