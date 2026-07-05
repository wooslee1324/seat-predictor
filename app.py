"""오늘 퇴근길 좌석 예측기 — 서울시 공공데이터 기반 프로토타입 (Mock Data)."""

from datetime import date, datetime, time, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="오늘 퇴근길 좌석 예측기",
    page_icon="🚇",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp { background-color: #0f1116; }
    #MainMenu, footer, header { visibility: hidden; }

    .app-title {
        font-size: 2.1rem;
        font-weight: 800;
        background: linear-gradient(90deg, #6C5CE7, #00CEC9);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }
    .app-subtitle {
        color: #9aa0ac;
        font-size: 0.95rem;
        margin-top: 0.2rem;
        margin-bottom: 1.6rem;
    }

    .guide-box {
        border-radius: 16px;
        padding: 22px 26px;
        margin-bottom: 14px;
        background: linear-gradient(135deg, rgba(108,92,231,0.18), rgba(0,206,201,0.10));
        border: 1px solid rgba(108,92,231,0.35);
    }
    .guide-box .headline {
        font-size: 1.05rem;
        font-weight: 700;
        color: #f1f2f6;
        margin-bottom: 6px;
    }
    .tip-box {
        border-radius: 16px;
        padding: 20px 26px;
        margin-bottom: 22px;
        background: linear-gradient(135deg, #00b894, #00cec9);
        color: #063a33;
        font-size: 1.15rem;
        font-weight: 700;
        line-height: 1.5;
        box-shadow: 0 8px 24px rgba(0,206,201,0.25);
    }
    .tip-box.calm {
        background: linear-gradient(135deg, #74b9ff, #a29bfe);
        color: #1a1a3d;
    }

    .metric-card {
        border-radius: 14px;
        padding: 18px 20px;
        background: #171a21;
        border: 1px solid #262b36;
        text-align: center;
    }
    .metric-card .label {
        color: #9aa0ac;
        font-size: 0.85rem;
        margin-bottom: 6px;
    }
    .metric-card .value {
        font-size: 1.7rem;
        font-weight: 800;
        color: #f1f2f6;
    }
    .metric-card .sub {
        font-size: 0.8rem;
        color: #9aa0ac;
        margin-top: 4px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="app-title">🚇 오늘 퇴근길 좌석 예측기</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="app-subtitle">서울시 공공데이터 기반 실시간 혼잡도 · 좌석 확률 예측 (프로토타입 · Mock Data)</div>',
    unsafe_allow_html=True,
)

SUBWAY_DOOR_OPTIONS = [f"{car}-{door}번" for car in range(1, 10) for door in range(1, 5)]
BUS_POSITION_OPTIONS = ["앞문 바로 뒤 좌석 쪽", "중간문 근처 2인석 쪽", "뒷문 앞 교통약자석 반대편", "앞문 쪽 1인석 라인"]


def congestion_level(pct: float):
    if pct >= 80:
        return "매우 혼잡", "🔴"
    if pct >= 60:
        return "혼잡", "🟠"
    if pct >= 40:
        return "보통", "🟡"
    return "여유", "🟢"


@st.cache_data(show_spinner=False)
def generate_prediction(transport: str, dep_station: str, arr_station: str, dep_hour: int, dep_minute: int):
    seed_key = (transport, dep_station.strip().lower(), arr_station.strip().lower(), dep_hour, dep_minute)
    seed = abs(hash(seed_key)) % (2**32)
    rng = np.random.default_rng(seed)

    dep_t = time(dep_hour, dep_minute)
    hour_decimal = dep_hour + dep_minute / 60
    rush_center, rush_width = 18.5, 1.3
    rush_intensity = np.exp(-0.5 * ((hour_decimal - rush_center) / rush_width) ** 2)

    base_congestion_now = float(np.clip(35 + rush_intensity * 55 + rng.normal(0, 4), 15, 97))

    minutes_offset = np.arange(0, 65, 5)
    base_dt = datetime.combine(date.today(), dep_t)
    times = [(base_dt + timedelta(minutes=int(m))).time() for m in minutes_offset]
    time_labels = [t.strftime("%H:%M") for t in times]

    decay = np.linspace(0, 1, len(minutes_offset))
    congestion_curve = base_congestion_now * (1 - 0.5 * decay) + rng.normal(0, 3, len(minutes_offset))
    congestion_curve = np.clip(congestion_curve, 8, 99)

    seat_base = float(np.clip(100 - base_congestion_now - rng.uniform(0, 5), 2, 60))
    seat_target = float(np.clip(seat_base + rng.uniform(30, 45), seat_base + 10, 96))
    k = 0.18
    t0 = rng.uniform(12, 20)
    seat_curve = seat_base + (seat_target - seat_base) / (1 + np.exp(-k * (minutes_offset - t0)))
    seat_curve += rng.normal(0, 2.5, len(minutes_offset))
    seat_curve = np.clip(seat_curve, 1, 98)

    df = pd.DataFrame(
        {
            "minutes_offset": minutes_offset,
            "time_label": time_labels,
            "congestion_pct": congestion_curve.round(1),
            "seat_prob_pct": seat_curve.round(1),
        }
    )

    if transport == "지하철":
        wait_spot = rng.choice(SUBWAY_DOOR_OPTIONS) + " 문 앞"
    else:
        wait_spot = rng.choice(BUS_POSITION_OPTIONS)

    return df, wait_spot


with st.form("route_form"):
    c1, c2, c3, c4 = st.columns([1, 1.4, 1.4, 1])
    with c1:
        transport = st.radio("교통수단", ["지하철", "버스"], horizontal=True)
    with c2:
        dep_station = st.text_input(
            "출발역 / 정류장", value="강남역" if transport == "지하철" else "강남역.강남역사거리"
        )
    with c3:
        arr_station = st.text_input(
            "도착역 / 정류장", value="사당역" if transport == "지하철" else "사당역4번출구"
        )
    with c4:
        dep_time = st.time_input("퇴근(출발) 시간", value=time(18, 30))

    submitted = st.form_submit_button("🔍 좌석 확률 예측하기", use_container_width=True)

if "last_inputs" not in st.session_state or submitted:
    st.session_state.last_inputs = (transport, dep_station, arr_station, dep_time)

transport, dep_station, arr_station, dep_time = st.session_state.last_inputs

df, wait_spot = generate_prediction(transport, dep_station, arr_station, dep_time.hour, dep_time.minute)

current_congestion = df.iloc[0]["congestion_pct"]
current_seat_prob = df.iloc[0]["seat_prob_pct"]
level_label, level_emoji = congestion_level(current_congestion)

future_window = df[(df["minutes_offset"] > 0) & (df["minutes_offset"] <= 30)]
best_row = future_window.loc[future_window["seat_prob_pct"].idxmax()]
best_offset = int(best_row["minutes_offset"])
best_prob = best_row["seat_prob_pct"]
best_time_label = best_row["time_label"]

st.markdown(
    f"""
    <div class="guide-box">
        <div class="headline">{level_emoji} 현재 시간 혼잡도 {current_congestion:.0f}% ({level_label})</div>
        <div style="color:#c8ccd6; font-size:0.9rem;">
            {dep_station} → {arr_station} · {transport} · 기준 시각 {dep_time.strftime('%H:%M')}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if best_prob - current_seat_prob >= 5:
    st.markdown(
        f"""
        <div class="tip-box">
            💡 <b>{best_offset}분 뒤({best_time_label})</b>에 타면 앉아서 갈 확률이
            <b>{best_prob:.0f}%</b>로 올라갑니다.<br/>
            <b>{wait_spot}</b>에서 대기하세요!
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        f"""
        <div class="tip-box calm">
            👍 지금 바로 타는 것이 가장 좋습니다. 현재 앉아서 갈 확률은
            <b>{current_seat_prob:.0f}%</b>입니다.<br/>
            <b>{wait_spot}</b>에서 대기하세요!
        </div>
        """,
        unsafe_allow_html=True,
    )

m1, m2, m3 = st.columns(3)
with m1:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="label">현재 혼잡도</div>
            <div class="value">{current_congestion:.0f}%</div>
            <div class="sub">{level_emoji} {level_label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with m2:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="label">현재 앉아서 갈 확률</div>
            <div class="value">{current_seat_prob:.0f}%</div>
            <div class="sub">지금 탑승 기준</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with m3:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="label">추천 대기 위치</div>
            <div class="value" style="font-size:1.3rem;">{wait_spot}</div>
            <div class="sub">{best_offset}분 뒤 탑승 기준</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.write("")
st.subheader("⏱️ 시간대별 앉아서 갈 확률 변화")

fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=df["minutes_offset"],
        y=df["seat_prob_pct"],
        mode="lines+markers",
        name="앉아서 갈 확률 (%)",
        line=dict(color="#6C5CE7", width=3),
        fill="tozeroy",
        fillcolor="rgba(108,92,231,0.12)",
    )
)
fig.add_trace(
    go.Scatter(
        x=df["minutes_offset"],
        y=df["congestion_pct"],
        mode="lines",
        name="혼잡도 (%)",
        line=dict(color="#FF7675", width=2, dash="dot"),
    )
)
fig.add_vline(
    x=best_offset,
    line_dash="dash",
    line_color="#00cec9",
    annotation_text=f"추천 탑승 · {best_time_label}",
    annotation_font_color="#00cec9",
)

fig.update_layout(
    template="plotly_dark",
    height=430,
    hovermode="x unified",
    margin=dict(l=10, r=10, t=30, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    xaxis=dict(
        title="퇴근 시각",
        tickmode="array",
        tickvals=df["minutes_offset"],
        ticktext=df["time_label"],
    ),
    yaxis=dict(title="확률 / 혼잡도 (%)", range=[0, 100]),
    plot_bgcolor="#0f1116",
    paper_bgcolor="#0f1116",
)

st.plotly_chart(fig, use_container_width=True)

st.caption(
    "⚠️ 본 대시보드는 프로토타입으로, 실제 서울시 공공데이터 API 연동 전 Mock Data를 기반으로 동작합니다."
)
