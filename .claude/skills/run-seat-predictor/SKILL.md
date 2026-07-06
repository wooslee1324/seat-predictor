---
name: run-seat-predictor
description: Build, run, and drive the seat-predictor static HTML app. Use when asked to open/run seat-predictor, take a screenshot of its dashboard, or interact with the running UI (route inputs, congestion banner, seat-probability chart, reference stats).
---

This is a static HTML/CSS/JS app (`index.html` at repo root) — **no build step,
no server, no Python**. All Seoul Open Data API calls happen client-side via
`seoul_api.js`, straight from the browser to `openapi.seoul.go.kr`. Drive it
by scripting a headless Chromium session directly against the file via
`.claude/skills/run-seat-predictor/driver.mjs` (a small `chromium-cli`-style
Playwright REPL — this repo doesn't have `chromium-cli` installed, so this
driver stands in for it).

All paths below are relative to the repo root.

## Prerequisites

- Node.js + npm, for the driver only (verified on Node 24.18.0). Nothing else —
  no Python, no `pip install`, no dev server.

## Setup

```bash
cd .claude/skills/run-seat-predictor
npm install
npx playwright install chromium
```

## Run (agent path)

There's no server to start. Point the driver straight at the file with an
**absolute** `file://` path (Playwright's `page.goto` doesn't resolve
relative paths the way a browser address bar would):

```bash
node .claude/skills/run-seat-predictor/driver.mjs <<'EOF'
nav file:///Users/user/Documents/GitHub/seat-predictor/index.html
wait-for text=오늘 퇴근길 좌석 예측기
click #predict-btn
wait 1500
screenshot .claude/skills/run-seat-predictor/screenshots/mock.png
console-errors
quit
EOF
```

Mock mode (no API keys) works with zero setup — this is the default and the
right first check. Screenshots land wherever `screenshot` is told to put
them (relative to the cwd `node` was run from). Use `console-errors` before
trusting a screenshot — a page can render its shell while a fetch/script
throws.

Because it's plain HTML with normal document-body scroll (no Streamlit-style
inner scroll container), `screenshot` is just a regular full-page shot — no
resize-to-content workaround needed.

| command | what it does |
|---|---|
| `nav <url>` | navigate (use an absolute `file://...index.html` path, or an `http(s)://` URL if hosting it) |
| `wait-for text=<substring>` (or a CSS selector) | block until it appears |
| `fill <selector> <text...>` | fill an input |
| `click <selector>` | click |
| `press <key>` | keyboard key, e.g. `Enter` |
| `wait <ms>` | fixed pause — use a long one for the first bus-mode submit (see Gotchas) |
| `eval <raw JS>` | rest of the line, unparsed, run via `page.evaluate` — for things like inspecting `localStorage` |
| `screenshot [path]` | full-page screenshot |
| `console-errors` | prints any `console.error`/uncaught page error seen so far as JSON |
| `quit` | closes the browser and exits |

### Element IDs (this app's DOM, for `fill`/`click`)

| id | what |
|---|---|
| `input[name="transport"][value="지하철"]` / `[value="버스"]` | 교통수단 radio |
| `#dep-station` / `#arr-station` | 출발/도착 (text input with a `<datalist>` — 지하철 모드일 때만 실제 역명으로 채워짐) |
| `#dep-time` | 시간 (`<input type="time">`) |
| `#predict-btn` | 제출 버튼 |
| `#settings-toggle` | "⚙️ 인증키 설정" 토글 버튼 |
| `#congestion-key-input` / `#subway-ridership-key-input` / `#bus-ridership-key-input` | 인증키 입력란 (설정 패널 안, 토글 열어야 보임) |
| `#settings-save-btn` | 인증키 저장 (localStorage) |
| `#guide-box` / `#tip-box` / `#metric-cards` / `#reference-stat` / `#chart` | 결과 영역 |

Transport switching is instant — `교통수단` is a plain `<input type=radio>`
with a `change` listener, not something batched behind a form-submit quirk
(unlike the old Streamlit version this skill used to target). Click the
radio and the station field's type (search-backed `<datalist>` for 지하철,
plain text for 버스) updates immediately, before you even touch the submit
button.

