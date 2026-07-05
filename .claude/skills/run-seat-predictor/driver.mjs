#!/usr/bin/env node
// Minimal chromium-cli-like REPL for driving the seat-predictor Streamlit app.
// Reads one command per line from stdin. Commands:
//   nav <url>
//   wait-for text=<substring>          (or a CSS selector)
//   fill <selector> <text...>
//   click <selector>
//   press <key>
//   wait <ms>
//   resize-to-content                  (see Gotchas in SKILL.md — Streamlit
//                                        scrolls inside [data-testid="stMain"],
//                                        not the document body)
//   screenshot [path]                  (implies resize-to-content first)
//   console-errors
//   quit
//
// Usage: node driver.mjs <<'EOF'
// nav http://localhost:8765
// wait-for text=오늘 퇴근길 좌석 예측기
// screenshot ./screenshots/dashboard.png
// quit
// EOF

import { chromium } from "playwright";

const consoleErrors = [];
let browser;
let page;

async function ensureBrowser() {
  if (browser) return;
  browser = await chromium.launch();
  page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
}

// Streamlit renders the app inside <section data-testid="stMain"> which has
// its own overflow-y scroll — the <body> never grows, so a plain
// `page.screenshot({ fullPage: true })` (and even a locator screenshot on
// stAppViewContainer) only captures one viewport-height slice. Resizing the
// viewport to stMain's real scrollHeight before shooting is what actually
// gets the whole page.
async function resizeToContent() {
  const scrollHeight = await page.evaluate(() => {
    const el = document.querySelector('[data-testid="stMain"]') || document.body;
    return el.scrollHeight;
  });
  await page.setViewportSize({ width: 1440, height: Math.min(scrollHeight + 40, 6000) });
  await page.waitForTimeout(400);
}

async function handle(line) {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith("#")) return;
  // Tokenize on whitespace, but keep 'single' or "double" quoted runs glued
  // together as one token — needed for CSS attribute selectors that embed a
  // space, e.g. input[aria-label='출발역 / 정류장']. Quotes embedded mid-token
  // (that case) are kept as-is since they're valid CSS attribute-selector
  // syntax. But if the WHOLE token is wrapped by one matching quote pair —
  // e.g. a Playwright chained selector like '[data-testid="x"] >> nth=0'
  // that only needed quoting to survive tokenization — the wrapping quotes
  // are stripped. Playwright treats a selector string that *starts* with a
  // quote char as its `text=` engine shorthand, so leaving them on breaks
  // anything that isn't literal text matching.
  const rawTokens = trimmed.match(/(?:[^\s'"]+|'[^']*'|"[^"]*")+/g) || [];
  const tokens = rawTokens.map((t) => {
    const q = t[0];
    return (q === "'" || q === '"') && t.length >= 2 && t[t.length - 1] === q ? t.slice(1, -1) : t;
  });
  const [cmd, ...rest] = tokens;
  const arg = rest.join(" ");
  await ensureBrowser();

  switch (cmd) {
    case "nav":
      await page.goto(arg, { waitUntil: "networkidle", timeout: 30000 });
      console.log("OK nav", arg);
      break;
    case "wait-for":
      if (arg.startsWith("text=")) {
        await page.waitForSelector(`text=${arg.slice(5)}`, { timeout: 20000 });
      } else {
        await page.waitForSelector(arg, { timeout: 20000 });
      }
      console.log("OK wait-for", arg);
      break;
    case "fill": {
      const [selector, ...value] = rest;
      await page.fill(selector, value.join(" "));
      console.log("OK fill", selector);
      break;
    }
    case "click":
      await page.click(arg);
      console.log("OK click", arg);
      break;
    case "press":
      await page.keyboard.press(arg);
      console.log("OK press", arg);
      break;
    case "wait":
      await page.waitForTimeout(parseInt(arg, 10) || 1000);
      console.log("OK wait", arg);
      break;
    case "resize-to-content":
      await resizeToContent();
      console.log("OK resize-to-content");
      break;
    case "screenshot": {
      await resizeToContent();
      const path = arg || "./screenshots/screenshot.png";
      await page.screenshot({ path });
      console.log("OK screenshot", path);
      break;
    }
    case "console-errors":
      console.log("CONSOLE_ERRORS", JSON.stringify(consoleErrors));
      break;
    case "quit":
      await browser.close();
      process.exit(0);
      break;
    default:
      console.log("ERR unknown command:", cmd);
  }
}

// Read all of stdin up front and process commands sequentially. (An
// event-driven `readline` "line" handler races the stream's "close" event —
// with a heredoc, stdin ends right after the last line is delivered, so an
// async handler still awaiting page.screenshot() can get its browser closed
// out from under it by a "close" listener firing in parallel.)
const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const lines = Buffer.concat(chunks).toString("utf8").split("\n");

for (const line of lines) {
  try {
    await handle(line);
  } catch (err) {
    console.log("ERR", err.message);
  }
}
if (browser) await browser.close();
process.exit(0);
