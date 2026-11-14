"""Live web delta search: Telem AI + Tavily, filtered to content published after an episode.

Both providers run concurrently. Results are canonicalised, post-filtered on publish date,
then a *submodular* greedy selection (facility location + relevance) picks a small,
non-redundant set. Missing keys are reported as `not_configured` - nothing is faked.

Telem request/response field names are not formally documented to us, so the client sends
the common variants and parses the response defensively; any error is surfaced verbatim.
"""
from __future__ import annotations

import asyncio
import math
import re
import time
from collections import Counter
from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from config import settings
from vault_engine import approx_tokens, tokenize

# Allow-list of PUBLIC topic tags. Web queries are built ONLY from these canonical strings, so no
# private note text, names, course codes or URLs can ever leave the machine. Order = specificity.
PUBLIC_TOPICS: list[tuple[str, str]] = [
    ("Kalman-Bucy filter", r"kalman-bucy"),
    ("Extended Kalman Filter", r"extended kalman|\bekf\b"),
    ("Unscented Kalman Filter", r"\bukf\b|unscented"),
    ("adaptive Kalman filter", r"adaptive kalman"),
    ("Joseph form covariance update", r"joseph form"),
    ("Riccati recursion", r"riccati"),
    ("steady-state Kalman gain", r"steady-state kalman gain|kalman gain"),
    ("process noise covariance tuning", r"process noise|tuning q|\bq and r\b|q, r"),
    ("NEES consistency test", r"\bnees\b"),
    ("Ito's lemma", r"ito's lemma"),
    ("Ito isometry", r"ito isometry"),
    ("Ito calculus", r"\bito\b"),
    ("stochastic calculus", r"stochastic calculus"),
    ("stochastic differential equations", r"stochastic differential"),
    ("Brownian motion", r"brownian"),
    ("Kalman filter", r"kalman"),
    ("state-space model", r"state-space|state space"),
    ("state estimation", r"state[- ]estimation"),
    ("filter divergence", r"diverg"),
    ("positive definite covariance", r"positive definite"),
    ("float32 numerical precision", r"float32|float precision"),
    ("eigenvalue perturbation", r"eigenvalue perturbation"),
    ("Bauer-Fike theorem", r"bauer-fike"),
    ("diffusion models trajectory forecasting", r"diffusion model"),
    ("IMU drift", r"\bimu\b|drift"),
]


def extract_public_tags(text: str, limit: int = 6) -> list[str]:
    low = text.lower()
    return [tag for tag, rx in PUBLIC_TOPICS if re.search(rx, low)][:limit]


TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "ref", "fbclid", "gclid"}


def canonical_url(url: str) -> str:
    try:
        p = urlparse(url)
    except ValueError:
        return url
    host = p.netloc.lower().removeprefix("www.")
    q = urlencode([(k, v) for k, v in parse_qsl(p.query) if k.lower() not in TRACKING])
    return urlunparse(("https", host, p.path.rstrip("/") or "/", "", q, ""))


def _parse_date(raw: Any) -> datetime | None:
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip().replace("Z", "+00:00")
    for parse in (datetime.fromisoformat,):
        try:
            d = parse(s)
            return d.astimezone().replace(tzinfo=None) if d.tzinfo else d
        except ValueError:
            pass
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


def _first(d: dict, *keys: str) -> Any:
    for k in keys:
        v = d.get(k)
        if v:
            return v
    return None


def _normalise(item: dict, source: str) -> dict | None:
    url = _first(item, "url", "link", "href", "source_url")
    if not url:
        return None
    content = _first(item, "content", "summary", "excerpt", "snippet", "text", "description", "markdown") or ""
    published = _first(item, "publish_date", "published_date", "published_at", "publishedDate", "date", "published", "datePublished")
    provider = item.get("provider")
    if source == "telem" and isinstance(provider, str):
        source = f"telem:{provider}"
    return {
        "source": source,
        "title": str(_first(item, "title", "name") or url)[:200],
        "url": str(url),
        "content": str(content),
        "published": published if isinstance(published, str) else None,
        "provider_score": item.get("score"),
    }


