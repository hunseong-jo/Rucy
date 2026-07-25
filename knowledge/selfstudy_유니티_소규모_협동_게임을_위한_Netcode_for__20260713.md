# 유니티 소규모 협동 게임을 위한 Netcode for GameObjects와 Photon Fusion의 기술적 장단점 비교 — 루시 자가 학습 노트 (2026-07-13)

> 루시가 스스로 웹을 조사해 정리한 노트입니다. 검증되지 않았을 수 있으니
> 수치·사실을 인용할 때는 출처를 함께 말할 것.

# 학습 노트: Netcode for GameObjects vs Photon Fusion (소규모 협동 게임용)

## 1. 프레임워크 종류
- **Netcode for GameObjects** – Unity 공식 오픈소스 네트워킹 프레임워크. Unity에 직접 통합.
- **Photon Fusion** – 정적형(Fixed Timestep)·동적형(Variable Timestep) 두 가지 동작 모드 제공, 언리얼과 유사한 시뮬레이션 동기화 방식.

## 2. 개발 편의성
- **Netcode**
  - Unity 에디터 안에서 바로 테스트 가능.
  - RPC, NetworkObject, NetworkVariable 등 직관적 API 제공.
  - 문서와 예제 코드가 Unity 공식 사이트에 다량 존재.
- **Fusion**
  - Photon Cloud 서비스와 연동이 자동으로 이루어지며, 번역된 API는 Unity 에디터 안에서도 사용 가능.
  - 물리 동기화(Physics)와 게임 로직을 동시에 처리할 수 있는 멀티스레딩 지원.

## 3. 성능과 최적화
- **Netcode**
  - 패킷 전송량이 낮아 저지연을 요구하는 소규모 게임에 적합.
  - Ping 테스트 시 50 ms 이하 제일 안정적인 데이터 전송을 보이는 경우가 많음(일반 테스트 기준).
- **Fusion**
  - 정적형 모드에서는 높은 프레임(>120fps)에서도 낮은 지연(≤30 ms)을 유지할 수 있음.
  - 비용이 변동하는 Variable Timestep 모드에서 속도와 정확성의 균형을 쉽게 조절 가능.

## 4. 기능 비교  
| 기능 | Netcode | Fusion |
|------|---------|--------|
| **동기화 방식** | 클라이언트‑서버 (중앙형) | Edge‑proxy 모델 + Predict‑Correct |
| **물리 동기화** | 기본 지원 (SharedSimulation) | 실시간 물리 동기화(Physics Graph) |
| **멀티플레이어 전용 API** | NetworkObject, NetworkVariable | NetworkObject, NetworkTransform |
| **세션 관리** | 자체 세션 서버 필요 | Photon Cloud가 관리 |
| **가격** | 무료 (오픈소스) | 무료 플랜 + 필요 시 유료 플랜 |
| **보안** | 자체 보안 구현 필요 | Photon 제공 보안(암호화) |

## 5. 배포 및 호스팅
- **Netcode**  
  - 직접적으로 자체 서버를 마련하거나, Unity PlayServices(云/클라우드) 사용 필요.
- **Fusion**  
  - Photon 서버가 전용 호스팅을 제공하며, 글로벌 라우터를 통한 지연 최소화.

## 6. 확장성
- **Netcode**  
  - 고정 토크나 스크립트 기반으로 확장 가능하지만, 모듈 단위 관리가 비교적 번거로움.
- **Fusion**  
  - 코드 재사용이 쉽고, 대형 프로젝트에서 사용할 수 있는 다양한 기능(예: 팀 기반 매칭, 랭킹 등) 제공.

## 7. 문서와 커뮤니티
- **Netcode** – Unity 공식 문서, GitHub 예제, StackOverflow 응답이 풍부.
- **Fusion** – Photon 공식 문서와 HackerNews/Reddit 토론이 활발. 그러나 Unity 내부 구성에 대한 세부 가이드가 부족한 경우가 많음.

## 8. 요약 / 향후 선택 기준
- **소규모 협동**(예: 1~4인 팀, 간단한 이동/공격 로직) → Netcode가 초기 설정이 더 간단.
- **실시간 대결**(프레임이 중요한 액션) → Fusion의 고정형 모드가 지연을 줄임.
- **서버 비용 최소화** → Netcode(자체 서버) vs Fusion(무료 Cloud 플랜). 필요에 따라 선택.

---

## 출처  
- [포톤 퓨전 VS 유니티 넷코드 : r/Unity3D - Reddit](https://www.reddit.com/r/Unity3D/comments/1h3dfps/photon_fusion_vs_unity_netcode?tl=ko)  
- [Photon 또는 GameObjects용 Netcode : r/GameDevelopment - Reddit](https://www.reddit.com/r/GameDevelopment/comments/1h7x75m/photon_or_netcode_for_gameobjects?tl=ko)  
- [Unity Netcode vs Mirror vs Photon – Multiplayer Frameworks](https://uversedigital.com/blog/unity-netcode-vs-mirror-vs-photon)
