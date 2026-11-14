"use client";
import type { RecallState } from "@/lib/useRecall";
import TelemetryHUD from "./TelemetryHUD";

export default function SearchIntelligence({ s }: { s: RecallState }) {
  const result = s.result;
  if (!result) return null;
  const top = result.search.results.find((r) => r.id === result.episode?.id) || result.search.results[0];
  const baseline = result.baseline;
  const same = baseline?.id === top?.id;
  return <div className="space-y-3">
    <section className="rounded-xl border border-white/10 bg-black/20 p-4">
      <h3 className="mb-3 text-sm font-semibold text-white">Search intelligence</h3>
      <div className={`rounded-lg border p-3 ${same ? "border-slate-500/30 bg-slate-500/5" : "border-rose-300/20 bg-rose-300/5"}`}>
        <div className="text-[11px] uppercase tracking-wide text-slate-400">Keyword / semantic baseline</div>
        <p className="mt-1 text-sm text-white">{baseline?.title || "No baseline candidate"}</p>
        <p className={`mt-1 text-xs ${same ? "text-slate-300" : "text-rose-200"}`}>{!baseline ? "No lexical match" : result.ambiguous ? "Does not resolve the ambiguity" : same ? "Agrees with resolver" : "Different lookalike selected"}</p>
        <p className="mt-1 text-xs text-slate-400">BM25 + cosine similarity; ignores the person graph and time clues.</p>
      </div>
      <div className="mt-2 rounded-lg border border-cyan-300/25 bg-cyan-300/5 p-3">
        <div className="text-[11px] uppercase tracking-wide text-cyan-200">Relational + temporal resolver</div>
        <p className="mt-1 text-sm text-white">{result.ambiguous ? "Abstained — please choose a memory" : top?.title || "No match"}</p>
        <p className="mt-1 text-xs text-cyan-100">{result.chosen ? "Selected by you" : result.ambiguous ? "Confidence margin is below 15%" : "Matched using context, relationships, and time"}</p>
        {top && <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
          {[["Graph · S_graph", top.s_graph.toFixed(3)], ["Time · S_time", top.s_time.toFixed(3)], ["Semantic · S_sem", top.s_sem.toFixed(3)], ["Margin · ΔP", result.margin === undefined ? "User-selected" : `${(result.margin * 100).toFixed(1)}%`]].map(([label, value]) => <div key={label} className="rounded bg-black/20 p-2"><dt className="text-slate-400">{label}</dt><dd className="mt-1 font-mono text-base text-white">{value}</dd></div>)}
        </dl>}
      </div>
    </section>
    <TelemetryHUD s={s} />
    <details className="rounded-xl bg-black/20 p-3 text-xs"><summary className="cursor-pointer text-slate-300">Resolver trace</summary><ol className="mt-3 space-y-3">{s.trace.map((step, i) => <li key={i}><strong className="text-cyan-100">{step.title}</strong><p className="mt-1 leading-relaxed text-slate-400">{step.detail}</p></li>)}</ol></details>
  </div>;
}
