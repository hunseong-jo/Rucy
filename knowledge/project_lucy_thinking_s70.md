---
name: project-lucy-thinking-s70
description: "루시(my-agent) 사고력 강화 — 어려운 질문에 추론 모드·deep·독립감수·분해 4중 장치(세션70, 2026-07-22)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 6696b47c-aec6-4675-bfe6-3e4a21940f9f
  modified: 2026-07-22T02:37:39.354Z
---

**세션70(2026-07-22): "루시 사고 능력 올려줘" → 어려운 질문 전용 4중 장치 추가.** 전부 config `deliberate`로 끔·쉬운 질문/이미지 보는 턴엔 안 켜져 무료 한도·속도 그대로.

기존 파이프라인엔 이미 계획(PLAN_HINT)·과거실수 회상·자가감수·`/검증`이 있었음. 구멍 2개 발견 → 메움:
1. **추론 모드(reasoning)** — 두뇌별 `reasoning` 필드 + `call_model(deep_think=)`, 어려운 질문에서만 주입. gpt-oss-120b·glm-5.2·mistral-medium-3.5=`{"reasoning_effort":"high"}`, nemotron-3-super=`{"system":"detailed thinking on"}`(agent.py `_reasoning_for`). ⭐**400 안전망**: 추론 인자 거부하는 두뇌는 **버리지 않고** 인자만 빼서 재시도(`_no_reason` set) → 답 못 받는 일 없음. ⚠️**high는 느림**(실측: 사소한 "17+25"에 glm-5.2 114초·mistral 79초, gpt-oss 0.8초) → 깊은 두뇌를 **빠른 것부터** 정렬해 느린 둘은 뒤 폴백으로만.
2. **deep 손질** — 강한 추론 두뇌 5개(Cerebras zai-glm-4.7·gpt-oss-120b·nemotron-3-super·glm-5.2·mistral)에 `deep=true`(예전엔 nemotron 1개뿐이라 라우팅 거의 무발동).
3. **독립 감수** — `review(author=)` 신설, 답한 두뇌 말고 **다른 두뇌**가 감수(자기 답 자기검토 방지). 답한 두뇌를 순서 맨 뒤로. **추가 호출 없음**(감수 1회). `deliberate.review_independent`.
4. **분해 지시** — 여러 갈래 큰 질문(140자↑ 또는 어려운 키워드 2개↑ 또는 "그리고/각각/단계" 다수)에 `DECOMPOSE_HINT` 한 줄 추가(`is_very_hard`, 추가 호출 없음). `deliberate.decompose`.

**검증(실물)**: gpt-oss·glm-5.2·mistral 모두 `reasoning_effort` 수용(400 없음) 확인, respond() E2E에서 라우팅 `+ 깊게 생각`+계획+독립감수(실제로 답 고침)까지 동작. ⭐Cerebras는 8192 컨텍스트라 하드+도구 질문에선 매번 컨텍스트초과로 빠져 gpt-oss로 폴백됨(deep 표시는 무해하나 사실상 무의미).

**함정/미결**: Groq(qwen3)·Cerebras·로컬엔 아직 `reasoning` 안 붙임(빠른 주력/최후보루는 빠르게 유지). 새 두뇌에 `reasoning` 붙일 땐 규격 확인(틀려도 400 안전망이 받아냄). 백업 `config.json.bak_s70`·`agent.py.bak_s70`. 사용설명서(유일 원본)·지식색인 갱신 완료. 관련 [[feedback-verify-by-actually-running]]([[feedback_verify_by_actually_running]]) — 이번에도 실물로 돌려 확인함.
