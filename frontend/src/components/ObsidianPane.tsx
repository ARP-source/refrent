"use client";

import { Clock3, Edit3, Eye, Play, Save, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type ComponentType } from "react";
import ReactMarkdown from "react-markdown";
import type { RecallState } from "@/lib/useRecall";
import { API, type GraphNode, type NoteDetail } from "@/lib/types";

// palette: midnight / electric blue / cantaloupe, with soft tints in between
const TYPE_COLOR: Record<string, string> = {
  episode: "#a9dcff",
  person: "#FC734D",
  course: "#0297DE",
  event: "#ffc9b5",
  project: "#5fc4f2",
  repo: "#c5d4e3",
  tool: "#c5d4e3",
  org: "#fd9d82",
};
const BLUE = "#4cc0f7";
const ORANGE = "#FC734D";
const QUERY_ID = "__query__";
const CURVE = 0.16;
const WIKI_RE = /\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]/g;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type FG = ComponentType<any>;
type GNode = GraphNode & { virtual?: boolean };
type GLink = { source: string | GNode; target: string | GNode; weight: number; virtual?: boolean };

const idOf = (v: string | GNode) => (typeof v === "string" ? v : v.id);
const hash = (s: string) => {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return ((h >>> 0) % 1000) / 1000;
};
const rgba = (hex: string, a: number) => {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${Math.max(0, Math.min(1, a))})`;
};

function useSize<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [size, setSize] = useState({ w: 300, h: 300 });
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setSize({ w: e.contentRect.width, h: e.contentRect.height }));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, size] as const;
}

function when(ts: string | null) {
  if (!ts) return "";
  const d = new Date(ts);
  const days = Math.round((Date.now() - d.getTime()) / 86400000);
  return `${d.toLocaleDateString(undefined, { month: "short", day: "numeric" })} - ${days <= 0 ? "today" : days === 1 ? "yesterday" : `${days} days ago`}`;
}

export default function ObsidianPane({ s }: { s: RecallState }) {
  const [Graph, setGraph] = useState<FG | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fgRef = useRef<any>(null);
  const [wrapRef, size] = useSize<HTMLDivElement>();
  const [note, setNote] = useState<NoteDetail | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const nodeCache = useRef(new Map<string, GNode>());
  const fitted = useRef(false);

  useEffect(() => {
    import("react-force-graph-2d").then((m) => setGraph(() => m.default as unknown as FG));
  }, []);

  const active = !!s.topId || s.ambiguousIds.length > 0;
  const winners = useMemo(() => (s.topId ? [s.topId] : s.ambiguousIds), [s.topId, s.ambiguousIds]);
  const pathHubs = useMemo(() => new Set(s.path), [s.path]);
  const onPath = useMemo(() => new Set<string>([QUERY_ID, ...s.path, ...winners]), [s.path, winners]);

  // stable node objects (positions survive rebuilds) + a virtual Query node wired into the context hubs
  const data = useMemo(() => {
    const cache = nodeCache.current;
    const nodes: GNode[] = s.graph.nodes.map((n) => {
      const prev = cache.get(n.id);
      const node = prev ? Object.assign(prev, { ...n, x: prev.x, y: prev.y }) : { ...n };
      cache.set(n.id, node);
      return node;
    });
    const links: GLink[] = s.graph.links.map((l) => ({ source: idOf(l.source as string | GNode), target: idOf(l.target as string | GNode), weight: l.weight }));
    if (s.queryLabel && (s.path.length || winners.length)) {
      const anchors = (s.path.length ? s.path : winners).map((id) => cache.get(id)).filter(Boolean) as GNode[];
      const cx = anchors.reduce((a, n) => a + (n.x ?? 0), 0) / Math.max(anchors.length, 1);
      const cy = anchors.reduce((a, n) => a + (n.y ?? 0), 0) / Math.max(anchors.length, 1);
      const q: GNode = cache.get(QUERY_ID) ?? { id: QUERY_ID, title: "", type: "query", timestamp: null, degree: 0, score: 1, virtual: true, x: cx - 50, y: cy - 50 };
      q.title = s.queryLabel.length > 40 ? s.queryLabel.slice(0, 38) + "..." : s.queryLabel;
      cache.set(QUERY_ID, q);
      nodes.push(q);
      for (const t of s.path.length ? s.path : winners) links.push({ source: QUERY_ID, target: t, weight: 1, virtual: true });
    } else {
      cache.delete(QUERY_ID);
    }
    return { nodes, links };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s.graphVersion, s.queryLabel, s.path, winners]);

  const byName = useMemo(() => {
    const m = new Map<string, string>();
    for (const n of s.graph.nodes) {
      m.set(n.id.toLowerCase(), n.id);
      m.set(n.title.toLowerCase(), n.id);
    }
    return m;
  }, [s.graph.nodes]);

  const openNote = useCallback(async (id: string) => {
    if (id === QUERY_ID) return;
    const r = await fetch(`${API}/api/notes/${encodeURIComponent(id)}`);
    if (!r.ok) return;
    const n = (await r.json()) as NoteDetail;
    setNote(n);
    setDraft(n.raw ?? "");
    setEditing(false);
    setSaveErr(null);
  }, []);

  useEffect(() => {
    if (s.focusNote) openNote(s.focusNote);
  }, [s.focusNote, openNote, s.graphVersion]);

  // airy layout
  useEffect(() => {
    const fg = fgRef.current;
    if (!fg || !Graph) return;
    fg.d3Force("charge")?.strength(-80);
    fg.d3Force("link")?.distance((l: GLink) => (l.virtual ? 70 : 38));
    // gentle gravity so disconnected clusters (e.g. STAT 310 vs CS229) stay in frame instead of drifting away
    let simNodes: GNode[] = [];
    const gravity = Object.assign(
      (alpha: number) => {
        for (const n of simNodes as (GNode & { vx?: number; vy?: number })[]) {
          n.vx = (n.vx ?? 0) - (n.x ?? 0) * 0.06 * alpha;
          n.vy = (n.vy ?? 0) - (n.y ?? 0) * 0.06 * alpha;
        }
      },
      { initialize: (ns: GNode[]) => { simNodes = ns; } },
    );
    fg.d3Force("gravity", gravity);
    fg.d3ReheatSimulation?.();
  }, [Graph, data]);

  // camera: whole vault on first load, the winning path after a recall
  const fitPending = useRef(false);
  const fit = useCallback(() => {
    const fg = fgRef.current;
    if (!fg) return;
    const keep = winners.length ? new Set<string>([QUERY_ID, ...s.path, ...winners]) : null;
    const pts = [...nodeCache.current.values()].filter((n) => (!keep || keep.has(n.id)) && Number.isFinite(n.x) && Number.isFinite(n.y));
    if (!pts.length) return;
    const xs = pts.map((n) => n.x!), ys = pts.map((n) => n.y!);
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const pad = keep ? 140 : 60;
    const k = Math.max(0.6, Math.min(keep ? 3.2 : 2.2, Math.min(size.w / (x1 - x0 + pad), size.h / (y1 - y0 + pad))));
    fg.centerAt((x0 + x1) / 2, (y0 + y1) / 2, 900);
    fg.zoom(k, 900);
  }, [s.path, winners, size.w, size.h]);
  // re-frame when the card changes size (e.g. note viewer opens/closes)
  useEffect(() => {
    if (!fitted.current) return;
    const t = setTimeout(fit, 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [size.w, size.h]);
  useEffect(() => {
    if (winners.length === 0) return;
    fitPending.current = true;
    const t = setTimeout(() => fitPending.current && fit(), 2500);
    return () => clearTimeout(t);
  }, [winners, fit]);

  const linkState = useCallback(
    (l: GLink): "path" | "tie" | "dim" | "idle" => {
      if (!active) return "idle";
      const a = idOf(l.source), b = idOf(l.target);
      const onWin = l.virtual || (pathHubs.has(a) && winners.includes(b)) || (pathHubs.has(b) && winners.includes(a));
      if (onWin) return s.topId ? "path" : "tie";
      return "dim";
    },
    [active, pathHubs, winners, s.topId],
  );

  // curved, colour-blended links (same curve force-graph uses for its particles)
  const drawLink = useCallback(
    (l: GLink, ctx: CanvasRenderingContext2D, scale: number) => {
      const a = l.source as GNode, b = l.target as GNode;
      if (!Number.isFinite(a.x) || !Number.isFinite(b.x)) return;
      const st = linkState(l);
      const dx = b.x! - a.x!, dy = b.y! - a.y!;
      const len = Math.hypot(dx, dy) || 1;
      const ang = Math.atan2(dy, dx);
      const cx = (a.x! + b.x!) / 2 + len * CURVE * Math.cos(ang - Math.PI / 2);
      const cy = (a.y! + b.y!) / 2 + len * CURVE * Math.sin(ang - Math.PI / 2);
      const ca = st === "path" ? BLUE : st === "tie" ? ORANGE : TYPE_COLOR[a.type] ?? "#a9dcff";
      const cb = st === "path" ? "#ffffff" : st === "tie" ? "#ffd9cc" : TYPE_COLOR[b.type] ?? "#a9dcff";
      const alpha = st === "path" || st === "tie" ? 0.95 : st === "dim" ? 0.035 : 0.2;
      const g = ctx.createLinearGradient(a.x!, a.y!, b.x!, b.y!);
      g.addColorStop(0, rgba(ca, alpha));
      g.addColorStop(1, rgba(cb, alpha * 0.8));
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      ctx.strokeStyle = g;
      ctx.lineWidth = (st === "path" || st === "tie" ? 1.8 : 0.7) / Math.sqrt(scale);
      if (l.virtual) ctx.setLineDash([3 / scale, 3 / scale]);
      if (st === "path" || st === "tie") {
        ctx.shadowColor = st === "path" ? BLUE : ORANGE;
        ctx.shadowBlur = 12;
      }
      ctx.beginPath();
      ctx.moveTo(a.x!, a.y!);
      ctx.quadraticCurveTo(cx, cy, b.x!, b.y!);
      ctx.stroke();
      ctx.restore();
    },
    [linkState],
  );

  // glowing orbs: additive halo + bright core, gentle twinkle, distractors fade away
  const drawNode = useCallback(
    (node: GNode, ctx: CanvasRenderingContext2D, scale: number) => {
      // the very first frame after (re)mounting can run before the simulation has placed a node
      if (!Number.isFinite(node.x) || !Number.isFinite(node.y) || !Number.isFinite(scale)) return;
      const t = performance.now() / 1000;
      const ns = s.nodeScores[node.id];
      const isQuery = node.id === QUERY_ID;
      const isTop = node.id === s.topId;
      const isTie = s.ambiguousIds.includes(node.id);
      const inPath = onPath.has(node.id);
      const hub = node.type !== "episode" && !isQuery;
      let color = TYPE_COLOR[node.type] ?? "#a9dcff";
      if (isTop || isQuery || pathHubs.has(node.id)) color = BLUE;
      if (isTie) color = ORANGE;

      let r = hub ? 3.4 + Math.min(node.degree, 14) * 0.32 : 1.9;
      if (active && ns) r = 1.6 + (ns.s_graph + ns.s_time) * 3.4;
      if (isTop || isTie) r += 2.2;
      if (isQuery) r = 4.2;
      r *= 1 + 0.07 * Math.sin(t * 1.4 + hash(node.id) * 6.28);
      if (!Number.isFinite(r) || r <= 0) r = 2;

      const dim = active && !inPath && !isTie;
      const a = dim ? 0.13 : 1;
      const x = node.x!, y = node.y!;

      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      const haloR = r * (isTop || isTie || isQuery ? 6 : hub ? 4.2 : 3.4);
      const halo = ctx.createRadialGradient(x, y, 0, x, y, haloR);
      halo.addColorStop(0, rgba(color, (isTop || isTie ? 0.55 : hub ? 0.32 : 0.22) * a));
      halo.addColorStop(0.35, rgba(color, (isTop || isTie ? 0.2 : 0.09) * a));
      halo.addColorStop(1, rgba(color, 0));
      ctx.fillStyle = halo;
      ctx.beginPath();
      ctx.arc(x, y, haloR, 0, Math.PI * 2);
      ctx.fill();

      const core = ctx.createRadialGradient(x - r * 0.3, y - r * 0.3, 0, x, y, r);
      core.addColorStop(0, rgba("#ffffff", 0.95 * a));
      core.addColorStop(0.45, rgba(color, 0.95 * a));
      core.addColorStop(1, rgba(color, 0.35 * a));
      ctx.fillStyle = core;
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();

      if (isQuery) {
        // four-point sparkle for the query
        ctx.strokeStyle = rgba("#ffffff", 0.8);
        ctx.lineWidth = 0.8 / scale;
        const L = r * 3.2;
        ctx.beginPath();
        ctx.moveTo(x - L, y); ctx.lineTo(x + L, y);
        ctx.moveTo(x, y - L); ctx.lineTo(x, y + L);
        ctx.stroke();
      }
      ctx.restore();

      const busyHub = hub && node.type !== "event" && node.degree >= 6;
      const showLabel = isQuery || isTop || isTie || hover === node.id || note?.id === node.id || (busyHub && !active) || (inPath && hub);
      if (showLabel) {
        const label = node.title.length > 42 ? node.title.slice(0, 40) + "..." : node.title;
        const fs = Math.max((isTop || isTie || isQuery ? 12 : 10.5) / scale, 1.6);
        ctx.font = `${isTop || isTie || isQuery ? 600 : 500} ${fs}px Inter, ui-sans-serif, system-ui`;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        ctx.shadowColor = "rgba(2,7,10,.95)";
        ctx.shadowBlur = 6;
        ctx.fillStyle = isTie ? "#ffd9cc" : isTop || isQuery ? "#e6f6ff" : rgba("#dbe9f5", hub ? 0.72 : 0.9);
        ctx.fillText(label, x, y + r + 2.5 / scale);
        ctx.shadowBlur = 0;
      }
    },
    [s.nodeScores, s.topId, s.ambiguousIds, pathHubs, onPath, active, hover, note?.id],
  );

  const save = async () => {
    if (!note) return;
    const r = await fetch(`${API}/api/notes/${encodeURIComponent(note.id)}`, {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ raw: draft }),
    });
    if (!r.ok) {
      setSaveErr((await r.json().catch(() => ({}))).detail ?? "save failed");
      return;
    }
    const n = (await r.json()) as NoteDetail;
    setNote(n);
    setEditing(false);
    setSaveErr(null);
  };

  const md = useMemo(
    () =>
      (note?.body ?? "")
        .replace(/^#\s.*$/m, "") // title is already shown above
        .replace(WIKI_RE, (_m, target: string, alias?: string) => `[${alias ?? target}](wikilink:${encodeURIComponent(target.trim())})`),
    [note?.body],
  );

  return (
    <section className="panel flex h-full min-h-0 flex-col overflow-hidden">
      <div className="px-5 pt-4 font-serif text-[22px] leading-none text-white/90">Vault</div>

      <div ref={wrapRef} className={`relative min-h-[200px] ${note ? "h-[58%]" : "flex-1"}`}>
        {Graph && (
          <Graph
            ref={fgRef}
            graphData={data}
            width={size.w}
            height={size.h}
            backgroundColor="rgba(0,0,0,0)"
            nodeId="id"
            nodeCanvasObject={drawNode}
            nodePointerAreaPaint={(node: GNode, color: string, ctx: CanvasRenderingContext2D) => {
              ctx.fillStyle = color;
              ctx.beginPath();
              ctx.arc(node.x!, node.y!, 7, 0, 2 * Math.PI);
              ctx.fill();
            }}
            linkCanvasObjectMode={() => "replace"}
            linkCanvasObject={drawLink}
            linkCurvature={CURVE}
            linkDirectionalParticles={(l: GLink) => (["path", "tie"].includes(linkState(l)) ? 3 : 0)}
            linkDirectionalParticleColor={(l: GLink) => (linkState(l) === "tie" ? "#ffd9cc" : "#ffffff")}
            linkDirectionalParticleWidth={2.4}
            linkDirectionalParticleSpeed={0.011}
            onNodeClick={(n: GNode) => openNote(n.id)}
            onNodeHover={(n: GNode | null) => setHover(n?.id ?? null)}
            onBackgroundClick={() => setNote(null)}
            autoPauseRedraw={false}
            onEngineStop={() => {
              if (!fitted.current) {
                fitted.current = true;
                fit();
              } else if (fitPending.current) {
                fitPending.current = false;
                fit();
              }
            }}
            cooldownTicks={160}
            d3VelocityDecay={0.3}
          />
        )}
      </div>

      {note && (
        <div className="flex min-h-0 flex-1 flex-col bg-black/20">
          <div className="flex items-start gap-2 px-5 pt-3.5">
            <div className="min-w-0 flex-1">
              <div className="line-clamp-2 text-[15px] font-medium leading-snug text-white">{note.title}</div>
              {note.timestamp && <div className="mt-1 flex items-center gap-1.5 text-[12px] text-slate-400"><Clock3 size={12} /> {when(note.timestamp)}</div>}
            </div>
            {note.actions?.length > 0 && (
              <button title="Take me there" onClick={() => s.replayNote(note.id)} className="rounded-full p-2 text-cyan-200 transition hover:bg-cyan-400/15"><Play size={15} /></button>
            )}
            {editing ? (
              <>
                <button title="Save" onClick={save} className="rounded-full p-2 text-emerald-300 transition hover:bg-emerald-400/15"><Save size={15} /></button>
                <button title="Cancel" onClick={() => { setEditing(false); setDraft(note.raw ?? ""); }} className="rounded-full p-2 text-slate-400 transition hover:bg-white/5"><Eye size={15} /></button>
              </>
            ) : (
              <button title="Edit note" onClick={() => setEditing(true)} className="rounded-full p-2 text-slate-300 transition hover:bg-white/5"><Edit3 size={15} /></button>
            )}
            <button title="Close" onClick={() => setNote(null)} className="rounded-full p-2 text-slate-500 transition hover:bg-white/5"><X size={15} /></button>
          </div>
          {saveErr && <div className="mx-5 mt-2 rounded-lg bg-rose-500/10 px-2 py-1 text-xs text-rose-300">{saveErr}</div>}

          {editing ? (
            <textarea
              className="m-4 flex-1 resize-none rounded-2xl bg-black/30 p-3 font-mono text-[11.5px] leading-relaxed text-slate-200 outline-none"
              value={draft}
              spellCheck={false}
              onChange={(e) => setDraft(e.target.value)}
            />
          ) : (
            <div className="md min-h-0 flex-1 overflow-y-auto px-5 pb-4 pt-1 text-[13px] text-slate-300">
              <ReactMarkdown
                urlTransform={(u) => u}
                components={{
                  a: ({ href, children }) => {
                    if (href?.startsWith("wikilink:")) {
                      const target = decodeURIComponent(href.slice(9));
                      const id = byName.get(target.toLowerCase());
                      return (
                        <button onClick={() => id && openNote(id)} className={id ? "text-cyan-200 underline decoration-cyan-400/30 underline-offset-2 hover:text-white" : "text-slate-400"}>
                          {children}
                        </button>
                      );
                    }
                    return <a href={href} target="_blank" rel="noreferrer" className="text-cyan-300 underline">{children}</a>;
                  },
                }}
              >
                {md}
              </ReactMarkdown>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
