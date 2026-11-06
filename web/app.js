/* AI4Brain single-page app. All user-facing text is plain English and non-clinical. */
const { esc, fmt } = Charts;
const main = document.getElementById("main");
const rail = document.getElementById("rail");

const store = {
  mem: {},
  get(k) { try { return localStorage.getItem(k) ?? this.mem[k] ?? null; } catch { return this.mem[k] ?? null; } },
  set(k, v) { this.mem[k] = v; try { localStorage.setItem(k, v); } catch { /* private mode */ } },
  del(k) { delete this.mem[k]; try { localStorage.removeItem(k); } catch { /* private mode */ } },
};

const state = { meta: null, me: null, twin: null, mood: null, voiceOn: false };

async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json" };
  const pid = store.get("profile");
  if (pid) headers["X-Profile"] = pid;
  const res = await fetch(path, { method: opts.method || "GET", headers, body: opts.body ? JSON.stringify(opts.body) : undefined });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed with status ${res.status}`);
  return data;
}

const LOGO = `<svg viewBox="0 0 32 32" aria-hidden="true"><polygon points="16,2 29,10 29,23 16,30 3,23 3,10" fill="#2F6F8F"/><polygon points="16,9 23,13 23,20 16,24 9,20 9,13" fill="#E2AE2A"/></svg>`;

function renderRail(active) {
  const links = [["#/twin", "Brain Twin"], ["#/practice", "Practice"], ["#/plan", "Plan and goals"], ["#/coach", "Coach"], ["#/lab", "AI collaboration"], ["#/data", "My data"]];
  rail.hidden = false;
  rail.innerHTML = `<div class="brand">${LOGO}<span>AI4Brain</span></div><div class="rail-links">` +
    links.map(([h, t]) => `<a href="${h}" ${h === active ? 'aria-current="page"' : ""}>${t}</a>`).join("") +
    `</div><div class="rail-foot">Practice tool only. It says nothing about your health.</div>`;
  /* On phones the menu is one sideways row; keep the current page in view. */
  const strip = rail.querySelector(".rail-links"), cur = strip.querySelector("[aria-current]");
  if (cur && strip.scrollWidth > strip.clientWidth) strip.scrollLeft = cur.offsetLeft - (strip.clientWidth - cur.offsetWidth) / 2;
}

function errorBox(err) { return `<div class="error" role="alert">${esc(err.message || err)}</div>`; }

/* Marks a button as working while its request runs, so a slow reply never looks like a dead click.
   Repeat clicks are ignored until the first one finishes. */
async function busy(btn, work) {
  if (!btn) return work();
  if (btn.getAttribute("aria-busy") === "true") return undefined;
  btn.setAttribute("aria-busy", "true");
  try { return await work(); } finally { btn.removeAttribute("aria-busy"); }
}

function demoNote() {
  return state.me?.is_demo ? `<div class="demo-note">You are viewing sample data from a simulated learner. <a href="#/data">Delete it and start your own</a>.</div>` : "";
}

/* ---------- welcome and consent ---------- */
function renderWelcome() {
  rail.hidden = true;
  const sampleRows = [
    ["Attention", 58, 46, 69], ["Working memory", 49, 35, 63], ["Processing speed", 67, 58, 75], ["Logical reasoning", 62, 44, 78], ["Cognitive flexibility", 44, 30, 58],
    ["Verbal reasoning", 71, 60, 80], ["Spatial reasoning", 38, 24, 55], ["Decision making", 55, 38, 71], ["Creative thinking", 52, 28, 76], ["Self-monitoring", 64, 54, 73],
  ].map(([name, pct, low, high]) => ({ name, pct, low, high, n_trials: 1 }));
  main.innerHTML = `<div class="welcome">
    <div>
      <div class="brand welcome-brand">${LOGO}<span>AI4Brain</span></div>
      <h1>A twin of how you think, with the doubt left in.</h1>
      <p class="tag">Practise ten thinking skills. Every estimate comes with an honest range, and every piece of coaching shows its evidence.</p>
      <form class="consent" id="consent-form">
        <label><input type="checkbox" id="c-store" required> <span><b>Save my results on this device.</b> Required. I can export or delete them at any time.</span></label>
        <label><input type="checkbox" id="c-llm"> <span>Let Claude write coaching messages. Optional. It sees summary numbers and the question I ask, with personal details removed and no identifier. This also needs an API key on the server.</span></label>
        <label><input type="checkbox" id="c-voice"> <span>Allow voice coaching. Optional. Speech stays in the browser and no voice print is ever made.</span></label>
        <label class="retention"><span>Delete my data after</span>
          <select id="c-ret" aria-label="Delete my data after"><option value="30">30 days idle</option><option value="90">90 days idle</option><option value="180" selected>180 days idle</option><option value="365">1 year idle</option></select>
        </label>
        <p class="small muted consent-note">This is a practice tool. It is not a medical or psychological test. No camera or biometric data is used.</p>
      </form>
      <div class="row">
        <button class="btn primary big" id="start">Start my twin</button>
        <button class="btn big" id="sample">Explore sample data</button>
      </div>
      <div id="welcome-err"></div>
    </div>
    <figure class="welcome-radar" aria-hidden="true"><div class="radar-slot"></div><figcaption class="small muted">A sample twin. The line is each estimate; the shaded band is how far it could be off.</figcaption></figure>
  </div>`;
  /* Drawn at its real width, and brought into focus once: the app's idea in one moment. */
  const slot = main.querySelector(".radar-slot");
  slot.innerHTML = Charts.radar(sampleRows, { size: slot.clientWidth || 520 });
  slot.classList.add("focus-pull");
  const err = document.getElementById("welcome-err");
  const startBtn = document.getElementById("start");
  startBtn.onclick = () => busy(startBtn, async () => {
    const box = document.getElementById("c-store");
    if (!box.checked) {
      err.innerHTML = errorBox("Tick the first box to save results. Your twin can't work without it. Or explore the sample data instead.");
      box.focus();
      return;
    }
    err.innerHTML = "";
    try {
      const r = await api("/api/profile", { method: "POST", body: { consent: { store: true, llm: document.getElementById("c-llm").checked, voice: document.getElementById("c-voice").checked }, retention_days: +document.getElementById("c-ret").value } });
      store.set("profile", r.profile_id);
      location.hash = "#/practice";
    } catch (e) { err.innerHTML = errorBox(`Your twin wasn't created: ${e.message}. Check the app is still running, then try again.`); }
  });
  const sampleBtn = document.getElementById("sample");
  sampleBtn.onclick = () => busy(sampleBtn, async () => {
    sampleBtn.textContent = "Building sample data";
    err.innerHTML = "";
    try {
      const r = await api("/api/demo", { method: "POST" });
      store.set("profile", r.profile_id);
      location.hash = "#/twin";
    } catch (e) {
      sampleBtn.textContent = "Explore sample data";
      err.innerHTML = errorBox(`The sample data wasn't built: ${e.message}. Try again.`);
    }
  });
}

/* ---------- twin dashboard ---------- */
function snapshotAt(hist, profile, t) {
  /* The twin as it stood at time t, from the immutable history. */
  return profile.map((d) => {
    const pts = (hist[d.key] || []).filter((p) => +new Date(p.at) <= t);
    if (!pts.length) return { key: d.key, name: d.name, pct: 50, low: 15, high: 85, n_trials: 0 };
    const p = pts[pts.length - 1];
    return { key: d.key, name: d.name, pct: p.pct, low: p.low, high: p.high, n_trials: p.n_trials };
  });
}

