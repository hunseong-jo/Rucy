---
name: project-meal-capture
description: "핵심 매커니즘 - 식사 사진 촬영→AI 분석→식단 분류 흐름. WebCamTexture+IMealAnalyzer seam, 휴리스틱 기본/Sentis 스테이징"
metadata: 
  node_type: memory
  type: project
  originSessionId: 91809464-76ea-451b-8b87-17c20a104421
---

## 식사 사진 촬영 → AI 분석 핵심 매커니즘 (2026-06-28 세션10) — [[project-diet-creature-game]] [[feature-creature-species]]

게임의 핵심 루프(식사 촬영→식습관 분석→어울리는 생명체 부화)의 **마지막 빈 칸**이었던 "사진 촬영+AI 분석"을 구현. 기존엔 MEAL 버튼이 식단 4종 수동선택 팝업(채식/육류/인스턴트/디저트)으로 대체하고 있었음.

### 사용자 결정 (세션10)
- AI 분석: 처음엔 "백엔드 프록시(안전)" 골랐다가, "무료/온디바이스 없냐" 물어봄 → 최종 **온디바이스 무료 Unity Sentis** 선택.
- 사진 입력: 모바일 카메라/갤러리 + 에디터 폴백 "둘 다".
- ⚠️ 클라이언트에 API키 직접 넣으면 추출 위험(출시 부적합) — 그래서 온디바이스/프록시 선호.

### 현실 제약 (이 세션)
- Unity MCP 미연결 → 패키지 설치·컴파일·실행 검증 못함. 학습된 음식분류 ONNX 모델도 못 만듦.
- 그래서: **공통 흐름은 새 패키지 0개로 지금 바로 동작**하게, **Sentis는 코드로 완성해 스테이징**(패키지+모델만 넣으면 켜짐). (백그라운드에 Unity 에디터가 켜져 있어 새 .cs들의 .meta는 자동생성됨 — 그래서 내가 쓴 meta 3개는 Unity것으로 덮임, MealCaptureUI.cs.meta만 내 GUID. GUID 참조 없어 무관.)

### 구조 (전부 신규, Assets/Scripts)
- **IMealAnalyzer.cs**: `DietResult{category 0~3, confidence, label, ok}` 구조체 + `IMealAnalyzer{ Analyze(Texture2D, Action<DietResult>); DisplayName }` 인터페이스 + `MealAnalyzer`(static seam): `Current` 게터가 기본 분석기 생성(DIET_SENTIS 정의시 SentisMealAnalyzer.TryCreate 우선, 아니면 Heuristic). `CategoryNames={채식,육류,인스턴트,디저트}`. **여기가 교체 지점** — 프록시 쓰려면 Current에 주입.
- **HeuristicMealAnalyzer.cs**: ⚠️플레이스홀더. 사진 색/채도(HSV) 분포로 4종 대충 추정. 사진 null이면 랜덤. 흐름 검증·데모용(정확도 낮음).
- **MealCaptureUI.cs**(MonoBehaviour, 런타임 생성 팝업): **WebCamTexture**(Unity 내장, 플러그인 0)로 라이브 프리뷰→"촬영"→"분석 중"(점 애니)→결과("오늘은 OO 식사네요! 알이 한 뼘 자랐어요")→확인/다시. 에디터 등 카메라 없으면 "임의로 기록(테스트)" 버튼 폴백. 사진은 저장 안 함(프라이버시). Popup/UIFactory/UITheme/Sfx 기존 패턴 사용. `Create(parent,font,Action<int> onConfirm)`. 카메라 권한 RequestUserAuthorization(WebCam). 방향 보정 best-effort(videoRotationAngle/verticallyMirrored). '앨범에서 선택'은 NativeGallery 플러그인 추가 후 연결 예정(미구현).
- **SentisMealAnalyzer.cs**: `FoodLabelMap`(항상 컴파일, 영문 라벨→4종 키워드 매핑) + `SentisMealAnalyzer`(`#if DIET_SENTIS`로 감쌈). ⚠️using Unity.Sentis도 #if로 파일최상단(CS1529 회피 — 처음에 클래스 뒤에 뒀다 수정). Sentis 2.x API(Worker/ModelLoader/TextureConverter.ToTensor/Tensor<float>) — 설치버전 따라 미세조정 필요할 수 있음. 모델 4클래스 직접출력이면 인덱스 그대로, 아니면 labels.txt로 매핑. 추론 실패시 휴리스틱 폴백.

