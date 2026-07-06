"""로컬 통합 테스트 — 실행 중인 FastAPI 백엔드의 5개 엔드포인트를 실제로 호출해
정상 여부를 확인하고, 실패하면 원인을 4가지로 분류한다.

  · 인증키 문제        · API 파라미터 문제
  · 서울시 API 응답 형식 문제   · 코드 문제

원칙
- 인증키 값은 절대 출력·기록하지 않는다(설정 '여부'만 표시).
- 실제 좌석 수를 실시간 값처럼 표현하지 않는다(좌석 확률은 /predict 의 추정치).

사용법
  # 1) 다른 터미널에서 백엔드 실행 (프로젝트 루트에서)
  #    uvicorn backend.main:app
  # 2) 이 스크립트 실행
  python3 scripts/integration_test.py --station 강남역 --ars 23305
  # 3) (선택) 실패 원인을 더 정밀하게: 서울 API를 직접 호출해 RESULT 코드로 진단
  python3 scripts/integration_test.py --diagnose --station 강남역 --ars 23305

의존성: requests (backend/requirements.txt 에 포함). 서버가 떠 있어야 한다.
"""

from __future__ import annotations

import argparse
import sys

import requests

# ---------------------------------------------------------------------------
# 서울 열린데이터광장 / TOPIS 공통 결과 코드 해석 (확인 필요 — 실제 message 로 재확인)
# ---------------------------------------------------------------------------
SEOUL_RESULT_CODES = {
    "INFO-000": ("정상 처리", "정상"),
    "INFO-100": ("인증키가 유효하지 않음", "인증키 문제"),
    "INFO-200": ("해당하는 데이터가 없음(파라미터/데이터 범위 확인)", "API 파라미터 문제"),
    "ERROR-300": ("필수 값이 누락됨", "API 파라미터 문제"),
    "ERROR-301": ("파일 타입 값이 누락됨", "API 파라미터 문제"),
    "ERROR-310": ("해당 서비스를 찾을 수 없음(서비스명 확인)", "코드 문제"),
    "ERROR-331": ("요청 시작 위치 값 오류", "API 파라미터 문제"),
    "ERROR-336": ("요청은 한 번에 최대 1000건", "API 파라미터 문제"),
    "ERROR-500": ("서버 오류", "서울시 API 응답/서버 문제"),
    "ERROR-600": ("DB 연결 실패", "서울시 API 응답/서버 문제"),
}

# 공공데이터포털(data.go.kr) 표준 오류 코드 일부 (버스 도착정보 등)
DATAGO_REASON_CODES = {
    "30": ("등록되지 않은 서비스키", "인증키 문제"),
    "31": ("활용기간 만료", "인증키 문제"),
    "32": ("등록되지 않은 IP", "인증키 문제"),
    "22": ("호출 횟수 초과", "인증키 문제"),
    "20": ("서비스 접근 거부", "인증키 문제"),
    "12": ("폐기된 서비스", "코드 문제"),
    "10": ("잘못된 요청 파라미터", "API 파라미터 문제"),
    "01": ("어플리케이션 에러", "서울시 API 응답/서버 문제"),
}


def _line(level: str, name: str, msg: str) -> None:
    mark = {"OK": "✅", "WARN": "⚠️ ", "FAIL": "❌"}.get(level, "  ")
    print(f"{mark} [{name}] {msg}")


# ---------------------------------------------------------------------------
# 백엔드 응답 분류 (합성 응답으로도 테스트 가능하도록 순수 함수로 분리)
# ---------------------------------------------------------------------------
def classify_health(status_code: int, body: dict | None) -> tuple[str, str]:
    if status_code == 200 and isinstance(body, dict) and body.get("status") == "정상":
        return "OK", "서버 정상 동작"
    if status_code != 200:
        return "FAIL", f"HTTP {status_code} — 코드 문제(서버 오류)"
    return "FAIL", "응답 형식이 예상과 다름 — 코드 문제"


def classify_stations(status_code: int, body: dict | None) -> tuple[str, str]:
    if status_code != 200 or not isinstance(body, dict):
        return "FAIL", f"HTTP {status_code} — 코드 문제"
    source = body.get("source")
    count = body.get("count", 0)
    if source == "실데이터":
        return "OK", f"실데이터 역 목록 {count}개"
    if source == "기본목록":
        return "WARN", "기본목록으로 폴백 — 인증키 미설정 또는 혼잡도 API 호출 실패(인증키 문제 의심)"
    return "FAIL", "source 필드 없음 — 코드 문제"


