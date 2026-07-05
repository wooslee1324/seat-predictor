---
name: run-seat-predictor
description: Build, run, and drive the seat-predictor Streamlit app. Use when asked to start seat-predictor, launch the app, take a screenshot of its dashboard, or interact with the running UI (route inputs, congestion banner, seat-probability chart).
---

This is a Streamlit dashboard (`app.py` at repo root) with no build step.
Drive it by starting the Streamlit server, then scripting a headless
Chromium session against it via `.claude/skills/run-seat-predictor/driver.mjs`
(a small `chromium-cli`-style Playwright REPL — this repo doesn't have
`chromium-cli` installed, so this driver stands in for it).

All paths below are relative to the repo root.

## Prerequisites

- Python 3.13 (any recent Python 3 with `venv` works; verified on 3.13.2).
- Node.js + npm, for the driver only (verified on Node 24.18.0).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

```bash
cd .claude/skills/run-seat-predictor
npm install
npx playwright install chromium
```

## Run (agent path)

1. Start the Streamlit server in the background and wait for the port:

```bash
source .venv/bin/activate
nohup streamlit run app.py --server.headless true --server.port 8765 > /tmp/streamlit.log 2>&1 &
echo $! > /tmp/streamlit.pid
for i in $(seq 1 30); do
  curl -sf http://localhost:8765 >/dev/null && echo SERVER_UP && break
  sleep 1
done
```

(macOS has no `timeout` binary by default — this is why the wait above is a
plain `for` loop with `curl`, not `timeout curl ...`.)

2. Drive it by piping commands into the driver:

```bash
node .claude/skills/run-seat-predictor/driver.mjs <<'EOF'
nav http://localhost:8765
wait-for text=오늘 퇴근길 좌석 예측기
wait 2500
screenshot .claude/skills/run-seat-predictor/screenshots/dashboard.png
console-errors
quit
EOF
```

Screenshots land wherever you tell `screenshot` to put them (relative to
the cwd `node` was run from). Use `console-errors` before trusting a
screenshot — a Streamlit page can render its shell while a callback throws.

3. Stop the server:

```bash
kill $(cat /tmp/streamlit.pid) 2>/dev/null; pkill -f "streamlit run app.py"
```

| command | what it does |
|---|---|
| `nav <url>` | navigate |
| `wait-for text=<substring>` (or a CSS selector) | block until it appears |
| `fill <selector> <text...>` | fill an input |
| `click <selector>` | click |
| `press <key>` | keyboard key, e.g. `Enter` |
| `wait <ms>` | fixed pause — use for Plotly's draw animation |
| `resize-to-content` | see Gotchas — resizes the viewport to `stMain`'s real height |
| `screenshot [path]` | implies `resize-to-content` first, then shoots |
| `console-errors` | prints any `console.error` seen so far as JSON |
| `quit` | closes the browser and exits |

To exercise the form (pick a different route/time before shooting), insert
before the `screenshot` line:

```
fill input[aria-label='출발역 / 정류장'] 신도림역
fill input[aria-label='도착역 / 정류장'] 홍대입구역
click button:has-text("좌석 확률 예측하기")
wait 2500
```

(Use single quotes around the attribute value, not double — the driver's
tokenizer glues a quoted run together to survive the embedded space, and
double-quoting here would nest inside `button:has-text("...")` elsewhere
in the same script. Single quotes for selectors, double quotes for
Playwright's own `:has-text(...)` syntax.)

## Run (human path)

```bash
source .venv/bin/activate
streamlit run app.py   # opens http://localhost:8501 — Ctrl-C to stop
```

## Test

No automated test suite exists yet — verification is the screenshot flow
above plus `console-errors` returning `[]`.

---

## Gotchas

- **Streamlit's content scrolls inside `<section data-testid="stMain">`,
  not the document body.** Both `page.screenshot({ fullPage: true })` and
  even a locator screenshot on `[data-testid="stAppViewContainer"]` only
  capture one viewport-height slice — the chart's x-axis and the footer
  caption get silently cropped off. The fix (already in `driver.mjs`'s
  `resize-to-content`): read `stMain.scrollHeight` and
  `page.setViewportSize()` to that height before shooting.
- **`requirements.txt` must not pin `pandas==2.2.2` on Python 3.13.** That
  version has no prebuilt wheel for cp313, so `pip install` silently falls
  back to compiling pandas from source via meson/ninja — it *works*, but
  takes 10+ minutes and looks hung. The committed `requirements.txt` uses
  `pandas>=2.2.3` (has cp313 wheels) instead. If you re-pin exact versions,
  check wheel availability for the Python version in use first.
- **Selectors with a space (Streamlit's `aria-label`s are Korean phrases
  with spaces, e.g. `출발역 / 정류장`) break naive space-splitting of the
  command line.** `driver.mjs` tokenizes with a small regex that glues a
  `'single'` or `"double"` quoted run together as one token. Wrap the
  attribute value in single quotes — `input[aria-label='출발역 / 정류장']`
  — and reserve double quotes for Playwright's own `:has-text("...")`
  syntax so the two don't nest inside a single unescaped token.
- **The `readline` "line" event races the stream's "close" event.** An
  earlier version of `driver.mjs` used `readline.createInterface` and
  called `browser.close()` in the `close` handler — with a heredoc, stdin
  ends right after the last line is delivered, so `close` could fire while
  an async command (e.g. `screenshot`) was still awaiting
  `page.screenshot()`, closing the browser out from under it
  (`Target page, context or browser has been closed`). Fixed by reading
  all of stdin up front and processing commands in a single sequential
  `for` loop instead of an event handler.

## Troubleshooting

- **`Cannot find module 'playwright'`**: you ran `node driver.mjs` from
  somewhere other than this skill directory, or skipped `npm install`
  here. `cd .claude/skills/run-seat-predictor && npm install`.
- **`Target page, context or browser has been closed`**: see the
  `readline`/`close` gotcha above — make sure you're on the current
  `driver.mjs` (sequential stdin read, not a `readline` "line"/"close"
  handler pair).
- **Chart looks cut off in the screenshot** (missing x-axis labels /
  footer caption): the `screenshot` command didn't resize first — use
  `screenshot`, not a raw Playwright call, or run `resize-to-content`
  immediately before it.