function insightHtml(i) {
  const action = i.action
    ? (i.action.type === "collab" ? `<a class="btn" href="#/lab">Open the lab</a>` : `<button class="btn" data-start="${i.action.dimension}" data-mode="${i.action.mode}">${i.action.mode === "assess" ? "Check in" : "Practise"}</button>`)
    : "";
  return `<div class="insight ${["state", "uncertain", "stale"].includes(i.kind) ? "attention" : ""}">
    <h3>${esc(i.title)}</h3>
    <p>${esc(i.message)}</p>
    <details class="why"><summary>Why I'm saying this (${esc(i.certainty.label)})</summary><ul>${i.because.map((b) => `<li>${esc(b)}</li>`).join("")}<li>${esc(i.certainty.basis)}</li></ul></details>
    ${action ? `<div class="insight-action">${action}</div>` : ""}
  </div>`;
}

function bindStarters(root) {
  root.querySelectorAll("[data-start]").forEach((b) => {
    b.onclick = () => {
      const target = `#/session/${b.dataset.start}/${b.dataset.mode || "assess"}`;
      if (location.hash === target) route(); else location.hash = target;
    };
  });
}

async function renderTwin() {
  renderRail("#/twin");
  main.innerHTML = `<div class="page"><p class="loading" role="status">Loading your twin</p></div>`;
  const t = await api("/api/twin");
  state.twin = t;
  const allTimes = Object.values(t.history).flat().map((p) => +new Date(p.at)).sort((a, b) => a - b);
  const assessed = t.profile.filter((d) => d.n_trials > 0).length;
  main.innerHTML = `<div class="page">
    ${demoNote()}
    <div class="page-head">
      <h1>Your Brain Twin</h1>
      <p class="lede">${assessed === 0 ? "Nothing measured yet, so every range is as wide as it can be." : `${assessed} of ${t.profile.length} skills have evidence. Drag the timeline to see how the picture changed.`}</p>
    </div>
    <div class="twin-hero">
      <div class="radar-wrap">
        <div id="radar"></div>
        <div class="legend"><span><i class="est"></i>Estimate</span><span><i class="band"></i>90% range</span></div>
        ${allTimes.length > 1 ? `<div class="scrub"><label for="scrub" class="small">Timeline</label><input type="range" id="scrub" min="0" max="${allTimes.length - 1}" value="${allTimes.length - 1}" aria-label="Move through your history"><output id="scrub-out"></output></div>` : ""}
      </div>
      <div>
        <div class="ranges" id="range-list"></div>
        <p class="small muted" style="margin-top:10px">Percent means the share of a balanced practice set you'd be expected to solve. It is not a comparison with other people.</p>
        <details class="why"><summary>Show these numbers as a table</summary><div id="radar-table"></div></details>
      </div>
    </div>

    <section class="section">
      <h2>What the coach sees</h2>
      <p class="sub">Each note comes from rules applied to your own results. Open one to see the evidence.</p>
      <div class="insights">${t.insights.map(insightHtml).join("") || `<p class="muted">Nothing to report yet.</p>`}</div>
    </section>

    <section class="section">
      <h2>Progress curves</h2>
      <p class="sub">The fan shows a plausible range if practice continues in a similar way. It is never a prediction.</p>
      <div class="legend curves-legend"><span><i class="est"></i>Estimate</span><span><i class="band"></i>90% range at each check-in</span><span><i class="proj"></i>Plausible range ahead</span></div>
      <div class="small-multiples" id="curves"></div>
    </section>

    <section class="section">
      <h2>Heatmaps</h2>
      <div class="heat-tabs segmented" role="group" aria-label="Choose heatmap">
        <button class="btn toggle" aria-pressed="true" id="ht-week">Estimate by week</button>
        <button class="btn toggle" aria-pressed="false" id="ht-level">Success by difficulty</button>
      </div>
      <div class="panel" id="heat"></div>
    </section>

    <section class="section">
      <h2>Goals</h2>
      <p class="sub">A goal counts as reached when there is at least an 80% probability that you are at or above the target. <a href="#/plan">Manage goals</a>.</p>
      <div id="goal-list">${goalRows(t.goals, false) || `<p class="muted">No goals yet. <a href="#/plan">Set one</a>.</p>`}</div>
    </section>
  </div>`;
  bindStarters(main);

  const radarEl = document.getElementById("radar");
  const paint = (rows, label) => {
    radarEl.innerHTML = Charts.radar(rows, { label, size: radarEl.clientWidth });
    Charts.bindRadar(radarEl, rows);
  };
  const now = t.profile;
  paint(now.map((d) => ({ ...d })), "Current Brain Twin");
  /* The one orchestrated moment: the band comes into focus once, when the twin first appears. */
  radarEl.classList.add("focus-pull");
  setTimeout(() => radarEl.classList.remove("focus-pull"), 600);
  document.getElementById("range-list").innerHTML = now.map((d) => Charts.rangeRow(d, { href: `#/skill/${d.key}` })).join("");
  document.getElementById("radar-table").innerHTML = `<table class="data"><thead><tr><th>Skill</th><th>Estimate</th><th>Low</th><th>High</th><th>Items</th></tr></thead><tbody>${now.map((d) => `<tr><td>${esc(d.name)}</td><td>${d.n_trials ? fmt(d.pct) + "%" : "none yet"}</td><td>${fmt(d.low)}</td><td>${fmt(d.high)}</td><td>${d.n_trials}</td></tr>`).join("")}</tbody></table>`;

  const scrub = document.getElementById("scrub");
  if (scrub) {
    const out = document.getElementById("scrub-out");
    const update = () => {
      const i = +scrub.value;
      const atEnd = i === allTimes.length - 1;
      const rows = atEnd ? now : snapshotAt(t.history, now, allTimes[i]);
      paint(rows, `Brain Twin on ${Charts.fmtDate(new Date(allTimes[i]).toISOString())}`);
      out.textContent = atEnd ? "Now" : Charts.fmtDate(new Date(allTimes[i]).toISOString());
      document.getElementById("range-list").innerHTML = rows.map((d) => Charts.rangeRow({ ...d, evidence: d.evidence || (d.n_trials ? `${d.n_trials} items by then` : "not yet measured") }, { href: `#/skill/${d.key}` })).join("");
    };
    scrub.oninput = update;
    update();
  }

  const curves = document.getElementById("curves");
  curves.innerHTML = now.filter((d) => (t.history[d.key] || []).length).map((d) =>
    `<div class="sm"><a href="#/skill/${d.key}"><h3>${esc(d.name)}</h3></a><div class="chart" data-key="${d.key}" data-name="${esc(d.name)}"></div></div>`).join("") ||
    `<p class="muted">Finish a check-in and your first curve will appear here.</p>`;
  /* Drawn at their on-screen width so axis labels keep their real size. */
  curves.querySelectorAll(".chart").forEach((el) => {
    const k = el.dataset.key, width = Math.max(150, el.clientWidth);
    el.innerHTML = Charts.progress(t.history[k], { projection: t.projections[k], now: t.now, width, height: 140, label: `${el.dataset.name} progress` });
    Charts.bindProgress(el, t.history[k], { projection: t.projections[k], width });
  });

  const heat = document.getElementById("heat");
  const drawWeek = () => {
    const hm = t.heatmaps;
    heat.innerHTML = Charts.heatmap(now, hm.week_labels, (k, i) => hm.by_week[k][i], (row, i, v) =>
      v === null ? `${row.name}, week of ${hm.week_labels[i]}: no check-in` : `${row.name}, week of ${hm.week_labels[i]}: about ${fmt(v)}%, from ${hm.trials_by_week[row.key][i]} items`) +
      `<div class="heat-legend"><span>Lower</span><div class="ramp"></div><span>Higher</span><span>Hatched: no check-in that week</span></div>`;
    Charts.bindHeat(heat);
  };
  const drawLevel = () => {
    const hm = t.heatmaps;
    const levels = Array.from({ length: 10 }, (_, i) => `L${i + 1}`);
    heat.innerHTML = Charts.heatmap(now, levels, (k, i) => (hm.by_level[k][i].rate === null ? null : hm.by_level[k][i].rate * 100), (row, i, v) =>
      v === null ? `${row.name}, level ${i + 1}: no items yet` : `${row.name}, level ${i + 1}: ${fmt(v)}% right over ${hm.by_level[row.key][i].n} items`) +
      `<div class="heat-legend"><span>Fewer right</span><div class="ramp"></div><span>More right</span><span>Hatched: no items yet</span></div>`;
    Charts.bindHeat(heat);
  };
  const tabW = document.getElementById("ht-week"), tabL = document.getElementById("ht-level");
  tabW.onclick = () => { tabW.setAttribute("aria-pressed", "true"); tabL.setAttribute("aria-pressed", "false"); drawWeek(); };
  tabL.onclick = () => { tabL.setAttribute("aria-pressed", "true"); tabW.setAttribute("aria-pressed", "false"); drawLevel(); };
  drawWeek();
}

