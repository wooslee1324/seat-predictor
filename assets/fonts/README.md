# 폰트 (자리각 모바일 데모)

이 데모는 둥글고 귀여운 한글 웹폰트 **Jua(주아)** 와 **Gaegu(개구)** 를 사용합니다.
둘 다 **SIL Open Font License(OFL)** 로 배포되는 무료·오픈 라이선스 폰트라 저작권
문제가 없습니다.

## 폰트가 적용되는 방식 (두 가지, 자동)

1. **온라인** — `mobile_demo.py` 가 Google Fonts 에서 자동으로 불러옵니다.
   데모 실행 시 인터넷이 연결되어 있으면 별도 설정 없이 바로 적용됩니다.
2. **오프라인** — 이 폴더(`assets/fonts/`)에 아래 파일이 있으면, 앱이 파일을 읽어
   base64 로 임베드하여 **인터넷 없이도** 적용합니다. 파일이 없으면 시스템 폰트로
   안전하게 폴백합니다(오류 없음).

## 오프라인용 폰트 파일 넣는 법

아래 이름으로 이 폴더에 넣어 주세요(`.woff2` 를 권장하지만 `.ttf` 도 됩니다).

- `Jua-Regular.woff2` (또는 `Jua-Regular.ttf`)
- `Gaegu-Bold.woff2` (또는 `Gaegu-Bold.ttf`)

내려받는 곳:

- Jua: https://fonts.google.com/specimen/Jua  (우측 상단 "Get font" → 다운로드)
- Gaegu: https://fonts.google.com/specimen/Gaegu

`.ttf` 만 받았다면 그대로 넣어도 되고, 용량을 줄이고 싶으면 온라인 변환기로
`.woff2` 로 바꿔 넣어도 됩니다. 파일명만 위와 같으면 자동 인식됩니다.

## 라이선스

Jua, Gaegu 모두 OFL(Open Font License). 자유롭게 사용·재배포 가능하며, 폰트 파일을
프로젝트에 포함해도 됩니다.
