# 모바일 데모 협업 가이드

이 브랜치는 수업 발표용 모바일 데모의 base 브랜치입니다. 기존 `app.py`는
Streamlit 웹 프로토타입으로 그대로 유지하고, `mobile_demo.py`는 스마트폰 화면처럼
보이도록 만든 발표용 진입점입니다.

## 실행 방법

```bash
streamlit run mobile_demo.py
```

기존 웹 프로토타입을 확인하려면 아래 명령어를 사용합니다.

```bash
streamlit run app.py
```

## 개발을 시작하기 전에

먼저 모바일 데모 base 브랜치로 이동하고 최신 내용을 받아옵니다.

```bash
git checkout mobile-demo-base
git pull origin mobile-demo-base
```

그 다음 본인이 맡은 기능용 브랜치를 새로 만듭니다.

```bash
git checkout -b feature-your-task-name
```

예시:

```bash
git checkout -b feature-favorite-routes
git checkout -b feature-map-screen
git checkout -b feature-result-design
```

## 수정 후 제출

```bash
git status
git add .
git commit -m "add favorite routes screen"
git push origin feature-your-task-name
```

GitHub에서 Pull Request를 만들고, 다른 팀원의 확인을 받은 뒤 병합합니다.

## 역할 분담 제안

- `mobile_demo.py`: 모바일 데모 화면.
- `app.py`: 기존 Streamlit 웹 프로토타입. 삭제하지 않고 유지합니다.
- `seoul_api.py`: 서울시 공공데이터 연동 및 예측 데이터 처리.
- `docs/`: 팀 가이드, 발표 스크립트, 역할 분담 기록.

## 주의사항

- `main` 브랜치에서 직접 작업하지 않습니다.
- `.streamlit/secrets.toml`은 GitHub에 올리지 않습니다.
- 데이터 처리 코드를 수정했다면 `app.py`와 `mobile_demo.py`가 모두 실행되는지 확인합니다.
- 작업을 시작하기 전에 항상 최신 브랜치를 먼저 받아와 충돌을 줄입니다.