### 배선 (HatcheryManager.cs)
- `OnMeal()`: 알 없으면 알선택, 가득차면 무시, **adminMode면 기존 식단선택팝업(빠른 테스트/즉시부화 유지), 평소엔 OpenMealCapture()**.
- `OpenMealCapture()`: `_mealCapture ??= MealCaptureUI.Create(transform,_font,ApplyMeal); _mealCapture.Open();`
- `ApplyMeal(int idx)`(신규, PickDiet에서 추출): growth++, EggGrowth, RecordMeal(idx), Save, UpdateGrowth. PickDiet의 비관리자 분기도 ApplyMeal 호출하도록 리팩터(동작 동일).
- 부화/종결정은 그대로: OnHatch가 EggType+DominantDietCategory()로 RandomIdByDiet. 즉 **사진 분석 결과가 RecordMeal로 식단카운트에 쌓여 부화 종에 실제 반영됨** → 핵심 루프 완성.

### ⚠️ 검증 안 됨 / 다음 할 일
- 이 세션 컴파일/플레이 검증 못함(정적검토만). 참조심볼(Popup.boxName/UIPolishSkip/UITheme.Body/Sfx.Play) 존재 확인함. 사용자가 Unity Console에서 컴파일 확인 필요.
- **지금 플레이**: 부화장 MEAL 탭 → 카메라 프리뷰(에디터=노트북웹캠) → 촬영 → 분석중 → 결과 → 확인 시 알 성장. 웹캠 없으면 "임의로 기록" 버튼.
- **Sentis 켜기(나중)**: ① Package Manager `com.unity.sentis` 추가 ② 음식분류 ONNX를 `Assets/Resources/Models/food.onnx`(+선택 labels.txt) ③ Player Settings Scripting Define에 `DIET_SENTIS`. 그러면 자동으로 Sentis 분석기 사용, 모델 없으면 휴리스틱 폴백.
- iOS는 Player Settings에 카메라 사용설명(NSCameraUsageDescription) 필요. Android 카메라 권한은 WebCamTexture가 자동 추가.
- 옛 `Assets/Scenes/MealCapture.unity`는 여전히 고아(런타임 팝업으로 대체). 삭제해도 무방.

## 후속: Sentis 실연동 + 갤러리 + UI 다듬기 (2026-06-28 세션11) — "순서대로 작업해줘"
세션10의 3가지 후속(①정확도 Sentis ②갤러리 ③UI)을 순서대로 진행. **이번엔 백그라운드 Unity 에디터가 live라 Editor.log(`~/AppData/Local/Unity/Editor/Editor.log`)로 컴파일 검증 가능했음** — 파일 변경마다 자동 reload/recompile됨. 검증법: `grep "error CS"` + Assembly-CSharp "with N defines" 카운트 변화 추적.

### ① Sentis = 실은 Inference Engine
- `com.unity.sentis@2.1.3`를 manifest에 추가했더니 **`com.unity.ai.inference@2.6.1`로 리졸브됨**(Sentis가 Inference Engine으로 리브랜드). **네임스페이스 `Unity.InferenceEngine`**(NOT Unity.Sentis). asmdef `Unity.InferenceEngine` autoReferenced:true라 Assembly-CSharp에서 asmdef 없이 사용 가능.
- 설치 패키지 소스를 직접 읽어 API 검증: `new Worker(Model,BackendType.GPUCompute)`, `worker.Schedule(Tensor)`, `worker.PeekOutput()`→Tensor, `ModelLoader.Load(ModelAsset)`, `new Tensor<float>(new TensorShape(1,3,224,224))` + `TextureConverter.ToTensor(tex,tensor,new TextureTransform().SetDimensions(w,h,c))`(구 `ToTensor(tex,w,h,c)`는 obsolete), `.ReadbackAndClone()`(Tensor<T>), `.DownloadToArray()`. SentisMealAnalyzer.cs를 이에 맞춰 수정(using도 Unity.InferenceEngine로).
- `Assets/Resources/Models/labels.txt` = ImageNet 1000 라벨(onnx model zoo synset.txt에서 synset id 떼어 가공, 네트워크로 받음). ImageNet 모델 쓰면 FoodLabelMap이 매핑.
- **`Assets/csc.rsp`에 `-define:DIET_SENTIS` 추가해 Sentis 경로 활성화**. Editor.log에서 Assembly-CSharp이 142→143 defines로 재컴파일+에러0 확인 = **Sentis 코드 실제 컴파일 성공**. 모델(`Resources/Models/food.onnx`) 없으면 TryCreate가 null→휴리스틱 폴백(동작 변화 0). **모델 파일만 넣으면 자동 온디바이스 AI**. ⚠️모델 학습/제공은 사용자 몫(난 ONNX 못 만듦). 4클래스 직접출력 모델이면 인덱스 그대로, ImageNet류면 labels.txt+FoodLabelMap.