### Exercising the form

Subway (searchable via native `<datalist>` — type-then-match, not a custom
dropdown, so a plain `fill` + partial text works without any virtualization
gotchas):

```
fill #dep-station 잠실역
fill #arr-station 홍대입구역
click #predict-btn
wait 1500
```

Bus (free text, no datalist):

```
click input[name="transport"][value="버스"]
fill #dep-station 강남역10번출구
fill #arr-station 사당역4번출구
click #predict-btn
wait 20000
```

(20s wait for bus — see Gotchas. Subway-only submits need ~1.5s.)

### Testing with real API keys

Keys are never in the repo (see Gotchas in the main project) — inject them
through the visible settings UI, the same path a real user takes:

```
nav file:///Users/user/Documents/GitHub/seat-predictor/index.html
wait-for text=오늘 퇴근길 좌석 예측기
click #settings-toggle
fill #congestion-key-input <your-subway-congestion-key>
fill #subway-ridership-key-input <your-subway-ridership-key>
fill #bus-ridership-key-input <your-bus-ridership-key>
click #settings-save-btn
wait 2000
click #predict-btn
wait 3000
screenshot .claude/skills/run-seat-predictor/screenshots/real.png
console-errors
quit
```

Saving keys clears the cached station-name list and re-fetches it for
whichever transport mode is currently selected, so give it a couple of
seconds after `#settings-save-btn` before submitting.

## Run (human path)

```bash
open index.html   # macOS — or just double-click it in Finder
```

No dev server, no `npm start` — it's a file.

## Test

No automated test suite — the screenshot + `console-errors` flow above is
the verification method.

---

## Gotchas

- **`file://` navigation needs an absolute path.** `nav index.html` will not
  resolve against the shell's `cwd` the way a browser's address bar
  sometimes does — always pass the full `file:///Users/.../index.html` path.
- **Bus mode's ridership reference stat fetches a whole day's data (~41,500
  rows, dozens of paginated API calls) on first use — 10-20s, not the ~1.5s
  a subway submit needs.** Give the first bus-mode `wait` in a script
  20000ms+, or the screenshot captures the page mid-fetch with stale results
  still showing from the previous submit.
- **Real API calls need actual internet access to `openapi.seoul.go.kr`**
  from wherever the driver runs. In a sandboxed/offline environment those
  calls fail (silently, by design — the app falls back to Mock Data/hides
  the reference stat), so only mock-mode behavior is verifiable there.
- **The settings panel is `display:none` until toggled.** `fill`ing
  `#congestion-key-input` before `click #settings-toggle` times out waiting
  for a hidden, non-interactable element.
- **A selector wrapped entirely in one quote pair** — e.g.
  `'[data-testid="x"] >> nth=0'` — must have the wrapping quotes stripped by
  the tokenizer, not left on, or Playwright treats a selector starting with
  a quote character as its `text=` engine (exact text match) and every such
  `fill`/`click` becomes a doomed text search. `driver.mjs` already handles
  this (strips a token's wrapping quotes only when the *whole* token is one
  matched pair; quotes embedded mid-token, like a CSS attribute value, are
  left alone). Mentioned here because this app's plain `id`/attribute
  selectors rarely need it, but it'll bite if you ever reach for `nth=`
  chaining.
- **`readline`'s "line" event races the stream's "close" event with a
  heredoc.** `driver.mjs` reads all of stdin up front and processes commands
  in one sequential loop instead of an event handler, so a still-pending
  `screenshot` isn't cut off when stdin closes right after the last line.

## Troubleshooting

- **`Cannot find module 'playwright'`**: run `node driver.mjs` from this
  skill directory (or otherwise ensure its `node_modules` is on the resolve
  path), or `npm install` here first.
- **`net::ERR_FILE_NOT_FOUND` on `nav`**: the `file://` path isn't absolute,
  or doesn't match the actual repo location on this machine.
- **Reference-stat box never appears even after a long wait**: probably no
  real API key is configured (open the settings panel and check), or there's
  no network path to `openapi.seoul.go.kr` from this environment — both are
  silent no-ops by design, not errors. Check `console-errors` to rule out an
  actual JS exception.
