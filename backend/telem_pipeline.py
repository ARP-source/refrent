"""Telem AI grounding pipeline, run on every restored recall.

Stage 1  Episodic query compiler -> Telem Search  (POST /v1/search)
         A vague human query ("that study guide Irina mentioned") has no usable web keywords.
         The vault graph has already resolved who/what/when; we compile ONLY public topic tags and the
         numeric drift into a precise query. Names, course codes, private text and URLs never leave.
Stage 2  Grounded drift verification -> Telem Fetch (POST /v1/fetch)
         Pull clean text from the top-ranked sources and look for passages that state how the edited
         quantities behave, then report whether the old snapshot or the new edit is consistent with them.
Stage 3  Continuous claim watch -> Telem Monitors (POST /v1/monitors)
         One click arms a monitor on the assumption; its live status is read back from Telem.

If TELEM_API_KEY is missing or a call fails, each stage says so and falls back to a small, clearly
labelled cached reference set, so the demo never hangs. Nothing cached is ever presented as live.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx

from config import settings

Emit = Callable[[dict[str, Any]], Awaitable[None]]
MONITORS_FILE = Path(__file__).resolve().parent / "telem_monitors.json"

# Cached, real public references used ONLY when Telem is unreachable. Text here is our own summary,
# never presented as a quote or as a live result.
FALLBACK_REFS = [
    {"title": "An Introduction to the Kalman Filter (Welch & Bishop, UNC TR 95-041)",
     "url": "https://www.cs.unc.edu/~welch/media/pdf/kalman_intro.pdf",
     "summary": "Summary: the Kalman gain grows as process noise Q grows relative to measurement noise R, so the "
                "filter trusts measurements more and its error covariance settles faster; smaller Q gives a smoother but slower filter."},
    {"title": "Kalman filter - Wikipedia",
     "url": "https://en.wikipedia.org/wiki/Kalman_filter",
     "summary": "Summary: the steady-state gain is fixed by the discrete algebraic Riccati equation in Q and R; "
                "the Q/R ratio sets the trade-off between responsiveness and noise rejection."},
]

# How quantities in the demo domain behave, as evidence patterns we look for in fetched text.
# key -> (label, regex for evidence when the value went UP, regex for evidence when it went DOWN)
_GAINS = r"(gain|faster|respons|converg|trust|weight|track|agile|quick)"
_UP = r"(increas|larg|high|bigger|more|greater|grow|rais)"
_DOWN = r"(decreas|small|low|reduc)"
CLAIMS: dict[str, tuple[str, str, str]] = {
    "Q": ("process noise covariance Q",
          _UP + r"\w*[^.]{0,80}(process noise|\bQ\b)[^.]{0,140}" + _GAINS +
          r"|(process noise|\bQ\b)[^.]{0,60}" + _UP + r"\w*[^.]{0,140}" + _GAINS,
          _DOWN + r"\w*[^.]{0,80}(process noise|\bQ\b)[^.]{0,140}(smooth|slow|lag|sluggish|trust[^.]{0,20}model)"),
    "R": ("measurement noise covariance R",
          _UP + r"\w*[^.]{0,80}(measurement noise|\bR\b)[^.]{0,140}(smaller gain|lower gain|less weight|slow|smooth|trust[^.]{0,20}(model|prediction))",
          _DOWN + r"\w*[^.]{0,80}(measurement noise|\bR\b)[^.]{0,140}" + _GAINS +
          r"|(measurement noise|\bR\b)[^.]{0,60}" + _DOWN + r"\w*[^.]{0,140}" + _GAINS),
}
# Raising Q or lowering R both raise the Q/R ratio; statements about that ratio support either edit.
_RATIO = (r"|(ratio|relative)[^.]{0,60}(process noise|\bQ\b)[^.]{0,80}(measurement noise|\bR\b)[^.]{0,160}" + _GAINS +
          r"|(process noise|\bQ\b)[^.]{0,40}(relative to|compared to|versus|vs\.?)[^.]{0,20}(measurement noise|\bR\b)[^.]{0,160}" + _GAINS +
          r"|\bQ\s*/\s*R\b[^.]{0,30}" + _UP + r"\w*[^.]{0,120}" + _GAINS)
CLAIMS = {k: (n, up + _RATIO if k == "Q" else up, down + _RATIO if k == "R" else down) for k, (n, up, down) in CLAIMS.items()}
GENERIC_EVIDENCE = re.compile(r"(kalman gain|process noise|measurement noise|riccati|steady[- ]state|converg|covariance)", re.I)


def _num(s: str) -> float | None:
    m = re.search(r"-?\d+(?:\.\d+)?", s or "")
    return float(m.group()) if m else None


def label_changes(changes: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Name each numeric edit from the snapshot text: 'Q = 0.01' -> Q, 'about 120 steps' -> steps."""
    if not changes or changes.get("status") != "changed":
        return []
    old = changes.get("before") or ""
    out = []
    for c in changes.get("changes") or []:
        b, a = _num(c.get("before", "")), _num(c.get("after", ""))
        if b is None or a is None or b == a:
            continue
        token = re.escape(c["before"].split()[0]) if c.get("before") else ""
        label = None
        m = re.search(r"\b([A-Za-z]\w{0,10})\s*=\s*" + token, old)
        if m:
            label = m.group(1)
        else:
            m = re.search(token + r"\s+([A-Za-z]+)", old)
            if m:
                label = m.group(1)
        out.append({"label": label or "value", "before": c["before"], "after": c["after"], "from": b, "to": a,
                    "direction": "up" if a > b else "down"})
    return out[:4]