function goalRows(goals, removable) {
  const icon = { reached: "✓", "on the way": "↗", "needs attention": "!", "past due": "!" };
  const cls = { reached: "good", "on the way": "", "needs attention": "warn", "past due": "bad" };
  return goals.map((g) => `<div class="goal-row">
    <div><b>${esc(g.name)}</b><div class="small muted">Target ${fmt(g.target_pct)}% by ${Charts.fmtDate(g.due_date)}</div></div>
    <div>${Charts.rangeRow({ name: g.name, pct: g.current_pct, low: g.low, high: g.high, n_trials: 1 }, { compact: true })}</div>
    <div class="small">${fmt(g.prob_reached * 100)}% probability reached</div>
    <div class="row"><span class="chip ${cls[g.status]}">${icon[g.status]} ${esc(g.status)}</span>${removable ? `<button class="btn small" data-del-goal="${g.id}" aria-label="Remove goal for ${esc(g.name)}">Remove</button>` : ""}</div>
  </div>`).join("");
}

/* ---------- skill detail ---------- */
async function renderSkill(key) {
  renderRail("#/twin");
  const d = await api(`/api/twin/${key}`);
  const info = d.info, s = d.state;
  main.innerHTML = `<div class="page">
    ${demoNote()}
    <p class="back"><a href="#/twin">Back to your twin</a></p>
    <div class="page-head"><h1>${esc(info.name)}</h1><p class="lede">${esc(info.plain)}</p></div>
    <div class="panel skill-now">${Charts.rangeRow({ ...s, name: info.name }, { compact: true })}
      <div class="row skill-now-foot">
        <span class="small muted">${esc(s.evidence || (s.n_trials ? `${s.n_trials} items` : "Not measured yet"))}</span>
        <div class="row">
          <button class="btn primary" data-start="${key}" data-mode="assess">Check in</button>
          <button class="btn" data-start="${key}" data-mode="train">Practise at my level</button>
        </div>
      </div>
    </div>

    <section class="section"><h2>How this has moved</h2>
      <div class="sm chart" id="big-curve">${d.history.length ? "" : `<p class="muted">No check-ins yet. Your first check-in draws the first point here.</p>`}</div>
      ${d.projection.available
        ? `<p class="small muted" style="margin-top:6px">${esc(d.projection.wording)} Chance the underlying trend is upward: ${fmt(d.projection.prob_growing * 100)}%.</p>`
        : `<p class="small muted" style="margin-top:6px">No projection yet. ${esc(d.projection.reason)}</p>`}
    </section>

    <section class="section"><h2>Why the estimate is where it is</h2>
      <p class="sub">These items moved it most. Items answered too fast, or while the window lost focus, count for less.</p>
      ${d.moved.length ? `<table class="data"><thead><tr><th>Task</th><th class="n">Level</th><th>Result</th><th class="n">Time</th><th class="n">Weight</th><th class="n">Moved estimate</th></tr></thead><tbody>${d.moved.map((m) => `<tr><td>${esc(taskName(info, m.task))}</td><td class="n">${m.level}</td><td class="${m.correct ? "res-ok" : "res-no"}">${m.correct ? "✓ Right" : "✗ Missed"}</td><td class="n">${m.rt_ms ? (m.rt_ms / 1000).toFixed(1) + " s" : "no response"}</td><td class="n">${m.weight}</td><td class="n moved ${m.moved > 0 ? "up" : "down"}">${m.moved > 0 ? "+" : ""}${m.moved} points</td></tr>`).join("")}</tbody></table>` : `<p class="muted">No items answered yet.</p>`}
    </section>

    <section class="section"><h2>What this measures, and its limits</h2>
      <div class="docs-grid limits">
        <div><h3>Definition</h3><p>${esc(info.definition)}</p></div>
        <div><h3>Tasks</h3><ul style="margin:0;padding-left:18px">${info.tasks.map((x) => `<li><b>${esc(x.name)}.</b> ${esc(x.how)}</li>`).join("")}</ul></div>
        <div><h3>Scoring</h3><p>${esc(info.scoring)}</p></div>
        <div><h3>Uncertainty</h3><p>${esc(info.uncertainty)}</p></div>
        <div><h3>Known biases</h3><p>${esc(info.biases)}</p></div>
      </div>
    </section>
  </div>`;
  bindStarters(main);
  const cv = document.getElementById("big-curve");
  if (d.history.length) {
    const width = Math.max(280, cv.clientWidth - 32);
    cv.innerHTML = Charts.progress(d.history, { projection: d.projection, width, height: width < 500 ? 200 : 260, label: `${info.name} progress` });
    Charts.bindProgress(cv, d.history, { projection: d.projection, width });
  }
}
const taskName = (info, key) => info.tasks.find((t) => t.key === key)?.name || key;

/* ---------- practice ---------- */
async function renderPractice() {
  renderRail("#/practice");
  const t = await api("/api/twin");
  state.twin = t;
  const moods = [["energised", "Energised"], ["ok", "OK"], ["tired", "Tired"], ["frustrated", "Frustrated"]];
  main.innerHTML = `<div class="page">
    ${demoNote()}
    <div class="page-head"><h1>Practice</h1><p class="lede">A check-in measures where you are. Practising picks a level you'd get right about 8 times in 10.</p></div>
    <div class="mood" role="group" aria-label="How are you feeling?">
      <span>How are you feeling? It's optional, and it only changes pacing.</span>
      ${moods.map(([k, l]) => `<button class="btn small toggle" aria-pressed="${state.mood === k}" data-mood="${k}">${l}</button>`).join("")}
    </div>
    <div class="practice-list">${t.profile.map((d) => `<div class="practice-row">
      <div><b>${esc(d.name)}</b><div class="plain">${esc(d.plain)}</div></div>
      ${Charts.scale(d, !d.n_trials)}
      ${Charts.rangeVal(d, !d.n_trials)}
      <div class="row practice-actions"><button class="btn small" data-start="${d.key}" data-mode="assess" aria-label="Check in: ${esc(d.name)}">Check in</button><button class="btn small" data-start="${d.key}" data-mode="train" aria-label="Practise: ${esc(d.name)}">Practise</button></div>
    </div>`).join("")}</div>
  </div>`;
  bindStarters(main);
  main.querySelectorAll("[data-mood]").forEach((b) => {
    b.onclick = () => {
      state.mood = state.mood === b.dataset.mood ? null : b.dataset.mood;
      main.querySelectorAll("[data-mood]").forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.mood === state.mood)));
    };
  });
}

