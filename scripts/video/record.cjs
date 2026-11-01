/* Drives the real app in Microsoft Edge, narrating as it goes, and records screencast frames.
   Usage: node record.cjs <work dir> <base url> <db path> <python> [--shots-only]
   Set PLAYWRIGHT_CORE to the path of the playwright-core package. */
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { chromium } = require(process.env.PLAYWRIGHT_CORE || "playwright-core");

const [work, base, dbPath, python] = process.argv.slice(2);
const shotsOnly = process.argv.includes("--shots-only");
const EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const ORACLE = path.join(__dirname, "oracle.py");
const segments = JSON.parse(fs.readFileSync(path.join(work, "segments.json"), "utf8"));
const framesDir = path.join(work, "frames");
const shotsDir = path.join(work, "shots");
fs.rmSync(framesDir, { recursive: true, force: true });
fs.mkdirSync(framesDir, { recursive: true });
fs.mkdirSync(shotsDir, { recursive: true });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const rnd = (a, b) => a + Math.random() * (b - a);

(async () => {
  const browser = await chromium.launch({ executablePath: EDGE, headless: true, args: ["--force-device-scale-factor=1", "--hide-scrollbars"] });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  page.on("pageerror", (e) => console.error("PAGE ERROR:", e.message));
  page.on("console", (m) => { if (m.type() === "error") console.error("CONSOLE:", m.text()); });

  /* Capture trial ids so the bot can answer. */
  let currentTrial = null;
  page.on("response", async (res) => {
    if (!res.url().includes("/api/session")) return;
    try {
      const j = await res.json();
      if (j.trial_id) currentTrial = j.trial_id;
    } catch { /* non-JSON */ }
  });

  /* Screencast. */
  const frames = [];
  let cdp = null;
  async function startCast() {
    cdp = await context.newCDPSession(page);
    cdp.on("Page.screencastFrame", async (f) => {
      const name = `f${String(frames.length).padStart(6, "0")}.jpg`;
      fs.writeFileSync(path.join(framesDir, name), Buffer.from(f.data, "base64"));
      frames.push({ name, t: f.metadata.timestamp });
      try { await cdp.send("Page.screencastFrameAck", { sessionId: f.sessionId }); } catch { /* closing */ }
    });
    await cdp.send("Page.startScreencast", { format: "jpeg", quality: 82, maxWidth: 1440, maxHeight: 900, everyNthFrame: 1 });
  }

  /* Burned-in captions, added to the page so they appear in the frames. */
  const showCaption = (text) => page.evaluate((t) => {
    let c = document.getElementById("__cap");
    if (!c) {
      c = document.createElement("div");
      c.id = "__cap";
      c.style.cssText = "position:fixed;left:50%;bottom:22px;transform:translateX(-50%);max-width:1040px;width:max-content;background:rgba(11,34,57,.92);color:#fff;padding:9px 18px;border-radius:8px;font:500 19px/1.35 'Segoe UI',sans-serif;z-index:99999;text-align:center;pointer-events:none";
      document.body.appendChild(c);
    }
    c.textContent = t;
    c.style.display = t ? "block" : "none";
  }, text).catch(() => {});

  const sentences = (t) => t.match(/[^.?!]+[.?!]+/g).map((s) => s.trim());
  const timeline = [];
  const t0 = () => Date.now();
  let startedAt = null;

  async function seg(id, actions) {
    const s = segments.find((x) => x.id === id);
    const start = t0();
    timeline.push({ id, wav: s.wav, seconds: s.seconds, at: (start - startedAt) / 1000 });
    /* Captions change sentence by sentence, timed by share of characters. */
    const parts = sentences(s.text);
    const total = parts.reduce((a, b) => a + b.length, 0);
    let stop = false;
    const capLoop = (async () => {
      for (const p of parts) {
        if (stop) return;
        await showCaption(p);
        await sleep((p.length / total) * s.seconds * 1000);
      }
    })();
    /* Keep the caption on screen across navigations. */
    const keep = setInterval(() => { page.evaluate(() => { const c = document.getElementById("__cap"); return !!c; }).then((has) => { if (!has && !stop) showCaption(parts[0]); }).catch(() => {}); }, 400);
    await actions(s.seconds * 1000);
    const left = s.seconds * 1000 + 450 - (t0() - start);
    if (left > 0) await sleep(left);
    stop = true;
    clearInterval(keep);
    await capLoop;
    await showCaption("");
  }

  const shot = async (name, opts = {}) => {
    await page.evaluate(() => { const c = document.getElementById("__cap"); if (c) c.style.visibility = "hidden"; }).catch(() => {});
    await page.screenshot({ path: path.join(shotsDir, name + ".png"), ...opts });
    await page.evaluate(() => { const c = document.getElementById("__cap"); if (c) c.style.visibility = "visible"; }).catch(() => {});
  };
  const click = async (sel) => { const el = await page.waitForSelector(sel, { timeout: 8000 }); await el.scrollIntoViewIfNeeded(); await el.click(); };
  const smoothTo = (sel) => page.evaluate((s) => { const e = document.querySelector(s); if (e) window.scrollTo({ top: e.getBoundingClientRect().top + scrollY - 20, behavior: "smooth" }); }, sel);
  const gotoHash = (h) => page.evaluate((x) => { location.hash = x; }, h);
  const answerOf = () => JSON.parse(execFileSync(python, ["-I", ORACLE, dbPath, String(currentTrial)]).toString());

  /* One bot response to whatever item is on screen. Accuracy is a plausible 80%. */
  async function respond(accuracy = 0.8, thinkMs = [500, 1000]) {
    await page.waitForSelector("#stage[data-kind]");
    const kind = await page.$eval("#stage", (s) => s.dataset.kind);
    const answer = answerOf();
    const right = Math.random() < accuracy;
    await sleep(rnd(...thinkMs));
    if (kind === "choice") {
      /* The item may time out while the bot thinks, as it can for a person. That is fine. */
      const keys = await page.$$eval(".choices .btn", (b) => b.map((x) => x.dataset.key));
      const k = right ? answer : keys.find((x) => x !== answer);
      if (k && keys.includes(k)) await page.click(`.choices .btn[data-key="${k}"]`, { timeout: 800 }).catch(() => {});
    } else if (kind === "go_nogo") {
      if (answer === "go" ? right : !right) await page.click(".stage .btn.big", { timeout: 800 }).catch(() => {});
      else await sleep(1000);
    } else if (kind === "mcq") {
      const values = await page.$$eval(".option", (o) => o.map((x) => x.dataset.value));
      const v = right ? String(answer) : values.find((x) => x !== String(answer));
      const index = values.indexOf(v);
      await (await page.$$(".option"))[index < 0 ? 0 : index].click();
      await page.waitForSelector("[data-conf]", { timeout: 3000 }).catch(() => {});
      await sleep(rnd(500, 900));
      const confs = await page.$$("[data-conf]");
      if (confs.length) await confs[right ? (Math.random() < 0.6 ? 2 : 1) : Math.floor(Math.random() * 2)].click();
    }
    await sleep(120);
  }
  async function waitNextItem() {
    /* Wait for feedback to clear and a new item, or for the session to end. */
    for (let i = 0; i < 60; i++) {
      await sleep(100);
      const ready = await page.evaluate(() => {
        const s = document.getElementById("stage");
        if (!s) return "gone";
        if (document.getElementById("go")) return "intro";
        if (document.getElementById("est-go")) return "est";
        if (s.querySelector(".choices .btn, .btn.big, .option, .recall-input, textarea, .word-input")) return "item";
        return "wait";
      });
      if (ready !== "wait") return ready;
    }
    return "timeout";
  }

  /* ------------ the walkthrough ------------ */
  await page.goto(base, { waitUntil: "networkidle" });
  await page.setContent(`<!doctype html><html><head><title>AI4Brain</title></head><body style="margin:0;background:#0b2239;color:#fff;font-family:Bahnschrift,'Segoe UI',sans-serif;display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;gap:14px">
      <svg width="82" height="82" viewBox="0 0 32 32"><polygon points="16,2 29,10 29,23 16,30 3,23 3,10" fill="#1468B8"/><polygon points="16,9 23,13 23,20 16,24 9,20 9,13" fill="#E46F1F"/></svg>
      <div style="font-size:72px;font-weight:600">AI4Brain</div>
      <div style="font-size:30px;color:#bcd3e6">Cognitive growth agent: CISTAC 1.0 challenge entry</div>
      <div style="font-size:21px;color:#8fb0ca;margin-top:6px">Demo recorded from the running app. A simulated learner supplies the sample data.</div></body></html>`);
  await startCast();
  startedAt = t0();

  await seg("title", async () => {});
  await page.goto(base, { waitUntil: "networkidle" });
  await page.waitForSelector("#start");

  await seg("consent", async (ms) => {
    await sleep(ms * 0.3);
    await page.check("#c-store");
    await sleep(ms * 0.2);
    await shot("welcome");
  });
  await click("#start");
  await page.waitForSelector(".practice-list");

  await seg("practice", async (ms) => {
    await sleep(ms * 0.6);
    await page.click('[data-mood="energised"]');
    await sleep(ms * 0.1);
    await shot("practice_empty");
  });

  await page.click('[data-start="attention"][data-mode="assess"]');
  await seg("attention", async (ms) => {
    const end = t0() + ms - 1000;
    await page.waitForSelector("#go");
    await sleep(1400);
    await page.click("#go");
    let n = 0;
    while (t0() < end) {
      await respond(0.85, [200, 420]);
      n += 1;
      const r = await waitNextItem();
      if (r === "est" || r === "gone") break;
      if (r === "intro") { await sleep(600); await page.click("#go"); }
      if (n === 4) await shot("session_flanker");
    }
  });
  /* End this session and move on to a reasoning one. */
  await page.click("#stop").catch(() => {});
  await page.waitForSelector("#est-skip", { timeout: 5000 }).catch(() => {});
  await page.click("#est-skip").catch(() => {});
  await page.waitForSelector(".changes", { timeout: 6000 }).catch(() => {});
  await gotoHash("#/session/logical_reasoning/assess");

  await seg("reasoning", async (ms) => {
    const end = t0() + ms - 900;
    await page.waitForSelector("#go");
    await sleep(1000);
    await page.click("#go");
    let first = true;
    while (t0() < end) {
      await page.waitForSelector("#stage[data-kind]");
      await respond(0.75, [1400, 2200]);
      if (first) { first = false; }
      const r = await waitNextItem();
      if (r === "est" || r === "gone") break;
      if (r === "intro") { await sleep(500); await page.click("#go"); }
    }
    await shot("session_mcq");
  });

  await seg("summary", async (ms) => {
    await page.click("#stop").catch(() => {});
    await page.waitForSelector("#est-go", { timeout: 5000 }).catch(() => {});
    await sleep(ms * 0.12);
    await page.click("#est-go").catch(() => {});
    await page.waitForSelector(".changes", { timeout: 6000 }).catch(() => {});
    await sleep(ms * 0.3);
    await shot("summary");
    await smoothTo(".changes");
    await sleep(ms * 0.2);
    await page.evaluate(() => window.scrollBy({ top: 420, behavior: "smooth" }));
  });

  /* Switch to the seeded sample profile. */
  const demoId = await page.evaluate(async () => (await (await fetch("/api/demo", { method: "POST" })).json()).profile_id);
  await page.evaluate((id) => { localStorage.setItem("profile", id); location.hash = "#/twin"; location.reload(); }, demoId);
  await page.waitForSelector("#radar svg");

  await seg("twin", async (ms) => {
    await shot("twin");
    await sleep(ms * 0.42);
    const max = await page.$eval("#scrub", (s) => +s.max);
    const steps = 42;
    for (let i = 0; i <= steps; i++) {
      await page.$eval("#scrub", (s, v) => { s.value = v; s.dispatchEvent(new Event("input")); }, Math.round((i / steps) * max));
      await sleep((ms * 0.48) / steps);
    }
    await shot("twin_history");
  });

  await seg("insights", async (ms) => {
    await smoothTo(".insights");
    await sleep(ms * 0.3);
    await page.evaluate(() => { document.querySelector("details.why:not(.none) summary"); const all = document.querySelectorAll(".insight details.why"); if (all[0]) all[0].open = true; });
    await sleep(ms * 0.15);
    await shot("insights");
    await page.evaluate(() => { const all = document.querySelectorAll(".insight details.why"); if (all[1]) all[1].open = true; });
  });

  await seg("curves", async (ms) => {
    await smoothTo("#curves");
    await sleep(ms * 0.5);
    await shot("curves");
  });

  await gotoHash("#/skill/cognitive_flexibility");
  await page.waitForSelector("#big-curve");
  await seg("skill", async (ms) => {
    await sleep(ms * 0.22);
    await shot("skill");
    await smoothTo("table.data");
    await sleep(ms * 0.32);
    await smoothTo(".docs-grid");
    await sleep(ms * 0.2);
    await shot("skill_docs");
  });

  await gotoHash("#/twin");
  await page.waitForSelector("#heat .heat");
  await seg("heat", async (ms) => {
    await smoothTo("#heat");
    await sleep(ms * 0.2);
    await shot("heat_week");
    await page.click("#ht-level");
    await sleep(ms * 0.2);
    await shot("heat_level");
    await smoothTo("#goal-list");
  });

  await gotoHash("#/plan");
  await page.waitForSelector(".today");
  await seg("plan", async (ms) => {
    await sleep(ms * 0.2);
    await shot("plan");
    await page.evaluate(() => { const h = [...document.querySelectorAll("h2")].find((x) => x.textContent.startsWith("How priorities")); window.scrollTo({ top: h.getBoundingClientRect().top + scrollY - 20, behavior: "smooth" }); });
    await sleep(ms * 0.38);
    await shot("plan_priority");
    await page.evaluate(() => window.scrollBy({ top: 700, behavior: "smooth" }));
  });

  await gotoHash("#/coach");
  await page.waitForSelector("#chat-in");
  await seg("coach", async (ms) => {
    const ask = async (q) => {
      await page.fill("#chat-in", "");
      await page.type("#chat-in", q, { delay: 22 });
      await page.keyboard.press("Enter");
      await sleep(1100);
    };
    await sleep(500);
    await ask("What should I practise next?");
    await sleep(ms * 0.12);
    await ask("Do these scores mean I have ADHD?");
    await sleep(ms * 0.2);
    await shot("coach_safety");
    await ask("Why did my spatial reasoning change?");
    await page.evaluate(() => { const d = document.querySelectorAll(".msg details.why"); if (d.length) d[d.length - 1].open = true; const l = document.getElementById("log"); l.scrollTop = l.scrollHeight; });
    await sleep(ms * 0.1);
    await shot("coach");
  });

  /* Play the first unplayed round in the lab. */
  await gotoHash("#/lab");
  await page.waitForSelector("#round .lab-step");
  await seg("lab", async (ms) => {
    await sleep(ms * 0.1);
    await shot("lab_start");
    await page.click("[data-own]");
    await sleep(ms * 0.13);
    const flawed = await page.evaluate(() => {
      const idx = [...document.querySelectorAll(".ai-step .txt")].findIndex((t) => /Older candidates|proves method|Room B works|proved daily|Transport: 3|means gross/.test(t.textContent));
      return idx < 0 ? 0 : idx;
    });
    await page.click(`[data-flag="${flawed}"]`);
    await sleep(ms * 0.14);
    await shot("lab_round");
    await page.click("#refine");
    await sleep(ms * 0.16);
    const resp = await page.$("[data-resp]");
    if (resp) {
      const options = await page.$$eval("[data-resp]", (e) => e.map((x) => x.textContent));
      const okIndex = options.findIndex((t) => /Remove names|Work it out myself|Early data/.test(t));
      await page.click(`[data-resp="${okIndex < 0 ? 0 : okIndex}"]`);
    }
  });
  await seg("score", async (ms) => {
    const finals = await page.$$eval("[data-final]", (e) => e.map((x) => x.textContent));
    const pick = finals.findIndex((t) => /Remove personal|Find another|enough evidence|Find and read|^585$|^41,000$|^44$|^3\/4$/.test(t));
    await page.click(`[data-final="${pick < 0 ? 0 : pick}"]`);
    await sleep(ms * 0.22);
    await shot("lab_debrief");
    await sleep(ms * 0.3);
    await page.evaluate(() => { const e = document.getElementById("score"); e.scrollIntoView({ behavior: "smooth", block: "center" }); });
  });

  await gotoHash("#/data");
  await page.waitForSelector("#export");
  await seg("data", async (ms) => {
    await sleep(ms * 0.3);
    await shot("data");
    await page.click("#del");
    await sleep(ms * 0.3);
    await page.click("#del-no");
  });

  const results = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "..", "docs", "evaluation_results.json"), "utf8")).summary;
  await page.setContent(`<!doctype html><html><head><title>AI4Brain</title></head><body style="margin:0;background:#0b2239;color:#fff;font-family:Bahnschrift,'Segoe UI',sans-serif;display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;gap:26px">
     <div style="font-size:44px;font-weight:600">Tested on simulated learners</div>
     <div style="display:flex;gap:70px;text-align:center">
       <div><div style="font-size:84px;font-weight:600">${Math.round(results.clean.coverage_90 * 100)}%</div><div style="font-size:22px;color:#bcd3e6">true values inside<br>the 90% range</div></div>
       <div><div style="font-size:84px;font-weight:600">${results.clean.rmse_points.toFixed(1)}</div><div style="font-size:22px;color:#bcd3e6">points of error<br>(RMSE, one session)</div></div>
       <div><div style="font-size:84px;font-weight:600">${results.contaminated_unweighted.rmse_points.toFixed(1)} to ${results.contaminated_weighted.rmse_points.toFixed(1)}</div><div style="font-size:22px;color:#bcd3e6">error under careless responding,<br>before and after evidence weighting</div></div>
     </div>
     <div style="font-size:24px;color:#f0b48a">Not yet validated with people. That study comes next.</div>
     </body></html>`);
  await seg("eval", async () => {});
  await sleep(600);

  await cdp.send("Page.stopScreencast");
  await sleep(300);
  const endAt = (t0() - startedAt) / 1000;
  fs.writeFileSync(path.join(work, "timeline.json"), JSON.stringify({ timeline, frames, duration: endAt }, null, 0));
  console.log(`Recorded ${frames.length} frames over ${endAt.toFixed(1)} s`);
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
