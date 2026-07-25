# 유니티 C# 치트시트 (루시의 코드 작성 기준 — Unity 6 / 6000.x)

루시가 유니티 C#을 짜기 전에 참고하는 기준표. **API를 기억으로 지어내지 말고, 여기 없는 건
unity_context·unity_find로 실제 코드를 확인한 뒤 쓴다.** 짠 직후엔 unity_cs_check(몇 초).

## 이 PC의 프로젝트 관례 (실측)
- **saladfarm(DietCreature)**: `namespace DietCreature { }` 안에 클래스. 스크립트는 Assets/Scripts/ 평면 구조,
  파일명=클래스명. 2D 스프라이트 게임(3D 조명·그림자 안 씀). 매니저류(XxxManager)·카탈로그류(XxxCatalog)·
  팝업류(XxxPopup) 명명. 자주 쓰는 using 순서: UnityEngine → UnityEngine.UI → System.Collections.Generic.
- **입력은 신 Input System**: `using UnityEngine.InputSystem;` + `Pointer.current.press.wasPressedThisFrame` +
  `p.position.ReadValue()` (구 `Input.GetMouseButtonDown`은 이 프로젝트에서 안 씀 — 섞으면 설정에 따라 예외).
- UI 위 클릭 무시: `EventSystem.current.IsPointerOverGameObject()`.

## Unity 6에서 바뀐 것 (구버전 기억으로 쓰면 경고·에러)
- `Object.FindObjectOfType<T>()` → **폐기(Obsolete)**. 대신 `Object.FindFirstObjectByType<T>()`
  (아무거나 하나=`FindAnyObjectByType<T>()`, 전부=`FindObjectsByType<T>(FindObjectsSortMode.None)`).
- `FindObjectsOfType<T>()` → `FindObjectsByType<T>(FindObjectsSortMode.None)`.
- 텍스트는 대개 TextMeshPro(`TMPro.TMP_Text`)지만 **이 프로젝트는 UnityEngine.UI.Text도 씀** — 고칠 파일이
  뭘 쓰는지 unity_context로 먼저 확인.

## 매 프레임 비용 (unity_code_lint가 잡는 것들 — 애초에 이렇게 짠다)
- `Camera.main`·`GetComponent`·`GameObject.Find`는 **Awake/Start에서 캐시**해 필드에 둔다.
  Update 안에서는 캐시가 비었을 때만 복구(`if (_cam == null) _cam = Camera.main;` — 이 모양은 OK).
- 클릭·키 입력 뒤에만 도는 코드(`wasPressedThisFrame` 조기 반환 뒤)는 매 프레임 비용이 아니다.
- `Instantiate` 반복 생성은 풀링 검토. 빈 `Update()`는 지운다(호출 비용만 냄).

## 자주 쓰는 뼈대
```csharp
// MonoBehaviour 기본형 (saladfarm 관례)
using UnityEngine;

namespace DietCreature
{
    /// <summary>한 줄 요약.</summary>
    public class Foo : MonoBehaviour
    {
        [SerializeField] private float speed = 1f;   // 인스펙터 노출은 SerializeField+private
        private Camera _cam;

        private void Start() { _cam = Camera.main; }
        private void Update() { }
    }
}
```
```csharp
// 코루틴: IEnumerator + yield return new WaitForSeconds(1f); 시작은 StartCoroutine(Co());
// 씬 이동: UnityEngine.SceneManagement.SceneManager.LoadScene("Farm");
// 2D 클릭 판정: Physics2D.OverlapPoint(worldPos) → col.TryGetComponent(out Foo f)
// PlayerPrefs 저장: PlayerPrefs.SetInt/GetInt + Save() — 이 프로젝트 영속 저장 관례
```

## EditMode 테스트 (unity_new_script kind=test가 골격 생성)
- `[Test]` + NUnit `Assert`. 테스트는 Assets/Tests/ + asmdef(자동 생성됨).
- ⚠️게임 코드가 Assembly-CSharp(asmdef 없음)이라 **테스트에서 게임 클래스 직접 참조 불가** —
  순수 로직을 테스트하려면 로직을 plain 클래스로 분리하는 게 정석.

## 컴파일 에러 빠른 해석 (unity_cs_check가 주는 CS코드)
- CS0103 이름 없음(오타·using 누락) · CS0246 타입 없음(using/어셈블리) · CS1002 `;` 누락 ·
  CS1525 잘못된 토큰(괄호 짝) · CS0029 형 변환 불가 · CS0117 그 멤버 없음(**환각 신호 —
  unity_context로 실제 멤버 확인**) · CS0619/CS0618 폐기 API(위 Unity 6 절 참조).

## 루시의 작업 순서 (유니티 C#)
1. `unity_context <클래스>` — 실제 코드 모양·쓰는 곳 파악 (환각 방지)
2. 새 파일이면 `unity_new_script`(골격) / 내용은 `unity_cs_write`(전체) 또는 `unity_cs_edit`(부분)
3. 저장하면 자동으로 `unity_cs_check`(몇 초) — 에러면 cs_edit로 고쳐 반복
4. 여러 파일 얽힌 변경·테스트는 마지막에 `unity_run`(배치모드, 에디터 닫고)
