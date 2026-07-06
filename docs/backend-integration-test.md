# 백엔드 로컬 통합 테스트 가이드

실제 서울시 인증키를 넣고 FastAPI 백엔드의 5개 엔드포인트를 로컬에서 호출·검증하는
방법입니다. 실패 시 원인을 **인증키 / API 파라미터 / 서울시 API 응답 형식 / 코드**
문제로 구분합니다.

> 참고: 이 문서에 실제 인증키 값은 절대 적지 않습니다. 인증키 파일
> `.streamlit/secrets.toml` 은 커밋하지 않습니다(`.gitignore` 제외).

## 1. 인증키 설정 (`.streamlit/secrets.toml`)

예시 파일을 복사해서 값만 채웁니다.

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

`.streamlit/secrets.toml` 을 열어 발급받은 키를 넣습니다.

```toml
[seoul_api]
subway_congestion_key = "발급받은_지하철혼잡도_키"   # /stations, /predict 실데이터
subway_ridership_key  = "발급받은_지하철승하차_키"   # 참고용 통계(선택)
bus_ridership_key     = "발급받은_버스승하차_키"     # 참고용 통계(선택)

# 실시간 도착정보용 (없으면 아래 폴백 규칙 적용)
subway_realtime_key   = "발급받은_지하철실시간도착_키"
bus_realtime_key      = "발급받은_버스실시간도착_키"
```

키 발급처

- 지하철 혼잡도 / 지하철 실시간 도착 / 승하차 통계: **서울 열린데이터광장**
  (`https://data.seoul.go.kr` → 인증키 신청, 무료 즉시 발급).
- 버스 실시간 도착: **TOPIS / 공공데이터포털(`data.go.kr`)** 키가 필요할 수 있음
  (버스 도착정보는 발급 포털이 다를 수 있으니 확인 필요).

폴백 규칙(키가 없을 때 동작)

- `subway_realtime_key` 가 없으면 `subway_congestion_key`(같은 열린데이터광장 키)로
  자동 폴백.
- `bus_realtime_key` 가 없으면 `bus_ridership_key` 로 폴백 시도(포털이 달라 실패할
  수 있음).
- 키가 아예 없어도 서버는 죽지 않고 `/stations` 는 기본목록, `/predict` 는 추정
  (Mock), `/realtime/*` 는 `available:false` 로 안전하게 응답합니다.

환경변수로 넣어도 됩니다(배포 환경 권장, `secrets.toml` 보다 우선).

```bash
export SEOUL_SUBWAY_CONGESTION_KEY="..."
export SEOUL_SUBWAY_REALTIME_KEY="..."
export SEOUL_BUS_REALTIME_KEY="..."
```

## 2. 백엔드 로컬 실행

프로젝트 **루트**에서 실행합니다(패키지 `core`, `backend` 를 import 하므로).

```bash
python3 -m venv .venv && source .venv/bin/activate   # (없다면)
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload
```

- 서버: `http://localhost:8000`
- 자동 문서(Swagger UI): `http://localhost:8000/docs`

## 3. 엔드포인트 수동 호출 (curl)

```bash
curl http://localhost:8000/health

curl http://localhost:8000/stations

curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"transport":"지하철","dep_station":"강남역","arr_station":"사당역","dep_hour":18,"dep_minute":30}'

curl "http://localhost:8000/realtime/subway/arrivals?station=강남역"

# ARS 번호는 정류소마다 다릅니다(정류소 안내판/버스앱에서 확인). 예시는 임의 값.
curl "http://localhost:8000/realtime/bus/arrivals?ars_id=23305"
```

## 4. 자동 통합 테스트 스크립트

서버를 켠 상태에서 다른 터미널에서 실행합니다.

```bash
# 5개 엔드포인트 호출 + 성공/실패 자동 분류
python3 scripts/integration_test.py --station 강남역 --ars 23305

# 실패 원인을 더 정밀하게(서울 API를 직접 호출해 RESULT 코드로 진단)
python3 scripts/integration_test.py --diagnose --station 강남역 --ars 23305
```

