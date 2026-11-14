"use client";

import { Activity, Gauge, Layers, Network, Timer } from "lucide-react";
import CountUp from "@/components/reactbits/CountUp";
import type { RecallState } from "@/lib/useRecall";

function Tile({ icon: Icon, label, value, decimals = 0, suffix = "", sub, tone = "text-slate-100" }: { icon: typeof Gauge; label: string; value: number | null; decimals?: number; suffix?: string; sub?: string; tone?: string }) {
  return (
    <div className="rounded-xl border border-cyan-500/15 bg-ink-950/50 p-2">
      <div className="eyebrow flex items-center gap-1"><Icon size={10} /> {label}</div>
      <div className={`mt-0.5 font-serif text-[22px] leading-tight ${tone}`}>
        {value === null ? "-" : <CountUp to={value} decimals={decimals} suffix={suffix} duration={1.1} trigger="load" />}
      </div>
      {sub && <div className="truncate text-[10px] text-slate-500">{sub}</div>}
    </div>
  );
}

function DecayCurve({ t }: { t: NonNullable<RecallState["telemetry"]> }) {
  const W = 300, H = 92, P = 6;
  const maxD = 30;
  const x = (d: number) => P + ((maxD - d) / maxD) * (W - 2 * P); // older on the left, today on the right
  const y = (v: number) => H - 16 - v * (H - 28);
  const pts = t.curve.map((p) => `${x(p.days_ago)},${y(p.weight)}`).join(" ");
  const area = `${x(maxD)},${y(0)} ${pts} ${x(0)},${y(0)}`;
  const muDays = t.temporal ? (Date.now() - new Date(t.temporal.mu).getTime()) / 86400000 : null;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
      <defs>
        <linearGradient id="decay" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#FC734D" stopOpacity="0.5" />
          <stop offset="100%" stopColor="#0297DE" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0, 7, 14, 21, 28].map((d) => (
        <g key={d}>
          <line x1={x(d)} x2={x(d)} y1={6} y2={y(0)} stroke="#1f2432" strokeDasharray="2 3" />
          <text x={x(d)} y={H - 4} fontSize="8" fill="#64748b" textAnchor="middle">{d === 0 ? "now" : `-${d}d`}</text>
        </g>
      ))}
      {t.curve.length > 0 && (
        <>
          <polygon points={area} fill="url(#decay)" />
          <polyline points={pts} fill="none" stroke="#FC734D" strokeWidth="1.6" />
        </>
      )}
      {muDays !== null && <line x1={x(muDays)} x2={x(muDays)} y1={8} y2={y(0)} stroke="#fd9d82" strokeWidth="1" />}
      {t.markers.map((m, i) => (
        <g key={m.id}>
          <circle cx={x(Math.min(m.days_ago, maxD))} cy={y(m.s_time)} r={i === 0 ? 4 : 2.6} fill={i === 0 ? "#2fb4f5" : "#8aa3b8"} stroke="#02070A" strokeWidth="1" />
          {i === 0 && <text x={x(Math.min(m.days_ago, maxD))} y={y(m.s_time) - 7} fontSize="8" fill="#b5e3fa" textAnchor="middle">top</text>}
        </g>
      ))}
      {t.curve.length === 0 && <text x={W / 2} y={H / 2} fontSize="9" fill="#64748b" textAnchor="middle">no time expression in query - S_time disabled</text>}
    </svg>
  );
}

export default function TelemetryHUD({ s, compact = false }: { s: RecallState; compact?: boolean }) {
  const t = s.telemetry;
  const segs = t
    ? [
        { k: "DOM", v: t.dom_ms, c: "#38bdf8" },
        { k: "resolve", v: t.resolve_ms, c: "#a78bfa" },
        { k: "retrieve", v: t.retrieval_ms, c: "#22d3ee" },
        { k: "replay", v: t.replay_ms, c: "#34d399" },
        { k: "web", v: t.enrich_ms, c: "#f472b6" },
      ]
    : [];
  const total = segs.reduce((a, b) => a + b.v, 0) || 1;

  return (
    <section className="panel shrink-0 p-3">
      <div className="mb-2 flex items-center gap-1.5 text-xs">
        <Activity size={13} className="text-cyan-300" />
        <span className="font-semibold text-slate-200">Telemetry</span>
        <span className="ml-auto text-[10px] text-slate-500">{t ? `run ${t.rid}` : "waiting for first recall"}</span>
      </div>
      <div className={compact ? "hidden" : "grid grid-cols-2 gap-1.5 2xl:grid-cols-4"}>
        <Tile icon={Timer} label="Retrieval" value={t ? t.retrieval_ms : null} decimals={1} suffix="ms" sub={t ? `${t.candidates} episodes scored` : "vault search"} tone="text-cyan-300" />
        <Tile icon={Layers} label="Compression" value={t ? t.compression * 100 : null} decimals={1} suffix="%" sub={t ? `${t.tokens_context} / ${t.tokens_naive} tok (est.)` : "context vs full vault"} tone="text-emerald-300" />
        <Tile icon={Network} label="PPR score" value={t ? t.ppr_top : null} decimals={4} sub={t ? `S_graph ${t.s_graph_top.toFixed(2)}` : "top episode"} tone="text-violet-300" />
        <Tile icon={Gauge} label="End-to-end" value={t ? t.total_ms / 1000 : null} decimals={2} suffix="s" sub={t ? `score ${t.score_top.toFixed(3)}` : "incl. agent replay"} tone="text-amber-300" />
      </div>
      {t && (
        <>
          <div className="mt-2 flex h-2 overflow-hidden rounded-full bg-ink-700">
            {segs.map((g) => <div key={g.k} style={{ width: `${(g.v / total) * 100}%`, background: g.c }} title={`${g.k}: ${Math.round(g.v)}ms`} />)}
          </div>
          <div className="mt-1 flex flex-wrap gap-x-2.5 text-[9.5px] text-slate-500">
            {segs.map((g) => (
              <span key={g.k} className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full" style={{ background: g.c }} />{g.k} {Math.round(g.v)}ms</span>
            ))}
          </div>
          <div className="mt-2 rounded-lg border border-ink-700 bg-ink-950 px-2 pt-1.5">
            <div className="flex text-[10px] text-slate-500">
              <span>Gaussian temporal decay S_time</span>
              {t.temporal && <span className="ml-auto font-mono text-amber-300/80">mu = {t.temporal.label}, sigma = {t.temporal.sigma_days}d</span>}
            </div>
            <DecayCurve t={t} />
          </div>
        </>
      )}
    </section>
  );
}
