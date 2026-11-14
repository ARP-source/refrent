"""Referent new-tab page served at /home.

The primary page is the React Bits build of frontend/src/app/newtab (exported to frontend/out/newtab.html).
HOME_HTML below is a dependency-free fallback used only when the UI has not been built.
Either way it is a plain web page inside the native browsing view, so it only talks to the engine's
same-origin API: /api/notes for recent episodes and /api/recall for memory recall.
"""
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()
_BUILT = Path(__file__).resolve().parent.parent / "frontend" / "out" / "newtab.html"

HOME_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>New tab</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {
    --ink: #0b3350; --ink-soft: rgba(11, 51, 80, .62); --ink-faint: rgba(11, 51, 80, .42);
    --sky: #0297de; --orange: #fc734d; --rim: rgba(255, 255, 255, .85);
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; min-height: 100%; }
  body {
    font-family: Inter, ui-sans-serif, system-ui, sans-serif; color: var(--ink);
    background: linear-gradient(180deg, #bfe5fb 0%, #dcf1fd 40%, #f3faff 74%, #fff4ec 100%);
    background-attachment: fixed; overflow-x: hidden;
  }
  .sky { position: fixed; inset: 0; pointer-events: none; z-index: 0; overflow: hidden; }
  .cloud { position: absolute; border-radius: 50%; filter: blur(10px);
    background: radial-gradient(closest-side, rgba(255,255,255,.95), rgba(255,255,255,0)); animation: drift 22s ease-in-out infinite alternate; }
  .c1 { width: 60vw; height: 50vh; left: -14vw; top: 8vh; }
  .c2 { width: 55vw; height: 55vh; right: -16vw; top: 38vh; animation-delay: -11s; }
  .sun { position: absolute; width: 70vw; height: 50vh; right: -10vw; bottom: -24vh; border-radius: 50%;
    background: radial-gradient(closest-side, rgba(252,115,77,.28), rgba(252,115,77,0)); }
  .rays { position: absolute; inset: -20% 0 0 0; opacity: .55; mix-blend-mode: soft-light;
    background: repeating-conic-gradient(from 180deg at 50% -10%, rgba(255,255,255,0) 0deg 6deg, rgba(255,255,255,.9) 7deg 8deg, rgba(255,255,255,0) 9deg 14deg);
    -webkit-mask-image: radial-gradient(80% 70% at 50% 0%, #000 0%, transparent 75%); mask-image: radial-gradient(80% 70% at 50% 0%, #000 0%, transparent 75%); }
  @keyframes drift { from { transform: translate3d(-3vw, 0, 0) scale(1); } to { transform: translate3d(4vw, -2vh, 0) scale(1.08); } }
  @media (prefers-reduced-motion: reduce) { .cloud { animation: none; } }

  main { position: relative; z-index: 1; max-width: 880px; margin: 0 auto; padding: 12vh 24px 64px; }
  .greet { text-align: center; color: var(--ink-soft); font-size: 14px; letter-spacing: .02em; }
  h1 { margin: 6px 0 28px; text-align: center; font-family: "Instrument Serif", Georgia, serif; font-weight: 400;
    font-size: clamp(56px, 9vw, 92px); line-height: 1; letter-spacing: -.01em; }
  h1 span { color: var(--orange); }

  .glass { background: linear-gradient(180deg, rgba(255,255,255,.78), rgba(240,249,255,.6));
    backdrop-filter: blur(22px) saturate(170%); -webkit-backdrop-filter: blur(22px) saturate(170%);
    box-shadow: inset 0 1px 0 #fff, inset 0 0 0 1px var(--rim), 0 18px 48px -24px rgba(14, 92, 150, .45); }

  form.search { display: flex; align-items: center; gap: 10px; padding: 8px 8px 8px 10px; border-radius: 999px; transition: box-shadow .2s; }
  form.search:focus-within { box-shadow: inset 0 1px 0 #fff, 0 0 0 2px rgba(252,115,77,.5), 0 18px 48px -20px rgba(252,115,77,.45); }
  .mode { display: flex; background: rgba(11,51,80,.07); border-radius: 999px; padding: 3px; flex-shrink: 0; }
  .mode button { border: 0; background: transparent; color: var(--ink-soft); font: 500 13px Inter, sans-serif; padding: 7px 14px; border-radius: 999px; cursor: pointer; }
  .mode button.on { background: #fff; color: var(--ink); box-shadow: 0 1px 4px rgba(14,92,150,.18); }
  .mode button.on.recall { background: var(--orange); color: #fff; box-shadow: 0 4px 14px -4px rgba(252,115,77,.8); }
  form.search input { flex: 1; min-width: 0; border: 0; outline: 0; background: transparent; font: 400 17px Inter, sans-serif; color: var(--ink); padding: 10px 4px; }
  form.search input::placeholder { color: var(--ink-faint); }
  .go { border: 0; border-radius: 999px; padding: 11px 20px; font: 600 14px Inter, sans-serif; color: #fff; cursor: pointer; background: var(--sky); transition: transform .15s; }
  .go.recall { background: linear-gradient(180deg, #fd8b68, #fc734d); box-shadow: 0 6px 18px -6px rgba(252,115,77,.9); }
  .go:active { transform: scale(.97); }
  .status { min-height: 20px; margin: 10px 0 0; text-align: center; font-size: 13px; color: var(--ink-soft); }
  .status.err { color: #c2410c; }

  .chips { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; margin: 14px 0 0; }
  .chip { border: 0; cursor: pointer; border-radius: 999px; padding: 7px 14px; font: 500 12.5px Inter, sans-serif; color: var(--ink);
    background: rgba(255,255,255,.7); box-shadow: inset 0 0 0 1px rgba(2,121,179,.15); transition: all .15s; }
  .chip:hover { background: #fff; color: #ea580c; box-shadow: inset 0 0 0 1px rgba(252,115,77,.55); }

  h2 { margin: 44px 4px 12px; font: 600 11px Inter, sans-serif; letter-spacing: .14em; text-transform: uppercase; color: var(--ink-faint); }
  .tiles { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; }
  .tile { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 16px 8px 14px; border-radius: 20px; text-decoration: none; color: var(--ink);
    font-size: 12.5px; font-weight: 500; transition: transform .18s, box-shadow .18s; }
  .tile:hover { transform: translateY(-2px); box-shadow: inset 0 1px 0 #fff, inset 0 0 0 1px rgba(252,115,77,.45), 0 20px 40px -22px rgba(252,115,77,.6); }
  .ico { width: 44px; height: 44px; border-radius: 14px; display: grid; place-items: center; font: 600 17px Inter, sans-serif; color: #fff; }

  .recent { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .card { display: block; padding: 14px 16px; border-radius: 18px; text-decoration: none; color: var(--ink); transition: transform .18s; }
  .card:hover { transform: translateY(-1px); }
  .card .t { font-size: 14px; font-weight: 500; line-height: 1.35; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
  .card .m { margin-top: 6px; font-size: 12px; color: var(--ink-soft); display: flex; gap: 8px; align-items: center; }
  .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--orange); flex-shrink: 0; }
  .empty { color: var(--ink-soft); font-size: 13px; padding: 4px; }
  footer { margin-top: 40px; text-align: center; font-size: 12px; color: var(--ink-faint); }
  footer b { color: var(--ink-soft); font-weight: 600; }

  @media (max-width: 720px) {
    main { padding-top: 8vh; }
    .tiles { grid-template-columns: repeat(3, 1fr); }
    .recent { grid-template-columns: 1fr; }
    .mode button { padding: 7px 10px; }
  }
</style>
</head>
<body>
<div class="sky" aria-hidden="true"><div class="rays"></div><div class="cloud c1"></div><div class="cloud c2"></div><div class="sun"></div></div>
<main>
  <div class="greet" id="greet">&nbsp;</div>
  <h1>Referent<span>.</span></h1>

  <form class="search glass" id="form" autocomplete="off">
    <div class="mode" role="group" aria-label="Search mode">
      <button type="button" id="m-web" class="on" aria-pressed="true">Web</button>
      <button type="button" id="m-recall" aria-pressed="false">Recall</button>
    </div>
    <input id="q" aria-label="Search the web or enter a URL" placeholder="Search the web or enter a URL" autofocus>
    <button class="go" id="go" type="submit">Search</button>
  </form>
  <p class="status" id="status" role="status"></p>

  <div class="chips" id="chips" aria-label="Try a memory"></div>

  <h2>Shortcuts</h2>
  <nav class="tiles" id="tiles"></nav>

  <h2>Pick up where you left off</h2>
  <section class="recent" id="recent"><div class="empty">Loading your recent episodes…</div></section>

  <footer>Ask the way you remember it · Graph-resolved recall, grounded by <b>Telem AI</b></footer>
</main>
<script>
(() => {
  const DEMOS = [
    ["Find the right guide", "the Kalman study guide from two weeks ago right before Prof. Rostova's office hours"],
    ["Priya's proposal", "the proposal method section we revised with Priya Raman eight days ago"],
    ["Too close to guess", "the formula sheet I had open last night for Rostova's quiz"],
    ["Dana's primer", "the Ito calculus primer I read for Dana Chen's MATH 340"],
  ];
  const TILES = [
    ["Canvas", "/portals/canvas/", "#c2410c", "C"],
    ["Docs", "/portals/docs/proposal", "#1a73e8", "D"],
    ["Lab Wiki", "/portals/wiki/", "#0f766e", "W"],
    ["Code", "/portals/code/ekf-tracker", "#334155", "&lt;/&gt;"],
    ["Scholar", "https://scholar.google.com/", "#4285f4", "S"],
    ["arXiv", "https://arxiv.org/", "#b31b1b", "a"],
  ];
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  let mode = "web";

  const h = new Date().getHours();
  $("greet").textContent = `${h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening"} · ${new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}`;

  const setMode = (m) => {
    mode = m;
    $("m-web").classList.toggle("on", m === "web"); $("m-web").setAttribute("aria-pressed", m === "web");
    $("m-recall").classList.toggle("on", m === "recall"); $("m-recall").classList.toggle("recall", m === "recall"); $("m-recall").setAttribute("aria-pressed", m === "recall");
    $("go").textContent = m === "recall" ? "Recall" : "Search"; $("go").classList.toggle("recall", m === "recall");
    $("q").placeholder = m === "recall" ? "Ask the way you remember it…" : "Search the web or enter a URL";
    $("q").setAttribute("aria-label", $("q").placeholder); $("q").focus();
  };
  $("m-web").onclick = () => setMode("web");
  $("m-recall").onclick = () => setMode("recall");

  const looksLikeUrl = (s) => !/\s/.test(s) && (/^(https?:\/\/|localhost(:\d+)?|127\.\d+\.\d+\.\d+|\/)/i.test(s) || /^[\w-]+(\.[\w-]+)+(:\d+)?([/?#]\S*)?$/i.test(s));
  const status = (text, err = false) => { $("status").textContent = text; $("status").className = "status" + (err ? " err" : ""); };

  async function recall(query) {
    status("Searching your memory… the browser will take you there.");
    try {
      const r = await fetch("/api/recall", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ query, replay: true, enrich: true }) });
      if (r.status === 409) return status("A recall is already running. Try again in a moment.", true);
      if (!r.ok) return status("Recall failed: " + (await r.text()).slice(0, 160), true);
      const res = await r.json();
      if (res.ambiguous) status("Two memories are too close to call. Pick one in the Referent window.");
    } catch (e) { status("Could not reach the Referent engine. Is it running?", true); }
  }

  $("form").onsubmit = (e) => {
    e.preventDefault();
    const v = $("q").value.trim();
    if (!v) return;
    if (looksLikeUrl(v)) location.href = /^(https?:\/\/|\/)/i.test(v) ? v : (/^(localhost|127\.)/.test(v) ? "http://" : "https://") + v;
    else if (mode === "recall") recall(v);
    else location.href = "https://www.google.com/search?q=" + encodeURIComponent(v);
  };

  $("chips").innerHTML = DEMOS.map(([l, q], i) => `<button class="chip" data-i="${i}" title="${esc(q)}">${esc(l)}</button>`).join("");
  $("chips").onclick = (e) => { const b = e.target.closest(".chip"); if (b) { const q = DEMOS[+b.dataset.i][1]; setMode("recall"); $("q").value = q; recall(q); } };

  $("tiles").innerHTML = TILES.map(([n, u, c, g]) => `<a class="tile glass" href="${u}"><span class="ico" style="background:${c}">${g}</span>${n}</a>`).join("");

  const ago = (ts) => {
    if (!ts) return "";
    const d = Math.round((Date.now() - new Date(ts).getTime()) / 86400000);
    return d <= 0 ? "today" : d === 1 ? "yesterday" : `${d} days ago`;
  };
  fetch("/api/notes").then((r) => r.json()).then((notes) => {
    const eps = notes.filter((n) => n.type === "episode" && n.url).slice(0, 6);
    $("recent").innerHTML = eps.length ? eps.map((n) => `<a class="card glass" href="${esc(n.url)}"><div class="t">${esc(n.title)}</div><div class="m"><span class="dot"></span>${esc(ago(n.timestamp))}${n.people && n.people.length ? " · " + esc(n.people.slice(0, 2).join(", ")) : ""}</div></a>`).join("")
      : `<div class="empty">No episodes yet. Browse and capture a view to start your vault.</div>`;
  }).catch(() => { $("recent").innerHTML = `<div class="empty">Recent episodes are unavailable right now.</div>`; });
})();
</script>
</body>
</html>
"""


@router.get("/home", response_class=HTMLResponse, include_in_schema=False)
async def home_page() -> HTMLResponse:
    html = _BUILT.read_text("utf-8") if _BUILT.is_file() else HOME_HTML
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})