def classify_predict(status_code: int, body: dict | None) -> tuple[str, str]:
    if status_code != 200 or not isinstance(body, dict):
        return "FAIL", f"HTTP {status_code} — 코드/파라미터 문제"
    ds = body.get("data_source")
    if ds == "실데이터":
        return "OK", "실데이터 혼잡도 기반 예측(좌석 확률은 추정치)"
    if ds == "추정(Mock)":
        return "WARN", "Mock 예측 — 실데이터 혼잡도 미매핑(인증키 미설정 또는 해당 역 실데이터 없음)"
    return "FAIL", "data_source 필드 없음 — 코드 문제"


def classify_realtime(status_code: int, body: dict | None, kind: str) -> tuple[str, str]:
    if status_code != 200 or not isinstance(body, dict):
        return "FAIL", f"HTTP {status_code} — 코드 문제"
    if body.get("available") is True:
        n = len(body.get("arrivals", []))
        if n > 0:
            return "OK", f"실시간 도착정보 {n}건 수신"
        return "WARN", "정상 응답이나 도착 예정 없음 — 시간대/역·정류장(파라미터) 확인 권장"
    # available == False
    msg = str(body.get("message", ""))
    if "인증키" in msg:
        return "WARN", "미제공 — 인증키 문제(키 미설정)"
    if "호출에 실패" in msg:
        return "WARN", "미제공 — 서울시 API 호출 실패(네트워크/파라미터/응답형식). --diagnose 로 세분화"
    return "WARN", f"미제공 — {msg or '원인 미상'}"


# ---------------------------------------------------------------------------
# 실제 호출
# ---------------------------------------------------------------------------
def _get(base: str, path: str, **params):
    return requests.get(base + path, params=params or None, timeout=15)


def run_endpoint_tests(base: str, station: str, ars: str | None) -> int:
    print(f"\n=== 백엔드 엔드포인트 테스트 ({base}) ===")
    failures = 0

    tests = []
    try:
        r = _get(base, "/health")
        tests.append(("GET /health", classify_health(r.status_code, _json(r))))
    except requests.exceptions.ConnectionError:
        _line("FAIL", "GET /health", f"서버에 연결할 수 없음 — 백엔드가 실행 중인지 확인({base})")
        print("\n서버가 실행 중이 아닙니다. 먼저 'uvicorn backend.main:app' 을 실행하세요.")
        return 1

    r = _get(base, "/stations")
    tests.append(("GET /stations", classify_stations(r.status_code, _json(r))))

    r = requests.post(
        base + "/predict",
        json={"transport": "지하철", "dep_station": station, "arr_station": "사당역",
              "dep_hour": 18, "dep_minute": 30},
        timeout=15,
    )
    tests.append(("POST /predict", classify_predict(r.status_code, _json(r))))

    r = _get(base, "/realtime/subway/arrivals", station=station)
    tests.append((f"GET /realtime/subway/arrivals?station={station}",
                  classify_realtime(r.status_code, _json(r), "subway")))

    if ars:
        r = _get(base, "/realtime/bus/arrivals", ars_id=ars)
        tests.append((f"GET /realtime/bus/arrivals?ars_id={ars}",
                      classify_realtime(r.status_code, _json(r), "bus")))
    else:
        _line("WARN", "GET /realtime/bus/arrivals", "--ars 미지정으로 건너뜀(정류소 ARS 번호 필요)")

    for name, (level, msg) in tests:
        _line(level, name, msg)
        if level == "FAIL":
            failures += 1
    return failures


def _json(resp):
    try:
        return resp.json()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# (선택) 서울 API 직접 진단 — 원인 세분화. 키 값은 절대 출력하지 않는다.
# ---------------------------------------------------------------------------
def _mask(key: str | None) -> str:
    return "설정됨" if key else "미설정"


