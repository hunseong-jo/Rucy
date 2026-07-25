# Stable Diffusion WebUI API의 img2img 및 inpaint 기능을 활용한 특정 영역 수정 — 루시 자가 학습 노트 (2026-07-17)

> 루시가 스스로 웹을 조사해 정리한 노트입니다. 검증되지 않았을 수 있으니
> 수치·사실을 인용할 때는 출처를 함께 말할 것.

# Stable Diffusion WebUI img2img 및 Inpaint 기능 학습 노트

## 개요
* Stable Diffusion WebUI의 **img2img** 탭 내에서 사용 가능한 편집 기능으로, 이미지의 특정 부위를 수정하고자 할 때 사용된다.
* 소위 'Inpaint(인페인트)'라고 불리며, 마스크를 활용해 텍스트 프롬프트에 따라 특정 영역을 변경하는 기술이다.
* 마스크를 페인트 칠하듯이 씌우면 해당 부분만 새로운 이미지로 생성해 편집한다.

## 주요 용도 및 예시
* **부분 수정:** 이미지 전체가 아닌 원하는 영역만 수정할 때 활용한다.
* **결함 보정:** 주로 팔, 다리, 손, 발 등이 기형적으로 그려진 경우 해당 부분만 교정하는 데 쓰인다.
* **변경 적용:** 예를 들어 소파를 검은색으로 다시 칠하는 등 특정 물체의 색상이나 형태를 바꾸는 작업에 적용 가능하다.

## 사용 절차
1. **이미지 가져오기:** txt2img 또는 img2img로 생성된 이미지를 사용하거나, **PNG info** 기능을 통해 기존 이미지를 불러온다.
2. **Inpaint로 전송:** 불러온 이미지에서 **'send to inpaint'** 버튼을 클릭하여 img2img inpaint 모드로 진입한다.
3. **마스킹 및 생성:** 수정하고 싶은 부분에 마스킹(칠하기)을 수행한 뒤 이미지를 생성한다.

## 주요 설정 옵션
* **mask blur:** 마스크의 경계를 흐리게 하는 옵션이며, 기본값은 **4**이다.
* img2img와 유사한 옵션들을 포함하고 있다.

## 출처
* 잡식성 개발자의 블로그: https://rightnowhj.tistory.com/59
* 루피캣: https://rupicat.com/entry/Stable-Diffusion-Webui-img2img-inpaint%EB%A1%9C-%EC%86%90%EB%B0%9C-%EC%88%98%EC%A0%95
* TILNOTE: https://tilnote.io/pages/640adfbef4ea08b9071cc823
