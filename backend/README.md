# 백엔드 (FastAPI)

`core/` 의 예측·데이터 로직을 REST API로 노출하는 서버입니다. 발표용 데모
(`app.py`, `mobile_demo.py`)와 **같은 `core/` 로직을 공유**하므로, 앞으로 만들
모바일 웹앱(PWA)이나 다른 클라이언트가 이 API를 그대로 사용할 수 있습니다.

기존 Streamlit 데모는 이 백엔드와 무관하게 그대로 동작합니다. 백엔드는 Streamlit에
의존하지 않는 `core/seoul_api.py` · `core/prediction.py` 만 호출합니다.

## 폴더 구조

```
backend/
├── main.py            # FastAPI 앱 생성, CORS, 라우터 등록
├── config.py          # 인증키 로드(환경변수/secrets.toml), 설정값
├── schemas.py         # 요청/응답 스키마(Pydantic)
├── services.py        # core 를 호출하는 서비스 계층
├── routers/
│   ├── health.py      # GET /health
│   ├── stations.py    # GET /stations
│   ├── predict.py     # POST /predict
│   └── realtime.py    # GET /realtime/subway/arrivals, /realtime/bus/arrivals
├── requirements.txt   # 백엔드 실행에 필요한 라이브러리
└── README.md          # (이 문서)
```

## 실행 방법

프로젝트 루트에서 실행합니다. 이 저장소는 `core/` 를 최상위 패키지로 import 하므로
**반드시 루트 폴더에서** 서버를 켜야 합니다.

### 1. 가상환경 준비 (없다면)

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 2. 라이브러리 설치

```bash
pip install -r backend/requirements.txt
```

### 3. (선택) 서울 공공데이터 인증키 설정

인증키가 없어도 서버는 정상 동작합니다. 이 경우 `/stations` 는 기본 역 목록을,
`/predict` 는 추정(Mock) 예측을 돌려줍니다. 실데이터를 쓰려면 아래 둘 중 하나로
키를 넣습니다.

방법 A — 환경변수(배포 환경 권장):

```bash
export SEOUL_SUBWAY_CONGESTION_KEY="발급받은_지하철혼잡도_인증키"
```

방법 B — 데모와 키 공유(로컬 개발 편의): 데모가 쓰는 `.streamlit/secrets.toml` 의
`[seoul_api]` 섹션을 백엔드도 자동으로 읽습니다. 이미 데모용으로 설정해 두었다면
추가 작업이 필요 없습니다.

> ⚠️ `.streamlit/secrets.toml` 은 인증키 파일이므로 **절대 커밋하지 않습니다**.
> `.gitignore` 로 이미 제외되어 있습니다.

### 4. 서버 실행

```bash
uvicorn backend.main:app --reload
```

- 서버 주소: `http://localhost:8000`
- 자동 생성 API 문서(Swagger UI): `http://localhost:8000/docs`

## 엔드포인트

### `GET /health` — 서버 상태 확인

```bash
curl http://localhost:8000/health
```

응답 예시:

```json
{ "status": "정상", "service": "오늘 좌석 예측기 API", "version": "0.1.0" }
```

### `GET /stations` — 지하철 역 목록

```bash
curl http://localhost:8000/stations
```

응답 예시:

```json
{ "stations": ["가락시장역", "..."], "count": 200, "source": "실데이터" }
```

`source` 는 실데이터를 받았으면 `"실데이터"`, 인증키가 없어 기본 목록으로
폴백했으면 `"기본목록"` 입니다.

### `POST /predict` — 좌석 확률 예측