def compile_query(raw: str, resolved: dict[str, Any], tags: list[str], edits: list[dict[str, Any]]) -> dict[str, Any]:
    """Private anchors stay local; only public topic tags and the numeric drift are compiled into the web query."""
    entities = []
    if resolved.get("person"):
        entities.append({"kind": "person", "value": resolved["person"]["name"], "sent": False})
    if resolved.get("context") and resolved["context"].get("name"):
        entities.append({"kind": resolved["context"].get("type") or "context", "value": resolved["context"]["name"], "sent": False})
    if resolved.get("temporal") and resolved["temporal"].get("label"):
        entities.append({"kind": "time", "value": resolved["temporal"]["label"], "sent": False})
    entities += [{"kind": "topic", "value": t, "sent": True} for t in tags[:4]]
    drift_terms = [f"{e['label']}={e['before']} vs {e['label']}={e['after']}" for e in edits if e["label"] in ("Q", "R")]
    words = list(tags[:4])
    if drift_terms:
        words += ["Riccati covariance", "steady-state convergence"]
    compiled = " ".join(dict.fromkeys(" ".join(words).split()))
    if drift_terms:
        compiled += " " + " ".join(drift_terms)
    # claim-verification query: asks the web how the edited quantities behave, independent of our numbers
    moved = {e["label"]: e["direction"] for e in edits if e["label"] in ("Q", "R")}
    claim = None
    if moved:
        parts = []
        if "Q" in moved:
            parts.append(f"{'increasing' if moved['Q'] == 'up' else 'decreasing'} process noise covariance Q")
        if "R" in moved:
            parts.append(f"{'increasing' if moved['R'] == 'up' else 'decreasing'} measurement noise covariance R")
        claim = f"effect of {' and '.join(parts)} on Kalman gain and convergence speed (Q/R ratio tuning)"
    return {"raw": raw, "entities": entities, "drift_terms": drift_terms, "compiled": compiled.strip() or " ".join(tags), "claim": claim}


