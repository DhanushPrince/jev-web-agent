const $ = (id) => document.getElementById(id);
const token = document.querySelector('meta[name="demo-token"]').content;
let state = null,
  busy = false,
  automatic = false;
const goals = {
  flights: 'Find one-way flights from Zurich to London on September 20, 2026, for one adult in economy. Stop when matching flight options are visible. Do not select or book a flight.',
  travel: 'Find a Design stay in Lisbon with Free cancellation and open Casa Flora.',
  research:
    "Open the article about using finite choices to control browser agents.",
  'google-blog':
    'Search Google for "jev", then open the first blog/article result link. Stop as soon as that result\'s page has opened. Do not open any other result.',
  'amazon-nb413':
    'Search for "New Balance Men 413 Running Shoes black", then open the first New Balance 413 black running shoe result. Stop as soon as that product page has opened. Do not add to cart or buy.',
};
// Presets that carry both a start URL and a goal. They run through the same
// backend path as Custom URL (the "config" scenario), which accepts a URL.
const presets = {
  'google-blog': { url: 'https://www.google.com/' },
  'amazon-nb413': { url: 'https://www.amazon.in/' },
};
const escape = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const percent = (value) => `${(value * 100).toFixed(value < 0.01 ? 1 : 0)}%`;
async function call(name, body = {}) {
  const response = await fetch(`/api/${name}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Demo-Token": token },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw Error(data.error || "Request failed");
  state = data;
  render();
  return data;
}
function controls() {
  const live = state?.page && !["done", "blocked"].includes(state.status);
  $("start").disabled = busy;
  $("scenario").disabled = busy;
  $("goal").disabled = busy;
  $("choose").disabled = busy || !live;
  $("execute").disabled = busy || !state?.decision || !live;
  $("auto").disabled = busy || !live;
  $("auto").hidden = automatic;
  $("stop").hidden = !automatic;
  $("download").disabled = !state?.history?.length;
}
async function perform(fn, label) {
  if (busy) return;
  busy = true;
  $("error").hidden = true;
  controls();
  $("status").textContent = label;
  try {
    await fn();
  } catch (error) {
    automatic = false;
    try {
      state = await fetch("/api/state").then((r) => r.json());
      render();
    } catch {
      /* Preserve the original failure if the server disconnected. */
    }
    $("error").textContent = error.message;
    $("error").hidden = false;
    $("status").textContent = "Paused · needs attention";
  } finally {
    busy = false;
    controls();
  }
}
function render() {
  if (!state) return;
  $("helper").textContent = `Text helper · ${state.text_model}`;
  $("plan").innerHTML = (state.plan || [])
    .map(
      (goal, i) =>
        `<div class="plan-step ${i === state.plan_index ? "current" : ""}"><span>${i < state.plan_index ? "✓" : i + 1}</span>${escape(goal)}</div>`,
    )
    .join("");
  const page = state.page,
    d =
      state.decision ||
      (state.status === "done" ? state.decisions?.at(-1) : null);
  const labels = {
    idle: "Ready to explore",
    ready: "Page observed · ready for a decision",
    predicted: "Choice ready · inspect or execute",
    done: "Jev reports complete · inspect the page",
    blocked: "Stopped · no supported next action",
  };
  $("status").textContent = labels[state.status] || state.status;
  if (!page) {
    controls();
    return;
  }
  $("empty").hidden = true;
  $("screenshot").hidden = false;
  $("screenshot").src = `data:image/jpeg;base64,${page.screenshot}`;
  $("url").textContent = page.url;
  $("page-title").textContent = page.title;
  $("action-count").textContent = `${state.elements.length} elements`;
  const chosen = page.actions.find((a) => a.id === d?.choice);
  $("choice-title").textContent = d
    ? chosen?.label || d.choice
    : "Choose an action";
  $("latency").textContent = d ? `${d.latency_ms} ms` : "—";
  $("confidence").textContent = d?.target_confidence != null ? percent(d.target_confidence) : "—";
  $("completion").textContent = d ? d.operation : "—";
  $("ranking-note").textContent = d ? "Ranked by Jev" : "Unranked";
  const op = Object.entries(d?.operation_probabilities || {}).sort((a,b)=>b[1]-a[1]);
  $("operation-choices").innerHTML = op.map(([name,p]) =>
    `<span class="operation-choice ${name === d.operation ? 'best' : ''}">${escape(name)} <b>${percent(p)}</b></span>`).join('');
  const probability = e => d?.target_probabilities[e.index] ??
    Math.max(-1, ...(e.options || []).map(o=>d?.target_probabilities[o.index] ?? -1));
  const selectedIndex = d?.target?.split(':')[0];
  const elements = [...state.elements];
  if (d) elements.sort((a,b)=>probability(b)-probability(a));
  $("choices").innerHTML = elements.map(e => {
    const p = probability(e);
    return `<div class="choice ${selectedIndex === e.index ? 'best' : ''}" data-action="${escape(e.index)}"><span class="choice-id">[${escape(e.index)}]</span><div class="choice-label">${escape(e.label)}<small>${escape(e.role)} · ${escape(e.operations.join(' / '))}${e.value ? ' · '+escape(e.value) : ''}${e.checked !== undefined ? ' · checked '+escape(e.checked) : ''}</small>${p >= 0 ? `<div class="bar" style="--probability:${p*100}%"></div>` : ''}</div><span class="probability">${p >= 0 ? percent(p) : '—'}</span></div>`;
  }).join('');
  const targets = new Map();
  for (const a of page.actions) if (a.rect && !targets.has(a.node)) targets.set(a.node, a);
  $("targets").innerHTML = [...targets.values()].map((a,i) => {
    const index=String(i+1);
    return `<div class="target ${index === selectedIndex ? 'selected' : ''}" data-action="${index}" style="left:${100*a.rect.x/page.w}%;top:${100*a.rect.y/page.h}%;width:${100*a.rect.w/page.w}%;height:${100*a.rect.h/page.h}%"><span>${index}</span></div>`;
  }).join('');
  $("targets").hidden = !$("overlays").checked;
  const hasHistory = state.history.length > 0;
  $("history").hidden = hasHistory;
  $("history-table").hidden = !hasHistory;
  $("history-body").innerHTML = state.history
    .map((h) => {
      const op = escape(h.operation || h.kind || "—");
      const target = escape(h.action || "—");
      const conf = h.confidence != null ? percent(h.confidence) : "—";
      const jevMs = h.latency_ms != null ? `${h.latency_ms}` : "—";
      const mText = h.text ? `“${escape(h.text)}”` : "—";
      const mMs = h.text ? `${h.text_latency_ms || 0}` : "—";
      const result = h.page_changed ? "Page changed" : "No change";
      // Full operation Choice distribution (Σp = 1); winner highlighted.
      const dist = Object.entries(h.operation_probabilities || {}).sort((a, b) => b[1] - a[1]);
      const distHtml = dist.length
        ? `<div class="op-dist">${dist
            .map(
              ([name, p]) =>
                `<span class="op-chip ${name === h.operation ? "best" : ""}">${escape(name)} ${percent(p)}</span>`,
            )
            .join("")}</div>`
        : "";
      return (
        `<tr><td>${String(h.step).padStart(2, "0")}</td>` +
        `<td><b>${op}</b>${distHtml}</td>` +
        `<td class="cell-target" title="${target}">${target}</td>` +
        `<td>${conf}</td>` +
        `<td>${jevMs}</td>` +
        `<td>${mText}</td>` +
        `<td>${mMs}</td>` +
        `<td>${result}</td></tr>`
      );
    })
    .join("");
  $("step-count").textContent = `${state.history.length} actions · ${(state.elapsed_ms / 1000).toFixed(2)} s`;
  $("model-state").textContent = JSON.stringify(
    d?.request || {
      goal: state.goal,
      url: page.url,
      text: page.text,
      actions: page.actions.map(({ rect, node, ...rest }) => rest),
    },
    null,
    2,
  );
  renderIO(d);
  controls();
}
function renderHead(name, q) {
  // Normalize criteria of a choice/score/noul question into {label, when} rows,
  // shown as "Returned as" / "Choose when" like the console playground.
  const type = q?.type || "choice";
  const crit = q?.criteria;
  let rows = [];
  if (Array.isArray(crit)) {
    // score: ordered array of level descriptions.
    rows = crit.map((desc, i) => ({ label: String(i), when: describe(desc) }));
  } else if (crit && typeof crit === "object") {
    // choice / noul: map of option -> description (may be null/string/object).
    rows = Object.entries(crit).map(([k, v]) => ({ label: k, when: describe(v) }));
  }
  const rowsHtml = rows.length
    ? rows
        .map(
          (r) =>
            `<div class="head-opt"><div class="head-opt-name">Returned as: ${escape(r.label)}</div>` +
            `<div class="head-opt-when">Choose when: ${escape(r.when || "—")}</div></div>`,
        )
        .join("")
    : '<div class="muted">no options</div>';
  // Question (instructions): can be a string, or {goal, rules, operation}, or array.
  const instr = q?.instructions;
  let questionHtml = "";
  if (instr) {
    if (typeof instr === "string") {
      questionHtml = `<div class="head-q"><span>Question</span> ${escape(instr)}</div>`;
    } else if (typeof instr === "object") {
      const goal = instr.goal ? `<div class="head-q"><span>Goal</span> ${escape(instr.goal)}</div>` : "";
      const op = instr.operation ? `<div class="head-q"><span>Operation</span> ${escape(instr.operation)}</div>` : "";
      const rules = instr.rules
        ? `<div class="head-q"><span>Rules</span> ${escape(
            Array.isArray(instr.rules) ? instr.rules.join(" | ") : instr.rules,
          )}</div>`
        : "";
      questionHtml = goal + op + rules;
    }
  }
  return (
    `<details class="head"><summary><b>${escape(name)}</b>` +
    `<span class="pill">${escape(type)}</span><span class="pill">${rows.length} option${rows.length === 1 ? "" : "s"}</span></summary>` +
    `<div class="head-body">${questionHtml}<div class="io-subhead">Options</div>${rowsHtml}</div></details>`
  );
}
function describe(v) {
  if (v == null) return "";
  if (typeof v === "string") return v;
  if (typeof v === "object") {
    // Target-head criteria look like {element, current_value, role, ...}.
    if (v.element || v.role) {
      const parts = [];
      if (v.element) {
        const el = String(v.element);
        parts.push(el.length > 70 ? el.slice(0, 70) + "…" : el);
      }
      if (v.role) parts.push(String(v.role));
      if (v.current_value) parts.push(`value: ${v.current_value}`);
      if (v.expanded !== undefined) parts.push(`expanded: ${v.expanded}`);
      return parts.join(" · ");
    }
    return JSON.stringify(v);
  }
  return String(v);
}
function renderIO(d) {
  // Step/turn label: the decision shown is for the step after those already executed.
  const done = state?.history?.length || 0;
  const stepEl = $("io-step");
  if (stepEl) {
    if (d) stepEl.textContent = `· Step ${done + 1}`;
    else if (done) stepEl.textContent = `· ${done} step${done === 1 ? "" : "s"} done`;
    else stepEl.textContent = "";
  }
  // 1 · Input to Jev — the exact request payload (page + elements + questions).
  $("io-input").textContent = d?.request
    ? JSON.stringify(d.request, null, 2)
    : "Choose next (or run) to send a request to Jev.";
  const req = d?.request;
  const reqState = req?.state;
  const reqEls = reqState?.elements || [];
  const heads = req?.questions ? Object.keys(req.questions) : [];
  // State block — mirrors the playground's STATE field.
  $("io-input-page").innerHTML = reqState?.page
    ? `<div class="io-subhead">State</div>` +
      `<div class="io-line"><span>Model</span><b>${escape(req.model || "—")}</b></div>` +
      `<div class="io-line"><span>URL</span><b>${escape(reqState.page.url || "—")}</b></div>` +
      `<div class="io-line"><span>Title</span><b>${escape(reqState.page.title || "—")}</b></div>` +
      (reqState.page.text
        ? `<details class="head"><summary><b>Page text</b></summary>` +
          `<div class="head-body"><pre class="io-statetext">${escape(reqState.page.text)}</pre></div></details>`
        : "")
    : "";
  // Question heads — each shows its Question (instructions) + options (Returned as / Choose when).
  $("io-input-heads").innerHTML = heads.length
    ? `<div class="io-subhead">Questions (${heads.length})</div>` +
      heads.map((h) => renderHead(h, req.questions[h])).join("")
    : "";
  // Elements table.
  $("io-input-count").textContent = reqEls.length ? `(${reqEls.length})` : "";
  $("io-input-elements").hidden = reqEls.length === 0;
  $("io-input-elements-body").innerHTML = reqEls
    .map((e) => {
      const ops = (e.operations || []).join(", ");
      const label = (e.label || "").length > 60 ? e.label.slice(0, 60) + "…" : e.label || "";
      return (
        `<tr><td>${escape(e.index)}</td>` +
        `<td>${escape(e.role || "")}</td>` +
        `<td class="cell-target" title="${escape(e.label || "")}">${escape(label)}</td>` +
        `<td>${escape(ops)}</td>` +
        `<td>${escape(e.value || "")}</td></tr>`
      );
    })
    .join("");

  // 2 · Jev output — chosen operation + target, with probabilities.
  $("io-jev-latency").textContent = d?.latency_ms != null ? `· ${d.latency_ms} ms` : "";
  if (d) {
    const ops = Object.entries(d.operation_probabilities || {}).sort((a, b) => b[1] - a[1]);
    const opRows = ops
      .map(
        ([name, p]) =>
          `<div class="io-row ${name === d.operation ? "best" : ""}"><span>${escape(name)}</span><b>${percent(p)}</b></div>`,
      )
      .join("");
    const chosen = state.page?.actions?.find((a) => a.id === d.choice);
    const targetLabel = chosen?.label || (d.target ? escape(d.target) : "— (no target)");
    const conf = d.target_confidence != null ? percent(d.target_confidence) : "—";
    $("io-jev-output").innerHTML =
      `<div class="io-line"><span>Operation</span><b>${escape(d.operation || "—")}</b></div>` +
      `<div class="io-line"><span>Target</span><b>${escape(targetLabel)}</b></div>` +
      `<div class="io-line"><span>Target confidence</span><b>${conf}</b></div>` +
      `<div class="io-subhead">Operation probabilities</div>${opRows}`;
  } else {
    $("io-jev-output").innerHTML = '<span class="muted">No decision yet. Choose next to send a request.</span>';
  }

  // 3 · Mercury output — text generated for TYPE_TEXT (only when it ran).
  const calls = state.text_calls || [];
  if (calls.length) {
    $("io-mercury-output").innerHTML = calls
      .map(
        (c) =>
          `<div class="io-mercury"><div class="io-line"><span>Field</span><b>${escape(c.field)}</b></div>` +
          `<div class="io-line"><span>Generated text</span><b>“${escape(c.value)}”</b></div>` +
          `<div class="io-line"><span>Model</span><b>${escape(c.model)}</b></div>` +
          `<div class="io-line"><span>Latency</span><b>${c.latency_ms} ms</b></div></div>`,
      )
      .join("");
  } else {
    $("io-mercury-output").innerHTML =
      '<span class="muted">No text generated yet. Mercury runs only when the operation is TYPE_TEXT.</span>';
  }
}
$("task-form").addEventListener("submit", (event) => {
  event.preventDefault();
  automatic = false;
  const scenario = $("scenario").value;
  // Presets carry a URL, so run them through the URL-accepting backend path.
  const useUrl = scenario === "config" || presets[scenario];
  perform(
    () =>
      call("reset", {
        scenario: useUrl ? "config" : scenario,
        goal: $("goal").value,
        url: useUrl ? $("start-url").value : undefined,
      }),
    "Opening a fresh browser…",
  );
});
function syncScenario() {
  const scenario = $("scenario").value;
  const preset = presets[scenario];
  const isConfig = scenario === "config";
  const showUrl = isConfig || !!preset;
  $("url-row").hidden = !showUrl;
  $("start-url").required = showUrl;
  if (preset) {
    $("start-url").value = preset.url;
    $("goal").value = goals[scenario] || "";
  } else if (isConfig) {
    if (!$("start-url").value) $("start-url").value = state?.config_url || "";
    $("goal").value = state?.config_goal || $("goal").value || "";
  } else {
    $("goal").value = goals[scenario];
  }
}
$("scenario").addEventListener("change", syncScenario);
$("choose").addEventListener("click", () =>
  perform(() => call("predict"), "Jev is comparing the actions…"),
);
$("execute").addEventListener("click", () =>
  perform(
    () => call("act", { fingerprint: state.page.fingerprint }),
    "Executing the choice…",
  ),
);
$("auto").addEventListener("click", () =>
  perform(async () => {
    automatic = true;
    controls();
    for (let i = 0; i < state.max_steps * 2 && automatic; i++) {
      $("status").textContent = "Running…";
      if ($("pace").checked) {
        await call("predict");
        await new Promise(resolve => setTimeout(resolve, 450));
        if (!automatic) break;
        await call("act", {fingerprint: state.page.fingerprint});
      } else {
        await call("tick");
      }
      if (["done", "blocked"].includes(state.status)) break;
    }
    automatic = false;
  }, "Running the browser…"),
);
$("stop").addEventListener("click", () => {
  automatic = false;
  $("status").textContent = "Pausing after the current request…";
  controls();
});
$("overlays").addEventListener("change", () => {
  $("targets").hidden = !$("overlays").checked;
});
$("choices").addEventListener("pointerover", (event) => {
  const id = event.target.closest("[data-action]")?.dataset.action;
  document
    .querySelectorAll(".target")
    .forEach((t) =>
      t.classList.toggle(
        "selected",
        t.dataset.action === id || t.dataset.action === state?.decision?.target?.split(':')[0],
      ),
    );
});
$("choices").addEventListener("pointerleave", () =>
  document
    .querySelectorAll(".target")
    .forEach((t) =>
      t.classList.toggle(
        "selected",
        t.dataset.action === state?.decision?.target?.split(':')[0],
      ),
    ),
);
$("download").addEventListener("click", () => {
  const { page, ...rest } = state;
  const blob = new Blob(
    [
      JSON.stringify(
        { ...rest, page: { ...page, screenshot: undefined } },
        null,
        2,
      ),
    ],
    { type: "application/json" },
  );
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "typesafe-browser-trace.json";
  a.click();
  URL.revokeObjectURL(url);
});
$("save-traces").addEventListener("click", () =>
  perform(async () => {
    // Ask the server to assemble + write traces.json (exact Jev input/response + what it did).
    const res = await fetch("/api/trace", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Demo-Token": token },
      body: "{}",
    });
    const info = await res.json();
    if (!res.ok) throw Error(info.error || "Could not write traces.json");
    // Also offer the assembled per-step traces as an in-browser download.
    const trace = {
      session_id: info.session_id,
      goal: state.goal,
      url: state.page?.url,
      scenario: state.scenario,
      status: state.status,
      elapsed_ms: state.elapsed_ms,
      steps: state.traces || [],
    };
    const blob = new Blob([JSON.stringify(trace, null, 2)], { type: "application/json" });
    const href = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = href;
    a.download = `${info.session_id}.json`;
    a.click();
    URL.revokeObjectURL(href);
    $("status").textContent = `Saved ${info.session_id}.json · ${info.steps} steps → output/`;
  }, "Saving traces.json…"),
);
fetch("/api/state")
  .then((r) => r.json())
  .then((s) => {
    state = s;
    syncScenario();
    render();
  })
  .catch(() => {
    $("status").textContent = "Cannot reach local demo server";
  });
