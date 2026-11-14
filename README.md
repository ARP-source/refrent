# RecallOS - Episodic Memory Browser

Ask for things the way you remember them - *"the Kalman study guide from two weeks ago right before
Prof. Rostova's office hours"* - and RecallOS finds the exact file, drives a real Chromium to it,
highlights the exact sentence, tells you what changed since you last looked, and checks the web for
anything new on that topic.

```
[ Live Chromium (CDP screencast) ] [ Obsidian vault: force graph + markdown ] [ Recall bar + telemetry ]
```

## Desktop app (Windows)

`desktop/` is an Electron shell. It shows a splash, starts the Python engine (which also serves the built UI
and the browser agent), opens the RecallOS window, and stops the engine when you close the app.

```powershell
cd frontend; npm run build                 # builds the UI into frontend/out (served by the engine)
cd ..\desktop; npm install; npm start      # run the app without installing
npm run dist                               # -> desktop/dist/RecallOS Setup 1.0.0.exe (Start Menu + desktop shortcut)
```

The installed app uses this folder's Python environment (`backend/.venv`) and vault, so keep the project
folder where it is (its path is in `desktop/package.json` -> `recallRoot`). Engine log:
`%APPDATA%\RecallOS\backend.log`.

## Run it (developer mode, in a browser)

```powershell
# one-time
cd backend; python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
cd ..\frontend; npm install

# every time (or just .\start.ps1 from the repo root)
cd backend;  .\.venv\Scripts\python.exe main.py     # API + WebSocket + demo portals on :8000
cd frontend; npm run dev                             # UI on http://localhost:3000
```

Optional: copy `.env.example` to `.env` and set `TELEM_API_KEY` / `TAVILY_API_KEY` for the live
"New since you last looked" search. Without keys the drawer says so; nothing is faked.

## Demo script

| Query (click the chips) | What it shows |
|---|---|
| *the Kalman study guide from two weeks ago right before Prof. Rostova's office hours* | 10 lookalike STAT 310 guides/drafts. Keyword/vector search picks the "Rostova quiz & office hours FAQ" guide (most matching words); RecallOS anchors on the calendar event and picks the Quiz 3 prep guide opened 22 min before office hours. The agent opens it and the banner shows Prof. Rostova changed Q 0.01 -> 0.05, R 0.5 -> 0.2, 120 -> 40 steps. |
| *what is she talking about from 2 weeks ago?* (on the CS229 page) | "she" is resolved from the live DOM to Dana Chen; Gaussian decay around 14 days ago. |
| *the formula sheet I had open last night for Rostova's quiz* | Two sheets opened 3 minutes apart: margin 1.2% < 15%, so RecallOS refuses to guess, highlights both in orange and lets you pick. |
| *that repo I had open before my Kalman filter broke* | Graph + semantic recall without a time expression. |

## How it scores

```
S = w_sem * S_sem + w_time * S_time + w_graph * S_graph
S_sem   = 0.6 * BM25 + 0.4 * cosine(hashed TF-IDF uni+bigrams)
S_time  = exp(-(t - mu)^2 / 2 sigma^2)          mu/sigma from "2 weeks ago", or the calendar anchor
                                                ("right before <event>" -> event - 25 min, sigma 45 min)
S_graph = Personalized PageRank (alpha 0.85, power iteration) over [[WikiLinks]],
          seeded by DOM-resolved people, named entities, page context and the anchor event
ambiguity: (S1 - S2) / S1 < 0.15  ->  "I won't guess"
```

* **Change detection** - each episode stores `snapshot_text` (the section as it read that day). After
  replay the agent reads the live section and a word-level diff reports edits and who made them.
* **Privacy** - web queries are built only from an allow-list of public topic tags
  (`search_federation.PUBLIC_TOPICS`); no note text, names, course codes or URLs leave the machine.
* **Web dedup** - canonical-URL dedup, strict `published_after` filter, then greedy submodular
  (facility-location) selection.

## Layout

```
backend/   main.py (FastAPI, WS hub, pipeline) - vault_engine.py - deictic_resolver.py
           search_federation.py - browser_agent.py (Playwright/CDP) - mock_portals.py - seed_vault.py
vault/     the Obsidian vault (.md + YAML frontmatter + [[WikiLinks]]) - open it in Obsidian too
frontend/  Next.js 16 + Tailwind 4: BrowserViewport, ObsidianPane (react-force-graph-2d),
           CommandBar, TelemetryHUD, DreamBackground (three.js) and components/reactbits/*
```

UI components `LightRays`, `ShinyText`, `SpotlightCard` and `CountUp` come from
[React Bits](https://reactbits.dev) (copied unmodified from its public registry); the star field uses
[three.js](https://threejs.org).

Notes: the Telem AI request/response field names are not publicly documented to us; the client sends
common variants and parses defensively, and any error is shown verbatim in the drawer.
