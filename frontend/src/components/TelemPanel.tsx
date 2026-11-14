"use client";

import { useEffect, useState } from "react";
import { ArrowRight, BellRing, CheckCircle2, ChevronDown, ChevronUp, CircleDashed, ExternalLink, Loader2, Lock, Radar, Send, ShieldCheck, X, Zap } from "lucide-react";
import type { RecallState } from "@/lib/useRecall";
import type { TelemRun } from "@/lib/types";
import CountUp from "./reactbits/CountUp";
import ShinyText from "./reactbits/ShinyText";
import SpotlightCard from "./reactbits/SpotlightCard";
import StarBorder from "./reactbits/StarBorder";

const COLLAPSE_KEY = "referent.telemCollapsed";
const host = (u: string) => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch { return u; } };
const day = (iso?: string | null) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "");

function Stage({ n, label, state }: { n: number; label: string; state: "wait" | "run" | "ok" | "warn" }) {
  const icon = state === "run" ? <Loader2 size={12} className="animate-spin" /> : state === "ok" ? <CheckCircle2 size={12} /> : state === "warn" ? <CircleDashed size={12} /> : <span className="text-[10px]">{n}</span>;
  const tone = state === "ok" ? "bg-emerald-500 text-white" : state === "run" ? "bg-sky-500 text-white" : state === "warn" ? "bg-orange-100 text-orange-700" : "bg-sky-900/10 text-sky-900/60";
  return <span className="flex items-center gap-1.5 text-[11px] font-medium text-sky-900/80"><span className={`grid h-5 w-5 place-items-center rounded-full ${tone}`}>{icon}</span>{label}</span>;
}

const VERDICT_TONE: Record<string, string> = {
  edit_supported: "bg-emerald-500 text-white",
  partially_supported: "bg-amber-400 text-amber-950",
  unverified: "bg-orange-100 text-orange-800",
  context_only: "bg-sky-100 text-sky-900",
};
const VERDICT_LABEL: Record<string, string> = {
  edit_supported: "Live edit grounded",
  partially_supported: "Partly grounded",
  unverified: "Unverified",
  context_only: "Context sources",
};