/* ---------- session runner ---------- */
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let activeRun = 0;

async function runSession(dimension, mode) {
  /* A session takes the whole screen; "End session" is the way out, so results are always saved. */
  rail.hidden = true;
  const runId = ++activeRun;
  const dimInfo = state.meta.dimensions.find((d) => d.key === dimension);
  const started = await api("/api/session", { method: "POST", body: { dimension, mode, mood: state.mood } });
  main.innerHTML = `<div class="page runner">
    <div class="runner-top"><div class="runner-title"><span class="brand-mark">${LOGO}</span><h1>${esc(dimInfo.name)}</h1><span class="chip quiet">${mode === "assess" ? "Check-in" : "Practice"}</span></div><button class="btn small" id="stop">End session</button></div>
    <div class="progress"><div id="bar" style="width:0"></div></div>
    <div class="stage" id="stage"></div>
    <div class="live-band" id="live" ${mode === "assess" ? "" : "hidden"}></div>
  </div>`;
  const stage = document.getElementById("stage");
  const bar = document.getElementById("bar");
  const live = document.getElementById("live");
  let stopping = false;
  document.getElementById("stop").onclick = () => { stopping = true; finish(); };

  async function showIntro(item) {
    return new Promise((resolve) => {
      const task = dimInfo.key === "metacognition" ? null : dimInfo.tasks.find((t) => t.key === item.task);
      stage.innerHTML = `<h2>${esc(task ? task.name : "Confidence check")}</h2>
        <p style="max-width:52ch">${esc(item.instructions)}${dimInfo.key === "metacognition" ? " After each answer, say how sure you are. Knowing what you don't know counts here." : ""}</p>
        ${item.kind === "choice" ? `<p class="key-hint">Use the left and right arrow keys, or tap the buttons.</p>` : ""}
        <button class="btn primary big" id="go">Begin</button>`;
      const go = document.getElementById("go");
      go.focus();
      go.onclick = () => resolve();
    });
  }

  let finished = false;
  async function finish() {
    if (finished) return;
    finished = true;
    Tasks.detach();
    await askEstimate(started.session_id, dimInfo, i);
  }

  Tasks.attach();
  let trialId = started.trial_id, item = started.item, lastTask = null, i = 0;
  const isMeta = dimension === "metacognition";
  while (item && !stopping && runId === activeRun) {
    if (item.task !== lastTask && (!isMeta || lastTask === null)) { await showIntro(item); lastTask = item.task; }
    if (stopping || runId !== activeRun) break;
    stage.innerHTML = "";
    await sleep(item.kind === "choice" || item.kind === "go_nogo" ? 300 : 120);
    if (stopping || runId !== activeRun) break;
    const r = await Tasks.runItem(stage, item);
    if (stopping || runId !== activeRun) break;
    const result = await api(`/api/session/${started.session_id}/answer`, { method: "POST", body: { trial_id: trialId, ...r } });
    i += 1;
    bar.style.width = `${(result.progress.i / result.progress.max) * 100}%`;
    if (mode === "assess") {
      live.innerHTML = `<div class="small muted">Live estimate for ${esc(state.meta.dimensions.find((d) => d.key === result.live.dimension).name)}. The range narrows as evidence builds.</div>${Charts.rangeRow({ ...result.live, name: "", n_trials: i })}`;
    }
    const showFeedback = mode === "train" || item.kind === "mcq" || item.kind === "recall" || item.kind === "free_text";
    if (showFeedback) {
      stage.innerHTML = feedbackHtml(result, item, mode);
      await sleep(mode === "train" ? 1000 : 500);
    }
    if (result.done) break;
    trialId = result.trial_id;
    item = result.item;
  }
  if (!stopping && runId === activeRun) finish();
}

function feedbackHtml(result, item, mode) {
  if (item.task === "alt_uses") {
    const d = result.detail;
    return `<div class="feedback">${d.ideas} ideas counted, ${d.unusual} outside the common list.</div><div class="small muted">This scoring is rough, so it counts for less in your estimate.</div>`;
  }
  if (mode === "assess" && item.kind !== "free_text") return `<div class="feedback">Recorded</div>`;
  if (result.correct) return `<div class="feedback ok">✓ Right</div>`;
  const ans = result.answer && item.kind !== "go_nogo" && !item.payload?.grid_options ? ` The answer was ${esc(result.answer)}.` : "";
  return `<div class="feedback no">✗ ${result.timed_out ? "Out of time." : "Not this time."}${ans}</div>`;
}

async function askEstimate(sessionId, dimInfo, count) {
  const stage = document.getElementById("stage");
  if (!count) { await showSummary(sessionId, null, dimInfo); return; }
  stage.innerHTML = `<h2>Before you see the results</h2>
    <p>You answered ${count} items. How many do you think you got right? This helps measure self-monitoring.</p>
    <div class="row" style="justify-content:center"><input id="est" type="number" min="0" max="${count}" value="${Math.round(count * 0.6)}" class="word-input" style="width:110px" aria-label="Estimated number right"><button class="btn primary" id="est-go">See results</button><button class="btn" id="est-skip">Skip</button></div>`;
  document.getElementById("est-go").onclick = () => showSummary(sessionId, +document.getElementById("est").value, dimInfo);
  document.getElementById("est-skip").onclick = () => showSummary(sessionId, null, dimInfo);
  document.getElementById("est").focus();
}

