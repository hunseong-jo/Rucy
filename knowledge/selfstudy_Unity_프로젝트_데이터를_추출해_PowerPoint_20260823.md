# Unity 프로젝트 데이터를 추출해 PowerPoint 기획서 자동 업데이트하기 (CSV/JSON → python-pptx 워크플로우) — 루시 자가 학습 노트 (2026-08-23)

> 루시가 스스로 웹을 조사해 정리한 노트입니다. 검증되지 않았을 수 있으니
> 수치·사실을 인용할 때는 출처를 함께 말할 것.

## 핵심 내용 정리

### 1. Python‑pptx 로 PowerPoint 자동화  
- `python-pptx` 라이브러리를 이용하면 슬라이드 추가·텍스트 교체·이미지 삽입 등을 스크립트로 제어할 수 있다.  
- YouTube 영상 “How To Automate PowerPoint With Python”(https://www.youtube.com/watch?v=STUNieOfv1g)에서 기본적인 API 사용법(프레젠테이션 열기 → 슬라이드 객체 접근 → `shapes.title.text = "New Text"` 등)을 시연한다.  

### 2. 외부 데이터(Excel/CSV/JSON) 연동 방법  
- Reddit 글 “PowerPoint presentation update based on Excel file”(https://www.reddit.com/r/learnpython/comments/1j0w9ha/powerpoint_presentation_update_based_on_excel_file?tl=ko)에서는  
  * `pandas.read_excel()` 혹은 `openpyxl` 으로 엑셀(또는 CSV) 데이터를 읽어 DataFrame 으로 변환  
  * `python-pptx` 로 슬라이드 내 텍스트 · 표 · 도형을 찾아 `text` 속성을 교체하거나 `Table` 객체에 `cell.text` 를 할당  
  * 반복문으로 행(row)마다 슬라이드/표를 업데이트하는 패턴을 제시한다.  

### 3. Unity 파이프라인 자동화와 데이터 출력  
- Unity 공식 FAQ “Automating 3D data workflows with pipeline automation”(https://unity.com/kr/resources/automating-3d-data-workflows-with-pipeline-automation-faqs-faq)에서는  
  * Unity 에디터에서 커스텀 파이프라인을 구성해 3D 모델, 메타데이터, 통계 등을 자동으로 추출할 수 있다고 명시  
  * 추출 포맷으로 CSV·JSON 등을 지원한다는 점을 언급한다.  

### 4. 연결 가능한 워크플로우(가능성)  
| 단계 | 도구/방법 | 비고 |
|------|-----------|------|
| 1️⃣ Unity 데이터 추출 | Unity 파이프라인 자동화 → CSV/JSON 저장 | Unity FAQ에 언급된 기능 |
| 2️⃣ 데이터 파싱 | Python `pandas.read_csv()` / `json.load()` | Reddit 예시와 동일한 데이터 로드 방식 |
| 3️⃣ PPT 업데이트 | `python-pptx` 로 슬라이드·표·텍스트 교체 | YouTube 영상에서 시연된 기본 API 활용 |

> **주의:** 조사된 세 출처는 각각 **Python‑pptx 자동화**, **Excel‑기반 PPT 업데이트**, **Unity 데이터 추출**에 대해 별도로 다루고 있으며, Unity → CSV/JSON → Python‑pptx 흐름을 직접 연결한 사례는 제시되지 않았다. 따라서 실제 구현 시 위 세 단계(데이터 추출 → 파싱 → PPT 업데이트)를 조합해 별도 스크립트를 작성해야 한다.

## 출처
- How To Automate PowerPoint With Python, YouTube. https://www.youtube.com/watch?v=STUNieOfv1g  
- 엑셀 파일 기반 파워포인트 발표 자료 업데이트, Reddit. https://www.reddit.com/r/learnpython/comments/1j0w9ha/powerpoint_presentation_update_based_on_excel_file?tl=ko  
- Unity 파이프라인 자동화를 사용하여 3D 데이터 워크플로우를 자동화하세요, Unity 공식 사이트. https://unity.com/kr/resources/automating-3d-data-workflows-with-pipeline-automation-faqs-faq
