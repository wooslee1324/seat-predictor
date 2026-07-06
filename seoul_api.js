/**
 * 서울 열린데이터광장 실데이터 연동 (브라우저 전용, 서버 없음).
 *
 * seoul_api.py의 클라이언트 사이드 포트. 일반 <script> 태그로 로드되므로
 * (ES module import/export 아님 — file://에서 모듈 CORS 제한에 걸리는 것을
 * 피하기 위함) 전역 객체 `SeoulAPI`에 함수를 노출한다.
 *
 * - 지하철 혼잡도(subwConfusion): 예측용 실데이터. 시간대별 값을 제공해 좌석
 *   확률 곡선 계산에 직접 쓰인다.
 * - 지하철 역 승하차 인원(CardSubwayStatsNew) / 버스 정류장 승하차 인원
 *   (CardBusStatisticsServiceNew): 둘 다 참고 지표 전용. 역·정류장/노선당
 *   "하루 총합"만 주고 시간대 구분이 없어서 예측 계산에는 쓸 수 없다.
 *
 * 인증키는 커밋되는 소스에 넣지 않는다 — localStorage에서 읽는다
 * (SeoulAPI.getKeys()/setKeys()).
 */
(function (global) {
  "use strict";

  const BASE_URL = "http://openapi.seoul.go.kr:8088";
  const KEYS_STORAGE_KEY = "seatPredictor.seoulApiKeys";
  const CACHE_PREFIX = "seatPredictor.cache.";

  const CONGESTION_SERVICE = "subwConfusion";
  const CONGESTION_PAGE_SIZE = 1000;
  const CONGESTION_CACHE_TTL_MS = 30 * 24 * 60 * 60 * 1000; // 30일 — 분기별 갱신

  const BUS_RIDERSHIP_SERVICE = "CardBusStatisticsServiceNew";
  const BUS_RIDERSHIP_PAGE_SIZE = 1000;
  const BUS_RIDERSHIP_MAX_PAGES = 60; // 안전판 — 하루 전체가 약 41,500건(=42페이지)
  const BUS_RIDERSHIP_CACHE_TTL_MS = 24 * 60 * 60 * 1000; // 하루
  const BUS_RIDERSHIP_DATA_LAG_DAYS = 5; // 문서상 3일이지만 실측상 4일+ 지연되는 경우가 있어 안전 마진
  const BUS_RIDERSHIP_MAX_MATCHED_STOPS = 15;

  const SUBWAY_RIDERSHIP_SERVICE = "CardSubwayStatsNew";
  const SUBWAY_RIDERSHIP_PAGE_SIZE = 1000;
  const SUBWAY_RIDERSHIP_MAX_PAGES = 5; // 하루 전체가 약 618건(1페이지면 충분)
  const SUBWAY_RIDERSHIP_CACHE_TTL_MS = 24 * 60 * 60 * 1000;
  const SUBWAY_RIDERSHIP_DATA_LAG_DAYS = 5;

  // ---------------------------------------------------------------------
  // 인증키 저장 (localStorage — 커밋되는 코드에는 절대 넣지 않음)
  // ---------------------------------------------------------------------

  function getKeys() {
    try {
      return JSON.parse(localStorage.getItem(KEYS_STORAGE_KEY) || "{}");
    } catch (err) {
      return {};
    }
  }

  function setKeys(keys) {
    localStorage.setItem(KEYS_STORAGE_KEY, JSON.stringify(keys || {}));
  }

  // ---------------------------------------------------------------------
  // 캐시 (localStorage, TTL 기반)
  // ---------------------------------------------------------------------

  function cacheGet(key) {
    try {
      const raw = localStorage.getItem(CACHE_PREFIX + key);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (Date.now() - parsed.savedAt > parsed.ttlMs) return null;
      return parsed.data;
    } catch (err) {
      return null;
    }
  }

  function cacheSet(key, data, ttlMs) {
    try {
      localStorage.setItem(
        CACHE_PREFIX + key,
        JSON.stringify({ data, savedAt: Date.now(), ttlMs })
      );
    } catch (err) {
      // localStorage 용량 초과 등은 조용히 무시 — 캐시는 최적화일 뿐 필수 아님
    }
  }

  // ---------------------------------------------------------------------
  // 공통 유틸
  // ---------------------------------------------------------------------

  function rowsFromXml(xmlText) {
    const doc = new DOMParser().parseFromString(xmlText, "application/xml");
    if (doc.querySelector("parsererror")) {
      throw new Error("XML 파싱 실패");
    }
    const codeEl = doc.querySelector("RESULT > CODE");
    const code = codeEl ? codeEl.textContent : null;
    if (code && code !== "INFO-000") {
      const msgEl = doc.querySelector("RESULT > MESSAGE");
      throw new Error(`Seoul API error ${code}: ${msgEl ? msgEl.textContent : ""}`);
    }
    const totalEl = doc.querySelector("list_total_count");
    const total = totalEl ? parseInt(totalEl.textContent, 10) : 0;
    const rowEls = Array.from(doc.querySelectorAll("row"));
    const rows = rowEls.map((rowEl) => {
      const row = {};
      Array.from(rowEl.children).forEach((child) => {
        row[child.tagName] = child.textContent;
      });
      return row;
    });
    return { rows, total };
  }

  async function fetchAllPages(service, authKey, extraPath, pageSize, maxPages) {
    const rows = [];
    let start = 1;
    let page = 0;
    for (;;) {
      const end = start + pageSize - 1;
      const url = `${BASE_URL}/${authKey}/xml/${service}/${start}/${end}/${extraPath}`;
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const text = await resp.text();
      const { rows: pageRows, total } = rowsFromXml(text);
      rows.push(...pageRows);
      page += 1;
      if (pageRows.length === 0 || start + pageRows.length - 1 >= total) break;
      if (maxPages && page >= maxPages) break;
      start += pageSize;
    }
    return rows;
  }

  function todayMinusDays(days) {
    const d = new Date();
    d.setDate(d.getDate() - days);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}${m}${day}`;
  }

  function linearInterp(xs, ys, targets) {
    // xs must be sorted ascending. Returns null if any target is out of range.
    const minX = xs[0];
    const maxX = xs[xs.length - 1];
    const result = [];
    for (const t of targets) {
      if (t < minX || t > maxX) return null;
      let i = 0;
      while (i < xs.length - 1 && xs[i + 1] < t) i++;
      const x0 = xs[i];
      const x1 = xs[Math.min(i + 1, xs.length - 1)];
      const y0 = ys[i];
      const y1 = ys[Math.min(i + 1, xs.length - 1)];
      if (x1 === x0) {
        result.push(y0);
      } else {
        const ratio = (t - x0) / (x1 - x0);
        result.push(y0 + ratio * (y1 - y0));
      }
    }
    return result;
  }

  // ---------------------------------------------------------------------
  // 지하철 혼잡도 (subwConfusion) — 예측용
  // ---------------------------------------------------------------------

  function timeColumns() {
    // TIME0530..TIME2330(당일) + TIME0000/TIME0030(익일)을 분단위 오프셋과 함께 반환.
    const cols = [];
    for (let minute = 330; minute < 1440; minute += 30) {
      const h = String(Math.floor(minute / 60)).padStart(2, "0");
      const m = String(minute % 60).padStart(2, "0");
      cols.push([minute, `TIME${h}${m}`]);
    }
    cols.push([1440, "TIME0000"]);
    cols.push([1470, "TIME0030"]);
    return cols;
  }

  const TIME_COLUMNS = timeColumns();

  async function loadCongestionTable(authKey) {
    const cacheKey = `congestion.${authKey}`;
    const cached = cacheGet(cacheKey);
    if (cached) return cached;

    const rawRows = await fetchAllPages(CONGESTION_SERVICE, authKey, "", CONGESTION_PAGE_SIZE, null);
    const records = [];
    for (const row of rawRows) {
      for (const [minute, col] of TIME_COLUMNS) {
        if (row[col] === undefined) continue;
        records.push({
          station: row.DPTRE_STTN,
          line: row.LINE,
          dow: row.DOW_SE,
          direction: row.UP_DOWN_SE,
          minuteOfDay: minute,
          congestionPct: parseFloat(row[col]),
        });
      }
    }
    cacheSet(cacheKey, records, CONGESTION_CACHE_TTL_MS);
    return records;
  }

  function stationNameVariants(name) {
    // subwConfusion은 '강남'처럼 역 이름에서 '역'을 뗀 표기를 쓰지만 '서울역'처럼
    // '역'이 이름 자체에 포함된 경우도 있어 양쪽 다 시도한다.
    const trimmed = (name || "").trim();
    if (trimmed.endsWith("역") && trimmed.length > 1) {
      return [trimmed, trimmed.slice(0, -1)];
    }
    return [trimmed, trimmed + "역"];
  }

  function displayName(rawName) {
    return rawName.endsWith("역") ? rawName : `${rawName}역`;
  }

  async function getStationOptions(authKey) {
    if (!authKey) return [];
    try {
      const table = await loadCongestionTable(authKey);
      const names = new Set(table.map((r) => displayName(r.station)).filter(Boolean));
      return Array.from(names).sort((a, b) => a.localeCompare(b, "ko"));
    } catch (err) {
      return [];
    }
  }

  async function getRealCongestionSeries(authKey, stationName, depHour, depMinute, minutesOffsets, dow) {
    dow = dow || "평일";
    if (!authKey) return null;
    let table;
    try {
      table = await loadCongestionTable(authKey);
    } catch (err) {
      return null;
    }

    const variants = stationNameVariants(stationName);
    const matched = table.filter((r) => variants.includes(r.station) && r.dow === dow);
    if (matched.length === 0) return null;

    // 역이 여러 노선에 걸쳐 있으면(예: 사당 2/4호선) 결정적으로 첫 노선만 사용.
    // 상/하선(또는 내/외선)은 구분 입력을 받지 않으므로 평균낸다.
    const lines = Array.from(new Set(matched.map((r) => r.line))).sort();
    const lineUsed = lines[0];
    const lineRows = matched.filter((r) => r.line === lineUsed);

    const byMinute = new Map();
    for (const r of lineRows) {
      if (!byMinute.has(r.minuteOfDay)) byMinute.set(r.minuteOfDay, []);
      byMinute.get(r.minuteOfDay).push(r.congestionPct);
    }
    const minutes = Array.from(byMinute.keys()).sort((a, b) => a - b);
    const values = minutes.map((m) => {
      const arr = byMinute.get(m);
      return arr.reduce((a, b) => a + b, 0) / arr.length;
    });

    const baseMinute = depHour * 60 + depMinute;
    const targets = minutesOffsets.map((o) => baseMinute + o);
    const interpolated = linearInterp(minutes, values, targets);
    if (interpolated === null) return null;

    return { congestionPct: interpolated, line: lineUsed, dow };
  }

  // ---------------------------------------------------------------------
  // 버스 정류장 승하차 인원 (CardBusStatisticsServiceNew) — 참고 지표 전용
  // ---------------------------------------------------------------------

  function cleanBusStopName(name) {
    return (name || "").replace(/\([^)]*\)$/, "").trim();
  }

  async function loadBusRidershipTable(authKey, useDate) {
    const cacheKey = `busRidership.${authKey}.${useDate}`;
    const cached = cacheGet(cacheKey);
    if (cached) return cached;

    const rawRows = await fetchAllPages(
      BUS_RIDERSHIP_SERVICE,
      authKey,
      `${useDate}/`,
      BUS_RIDERSHIP_PAGE_SIZE,
      BUS_RIDERSHIP_MAX_PAGES
    );
    const records = rawRows.map((row) => ({
      stopName: row.SBWY_STNS_NM,
      routeName: row.RTE_NM,
      boarding: row.GTON_TNOPE ? parseFloat(row.GTON_TNOPE) : 0,
      alighting: row.GTOFF_TNOPE ? parseFloat(row.GTOFF_TNOPE) : 0,
    }));
    cacheSet(cacheKey, records, BUS_RIDERSHIP_CACHE_TTL_MS);
    return records;
  }

  async function getBusRidershipStat(authKey, stopName, useDate) {
    if (!authKey) return null;
    useDate = useDate || todayMinusDays(BUS_RIDERSHIP_DATA_LAG_DAYS);

    let table;
    try {
      table = await loadBusRidershipTable(authKey, useDate);
    } catch (err) {
      return null;
    }
    if (table.length === 0) return null;

    const tokens = (stopName || "")
      .trim()
      .split(/[.\s]/)
      .filter((t) => t.length >= 2);
    if (tokens.length === 0) return null;

    const matched = table.filter((r) => {
      const clean = cleanBusStopName(r.stopName);
      return tokens.some((t) => clean.includes(t));
    });
    if (matched.length === 0) return null;

    const stopSet = new Set(matched.map((r) => r.stopName));
    if (stopSet.size > BUS_RIDERSHIP_MAX_MATCHED_STOPS) return null;

    const routeSet = new Set(matched.map((r) => r.routeName));
    const boarding = matched.reduce((sum, r) => sum + r.boarding, 0);
    const alighting = matched.reduce((sum, r) => sum + r.alighting, 0);

    return {
      boarding: Math.round(boarding),
      alighting: Math.round(alighting),
      stopCount: stopSet.size,
      routeCount: routeSet.size,
      date: useDate,
    };
  }

  // ---------------------------------------------------------------------
  // 지하철 역 승하차 인원 (CardSubwayStatsNew) — 참고 지표 전용
  // ---------------------------------------------------------------------

  async function loadSubwayRidershipTable(authKey, useDate) {
    const cacheKey = `subwayRidership.${authKey}.${useDate}`;
    const cached = cacheGet(cacheKey);
    if (cached) return cached;

    const rawRows = await fetchAllPages(
      SUBWAY_RIDERSHIP_SERVICE,
      authKey,
      `${useDate}/`,
      SUBWAY_RIDERSHIP_PAGE_SIZE,
      SUBWAY_RIDERSHIP_MAX_PAGES
    );
    const records = rawRows.map((row) => ({
      station: row.SBWY_STNS_NM,
      line: row.SBWY_ROUT_LN_NM,
      boarding: row.GTON_TNOPE ? parseFloat(row.GTON_TNOPE) : 0,
      alighting: row.GTOFF_TNOPE ? parseFloat(row.GTOFF_TNOPE) : 0,
    }));
    cacheSet(cacheKey, records, SUBWAY_RIDERSHIP_CACHE_TTL_MS);
    return records;
  }

  async function getSubwayRidershipStat(authKey, stationName, useDate) {
    if (!authKey) return null;
    useDate = useDate || todayMinusDays(SUBWAY_RIDERSHIP_DATA_LAG_DAYS);

    let table;
    try {
      table = await loadSubwayRidershipTable(authKey, useDate);
    } catch (err) {
      return null;
    }
    if (table.length === 0) return null;

    const variants = stationNameVariants(stationName);
    const matched = table.filter((r) => variants.includes(r.station));
    if (matched.length === 0) return null;

    const lineSet = new Set(matched.map((r) => r.line));
    const boarding = matched.reduce((sum, r) => sum + r.boarding, 0);
    const alighting = matched.reduce((sum, r) => sum + r.alighting, 0);

    return {
      boarding: Math.round(boarding),
      alighting: Math.round(alighting),
      lineCount: lineSet.size,
      date: useDate,
    };
  }

  // ---------------------------------------------------------------------

  global.SeoulAPI = {
    getKeys,
    setKeys,
    getStationOptions,
    getRealCongestionSeries,
    getBusRidershipStat,
    getSubwayRidershipStat,
  };
})(window);