async function showSummary(sessionId, estimate, dimInfo) {
  const r = await api(`/api/session/${sessionId}/finish`, { method: "POST", body: { self_estimate: estimate } });
  renderRail("#/practice");
  const s = r.summary, st = s.stats;
  const nameOf = (k) => state.meta.dimensions.find((d) => d.key === k).name;
  if (!st.n) { location.hash = "#/practice"; return; }
  main.innerHTML = `<div class="page">
    <div class="page-head"><h1>${esc(dimInfo.name)}: what changed</h1><p class="lede">${st.n} items. ${s.mode === "assess" ? "Your estimate has been updated." : "Your estimate and next level have been updated."}</p></div>
    <div class="panel"><div class="stat-line">
      <div><b>${fmt(st.accuracy * 100)}%</b><span>right</span></div>
      <div><b>${st.median_rt_ms ? (st.median_rt_ms / 1000).toFixed(1) + " s" : "n/a"}</b><span>typical response</span></div>
      <div><b>${st.mean_level}</b><span>average level</span></div>
      <div><b>${fmt(st.data_quality * 100)}%</b><span>evidence weight</span></div>
      ${st.self_estimate !== undefined ? `<div><b>${st.self_estimate} of ${st.n}</b><span>your guess (actual ${st.actual_correct})</span></div>` : ""}
    </div>
    ${st.focus_lost || st.too_fast ? `<p class="small muted" style="margin:10px 0 0">${st.focus_lost ? `${st.focus_lost} items happened while the window had lost focus. ` : ""}${st.too_fast ? `${st.too_fast} items were answered too fast to have been read. ` : ""}These count for less.</p>` : ""}
    </div>

    <section class="section"><h2>Before and after</h2>
      <div class="changes">${Object.entries(s.changes).map(([k, c]) => `<div><b>${esc(nameOf(k))}</b>
        ${c.before ? `<div class="before-after"><span class="small muted">Before</span>${track(c.before)}<span class="range-val">${fmt(c.before.pct)}% <span>${fmt(c.before.low)} to ${fmt(c.before.high)}</span></span></div>` : ""}
        <div class="before-after"><span class="small muted">After</span>${track(c.after)}<span class="range-val"><b>${fmt(c.after.pct)}%</b> <span>${fmt(c.after.low)} to ${fmt(c.after.high)}</span></span></div></div>`).join("")}</div>
    </section>

    ${s.top_evidence?.length ? `<section class="section"><h2>Why it moved</h2><table class="data"><thead><tr><th>Item</th><th class="n">Level</th><th>Result</th><th class="n">Weight</th><th class="n">Effect</th></tr></thead><tbody>${s.top_evidence.map((t) => `<tr><td>${esc((t.prompt || t.task).slice(0, 60))}</td><td class="n">${t.level}</td><td class="${t.correct ? "res-ok" : "res-no"}">${t.correct ? "✓ Right" : "✗ Missed"}</td><td class="n">${t.weight}</td><td class="n moved ${t.moved > 0 ? "up" : "down"}">${t.moved > 0 ? "+" : ""}${t.moved} points</td></tr>`).join("")}</tbody></table></section>` : ""}

    ${s.state_proxy.state !== "steady" ? `<section class="section"><div class="insight attention"><h3>That looked hard going</h3><p>I noticed ${esc(s.state_proxy.signals.join("; "))}. I'll ease the next session a little. ${esc(s.state_proxy.effect)}</p></div></section>` : ""}

    <section class="section"><h2>Coach notes</h2><div class="insights">${r.insights.slice(0, 3).map(insightHtml).join("")}</div></section>
    <section class="section"><h2>Your plan changed</h2><ul>${r.plan_changes.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>
      <div class="row"><a class="btn primary" href="#/plan">See my plan</a><a class="btn" href="#/twin">See my twin</a><button class="btn" data-start="${dimInfo.key}" data-mode="${s.mode}">Go again</button></div>
    </section>
  </div>`;
  bindStarters(main);
  main.focus();
}

function track(x) {
  return Charts.scale(x);
}

/* ---------- plan and goals ---------- */
async function renderPlan() {
  renderRail("#/plan");
  const [{ plan, history }, t] = await Promise.all([api("/api/plan"), api("/api/twin")]);
  const today = plan.days[0];
  const weights = plan.weights;
  const defaultDue = new Date(Date.now() + 21 * 86400000).toISOString().slice(0, 10);
  main.innerHTML = `<div class="page">
    ${demoNote()}
    <div class="page-head"><h1>Plan and goals</h1><p class="lede">Version ${plan.version} of your plan. It updates after every session, and each step says why it's there.</p></div>

    <section class="section first"><h2>Today</h2>
      <div class="today">${today.sessions.map((s, i) => `<div class="plan-session${i === 0 ? " next" : ""}">
        <div><h3>${esc(s.name)}: ${s.mode === "assess" ? "check-in" : `practice${s.level ? ` around level ${s.level}` : ""}`}</h3>
          <span class="small muted">About ${s.minutes} minutes</span>
          <ul>${s.why.map((w) => `<li>Because ${esc(w)}.</li>`).join("")}</ul>
          <p class="small worked"><b>You'll know it worked when:</b> ${esc(s.success_measure)}</p></div>
        <button class="btn${i === 0 ? " primary" : ""}" data-start="${s.dimension}" data-mode="${s.mode}" aria-label="Start ${esc(s.name)}">Start</button>
      </div>`).join("")}</div>
    </section>

    <section class="section"><h2>This week</h2>
      <p class="sub">Sessions are spaced out and interleaved, so the same skill isn't repeated too soon.</p>
      <div class="week">${plan.days.map((d, i) => `<div class="day${i === 0 ? " is-today" : ""}"><b>${new Date(d.date + "T12:00:00").toLocaleDateString("en-GB", { weekday: "short", day: "numeric" })}</b>${d.sessions.map((s) => `<div>${esc(s.name)}</div>`).join("")}</div>`).join("")}</div>
    </section>

    <section class="section"><h2>Goals</h2>
      <div id="goals">${goalRows(t.goals, true) || `<p class="muted">No goals yet. Add one and the plan will shift towards it.</p>`}</div>
      <form class="form-row" id="goal-form" style="margin-top:12px">
        <label>Skill<select id="g-dim">${t.profile.map((d) => `<option value="${d.key}">${esc(d.name)}</option>`).join("")}</select></label>
        <label>Target percent<input id="g-target" type="number" min="1" max="99" value="70" style="width:90px"></label>
        <label>By<input id="g-due" type="date" value="${defaultDue}"></label>
        <button class="btn primary" type="submit">Add goal</button>
      </form><div id="goal-err"></div>
    </section>

    <section class="section"><h2>Measurable milestones</h2>
      <table class="data"><thead><tr><th>Skill</th><th>Source</th><th>From</th><th>To</th><th>By</th><th>How it's measured</th></tr></thead><tbody>
      ${plan.milestones.map((m) => `<tr><td>${esc(m.name)}</td><td>${esc(m.source)}</td><td>${fmt(m.from_pct)}%</td><td>${fmt(m.to_pct)}%</td><td>${Charts.fmtDate(m.due)}</td><td>${esc(m.measure)}</td></tr>`).join("")}
      </tbody></table>
    </section>

    <section class="section"><h2>How priorities are worked out</h2>
      <p class="formula">priority = ${weights.goal_gap} goal gap + ${weights.uncertainty} uncertainty + ${weights.staleness} time since practice + ${weights.plateau} plateau</p>
      <div class="legend prio-legend"><span><i class="c-goal"></i>Goal gap</span><span><i class="c-unc"></i>Uncertainty</span><span><i class="c-stale"></i>Time since practice</span><span><i class="c-plat"></i>Plateau</span></div>
      <p class="small muted">Bars are scaled to the highest priority, ${Math.max(...plan.ranked.map((r) => r.priority)).toFixed(2)}.</p>
      ${plan.ranked.map((r) => {
        const c = r.components;
        const top = Math.max(...plan.ranked.map((x) => x.priority)) || 1;
        const seg = (cls, key) => `<i class="${cls}" style="width:${(weights[key] * c[key] * 100) / top}%" title="${key}"></i>`;
        return `<div class="prio-row"><span>${esc(r.name)}</span><div class="prio-bar">${seg("c-goal", "goal_gap")}${seg("c-unc", "uncertainty")}${seg("c-stale", "staleness")}${seg("c-plat", "plateau")}</div><span class="num">${r.priority.toFixed(2)}</span></div>`;
      }).join("")}
    </section>

    <section class="section"><h2>What changed recently</h2>
      ${(() => {
        const ver = (h) => `<div class="plan-version"><h3>Version ${h.version} <span class="small muted">${Charts.fmtDate(h.created_at)}</span></h3><ul>${h.changes.map((c) => `<li>${esc(c)}</li>`).join("")}</ul></div>`;
        const recent = history.slice(0, 5);
        return (recent[0] ? ver(recent[0]) : "") +
          (recent.length > 1 ? `<details class="why earlier"><summary>Show earlier versions (${recent.length - 1})</summary>${recent.slice(1).map(ver).join("")}</details>` : "");
      })()}
    </section>
  </div>`;
  bindStarters(main);
  document.getElementById("goal-form").onsubmit = async (e) => {
    e.preventDefault();
    await busy(e.submitter, async () => {
      try {
        await api("/api/goals", { method: "POST", body: { dimension: document.getElementById("g-dim").value, target_pct: +document.getElementById("g-target").value, due_date: document.getElementById("g-due").value + "T23:59:00+00:00" } });
        await renderPlan();
      } catch (err) { document.getElementById("goal-err").innerHTML = errorBox(err); }
    });
  };
  main.querySelectorAll("[data-del-goal]").forEach((b) => {
    b.onclick = () => busy(b, async () => { await api(`/api/goals/${b.dataset.delGoal}`, { method: "DELETE" }); await renderPlan(); });
  });
}

/* ---------- coach ---------- */
function speak(text) {
  if (!state.voiceOn || !("speechSynthesis" in window)) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "en-GB";
  u.rate = 1.02;
  speechSynthesis.speak(u);
}

function msgHtml(m) {
  const meta = m.meta || {};
  const source = meta.source ? `<div class="meta">${meta.source === "claude" ? "Written by Claude, checked by the safety filter" : meta.source === "safety response" ? "Fixed safety response" : "Written by the built-in coach"}</div>` : "";
  const evidence = m.evidence?.length ? `<details class="why"><summary>Evidence behind this reply</summary><ul>${m.evidence.map((e) => `<li>${esc(e)}</li>`).join("")}</ul></details>` : "";
  return `<div class="msg ${m.role}">${esc(m.text)}${source}${evidence}</div>`;
}

async function renderCoach() {
  renderRail("#/coach");
  const [{ messages }, t, me] = await Promise.all([api("/api/coach"), api("/api/twin"), api("/api/me")]);
  state.me = me;
  const hasTts = "speechSynthesis" in window;
  const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
  const voiceAllowed = me.consent.voice;
  const llmNote = !state.meta.llm_configured
    ? "Using the built-in coach. It works offline and needs no key."
    : me.consent.llm ? "Claude writes replies, and each one is checked before you see it." : "Claude is available. Turn it on under My data.";
  main.innerHTML = `<div class="page">
    ${demoNote()}
    <div class="page-head"><h1>Coach</h1><p class="lede">Ask about a score, why it moved, or what to do next. ${esc(llmNote)}</p></div>
    <div class="coach-grid">
      <div class="chat">
        <div class="chat-log" id="log" aria-live="polite">${messages.length ? messages.map(msgHtml).join("") : `<div class="msg assistant">Hi. I can only speak from your results, so ask me anything about them. If I don't know, I'll say so.</div>`}</div>
        <div class="prompt-chips">${["How am I doing?", "What should I practise next?", "What does the percentage mean?", "I'm feeling tired today"].map((p) => `<button data-q="${esc(p)}">${esc(p)}</button>`).join("")}</div>
        <form class="chat-form" id="chat-form">
          <input id="chat-in" autocomplete="off" maxlength="2000" placeholder="Ask your coach" aria-label="Message to your coach">
          ${Rec && voiceAllowed ? `<button type="button" class="btn" id="mic" title="Speak your question">Speak</button>` : ""}
          <button class="btn primary" type="submit">Send</button>
        </form>
      </div>
      <div>
        ${hasTts ? `<div class="row voice-row"><button class="btn small toggle" id="voice" aria-pressed="${state.voiceOn}" ${voiceAllowed ? "" : "disabled"}>Read replies aloud</button>${voiceAllowed ? "" : `<span class="small muted">Turn on voice under <a href="#/data">My data</a> first.</span>`}</div>` : ""}
        <h2 class="notes-head">Notes for you</h2>
        <div class="insights">${t.insights.map(insightHtml).join("") || `<p class="muted">No notes yet. They appear after your first check-in.</p>`}</div>
        <p class="small muted coach-limits">Coach limits: no health judgements, no promises about the future, and only numbers from your own results. Voice is processed by your browser, and no voice data reaches this app's server.</p>
      </div>
    </div>
  </div>`;
  bindStarters(main);
  const log = document.getElementById("log");
  log.scrollTop = log.scrollHeight;
  const input = document.getElementById("chat-in");
  const sendBtn = document.querySelector("#chat-form [type=submit]");
  const send = (text) => busy(sendBtn, async () => {
    if (!text.trim()) return;
    log.insertAdjacentHTML("beforeend", msgHtml({ role: "user", text }));
    input.value = "";
    /* A placeholder reply shows the coach is working; it is replaced by the answer or an error. */
    log.insertAdjacentHTML("beforeend", `<div class="msg assistant pending" role="status">Checking your results</div>`);
    log.scrollTop = log.scrollHeight;
    try {
      const r = await api("/api/coach", { method: "POST", body: { text } });
      log.querySelector(".pending")?.remove();
      log.insertAdjacentHTML("beforeend", msgHtml({ role: "assistant", text: r.reply, meta: { source: r.source }, evidence: r.evidence }));
      speak(r.reply);
    } catch (err) {
      log.querySelector(".pending")?.remove();
      log.insertAdjacentHTML("beforeend", errorBox(err));
    }
    log.scrollTop = log.scrollHeight;
  });
  document.getElementById("chat-form").onsubmit = (e) => { e.preventDefault(); send(input.value); };
  main.querySelectorAll("[data-q]").forEach((b) => { b.onclick = () => send(b.dataset.q); });
  const v = document.getElementById("voice");
  if (v) v.onclick = () => { state.voiceOn = !state.voiceOn; v.setAttribute("aria-pressed", String(state.voiceOn)); if (!state.voiceOn) speechSynthesis.cancel(); };
  const mic = document.getElementById("mic");
  if (mic) mic.onclick = () => {
    const rec = new Rec();
    rec.lang = "en-GB";
    rec.onresult = (e) => send(e.results[0][0].transcript);
    rec.onerror = () => { mic.textContent = "Speak"; };
    rec.onend = () => { mic.textContent = "Speak"; };
    mic.textContent = "Listening";
    rec.start();
  };
}

/* ---------- AI collaboration lab ---------- */
function scorePanel(score) {
  const measured = score.rounds > 0;
  return `<div class="panel">
    <h2>AI collaboration score</h2>
    ${measured ? `<div class="score-head"><span class="score-big">${fmt(score.score)}</span><span class="muted">of 100</span></div>
      ${Charts.scale({ pct: score.score, low: score.low, high: score.high })}
      <p class="small muted score-note">Likely range ${fmt(score.low)} to ${fmt(score.high)}, from ${score.rounds} of ${score.total_rounds} rounds.</p>` : `<p class="muted score-note">Play a round to get your first score. Scores are measured from what you do, not from what you say about yourself.</p>`}
    <div class="comps">${Object.values(score.components).map((c) => `<div class="comp-row"><span>${esc(c.name)} <span class="small muted">(${Math.round(c.weight * 100)}%)</span></span><div class="comp-bar"><i style="width:${c.score * 100}%"></i></div><span class="num">${c.observations ? fmt(c.score * 100) : "?"}</span></div>`).join("")}</div>
    <p class="formula">Score = 100 x (0.20 C + 0.25 V + 0.20 I + 0.20 A + 0.15 R)</p>
    ${measured ? `<p class="small muted">If the weights shifted, your score would stay between ${fmt(score.weight_low)} and ${fmt(score.weight_high)}. With equal weights it would be ${fmt(score.equal_weights_score)}.</p>` : ""}
    <p class="small muted" style="margin-bottom:0">${esc(score.note)}</p>
  </div>`;
}

async function renderLab() {
  renderRail("#/lab");
  const data = await api("/api/collab/next");
  main.innerHTML = `<div class="page">
    ${demoNote()}
    <div class="page-head"><h1>AI collaboration lab</h1><p class="lede">Work through problems with an AI helper that is sometimes wrong on purpose. Your habits are the thing being measured.</p></div>
    <div class="lab-grid"><div id="round"></div><div id="score">${scorePanel(data.score)}</div></div>
  </div>`;
  if (data.scenario) playRound(data.scenario, data.played, data.total);
  else {
    document.getElementById("round").innerHTML = `<div class="lab-step"><h2>You've played every round</h2><p>Your score is on the right. Play again to see whether your habits have shifted.</p><button class="btn primary" id="again">Play again</button></div>`;
    document.getElementById("again").onclick = async () => { await api("/api/collab/reset", { method: "POST" }); renderLab(); };
  }
}