def diagnose(station: str, ars: str | None) -> None:
    print("\n=== 서울 API 직접 진단 (원인 세분화) ===")
    try:
        from backend import config
        from core import realtime
    except Exception as exc:  # noqa: BLE001
        print(f"진단 모듈 로드 실패 — 프로젝트 루트에서 실행하세요 ({exc})")
        return

    # 1) 지하철 혼잡도 키 / 실시간 키
    print(f"- 지하철 혼잡도 키(subway_congestion): {_mask(config.congestion_key())}")
    print(f"- 지하철 실시간 키(subway_realtime): {_mask(config.subway_realtime_key())}")
    print(f"- 버스 실시간 키(bus_realtime): {_mask(config.bus_realtime_key())}")

    # 2) 지하철 실시간 도착 RAW 호출 → RESULT 코드 해석
    skey = config.subway_realtime_key()
    if skey:
        name = realtime._subway_query_name(station)
        url = f"{realtime.SUBWAY_REALTIME_BASE}/{skey}/json/realtimeStationArrival/0/5/{name}"
        _diagnose_raw("지하철 실시간 도착", url, portal="seoul")
    else:
        print("- 지하철 실시간 진단 건너뜀(키 미설정)")

    # 3) 버스 실시간 도착 RAW 호출 → RESULT 코드 해석
    bkey = config.bus_realtime_key()
    if bkey and ars:
        try:
            import requests as _rq
            resp = _rq.get(realtime.BUS_STATION_ARRIVAL_URL,
                           params={"serviceKey": bkey, "arsId": ars, "resultType": "json"}, timeout=15)
            _interpret_bus(resp)
        except Exception as exc:  # noqa: BLE001
            print(f"- 버스 실시간 진단 호출 실패: {exc.__class__.__name__}(네트워크/도메인 확인)")
    elif not bkey:
        print("- 버스 실시간 진단 건너뜀(키 미설정)")
    else:
        print("- 버스 실시간 진단 건너뜀(--ars 미지정)")


def _diagnose_raw(label: str, url: str, portal: str) -> None:
    import requests as _rq
    try:
        resp = _rq.get(url, timeout=15)
    except Exception as exc:  # noqa: BLE001
        print(f"- {label}: 호출 실패 {exc.__class__.__name__} → 네트워크/도메인 문제")
        return
    try:
        data = resp.json()
    except Exception:
        head = resp.text[:80].replace("\n", " ")
        print(f"- {label}: JSON 아님(응답 형식 문제) HTTP {resp.status_code} 앞부분='{head}'")
        return
    err = data.get("errorMessage") or {}
    code = err.get("code")
    if code:
        desc, cause = SEOUL_RESULT_CODES.get(code, (err.get("message", "알 수 없음"), "원인 판별 불가 — 원문 확인"))
        print(f"- {label}: 코드 {code} → {desc} [{cause}]")
    else:
        print(f"- {label}: RESULT 코드 없음(응답 형식 확인 필요) HTTP {resp.status_code}")


def _interpret_bus(resp) -> None:
    try:
        data = resp.json()
    except Exception:
        head = resp.text[:80].replace("\n", " ")
        print(f"- 버스 실시간 도착: JSON 아님(응답 형식 문제) HTTP {resp.status_code} 앞부분='{head}'")
        return
    # 공공데이터포털 표준 오류 형태
    svc = data.get("OpenAPI_ServiceResponse")
    if isinstance(svc, dict):
        rc = (svc.get("cmmMsgHeader") or {}).get("returnReasonCode")
        desc, cause = DATAGO_REASON_CODES.get(str(rc), ("알 수 없는 오류", "원인 판별 불가 — 원문 확인"))
        print(f"- 버스 실시간 도착: 코드 {rc} → {desc} [{cause}]")
        return
    header = data.get("msgHeader") or {}
    hcd = header.get("headerCd")
    hmsg = header.get("headerMsg", "")
    if hcd is not None:
        cause = "정상" if str(hcd) == "0" else "원인 판별 불가 — headerMsg 확인"
        print(f"- 버스 실시간 도착: headerCd {hcd} ('{hmsg}') [{cause}]")
    else:
        print(f"- 버스 실시간 도착: 표준 헤더 없음(응답 형식 확인 필요) HTTP {resp.status_code}")


def main() -> int:
    parser = argparse.ArgumentParser(description="seat-predictor 백엔드 로컬 통합 테스트")
    parser.add_argument("--base-url", default="http://localhost:8000", help="백엔드 주소")
    parser.add_argument("--station", default="강남역", help="테스트할 지하철 역명")
    parser.add_argument("--ars", default=None, help="테스트할 버스 정류소 ARS 번호")
    parser.add_argument("--diagnose", action="store_true", help="서울 API 직접 호출로 원인 세분화")
    args = parser.parse_args()

    failures = run_endpoint_tests(args.base_url.rstrip("/"), args.station, args.ars)
    if args.diagnose:
        diagnose(args.station, args.ars)

    print()
    if failures:
        print(f"결과: 실패(FAIL) {failures}건 — 위 분류를 참고해 원인을 확인하세요.")
        return 1
    print("결과: 치명적 실패 없음(WARN 은 인증키 미설정 등으로 정상일 수 있음).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
