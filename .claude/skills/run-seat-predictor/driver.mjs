#!/usr/bin/env node
// Minimal chromium-cli-like REPL for driving the seat-predictor static HTML app.
// Reads one command per line from stdin. Commands:
//   nav <url>                          (use an absolute file:// path or http(s) URL)
//   wait-for text=<substring>          (or a CSS selector)
//   fill <selector> <text...>
//   click <selector>
//   press <key>
//   wait <ms>
//   eval <raw JS>                      (rest of the line, unparsed — for localStorage etc.)
//   screenshot [path]                  (plain full-page screenshot — no Streamlit-specific
//                                        scroll-container workaround needed for this plain
//                                        HTML page, unlike the old Streamlit-era driver)
//   console-errors
//   quit
//
// Usage: node driver.mjs <<'EOF'
// nav file:///absolute/path/to/index.html
// wait-for text=오늘 퇴근길 좌석 예측기
// click #predict-btn
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
  page.on("pageerror", (err) => consoleErrors.push(`pageerror: ${err.message}`));
}

async function handle(line) {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith("#")) return;

  // eval takes the rest of the line completely raw (no tokenizing) since JS
  // snippets routinely contain quotes/spaces that would otherwise collide
  // with the tokenizer below (e.g. localStorage.setItem('a', JSON.stringify({...}))).
  if (trimmed === "eval" || trimmed.startsWith("eval ")) {
    await ensureBrowser();
    const code = trimmed.slice(4).trim();
    const result = await page.evaluate(code);
    console.log("OK eval ->", JSON.stringify(result));
    return;
  }

  // Tokenize on whitespace, but keep 'single' or "double" quoted runs glued
  // together as one token — needed for selectors that embed a space. Quotes
  // embedded mid-token (e.g. input[aria-label='출발역 / 정류장']) are kept
  // as-is since they're valid CSS attribute-selector syntax. But if the
  // WHOLE token is wrapped by one matching quote pair — e.g. a chained
  // selector '[data-testid="x"] >> nth=0' that only needed quoting to
  // survive tokenization — the wrapping quotes are stripped. Playwright
  // treats a selector string that *starts* with a quote char as its `text=`
  // engine shorthand (exact text match), not a real selector, so leaving
  // them on breaks anything that isn't literal text matching.
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
    case "screenshot": {
      const path = arg || "./screenshots/screenshot.png";
      await page.screenshot({ path, fullPage: true });
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
