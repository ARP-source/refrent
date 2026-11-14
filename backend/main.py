"""RecallOS backend: FastAPI + WebSocket telemetry hub.

Run:  python main.py      (serves API, WebSocket and the demo portals on settings.base_url)
"""
from __future__ import annotations

import asyncio
import difflib
import json
import re
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Header
import secrets
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import mock_portals
import seed_vault
from browser_agent import BrowserAgent
from config import settings
from deictic_resolver import DeicticResolver, Resolved
from search_federation import Federation, extract_public_tags
from vault_engine import Note, Vault, approx_tokens

AMBIGUITY_MARGIN = 0.15  # refuse to guess when (s1 - s2) / s1 is below this
ANCHOR_OFFSET = timedelta(minutes=25)
ANCHOR_SIGMA = timedelta(minutes=45)


# ----------------------------------------------------------------------------- hub
class Client:
    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.events: deque[str] = deque(maxlen=500)
        self.frame: bytes | None = None
        self.signal = asyncio.Event()

    def push(self, text: str) -> None:
        self.events.append(text)
        self.signal.set()

    def push_frame(self, data: bytes) -> None:
        self.frame = data  # latest-frame-wins: slow clients drop frames, never events
        self.signal.set()

    async def pump(self) -> None:
        while True:
            await self.signal.wait()
            self.signal.clear()
            while self.events:
                await self.ws.send_text(self.events.popleft())
            if self.frame is not None:
                f, self.frame = self.frame, None
                await self.ws.send_bytes(f)


class Hub:
    def __init__(self) -> None:
        self.clients: set[Client] = set()

    async def emit(self, event: dict[str, Any]) -> None:
        event.setdefault("ts", time.time())
        text = json.dumps(event, default=str)
        for c in list(self.clients):
            c.push(text)

    async def emit_frame(self, data: bytes) -> None:
        for c in list(self.clients):
            c.push_frame(data)


hub = Hub()
vault = Vault(settings.vault_dir)
resolver = DeicticResolver()
federation = Federation()
agent = BrowserAgent(hub.emit, hub.emit_frame)
recall_lock = asyncio.Lock()
pending: dict[str, dict[str, Any]] = {}  # rid -> context of an ambiguous recall awaiting the user's pick


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not any(n.type == "episode" for n in vault.notes.values()):
        seed_vault.seed(settings.vault_dir)
        vault.reload()
    task = asyncio.create_task(_start_agent_later())  # portals are served by this process
    yield
    task.cancel()
    await agent.stop()


async def _start_agent_later() -> None:
    await asyncio.sleep(0.5)
    await agent.start()
    await hub.emit({"type": "status", **status_payload()})


app = FastAPI(title="RecallOS", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.frontend_origins), allow_methods=["*"], allow_headers=["*"])
app.include_router(mock_portals.router)


def status_payload() -> dict[str, Any]:
    episodes = sum(1 for n in vault.notes.values() if n.type == "episode")
    return {
        "keys": settings.key_status(),
        "browser": agent.status(),
        "vault": {"notes": len(vault.notes), "episodes": episodes, "edges": vault.graph.number_of_edges(), "dir": str(settings.vault_dir)},
        "base_url": settings.base_url,
        "ambiguity_margin": AMBIGUITY_MARGIN,
    }