def _verdict(edits: list[dict[str, Any]], passages: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare the direction of each edit with what the grounded passages say about that quantity."""
    checks = []
    for e in edits:
        claim = CLAIMS.get(e["label"])
        if not claim:
            continue
        name, up_rx, down_rx = claim
        rx = up_rx if e["direction"] == "up" else down_rx
        hits = [p for p in passages if re.search(rx, p["text"], re.I)]
        checks.append({"label": e["label"], "name": name, "edit": f"{e['before']} -> {e['after']}",
                       "direction": e["direction"], "supported": bool(hits), "evidence": [h["id"] for h in hits[:2]]})
    steps = next((e for e in edits if e["label"].lower().startswith("step")), None)
    if not checks:
        return {"status": "context_only", "checks": [],
                "headline": "No tunable quantity changed in this section; Telem sources are shown as context."}
    edits_txt = ", ".join(f"{c['label']} {c['edit']}" for c in checks)
    if all(c["supported"] for c in checks):
        tail = f" The faster convergence ({steps['before']} -> {steps['after']} steps) is the expected effect; the exact count is model-specific." if steps else ""
        return {"status": "edit_supported", "checks": checks,
                "headline": f"Live edit is grounded: sources state that {edits_txt} raises the Kalman gain and speeds convergence. The snapshot's values were a slower, smoother tuning, not an error.{tail}"}
    if any(c["supported"] for c in checks):
        return {"status": "partially_supported", "checks": checks,
                "headline": "Partly grounded: " + ", ".join(f"{c['label']} {'supported' if c['supported'] else 'not stated in the sources'}" for c in checks) + "."}
    return {"status": "unverified", "checks": checks,
            "headline": f"The fetched sources did not state how {edits_txt} behaves. Treat the edit as unverified."}


def _passages(doc_id: int, url: str, title: str, text: str, query: str) -> list[dict[str, Any]]:
    sents = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", re.sub(r"[#*_`>|\[\]$\\]", " ", text)))
    qwords = set(re.findall(r"[a-z]{4,}", query.lower()))
    scored = []
    for s in sents:
        if not (40 <= len(s) <= 420) or not GENERIC_EVIDENCE.search(s):
            continue
        scored.append((len(qwords & set(re.findall(r"[a-z]{4,}", s.lower()))), s.strip()))
    scored.sort(key=lambda x: -x[0])
    return [{"id": f"{doc_id}:{i}", "url": url, "title": title, "text": s} for i, (_, s) in enumerate(scored[:150])]


class TelemPipeline:
    def __init__(self) -> None:
        self.base = settings.telem_base.rstrip("/")
        try:
            self.monitors: dict[str, dict[str, Any]] = json.loads(MONITORS_FILE.read_text("utf-8"))
        except (OSError, ValueError):
            self.monitors = {}

    @property
    def host(self) -> str:
        return re.sub(r"^https?://", "", self.base).split("/")[0]

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {settings.telem_api_key.strip()}", "Content-Type": "application/json"}

    async def _post(self, client: httpx.AsyncClient, path: str, body: dict[str, Any], timeout: float) -> Any:
        r = await client.post(self.base + path, json=body, headers=self._headers(), timeout=timeout)
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        return r.json()

    # ------------------------------------------------------------------ stage 1
    async def search(self, client: httpx.AsyncClient, queries: list[str]) -> dict[str, Any]:
        """One batched Telem call: [0] the graph-compiled query, [1] (optional) the claim-verification query."""
        t = time.perf_counter()
        if not settings.telem_api_key:
            return {"ok": False, "status": "not_configured", "ms": 0, "results": [], "providers": []}
        try:
            data = await self._post(client, "/v1/search", {"user_input": [{"query": q} for q in queries],
                                                            "search": {"auto_routing": "accuracy", "num_results": 5, "tier": "default"}}, 25)
        except Exception as exc:
            return {"ok": False, "status": "error", "error": str(exc)[:200], "ms": round((time.perf_counter() - t) * 1000), "results": [], "providers": []}
        hits, providers = [], []
        for run in data.get("preprocessor_runs") or []:
            name = run.get("preprocessor_name")
            batch = int(run.get("batch_index") or 0)
            if not any(p["name"] == name for p in providers):
                providers.append({"name": name, "ok": not run.get("error") and run.get("status") == "succeeded"})
            for i, res in enumerate((run.get("output_payload") or {}).get("results") or []):
                if isinstance(res, dict) and res.get("url"):
                    hits.append({"title": str(res.get("title") or res["url"])[:200], "url": res["url"], "provider": res.get("provider") or name,
                                 "rank": res.get("rank") or i + 1, "batch": batch,
                                 "snippet": re.sub(r"\s+", " ", str(res.get("excerpt") or res.get("summary") or res.get("content") or ""))[:280]})
        # reciprocal-rank fusion across Telem's routed providers: agreement between providers lifts a source
        fused: dict[str, dict[str, Any]] = {}
        for h in hits:
            key = h["url"].split("#")[0].rstrip("/").lower()
            f = fused.setdefault(key, {**h, "rrf": 0.0, "providers": [], "batches": []})
            f["rrf"] += 1 / (60 + int(h["rank"]))
            if h["batch"] not in f["batches"]:
                f["batches"].append(h["batch"])
            if h["provider"] not in f["providers"]:
                f["providers"].append(h["provider"])
            if len(h["snippet"]) > len(f["snippet"]):
                f["snippet"] = h["snippet"]
        ranked = sorted(fused.values(), key=lambda r: -r["rrf"])
        top = ranked[0]["rrf"] if ranked else 1
        for r in ranked:
            r["score"] = round(r.pop("rrf") / top, 3)
        return {"ok": True, "status": "live", "ms": round((time.perf_counter() - t) * 1000), "session_id": data.get("session_id"),
                "providers": providers, "raw_hits": len(hits), "queries": len(queries), "results": ranked[:8]}

    # ------------------------------------------------------------------ stage 2
    async def fetch(self, client: httpx.AsyncClient, urls: list[str]) -> dict[str, Any]:
        t = time.perf_counter()
        if not urls:
            return {"ok": False, "status": "skipped", "ms": 0, "docs": []}
        try:
            data = await self._post(client, "/v1/fetch", {"urls": urls[:5], "options": {"tier": "default", "inline_max_chars": 60000}}, 25)
        except Exception as exc:
            return {"ok": False, "status": "error", "error": str(exc)[:200], "ms": round((time.perf_counter() - t) * 1000), "docs": []}
        items: list[Any] = []
        for run in (data.get("preprocessor_runs") or []) if isinstance(data, dict) else []:
            items += (run.get("output_payload") or {}).get("fetched_results") or []
        if not items:
            items = data if isinstance(data, list) else next((data[k] for k in ("results", "data", "documents") if isinstance(data.get(k), list)), [])
        docs = []
        for i, d in enumerate(items):
            if not isinstance(d, dict):
                continue
            text = d.get("content") or d.get("markdown") or d.get("text") or ""
            ok = d.get("status", "succeeded") == "succeeded" and d.get("http_status") in (None, 200) and len(text) > 200
            docs.append({"url": d.get("canonical_url") or d.get("url") or urls[min(i, len(urls) - 1)], "title": d.get("title"), "ok": ok,
                         "chars": len(text), "provider": d.get("provider"), "text": text if ok else "", "error": d.get("error")})
        return {"ok": any(d["ok"] for d in docs), "status": "live", "ms": round((time.perf_counter() - t) * 1000), "docs": docs}

    # ------------------------------------------------------------------ full run
    async def run(self, emit: Emit, rid: str, note: Any, raw_query: str, resolved: dict[str, Any], tags: list[str],
                  changes: dict[str, Any] | None) -> dict[str, Any]:
        t0 = time.perf_counter()
        edits = label_changes(changes)
        compiled = compile_query(raw_query, resolved, tags, edits)
        state: dict[str, Any] = {"type": "telem", "rid": rid, "note_id": note.id, "note_title": note.title, "host": self.host,
                                 "configured": bool(settings.telem_api_key), "query": compiled, "edits": edits,
                                 "stage": "search", "search": None, "fetch": None, "verdict": None,
                                 "monitor": self.monitors.get(note.id), "fallback": False, "since": note.timestamp.isoformat() if note.timestamp else None}
        await emit(dict(state))
        async with httpx.AsyncClient() as client:
            s = await self.search(client, [compiled["compiled"]] + ([compiled["claim"]] if compiled.get("claim") else []))
            state.update({"search": s, "stage": "fetch"})
            await emit(dict(state))
            # fetch the best sources for each query: claim-verification hits first, then the compiled-query hits
            claim_hits = [r["url"] for r in s.get("results", []) if 1 in r.get("batches", [])][:3]
            urls = list(dict.fromkeys(claim_hits + [r["url"] for r in s.get("results", [])]))[:5]
            f = await self.fetch(client, urls) if s.get("ok") else {"ok": False, "status": "skipped", "ms": 0, "docs": []}
        passages: list[dict[str, Any]] = []
        for i, d in enumerate(f.get("docs", [])):
            if d.get("ok"):
                passages += _passages(i, d["url"], d.get("title") or "", d["text"], compiled["compiled"])
        # search snippets are grounded text too
        passages += [{"id": f"s:{i}", "url": r["url"], "title": r["title"], "text": r["snippet"]} for i, r in enumerate(s.get("results", [])) if r.get("snippet")]
        verdict = _verdict(edits, passages)
        if verdict["status"] in ("unverified", "context_only") and not (s.get("ok") and f.get("ok")):
            # Telem unreachable: fall back to cached reference summaries, clearly labelled
            state["fallback"] = True
            cached = [{"id": f"cache:{i}", "url": r["url"], "title": r["title"], "text": r["summary"], "cached": True} for i, r in enumerate(FALLBACK_REFS)]
            verdict = _verdict(edits, cached)
            passages = cached
        # one citation per checked quantity first (Q's evidence, R's evidence), then any other supporting passage
        order = list(dict.fromkeys([c["evidence"][0] for c in verdict["checks"] if c["evidence"]] + [e for c in verdict["checks"] for e in c["evidence"]]))
        by_id = {p["id"]: p for p in passages}
        picks = [by_id[i] for i in order if i in by_id] or passages[:2]
        verdict["citations"] = [{**p, "text": p["text"][:320]} for p in picks[:2]]
        state.update({"stage": "done", "verdict": verdict, "passages_scanned": len(passages), "ms": round((time.perf_counter() - t0) * 1000),
                      "fetch": {k: v for k, v in f.items() if k != "docs"} | {"docs": [{k: v for k, v in d.items() if k != "text"} for d in f.get("docs", [])]}})
        await emit(dict(state))
        return state

    # ------------------------------------------------------------------ stage 3: monitors
    def _save(self) -> None:
        try:
            MONITORS_FILE.write_text(json.dumps(self.monitors, indent=2), "utf-8")
        except OSError:
            pass

    async def arm_monitor(self, note: Any, tags: list[str], edits: list[dict[str, Any]]) -> dict[str, Any]:
        if not settings.telem_api_key:
            raise RuntimeError("TELEM_API_KEY is not configured")
        topic = ", ".join(tags[:3]) or "this topic"
        drift = "; ".join(f"{e['label']} {e['before']} vs {e['after']}" for e in edits if e["label"] in ("Q", "R"))
        query = f"New research, tutorials or errata on {topic}" + (f", especially evidence about {drift} and steady-state Kalman convergence" if drift else "")
        async with httpx.AsyncClient() as client:
            data = await self._post(client, "/v1/monitors", {"query": query[:400], "options": {"frequency": "1d"}, "ttl": "14d"}, 25)
        mon = data.get("monitor") if isinstance(data.get("monitor"), dict) else data
        if not mon.get("id"):
            raise RuntimeError(f"Telem did not return a monitor id: {str(data)[:200]}")
        rec = {"id": mon["id"], "query": mon.get("query") or query, "status": mon.get("status") or "active",
               "frequency": mon.get("frequency") or "1d", "created_at": mon.get("created_at"), "expires_at": mon.get("expires_at"),
               "agent_note": data.get("agent_note"), "note_id": note.id, "topic": topic}
        self.monitors[note.id] = rec
        self._save()
        return rec

    async def refresh_monitor(self, note_id: str) -> dict[str, Any] | None:
        rec = self.monitors.get(note_id)
        if not rec or not settings.telem_api_key:
            return rec
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{self.base}/v1/monitors/{rec['id']}", headers=self._headers(), timeout=10)
            if r.status_code == 404:
                rec["status"] = "ended"
            elif r.status_code < 400:
                m = r.json()
                m = m.get("monitor", m) if isinstance(m, dict) else {}
                rec.update({k: m[k] for k in ("status", "last_polled_at", "expires_at", "frequency") if m.get(k) is not None})
                if (m.get("agent_state") or {}).get("status"):
                    rec["agent_status"] = m["agent_state"]["status"]
            rec.pop("refresh_error", None)
            self._save()
        except Exception as exc:
            rec["refresh_error"] = str(exc)[:160]
        return rec


pipeline = TelemPipeline()


async def safe_run(*args: Any, **kwargs: Any) -> dict[str, Any] | None:
    try:
        return await pipeline.run(*args, **kwargs)
    except Exception as exc:  # grounding must never break a recall
        print(f"[telem] pipeline failed: {exc}")
        return None


# ---------------------------------------------------------------------------- assistant web tasks
EMAIL_RX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RX = re.compile(r"(?:\+?\d{1,2}[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}")
PROFILE_RX = re.compile(r"https?://(?:www\.)?(?:linkedin\.com/in|twitter\.com|x\.com|github\.com|scholar\.google\.com/citations)[^\s)\]\"'>]+", re.I)
_JUNK_EMAIL = re.compile(r"(example\.|sentry|noreply|no-reply|wixpress|\.png|\.jpg|\.svg|@2x)", re.I)


async def web_task(message: str, want_contacts: bool) -> dict[str, Any]:
    """Run a user-requested web task through Telem: search, fetch the top pages, pull out contacts and links."""
    async with httpx.AsyncClient() as client:
        s = await pipeline.search(client, [message])
        urls = [r["url"] for r in s.get("results", [])[:3]]
        f = await pipeline.fetch(client, urls) if (s.get("ok") and want_contacts and urls) else {"ok": False, "docs": [], "ms": 0}
    contacts: list[dict[str, str]] = []
    seen: set[str] = set()
    for d in f.get("docs", []):
        text = d.get("text") or ""
        found = [("email", e) for e in EMAIL_RX.findall(text) if not _JUNK_EMAIL.search(e)]
        found += [("phone", p.strip()) for p in PHONE_RX.findall(text)]
        found += [("profile", u.rstrip(".,;")) for u in PROFILE_RX.findall(text)]
        for kind, value in found:
            if value.lower() not in seen and len(contacts) < 12:
                seen.add(value.lower())
                contacts.append({"type": kind, "value": value, "source": d["url"]})
    return {"ok": s.get("ok", False), "status": s.get("status"), "error": s.get("error"),
            "results": [{"title": r["title"], "url": r["url"], "snippet": r["snippet"], "providers": r["providers"]} for r in s.get("results", [])[:6]],
            "contacts": contacts, "search_ms": s.get("ms", 0), "fetch_ms": f.get("ms", 0), "fetched": len([d for d in f.get("docs", []) if d.get("ok")])}
