# 코드 구조와 파일 역할

이 문서는 현재 코드 구조를 점검하고, 각 파일이 맡은 역할과 이번 리팩터링으로
바뀐 점을 정리합니다. 목표는 "발표용 데모"에서 "실제 확장 가능한 서비스"로
넘어갈 수 있는 안전한 뼈대를 만드는 것입니다.

## 한눈에 보는 계층

```
┌───────────────────────────────────────────────┐
│  진입점(UI 계층) — 화면을 그리는 코드            │
│                                                │
│   app.py            mobile_demo.py             │
│   (웹 프로토타입)     (모바일 발표 데모)           │
│        │                  │                    │
│        └────────┬─────────┘                    │
│                 ▼                              │
│  seoul_api.py (하위호환 shim)                   │
└─────────────────┬──────────────────────────────┘
                  ▼
┌───────────────────────────────────────────────┐
│  core/ — 순수 파이썬 도메인 로직                 │
│  (Streamlit·FastAPI 등 프레임워크에 의존하지 않음) │
│                                                │
│   core/prediction.py   예측 엔진 + 프리셋        │
│   core/seoul_api.py     서울 공공데이터 연동      │
│   core/cache.py         TTL 캐시                │
└───────────────────────────────────────────────┘
```

핵심 아이디어는 **"화면 코드"와 "로직 코드"를 분리**하는 것입니다. 이전에는 예측
로직이 `app.py`와 `mobile_demo.py` 양쪽에 거의 똑같이 복제되어 있었고, 데이터
연동 코드가 Streamlit에 묶여 있어 백엔드나 앱에서 재사용할 수 없었습니다. 이제
로직은 전부 `core/`에 모이고, 화면 코드는 그 로직을 불러다 쓰기만 합니다.

## 파일별 역할

### app.py — 기존 웹 프로토타입 (유지)

넓은 화면(desktop) 기준의 Streamlit 대시보드입니다. 처음 만든 MVP이며,
검증·데모·참고용으로 그대로 유지합니다(삭제하지 않습니다). 이번 리팩터링에서
내부에 복제돼 있던 예측 함수(`generate_prediction`)와 혼잡도 등급 함수를
제거하고, 대신 `core.prediction`의 `build_prediction(WEB_PRESET, ...)`을
호출하도록 바꿨습니다. 화면 구성과 출력 결과는 이전과 동일합니다.

실행: `streamlit run app.py`

### mobile_demo.py — 모바일 발표 데모 (유지)

스마트폰 화면처럼 보이도록 폭을 좁히고(430px) 하단 탭바·저장 경로 등을 넣은
발표용 진입점입니다. 마찬가지로 복제돼 있던 예측 로직을 제거하고
`build_prediction(MOBILE_PRESET, ...)`을 호출합니다. **출력 결과는 리팩터링
이전과 완전히 동일**함을 회귀 검증(`scripts/regression_check.py`)으로 확인했습니다.

실행: `streamlit run mobile_demo.py`

### seoul_api.py — 하위호환 shim

실제 서울 공공데이터 연동 구현은 `core/seoul_api.py`로 옮겼습니다. 다만 기존
코드가 `import seoul_api`로 이 모듈을 참조하고 있어, 이 파일은 `core.seoul_api`의
공개 함수 네 개(`get_station_options`, `get_real_congestion_series`,
`get_bus_ridership_stat`, `get_subway_ridership_stat`)를 그대로 다시 내보내는
얇은 연결 파일 역할만 합니다. 덕분에 기존 import가 깨지지 않습니다. 새로 작성하는
코드는 `from core.seoul_api import ...`를 직접 쓰는 것을 권장합니다.

### core/prediction.py — 예측 엔진 (신규)

좌석 확률·혼잡도 곡선을 만드는 로직을 하나로 통합했습니다.

- `PredictionConfig`: 곡선을 만드는 데 쓰이는 모든 튜닝 상수를 담는 설정 객체.
- `WEB_PRESET` / `MOBILE_PRESET`: 각각 기존 웹·모바일 화면의 결과를 그대로
  재현하는 프리셋. 새 화면이나 서비스가 다른 곡선을 원하면 설정만 바꿔 프리셋을
  추가하면 됩니다.
- `build_prediction(config, ...)`: 실제 예측을 수행하는 단일 함수.
- `congestion_level(pct)` / `congestion_level_color(pct)`: 혼잡도 등급 라벨과
  이모지/색상을 돌려주는 헬퍼(웹은 이모지, 모바일은 CSS 색상 변수를 사용).

좌석 확률은 실측값이 아니라 "혼잡도가 낮을수록 좌석 확률이 높다"는 유도 공식으로
만든 추정치입니다. 이 점은 각 화면 캡션에 항상 표시합니다. 같은 입력이면 항상 같은
결과가 나오도록 시드는 입력 조합에서 결정론적으로(SHA-256) 만듭니다.

### core/seoul_api.py — 서울 공공데이터 연동 (신규 위치)

기존 `seoul_api.py`의 구현을 옮긴 것으로, **Streamlit 의존을 제거**했습니다.
무거운 API 응답 캐싱은 `@st.cache_data` 대신 `core/cache.py`의 `ttl_cache`로
처리하므로, 앞으로 만들 백엔드 API 등 다른 실행 환경에서도 그대로 재사용할 수
있습니다. 세 가지 데이터를 다룹니다.

- 지하철 혼잡도(`subwConfusion`): 예측용 실데이터. 시간대별 값이 있어 좌석 확률
  곡선에 직접 쓰입니다.
- 지하철/버스 하루 승하차 인원(`CardSubwayStatsNew`, `CardBusStatisticsServiceNew`):
  시간대 구분 없는 하루 총합만 제공되어 예측에는 쓰지 않고, "오늘 이 역/정류장
  하루 이용객 약 N명" 같은 참고 지표로만 노출합니다.

### core/cache.py — TTL 캐시 (신규)

프레임워크에 의존하지 않는 간단한 시간 기반 캐시 데코레이터입니다. Streamlit의
`@st.cache_data`가 하던 "일정 시간 동안 결과 재사용" 동작을 순수 파이썬으로
대체합니다.

### scripts/regression_check.py — 회귀 검증 (신규)

리팩터링 후에도 모바일 예측 결과가 이전과 완전히 같은지, 웹 예측이 결정론적인지
검증합니다. 코드를 GitHub에 반영하기 전에 실행하는 것을 권장합니다.

실행: `python3 scripts/regression_check.py`

## 이번 리팩터링에서 지킨 원칙

- 기존 기능을 바꾸지 않았습니다. 화면 구성·출력 결과는 그대로이며, 모바일 결과는
  회귀 검증으로 완전 일치를 확인했습니다.
- `app.py`는 삭제하지 않고 유지했습니다.
- 모든 코드 주석과 문서는 한국어로만 작성했습니다.
- 인증키 파일(`.streamlit/secrets.toml`)은 `.gitignore`로 제외되어 커밋되지
  않습니다.
- 작업은 `main`이 아니라 별도 기능 브랜치에서 진행했습니다.
