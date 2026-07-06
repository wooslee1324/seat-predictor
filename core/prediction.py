"""좌석 확률 예측 엔진 (프레임워크 비의존).

기존에는 app.py(웹)와 mobile_demo.py(모바일 데모)가 거의 같은 예측 로직을 각자
복제해 두 곳에서 미세하게 다른 상수를 유지하고 있었다. 이 모듈은 그 로직을
하나의 build_prediction() 함수 + PredictionConfig 로 통합하고, 두 진입점의
"보이는 결과"를 그대로 재현하는 프리셋(WEB_PRESET, MOBILE_PRESET)을 제공한다.

핵심 원칙
- 좌석 확률(seat_prob_pct)은 실측값이 아니라 "혼잡도가 낮을수록 좌석 확률이
  높다"는 유도 공식으로 추정한 값이다. 이 점은 각 화면 캡션에 항상 표시한다.
- real_congestion_pct 가 주어지면 그 값을 혼잡도로 쓰고, 없으면 mock 곡선을
  생성한다. 두 경우 모두 동일한 좌석 확률 유도 공식을 쓴다.
- 시드는 (교통수단, 출발지, 도착지, 시, 분) 조합에서 결정론적으로 만들어(SHA-256)
  같은 입력이면 항상 같은 결과가 나온다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from hashlib import sha256
from typing import Optional

import numpy as np
import pandas as pd

# 혼잡도 구간 임계값(공통) — (임계값, 라벨, 이모지, CSS 색상변수)
_CONGESTION_LEVELS = [
    (80, "매우 혼잡", "🔴", "var(--red)"),
    (60, "혼잡", "🟠", "var(--amber)"),
    (40, "보통", "🟡", "var(--teal)"),
    (0, "여유", "🟢", "var(--green)"),
]

MINUTES_OFFSET_STEP = 5
MINUTES_OFFSET_END = 65  # np.arange(0, 65, 5) -> 0,5,...,60


def congestion_level(pct: float) -> tuple[str, str]:
    """혼잡도(%) -> (라벨, 이모지). 웹(app.py)에서 사용."""
    for threshold, label, emoji, _color in _CONGESTION_LEVELS:
        if pct >= threshold:
            return label, emoji
    return _CONGESTION_LEVELS[-1][1], _CONGESTION_LEVELS[-1][2]


def congestion_level_color(pct: float) -> tuple[str, str]:
    """혼잡도(%) -> (라벨, CSS 색상변수). 모바일 데모(mobile_demo.py)에서 사용."""
    for threshold, label, _emoji, color in _CONGESTION_LEVELS:
        if pct >= threshold:
            return label, color
    return _CONGESTION_LEVELS[-1][1], _CONGESTION_LEVELS[-1][3]


def _seed_from(*parts: object) -> int:
    """입력 조합에서 결정론적 시드를 만든다(SHA-256 앞 8바이트)."""
    digest = sha256("|".join(map(str, parts)).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % (2**32)


@dataclass(frozen=True)
class PredictionConfig:
    """예측 곡선을 만드는 데 쓰이는 모든 튜닝 상수.

    프리셋(WEB_PRESET, MOBILE_PRESET)으로 기존 두 화면의 결과를 그대로 재현한다.
    새 화면/서비스가 다른 느낌의 곡선을 원하면 이 설정만 바꿔 만들면 된다.
    """

    # mock 혼잡도 곡선 — 러시아워 가우시안 (교통수단별 중심/폭)
    rush_center: dict = field(default_factory=lambda: {"지하철": 18.5, "버스": 18.5})
    rush_width: dict = field(default_factory=lambda: {"지하철": 1.3, "버스": 1.3})
    base_intercept: float = 35.0
    base_intensity: float = 55.0
    base_noise_sd: float = 4.0
    base_clip: tuple[float, float] = (15.0, 97.0)
    decay_factor: float = 0.5
    curve_noise_sd: float = 3.0
    curve_clip: tuple[float, float] = (8.0, 99.0)

    # 좌석 확률 곡선 — 로지스틱 성장
    seat_base_intercept: float = 100.0
    seat_base_uniform: tuple[float, float] = (0.0, 5.0)
    seat_base_clip: tuple[float, float] = (2.0, 60.0)
    seat_target_uniform: tuple[float, float] = (30.0, 45.0)
    seat_target_min_gap: float = 10.0
    seat_target_clip_hi: float = 96.0
    seat_k: float = 0.18
    seat_t0_fixed: Optional[float] = None  # None이면 아래 uniform 범위에서 뽑음
    seat_t0_uniform: tuple[float, float] = (12.0, 20.0)
    seat_noise_sd: float = 2.5
    seat_clip: tuple[float, float] = (1.0, 98.0)

    # 추천 대기 위치
    door_options: tuple[str, ...] = field(
        default_factory=lambda: tuple(f"{car}-{door}번" for car in range(1, 10) for door in range(1, 5))
    )
    door_suffix: str = " 문 앞"
    bus_options: tuple[str, ...] = (
        "앞문 바로 뒤 좌석 쪽",
        "중간문 근처 2인석 쪽",
        "뒷문 앞 교통약자석 반대편",
        "앞문 쪽 1인석 라인",
    )


# 웹 프로토타입(app.py)의 기존 곡선을 재현하는 프리셋.
WEB_PRESET = PredictionConfig()

# 모바일 데모(mobile_demo.py)의 기존 곡선을 재현하는 프리셋.
MOBILE_PRESET = PredictionConfig(
    rush_center={"지하철": 18.4, "버스": 18.1},
    rush_width={"지하철": 1.35, "버스": 1.55},
    base_intercept=32.0,
    base_intensity=58.0,
    base_noise_sd=4.0,
    base_clip=(12.0, 98.0),
    decay_factor=0.48,
    curve_noise_sd=2.4,
    curve_clip=(8.0, 100.0),
    seat_base_intercept=104.0,
    seat_base_uniform=(7.0, 13.0),
    seat_base_clip=(3.0, 64.0),
    seat_target_uniform=(28.0, 42.0),
    seat_target_min_gap=8.0,
    seat_target_clip_hi=96.0,
    seat_k=0.18,
    seat_t0_fixed=16.0,
    seat_noise_sd=2.0,
    seat_clip=(1.0, 98.0),
    door_options=tuple(f"{car}-{door}번 문" for car in range(1, 10) for door in range(1, 5)),
    door_suffix="",
    bus_options=(
        "앞문 뒤 좌석",
        "중간문 근처",
        "뒷문 앞 2인석",
        "앞쪽 1인석",
    ),
)


def build_prediction(
    config: PredictionConfig,
    transport: str,
    dep_station: str,
    arr_station: str,
    dep_hour: int,
    dep_minute: int,
    real_congestion_pct: Optional[tuple] = None,
    real_line: Optional[str] = None,
) -> tuple[pd.DataFrame, str, bool, Optional[str]]:
    """예측 결과를 만든다.

    반환값: (df, wait_spot, is_real, data_line)
    - df: minutes_offset / time_label / congestion_pct / seat_prob_pct 컬럼
    - wait_spot: 추천 대기 위치 문자열
    - is_real: 혼잡도가 실데이터에서 왔는지 여부
    - data_line: 실데이터일 때의 노선명(없으면 None)
    """
    seed = _seed_from(
        transport,
        dep_station.strip().lower(),
        arr_station.strip().lower(),
        dep_hour,
        dep_minute,
    )
    rng = np.random.default_rng(seed)

    minutes_offset = np.arange(0, MINUTES_OFFSET_END, MINUTES_OFFSET_STEP)
    base_dt = datetime.combine(date.today(), time(dep_hour, dep_minute))
    time_labels = [(base_dt + timedelta(minutes=int(m))).strftime("%H:%M") for m in minutes_offset]

    if real_congestion_pct is not None:
        congestion_curve = np.array(real_congestion_pct, dtype=float)
        base_congestion = float(congestion_curve[0])
        is_real = True
    else:
        hour_decimal = dep_hour + dep_minute / 60
        center = config.rush_center.get(transport, next(iter(config.rush_center.values())))
        width = config.rush_width.get(transport, next(iter(config.rush_width.values())))
        rush_intensity = np.exp(-0.5 * ((hour_decimal - center) / width) ** 2)
        base_congestion = float(
            np.clip(
                config.base_intercept + rush_intensity * config.base_intensity + rng.normal(0, config.base_noise_sd),
                config.base_clip[0],
                config.base_clip[1],
            )
        )
        decay = np.linspace(0, 1, len(minutes_offset))
        congestion_curve = base_congestion * (1 - config.decay_factor * decay) + rng.normal(
            0, config.curve_noise_sd, len(minutes_offset)
        )
        congestion_curve = np.clip(congestion_curve, config.curve_clip[0], config.curve_clip[1])
        is_real = False

    seat_base = float(
        np.clip(
            config.seat_base_intercept
            - min(base_congestion, 100)
            - rng.uniform(*config.seat_base_uniform),
            config.seat_base_clip[0],
            config.seat_base_clip[1],
        )
    )
    seat_target = float(
        np.clip(
            seat_base + rng.uniform(*config.seat_target_uniform),
            seat_base + config.seat_target_min_gap,
            config.seat_target_clip_hi,
        )
    )
    if config.seat_t0_fixed is None:
        t0 = rng.uniform(*config.seat_t0_uniform)
    else:
        t0 = config.seat_t0_fixed
    seat_curve = seat_base + (seat_target - seat_base) / (1 + np.exp(-config.seat_k * (minutes_offset - t0)))
    seat_curve += rng.normal(0, config.seat_noise_sd, len(minutes_offset))
    seat_curve = np.clip(seat_curve, config.seat_clip[0], config.seat_clip[1])

    df = pd.DataFrame(
        {
            "minutes_offset": minutes_offset,
            "time_label": time_labels,
            "congestion_pct": congestion_curve.round(1),
            "seat_prob_pct": seat_curve.round(1),
        }
    )

    if transport == "지하철":
        wait_spot = str(rng.choice(config.door_options)) + config.door_suffix
    else:
        wait_spot = str(rng.choice(config.bus_options))

    return df, wait_spot, is_real, real_line