스크립트는 **인증키 값을 출력하지 않고 '설정됨/미설정'만** 표시합니다. 결과는
✅ 정상 / ⚠️ 주의(키 미설정 등으로 정상일 수 있음) / ❌ 실패(코드 문제)로 나옵니다.

## 5. 실패 원인 구분 가이드

### 증상별 1차 분류

| 증상 | 유력 원인 |
| --- | --- |
| 스크립트가 서버에 연결 못 함 | 서버 미실행(실행/코드 문제) |
| `/health` 가 200이 아님 | 코드 문제 |
| `/stations` 가 `source: 기본목록` | 인증키 미설정 또는 혼잡도 API 호출 실패(**인증키 문제** 의심) |
| `/predict` 가 `data_source: 추정(Mock)` | 실데이터 혼잡도 미매핑(**인증키 미설정** 또는 해당 역 실데이터 없음) |
| `/realtime/*` 가 `available:false` + "인증키" 문구 | **인증키 문제** |
| `/realtime/*` 가 `available:false` + "호출에 실패" | 서울시 API 호출 실패 → `--diagnose` 로 세분화 |
| `/realtime/*` 가 `available:true` 인데 목록 비어 있음 | 정상(도착 예정 없음) 또는 **역명/ARS(파라미터)** 확인 |

### `--diagnose` 의 서울 API RESULT 코드 해석 (열린데이터광장 계열, 확인 필요)

| 코드 | 의미 | 분류 |
| --- | --- | --- |
| `INFO-000` | 정상 처리 | 정상 |
| `INFO-100` | 인증키가 유효하지 않음 | **인증키 문제** |
| `INFO-200` | 해당 데이터 없음 | **API 파라미터 문제**(역명/범위 확인) |
| `ERROR-300` | 필수 값 누락 | **API 파라미터 문제** |
| `ERROR-310` | 서비스를 찾을 수 없음 | **코드 문제**(서비스명 확인) |
| `ERROR-331` | 요청 시작 위치 오류 | **API 파라미터 문제** |
| `ERROR-336` | 한 번에 최대 1000건 | **API 파라미터 문제** |
| `ERROR-500` / `ERROR-600` | 서버/DB 오류 | **서울시 API 응답/서버 문제** |

버스 도착정보(공공데이터포털 계열)는 `returnReasonCode` 로 구분됩니다: `30`(미등록
서비스키)·`31`(기간 만료)·`32`(미등록 IP)·`22`(호출 초과)는 **인증키 문제**,
`10`(잘못된 파라미터)은 **API 파라미터 문제**, `01`(어플리케이션 에러)은 **서버
문제**입니다. 응답이 JSON이 아니면(HTML/XML 등) **응답 형식 문제**입니다.

## 6. 테스트 결과 기록 템플릿

실행 후 아래 표를 채워 팀과 공유하세요(키 값은 적지 않습니다).

| 엔드포인트 | 결과(✅/⚠️/❌) | data_source / available | 원인 분류 | 메모 |
| --- | --- | --- | --- | --- |
| GET /health | | | | |
| GET /stations | | (실데이터/기본목록) | | |
| POST /predict | | (실데이터/추정) | | |
| GET /realtime/subway/arrivals | | (available) | | |
| GET /realtime/bus/arrivals | | (available) | | |

## 정보 구분 원칙 (중요)

- `/realtime/*` 응답은 **실시간 '도착정보'만** 담습니다.
- **예상 혼잡도·예상 좌석 확률**은 `POST /predict` 의 추정치입니다(실측 아님).
- 버스의 `realtime_congestion`·`is_full` 은 버스 API가 줄 때만 담기는 **참고용
  실시간 혼잡 신호**이며, 좌석 수·좌석 확률이 아닙니다.
- **참고용 통계**(하루 승하차 등)는 과거 집계 데이터입니다.

이 네 가지를 화면·응답에서 섞지 않습니다.
