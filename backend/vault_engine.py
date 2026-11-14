"""Obsidian vault engine.

* Parses Markdown notes with YAML frontmatter and [[WikiLinks]].
* Builds a NetworkX graph of the links (episodes <-> entity hubs <-> episodes).
* Scores episodes with three signals:
    S_sem   hybrid lexical-vector similarity (BM25 + hashed TF-IDF cosine)
    S_time  Gaussian temporal decay around the time resolved from the query
    S_graph Personalized PageRank over the WikiLink graph
"""
from __future__ import annotations

import math
import re
import threading
import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import networkx as nx
import yaml

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]")
FM_RE = re.compile(r"\A---\s*\r?\n(.*?)\r?\n---\s*\r?\n?(.*)\Z", re.S)
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-]*")
STOP = set(
    """a an the and or but if of to in on at by for with from as is are was were be been being it its this that
    these those i me my we our you your he she they them his her their him what which who whom how when where why
    do does did doing have has had having not no so than too very can could should would will just about into over
    after before up down out off then there here also some any each""".split()
)
HASH_DIM = 1024


def tokenize(text: str) -> list[str]:
    out = []
    for tok in TOKEN_RE.findall(text.lower()):
        if tok in STOP or len(tok) < 2:
            continue
        if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
            tok = tok[:-1]
        out.append(tok)
    return out


def approx_tokens(text: str) -> int:
    """Cheap, deterministic token estimate (~0.75 words per token for English)."""
    return int(math.ceil(len(text.split()) / 0.75)) if text.strip() else 0


@dataclass
class Note:
    id: str
    path: Path
    title: str
    type: str
    timestamp: datetime | None
    url: str | None
    meta: dict[str, Any]
    body: str
    raw_links: list[str]
    people: list[str]
    entities: list[str]
    tokens: list[str] = field(default_factory=list)

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "url": self.url,
            "people": self.people,
            "entities": self.entities,
            "selector": self.meta.get("selector"),
            "text_fragment": self.meta.get("text_fragment"),
            "portal": self.meta.get("portal"),
            "actions": self.meta.get("actions", []),
            "session": self.meta.get("session", {}),
        }


def parse_markdown(path: Path, raw: str) -> Note:
    meta: dict[str, Any] = {}
    body = raw
    m = FM_RE.match(raw)
    if m:
        loaded = yaml.safe_load(m.group(1)) or {}
        if isinstance(loaded, dict):
            meta = loaded
        body = m.group(2)
    ts = meta.get("timestamp")
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts)
        except ValueError:
            ts = None
    elif not isinstance(ts, datetime):
        ts = None
    if ts is not None and ts.tzinfo is not None:
        ts = ts.astimezone().replace(tzinfo=None)
    links = [m.group(1).strip() for m in WIKILINK_RE.finditer(body)]
    return Note(
        id=path.stem,
        path=path,
        title=str(meta.get("title") or path.stem),
        type=str(meta.get("type") or "note"),
        timestamp=ts,
        url=meta.get("url"),
        meta=meta,
        body=body,
        raw_links=links,
        people=[str(p) for p in meta.get("people", []) or []],
        entities=[str(e) for e in meta.get("entities", []) or []],
    )


def _hash_features(tokens: list[str]) -> Counter:
    feats: Counter = Counter()
    for t in tokens:
        feats[t] += 1
    for a, b in zip(tokens, tokens[1:]):
        feats[a + "_" + b] += 1
    return feats


def _hash_vec(weights: dict[str, float]) -> dict[int, float]:
    vec: dict[int, float] = defaultdict(float)
    for feat, w in weights.items():
        h = zlib.crc32(feat.encode())
        sign = 1.0 if (h >> 31) & 1 else -1.0
        vec[h % HASH_DIM] += sign * w
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {k: v / norm for k, v in vec.items()}