function playRound(sc, played, total) {
  const box = document.getElementById("round");
  const ev = { flagged_steps: [], refine_count: 0, clarifications: [], free_questions: [], own_answer: null };
  let steps = sc.draft.steps.map((t) => ({ text: t }));
  let conclusion = sc.draft.conclusion;
  let aiVisible = false;
  const notes = [];

  const optionButtons = (name, onPick) => `<div class="options">${sc.options.map((o, i) => `<button class="option" data-${name}="${i}">${esc(o)}</button>`).join("")}</div>`;

  function draw() {
    let html = `<div class="lab-step lab-brief"><p class="small muted round-count">Round ${played + 1} of ${total}</p><h2>${esc(sc.title)}</h2><p>${esc(sc.prompt)}</p></div>`;
    if (!aiVisible) {
      html += `<div class="lab-step"><h3>Your first answer</h3><p class="small muted">You can commit to your own answer before seeing what the AI says, or go straight to the AI.</p>${optionButtons("own")}<p class="skip-ai"><span class="muted">or</span> <button class="btn small" id="ask-ai">Ask the AI straight away</button></p></div>`;
      box.innerHTML = html;
      box.querySelectorAll("[data-own]").forEach((b) => { b.onclick = () => { ev.own_answer = sc.options[+b.dataset.own]; aiVisible = true; draw(); }; });
      document.getElementById("ask-ai").onclick = () => { aiVisible = true; draw(); };
      return;
    }
    if (ev.own_answer) html += `<div class="lab-step small own-answer">Your first answer: <b>${esc(ev.own_answer)}</b></div>`;
    html += `<div class="lab-step"><h3>The AI's reasoning</h3><p class="small muted">Flag any step you think is wrong or unsupported.</p><div class="ai-voice">
      ${steps.map((s, i) => `<div class="ai-step${ev.flagged_steps.includes(i) ? " flagged" : ""}"><div class="txt">${esc(s.text)}</div>${s.fixed ? "" : `<button class="btn small toggle flag" aria-pressed="${ev.flagged_steps.includes(i)}" data-flag="${i}">${ev.flagged_steps.includes(i) ? "Flagged" : "Flag"}</button>`}</div>`).join("")}
      <p class="ai-suggestion"><b>AI's suggestion:</b> ${esc(conclusion)}</p></div>
      ${notes.map((n) => `<p class="small lab-note">${esc(n)}</p>`).join("")}
      <div class="lab-actions">
        <div class="row"><button class="btn small" id="refine">Tell the AI to check this and try again</button></div>
        <p class="small muted">Ask a clarifying question:</p>
        <div class="row">${sc.clarifications.map((q, i) => `<button class="btn small" data-clar="${i}" ${ev.clarifications.includes(i) ? "disabled" : ""}>${esc(q)}</button>`).join("")}</div>
        <form class="row free-q" id="free-q"><input id="free-q-in" maxlength="300" placeholder="Or type your own question" aria-label="Your own question"><button class="btn small">Ask</button></form>
      </div></div>`;
    if (sc.responsible) {
      html += `<div class="lab-step"><h3>Using this responsibly</h3><p>${esc(sc.responsible.q)}</p><div class="options">${sc.responsible.options.map((o, i) => `<button class="option" aria-pressed="${ev.responsible_choice === o}" data-resp="${i}">${esc(o)}</button>`).join("")}</div></div>`;
    }
    html += `<div class="lab-step"><h3>Your final answer</h3>${optionButtons("final")}</div>`;
    box.innerHTML = html;
    box.querySelectorAll("[data-flag]").forEach((b) => {
      b.onclick = () => {
        const i = +b.dataset.flag, at = ev.flagged_steps.indexOf(i);
        if (at >= 0) ev.flagged_steps.splice(at, 1); else ev.flagged_steps.push(i);
        draw();
      };
    });
    const refineBtn = document.getElementById("refine");
    refineBtn.onclick = () => busy(refineBtn, async () => {
      ev.refine_count += 1;
      const r = await api("/api/collab/refine", { method: "POST", body: { scenario_id: sc.id } });
      notes.push(`AI, after checking: ${r.note} ${r.steps.join(" ")} Suggestion now: ${r.conclusion}.`);
      conclusion = r.conclusion;
      draw();
    });
    box.querySelectorAll("[data-clar]").forEach((b) => {
      b.onclick = () => busy(b, async () => {
        const i = +b.dataset.clar;
        ev.clarifications.push(i);
        const r = await api("/api/collab/clarify", { method: "POST", body: { scenario_id: sc.id, index: i } });
        notes.push(`You asked: ${sc.clarifications[i]} AI: ${r.answer}`);
        draw();
      });
    });
    document.getElementById("free-q").onsubmit = (e) => {
      e.preventDefault();
      busy(e.submitter, async () => {
        const text = document.getElementById("free-q-in").value.trim();
        if (!text) return;
        ev.free_questions.push(text);
        const r = await api("/api/collab/clarify", { method: "POST", body: { scenario_id: sc.id } });
        notes.push(`You asked: ${text} AI: ${r.answer}`);
        draw();
      });
    };
    box.querySelectorAll("[data-resp]").forEach((b) => {
      b.onclick = () => { ev.responsible_choice = sc.responsible.options[+b.dataset.resp]; draw(); };
    });
    box.querySelectorAll("[data-final]").forEach((b) => {
      b.onclick = async () => {
        if (sc.responsible && !ev.responsible_choice) {
          const spot = box.querySelector("[data-resp]");
          spot?.focus();
          if (!box.querySelector("#resp-need")) spot?.parentElement.insertAdjacentHTML("beforebegin", `<p id="resp-need" class="error">Choose an option here first.</p>`);
          return;
        }
        ev.final_answer = sc.options[+b.dataset.final];
        await busy(b, async () => {
          const r = await api("/api/collab/round", { method: "POST", body: { scenario_id: sc.id, events: ev } });
          document.getElementById("score").innerHTML = scorePanel(r.score);
          debrief(r.debrief);
        });
      };
    });
  }

  function debrief(d) {
    const parts = [];
    if (d.draft_wrong) parts.push(d.hits ? `You caught ${d.hits} flawed step${d.hits > 1 ? "s" : ""}${d.missed ? ` and missed ${d.missed}` : ""}.` : `The AI's draft was flawed and you didn't flag it.`);
    else parts.push(d.false_alarms ? `The AI was right this time, and you flagged ${d.false_alarms} sound step${d.false_alarms > 1 ? "s" : ""}.` : "The AI was right this time, and you didn't raise a false alarm.");
    if (d.ambiguous) parts.push(d.asked_relevant ? "You asked a useful question before accepting." : "The request was vague, and a clarifying question would have helped.");
    if (d.responsible_ok !== null) parts.push(d.responsible_ok ? "Your responsible-use choice was sound." : "Your responsible-use choice carried some risk.");
    if (d.personal_data?.length) parts.push("You typed personal details into a question. It's safer to leave those out.");
    box.innerHTML = `<div class="lab-step"><h2>${d.final_correct ? "✓ Good final answer" : "✗ Not the strongest answer"}</h2>
      <p>${d.final_correct ? "" : `A stronger answer: ${esc(d.correct)}. `}${esc(parts.join(" "))}</p>
      ${d.steps.map((s) => `<div class="ai-step ${s.flawed ? "flawed-known" : "ok-known"}"><div class="txt">${s.flawed ? "✗" : "✓"} ${esc(s.text)}${s.why ? `<div class="small">${esc(s.why)}</div>` : ""}</div>${s.flagged ? `<span class="chip quiet">you flagged this</span>` : ""}</div>`).join("")}
      <button class="btn primary" id="next-round">Next round</button></div>`;
    document.getElementById("next-round").onclick = renderLab;
    document.getElementById("next-round").focus();
  }
  draw();
}