### ② 갤러리 (NativeGallery)
- `com.yasirkula.nativegallery@1.9.3` + manifest scopedRegistry에 `com.yasirkula` 스코프 추가(openupm). asmdef autoReferenced 기본 true, `NativeGallery` 전역 네임스페이스(using 불필요).
- MealCaptureUI에 `#if DIET_NATIVEGALLERY` "앨범에서" 버튼 + `PickFromGallery()`(GetImageFromGallery(cb,title,mime)→LoadImageAtPath(path,1024,false)→분석). csc.rsp에 `-define:DIET_NATIVEGALLERY`도 추가(소스로 API/autoref 검증, 다음 리프레시에 컴파일). ⚠️실기기에서만 동작(에디터는 촬영/테스트로).

### ③ 촬영 UI 다듬기 (의존성 0, 완결)
- 프리뷰 **비율 맞춤**: PreviewFrame에 RectMask2D + Preview에 AspectRatioFitter(EnvelopeParent), SetPreviewAspect(w,h,rot)로 카메라 해상도/회전 반영(90/270시 가로세로 보정).
- **뷰파인더 코너 브래킷** 4모서리(ㄱ자, AddViewfinderCorners/MakeBar, 흰 반투명 Image+UIPolishSkip).
- **셔터 플래시**: 촬영 시 흰 화면 0.85→0 페이드(FlashRoutine, box 위 Flash Image).
- **결과 색상**: "오늘은 <color=#hex><b>식단</b></color> 식사네요!" rich text, 식단4색(CatColors, 식단픽커 색 계열).
- 무가드 코드라 143-define 컴파일(에러0)에 포함되어 검증됨.

### 상태 요약
세 작업 모두 코드+패키지+컴파일 검증 완료. 가이드 `Assets/MealAI-Setup.md`. 플레이(실제 카메라/소리/모델 추론)는 사용자 실행 검증 필요.

### 후속2: 실제 모델 번들 (2026-06-28 세션11 "이어서 계속")
- **실제 MobileNetV2 ONNX(ImageNet 1000클래스, opset7, 14MB)를 받아 `Assets/Resources/Models/food.onnx`에 넣음**(onnx model zoo media URL `media.githubusercontent.com/media/onnx/models/.../mobilenetv2-7.onnx`, curl -L로 LFS 바이너리 정상 수신). 이제 온디바이스 AI가 실제로 추론함.
- **전처리 재작성**: 기존 TextureConverter.ToTensor(정규화 없음)→`SentisMealAnalyzer.BuildInput`(CPU): GetPixels32→224x224 최근접 리사이즈+행뒤집기(아래위→ONNX 위아래)+**ImageNet 정규화(mean .485/.456/.406, std .229/.224/.225)**→`new Tensor<float>(new TensorShape(1,3,224,224), float[])`. MobileNet은 정규화 필수라 이게 핵심.
- 출력 1000 logits→argmax→labels[idx]→FoodLabelMap→4종. 비음식 클래스(plate 등)면 -1→휴리스틱 폴백.
- ⚠️**품질 한계**: ImageNet엔 한식/혼합접시 없음 → 명확한 단일음식만 잘 맞고 한식·섞인접시는 폴백 잦음. 진짜 정확도는 Food-101/커스텀 4종 모델로 food.onnx 교체 필요(전처리 정규화도 모델에 맞게). 14MB 부담되면 food.onnx 삭제=휴리스틱.
- ⚠️ **이 최신 변경(BuildInput 재작성+DIET_NATIVEGALLERY+food.onnx 임포트)은 Unity가 아직 리프레시 안 해 미반영**(Editor.log 12232줄 고정, 143 defines, food.onnx.meta 없음). 사용자가 Unity 포커스하면 onnx 임포트+재컴파일됨. API는 설치 소스로 검증함(Tensor<float>(shape,float[]) ctor 등). 이전 단계(DIET_SENTIS 143-define)는 컴파일 검증됨.

