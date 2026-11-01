/* Session runner: renders each item kind, measures response time, tracks focus loss. */
const Tasks = (() => {
  const { esc, shapeGrid } = Charts;
  const ARROW = { left: "←", right: "→" };
  let focusLost = false;
  let cleanup = [];

  const onFocusChange = () => { if (document.hidden) focusLost = true; };
  const onBlur = () => { focusLost = true; };

  function addCleanup(fn) { cleanup.push(fn); }
  function runCleanup() { cleanup.forEach((f) => f()); cleanup = []; }

  function listenKeys(handler) {
    window.addEventListener("keydown", handler);
    addCleanup(() => window.removeEventListener("keydown", handler));
  }

  function deadlineBar(stage, ms) {
    const bar = document.createElement("div");
    bar.className = "deadline";
    bar.innerHTML = "<div></div>";
    stage.appendChild(bar);
    const inner = bar.firstChild;
    inner.style.transition = `transform ${ms}ms linear`;
    requestAnimationFrame(() => requestAnimationFrame(() => { inner.style.transform = "scaleX(0)"; }));
  }

  /* Two-choice speeded items. Left and right arrows map to the two on-screen buttons. */
  function renderChoice(stage, item, submit) {
    const p = item.payload;
    let stim = "";
    if (p.stimulus_type === "arrows") stim = `<div class="stimulus huge" aria-label="Arrows: ${p.arrows.join(", ")}">${p.arrows.map((d) => ARROW[d]).join("")}</div>`;
    else if (p.stimulus_type === "strings") stim = `<div><div class="stimulus mono">${esc(p.left)}</div><div class="stimulus mono">${esc(p.right)}</div></div>`;
    else if (p.stimulus_type === "symbol_key") {
      stim = `<div class="row" style="justify-content:center">${p.key.map((k) => `<span class="chip quiet" style="font-size:1rem">${esc(k.s)} = ${k.d}</span>`).join("")}</div>
              <div class="stimulus">${esc(p.probe.s)} = ${p.probe.d}</div>`;
    } else if (p.stimulus_type === "number") stim = `<div class="cue">${esc(p.cue)}</div><div class="stimulus huge">${p.number}</div>`;
    else if (p.stimulus_type === "figure") {
      const fill = p.colour === "blue" ? "#1468b8" : "#e46f1f";
      const shape = p.shape === "circle" ? `<circle cx="50" cy="50" r="42" fill="${fill}"/>` : `<rect x="10" y="10" width="80" height="80" rx="4" fill="${fill}"/>`;
      stim = `<div class="cue">${esc(p.cue)}</div><svg width="110" height="110" viewBox="0 0 100 100" role="img" aria-label="${p.colour} ${p.shape}">${shape}</svg>`;
    }
    stage.innerHTML = stim;
    deadlineBar(stage, item.deadline_ms);
    const row = document.createElement("div");
    row.className = "choices";
    p.choices.forEach((c, i) => {
      const b = document.createElement("button");
      b.className = "btn";
      b.textContent = (i === 0 ? "← " : "") + c.label + (i === 1 ? " →" : "");
      b.dataset.key = c.key;
      b.onclick = () => submit(c.key);
      row.appendChild(b);
    });
    stage.appendChild(row);
    listenKeys((e) => {
      if (e.key === "ArrowLeft") { e.preventDefault(); submit(p.choices[0].key); }
      if (e.key === "ArrowRight") { e.preventDefault(); submit(p.choices[1].key); }
    });
    const timer = setTimeout(() => submit(null), item.deadline_ms);
    addCleanup(() => clearTimeout(timer));
  }

  function renderGoNoGo(stage, item, submit) {
    const p = item.payload;
    stage.innerHTML = `<div class="key-hint">Press Space or tap, unless you see ${esc(p.hold)}</div><div class="go-letter">${esc(p.letter)}</div>`;
    deadlineBar(stage, item.deadline_ms);
    const b = document.createElement("button");
    b.className = "btn big";
    b.textContent = "Press";
    b.onclick = () => submit("go");
    stage.appendChild(b);
    listenKeys((e) => { if (e.code === "Space") { e.preventDefault(); submit("go"); } });
    const timer = setTimeout(() => submit(null), item.deadline_ms);
    addCleanup(() => clearTimeout(timer));
  }

  function renderRecall(stage, item, submit, setClock) {
    const p = item.payload;
    stage.innerHTML = `<div class="key-hint">${esc(item.prompt)}</div><div class="digit-show" aria-live="off"></div>`;
    const show = stage.querySelector(".digit-show");
    let i = 0, alive = true;
    addCleanup(() => { alive = false; });
    const step = () => {
      if (!alive) return;
      if (i >= p.sequence.length) {
        show.remove();
        const input = document.createElement("input");
        input.className = "recall-input";
        input.inputMode = "numeric";
        input.autocomplete = "off";
        input.setAttribute("aria-label", item.prompt);
        input.maxLength = 20;
        const form = document.createElement("form");
        form.appendChild(input);
        form.onsubmit = (e) => { e.preventDefault(); submit(input.value.trim()); };
        stage.appendChild(form);
        const b = document.createElement("button");
        b.className = "btn primary";
        b.textContent = "Submit";
        b.onclick = () => submit(input.value.trim());
        stage.appendChild(b);
        input.focus();
        setClock();
        const timer = setTimeout(() => submit(input.value.trim() || null), item.deadline_ms);
        addCleanup(() => clearTimeout(timer));
        return;
      }
      show.textContent = p.sequence[i++];
      setTimeout(() => {
        if (!alive) return;
        show.textContent = "";
        setTimeout(step, 180);
      }, p.show_ms);
    };
    setTimeout(step, 450);
  }

  function renderMcq(stage, item, submit) {
    const p = item.payload;
    let html = `<div class="mcq-prompt ${p.big_prompt ? "big" : ""}">${esc(item.prompt)}</div>`;
    if (p.grid_options) {
      html += `<div class="target-shape"><span class="key-hint">Target</span>${shapeGrid(p.target, p.grid_size, 120, "#0b2239")}</div>`;
    }
    stage.innerHTML = html;
    const wrap = document.createElement("div");
    wrap.className = "options" + (p.grid_options ? " shapes" : p.options.length === 4 && !p.option_labels && !p.fixed_order ? " grid2" : "");
    const opts = p.grid_options
      ? p.grid_options.map((o) => ({ value: o.id, html: shapeGrid(o.cells, p.grid_size, 96), label: `Option ${+o.id + 1}` }))
      : p.options.map((o) => ({ value: o, html: esc(p.option_labels ? `${o}: ${p.option_labels[o]}` : o), label: String(o) }));
    let picked = null;
    const buttons = opts.map((o, i) => {
      const b = document.createElement("button");
      b.className = "option" + (p.grid_options ? " shape" : "");
      b.setAttribute("aria-pressed", "false");
      b.setAttribute("aria-label", o.label);
      b.dataset.value = o.value;
      b.innerHTML = (p.grid_options ? "" : `<span class="opt-key">${i + 1}</span>`) + o.html;
      b.onclick = () => choose(o.value, b);
      wrap.appendChild(b);
      return b;
    });
    stage.appendChild(wrap);
    const confBox = document.createElement("div");
    confBox.className = "confidence";
    confBox.hidden = true;
    stage.appendChild(confBox);

    const c = item.c || 0;
    const levels = [
      { label: "Guessing", value: Math.max(c, 0.25) },
      { label: "Fairly sure", value: (Math.max(c, 0.25) + 1) / 2 },
      { label: "Certain", value: 0.97 },
    ];
    let clockStop = null;
    function choose(value, btn) {
      picked = value;
      clockStop = performance.now();
      buttons.forEach((b) => b.setAttribute("aria-pressed", b === btn ? "true" : "false"));
      if (!item.ask_confidence) { submit(value); return; }
      confBox.hidden = false;
      confBox.innerHTML = `<div class="key-hint">How sure are you?</div>`;
      const row = document.createElement("div");
      row.className = "row";
      levels.forEach((l) => {
        const cb = document.createElement("button");
        cb.className = "btn";
        cb.textContent = l.label;
        cb.dataset.conf = l.value;
        cb.onclick = () => submit(picked, l.value, clockStop);
        row.appendChild(cb);
      });
      if (!item.confidence_required) {
        const skip = document.createElement("button");
        skip.className = "btn";
        skip.textContent = "Skip";
        skip.onclick = () => submit(picked, null, clockStop);
        row.appendChild(skip);
      }
      confBox.appendChild(row);
    }
    listenKeys((e) => {
      const n = parseInt(e.key, 10);
      if (!n) return;
      if (picked === null && n <= opts.length) buttons[n - 1].click();
      else if (picked !== null && n <= 3) confBox.querySelectorAll("button")[n - 1]?.click();
    });
    const timer = setTimeout(() => submit(picked), item.deadline_ms);
    addCleanup(() => clearTimeout(timer));
  }

  function renderFreeText(stage, item, submit) {
    const p = item.payload;
    stage.innerHTML = `<div class="mcq-prompt big">${esc(item.prompt)}</div><div class="timer" aria-live="off"></div>`;
    const clock = stage.querySelector(".timer");
    let field;
    if (p.multiline) {
      field = document.createElement("textarea");
      field.className = "ideas";
      field.placeholder = "One idea per line";
    } else {
      field = document.createElement("input");
      field.className = "word-input";
      field.autocomplete = "off";
      field.placeholder = "One word";
    }
    field.setAttribute("aria-label", item.prompt);
    field.maxLength = 2000;
    stage.appendChild(field);
    const b = document.createElement("button");
    b.className = "btn primary";
    b.textContent = p.multiline ? "I'm done" : "Submit";
    b.onclick = () => submit(field.value);
    stage.appendChild(b);
    if (!p.multiline) field.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); submit(field.value); } });
    field.focus();
    let left = p.seconds;
    clock.textContent = `${left} s left`;
    const iv = setInterval(() => {
      left -= 1;
      clock.textContent = `${left} s left`;
      if (left <= 0) submit(field.value);
    }, 1000);
    addCleanup(() => clearInterval(iv));
  }

  /* Runs one item. Resolves with the data the server needs. */
  function runItem(stage, item) {
    return new Promise((resolve) => {
      runCleanup();
      focusLost = false;
      let start = performance.now(), done = false;
      const submit = (response, confidence = null, stopAt = null) => {
        if (done) return;
        done = true;
        const rt = (stopAt || performance.now()) - start;
        runCleanup();
        resolve({ response, rt_ms: Math.round(rt), focus_lost: focusLost, confidence });
      };
      const setClock = () => { start = performance.now(); focusLost = false; };
      stage.dataset.kind = item.kind;
      stage.dataset.task = item.task;
      if (item.kind === "choice") renderChoice(stage, item, submit);
      else if (item.kind === "go_nogo") renderGoNoGo(stage, item, submit);
      else if (item.kind === "recall") renderRecall(stage, item, submit, setClock);
      else if (item.kind === "mcq") renderMcq(stage, item, submit);
      else renderFreeText(stage, item, submit);
      start = performance.now();
    });
  }

  function attach() {
    document.addEventListener("visibilitychange", onFocusChange);
    window.addEventListener("blur", onBlur);
  }
  function detach() {
    document.removeEventListener("visibilitychange", onFocusChange);
    window.removeEventListener("blur", onBlur);
    runCleanup();
  }

  return { runItem, attach, detach };
})();
