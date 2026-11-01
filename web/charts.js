/* Hand-drawn SVG charts. No external libraries, so the app works offline. */
const Charts = (() => {
  const INK = "#0b2239", INK2 = "#3f5870", INK3 = "#6f8498", GRID = "#d3dfe9";
  const BAND = "#a9cdec", SIGNAL = "#1468b8", DEEP = "#0e4f8f", EMBER = "#c9570f";

  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = (x) => Math.round(x);

  function showTip(evt, html) {
    const tip = document.getElementById("tooltip");
    tip.innerHTML = html;
    tip.hidden = false;
    const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
    let x = evt.clientX + pad, y = evt.clientY + pad;
    if (x + w > window.innerWidth - 8) x = evt.clientX - w - pad;
    if (y + h > window.innerHeight - 8) y = evt.clientY - h - pad;
    tip.style.left = x + "px";
    tip.style.top = y + "px";
  }
  function hideTip() { document.getElementById("tooltip").hidden = true; }

  /* The Brain Twin radar. The ring between low and high is the uncertainty; the line is the estimate. */
  function radar(rows, opts = {}) {
    const size = opts.size || 560, cx = size / 2, cy = size / 2 + 2, R = size * 0.34;
    const n = rows.length;
    const pt = (i, v) => {
      const a = -Math.PI / 2 + (i * 2 * Math.PI) / n;
      return [cx + (R * v * Math.cos(a)) / 100, cy + (R * v * Math.sin(a)) / 100];
    };
    const poly = (vals) => vals.map((v, i) => pt(i, v).map((x) => x.toFixed(1)).join(",")).join(" ");
    let svg = `<svg viewBox="0 0 ${size} ${size + 4}" role="img" aria-label="${esc(opts.label || "Radar chart of estimated percentage and uncertainty for each skill")}">`;
    for (const ring of [25, 50, 75, 100]) {
      svg += `<polygon points="${poly(rows.map(() => ring))}" fill="none" stroke="${GRID}" stroke-width="1"/>`;
      const p = pt(0, ring);
      svg += `<text x="${p[0] + 4}" y="${p[1] + 11}" font-size="10.5" fill="${INK3}">${ring}</text>`;
    }
    rows.forEach((_, i) => {
      const p = pt(i, 100);
      svg += `<line x1="${cx}" y1="${cy}" x2="${p[0]}" y2="${p[1]}" stroke="${GRID}" stroke-width="1"/>`;
    });
    const outer = rows.map((r) => r.high), inner = rows.map((r) => r.low);
    const pathOf = (vals) => "M" + vals.map((v, i) => pt(i, v).map((x) => x.toFixed(1)).join(" ")).join("L") + "Z";
    svg += `<path d="${pathOf(outer)} ${pathOf(inner)}" fill="${BAND}" fill-opacity=".58" fill-rule="evenodd" stroke="none"/>`;
    svg += `<polygon points="${poly(rows.map((r) => r.pct))}" fill="none" stroke="${DEEP}" stroke-width="2.25" stroke-linejoin="round"/>`;
    rows.forEach((r, i) => {
      const p = pt(i, r.pct);
      const empty = r.n_trials === 0;
      svg += `<circle cx="${p[0]}" cy="${p[1]}" r="${empty ? 3.5 : 4.5}" fill="${empty ? "#fff" : DEEP}" stroke="${empty ? INK3 : "#fff"}" stroke-width="1.5"/>`;
      const a = -Math.PI / 2 + (i * 2 * Math.PI) / n;
      const lx = cx + (R + 16) * Math.cos(a), ly = cy + (R + 16) * Math.sin(a);
      const anchor = Math.abs(Math.cos(a)) < 0.2 ? "middle" : Math.cos(a) > 0 ? "start" : "end";
      const words = r.name.split(" ");
      const lines = words.length > 1 ? [words[0], words.slice(1).join(" ")] : [r.name];
      const dy = Math.sin(a) < -0.5 ? -(lines.length - 1) * 14 : Math.sin(a) > 0.5 ? 10 : 4 - (lines.length - 1) * 7;
      svg += `<text x="${lx}" y="${ly + dy}" text-anchor="${anchor}" font-size="13.5" fill="${INK}" font-weight="500">` +
        lines.map((l, k) => `<tspan x="${lx}" dy="${k ? 14 : 0}">${esc(l)}</tspan>`).join("") + `</text>`;
      const big = pt(i, 100);
      svg += `<circle class="hit" data-i="${i}" cx="${(p[0] + big[0]) / 2}" cy="${(p[1] + big[1]) / 2}" r="${Math.max(18, R * 0.3)}" fill="transparent"/>`;
    });
    svg += `</svg>`;
    return svg;
  }

  function bindRadar(el, rows) {
    el.querySelectorAll(".hit").forEach((h) => {
      const r = rows[+h.dataset.i];
      const label = r.n_trials === 0
        ? `<b>${esc(r.name)}</b><br>No evidence yet`
        : `<b>${esc(r.name)}</b><br>About ${fmt(r.pct)}%, range ${fmt(r.low)} to ${fmt(r.high)}<br>${r.n_trials} items`;
      h.addEventListener("mousemove", (e) => showTip(e, label));
      h.addEventListener("mouseleave", hideTip);
    });
  }

  /* Progress curve: estimate line, uncertainty ribbon and, when offered, a projection fan. */
  function progress(points, opts = {}) {
    const W = opts.width || 320, H = opts.height || 150;
    const m = { l: 28, r: 8, t: 8, b: 20 };
    const proj = opts.projection && opts.projection.available ? opts.projection.ranges : null;
    const ts = points.map((p) => +new Date(p.at));
    const end = proj ? +new Date(proj[proj.length - 1].at) : Math.max(...ts);
    const start = Math.min(...ts);
    const span = Math.max(end - start, 86400000);
    const x = (t) => m.l + ((t - start) / span) * (W - m.l - m.r);
    const y = (v) => m.t + (1 - v / 100) * (H - m.t - m.b);
    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(opts.label || "Progress over time")}">`;
    for (const v of [0, 50, 100]) {
      svg += `<line x1="${m.l}" x2="${W - m.r}" y1="${y(v)}" y2="${y(v)}" stroke="${v === 0 ? "#b4c6d6" : GRID}" stroke-width="1"/>`;
      svg += `<text x="${m.l - 5}" y="${y(v) + 3.5}" font-size="10" text-anchor="end" fill="${INK3}">${v}</text>`;
    }
    const fd = (t) => new Date(t).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
    svg += `<text x="${m.l}" y="${H - 5}" font-size="10" fill="${INK3}">${fd(start)}</text>`;
    svg += `<text x="${W - m.r}" y="${H - 5}" font-size="10" text-anchor="end" fill="${INK3}">${fd(end)}</text>`;
    if (points.length) {
      const up = points.map((p) => `${x(+new Date(p.at)).toFixed(1)},${y(p.high).toFixed(1)}`);
      const down = points.slice().reverse().map((p) => `${x(+new Date(p.at)).toFixed(1)},${y(p.low).toFixed(1)}`);
      svg += `<polygon points="${up.concat(down).join(" ")}" fill="${BAND}" fill-opacity=".55"/>`;
      if (proj) {
        const last = points[points.length - 1];
        const startPt = { at: opts.now || last.at, low90: last.low, high90: last.high, low50: last.pct, high50: last.pct, pct: last.pct };
        const seq = [startPt].concat(proj);
        const band = (lowK, highK) => seq.map((p) => `${x(+new Date(p.at)).toFixed(1)},${y(p[highK]).toFixed(1)}`)
          .concat(seq.slice().reverse().map((p) => `${x(+new Date(p.at)).toFixed(1)},${y(p[lowK]).toFixed(1)}`)).join(" ");
        svg += `<polygon points="${band("low90", "high90")}" fill="${EMBER}" fill-opacity=".13"/>`;
        svg += `<polygon points="${band("low50", "high50")}" fill="${EMBER}" fill-opacity=".2"/>`;
        svg += `<polyline points="${seq.map((p) => `${x(+new Date(p.at)).toFixed(1)},${y(p.pct).toFixed(1)}`).join(" ")}" fill="none" stroke="${EMBER}" stroke-width="1.5" stroke-dasharray="4 3"/>`;
      }
      svg += `<polyline points="${points.map((p) => `${x(+new Date(p.at)).toFixed(1)},${y(p.pct).toFixed(1)}`).join(" ")}" fill="none" stroke="${DEEP}" stroke-width="2" stroke-linejoin="round"/>`;
      points.forEach((p) => {
        svg += `<circle cx="${x(+new Date(p.at)).toFixed(1)}" cy="${y(p.pct).toFixed(1)}" r="${points.length > 25 ? 1.6 : 2.8}" fill="${DEEP}"/>`;
      });
    }
    svg += `<rect class="hover-layer" x="${m.l}" y="${m.t}" width="${W - m.l - m.r}" height="${H - m.t - m.b}" fill="transparent"/>`;
    svg += `<line class="crosshair" x1="0" x2="0" y1="${m.t}" y2="${H - m.b}" stroke="${INK2}" stroke-width="1" visibility="hidden"/>`;
    svg += `</svg>`;
    return svg;
  }

  function bindProgress(el, points, opts = {}) {
    const svg = el.querySelector("svg");
    if (!svg || !points.length) return;
    const W = opts.width || 320;
    const m = { l: 28, r: 8 };
    const proj = opts.projection && opts.projection.available ? opts.projection.ranges : [];
    const all = points.map((p) => ({ at: +new Date(p.at), html: `<b>${fmtDate(p.at)}</b><br>About ${fmt(p.pct)}%, range ${fmt(p.low)} to ${fmt(p.high)}` }))
      .concat(proj.map((p) => ({ at: +new Date(p.at), html: `<b>In ${p.days} days, if practice continues</b><br>Plausible range ${fmt(p.low90)} to ${fmt(p.high90)}` })));
    const start = Math.min(...all.map((a) => a.at)), end = Math.max(...all.map((a) => a.at));
    const span = Math.max(end - start, 86400000);
    const toX = (t) => m.l + ((t - start) / span) * (W - m.l - m.r);
    const cross = svg.querySelector(".crosshair");
    const layer = svg.querySelector(".hover-layer");
    layer.addEventListener("mousemove", (e) => {
      const box = svg.getBoundingClientRect();
      const px = ((e.clientX - box.left) / box.width) * W;
      let best = all[0], bestD = Infinity;
      for (const a of all) {
        const d = Math.abs(toX(a.at) - px);
        if (d < bestD) { bestD = d; best = a; }
      }
      cross.setAttribute("x1", toX(best.at));
      cross.setAttribute("x2", toX(best.at));
      cross.setAttribute("visibility", "visible");
      showTip(e, best.html);
    });
    layer.addEventListener("mouseleave", () => { cross.setAttribute("visibility", "hidden"); hideTip(); });
  }

  function fmtDate(iso) {
    return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  }

  /* One-hue sequential ramp, light to dark. */
  const RAMP = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"];
  function heatColor(v) { return RAMP[Math.max(0, Math.min(RAMP.length - 1, Math.round((v / 100) * (RAMP.length - 1))))]; }
  function heatInk(v) { return v >= 55 ? "#fff" : INK; }

  function heatmap(rowsMeta, columns, valueOf, tipOf) {
    let html = `<div class="heat" style="grid-template-columns:minmax(120px,auto) repeat(${columns.length},minmax(30px,1fr))">`;
    html += `<div></div>` + columns.map((c) => `<div class="hd">${esc(c)}</div>`).join("");
    for (const row of rowsMeta) {
      html += `<div class="lab">${esc(row.name)}</div>`;
      columns.forEach((_, i) => {
        const v = valueOf(row.key, i);
        if (v === null || v === undefined) html += `<div class="cell empty" data-tip="${esc(tipOf(row, i, null))}"></div>`;
        else html += `<div class="cell" style="background:${heatColor(v)};color:${heatInk(v)}" data-tip="${esc(tipOf(row, i, v))}">${fmt(v)}</div>`;
      });
    }
    return html + `</div>`;
  }

  function bindHeat(el) {
    el.querySelectorAll(".cell").forEach((c) => {
      c.addEventListener("mousemove", (e) => showTip(e, esc(c.dataset.tip)));
      c.addEventListener("mouseleave", hideTip);
    });
  }

  function shapeGrid(cells, size, px = 96, color = SIGNAL) {
    const u = px / size;
    let svg = `<svg class="shape-grid" width="${px}" height="${px}" viewBox="0 0 ${px} ${px}" aria-hidden="true">`;
    for (let i = 0; i <= size; i++) {
      svg += `<line x1="0" x2="${px}" y1="${i * u}" y2="${i * u}" stroke="${GRID}"/><line y1="0" y2="${px}" x1="${i * u}" x2="${i * u}" stroke="${GRID}"/>`;
    }
    for (const [r, c] of cells) svg += `<rect x="${c * u + 1}" y="${r * u + 1}" width="${u - 2}" height="${u - 2}" fill="${color}" rx="1.5"/>`;
    return svg + `</svg>`;
  }

  function rangeRow(row, opts = {}) {
    const none = row.n_trials === 0;
    const left = Math.max(0, row.low), width = Math.max(1, row.high - row.low);
    const name = esc(row.name);
    const track = `<div class="range-track" aria-hidden="true">
        <div class="range-band ${none ? "none" : ""}" style="left:${left}%;width:${width}%"></div>
        ${none ? "" : `<div class="range-dot" style="left:${row.pct}%"></div>`}
      </div>`;
    const val = none
      ? `<div class="range-val"><b>?</b><span>no evidence</span></div>`
      : `<div class="range-val"><b>${fmt(row.pct)}%</b><span>${fmt(row.low)} to ${fmt(row.high)}</span></div>`;
    const inner = `<div class="range-name">${name}<small>${esc(row.evidence || "")}</small></div>${track}${val}`;
    if (opts.href) return `<a class="range-row" href="${opts.href}" aria-label="${name}: ${none ? "no evidence yet" : `about ${fmt(row.pct)} percent, range ${fmt(row.low)} to ${fmt(row.high)}`}">${inner}</a>`;
    return `<div class="range-row">${inner}</div>`;
  }

  return { radar, bindRadar, progress, bindProgress, heatmap, bindHeat, shapeGrid, rangeRow, fmtDate, esc, fmt, showTip, hideTip };
})();
