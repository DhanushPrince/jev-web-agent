#!/usr/bin/env python3
"""Jev Playground — a local UI like the TypeSafe console.

Type a STATE, a QUESTION, and a set of OPTIONS ("returned as" + "choose when"),
click Run decision, and see Jev's answer (choice + probability per option + confidence).

Run:
  uv run --env-file .env python jev_playground.py
  # then open http://127.0.0.1:8777

Environment (from .env):
  TYPESAFE_API_KEY   required
  TYPESAFE_MODEL     optional (default "jev-latest")
  TYPESAFE_BASE_URL  optional (default OpenRouter decisions endpoint)
"""

import json
import os
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("JEV_PLAYGROUND_PORT", "8777"))
ENDPOINT = os.environ.get("TYPESAFE_BASE_URL", "https://openrouter.ai/api/alpha/decisions")
MODEL = os.environ.get("TYPESAFE_MODEL", "jev-latest")


def call_jev(body, key):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        ENDPOINT,
        data=data,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload, status = json.loads(resp.read().decode()), resp.status
    except urllib.error.HTTPError as e:
        payload, status = {"error": e.read().decode(errors="replace")}, e.code
    except urllib.error.URLError as e:
        payload, status = {"error": str(e)}, 0
    return status, payload, round((time.perf_counter() - started) * 1000)


def build_body(state, question, options, qtype):
    """Assemble a single-question request body from the form fields."""
    q = {"type": qtype, "instructions": question}
    if qtype == "choice":
        # options: [{"name": "...", "when": "..."}]  ->  criteria map {name: when}
        q["criteria"] = {o["name"]: (o["when"] or None) for o in options if o.get("name")}
    elif qtype == "noul":
        q["criteria"] = {"true": options[0].get("when") if options else "", "false": options[1].get("when") if len(options) > 1 else ""}
    elif qtype == "score":
        q["criteria"] = [o["when"] or o["name"] for o in options if o.get("name") or o.get("when")]
    return {"model": MODEL, "state": state, "questions": {"decision": q}}