/** Telem AI pipeline, always visible in the main view after a recall: compile -> search -> fetch -> verdict -> monitor. */
export default function TelemPanel({ s }: { s: RecallState }) {
  const t: TelemRun | null = s.telem;
  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => { try { setCollapsed(localStorage.getItem(COLLAPSE_KEY) === "1"); } catch { /* storage unavailable */ } }, []);
  const toggle = () => setCollapsed((c) => { try { localStorage.setItem(COLLAPSE_KEY, c ? "0" : "1"); } catch { /* ignore */ } return !c; });
  if (!t) return null;

  const searchState = !t.search ? "run" : t.search.ok ? "ok" : "warn";
  const fetchState = t.stage === "search" ? "wait" : !t.fetch ? "run" : t.fetch.ok ? "ok" : "warn";
  const monState = t.monitor ? "ok" : "wait";
  const v = t.verdict;
  const results = t.search?.results ?? [];
  const sinceCount = s.enrichment?.results.length ?? 0;
  const providers = (t.search?.providers ?? []).filter((p) => p.ok).map((p) => p.name);

  return <section aria-label="Telem AI grounding" className="shrink-0 border-t border-sky-100 bg-gradient-to-r from-white/95 via-sky-50/95 to-orange-50/80 text-sky-950 backdrop-blur-xl">
    {/* header strip */}
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2">
      <span className="flex items-center gap-1.5 rounded-full bg-gradient-to-r from-orange-500 to-orange-400 px-2.5 py-1 text-[11px] font-bold text-white shadow-[0_3px_12px_-3px_rgba(252,115,77,.8)]"><Zap size={12} fill="currentColor" /><ShinyText text="Powered by Telem AI Router" color="#ffffff" shineColor="#fff3c4" speed={2.4} /></span>
      <span className="text-[11px] text-sky-900/60">Search + Fetch + Monitors · {t.host}</span>
      <div className="flex items-center gap-3">
        <Stage n={1} label="Search" state={searchState} />
        <ArrowRight size={12} className="text-sky-900/30" />
        <Stage n={2} label="Fetch + verify" state={fetchState} />
        <ArrowRight size={12} className="text-sky-900/30" />
        <Stage n={3} label="Monitor" state={monState} />
      </div>
      {collapsed && v && <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${VERDICT_TONE[v.status]}`}>{VERDICT_LABEL[v.status]}</span>}
      {t.ms !== undefined && <span className="font-mono text-[11px] text-sky-900/55"><CountUp key={t.rid} to={t.ms / 1000} decimals={1} duration={0.9} trigger="load" /> s end-to-end</span>}
      {t.fallback && <span className="rounded-full bg-orange-100 px-2 py-0.5 text-[10px] font-semibold text-orange-700">Telem unreachable · cached references</span>}
      <div className="ml-auto flex items-center gap-1">
        <button onClick={toggle} aria-expanded={!collapsed} aria-label={collapsed ? "Expand Telem panel" : "Collapse Telem panel"} className="rounded-lg p-1 text-sky-900/60 hover:bg-white">{collapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}</button>
        <button onClick={() => s.setTelem(null)} aria-label="Dismiss Telem panel" className="rounded-lg p-1 text-sky-900/60 hover:bg-white"><X size={15} /></button>
      </div>
    </div>

    {!collapsed && <div className="grid max-h-[28vh] grid-cols-1 gap-3 overflow-y-auto px-4 pb-3 lg:grid-cols-[1.05fr_1.5fr_1fr]">
      {/* 1. query compiler */}
      <SpotlightCard theme="light" spotlightColor="rgba(2, 151, 222, 0.18)" className="!rounded-2xl !bg-white/85 !p-3">
        <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-sky-800/60">1 · Episodic query compiler</div>
        <p className="text-[12px] leading-snug text-sky-900/70">“{t.query.raw}”</p>
        <p className="mt-0.5 text-[10.5px] text-orange-600">Unsearchable on the open web: no topic, only people and time.</p>
        <div className="mt-2 flex flex-wrap gap-1">
          {t.query.entities.map((e, i) => <span key={i} title={e.sent ? "Sent to Telem" : "Resolved by the vault graph; stays on this device"}
            className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-[10.5px] ${e.sent ? "bg-sky-100 text-sky-900" : "bg-slate-100 text-slate-500"}`}>
            {e.sent ? <Send size={9} /> : <Lock size={9} />}{e.value}</span>)}
        </div>
        <div className="mt-2 rounded-xl bg-sky-950 px-2.5 py-2 font-mono text-[11px] leading-snug text-sky-100">
          <span className="text-orange-300">POST</span> /v1/search<br />{t.query.compiled}
        </div>
        <p className="mt-1.5 flex items-center gap-1 text-[10.5px] text-emerald-700"><ShieldCheck size={11} />Names, course codes and private text never leave the device</p>
      </SpotlightCard>

      {/* 2. grounded verdict */}
      <SpotlightCard theme="light" spotlightColor="rgba(2, 151, 222, 0.18)" className="!rounded-2xl !bg-white/85 !p-3">
        <div className="mb-1.5 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-widest text-sky-800/60">
          2 · Grounded drift verification
          {t.search && <span className="ml-auto font-mono normal-case tracking-normal text-sky-900/50">search {t.search.ms} ms · fetch {t.fetch?.ms ?? "…"} ms{t.passages_scanned ? <> · <CountUp key={t.rid} to={t.passages_scanned} duration={1} trigger="load" /> passages</> : null}</span>}
        </div>
        {!v && <p className="flex items-center gap-2 py-3 text-[12px] text-sky-900/70"><Loader2 size={14} className="animate-spin text-sky-500" />{t.stage === "search" ? "Routing the compiled query across Telem providers…" : "Fetching clean text from the top-ranked sources…"}</p>}
        {v && <>
          <div className="flex items-start gap-2">
            <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${VERDICT_TONE[v.status]}`}>{VERDICT_LABEL[v.status]}</span>
            <p className="text-[12.5px] font-medium leading-snug">{v.headline}</p>
          </div>
          {v.checks.length > 0 && <div className="mt-1.5 flex flex-wrap gap-1.5">{v.checks.map((c) => <span key={c.label} className={`rounded-md px-1.5 py-0.5 font-mono text-[10.5px] ${c.supported ? "bg-emerald-50 text-emerald-700" : "bg-orange-50 text-orange-700"}`}>{c.supported ? "✓" : "?"} {c.label} {c.edit}</span>)}</div>}
          <ol className="mt-2 space-y-1.5">
            {v.citations.map((c, i) => <li key={c.id} className="rounded-xl bg-sky-50/80 p-2">
              <a href={c.url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-[11px] font-semibold text-sky-700 hover:text-orange-600">[{i + 1}] {c.title || host(c.url)} <ExternalLink size={10} /></a>
              <p className="mt-0.5 line-clamp-2 text-[11.5px] leading-snug text-sky-950/80">{c.cached ? c.text : `“${c.text}”`}</p>
              <p className="mt-0.5 text-[10px] text-sky-900/50">{host(c.url)}{(() => { const r = results.find((x) => x.url === c.url); return r ? ` · Telem rank score ${r.score.toFixed(2)} · ${r.providers.join(" + ")}` : c.cached ? " · cached reference (offline)" : ""; })()}</p>
            </li>)}
          </ol>
        </>}
        {t.search && !t.search.ok && <p className="mt-1 text-[11px] text-orange-700">Telem search: {t.search.status}{t.search.error ? ` · ${t.search.error}` : ""}</p>}
      </SpotlightCard>

      {/* 3. monitor */}
      <SpotlightCard theme="light" spotlightColor="rgba(252, 115, 77, 0.2)" className="flex flex-col !rounded-2xl !bg-white/85 !p-3">
        <div className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-sky-800/60">3 · Continuous claim watch</div>
        {t.monitor ? <div className="rounded-xl bg-emerald-50 p-2.5">
          <p className="flex items-center gap-1.5 text-[12px] font-semibold text-emerald-800"><Radar size={14} className="animate-pulse" />Telem Monitor {t.monitor.id.slice(0, 8)} · {t.monitor.status}</p>
          <p className="mt-1 line-clamp-3 text-[11px] leading-snug text-emerald-900/80">Watching: {t.monitor.query}</p>
          <p className="mt-1 text-[10.5px] text-emerald-900/60">{t.monitor.frequency ? `Every ${t.monitor.frequency}` : "Daily"}{t.monitor.created_at ? ` · since ${day(t.monitor.created_at)}` : ""}{t.monitor.expires_at ? ` · until ${day(t.monitor.expires_at)}` : ""}</p>
        </div> : <StarBorder as="button" theme="light" color="#fc734d" duration={4} radius={14} backgroundColor="#fc734d" textColor="#ffffff"
          disabled={s.arming || !t.configured} onClick={() => s.armMonitor(t.note_id)}
          className="flex w-full items-center justify-center gap-2 text-[12.5px] font-semibold disabled:opacity-50">
          {s.arming ? <Loader2 size={14} className="animate-spin" /> : <BellRing size={14} />}{t.configured ? "Arm Telem Monitor on this assumption" : "Add TELEM_API_KEY to arm monitors"}
        </StarBorder>}
        {providers.length > 0 && <p className="mt-2 text-[11px] text-sky-900/65">Routed across {providers.join(", ")} · {t.search?.raw_hits ?? 0} hits fused to {results.length}{t.search?.queries === 2 ? " (compiled + claim query, one batched call)" : ""}</p>}
        {sinceCount > 0 && <p className="mt-1 text-[11px] text-sky-900/65">{sinceCount} new sources published since your snapshot{t.since ? ` (${day(t.since)})` : ""}</p>}
      </SpotlightCard>
    </div>}
  </section>;
}
