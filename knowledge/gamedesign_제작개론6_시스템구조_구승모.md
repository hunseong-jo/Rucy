# 게임제작개론 : #6 게임 시스템 구조에 대한 이해

저자: Seungmo Koo · 슬라이드 28장
출처: https://www.slideshare.net/slideshow/6-20903192/20903192
(공개 자료의 개인 학습용 사본. 인용할 때는 저자와 출처를 밝힐 것.)

### p1
게임 제작 개론 #6
게임 시스템 구조
NHN NEXT
구승모

### p2
Agenda
• 게임 시스템의 구조
– Single Game
– Multiplayer Game
– Case-study
• 결정형 및 비결정형 게임

### p3
학습 목표
• 기본적인 게임 시스템 구조에 대해 이해하고 게임의
구조적 특징이 콘텐츠에 어떤 영향을 주는지 설명 할 수
있다
• 결정형/비결정형 게임의 차이를 알고 어떤 게임이
각각에 해당하는지 실제 예를 들 수 있다

### p5
게임의 처리 과정
• 일반적인 게임의 처리 루프
– 싱글 플레이어 게임
– 그럼, 멀티 플레이어 게임은?
Inputs
Simulate
Render
Wait
States
events
timer
State State State
Time

### p6
멀티 플레이어 게임
• Input이 네트워크 상의 다른 컴퓨터로부터 올 수 있음
• 게임 로직 처리 및 상태 관리를 다른 컴퓨터에서 함
• 구조에 따른 분류
– P2P, Client-Server, Web-based, Hybrid
Inputs
Simulate
Render
Wait
States
my events
other hosts
over the network

### p8
Peer to Peer
• P2P 구조
– 클라이언트간 상호 직접 연결
– 빠른 반응성 및 저렴한 유지 비용이 장점
– 확장성 및 해킹(Cheating)에 취약
– FPS 및 RTS 장르에 적합
Peer Peer
Peer Peer

### p9
P2P 방식의 처리 구조
• 게임 입력(event) 교환을 통해 각자 게임 로직 처리
Inputs
Simulate
Render
Wait
States
peer
events
Inputs
Simulate
Render
Wait
States
Compare Compare
exchange

### p10
P2P 방식의 동기화 구조
• 주기적으로 이벤트 모아서 교환
– (예) 1초에 20번 업데이트  50ms 간격의 Round
– 입력이 없더라도 Beacon신호는 Round 단위로 교환
• 상대 Peer로부터 해당 라운드의 이벤트를 모아 각자처리
– 각각의 클라이언트는 모두 아래와 같은 형태의 Queue를 유지
events eventsevents나
상대1
상대2
Round
0 ms 50 100 150
Round Round Round
events
events events
모든 Peer들의
입력이 모이면
해당 Round를
처리(Simulate)
하고 렌더링
특정 Peer의 정
보가 제시간에
도달하지 않으
면 Lag현상
??
events

### p11
월드 오브 워크래프트는?

### p12
Client-Server
• CS 구조
– 클라이언트는 서버를 통한 간접 연결
– 중요 로직은 서버에서 처리함으로써 해킹으로부터 비교적 안전
– NPC를 서버가 능동적으로 활용(drive)할 수 있음
– 구현 및 유지 보수 비용이 비교적 높음
– MMOG 장르에 적합
Client Client
Client Client
Server

### p13
Client-Server 방식의 처리 구조
• 서버가 게임 로직 처리(Simulate) 및 상태 관리
Simulate
States
Inputs
Render
Wait
eventsServer
state info

### p14
Client-Server 방식의 동기화 구조
• 모든 이벤트는 서버에 처리
– 클라이언트에서 발생하는 입력은 서버에 보냄
– 서버에서 모두 모아 계산한 후 해당 클라이언트로 방송
– 네트워크 트래픽이 서버에 집중되는 구조
– NPC가 생성하는 이벤트도 해당 영역내의 클라이언트에게 방송
Server
Client A
Client B
NPC
NPC
NPC
A
B
A
A
B
B
Event A
Event BNPC Event

### p16
Web-Based
• 웹 서비스 방식 (REST)
– HTTPS를 이용한 보안성 확보가 쉬움
– 연결 유지가 필요 없어 접속이 불안정한 환경에서 유리
– 모바일 게임 및 소셜 게임 장르에 적합
– 부하 분산(웹서버 추가)이 용이하여 확장성이 높음
• L4/L7 스위치를 통한 Load-Balancing이 가능
Client
LB Web Server
Browser
Web Server
Client
Browser
Web ServerHTTP

### p17
Web-Based 방식의 처리 방식
• Request/Response 구조
– 웹의 특징을 그대로 물려 받음
• Atomic, Stateless
– 플레이어간 순서 보장이 필요할 경우
• 사과를 친구가 먼저 수확한 경우 어떻게 처리?
• 주로 Back-end (주로 캐시서버나 DB)에서 동기화
– 수동적: Server-initiated Action 어려움
• 몬스터의 선공과 같은 능동적 NPC 행동 불가
Web Client
Web Server
State State State
Response
Request

