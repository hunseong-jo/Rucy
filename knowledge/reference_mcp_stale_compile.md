---
name: reference-mcp-stale-compile
description: Unity MCP assets-refresh가 스크립트 재컴파일을 놓쳐 옛 코드로 플레이되는 함정과 해결법.
metadata: 
  node_type: memory
  type: reference
  originSessionId: 39efb0cf-0d84-4dea-9266-d10f0337cb60
---

# MCP `assets-refresh`는 재컴파일을 놓칠 수 있다 (스테일 컴파일 함정)

Edit 도구로 .cs 수정 → `mcp__ai-game-developer__assets-refresh` 호출해도 **재컴파일이 안 되거나 부분만 반영**될 수 있음. 실제 사례(2026-07-01 세션17): HatcheryManager에 필드 추가(1차 편집)는 반영됐는데 같은 파일의 메서드 추가(2차 편집)는 반영 안 됨 → 플레이모드가 **메서드 없는 옛 어셈블리로 실행**돼 온보딩이 안 뜸. `console-get-logs`엔 CS에러 0건이라 겉으론 정상처럼 보임.

## 증상
- 코드상 분명히 있는 메서드가 런타임에 `Type.GetMethod(name, NonPublic|Instance)` == null.
- 새 기능(팝업 등)이 조건 맞는데도 안 나타남. 에러 로그는 없음.

## 진단
`script-execute`로 리플렉션 체크:
`typeof(DietCreature.X).GetMethod("메서드", BindingFlags.NonPublic|BindingFlags.Instance) != null`

## 해결 (강제 재컴파일)
```csharp
UnityEditor.AssetDatabase.ImportAsset("Assets/Scripts/파일.cs", UnityEditor.ImportAssetOptions.ForceUpdate);
UnityEditor.Compilation.CompilationPipeline.RequestScriptCompilation();
```
→ 도메인 리로드 후 메서드 반영됨. **코드 편집 후엔 assets-refresh만 믿지 말고, 특히 플레이모드 검증 전에 RequestScriptCompilation으로 확실히 재컴파일할 것.**

## 플레이모드 검증 팁(세션17에서 통함)
- 진입: `EditorApplication.isPlaying=true`. 단 `Assets/Editor/PlayFromIntro.cs`가 **항상 Intro부터** 재생시킴 → 버튼 클릭 시뮬로 진행: `GameObject.Find("StartButton").GetComponent<Button>().onClick.Invoke()`.
- UI 존재 검증은 RT스크린샷(함정) 대신 `GameObject.Find`/리플렉션+`console-get-logs`로. 멈춤 없이 안전했음.
- 검증 후 `SaveSystem.Delete()`로 세이브 정리. 관련: [[reference_unity_mcp_hang]]