def _extract_list(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("results", "data", "items", "documents", "hits", "web"):
            v = payload.get(key)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
            if isinstance(v, dict):
                inner = _extract_list(v)
                if inner:
                    return inner
    return []


def _telem_results(payload: Any) -> list[dict]:
    """Telem returns one run per provider: preprocessor_runs[i].output_payload.results (provider = preprocessor_name)."""
    items: list[dict] = []
    runs = payload.get("preprocessor_runs") if isinstance(payload, dict) else None
    if isinstance(runs, list):
        for run in runs:
            if not isinstance(run, dict) or run.get("error"):
                continue
            out = run.get("output_payload") or {}
            for res in out.get("results") or []:
                if isinstance(res, dict):
                    res = {**res, "provider": res.get("provider") or run.get("preprocessor_name")}
                    norm = _normalise(res, "telem")
                    if norm:
                        items.append(norm)
        return items
    return [x for x in (_normalise(i, "telem") for i in _extract_list(payload)) if x]


def _vec(text: str) -> dict[str, float]:
    c = Counter(tokenize(text))
    norm = math.sqrt(sum(v * v for v in c.values())) or 1.0
    return {k: v / norm for k, v in c.items()}


def _sim(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items())


def submodular_select(cands: list[dict], query: str, k: int = 6, lam: float = 0.7) -> list[dict]:
    """Greedy maximisation of f(S) = sum_i max_{j in S} sim(i, j) + lam * sum_{j in S} rel(j).

    Facility location is monotone submodular, so greedy gives a (1 - 1/e) approximation and
    naturally suppresses near-duplicates (a second copy adds ~0 marginal coverage).
    """
    if not cands:
        return []
    vecs = [_vec(c["title"] + " " + c["content"]) for c in cands]
    qv = _vec(query)
    rel = [_sim(qv, v) for v in vecs]
    n = len(cands)
    sim = [[_sim(vecs[i], vecs[j]) for j in range(n)] for i in range(n)]
    best_cover = [0.0] * n
    chosen: list[int] = []
    for _ in range(min(k, n)):
        gains = []
        for j in range(n):
            if j in chosen:
                continue
            cover = sum(max(0.0, sim[i][j] - best_cover[i]) for i in range(n))
            gains.append((cover + lam * rel[j], j))
        if not gains:
            break
        gain, j = max(gains)
        if gain <= 1e-6:
            break
        chosen.append(j)
        best_cover = [max(best_cover[i], sim[i][j]) for i in range(n)]
        cands[j]["marginal_gain"] = round(gain, 4)
        cands[j]["relevance"] = round(rel[j], 4)
    return [cands[j] for j in chosen]


class Federation:
    def __init__(self) -> None:
        self.timeout = httpx.Timeout(20.0)

    async def _telem(self, query: str, after: datetime | None, n: int) -> list[dict]:
        if not settings.telem_api_key:
            raise LookupError("not_configured")
        # https://hack.telem.ai/doc/resources/search-best-practices/ - auto-routing picks the providers per query;
        # published_after filters at the source and makes every result carry publish_date.
        headers = {"Authorization": f"Bearer {settings.telem_api_key.strip()}"}
        search: dict[str, Any] = {"auto_routing": "accuracy", "num_results": min(n, 20), "tier": "default"}
        if after:
            search["published_after"] = after.strftime("%Y-%m-%d")
        body: dict[str, Any] = {"user_input": {"query": query}, "search": search}
        async with httpx.AsyncClient(timeout=httpx.Timeout(45.0)) as client:
            r = await client.post(f"{settings.telem_base}/v1/search", json=body, headers=headers)
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
            items = _telem_results(r.json())
            # enrich thin results with /v1/fetch (page text), top 3 only
            thin = [it for it in items[:3] if len(it["content"]) < 200]

            async def fetch(it: dict) -> None:
                try:
                    fr = await client.post(f"{settings.telem_base}/v1/fetch", json={"urls": [it["url"]], "options": {"tier": "default"}}, headers=headers)
                    if fr.status_code < 400:
                        docs = _extract_list(fr.json())
                        doc = docs[0] if docs else {}
                        txt = _first(doc, "content", "text", "markdown", "summary")
                        if isinstance(txt, str) and txt:
                            it["content"] = txt
                            it["fetched"] = True
                except Exception as exc:  # fetch is best-effort enrichment
                    it["fetch_error"] = str(exc)[:120]

            await asyncio.gather(*(fetch(it) for it in thin))
            return items

    async def _tavily(self, query: str, after: datetime | None, n: int) -> list[dict]:
        if not settings.tavily_api_key:
            raise LookupError("not_configured")
        from tavily import AsyncTavilyClient

        client = AsyncTavilyClient(api_key=settings.tavily_api_key)
        kwargs: dict[str, Any] = {"query": query, "max_results": n, "search_depth": "basic"}
        if after:
            kwargs["start_date"] = after.strftime("%Y-%m-%d")
        data = await client.search(**kwargs)
        return [x for x in (_normalise(i, "tavily") for i in data.get("results", [])) if x]

    async def search(self, query: str, published_after: datetime | None, k: int = 6) -> dict[str, Any]:
        t0 = time.perf_counter()
        providers: dict[str, dict[str, Any]] = {}
        raw: list[dict] = []

        async def run(name: str, coro) -> None:
            t = time.perf_counter()
            try:
                items = await coro
                providers[name] = {"ok": True, "count": len(items), "ms": round((time.perf_counter() - t) * 1000)}
                raw.extend(items)
            except LookupError:
                providers[name] = {"ok": False, "status": "not_configured", "count": 0}
            except Exception as exc:
                providers[name] = {"ok": False, "status": "error", "error": str(exc)[:240], "count": 0,
                                   "ms": round((time.perf_counter() - t) * 1000)}

        await asyncio.gather(run("telem", self._telem(query, published_after, 8)), run("tavily", self._tavily(query, published_after, 8)))

        # canonical-URL dedup
        seen: dict[str, dict] = {}
        for it in raw:
            key = canonical_url(it["url"])
            if key in seen:
                seen[key].setdefault("also_from", []).append(it["source"])
                continue
            seen[key] = it
        unique = list(seen.values())

        # strict date post-filter where a date is known
        dropped = 0
        kept = []
        for it in unique:
            d = _parse_date(it.get("published"))
            if published_after and d and d < published_after:
                dropped += 1
                continue
            kept.append(it)

        selected = submodular_select(kept, query, k=k)
        tokens_raw = sum(approx_tokens(it["title"] + " " + it["content"]) for it in raw)
        for it in selected:
            words = re.sub(r"\s+", " ", it["content"]).split()
            it["snippet"] = " ".join(words[:60]) + (" ..." if len(words) > 60 else "")
            it.pop("content", None)
        tokens_kept = sum(approx_tokens(it["title"] + " " + it["snippet"]) for it in selected)
        return {
            "query": query,
            "published_after": published_after.isoformat() if published_after else None,
            "providers": providers,
            "raw_count": len(raw),
            "unique_count": len(unique),
            "date_filtered": dropped,
            "results": selected,
            "tokens_raw": tokens_raw,
            "tokens_kept": tokens_kept,
            "ms": round((time.perf_counter() - t0) * 1000),
        }