### p18
정리하면
• 만들고자 하는 게임 콘텐츠의 특성에 따라 구조 결정
– Scalability: 많은 수의 유저를 처리함에 유연한가?
– Responsiveness: 상대와의 작용-반작용이 빠르게 처리 되는가?
– NPC-Activeness: NPC 활용이 얼마나 적극적인가?
– Security: 해킹으로 부터 얼마나 안전한가?
– Robustness: 불안정한 접속 및 끊김으로 부터 복구가 쉬운가?
– Simplicity: 구현 및 유지 보수 비용이 싼가?
기준 Client-Server P2P Web-based
Scalability SOSO BAD GOOD
Responsiveness SOSO GOOD BAD
NPC-Activeness GOOD SOSO BAD
Security GOOD BAD GOOD
Robustness SOSO BAD GOOD
Simplicity BAD GOOD GOOD

### p19
Case Study
• LOL
• TERA
• Diablo 2
• Diablo 3
• 사이퍼즈
• 서든어택
• 피파온라인
• 애니팡
• 마비노기 영웅전
• … …

### p20
결정형 게임과 비결정형 게임
(Deterministic vs Non-deterministic)

### p21
결정형 게임
• 다음의 공통점은?
– 스타크래프트 리플레이
• 같은 경기를 녹화한 동영상보다 용량이 훨씬 작다
– LOL의 경기 참관하기 기능
• 5분 늦은 시점을 보여준다
– 스타크래프트 2 군단의 심장
• 리플레이 재생 중 특정 시점부터 이어하기 기능은?
• Discussion
– 위의 기능들에 대한 동작 원리는?
• 5분 구상하고 발표
• 어떻게 했을까?

### p22
결정형 게임의 구현 원리
• 이벤트의 집합으로 동일한 시뮬레이션이 가능
– 동일한 환경을 만들어주면 항상 같은 결과값이 나오도록 설계
• 랜덤으로 결정되는 것이 없음
– (참고) deterministic physics
• AI의 경우도 입력(플레이어의 특정 액션 등)에 따라 결정되는 구조
– (예) 플레이어에게 데미지를 100~150 사이 받으면 대상에게 분노하기
– (예) 프레임 단위 이벤트 동기화
Frame 1 2 3 4 5 6 7 8 …
PC 1     P#2 ↙ …
PC 2 P#1 P#2   …
PC 3  ↗ K#2 ↓ K#1 …
… … … … … … … … … …
NPC 1 IDLE ATK#7 - - DEF#1 - FWD - …
NPC 2 IDLE FWD - DEF#3 - ATK#4 - BACK …
… … … … … … … … … …

### p23
비결정형 게임
• 랜덤의 요소가 존재한다면?
– (예) 스타크래프트의 해병 라이플 데미지가 6~10 랜덤일 경우
• 피격대상의 히드라 HP가 8 남은 상태라면?
• 어떤 경우에는 히드라가 살고, 어떤 경우에는 죽게 됨
• 결정형 게임이 더 이상 아님
• 비 결정형 게임
– 똑같은 환경이 주어지더라도 다른 결과가 나옴
– 랜덤의 요소가 존재하여 똑같이 재현이 불가능
– (예) 테라, 와우, 아이온 등의 MMORPG

### p24
난수의 생성원리 소개
• 컴퓨터가 정말 무작위 숫자를 생성할 수 있을까?
– 특정 입력에 대해 서로 다른 결과를 생성할 수 있다면 가능
– 우리가 쓰는 컴퓨터는? deterministic machine
• Pseudo-Random Number
– 어떤 초기값(SEED)를 이용하여 이미 만들어진 메커니즘을 통하
여 생성되는 수로 무작위처럼 보이는 가짜 난수
– (예) middle-square, multiply-with-carry

### p25
좋은 난수 생성기?
• 온라인 포커 게임을 만든다고 했을 때
– 패 섞을(shuffle) 때 무작위 난수 생성을 이용하게 됨
– 만일, 난수 생성 알고리즘과 SEED를 알게 된다면?
• 그래서, 예측이 어려운 난수 생성이 필요
– 정말 무작위 하게 느껴지도록 하려면
• 연속되는 난수는 독립적이어야 함
• 생성 주기가 길어야 함
• 결과적으로 고르게 분포될수록 좋음
– 특정 숫자가 압도적으로 자주 나오지 않도록 함

### p26
비결정형을 결정형으로 만들기가 가능할까?
• 초기 SEED 값을 맞추는 방법
– 플레이어 입장에서는 랜덤이 동작하는 것처럼 보일 수 있음
– 생성되는 난수가 예측되기 때문에 사실상 결정형 게임이 됨
• Discussion
– MMORPG의 경우에 왜 결정형 게임으로 만들기 어려운가?
• 랜덤의 요소가 없으면 쉽게 결정형 게임으로 만들 수 있는가?

### p27
끝
• Q & A
• 강의 주제 안에서 알고 싶은 것은 게시판에 남겨주세요
• 다음 시간 강의 내용
– 게임 제작 팀 구성과 게임의 리소스 구성

### p28
참고 자료
• 참고 링크
– REST
• https://en.wikipedia.org/wiki/Representational_state_transfer
– Can a computer generate a truly random number?
• http://engineering.mit.edu/live/news/1753-can-a-computer-
generate-a-truly-random-number
– Pseudorandom number generator
• http://en.wikipedia.org/wiki/Pseudorandom_number_generator
– How to Generate a Sequence of Unique Random Integers
• http://preshing.com/20121224/how-to-generate-a-sequence-of-
unique-random-integers