## 후속3: 테스트 검증 (2026-06-28 세션12 "테스트해줘")
- **현재 라이브 분석기 = SentisMealAnalyzer (실제 ONNX 추론), 휴리스틱은 폴백만.** ⚠️함정: `DIET_SENTIS`/`DIET_NATIVEGALLERY` define은 **ProjectSettings scriptingDefineSymbols가 아니라 `Assets/csc.rsp`에 있음**(ProjectSettings엔 `UNITY_MCP_READY`만). csc.rsp만 보고 판단할 것. 패키지 설치 확인됨: `com.unity.sentis 2.1.3`→`com.unity.ai.inference 2.6.1`(packages-lock), `food.onnx`+`.meta`(임포트됨), `labels.txt` 존재.
- **컴파일 검증**: Editor.log 전체에 `error CS` 0건, "Reloading assemblies for play mode" 도달 = 정상 컴파일+플레이 진입. Assets/Scripts발 런타임 예외 0건.
- **휴리스틱 분류 로직 검증**(코드 추적, 폴백 경로): 7색 케이스 전부 의도대로 — 초록→채식, 빨강/갈색→육류, 밝은주황→인스턴트, 분홍/밝은무채(크림)→디저트, null→랜덤. 분기 우선순위·HSV 임계값 일관.
- **파이프라인**: OnShutter→AnalyzeRoutine→Analyze→ShowResult→OnConfirm→ApplyMeal(growth++/RecordMeal/Save) 배선 정상. 에디터 무웹캠시 NoCamera→"임의로 기록(테스트)" 폴백.
- ⚠️ **라이브 플레이(실제 Sentis 추론) 검증은 MCP 미연결로 못함** — [[reference-unity-mcp-hang]] 참조. Unity 재시작이 가장 확실한 복구.

## 후속4: 실제 런타임 추론 검증 완료 (2026-06-30 세션13 "이어서 해보자")
- **MCP(ai-game-developer/com.ivanmurzak.unity.mcp) 연결됨** → 처음으로 `script-execute`로 실제 추론 런타임 검증 성공. (팁: script-execute 첫 호출이 도메인 리로드 유발하면 `Response data is null` 뜸 → console-get-logs가 `[]` 응답할 때까지 기다렸다 재실행. Editor.log로 컴파일 진행 확인 가능.)
- **패키지 실상 재확인**: manifest엔 `com.unity.sentis 2.1.3`이지만 PackageCache에서 **2.2.0 shim**(`"type":"shim"`, package.json만 있고 소스 없음)으로 리졸브 → 실제는 **`com.unity.ai.inference`(네임스페이스 `Unity.InferenceEngine`)**. shim이 ai.inference 2.2.1 의존. API 심볼 전부 설치 소스에서 재확인(Worker(Model,BackendType)/Schedule(Tensor)/PeekOutput()→Tensor/ModelLoader.Load/Tensor<float>(TensorShape,float[])/TensorShape(int,int,int,int)/DownloadToArray/ReadbackAndClone).
- **런타임 검증 결과(에러0)**: food.onnx 로드 OK(inputs=1,outputs=1) / **모델 입력 name=`data` shape=`(1,3,224,224)` — BuildInput의 NCHW와 정확 일치** / GPU추론 OK(logits.len=1000, argmax 산출) / 임의입력은 비음식라벨→FoodLabelMap=-1→휴리스틱폴백(안전망 정상) / `SentisMealAnalyzer.TryCreate`=OK / **`MealAnalyzer.Current`=온디바이스 AI(Sentis) — 휴리스틱 아닌 실제 AI 활성 확정**.
- **상태: AI 분석 매커니즘 = 코드+패키지+컴파일+런타임추론 전부 검증 완료.** 남은 건 (a)실기기/플레이모드에서 실제 음식사진으로 UI 전체 흐름 손검증, (b)정확도 개선 — ImageNet 음식클래스 ~40종뿐+서구편향이라 한식/혼합접시는 폴백 잦음 → Food-101/커스텀 4종 모델로 food.onnx 교체가 다음 정확도 작업. 코드/전처리는 손댈 것 없음.