def _cos(a: dict[int, float], b: dict[int, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items())


class Vault:
    def __init__(self, directory: Path):
        self.dir = directory
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.notes: dict[str, Note] = {}
        self.graph: nx.Graph = nx.Graph()
        self._name_map: dict[str, str] = {}
        self._df: Counter = Counter()
        self._avgdl = 1.0
        self._vecs: dict[str, dict[int, float]] = {}
        self._tf: dict[str, Counter] = {}
        self.reload()

    # ------------------------------------------------------------------ load
    def reload(self) -> None:
        with self._lock:
            notes: dict[str, Note] = {}
            for p in sorted(self.dir.glob("*.md")):
                try:
                    n = parse_markdown(p, p.read_text(encoding="utf-8"))
                except Exception as exc:  # malformed frontmatter must not kill the vault
                    print(f"[vault] skipping {p.name}: {exc}")
                    continue
                notes[n.id] = n
            self.notes = notes
            self._build_name_map()
            self._build_graph()
            self._build_index()

    def _build_name_map(self) -> None:
        m: dict[str, str] = {}
        for n in self.notes.values():
            m[n.id.lower()] = n.id
        for n in self.notes.values():  # titles/aliases only fill gaps
            m.setdefault(n.title.lower(), n.id)
            for alias in n.meta.get("aliases", []) or []:
                m.setdefault(str(alias).lower(), n.id)
        self._name_map = m

    def resolve_name(self, name: str) -> str | None:
        return self._name_map.get(name.strip().lower())

    def _build_graph(self) -> None:
        g = nx.Graph()
        for n in self.notes.values():
            g.add_node(n.id, type=n.type, title=n.title)
        for n in self.notes.values():
            for target in n.raw_links:
                tid = self.resolve_name(target)
                if tid and tid != n.id:
                    w = g[n.id][tid]["weight"] + 1.0 if g.has_edge(n.id, tid) else 1.0
                    g.add_edge(n.id, tid, weight=w)
        self.graph = g

    def _search_text(self, n: Note) -> list[str]:
        head = " ".join([n.title] * 2 + n.people * 2 + n.entities)
        return tokenize(head + " " + n.body + " " + str(n.meta.get("text_fragment", "")))

    def _build_index(self) -> None:
        self._tf = {}
        self._df = Counter()
        total_len = 0
        for n in self.notes.values():
            n.tokens = self._search_text(n)
            self._tf[n.id] = Counter(n.tokens)
            total_len += len(n.tokens)
            for t in set(n.tokens):
                self._df[t] += 1
        self._avgdl = (total_len / len(self.notes)) if self.notes else 1.0
        self._vecs = {}
        for n in self.notes.values():
            feats = _hash_features(n.tokens)
            self._vecs[n.id] = _hash_vec({f: (1 + math.log(c)) * self._idf_feat(f) for f, c in feats.items()})

    def _idf(self, term: str) -> float:
        n = max(len(self.notes), 1)
        df = self._df.get(term, 0)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def _idf_feat(self, feat: str) -> float:
        if "_" in feat:
            a, b = feat.split("_", 1)
            return (self._idf(a) + self._idf(b)) / 2
        return self._idf(feat)

    # ----------------------------------------------------------- note access
    def get(self, note_id: str) -> Note | None:
        return self.notes.get(note_id)

    def raw(self, note_id: str) -> str | None:
        n = self.notes.get(note_id)
        return n.path.read_text(encoding="utf-8") if n else None

    def write_raw(self, note_id: str, raw: str) -> Note:
        if not re.fullmatch(r"[\w .\-()]+", note_id):
            raise ValueError("invalid note id")
        path = (self.dir / f"{note_id}.md").resolve()
        if path.parent != self.dir.resolve():
            raise ValueError("invalid note path")
        parse_markdown(path, raw)  # validate before touching disk
        path.write_text(raw, encoding="utf-8")
        self.reload()
        return self.notes[note_id]

    def write_episode(self, note_id: str, frontmatter: dict[str, Any], body: str) -> Note:
        fm = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True, width=1000)
        return self.write_raw(note_id, f"---\n{fm}---\n\n{body.strip()}\n")

    def backlinks(self, note_id: str) -> list[str]:
        return sorted(self.graph.neighbors(note_id)) if note_id in self.graph else []

    # ---------------------------------------------------------------- graph
    def graph_payload(self, scores: dict[str, float] | None = None) -> dict[str, Any]:
        scores = scores or {}
        nodes = []
        for n in self.notes.values():
            nodes.append(
                {
                    "id": n.id,
                    "title": n.title,
                    "type": n.type,
                    "timestamp": n.timestamp.isoformat() if n.timestamp else None,
                    "degree": self.graph.degree(n.id) if n.id in self.graph else 0,
                    "score": round(scores.get(n.id, 0.0), 4),
                }
            )
        links = [{"source": u, "target": v, "weight": d.get("weight", 1.0)} for u, v, d in self.graph.edges(data=True)]
        return {"nodes": nodes, "links": links}

    # --------------------------------------------------------------- search
    def semantic_scores(self, query: str) -> dict[str, dict[str, float]]:
        """Per-episode bm25/cosine and the blended S_sem (each normalised to [0,1])."""
        q_tokens = tokenize(query)
        if not q_tokens:
            return {}
        k1, b = 1.5, 0.75
        q_tf = Counter(q_tokens)
        q_vec = _hash_vec({f: (1 + math.log(c)) * self._idf_feat(f) for f, c in _hash_features(q_tokens).items()})
        raw_bm25: dict[str, float] = {}
        raw_cos: dict[str, float] = {}
        for nid, n in self.notes.items():
            if n.type != "episode":
                continue
            tf = self._tf[nid]
            dl = len(n.tokens) or 1
            s = 0.0
            for term in q_tf:
                f = tf.get(term, 0)
                if f:
                    s += self._idf(term) * f * (k1 + 1) / (f + k1 * (1 - b + b * dl / self._avgdl))
            raw_bm25[nid] = s
            raw_cos[nid] = max(_cos(q_vec, self._vecs[nid]), 0.0)
        mb = max(raw_bm25.values(), default=0.0) or 1.0
        mc = max(raw_cos.values(), default=0.0) or 1.0
        return {
            nid: {
                "bm25": raw_bm25[nid] / mb,
                "cosine": raw_cos[nid] / mc,
                "sem": 0.6 * raw_bm25[nid] / mb + 0.4 * raw_cos[nid] / mc,
            }
            for nid in raw_bm25
        }

    @staticmethod
    def gaussian_time(ts: datetime | None, mu: datetime, sigma: timedelta) -> float:
        if ts is None:
            return 0.0
        z = (ts - mu).total_seconds() / max(sigma.total_seconds(), 1.0)
        return math.exp(-0.5 * z * z)

    def ppr(self, personalization: dict[str, float], alpha: float = 0.85, tol: float = 1e-10, max_iter: int = 200) -> dict[str, float]:
        """Personalized PageRank by power iteration on the weighted, undirected WikiLink graph.

        r_{k+1} = alpha * W^T r_k + (alpha * dangling_mass + (1 - alpha)) * p
        where W is row-normalised edge weight and p the personalization (seed) vector.
        """
        g = self.graph
        if not g.number_of_nodes() or not personalization:
            return {}
        total = sum(personalization.values()) or 1.0
        p = {n: personalization.get(n, 0.0) / total for n in g.nodes}
        out_w = {n: sum(d.get("weight", 1.0) for _, _, d in g.edges(n, data=True)) for n in g.nodes}
        r = dict(p)
        for _ in range(max_iter):
            dangling = sum(r[n] for n in g.nodes if out_w[n] == 0)
            nxt = {n: (alpha * dangling + (1 - alpha)) * p[n] for n in g.nodes}
            for u in g.nodes:
                if out_w[u] == 0 or r[u] == 0:
                    continue
                share = alpha * r[u] / out_w[u]
                for v, d in g[u].items():
                    nxt[v] += share * d.get("weight", 1.0)
            err = sum(abs(nxt[n] - r[n]) for n in g.nodes)
            r = nxt
            if err < tol:
                break
        return r

    HUB_TYPES = {"person", "course", "project", "repo", "org", "tool"}

    def mentions(self, query: str) -> list[str]:
        """Hub notes explicitly named in the query (titles / aliases, word-boundary match)."""
        q = query.lower()
        found: list[str] = []
        for n in self.notes.values():
            if n.type not in self.HUB_TYPES:
                continue
            names = [n.title] + [str(a) for a in n.meta.get("aliases", []) or []]
            for name in names:
                if len(name) >= 4 and re.search(r"(?<![\w])" + re.escape(name.lower()) + r"(?![\w])", q):
                    found.append(n.id)
                    break
        return found

    def find_anchor_event(self, phrase: str, mu: datetime | None, sigma: timedelta | None) -> tuple[Note, float] | None:
        """Best calendar event matching `phrase` ('Prof. Rostova's office hours'), weighted by the time window."""
        q = set(tokenize(phrase))
        if not q:
            return None
        best: tuple[Note, float] | None = None
        for n in self.notes.values():
            if n.type != "event" or not n.timestamp:
                continue
            words = set(tokenize(" ".join([n.title, n.body] + n.people + [str(a) for a in n.meta.get("aliases", []) or []])))
            overlap = len(q & words) / len(q)
            if overlap == 0:
                continue
            score = overlap * (self.gaussian_time(n.timestamp, mu, sigma) if mu and sigma else 1.0)
            if not best or score > best[1]:
                best = (n, score)
        return best if best and best[1] > 0.05 else None

    def baseline(self, query: str) -> dict[str, Any] | None:
        """What plain keyword/vector search (no time, no graph, no DOM) would return."""
        sem = self.semantic_scores(query)
        if not sem:
            return None
        nid, s = max(sem.items(), key=lambda kv: kv[1]["sem"])
        ranked = sorted(sem.items(), key=lambda kv: kv[1]["sem"], reverse=True)[:3]
        return {"id": nid, "title": self.notes[nid].title, "score": round(s["sem"], 4),
                "top3": [{"id": k, "title": self.notes[k].title, "score": round(v["sem"], 4)} for k, v in ranked]}

    def search(
        self,
        query: str,
        entity_weights: dict[str, float] | None = None,
        mu: datetime | None = None,
        sigma: timedelta | None = None,
        anchor_mu: datetime | None = None,
        anchor_sigma: timedelta | None = None,
        top_k: int = 5,
    ) -> dict[str, Any]:
        with self._lock:
            sem = self.semantic_scores(query)
            seeds: dict[str, float] = {}
            hub_w: dict[str, float] = {}
            for name, wgt in (entity_weights or {}).items():
                hid = self.resolve_name(name)
                if hid:
                    hub_w[hid] = max(hub_w.get(hid, 0.0), wgt)
            hub_ids = list(hub_w)
            total_hw = sum(hub_w.values()) or 1.0
            for hid, wgt in hub_w.items():
                seeds[hid] = seeds.get(hid, 0.0) + 0.5 * wgt / total_hw
            top_sem = sorted(sem.items(), key=lambda kv: kv[1]["sem"], reverse=True)[:5]
            sem_total = sum(v["sem"] for _, v in top_sem) or 1.0
            for nid, v in top_sem:
                seeds[nid] = seeds.get(nid, 0.0) + (0.5 if hub_ids else 1.0) * v["sem"] / sem_total
            ppr_raw = self.ppr(seeds)
            episode_ppr = {nid: ppr_raw.get(nid, 0.0) for nid in sem}
            mp = max(episode_ppr.values(), default=0.0) or 1.0

            anchored = anchor_mu is not None and anchor_sigma is not None
            temporal = (mu is not None and sigma is not None) or anchored
            w_sem, w_time, w_graph = (0.35, 0.35, 0.30) if temporal else (0.55, 0.0, 0.45)

            rows = []
            for nid, s in sem.items():
                n = self.notes[nid]
                if anchored:  # "right before <event>": a tight window around the calendar anchor
                    s_time = self.gaussian_time(n.timestamp, anchor_mu, anchor_sigma)
                else:
                    s_time = self.gaussian_time(n.timestamp, mu, sigma) if temporal else 0.0
                s_graph = episode_ppr[nid] / mp
                score = w_sem * s["sem"] + w_time * s_time + w_graph * s_graph
                rows.append(
                    {
                        "id": nid,
                        "title": n.title,
                        "timestamp": n.timestamp.isoformat() if n.timestamp else None,
                        "s_sem": round(s["sem"], 4),
                        "bm25": round(s["bm25"], 4),
                        "cosine": round(s["cosine"], 4),
                        "s_time": round(s_time, 4),
                        "s_graph": round(s_graph, 4),
                        "ppr_raw": episode_ppr[nid],
                        "score": round(score, 4),
                        "excerpt": self._excerpt(n, query),
                    }
                )
            rows.sort(key=lambda r: r["score"], reverse=True)
            curve = self._time_curve(mu, sigma) if (mu is not None and sigma is not None) else (
                self._time_curve(anchor_mu, timedelta(days=1)) if anchored else []
            )
            return {
                "node_scores": {
                    r["id"]: {"score": r["score"], "s_sem": r["s_sem"], "s_time": r["s_time"], "s_graph": r["s_graph"]} for r in rows
                },
                "results": rows[:top_k],
                "weights": {"sem": w_sem, "time": w_time, "graph": w_graph},
                "ppr_seeds": {k: round(v, 4) for k, v in seeds.items()},
                "hub_ids": hub_ids,
                "temporal": temporal,
                "curve": curve,
                "candidates": len(sem),
                "all_scores": {r["id"]: r["score"] for r in rows},
            }

    def _time_curve(self, mu: datetime, sigma: timedelta) -> list[dict]:
        now = datetime.now()
        return [
            {"days_ago": d, "weight": round(self.gaussian_time(now - timedelta(days=d), mu, sigma), 4)}
            for d in range(0, 31)
        ]

    def _excerpt(self, n: Note, query: str, max_words: int = 55) -> str:
        q = set(tokenize(query))
        paras = [p.strip() for p in re.split(r"\n\s*\n", n.body) if p.strip() and not p.startswith("#")]
        if not paras:
            return n.title
        best = max(paras, key=lambda p: len(q & set(tokenize(p))))
        words = WIKILINK_RE.sub(lambda m: m.group(2) or m.group(1), best).split()
        return " ".join(words[:max_words]) + (" ..." if len(words) > max_words else "")

    def corpus_tokens(self) -> int:
        """Tokens a naive 'stuff the whole vault in the prompt' approach would spend."""
        return sum(approx_tokens(n.body) + approx_tokens(n.title) for n in self.notes.values())
