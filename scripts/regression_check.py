"""회귀 검증: core 로 통합한 예측 로직이 리팩터링 이전 결과와 동일한지 확인.

- MOBILE_PRESET: 기존 mobile_demo.py._build_prediction 과 완전 동일해야 한다.
- WEB_PRESET: 결정론적(같은 입력이면 같은 출력)이어야 한다.
검증에 실패하면 비정상 종료(exit 1)한다. GitHub 반영 전에 실행해 확인한다.
"""

import sys
from datetime import date, datetime, time, timedelta
from hashlib import sha256
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.prediction import MOBILE_PRESET, WEB_PRESET, build_prediction  # noqa: E402


# --- 리팩터링 이전 mobile_demo.py._build_prediction 을 그대로 복제한 기준 구현 ---
_OLD_DOOR = [f"{car}-{door}번 문" for car in range(1, 10) for door in range(1, 5)]
_OLD_BUS = ["앞문 뒤 좌석", "중간문 근처", "뒷문 앞 2인석", "앞쪽 1인석"]


def _old_seed(*parts):
    digest = sha256("|".join(map(str, parts)).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % (2**32)


def old_mobile_build(transport, dep, arr, hour, minute, real=None, line=None):
    seed = _old_seed(transport, dep.lower(), arr.lower(), hour, minute)
    rng = np.random.default_rng(seed)
    minutes_offset = np.arange(0, 65, 5)
    base_dt = datetime.combine(date.today(), time(hour, minute))
    labels = [(base_dt + timedelta(minutes=int(m))).strftime("%H:%M") for m in minutes_offset]
    if real is not None:
        curve = np.array(real, dtype=float)
        base = float(curve[0])
        is_real = True
    else:
        hd = hour + minute / 60
        rc = 18.4 if transport == "지하철" else 18.1
        rw = 1.35 if transport == "지하철" else 1.55
        intensity = np.exp(-0.5 * ((hd - rc) / rw) ** 2)
        base = float(np.clip(32 + intensity * 58 + rng.normal(0, 4), 12, 98))
        decay = np.linspace(0, 1, len(minutes_offset))
        curve = base * (1 - 0.48 * decay) + rng.normal(0, 2.4, len(minutes_offset))
        curve = np.clip(curve, 8, 100)
        is_real = False
    seat_base = float(np.clip(104 - min(base, 100) - rng.uniform(7, 13), 3, 64))
    seat_target = float(np.clip(seat_base + rng.uniform(28, 42), seat_base + 8, 96))
    seat = seat_base + (seat_target - seat_base) / (1 + np.exp(-0.18 * (minutes_offset - 16)))
    seat += rng.normal(0, 2.0, len(minutes_offset))
    seat = np.clip(seat, 1, 98)
    df = pd.DataFrame(
        {
            "minutes_offset": minutes_offset,
            "time_label": labels,
            "congestion_pct": curve.round(1),
            "seat_prob_pct": seat.round(1),
        }
    )
    wait = rng.choice(_OLD_DOOR if transport == "지하철" else _OLD_BUS)
    return df, str(wait), is_real, line


CASES = [
    ("지하철", "강남역", "사당역", 18, 30, None),
    ("지하철", "잠실역", "강남역", 22, 0, None),
    ("버스", "강남역10번출구", "사당역4번출구", 18, 30, None),
    ("버스", "홍대입구역", "신도림역", 8, 15, None),
    ("지하철", "강남역", "사당역", 18, 30, (72.0, 70.1, 66.5, 60.2, 55.0, 50.0, 45.0, 40.0, 38.0, 35.0, 33.0, 31.0, 30.0)),
]

failures = 0
for transport, dep, arr, hh, mm, real in CASES:
    old = old_mobile_build(transport, dep, arr, hh, mm, real)
    new = build_prediction(MOBILE_PRESET, transport, dep, arr, hh, mm, real)
    same_df = old[0].equals(new[0])
    same_wait = old[1] == new[1]
    same_flags = old[2] == new[2]
    ok = same_df and same_wait and same_flags
    print(f"[{'OK' if ok else 'FAIL'}] MOBILE {transport} {dep}->{arr} {hh:02d}:{mm:02d} "
          f"real={real is not None} | df={same_df} wait={same_wait}({new[1]})")
    if not ok:
        failures += 1

# WEB_PRESET 결정론 확인 (같은 입력 두 번 -> 동일)
for transport, dep, arr, hh, mm, real in CASES:
    a = build_prediction(WEB_PRESET, transport, dep, arr, hh, mm, real)
    b = build_prediction(WEB_PRESET, transport, dep, arr, hh, mm, real)
    ok = a[0].equals(b[0]) and a[1] == b[1]
    print(f"[{'OK' if ok else 'FAIL'}] WEB 결정론 {transport} {dep}->{arr} {hh:02d}:{mm:02d} | {ok} wait={a[1]}")
    if not ok:
        failures += 1

print()
if failures:
    print(f"검증 실패: {failures}건")
    sys.exit(1)
print("모든 검증 통과 — 기존 모바일 출력과 완전 일치, 웹 예측 결정론 확인")