# ----------------------------------------------------------------------------- models
class RecallIn(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    replay: bool = True
    enrich: bool = True
    graph_preview: bool = False


class ChooseIn(BaseModel):
    rid: str = Field(max_length=32)
    id: str = Field(max_length=300)
    replay: bool = True
    enrich: bool = True


class NoteIn(BaseModel):
    raw: str = Field(max_length=200_000)


class NavigateIn(BaseModel):
    url: str = Field(min_length=1, max_length=2000)


# ----------------------------------------------------------------------------- REST
class NativeAttachIn(BaseModel):
    id: int = Field(gt=0)
    marker: str = Field(max_length=100)
    endpoint: str = Field(max_length=100)


class NativeSelectIn(BaseModel):
    id: int = Field(gt=0)


def check_native_key(key: str | None) -> None:
    if not settings.native or not settings.native_key or not secrets.compare_digest(key or "", settings.native_key):
        raise HTTPException(403, "Native browser bridge requires the desktop session key")


@app.post("/api/browser/native/attach")
async def api_native_attach(body: NativeAttachIn, x_referent_key: str | None = Header(default=None)):
    check_native_key(x_referent_key)
    if body.endpoint != f"http://127.0.0.1:{settings.cdp_port}" or body.marker != f"about:blank#referent-{body.id}":
        raise HTTPException(400, "Unexpected browser target")
    async with recall_lock:
        await agent.attach_native(body.endpoint, body.marker, body.id)
    await hub.emit({"type": "status", **status_payload()})
    return {"ok": True}


@app.post("/api/browser/native/select")
async def api_native_select(body: NativeSelectIn, x_referent_key: str | None = Header(default=None)):
    check_native_key(x_referent_key)
    if body.id not in agent.tabs:
        raise HTTPException(404, "Tab not found")
    async with recall_lock:
        await agent.switch_tab(body.id)
    return {"ok": True}


@app.get("/api/status")
async def api_status():
    return status_payload()


@app.get("/api/graph")
async def api_graph():
    return vault.graph_payload()


@app.get("/api/notes")
async def api_notes():
    return sorted((n.public() for n in vault.notes.values()), key=lambda n: n["timestamp"] or "", reverse=True)


def note_detail(n: Note) -> dict[str, Any]:
    return {**n.public(), "raw": vault.raw(n.id), "body": n.body, "backlinks": vault.backlinks(n.id),
            "snapshot_text": n.meta.get("snapshot_text"), "tags": n.meta.get("tags", [])}


@app.get("/api/notes/{note_id}")
async def api_note(note_id: str):
    n = vault.get(note_id)
    if not n:
        raise HTTPException(404, "note not found")
    return note_detail(n)


@app.put("/api/notes/{note_id}")
async def api_note_put(note_id: str, body: NoteIn):
    try:
        n = vault.write_raw(note_id, body.raw)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:  # yaml errors etc.
        raise HTTPException(400, f"could not parse note: {exc}")
    await hub.emit({"type": "graph_update"})
    return note_detail(n)


@app.post("/api/vault/seed")
async def api_seed():
    count = seed_vault.seed(settings.vault_dir)
    vault.reload()
    await hub.emit({"type": "graph_update"})
    return {"seeded": count}


@app.post("/api/browser/navigate")
async def api_navigate(body: NavigateIn):
    try:
        await agent.navigate(body.url)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return agent.status()


@app.post("/api/episode/capture")
async def api_capture():
    snap = await agent.snapshot()
    built = agent.build_episode(snap, vault.resolve_name)
    if not built:
        raise HTTPException(409, "browser is not on a page")
    note_id, fm, body = built
    fm["snapshot_text"] = await agent.element_text(fm.get("selector"))
    fm["tags"] = extract_public_tags(f"{fm['title']} {fm.get('text_fragment') or ''} {body}")
    n = vault.write_episode(note_id, fm, body)
    await hub.emit({"type": "graph_update", "focus": n.id})
    await hub.emit({"type": "trace", "step": "capture", "title": "Episode captured to vault", "detail": f"{n.id}.md"})
    return n.public()


@app.post("/api/replay/{note_id}")
async def api_replay(note_id: str):
    n = vault.get(note_id)
    if not n or not n.meta.get("actions"):
        raise HTTPException(404, "note has no replayable actions")
    res = await agent.replay(n.meta["actions"], _label(n))
    await hub.emit({"type": "changes", **compare_snapshot(n, res)})
    return res


@app.post("/api/recall")
async def api_recall(body: RecallIn):
    if recall_lock.locked():
        raise HTTPException(409, "a recall is already running")
    async with recall_lock:
        return await run_recall(body.query.strip(), body.replay, body.enrich, body.graph_preview)


@app.post("/api/recall/choose")
async def api_choose(body: ChooseIn):
    ctx = pending.get(body.rid)
    if not ctx or body.id not in ctx["candidates"]:
        raise HTTPException(404, "no ambiguous recall with that candidate")
    if recall_lock.locked():
        raise HTTPException(409, "a recall is already running")
    async with recall_lock:
        pending.pop(body.rid, None)
        return await run_choice(ctx, body.id, body.replay, body.enrich)


# ----------------------------------------------------------------------------- helpers
def _label(n: Note) -> str:
    when = n.timestamp.strftime("%b %d") if n.timestamp else ""
    return f"{n.title[:48]}{' - ' + when if when else ''}"


def public_tags_for(note: Note) -> list[str]:
    tags = [t for t in (note.meta.get("tags") or []) if isinstance(t, str)]
    # re-validate against the allow-list so a hand-edited note cannot smuggle private text out
    allowed = set(extract_public_tags(" ".join(tags), limit=50))
    tags = [t for t in tags if t in allowed]
    return tags or extract_public_tags(f"{note.title} {note.meta.get('text_fragment') or ''} {note.body}")


def compare_snapshot(note: Note, replay_res: dict[str, Any] | None) -> dict[str, Any]:
    """Compare the text stored in the vault when the episode happened against the live page today."""
    base = {"note_id": note.id, "title": note.title, "seen_at": note.timestamp.isoformat() if note.timestamp else None,
            "selector": note.meta.get("selector")}
    old = (note.meta.get("snapshot_text") or "").strip()
    bbox = (replay_res or {}).get("bbox") or {}
    new = (bbox.get("liveText") or "").strip()
    if not old:
        return {**base, "status": "no_snapshot", "changed": False}
    if not new:
        return {**base, "status": "not_found", "changed": False, "before": old}
    a, b = old.split(), new.split()
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    changes = [
        {"op": tag, "before": " ".join(a[i1:i2]), "after": " ".join(b[j1:j2])}
        for tag, i1, i2, j1, j2 in sm.get_opcodes()
        if tag != "equal"
    ]
    num = re.compile(r"\d")
    return {
        **base,
        "status": "changed" if changes else "unchanged",
        "changed": bool(changes),
        "similarity": round(sm.ratio(), 4),
        "changes": changes[:12],
        "numeric_changes": sum(1 for c in changes if num.search(c["before"] + c["after"])),
        "edited_by": bbox.get("editedBy"),
        "edited_at": bbox.get("editedAt"),
        "before": old,
        "after": new,
    }


def winning_path(top_id: str, hub_weights: dict[str, float]) -> list[str]:
    """Query -> context hubs that actually link to the winner -> winner."""
    neighbors = set(vault.graph.neighbors(top_id)) if top_id in vault.graph else set()
    hubs = [h for h in hub_weights if h in neighbors]
    if not hubs and hub_weights:
        hubs = [max(hub_weights, key=hub_weights.get)]
    order = {"event": 0, "course": 1, "person": 2}
    return sorted(hubs, key=lambda h: order.get(vault.notes[h].type if h in vault.notes else "", 3))


def build_weights(resolved: Resolved, query: str) -> tuple[dict[str, float], list[str]]:
    weights: dict[str, float] = {}
    if resolved.person:
        weights[resolved.person["name"]] = 2.0
    mentioned = vault.mentions(query)
    for hid in mentioned:
        weights[vault.notes[hid].title] = 2.0
    if resolved.context and resolved.context.get("name"):
        weights.setdefault(resolved.context["name"], 1.0)
    return weights, mentioned


# ----------------------------------------------------------------------------- pipeline
class Run:
    def __init__(self, rid: str):
        self.rid = rid
        self.t0 = time.perf_counter()
        self.timings: dict[str, float] = {}

    async def trace(self, step: str, title: str, detail: str = "", **extra: Any) -> None:
        await hub.emit({"type": "trace", "rid": self.rid, "step": step, "title": title, "detail": detail,
                        "t_ms": round((time.perf_counter() - self.t0) * 1000), **extra})


async def run_recall(query: str, do_replay: bool, do_enrich: bool, graph_preview: bool = False) -> dict[str, Any]:
    run = Run(uuid.uuid4().hex[:8])
    await hub.emit({"type": "recall_start", "rid": run.rid, "query": query})

    # 1. live DOM -----------------------------------------------------------------
    ts = time.perf_counter()
    dom = await agent.snapshot()
    run.timings["dom_ms"] = (time.perf_counter() - ts) * 1000

    # 2. deictic + temporal resolution ---------------------------------------------
    ts = time.perf_counter()
    resolved = await resolver.resolve(query, dom)
    for step in resolved.trace:
        await run.trace(step["step"], step["title"], step.get("detail", ""), math=step.get("math"))
    weights, mentioned = build_weights(resolved, query)
    if mentioned:
        await run.trace("mention", "Named entities in the query",
                        ", ".join(vault.notes[m].title for m in mentioned) + " -> PPR seeds (weight 2)")

    win = resolved.temporal
    anchor_mu = anchor_sigma = None
    anchor_note: Note | None = None
    if resolved.anchor_phrase:
        found = vault.find_anchor_event(resolved.anchor_phrase, win.mu if win else None, win.sigma if win else None)
        if found:
            anchor_note = found[0]
            sign = -1 if resolved.anchor_rel == "before" else 1
            anchor_mu = anchor_note.timestamp + sign * ANCHOR_OFFSET
            anchor_sigma = ANCHOR_SIGMA
            weights[anchor_note.id] = 2.0
            await run.trace("anchor", f"Calendar anchor: {anchor_note.title}",
                            f'"{resolved.anchor_rel} {resolved.anchor_phrase}" -> event at {anchor_note.timestamp:%b %d %H:%M}; '
                            f"window mu = {anchor_mu:%H:%M}, sigma = {int(ANCHOR_SIGMA.total_seconds() // 60)} min",
                            math="S_time(t) = exp(-(t - (t_event - 25min))^2 / (2 * (45min)^2))")
        else:
            await run.trace("anchor", "No calendar event matched the anchor", f'"{resolved.anchor_phrase}"')
    run.timings["resolve_ms"] = (time.perf_counter() - ts) * 1000

    # 3. vault retrieval (S_sem + S_time + S_graph) ------------------------------------
    ts = time.perf_counter()
    search = vault.search(
        resolved.expanded_query or query,
        entity_weights=weights,
        mu=win.mu if win else None,
        sigma=win.sigma if win else None,
        anchor_mu=anchor_mu,
        anchor_sigma=anchor_sigma,
    )
    run.timings["retrieval_ms"] = (time.perf_counter() - ts) * 1000
    baseline = vault.baseline(query)
    w = search["weights"]
    seeds_txt = ", ".join(f"{k} ({v:.2f})" for k, v in sorted(search["ppr_seeds"].items(), key=lambda kv: -kv[1])[:4])
    await run.trace("ppr", "Personalized PageRank over [[WikiLink]] graph", f"alpha = 0.85, seeds: {seeds_txt or 'none'}",
                    math="PPR = alpha * W^T PPR + (1 - alpha) * p_seed")
    results = search["results"]
    if not results:
        await run.trace("empty", "No matching episodes", "Try rephrasing or capture more episodes.")
        out = {"rid": run.rid, "resolved": resolved.public(), "search": _search_public(search), "baseline": baseline,
               "replay": None, "enrichment": None, "ambiguous": False}
        await hub.emit({"type": "result", **out})
        return out

    r0 = results[0]
    if baseline:
        same = baseline["id"] == r0["id"]
        await run.trace("baseline", "Keyword/vector baseline " + ("agrees" if same else "picks a lookalike"),
                        f'BM25+cosine alone -> "{baseline["title"]}" ({baseline["score"]:.2f})'
                        + ("" if same else f' vs RecallOS -> "{r0["title"]}"'))
    await run.trace("score", f"Top episode: {r0['title']}",
                    f"{w['sem']:.2f}*{r0['s_sem']:.2f} + {w['time']:.2f}*{r0['s_time']:.2f} + {w['graph']:.2f}*{r0['s_graph']:.2f} = {r0['score']:.3f}",
                    math="S = w_sem*S_sem + w_time*S_time + w_graph*S_graph,  S_sem = 0.6*BM25 + 0.4*cos")

    hub_w = {vault.resolve_name(k): v for k, v in weights.items() if vault.resolve_name(k)}
    margin = (r0["score"] - results[1]["score"]) / r0["score"] if len(results) > 1 and r0["score"] > 0 else 1.0
    ambiguous = margin < AMBIGUITY_MARGIN

    if ambiguous:
        cands = [results[0]["id"], results[1]["id"]]
        await hub.emit({"type": "graph_scores", "rid": run.rid, "scores": search["all_scores"], "node_scores": search["node_scores"],
                        "seeds": search["ppr_seeds"], "top": None, "path": winning_path(cands[0], hub_w), "ambiguous": cands,
                        "query_label": query})
        await run.trace("refuse", "I won't guess - two memories are too close",
                        f"confidence margin {(margin * 100):.1f}% < {int(AMBIGUITY_MARGIN * 100)}%: "
                        f'"{results[0]["title"]}" ({results[0]["score"]:.3f}) vs "{results[1]["title"]}" ({results[1]["score"]:.3f}). Pick one.',
                        math="margin = (S_1 - S_2) / S_1")
        pending[run.rid] = {"rid": run.rid, "query": query, "candidates": cands, "hub_w": hub_w, "search": search,
                            "resolved": resolved, "baseline": baseline, "t0": run.t0, "timings": dict(run.timings),
                            "temporal": resolved.temporal}
        if len(pending) > 20:
            pending.pop(next(iter(pending)))
        details = []
        for cid in cands:
            n = vault.get(cid)
            r = next(x for x in results if x["id"] == cid)
            details.append({**r, "url": n.url, "selector": n.meta.get("selector"), "people": n.people})
        await hub.emit({"type": "ambiguous", "rid": run.rid, "margin": round(margin, 4), "threshold": AMBIGUITY_MARGIN, "candidates": details})
        telemetry = make_telemetry(run, search, resolved, None, results)
        out = {"rid": run.rid, "resolved": resolved.public(), "search": _search_public(search), "baseline": baseline,
               "ambiguous": True, "margin": round(margin, 4), "candidates": details, "replay": None, "enrichment": None,
               "telemetry": telemetry}
        await hub.emit({"type": "result", **out})
        return out

    path = winning_path(r0["id"], hub_w)
    await hub.emit({"type": "graph_scores", "rid": run.rid, "scores": search["all_scores"], "node_scores": search["node_scores"],
                    "seeds": search["ppr_seeds"], "top": r0["id"], "path": path, "ambiguous": [], "query_label": query,
                    "margin": round(margin, 4)})
    if graph_preview and do_replay:
        await asyncio.sleep(2.5)
    top = vault.get(r0["id"])
    restored = await restore(run, top, do_replay, do_enrich)
    telemetry = make_telemetry(run, search, resolved, restored.get("enrichment"), results)
    out = {"rid": run.rid, "resolved": resolved.public(), "search": _search_public(search), "baseline": baseline,
           "ambiguous": False, "margin": round(margin, 4), "episode": {**top.public(), "body": top.body}, **restored,
           "telemetry": telemetry, "path": path}
    await hub.emit({"type": "result", **out})
    return out


async def run_choice(ctx: dict[str, Any], note_id: str, do_replay: bool, do_enrich: bool) -> dict[str, Any]:
    run = Run(ctx["rid"])
    run.t0 = time.perf_counter()
    run.timings.update({k: v for k, v in ctx["timings"].items() if k in {"dom_ms", "resolve_ms", "retrieval_ms"}})
    search, results = ctx["search"], ctx["search"]["results"]
    n = vault.get(note_id)
    await run.trace("choice", "You picked the memory", f'"{n.title}" - no guessing involved')
    path = winning_path(note_id, ctx["hub_w"])
    await hub.emit({"type": "graph_scores", "rid": run.rid, "scores": search["all_scores"], "node_scores": search["node_scores"],
                    "seeds": search["ppr_seeds"], "top": note_id, "path": path, "ambiguous": [], "query_label": ctx["query"]})
    restored = await restore(run, n, do_replay, do_enrich)
    telemetry = make_telemetry(run, search, ctx["resolved"], restored.get("enrichment"), results, top_id=note_id)
    out = {"rid": run.rid, "resolved": ctx["resolved"].public(), "search": _search_public(search), "baseline": ctx["baseline"],
           "ambiguous": False, "chosen": True, "episode": {**n.public(), "body": n.body}, **restored, "telemetry": telemetry, "path": path}
    await hub.emit({"type": "result", **out})
    return out


async def restore(run: Run, top: Note, do_replay: bool, do_enrich: bool) -> dict[str, Any]:
    """Browser takeover + snapshot diff, concurrently with the privacy-safe web delta search."""
    out: dict[str, Any] = {"replay": None, "changes": None, "enrichment": None}

    async def replay_task() -> None:
        if not (do_replay and top.meta.get("actions")):
            return
        await run.trace("replay", "Browser agent takeover", f"Replaying {len(top.meta['actions'])} recorded actions -> {top.meta.get('selector')}")
        t = time.perf_counter()
        res = await agent.replay(top.meta["actions"], _label(top))
        run.timings["replay_ms"] = (time.perf_counter() - t) * 1000
        out["replay"] = {k: v for k, v in res.items() if k != "bbox"} | {"bbox": {k: v for k, v in (res.get("bbox") or {}).items() if k != "liveText"}}
        failed = [s for s in res.get("steps", []) if not s.get("ok")]
        await run.trace("replay_done", "Episode restored on screen" if res.get("ok") else "Replay finished with errors",
                        f"{len(res.get('steps', []))} steps in {run.timings['replay_ms']:.0f} ms" + (f"; {len(failed)} failed: {failed[0].get('error')}" if failed else ""))
        changes = compare_snapshot(top, res)
        out["changes"] = changes
        await hub.emit({"type": "changes", "rid": run.rid, **changes})
        if changes["status"] == "changed":
            who = f" by {changes['edited_by']}" if changes.get("edited_by") else ""
            first = changes["changes"][0] if changes["changes"] else {}
            await run.trace("diff", f"Changed since you last looked{who}",
                            f"{changes['numeric_changes']} numeric edit(s), similarity {changes['similarity']:.0%}; e.g. "
                            f'"{first.get("before", "")}" -> "{first.get("after", "")}"')
        elif changes["status"] == "unchanged":
            await run.trace("diff", "Unchanged since you last looked", "Live text matches the vault snapshot word-for-word")

    async def enrich_task() -> None:
        if not do_enrich:
            return
        tags = public_tags_for(top)
        if not tags:
            await run.trace("enrich", "Web delta skipped", "No public topic tags in this memory - nothing is sent off-device.")
            return
        q = " ".join(tags[:4])
        after = top.timestamp
        await run.trace("enrich", "Privacy-safe web delta (Telem + Tavily)",
                        f"public tags only: {', '.join(tags[:4])}" + (f"; published_after {after:%Y-%m-%d}" if after else ""))
        t = time.perf_counter()
        res = await federation.search(q, after)
        res["tags"] = tags[:4]
        run.timings["enrich_ms"] = (time.perf_counter() - t) * 1000
        out["enrichment"] = res
        prov = ", ".join(f"{k}: {v.get('count', 0) if v.get('ok') else v.get('status')}" for k, v in res["providers"].items())
        await hub.emit({"type": "enrichment", "rid": run.rid, **res})
        await run.trace("enrich_done", f"{len(res['results'])} new sources after submodular dedup",
                        f"{prov}; {res['raw_count']} raw -> {res['unique_count']} unique -> {len(res['results'])} selected",
                        math="max_S sum_i max_{j in S} sim(i,j) + lambda * sum_{j in S} rel(j)")

    await asyncio.gather(replay_task(), enrich_task())
    return out


def _search_public(search: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in search.items() if k not in {"all_scores", "node_scores"}}


def make_telemetry(run: Run, search: dict, resolved: Resolved, enrich: dict | None, results: list[dict], top_id: str | None = None) -> dict:
    top = next((r for r in results if r["id"] == top_id), results[0]) if results else None
    naive = vault.corpus_tokens() + (enrich["tokens_raw"] if enrich else 0)
    context = sum(approx_tokens(r["excerpt"]) + approx_tokens(r["title"]) for r in results[:3]) + (enrich["tokens_kept"] if enrich else 0)
    now = datetime.now()
    markers = []
    for r in results:
        if r["timestamp"]:
            d = (now - datetime.fromisoformat(r["timestamp"])).total_seconds() / 86400
            markers.append({"id": r["id"], "title": r["title"], "days_ago": round(d, 2), "score": r["score"], "s_time": r["s_time"]})
    if top_id:
        markers.sort(key=lambda m: m["id"] != top_id)
    t = run.timings
    telemetry = {
        "type": "telemetry",
        "rid": run.rid,
        "dom_ms": round(t.get("dom_ms", 0), 1),
        "resolve_ms": round(t.get("resolve_ms", 0), 1),
        "retrieval_ms": round(t.get("retrieval_ms", 0), 1),
        "replay_ms": round(t.get("replay_ms", 0)),
        "enrich_ms": round(t.get("enrich_ms", 0)),
        "total_ms": round(sum(t.values())),
        "tokens_naive": naive,
        "tokens_context": context,
        "compression": round(1 - context / naive, 4) if naive else 0,
        "ppr_top": round(top["ppr_raw"], 5) if top else 0,
        "s_graph_top": top["s_graph"] if top else 0,
        "s_time_top": top["s_time"] if top else 0,
        "s_sem_top": top["s_sem"] if top else 0,
        "score_top": top["score"] if top else 0,
        "candidates": search["candidates"],
        "curve": search["curve"],
        "markers": markers,
        "temporal": resolved.temporal.public() if resolved.temporal else None,
    }
    asyncio.create_task(hub.emit(dict(telemetry)))
    return telemetry


# ----------------------------------------------------------------------------- websocket
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    client = Client(ws)
    hub.clients.add(client)
    pump = asyncio.create_task(client.pump())
    client.push(json.dumps({"type": "status", **status_payload()}, default=str))
    if agent.last_frame:
        client.push_frame(agent.last_frame)
    if agent.page and agent.ready:
        client.push(json.dumps({"type": "url", "url": agent.page.url, "title": await agent.page.title()}))
        client.push(json.dumps({"type": "tabs", "tabs": await agent.tab_list()}))
        client.push(json.dumps({"type": "viewport", "w": agent.vw, "h": agent.vh}))
    try:
        while True:
            msg = json.loads(await ws.receive_text())
            kind = msg.get("type")
            if kind == "input":
                await agent.handle_input(msg)
            elif kind == "navigate":
                try:
                    await agent.navigate(str(msg.get("url", "")))
                except ValueError as exc:
                    client.push(json.dumps({"type": "browser_error", "message": str(exc)}))
            elif kind == "tab":
                action = msg.get("action")
                if action == "new":
                    url = msg.get("url")
                    asyncio.create_task(agent.new_tab(str(url) if url else None))
                elif action == "close" and isinstance(msg.get("id"), int):
                    await agent.close_tab(msg["id"])
                elif action == "switch" and isinstance(msg.get("id"), int):
                    await agent.switch_tab(msg["id"])
            elif kind == "resize":
                try:
                    await agent.resize(float(msg.get("w", 0)), float(msg.get("h", 0)))
                except (TypeError, ValueError):
                    pass
            elif kind == "ping":
                client.push(json.dumps({"type": "pong"}))
    except (WebSocketDisconnect, RuntimeError, json.JSONDecodeError):
        pass
    finally:
        hub.clients.discard(client)
        pump.cancel()


# ----------------------------------------------------------------------------- built UI (desktop app)
# Mounted last so /api, /ws and /portals keep priority. Built by `npm run build` in frontend/.
_UI_DIR = Path(__file__).resolve().parent.parent / "frontend" / "out"
if _UI_DIR.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=_UI_DIR, html=True), name="ui")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")