## 후속5: 커스텀 4종 모델 학습 파이프라인 구축 (2026-06-30 세션13 이어서) — 사용자 요구="한식 포함, 무료, 출시가능, '무슨 음식'이 아니라 과자/고기/채소/디저트 4단계 큰 분류만"
- **모델 라이선스 조사 결과(중요)**: 제로샷 CLIP(MobileCLIP-S0, ~43MB, 한식 코어스분류에 기술적 베스트)는 **Apple 연구전용 라이선스→상업 출시 불가**(Xenova/plhery ONNX 변환본도 동일 제약 상속). OpenAI CLIP은 MIT지만 ~150MB+로 모바일 과대. MM-Food-100K(10만장)은 OpenRAIL-M 비상업→제외. **결론: 커스텀 4종 모델 직접 학습이 유일한 "무료+출시가능+한식+소형" 해법.** 결과 가중치는 사용자 소유라 상업 OK(모델에 원본이미지 안 들어감).
- **데이터셋**: `Kaludi/data-food-category-classification`(11카테고리 Bread/Dairy/Dessert/Egg/Fried/Meat/Noodles/Rice/Seafood/Soup/Veg-Fruit, 2970장, 카테고리단위라 4매핑 깔끔) + `food101`(101클래스 10만장, 비빔밥(idx7)+pad_thai/pho/gyoza 등 일부 아시아 포함, 볼륨/디저트 보강). 둘 다 HF `load_dataset`로 자동다운. 한식 부스트는 사용자가 AI-Hub 한식이미지를 `extra_data/{veg,meat,instant,dessert}/`에 넣으면 학습 합쳐짐(옵션).
- **산출물(신규)**: `Documents/DietCreature/ModelTraining/train_food4.py`(MobileNetV2 ImageNet사전학습+4종헤드 전이학습→ONNX export, 입력 `data`(1,3,224,224) ImageNet정규화=BuildInput과 100%일치, 출력 `logits`(1,4) 원시로짓, opset13, onnxruntime 검증포함, 클래스가중치로 불균형보정, MAX_PER_SOURCE/USE_FOOD101 등 설정) + `ModelTraining/README.md`(Colab GPU 절차+한식 extra_data+적용법+라이선스). FOOD101_MAP/KALUDI_MAP 딕셔너리로 음식→4바구니 매핑(혼합음식은 가장 인상적 1바구니, 사용자 수정가능).
- **코드 보강**: `SentisMealAnalyzer.Analyze` 분기를 `if (logits.Length <= 4 || _labels==null || _labels.Length<logits.Length)` 로 변경 — **출력 4개 이하면 옛 labels.txt(1000줄)가 남아있어도 인덱스를 그대로 0~3으로 써서** 4종 모델 드롭인이 항상 안전. 에러0 컴파일 확인(assets-refresh+console).
- **적용 절차(사용자 몫)**: Colab서 train_food4.py 실행→food.onnx 받기→`Assets/Resources/Models/food.onnx` 덮어쓰기+`labels.txt`(+.meta) 삭제→Unity포커스 재임포트. val_acc 0.85+면 코어스분류로 충분. **현재 food.onnx는 아직 ImageNet MobileNetV2(세션11)** — 사용자가 커스텀 모델 학습/교체하면 한식 인식 개선됨.

