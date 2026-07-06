/**
 * 오늘 퇴근길 좌석 예측기 — 정적 HTML/JS 버전 (app.py 포트).
 *
 * 서버 없음 — 서울시 API 호출은 전부 브라우저에서 직접(seoul_api.js)
 * 이뤄진다. 인증키는 localStorage에서만 읽고(SeoulAPI.getKeys()) 이
 * 소스에는 절대 하드코딩하지 않는다.
 */
(function () {
  "use strict";

  const SUBWAY_DOOR_OPTIONS = [];
  for (let car = 1; car <= 9; car++) {
    for (let door = 1; door <= 4; door++) SUBWAY_DOOR_OPTIONS.push(`${car}-${door}번`);
  }
  const BUS_POSITION_OPTIONS = [
    "앞문 바로 뒤 좌석 쪽",
    "중간문 근처 2인석 쪽",
    "뒷문 앞 교통약자석 반대편",
    "앞문 쪽 1인석 라인",
  ];

  const MINUTES_OFFSET = [];
  for (let m = 0; m <= 60; m += 5) MINUTES_OFFSET.push(m);

  let stationOptionsCache = null; // 지하철 역명 목록(datalist), 최초 1회만 조회

  // ---------------------------------------------------------------------
  // 시드 고정 난수 (mock 생성용) — Python np.random.default_rng(seed)의
  // 정확한 알고리즘과는 다르지만, "같은 입력이면 같은 mock 결과"라는
  // 성질만 동일하게 재현하면 충분하다.
  // ---------------------------------------------------------------------

  function hashStringToSeed(str) {
    let h = 2166136261 >>> 0; // FNV-1a
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }

  function mulberry32(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function randUniform(rng, a, b) {
    return a + rng() * (b - a);
  }

  function randNormal(rng, mean, std) {
    let u = 0;
    let v = 0;
    while (u === 0) u = rng();
    while (v === 0) v = rng();
    const z = Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
    return mean + z * std;
  }

  function randChoice(rng, arr) {
    return arr[Math.floor(rng() * arr.length)];
  }

  function clamp(v, lo, hi) {
    return Math.min(hi, Math.max(lo, v));
  }

  function round1(v) {
    return Math.round(v * 10) / 10;
  }

  // ---------------------------------------------------------------------
  // 혼잡도 등급
  // ---------------------------------------------------------------------

  function congestionLevel(pct) {
    if (pct >= 80) return { label: "매우 혼잡", emoji: "🔴" };
    if (pct >= 60) return { label: "혼잡", emoji: "🟠" };
    if (pct >= 40) return { label: "보통", emoji: "🟡" };
    return { label: "여유", emoji: "🟢" };
  }

  // ---------------------------------------------------------------------
  // 예측 생성 — real_congestion_pct가 있으면 그 값을 쓰고, 없으면 mock.
  // 좌석 확률은 두 경우 모두 "혼잡도가 낮을수록 좌석 확률이 높다"는 동일한
  // 유도 공식을 쓴다 — 실측값이 아니라 혼잡도로부터 추정한 값.
  // ---------------------------------------------------------------------

  function generatePrediction(transport, depStation, arrStation, depHour, depMinute, realCongestionPct, realLine) {
    const seedKey = [
      transport,
      depStation.trim().toLowerCase(),
      arrStation.trim().toLowerCase(),
      depHour,
      depMinute,
    ].join("|");
    const seed = hashStringToSeed(seedKey);
    const rng = mulberry32(seed);

    const baseDate = new Date();
    baseDate.setHours(depHour, depMinute, 0, 0);
    const timeLabels = MINUTES_OFFSET.map((offset) => {
      const t = new Date(baseDate.getTime() + offset * 60000);
      return `${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}`;
    });

    const isReal = realCongestionPct != null;
    let congestionCurve;
    let baseCongestionNow;

    if (isReal) {
      congestionCurve = realCongestionPct.slice();
      baseCongestionNow = congestionCurve[0];
    } else {
      const hourDecimal = depHour + depMinute / 60;
      const rushCenter = 18.5;
      const rushWidth = 1.3;
      const rushIntensity = Math.exp(-0.5 * Math.pow((hourDecimal - rushCenter) / rushWidth, 2));
      baseCongestionNow = clamp(35 + rushIntensity * 55 + randNormal(rng, 0, 4), 15, 97);
      congestionCurve = MINUTES_OFFSET.map((_, i) => {
        const decay = i / (MINUTES_OFFSET.length - 1);
        return clamp(baseCongestionNow * (1 - 0.5 * decay) + randNormal(rng, 0, 3), 8, 99);
      });
    }

    const seatBase = clamp(100 - Math.min(baseCongestionNow, 100) - randUniform(rng, 0, 5), 2, 60);
    const seatTarget = clamp(seatBase + randUniform(rng, 30, 45), seatBase + 10, 96);
    const k = 0.18;
    const t0 = randUniform(rng, 12, 20);
    const seatCurve = MINUTES_OFFSET.map((m) => {
      let v = seatBase + (seatTarget - seatBase) / (1 + Math.exp(-k * (m - t0)));
      v += randNormal(rng, 0, 2.5);
      return clamp(v, 1, 98);
    });

    const df = MINUTES_OFFSET.map((m, i) => ({
      minutesOffset: m,
      timeLabel: timeLabels[i],
      congestionPct: round1(congestionCurve[i]),
      seatProbPct: round1(seatCurve[i]),
    }));

    const waitSpot =
      transport === "지하철"
        ? `${randChoice(rng, SUBWAY_DOOR_OPTIONS)} 문 앞`
        : randChoice(rng, BUS_POSITION_OPTIONS);

    return { df, waitSpot, isReal, realLine };
  }

  // ---------------------------------------------------------------------
  // DOM 헬퍼
  // ---------------------------------------------------------------------

  function el(id) {
    return document.getElementById(id);
  }

  function fmt(n) {
    return n.toLocaleString("ko-KR");
  }

  // ---------------------------------------------------------------------
  // 교통수단 전환 — 지하철: 역명 datalist 검색 입력, 버스: 자유 텍스트
  // ---------------------------------------------------------------------

  async function updateStationFieldsForTransport(transport) {
    const depInput = el("dep-station");
    const arrInput = el("arr-station");
    const depList = el("dep-station-list");
    const arrList = el("arr-station-list");

    if (transport === "지하철") {
      depInput.value = "강남역";
      arrInput.value = "사당역";
      depInput.placeholder = "예: 강남역";
      arrInput.placeholder = "예: 사당역";
      if (stationOptionsCache === null) {
        const keys = SeoulAPI.getKeys();
        stationOptionsCache = await SeoulAPI.getStationOptions(keys.congestionKey);
      }
      depList.innerHTML = stationOptionsCache.map((s) => `<option value="${s}">`).join("");
      arrList.innerHTML = depList.innerHTML;
    } else {
      depInput.value = "강남역10번출구";
      arrInput.value = "사당역4번출구";
      depInput.placeholder = "예: 강남역10번출구";
      arrInput.placeholder = "예: 사당역4번출구";
      depList.innerHTML = "";
      arrList.innerHTML = "";
    }
  }

  // ---------------------------------------------------------------------
  // 결과 렌더링
  // ---------------------------------------------------------------------

  function renderGuideBox({ transport, depStation, arrStation, depHour, depMinute, currentCongestion, level, isReal, dataLine }) {
    const timeStr = `${String(depHour).padStart(2, "0")}:${String(depMinute).padStart(2, "0")}`;
    let badgeHtml;
    if (isReal) {
      badgeHtml = `<div class="badge badge-real">✅ 서울시 공공데이터 기반 혼잡도 · ${dataLine} · 평일</div>`;
    } else {
      badgeHtml = `<div class="badge badge-mock">⚠️ Mock Data (해당 역의 실데이터를 찾지 못해 추정치 표시 중)</div>`;
    }
    el("guide-box").innerHTML = `
      <div class="headline">${level.emoji} 현재 시간 혼잡도 ${Math.round(currentCongestion)}% (${level.label})</div>
      <div class="sub-line">${depStation} → ${arrStation} · ${transport} · 기준 시각 ${timeStr}</div>
      ${badgeHtml}
    `;
  }

  function renderTipBox({ bestOffset, bestTimeLabel, bestProb, currentSeatProb, waitSpot }) {
    if (bestProb - currentSeatProb >= 5) {
      el("tip-box").className = "tip-box";
      el("tip-box").innerHTML = `
        💡 <b>${bestOffset}분 뒤(${bestTimeLabel})</b>에 타면 앉아서 갈 확률이
        <b>${Math.round(bestProb)}%</b>로 올라갑니다.<br/>
        <b>${waitSpot}</b>에서 대기하세요!
      `;
    } else {
      el("tip-box").className = "tip-box calm";
      el("tip-box").innerHTML = `
        👍 지금 바로 타는 것이 가장 좋습니다. 현재 앉아서 갈 확률은
        <b>${Math.round(currentSeatProb)}%</b>입니다.<br/>
        <b>${waitSpot}</b>에서 대기하세요!
      `;
    }
  }

  function renderMetricCards({ currentCongestion, level, currentSeatProb, waitSpot, bestOffset }) {
    el("metric-cards").innerHTML = `
      <div class="metric-card">
        <div class="label">현재 혼잡도</div>
        <div class="value">${Math.round(currentCongestion)}%</div>
        <div class="sub">${level.emoji} ${level.label}</div>
      </div>
      <div class="metric-card">
        <div class="label">현재 앉아서 갈 확률</div>
        <div class="value">${Math.round(currentSeatProb)}%</div>
        <div class="sub">지금 탑승 기준</div>
      </div>
      <div class="metric-card">
        <div class="label">추천 대기 위치</div>
        <div class="value value-small">${waitSpot}</div>
        <div class="sub">${bestOffset}분 뒤 탑승 기준</div>
      </div>
    `;
  }

  function renderReferenceStat(depStation, ridershipStat, ridershipKind) {
    const box = el("reference-stat");
    if (!ridershipStat) {
      box.innerHTML = "";
      box.style.display = "none";
      return;
    }
    const total = ridershipStat.boarding + ridershipStat.alighting;
    let scopeText;
    if (ridershipKind === "bus") {
      scopeText = `"${depStation}"과(와) 이름이 겹치는 정류장 ${ridershipStat.stopCount}곳 (버스 ${ridershipStat.routeCount}개 노선 합산)`;
    } else {
      scopeText = `"${depStation}" (${ridershipStat.lineCount}개 노선 합산)`;
    }
    box.style.display = "block";
    box.innerHTML = `
      📊 <b>참고 지표</b> — ${ridershipStat.date} 기준 ${scopeText} 하루 총 이용객 약
      <b>${fmt(total)}명</b> (승차 ${fmt(ridershipStat.boarding)} · 하차 ${fmt(ridershipStat.alighting)}).
      혼잡도·좌석 확률 계산에는 반영되지 않는 참고용 수치입니다.
    `;
  }

  function renderChart(df, bestOffset, bestTimeLabel) {
    const x = df.map((r) => r.minutesOffset);
    const seatY = df.map((r) => r.seatProbPct);
    const congY = df.map((r) => r.congestionPct);
    const timeLabels = df.map((r) => r.timeLabel);

    const traceSeat = {
      x,
      y: seatY,
      mode: "lines+markers",
      name: "앉아서 갈 확률 (%)",
      line: { color: "#6C5CE7", width: 3 },
      fill: "tozeroy",
      fillcolor: "rgba(108,92,231,0.12)",
    };
    const traceCong = {
      x,
      y: congY,
      mode: "lines",
      name: "혼잡도 (%)",
      line: { color: "#FF7675", width: 2, dash: "dot" },
    };

    const yUpper = Math.max(100, Math.max(...seatY, ...congY) * 1.1);

    const isNarrow = window.innerWidth <= 640;
    const layout = {
      height: isNarrow ? 320 : 430,
      hovermode: "x unified",
      margin: { l: 55, r: 20, t: 40, b: 60 },
      legend: { orientation: "h", yanchor: "bottom", y: 1.02, xanchor: "right", x: 1, font: { color: "#c8ccd6" } },
      xaxis: {
        title: "퇴근 시각",
        tickmode: "array",
        // 좁은 화면에서는 눈금을 10분 간격으로 줄여 겹침 방지
        tickvals: isNarrow ? x.filter((_, i) => i % 2 === 0) : x,
        ticktext: isNarrow ? timeLabels.filter((_, i) => i % 2 === 0) : timeLabels,
        color: "#9aa0ac",
        gridcolor: "rgba(255,255,255,0.07)",
      },
      yaxis: {
        title: "확률 / 혼잡도 (%)",
        range: [0, yUpper],
        color: "#9aa0ac",
        gridcolor: "rgba(255,255,255,0.07)",
      },
      // 카드 배경(#chart 컨테이너)이 비치도록 투명 처리
      plot_bgcolor: "rgba(0,0,0,0)",
      paper_bgcolor: "rgba(0,0,0,0)",
      font: {
        color: "#c8ccd6",
        family:
          '"Pretendard Variable", Pretendard, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      },
      shapes: [
        {
          type: "line",
          x0: bestOffset,
          x1: bestOffset,
          y0: 0,
          y1: 1,
          yref: "paper",
          line: { color: "#00cec9", dash: "dash" },
        },
      ],
      annotations: [
        {
          x: bestOffset,
          y: 1,
          yref: "paper",
          showarrow: false,
          text: `추천 탑승 · ${bestTimeLabel}`,
          font: { color: "#00cec9" },
          yshift: 12,
        },
      ],
    };

    Plotly.newPlot("chart", [traceSeat, traceCong], layout, { displayModeBar: false, responsive: true });
  }

  function setLoadingMessage(msg) {
    const box = el("loading-message");
    if (msg) {
      box.textContent = msg;
      box.style.display = "block";
    } else {
      box.style.display = "none";
    }
  }

  // ---------------------------------------------------------------------
  // 제출 처리
  // ---------------------------------------------------------------------

  async function handleSubmit(event) {
    event.preventDefault();
    const submitBtn = el("predict-btn");
    submitBtn.disabled = true;

    try {
      const transport = document.querySelector('input[name="transport"]:checked').value;
      const depStation = el("dep-station").value.trim();
      const arrStation = el("arr-station").value.trim();
      const [depHour, depMinute] = el("dep-time").value.split(":").map(Number);

      const keys = SeoulAPI.getKeys();

      let realCongestion = null;
      if (transport === "지하철" && keys.congestionKey) {
        realCongestion = await SeoulAPI.getRealCongestionSeries(
          keys.congestionKey,
          depStation,
          depHour,
          depMinute,
          MINUTES_OFFSET
        );
      }

      let ridershipStat = null;
      let ridershipKind = null;
      if (transport === "버스" && keys.busRidershipKey) {
        setLoadingMessage("버스 정류장 이용객 데이터를 불러오는 중... (하루 한 번만, 최초 조회 시 다소 걸릴 수 있어요)");
        ridershipStat = await SeoulAPI.getBusRidershipStat(keys.busRidershipKey, depStation);
        ridershipKind = "bus";
      } else if (transport === "지하철" && keys.subwayRidershipKey) {
        ridershipStat = await SeoulAPI.getSubwayRidershipStat(keys.subwayRidershipKey, depStation);
        ridershipKind = "subway";
      }
      setLoadingMessage(null);

      const realCongestionPct = realCongestion ? realCongestion.congestionPct : null;
      const realLine = realCongestion ? realCongestion.line : null;

      const { df, waitSpot, isReal, realLine: dataLine } = generatePrediction(
        transport,
        depStation,
        arrStation,
        depHour,
        depMinute,
        realCongestionPct,
        realLine
      );

      const currentCongestion = df[0].congestionPct;
      const currentSeatProb = df[0].seatProbPct;
      const level = congestionLevel(currentCongestion);

      const futureWindow = df.filter((r) => r.minutesOffset > 0 && r.minutesOffset <= 30);
      const bestRow = futureWindow.reduce((best, r) => (r.seatProbPct > best.seatProbPct ? r : best), futureWindow[0]);

      renderGuideBox({ transport, depStation, arrStation, depHour, depMinute, currentCongestion, level, isReal, dataLine });
      renderTipBox({
        bestOffset: bestRow.minutesOffset,
        bestTimeLabel: bestRow.timeLabel,
        bestProb: bestRow.seatProbPct,
        currentSeatProb,
        waitSpot,
      });
      renderMetricCards({ currentCongestion, level, currentSeatProb, waitSpot, bestOffset: bestRow.minutesOffset });
      renderReferenceStat(depStation, ridershipStat, ridershipKind);

      // Plotly가 컨테이너 폭을 측정할 수 있도록 결과 영역을 먼저 보이게 한다
      // (display:none 상태로 그리면 기본 폭 700px로 렌더링돼 모바일에서 넘침)
      el("results").style.display = "block";
      renderChart(df, bestRow.minutesOffset, bestRow.timeLabel);
    } finally {
      submitBtn.disabled = false;
    }
  }

  // ---------------------------------------------------------------------
  // 설정 패널 (인증키 — localStorage에만 저장, 커밋되는 코드에는 없음)
  // ---------------------------------------------------------------------

  function initSettingsPanel() {
    const keys = SeoulAPI.getKeys();
    el("congestion-key-input").value = keys.congestionKey || "";
    el("subway-ridership-key-input").value = keys.subwayRidershipKey || "";
    el("bus-ridership-key-input").value = keys.busRidershipKey || "";

    el("settings-toggle").addEventListener("click", () => {
      const panel = el("settings-panel");
      panel.style.display = panel.style.display === "none" ? "block" : "none";
    });

    el("settings-save-btn").addEventListener("click", async () => {
      SeoulAPI.setKeys({
        congestionKey: el("congestion-key-input").value.trim(),
        subwayRidershipKey: el("subway-ridership-key-input").value.trim(),
        busRidershipKey: el("bus-ridership-key-input").value.trim(),
      });
      stationOptionsCache = null; // 키가 바뀌었을 수 있으니 역명 목록 다시 조회
      const status = el("settings-status");
      status.textContent = "저장했습니다.";
      setTimeout(() => (status.textContent = ""), 2500);
      const transport = document.querySelector('input[name="transport"]:checked').value;
      await updateStationFieldsForTransport(transport);
    });
  }

  // ---------------------------------------------------------------------
  // 초기화
  // ---------------------------------------------------------------------

  document.addEventListener("DOMContentLoaded", () => {
    initSettingsPanel();

    document.querySelectorAll('input[name="transport"]').forEach((radio) => {
      radio.addEventListener("change", (e) => updateStationFieldsForTransport(e.target.value));
    });
    updateStationFieldsForTransport("지하철");

    el("route-form").addEventListener("submit", handleSubmit);
  });
})();
