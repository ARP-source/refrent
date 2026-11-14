"""Deictic + temporal resolver.

Turns "what is she talking about from 2 weeks ago?" into
    expanded query  : "what is Dana Chen talking about" (+ course context)
    temporal window : mu = now - 14d, sigma = 3.5d  (Gaussian)
using the *live DOM* of the page the user is looking at:

* pronouns (she/he/they/her/...) -> person entities on screen, matched on pronouns,
  ranked by viewport visibility and distance from the viewport centre;
* demonstratives (this/that/here) -> the page-level context entity (course, document, repo);
* relative time expressions -> a Gaussian window over timestamps.

If the DOM is ambiguous and an LLM key is configured, the LLM is asked to break the tie
(it only sees entity names and the query). The decision is always shown in the trace.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import httpx

from config import settings

NUM_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "couple": 2, "few": 3,
}
UNIT_DAYS = {"day": 1.0, "week": 7.0, "month": 30.0}

PRONOUN_CLASS = {
    "she": "she", "her": "she", "hers": "she", "herself": "she",
    "he": "he", "him": "he", "his": "he", "himself": "he",
    "they": "they", "them": "they", "their": "they", "theirs": "they",
}
DEMONSTRATIVES = {"this", "that", "these", "those", "here", "current"}
ANCHOR_RE = re.compile(
    r"\b(right before|just before|before|ahead of|prior to|right after|just after|after)\s+(?:the\s+|my\s+)?(.+?)\s*(?:[?!,;]|\.\s*$|$)",
    re.I,
)

REL_RE = re.compile(
    r"\b(?P<num>\d+|a\s+couple(?:\s+of)?|a\s+few|couple(?:\s+of)?|few|a|an|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
    r"(?P<unit>day|week|month)s?\s+ago\b",
    re.I,
)
SIMPLE_TIME = [
    (re.compile(r"\byesterday\b", re.I), 1.0, 0.5),
    (re.compile(r"\blast\s+night\b", re.I), 1.0, 0.4),
    (re.compile(r"\b(?:earlier\s+)?today\b|\bthis\s+morning\b", re.I), 0.0, 0.5),
    (re.compile(r"\blast\s+week\b", re.I), 7.0, 3.0),
    (re.compile(r"\bearlier\s+this\s+week\b|\bthis\s+week\b", re.I), 2.0, 2.0),
    (re.compile(r"\blast\s+month\b", re.I), 30.0, 8.0),
    (re.compile(r"\bthe\s+other\s+day\b", re.I), 3.0, 1.5),
]


@dataclass
class TemporalWindow:
    mu: datetime
    sigma: timedelta
    phrase: str
    label: str

    def public(self) -> dict[str, Any]:
        return {
            "mu": self.mu.isoformat(),
            "sigma_days": round(self.sigma.total_seconds() / 86400, 2),
            "phrase": self.phrase,
            "label": self.label,
        }


@dataclass
class Resolved:
    original: str
    expanded_query: str
    person: dict[str, Any] | None = None
    context: dict[str, Any] | None = None
    temporal: TemporalWindow | None = None
    entity_names: list[str] = field(default_factory=list)
    pronouns: list[str] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    anchor_rel: str | None = None  # "before" | "after"
    anchor_phrase: str | None = None

    def public(self) -> dict[str, Any]:
        return {
            "anchor_rel": self.anchor_rel,
            "anchor_phrase": self.anchor_phrase,
            "original": self.original,
            "expanded_query": self.expanded_query,
            "person": self.person,
            "context": self.context,
            "temporal": self.temporal.public() if self.temporal else None,
            "entity_names": self.entity_names,
            "pronouns": self.pronouns,
            "candidates": self.candidates,
        }


def parse_temporal(query: str, now: datetime) -> tuple[TemporalWindow | None, str]:
    """Return (window, query_without_time_phrase)."""
    m = REL_RE.search(query)
    if m:
        raw = re.sub(r"\s+", " ", m.group("num").lower())
        if raw.isdigit():
            n = int(raw)
        elif "couple" in raw:
            n = 2
        elif "few" in raw:
            n = 3
        else:
            n = NUM_WORDS.get(raw, 1)
        unit = m.group("unit").lower()
        days = n * UNIT_DAYS[unit]
        win = TemporalWindow(
            mu=now - timedelta(days=days),
            sigma=timedelta(days=max(1.0, 0.25 * days)),
            phrase=m.group(0),
            label=f"{n} {unit}{'s' if n != 1 else ''} ago",
        )
        return win, query[: m.start()] + query[m.end():]
    for rx, days, sigma_days in SIMPLE_TIME:
        m = rx.search(query)
        if m:
            win = TemporalWindow(
                mu=now - timedelta(days=days),
                sigma=timedelta(days=sigma_days),
                phrase=m.group(0),
                label=m.group(0).lower(),
            )
            return win, query[: m.start()] + query[m.end():]
    return None, query


def _clean(q: str) -> str:
    q = re.sub(r"\b(from|since|about|in|during|of|around|at)\s*[?.!]*\s*$", "", q.strip(), flags=re.I)
    q = re.sub(r"\s+", " ", q).strip(" ,.;?!")
    return q


class DeicticResolver:
    async def resolve(self, query: str, dom: dict[str, Any], now: datetime | None = None) -> Resolved:
        now = now or datetime.now()
        res = Resolved(original=query, expanded_query=query)
        trace = res.trace

        # 1. temporal ---------------------------------------------------------
        win, q_wo_time = parse_temporal(query, now)
        res.temporal = win
        if win:
            trace.append(
                {
                    "step": "temporal",
                    "title": "Relative time -> Gaussian window",
                    "detail": f'"{win.phrase}" resolves to mu = {win.mu:%Y-%m-%d}, sigma = {win.sigma.total_seconds()/86400:.2f} d',
                    "math": "S_time(t) = exp(-(t - mu)^2 / (2 sigma^2))",
                }
            )
        else:
            trace.append(
                {
                    "step": "temporal",
                    "title": "No time expression",
                    "detail": "No relative time found; S_time weight is redistributed to semantic + graph scores.",
                }
            )

        # 2. pronouns / demonstratives ---------------------------------------
        words = re.findall(r"[A-Za-z']+", q_wo_time.lower())
        res.pronouns = sorted({PRONOUN_CLASS[w] for w in words if w in PRONOUN_CLASS})
        has_demo = any(w in DEMONSTRATIVES for w in words)
        entities = dom.get("entities", []) or []
        ctx = dom.get("context")
        trace.append(
            {
                "step": "dom",
                "title": "Active DOM inspected",
                "detail": f'{dom.get("title") or "page"} - {len(entities)} entities on page, '
                f'{sum(1 for e in entities if e.get("inViewport"))} in viewport'
                + (f', page context = {ctx.get("type")}:{ctx.get("name")}' if ctx else ""),
            }
        )

        expanded = q_wo_time
        if res.pronouns:
            person = await self._resolve_person(res, entities, query)
            if person:
                res.person = person
                name = person["name"]
                expanded = re.sub(r"\b(her|his|their)\b", name + "'s", expanded, flags=re.I)
                expanded = re.sub(r"\b(she|he|they|hers|him|them|herself|himself)\b", name, expanded, flags=re.I)
        if ctx:
            res.context = ctx
        if has_demo and ctx:
            expanded = f"{expanded} {ctx.get('name', '')}".strip()
            trace.append(
                {
                    "step": "demonstrative",
                    "title": 'Demonstrative ("this/that/here") -> page context',
                    "detail": f'Bound to {ctx.get("type")} "{ctx.get("name")}" from the active page',
                }
            )
        elif ctx:
            trace.append(
                {
                    "step": "demonstrative",
                    "title": "Page context used as graph seed",
                    "detail": f'{ctx.get("type")} "{ctx.get("name")}" seeds Personalized PageRank',
                }
            )

        am = ANCHOR_RE.search(q_wo_time)
        if am:
            res.anchor_rel = "after" if "after" in am.group(1).lower() else "before"
            res.anchor_phrase = am.group(2).strip()

        res.expanded_query = _clean(expanded)
        names: list[str] = []
        if res.person:
            names.append(res.person["name"])
        if ctx and ctx.get("name"):
            names.append(ctx["name"])
        res.entity_names = names
        trace.append(
            {
                "step": "rewrite",
                "title": "Query rewritten",
                "detail": f'"{query}"  ->  "{res.expanded_query}"',
            }
        )
        return res

    # ------------------------------------------------------------------ helpers
    async def _resolve_person(self, res: Resolved, entities: list[dict], query: str) -> dict[str, Any] | None:
        people = [e for e in entities if e.get("type") == "person"]
        wanted = res.pronouns
        matches = [p for p in people if not p.get("pronouns") or any(w in p["pronouns"].split(",") for w in wanted)]
        if "they" in wanted and not matches:  # singular "they" can refer to anyone
            matches = people
        matches.sort(key=lambda p: (not p.get("inViewport"), p.get("dist", 1e9)))
        res.candidates = [
            {"name": p["name"], "pronouns": p.get("pronouns", ""), "inViewport": p.get("inViewport", False), "dist": p.get("dist")}
            for p in matches
        ]
        if not matches:
            res.trace.append(
                {
                    "step": "pronoun",
                    "title": f'Pronoun "{"/".join(wanted)}" - no matching person on screen',
                    "detail": "Nothing on the page matches; falling back to semantic search only.",
                }
            )
            return None
        top = matches[0]
        ambiguous = len(matches) > 1 and (
            matches[0].get("inViewport") == matches[1].get("inViewport")
            and abs(matches[0].get("dist", 0) - matches[1].get("dist", 0)) < 40
        )
        how = "viewport proximity"
        if ambiguous:
            llm_pick = await self._llm_pick(query, matches)
            if llm_pick:
                top = next((m for m in matches if m["name"] == llm_pick), top)
                how = "LLM tie-break"
            else:
                how = "viewport proximity (near-tie, no LLM tie-break available)"
        res.trace.append(
            {
                "step": "pronoun",
                "title": f'Pronoun "{"/".join(wanted)}" -> {top["name"]}',
                "detail": f"{len(matches)} candidate(s) on page; chosen by {how}"
                + (f' ({top.get("role")})' if top.get("role") else ""),
            }
        )
        return {k: top.get(k) for k in ("name", "pronouns", "role", "inViewport", "dist")}

    async def _llm_pick(self, query: str, cands: list[dict]) -> str | None:
        if not (settings.anthropic_api_key or settings.openai_api_key):
            return None
        prompt = (
            f"A user is looking at a web page and asked: {query!r}. "
            f"Candidate people visible on the page: {json.dumps([c['name'] for c in cands])}. "
            'Reply with JSON only: {"person": "<exact name from the list>"}.'
        )
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                if settings.anthropic_api_key:
                    r = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": settings.anthropic_api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={
                            "model": settings.anthropic_model,
                            "max_tokens": 60,
                            "messages": [{"role": "user", "content": prompt}],
                        },
                    )
                    r.raise_for_status()
                    text = r.json()["content"][0]["text"]
                else:
                    r = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                        json={
                            "model": settings.openai_model,
                            "max_tokens": 60,
                            "messages": [{"role": "user", "content": prompt}],
                        },
                    )
                    r.raise_for_status()
                    text = r.json()["choices"][0]["message"]["content"]
            m = re.search(r"\{.*\}", text, re.S)
            name = json.loads(m.group(0)).get("person") if m else None
            return name if name in {c["name"] for c in cands} else None
        except Exception as exc:
            print(f"[resolver] LLM tie-break failed: {exc}")
            return None