/* ---------- my data ---------- */
async function renderData() {
  renderRail("#/data");
  const me = await api("/api/me");
  state.me = me;
  main.innerHTML = `<div class="page">
    ${demoNote()}
    <div class="page-head"><h1>My data</h1><p class="lede">You control what's kept, for how long, and when it goes.</p></div>
    <div class="data-grid">
      <div class="panel"><h2>What's stored</h2><p>Your answers, response times, confidence ratings, session summaries, goals and chats with the coach. It is all kept in a local database, against a random ID. There's no name, no email and no account.</p>
        <p>Never collected: camera, microphone recordings, voice prints, face data or location.</p></div>
      <div class="panel"><h2>Choices</h2>
        <div class="choices-list">
          <label><input type="checkbox" id="d-llm" ${me.consent.llm ? "checked" : ""}> <span>Let Claude write coaching messages. It receives summary numbers and your question, with personal details removed. ${state.meta.llm_configured ? "" : `<span class="muted">No API key is set on this server, so this has no effect for now.</span>`}</span></label>
          <label><input type="checkbox" id="d-voice" ${me.consent.voice ? "checked" : ""}> <span>Allow voice coaching, handled in the browser.</span></label>
          <label class="retention"><span>Delete my data after</span><select id="d-ret" aria-label="Delete my data after">${[30, 90, 180, 365].map((d) => `<option value="${d}" ${d === me.retention_days ? "selected" : ""}>${d === 365 ? "1 year" : d + " days"} idle</option>`).join("")}</select></label>
        </div>
        <p class="small muted saved" id="saved" role="status">Consent given ${Charts.fmtDate(me.consent.accepted_at)}.</p>
      </div>
      <div class="panel"><h2>Take it with you</h2><p>Download everything held about you as a JSON file.</p><button class="btn primary" id="export">Download my data</button></div>
      <div class="panel danger-zone"><h2>Delete everything</h2><p>This removes your profile, history, plans and chats from the database for good. It can't be undone.</p>
        <button class="btn danger" id="del">Delete my data</button>
        <div id="del-confirm" class="del-confirm" hidden><p><b>Delete all your data permanently?</b></p><div class="row"><button class="btn danger" id="del-yes">Yes, delete everything</button><button class="btn" id="del-no">Keep my data</button></div></div>
      </div>
    </div>

    <section class="section"><h2>How to read the numbers</h2>
      <div class="docs-grid">
        <div><h3>The percentage</h3><p>The share of a balanced practice set, spanning all difficulty levels, that you'd be expected to solve. It is not a percentile and it doesn't compare you with anyone.</p></div>
        <div><h3>The range</h3><p>A 90% credible interval. It narrows as evidence builds, and widens as your last session recedes, because older evidence says less about you today.</p></div>
        <div><h3>What it can't tell you</h3><p>Difficulty levels are set by design and haven't been calibrated on people yet. Results depend on your device, your language and your day. They say nothing about your health, potential or worth.</p></div>
        <div><h3>Decisions</h3><p>Nothing here should be used to decide anything important about a person. Behaviour signals only adjust pacing and coaching tone, and no decision of any kind uses face or voice.</p></div>
      </div>
    </section>
  </div>`;
  const save = async (patch) => {
    const status = document.getElementById("saved");
    status.textContent = "Saving";
    try {
      await api("/api/consent", { method: "POST", body: patch });
      status.textContent = "Saved.";
    } catch (err) {
      status.textContent = `Not saved: ${err.message}. Try the change again.`;
    }
  };
  document.getElementById("d-llm").onchange = (e) => save({ llm: e.target.checked });
  document.getElementById("d-voice").onchange = (e) => save({ voice: e.target.checked });
  document.getElementById("d-ret").onchange = (e) => save({ retention_days: +e.target.value });
  const exportBtn = document.getElementById("export");
  exportBtn.onclick = () => busy(exportBtn, async () => {
    const data = await api("/api/export");
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "ai4brain-my-data.json";
    a.click();
    URL.revokeObjectURL(url);
  });
  const delBtn = document.getElementById("del");
  delBtn.onclick = () => { document.getElementById("del-confirm").hidden = false; delBtn.hidden = true; document.getElementById("del-yes").focus(); };
  document.getElementById("del-no").onclick = () => { document.getElementById("del-confirm").hidden = true; delBtn.hidden = false; delBtn.focus(); };
  const yesBtn = document.getElementById("del-yes");
  yesBtn.onclick = () => busy(yesBtn, async () => {
    await api("/api/delete", { method: "POST", body: { confirm: "delete" } });
    store.del("profile");
    state.me = null;
    location.hash = "";
  });
}

/* ---------- router ---------- */
async function route() {
  Charts.hideTip();
  Tasks.detach();
  activeRun += 1;
  try {
    if (!state.meta) state.meta = await api("/api/meta");
    if (!store.get("profile")) return renderWelcome();
    if (!state.me) {
      try { state.me = await api("/api/me"); }
      catch { store.del("profile"); return renderWelcome(); }
    }
    const parts = location.hash.replace(/^#\//, "").split("/");
    switch (parts[0]) {
      case "practice": await renderPractice(); break;
      case "plan": await renderPlan(); break;
      case "coach": await renderCoach(); break;
      case "lab": await renderLab(); break;
      case "data": await renderData(); break;
      case "skill": await renderSkill(parts[1]); break;
      case "session": await runSession(parts[1], parts[2] || "assess"); break;
      default: await renderTwin();
    }
    window.scrollTo(0, 0);
  } catch (err) {
    main.innerHTML = `<div class="page">${errorBox(err)}<a class="btn" href="#/twin">Back to your twin</a></div>`;
  }
}
window.addEventListener("hashchange", route);
route();