HTML = """<!doctype html><html><head><meta charset="utf-8"><title>Jev Playground</title>
<style>
:root{--bg:#0e0f10;--panel:#17181a;--line:#2a2c2f;--fg:#e6e6e6;--mut:#8a8f98;--lime:#c7f04a;--acc:#1a7f37}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,-apple-system,Segoe UI,Roboto}
.wrap{display:grid;grid-template-columns:1fr 1fr;gap:0;min-height:100vh}
.col{padding:24px;overflow:auto}.col.left{border-right:1px solid var(--line)}
h1{font-size:18px;margin:0 0 4px}.sub{color:var(--mut);margin:0 0 18px}
label{display:block;text-transform:uppercase;letter-spacing:.05em;font-size:11px;color:var(--mut);margin:16px 0 6px}
textarea,input,select{width:100%;background:#0b0c0d;border:1px solid var(--line);color:var(--fg);border-radius:8px;padding:10px 12px;font:inherit}
textarea{resize:vertical}
.opt{border:1px solid var(--line);border-radius:10px;padding:12px;margin:8px 0;position:relative;background:var(--panel)}
.opt .rm{position:absolute;right:10px;top:10px;background:none;border:none;color:var(--mut);cursor:pointer;font-size:16px}
.opt input{margin-top:4px}
.row{display:flex;gap:10px;align-items:center;justify-content:space-between;margin-top:16px}
button.pri{background:var(--lime);color:#111;border:none;border-radius:8px;padding:10px 16px;font-weight:600;cursor:pointer}
button.gho{background:none;border:1px solid var(--line);color:var(--fg);border-radius:8px;padding:8px 12px;cursor:pointer}
.qtype{display:flex;gap:8px;margin-bottom:8px}
.qtype button{flex:1;background:#0b0c0d;border:1px solid var(--line);color:var(--mut);border-radius:8px;padding:6px;cursor:pointer}
.qtype button.on{border-color:var(--lime);color:var(--lime)}
.ans{display:flex;align-items:center;justify-content:center;height:100%;color:var(--mut)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px}
.bar{height:8px;background:#0b0c0d;border-radius:99px;overflow:hidden;margin:4px 0 10px}
.bar>span{display:block;height:100%;background:var(--lime)}
.bestrow{font-weight:600;color:var(--lime)}
.optrow{display:flex;justify-content:space-between;font-size:13px}
pre{white-space:pre-wrap;word-break:break-word;font-size:12px;color:var(--mut)}
.meta{color:var(--mut);font-size:12px;margin-bottom:10px}
.nav{display:flex;gap:8px;margin-bottom:16px}
.nav button{background:none;border:1px solid var(--line);color:var(--mut);border-radius:8px;padding:6px 12px;cursor:pointer}
.nav button.on{border-color:var(--lime);color:var(--lime)}
.trace-item{border:1px solid var(--line);border-radius:10px;padding:12px;margin:8px 0;cursor:pointer;background:var(--panel)}
.trace-item:hover{border-color:var(--lime)}
.trace-item .tid{font-weight:600}
.trace-item .tg{color:var(--mut);font-size:12px;margin-top:4px}
.pill{display:inline-block;font-size:11px;padding:1px 8px;border-radius:99px;background:#0b0c0d;border:1px solid var(--line);color:var(--mut);margin-right:6px}
.pill.done{color:var(--lime);border-color:var(--lime)}
.step{border:1px solid var(--line);border-radius:10px;margin:10px 0;background:var(--panel)}
.step>summary{cursor:pointer;padding:12px;list-style:none;display:flex;justify-content:space-between;gap:10px}
.step>summary::-webkit-details-marker{display:none}
.step .body{padding:0 12px 12px}
.kv{display:flex;justify-content:space-between;font-size:12px;padding:3px 0;border-bottom:1px solid #202225}
.kv span{color:var(--mut)}
.sec{margin-top:10px;font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--mut)}
</style></head><body>
<div class="wrap">
  <div class="col left">
    <div class="nav"><button id="nav-play" class="on">🧪 Playground</button><button id="nav-trace">📄 Traces</button></div>
    <div id="play-panel">
    <h1>Jev Playground</h1>
    <p class="sub">A choice question picks one option from a set you define and returns a probability for each.</p>
    <div class="qtype" id="qtype">
      <button data-t="choice" class="on">choice</button>
      <button data-t="noul">noul</button>
      <button data-t="score">score</button>
    </div>
    <label>State</label>
    <textarea id="state" rows="6">Google homepage. User goal: Search Google for "jev", then open the first blog/article result. Search field is element #5. Google Search button is element #6. No actions have been taken yet.</textarea>
    <label>Question (instructions)</label>
    <textarea id="question" rows="2">What operation should the agent perform next?</textarea>
    <label>Options</label>
    <div id="options"></div>
    <button class="gho" id="add">+ Add option</button>
    <div class="row">
      <button class="gho" id="reset">↺ Reset</button>
      <button class="pri" id="run">▷ Run decision</button>
    </div>
    </div><!-- /play-panel -->
    <div id="trace-panel" style="display:none">
      <h1>Traces</h1>
      <p class="sub">Saved runs from <code>output/</code>. Pick one to inspect each step.</p>
      <div id="trace-list"></div>
    </div>
  </div>
  <div class="col right">
    <div id="answer" class="ans">Run the decision to see the answer</div>
  </div>
</div>
<script>
const $=id=>document.getElementById(id);
let qtype='choice';
const defaults={
  choice:[{name:'CLICK',when:'Click an element, button, menu option, or link.'},
          {name:'TYPE_TEXT',when:'Enter text into an editable field.'},
          {name:'WAIT',when:'Wait for the page to update.'},
          {name:'DONE',when:'Every requirement is visibly satisfied.'},
          {name:'BLOCKED',when:'No supported operation can progress.'}],
  noul:[{name:'true',when:'Yes / condition holds.'},{name:'false',when:'No / condition does not hold.'}],
  score:[{name:'0',when:'Low'},{name:'1',when:'Medium'},{name:'2',when:'High'}]
};
let options=JSON.parse(JSON.stringify(defaults.choice));
function renderOptions(){
  $('options').innerHTML=options.map((o,i)=>`
    <div class="opt">
      <button class="rm" data-i="${i}">×</button>
      <label>Returned as</label>
      <input data-i="${i}" data-k="name" value="${(o.name||'').replace(/"/g,'&quot;')}">
      <label>Choose when</label>
      <input data-i="${i}" data-k="when" value="${(o.when||'').replace(/"/g,'&quot;')}">
    </div>`).join('');
  document.querySelectorAll('.opt input').forEach(inp=>inp.addEventListener('input',e=>{
    options[e.target.dataset.i][e.target.dataset.k]=e.target.value;}));
  document.querySelectorAll('.opt .rm').forEach(b=>b.addEventListener('click',e=>{
    options.splice(+e.target.dataset.i,1);renderOptions();}));
}
$('add').onclick=()=>{options.push({name:'',when:''});renderOptions();};
$('reset').onclick=()=>{options=JSON.parse(JSON.stringify(defaults[qtype]));renderOptions();};
document.querySelectorAll('#qtype button').forEach(b=>b.onclick=()=>{
  qtype=b.dataset.t;document.querySelectorAll('#qtype button').forEach(x=>x.classList.toggle('on',x===b));
  options=JSON.parse(JSON.stringify(defaults[qtype]));renderOptions();});
$('run').onclick=async()=>{
  $('answer').innerHTML='<div class="ans">Running…</div>';
  const res=await fetch('/run',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({state:$('state').value,question:$('question').value,options,qtype})});
  const d=await res.json();
  if(d.error){$('answer').innerHTML=`<div class="card"><b>Error</b><pre>${d.error}</pre></div>`;return;}
  const a=d.answer||{};
  let html=`<div class="card"><div class="meta">HTTP ${d.http_status} · ${d.latency_ms} ms · model ${d.model||''}</div>`;
  if(a.type==='choice'){
    const probs=Object.entries(a.probabilities||{}).sort((x,y)=>y[1]-x[1]);
    html+=`<h1>Choice: ${a.choice} <span style="color:var(--mut);font-weight:400">· conf ${(a.confidence*100).toFixed(0)}%</span></h1>`;
    html+=probs.map(([k,v])=>`<div class="optrow ${k===a.choice?'bestrow':''}"><span>${k}</span><span>${(v*100).toFixed(0)}%</span></div><div class="bar"><span style="width:${v*100}%"></span></div>`).join('');
  }else if(a.type==='noul'){
    html+=`<h1>Noul: ${(a.noul*100).toFixed(0)}% yes</h1><div class="bar"><span style="width:${a.noul*100}%"></span></div>`;
  }else if(a.type==='score'){
    html+=`<h1>Score: ${a.score} <span style="color:var(--mut);font-weight:400">· conf ${(a.confidence*100).toFixed(0)}%</span></h1>`;
    html+=Object.entries(a.probabilities||{}).map(([k,v])=>`<div class="optrow"><span>${(a.legend||{})[k]||k}</span><span>${(v*100).toFixed(0)}%</span></div><div class="bar"><span style="width:${v*100}%"></span></div>`).join('');
  }
  html+=`<details style="margin-top:14px"><summary style="cursor:pointer;color:var(--mut)">Raw request &amp; response</summary>
    <label>Request sent to Jev</label><pre>${JSON.stringify(d.request,null,2)}</pre>
    <label>Response from Jev</label><pre>${JSON.stringify(d.response,null,2)}</pre></details></div>`;
  $('answer').innerHTML=html;
};
// ---- Tab switching ----
function showTab(t){
  $('play-panel').style.display = t==='play'?'':'none';
  $('trace-panel').style.display = t==='trace'?'':'none';
  $('nav-play').classList.toggle('on',t==='play');
  $('nav-trace').classList.toggle('on',t==='trace');
  if(t==='trace') loadTraces();
  if(t==='play') $('answer').innerHTML='<div class="ans">Run the decision to see the answer</div>';
}
$('nav-play').onclick=()=>showTab('play');
$('nav-trace').onclick=()=>showTab('trace');
async function loadTraces(){
  $('answer').innerHTML='<div class="ans">Select a trace to inspect</div>';
  const items=await fetch('/traces').then(r=>r.json());
  if(!items.length){$('trace-list').innerHTML='<p class="sub">No traces yet. Run the browser agent to create output/*.json.</p>';return;}
  $('trace-list').innerHTML=items.map(t=>`
    <div class="trace-item" data-id="${t.session_id}">
      <div class="tid">${t.session_id} <span class="pill ${t.status==='done'?'done':''}">${t.status||''}</span><span class="pill">${t.steps} steps</span><span class="pill">${((t.elapsed_ms||0)/1000).toFixed(1)}s</span></div>
      <div class="tg">${(t.goal||'').slice(0,110)}</div>
    </div>`).join('');
  document.querySelectorAll('.trace-item').forEach(el=>el.onclick=()=>openTrace(el.dataset.id));
}
function pct(v){return v==null?'—':`${(v*100).toFixed(0)}%`;}
function dist(map,winner){
  return Object.entries(map||{}).sort((a,b)=>b[1]-a[1]).map(([k,v])=>
    `<div class="optrow ${k===winner?'bestrow':''}"><span>${k}</span><span>${pct(v)}</span></div><div class="bar"><span style="width:${v*100}%"></span></div>`).join('');
}
async function openTrace(id){
  const d=await fetch('/trace?id='+encodeURIComponent(id)).then(r=>r.json());
  if(d.error){$('answer').innerHTML=`<div class="card">${d.error}</div>`;return;}
  let html=`<div class="card"><div class="meta">${d.session_id} · ${d.status} · ${((d.elapsed_ms||0)/1000).toFixed(2)}s · ${d.steps.length} steps</div>
    <div class="kv"><span>Goal</span><b>${(d.goal||'').slice(0,80)}</b></div>
    <div class="kv"><span>Final URL</span><b>${d.url||''}</b></div></div>`;
  html+=d.steps.map(s=>{
    const r=s.jev_response||{}, ex=s.executed||{}, m=s.mercury;
    const inp=s.jev_input||{}, st=inp.state||{}, heads=inp.questions?Object.keys(inp.questions):[];
    return `<details class="step"><summary>
        <b>#${String(s.step).padStart(2,'0')} · ${r.operation||ex.kind}</b>
        <span style="color:var(--mut)">${(ex.target_label||'').slice(0,40)} · conf ${pct(r.confidence)}</span>
      </summary>
      <div class="body">
        <div class="sec">Input to Jev</div>
        <div class="kv"><span>URL</span><b>${(st.page||{}).url||''}</b></div>
        <div class="kv"><span>Title</span><b>${(st.page||{}).title||''}</b></div>
        <div class="kv"><span>Elements</span><b>${(st.elements||[]).length}</b></div>
        <div class="kv"><span>Question heads</span><b>${heads.join(', ')}</b></div>
        <div class="sec">Jev output — operation distribution</div>
        ${dist(r.operation_probabilities,r.operation)}
        <div class="kv"><span>Chosen operation</span><b>${r.operation}</b></div>
        <div class="kv"><span>Target</span><b>${ex.target_label||r.target||'—'}</b></div>
        <div class="kv"><span>Confidence</span><b>${pct(r.confidence)}</b></div>
        <div class="kv"><span>Jev latency</span><b>${r.latency_ms||'—'} ms</b></div>
        <div class="sec">Mercury (text model)</div>
        ${m?`<div class="kv"><span>Text</span><b>“${m.text}”</b></div><div class="kv"><span>Model</span><b>${m.model}</b></div><div class="kv"><span>Latency</span><b>${m.latency_ms} ms</b></div>`:'<div class="kv"><span>—</span><b>not used (only for TYPE_TEXT)</b></div>'}
        <div class="sec">What it did</div>
        <div class="kv"><span>Executed</span><b>${ex.kind}</b></div>
        <div class="kv"><span>Page changed</span><b>${ex.page_changed}</b></div>
        <div class="kv"><span>URL after</span><b>${ex.url_after||''}</b></div>
        <details style="margin-top:10px"><summary style="cursor:pointer;color:var(--mut)">Raw jev_input / jev_response</summary>
          <div class="sec">jev_input</div><pre>${JSON.stringify(s.jev_input,null,2)}</pre>
          <div class="sec">jev_response</div><pre>${JSON.stringify(s.jev_response,null,2)}</pre></details>
      </div></details>`;
  }).join('');
  $('answer').innerHTML=`<div style="width:100%">${html}</div>`;
  $('answer').style.alignItems='flex-start';
}
renderOptions();
</script></body></html>"""