요청 본문(JSON):

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `transport` | `"지하철"` / `"버스"` | 예 | 교통수단 |
| `dep_station` | 문자열 | 예 | 출발역/정류장 |
| `arr_station` | 문자열 | 예 | 도착역/정류장 |
| `dep_hour` | 정수(0~23) | 예 | 출발 시각(시) |
| `dep_minute` | 정수(0~59) | 아니오(기본 0) | 출발 시각(분) |
| `profile` | `"web"` / `"mobile"` | 아니오(기본 web) | 예측 프리셋 |

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"transport":"지하철","dep_station":"강남역","arr_station":"사당역","dep_hour":18,"dep_minute":30}'
```

응답에는 현재 혼잡도·좌석 확률, 추천 탑승 시점과 대기 위치, 시간대별 곡선
(`series`), 그리고 좌석 확률이 추정치임을 알리는 `notice` 가 포함됩니다.

### `GET /realtime/subway/arrivals` — 지하철 실시간 도착정보

특정 역의 **실시간 도착 예정 열차** 정보를 반환합니다. 이 응답에는 **예상 좌석
확률이 포함되지 않습니다**(좌석 확률은 `POST /predict` 전용).

```bash
curl "http://localhost:8000/realtime/subway/arrivals?station=강남역"
```

응답 예시(제공 가능 시):

```json
{
  "station": "강남역",
  "available": true,
  "data_source": "실시간 도착정보",
  "arrivals": [
    {
      "line": "2호선",
      "direction": "상행",
      "destination": "성수",
      "train_line_name": "성수행 - 건대입구방면",
      "arrival_message": "전역 출발",
      "seconds_to_arrival": 90,
      "train_no": "2312",
      "received_at": "2026-07-06 18:30:11"
    }
  ],
  "message": "실시간 도착정보를 불러왔습니다.",
  "notice": "이 응답은 실시간 '도착정보'만 담고 있습니다. 예상 좌석 확률은 ..."
}
```

### `GET /realtime/bus/arrivals` — 버스 실시간 도착정보

정류소 **ARS 번호** 기준으로 실시간 도착 예정 버스 정보를 반환합니다. 버스 API가
줄 때만 **실시간 혼잡도**(`realtime_congestion`)와 **만차 여부**(`is_full`)가
담기며, 이는 좌석 확률이 아니라 참고용 실시간 혼잡 신호입니다.

```bash
curl "http://localhost:8000/realtime/bus/arrivals?ars_id=23305"
```

### 안전 처리(fallback)와 정보 구분 원칙

- **인증키가 없거나 API 호출이 실패해도 서버는 죽지 않습니다.** 이 경우
  `available: false`, `data_source: "미제공"`, `arrivals: []` 와 함께 이유를
  `message` 로 안내합니다.
- 실시간 엔드포인트는 **"실시간 도착정보"만** 반환합니다. "예상 혼잡도"·"예상 좌석
  확률"은 `POST /predict`, "참고용 통계"는 별도이며, 서로 섞지 않습니다.
- 실제 좌석 수는 어떤 API도 제공하지 않으므로, 좌석 관련 값은 언제나 `/predict`
  의 **추정치**로만 표시합니다.

### 실시간용 인증키 설정

`/realtime` 엔드포인트는 아래 키를 사용합니다(없으면 위의 안전 처리로 동작).

- `SEOUL_SUBWAY_REALTIME_KEY` (또는 `secrets.toml` 의 `subway_realtime_key`) —
  없으면 지하철 혼잡도 키(`subway_congestion_key`)로 폴백.
- `SEOUL_BUS_REALTIME_KEY` (또는 `secrets.toml` 의 `bus_realtime_key`) — 버스
  도착정보는 TOPIS/공공데이터포털 키가 필요할 수 있습니다.

> ⚠️ 인증키 파일(`.streamlit/secrets.toml`)은 **절대 커밋하지 않습니다**.

## core 와의 관계

이 백엔드는 `core/` 를 **읽기만** 하고 수정하지 않습니다. 따라서 예측 결과는
데모와 완전히 동일합니다. 예측 로직을 바꾸고 싶다면 `core/prediction.py` 를
고치면 되고, 그 변경은 데모와 백엔드에 함께 반영됩니다.