## 후속6: '중립(균형 식사)' 밴드 도입 + 분류 철학 결정 (2026-07-02 세션21)
- 사용자 테스트: **떡볶이→채식** 오분류 발견. 진단: KFOOD_MAP엔 `"tteokbokki":2`(인스턴트) 정상 → 매핑버그 아님. **원인=학습데이터 부족**(kfood 데이터셋 떡볶이 ~13장뿐, 스튜디오풍이라 실폰사진 일반화 실패). "인스턴트" 바구니 1185장은 대부분 Kaludi 서양식. 현 배포모델=4클래스 직접출력(labels.txt 없음, argmax→분류), val_acc 0.811. **떡볶이 개선은 실사진 extra_data/instant/ 추가 후 재학습 필요**(별도 이슈, 미착수).
- **분류 철학 결정(사용자)**: 이 식단분류는 "정확한 식습관 코칭"이 아니라 **"재미있는 생명체가 나오는 양념" 포지션**. 4분류(채식/육류/인스턴트/디저트)가 서로 다른 축(주재료/가공도/코스)을 섞어 한식 밥상 같은 혼합식이 애매한 건 구조적 한계로 인정. 5번째 생명체 카테고리 추가나 축 재설계는 파장 커서 안 함.
- **채택 해법 = '중립(균형)' 밴드**(재학습 0, 생명체/날씨/시너지/도감 전부 그대로): `MealCaptureUI.ShowResult`가 top-1 신뢰도 3단 판정 — ≥MinConfidence(0.55)→특정식단 / RetryThreshold(0.35)~0.55→**중립("치우치지 않은 건강한 식단이네요!", category=-1)** / <0.35→재촬영유도. 균형잡힌 식사=모델이 한쪽으로 못 몰아 확률 납작→낮은 top-1→중립으로 자연 귀결.
- 구현: `MealCaptureUI`에 RetryThreshold=0.35f/NeutralCategory=-1 상수+ShowResult 3분기. `HatcheryManager.ApplyMeal(-1)`는 growth++만 하고 **RecordMeal이 0~3 범위밖(-1)을 무시**해 식단집계엔 0기여(코드변경 불필요, 주석만). 검증: 컴파일0에러, RecordMeal(-1) 집계무변화·RecordMeal(2) 정상+1 확인. 임계값은 상수라 실폰사진으로 튜닝 권장. ⚠️한계: 이 밴드는 '모델이 헷갈리는' 경우(밥상)만 잡음, '확신하며 틀리는' 떡볶이는 못 잡음(데이터 이슈로 남음).

## 후속7: 로컬 GPU 재학습(레시피 개선) 완료 (2026-07-02 세션21 "AI 학습 시키자")
- 사용자 결정: 기존 데이터(새 사진 X)로 레시피만 개선해 재학습 + **로컬 GPU**. **로컬에 GTX 1650(4GB) 있음**. 단 설치된 torch가 `2.12.1+cpu`라 GPU 못 씀 → **CUDA torch로 교체**: pip가 같은 버전(2.12.1)이라 "이미 설치됨"으로 건너뜀 → `pip uninstall torch torchvision` 후 `--index-url .../cu121` 재설치 필요(→ **torch 2.5.1+cu121, torchvision 0.20.1, cuda True**). 드라이버 566.36/CUDA12.7이라 cu121 OK.
- train_food4.py 레시피 개선: EPOCHS 8→12, BATCH 64→32(4GB VRAM), 증강 강화(RandomRotation15+ColorJitter hue+RandomErasing). USE_FOOD101은 다운로드 커서 이번엔 False 유지(권장: 원하면 2차).
- 실행: `cd ModelTraining && PYTHONUTF8=1 python train_food4.py`(★PYTHONUTF8=1이 cp949 이모지 크래시 원천차단 → 인스크립트 ONNX export까지 성공, export_onnx.py 불필요). GPU 학습 ~25분(GPU util 20%대 = num_workers=0 PIL디코딩 병목, GPU 대기). stdout 블록버퍼링이라 에폭로그 실시간 안 보임(best.pt mtime으로 진행 추정).
- **결과: val_acc 0.811→0.833(+2.2%p)**. food.onnx(8.9MB, 출력(1,4)) 자동export→`Resources/Models/food.onnx` 교체(이전 백업 scratchpad). Unity 검증: 분석기=온디바이스AI(Sentis), 더미추론 4종 정상·예외0.
- ⚠️떡볶이는 여전히 실사진 없어 개선폭 작음(예고대로). 실개선은 extra_data/instant/ 실사진+재학습 필요. [[todo_extra_data_korean_boost]]