def build_and_call(payload):
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key:
        return {"error": "TYPESAFE_API_KEY not set. Start with: uv run --env-file .env python jev_playground.py"}
    body = build_body(payload["state"], payload["question"], payload.get("options", []), payload.get("qtype", "choice"))
    status, response, latency = call_jev(body, key)
    answer = (response or {}).get("answers", {}).get("decision")
    return {
        "http_status": status,
        "latency_ms": latency,
        "model": (response or {}).get("model"),
        "request": body,
        "response": response,
        "answer": answer,
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send(200, HTML, "text/html; charset=utf-8")
        if self.path == "/traces":
            # List available trace sessions (newest first).
            out = os.path.join(os.getcwd(), "output")
            items = []
            if os.path.isdir(out):
                for name in sorted(os.listdir(out), reverse=True):
                    if not name.endswith(".json"):
                        continue
                    try:
                        d = json.load(open(os.path.join(out, name)))
                        items.append(
                            {
                                "session_id": d.get("session_id") or name[:-5],
                                "goal": d.get("goal"),
                                "url": d.get("url"),
                                "status": d.get("status"),
                                "elapsed_ms": d.get("elapsed_ms"),
                                "steps": len(d.get("steps", [])),
                            }
                        )
                    except (ValueError, OSError):
                        continue
            return self._send(200, json.dumps(items))
        if self.path.startswith("/trace?"):
            sid = self.path.split("id=", 1)[1] if "id=" in self.path else ""
            sid = os.path.basename(sid)  # prevent path traversal
            fp = os.path.join(os.getcwd(), "output", f"{sid}.json")
            if os.path.isfile(fp):
                return self._send(200, open(fp).read())
            return self._send(404, json.dumps({"error": "trace not found"}))
        self._send(404, "not found", "text/plain")

    def do_POST(self):
        if self.path != "/run":
            return self._send(404, "not found", "text/plain")
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or "{}")
        self._send(200, json.dumps(build_and_call(payload)))

    def log_message(self, *_):
        pass


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Jev Playground: http://127.0.0.1:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
