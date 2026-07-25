---
name: reference-conhost-crash
description: 작업 중 터미널이 갑자기 튕기는 원인 - conhost.exe 스택 버퍼 오버런(Unity 아님). Windows Terminal로 해결.
metadata: 
  node_type: memory
  type: reference
  originSessionId: a33d7518-1d1e-4ca5-b00a-29c5f2f202c0
---

## 작업 중 터미널 튕김 = conhost.exe 크래시 (Unity 아님)

증상: Claude Code 작업 도중 터미널 창이 통째로 사라지고, "conhost.exe - 시스템 오류: 시스템이 이 응용 프로그램에서 스택 기반의 버퍼 오버런을 검색했습니다" 오류창이 뜸. (2026-07-01 세션15 재발 확인)

**원인**: Unity나 프로젝트 코드 문제가 아니라 **Windows 콘솔 호스트(conhost.exe)** 버그. Claude Code가 컬러/diff를 빠르게 대량 출력할 때 구버전 conhost가 렌더링 버퍼를 못 버티고 죽음. **파일은 디스크에 저장돼 있으니 작업물 손실은 거의 없음**(다음 세션에서 파일·메모리 확인하면 마지막 단계까지 남아있는 경우 많음).

**해결**: 
- **Windows Terminal 설치(Microsoft Store) 후 그걸로 실행** = 구형 conhost 대체, 이 크래시 안 남 (가장 확실).
- 또는 Windows 업데이트로 conhost 최신화.

**복구 절차**: 재시작 후 (1) 작업하던 .cs 파일 해당 부분 Read로 저장여부 확인, (2) Editor.log에서 `error CS` 검색해 컴파일 상태 확인, (3) MEMORY.md 인덱스로 메모리 저장여부 확인. [[reference-unity-mcp-hang]]과는 다른 이슈(그건 MCP 연결폭주로 에디터가 멈추는 것).
